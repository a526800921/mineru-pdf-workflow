"""HTML 表格 pretty-print 格式化器。

对 Markdown 文本中的 <table>...</table> 块进行语义保持的可读性格式化：
- 只调整结构标签的换行和缩进，不改变单元格内容、属性、标签。
- 幂等：重复执行不改变输出 hash。
- 失败策略：malformed HTML 抛出 TableFormatError，不写入半格式化文件。
- 跳过 fenced code block（```）内的伪表格。

用法:
  from scripts.lib.markdown_table_formatter import format_tables, TableFormatError

  try:
      formatted = format_tables(markdown_text)
  except TableFormatError as e:
      print(f"格式化失败: {e}")
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


class TableFormatError(Exception):
    """表格格式化失败（标签不闭合、嵌套异常等）。"""


# ── 常量 ──────────────────────────────────────────────────────

# 匹配表格结构标签（不含 <img/>、<br/>、<!-- --> 等 inline/自闭合标签）
_TAG_RE = re.compile(
    r"<(/?)\s*(table|tr|td|th)\b((?:\s[^>]*)?)>",
    re.IGNORECASE,
)

# 匹配完整 table 块：从 <table ...> 到 </table>
_TABLE_RE = re.compile(r"<table\b[^>]*>.*?</table>", re.DOTALL | re.IGNORECASE)

# 用于从 token 列表重建结构文本的白名单标签
_STRUCT_TAGS = frozenset({"table", "tr", "td", "th"})

# 缩进层级
_INDENT = {
    "table": 0,
    "tr": 2,
    "td": 4,
    "th": 4,
}


@dataclass
class _Token:
    kind: str  # "tag_open", "tag_close", "text"
    tag: str   # "table" / "tr" / "td" / "th", 仅 tag_* 时有效
    raw: str   # 原始文本


# ── 核心格式化 ────────────────────────────────────────────────


def format_tables(text: str) -> str:
    """对 Markdown 文本中所有 <table>...</table> 块执行 pretty-print。

    返回格式化后的完整文本。任一表格解析失败时抛出 TableFormatError，
    不修改 text。跳过 fenced code block 内的 <table> 标签。
    """
    # 预检：检测 <table> 存在但 </table> 缺失的 malformed HTML（不含代码块内）
    real_text = _mask_fenced_blocks(text)
    _table_open_re = re.compile(r"<table\b[^>]*>", re.IGNORECASE)
    open_count = len(_table_open_re.findall(real_text))
    close_count = real_text.lower().count("</table>")
    if open_count != close_count:
        raise TableFormatError(
            f"表格标签不匹配: 发现 {open_count} 个 <table>、"
            f"{close_count} 个 </table>"
        )

    # 找出所有表格块的位置（跳过代码块内）
    fenced_ranges = _fenced_block_ranges(text)
    blocks: list[tuple[int, int]] = []
    for m in _TABLE_RE.finditer(text):
        if _in_fenced_range(m.start(), m.end(), fenced_ranges):
            continue
        blocks.append((m.start(), m.end()))

    if not blocks:
        return text

    # 从后往前替换，保持位置偏移不变
    result = text
    for start, end in reversed(blocks):
        original = result[start:end]
        formatted = _format_one_table(original)
        result = result[:start] + formatted + result[end:]

    return result


def _fenced_block_ranges(text: str) -> List[tuple[int, int]]:
    """返回所有 Markdown fenced code block 的 (start, end) 范围。

    支持 ``` 和 ~~~ 围栏，要求围栏 marker 独占一行。
    """
    ranges: List[tuple[int, int]] = []
    # 匹配行首的 ``` 或 ~~~（可选语言标识）
    fence_re = re.compile(r"^(```|~~~)", re.MULTILINE)
    starts: List[int] = []
    in_fence = False
    for m in fence_re.finditer(text):
        # 确保 marker 在行首且整行只有它（+可选语言标识）
        line_start = m.start()
        # 检查该 marker 是否是已存在 fence 的闭合
        if in_fence:
            # 验证 marker 类型一致
            marker = m.group(1)
            if starts and marker == starts[-1][1]:
                # 闭合当前 fence
                ranges.append((starts[-1][0], m.end()))
                starts.pop()
                in_fence = bool(starts)
            continue
        # 开启新 fence
        marker = m.group(1)
        starts.append((m.start(), marker))
        in_fence = True

    # 未闭合的 fence 延伸到文末
    if starts:
        ranges.append((starts[-1][0], len(text)))

    return ranges


def _in_fenced_range(start: int, end: int, ranges: List[tuple[int, int]]) -> bool:
    """判断位置范围是否与任一 fenced block 范围重叠。"""
    for fs, fe in ranges:
        if start >= fs and end <= fe:
            return True
    return False


def _mask_fenced_blocks(text: str) -> str:
    """将 fenced code block 内容替换为等长空格，用于表外预检。"""
    result = list(text)
    for fs, fe in _fenced_block_ranges(text):
        for i in range(fs, min(fe, len(text))):
            # 保留换行以保持行数一致；其他字符替换为空格
            if result[i] != '\n':
                result[i] = ' '
    return ''.join(result)


def _format_one_table(html: str) -> str:
    """格式化单个 <table>...</table> 块。"""
    # 第一步：无条件校验标签平衡（即使外观已格式化也必须校验）
    tokens = _tokenize_table(html)
    _validate_tags(tokens)

    # 第二步：已格式化且校验通过 → 幂等跳过
    if _is_formatted(html):
        return html

    # 第三步：重建格式化输出
    return _rebuild(tokens)


def _tokenize_table(html: str) -> List[_Token]:
    """将表格 HTML 拆分为 token 列表。

    每个 token 分为三类：
    - tag_open: <table>, <tr>, <td colspan="2">, <th> 等
    - tag_close: </table>, </tr>, </td>, </th>
    - text: 标签间的文本（单元格内容）

    标签间的空白字符被隔离为独立的 text token，重建时再决定是否保留。
    """
    tokens: List[_Token] = []
    pos = 0

    for m in _TAG_RE.finditer(html):
        # 标签前的文本
        if m.start() > pos:
            text = html[pos : m.start()]
            tokens.append(_Token(kind="text", tag="", raw=text))

        is_close = m.group(1) == "/"
        tag = m.group(2).lower()
        full = m.group(0)
        kind = "tag_close" if is_close else "tag_open"
        tokens.append(_Token(kind=kind, tag=tag, raw=full))

        pos = m.end()

    # 最后的尾随文本
    if pos < len(html):
        tokens.append(_Token(kind="text", tag="", raw=html[pos:]))

    return tokens


def _validate_tags(tokens: List[_Token]) -> None:
    """校验标签平衡：open 和 close 数量一致。"""
    stack: List[str] = []
    for t in tokens:
        if t.kind == "tag_open":
            stack.append(t.tag)
        elif t.kind == "tag_close":
            if not stack:
                raise TableFormatError(f"多余的闭合标签: {t.raw}")
            expected = stack.pop()
            if expected != t.tag:
                raise TableFormatError(
                    f"标签不匹配: 期望 </{expected}>，实际 {t.raw}"
                )
    if stack:
        raise TableFormatError(f"未闭合标签: <{'> <'.join(stack)}>")


def _is_formatted(html: str) -> bool:
    """快速判断表格是否已格式化。

    标准：<table> 后紧接换行即为已格式化。
    """
    # <table> 或 <table ...> 后应该紧跟 \n
    m = re.match(r"<table\b[^>]*>\s*\n", html, re.IGNORECASE)
    return m is not None


def _rebuild(tokens: List[_Token]) -> str:
    """从 token 列表重建带缩进和换行的格式化表格文本。"""
    parts: List[str] = []

    i = 0
    while i < len(tokens):
        t = tokens[i]

        if t.kind == "tag_open":
            tag = t.tag

            if tag == "table":
                parts.append(t.raw)
                # 不追加换行：表格边界换行由上下文提供

            elif tag == "tr":
                tr_indent = " " * _INDENT["tr"]
                parts.append(f'\n{tr_indent}{t.raw}')

            elif tag in ("td", "th"):
                td_indent = " " * _INDENT["td"]
                parts.append(f'\n{td_indent}{t.raw}')

                # 收集 cell 内容直到 </td> / </th>
                cell_parts: List[str] = []
                i += 1
                while i < len(tokens):
                    ct = tokens[i]
                    if ct.kind == "tag_close" and ct.tag == tag:
                        break
                    # 保留 cell 内的全部内容，但压缩纯空白为单个空格
                    if ct.kind == "text":
                        cell_parts.append(_cell_content(ct.raw, cell_parts))
                    i += 1

                cell_content = "".join(cell_parts)
                parts.append(cell_content)

                # 闭合标签
                close_raw = tokens[i].raw if i < len(tokens) else f"</{tag}>"
                parts.append(close_raw)

            else:
                # 不应出现
                parts.append(t.raw)

        elif t.kind == "tag_close":
            tag = t.tag

            if tag == "table":
                parts.append(f"\n{t.raw}")

            elif tag == "tr":
                tr_close_indent = " " * _INDENT["tr"]
                parts.append(f'\n{tr_close_indent}{t.raw}')

            else:
                # td/th 的闭合标签已在 tag_open 分支处理
                pass

        elif t.kind == "text":
            # 标签间空白直接丢弃（非 cell 内）
            stripped = t.raw.strip()
            if stripped:
                parts.append(stripped)

        i += 1

    result = "".join(parts)

    # 规范化尾随空白
    result = re.sub(r"[ \t]+$", "", result, flags=re.MULTILINE)
    # 不许出现全空白行
    result = re.sub(r"\n[ \t]+\n", "\n", result)

    return result


def _cell_content(raw: str, existing_parts: List[str]) -> str:
    """处理单元格内容：保留实质内容，压缩纯空白。

    existing_parts 为空且 raw 仅含空白 → 返回空字符串（<td></td>）
    existing_parts 非空 → raw 为纯空白时返回单个空格（词间分隔）
    """
    if existing_parts:
        # 已有内容，纯空白变为一个空格
        if not raw.strip():
            return " "
    else:
        # 还没有内容，纯空白丢弃
        if not raw.strip():
            return ""
    # 有内容，保留原文
    return raw


# ── 结构校验 ──────────────────────────────────────────────────


def validate_structure(original: str, formatted: str) -> List[str]:
    """校验格式化前后表格结构一致。

    返回错误列表；空列表表示通过。

    校验项:
    - 表格数量
    - 逐表：行数、逐行列数
    - 逐格：文本内容、colspan、rowspan
    - <img> 标签数量
    """
    errors: List[str] = []

    orig_tables = _extract_all_tables(original)
    fmt_tables = _extract_all_tables(formatted)

    if len(orig_tables) != len(fmt_tables):
        errors.append(
            f"表格数量不一致: {len(orig_tables)} → {len(fmt_tables)}"
        )
        return errors

    for ti, (ot, ft) in enumerate(zip(orig_tables, fmt_tables)):
        # 行数
        if len(ot) != len(ft):
            errors.append(
                f"表格 {ti+1} 行数不一致: {len(ot)} → {len(ft)}"
            )
            continue

        for ri, (orow, frow) in enumerate(zip(ot, ft)):
            # 列数
            if len(orow) != len(frow):
                errors.append(
                    f"表格 {ti+1} 第 {ri+1} 行列数不一致: "
                    f"{len(orow)} → {len(frow)}"
                )
                continue

            for ci, (ocell, fcell) in enumerate(zip(orow, frow)):
                # 文本内容（压缩空白后比较）
                otext = _normalize_cell_text(ocell.get("text", ""))
                ftext = _normalize_cell_text(fcell.get("text", ""))
                if otext != ftext:
                    errors.append(
                        f"表格 {ti+1} ({ri+1},{ci+1}) 文本不一致: "
                        f"'{otext[:50]}' → '{ftext[:50]}'"
                    )

                # colspan
                ocs = ocell.get("colspan", 1)
                fcs = fcell.get("colspan", 1)
                if ocs != fcs:
                    errors.append(
                        f"表格 {ti+1} ({ri+1},{ci+1}) colspan 不一致: "
                        f"{ocs} → {fcs}"
                    )

                # rowspan
                ors = ocell.get("rowspan", 1)
                frs = fcell.get("rowspan", 1)
                if ors != frs:
                    errors.append(
                        f"表格 {ti+1} ({ri+1},{ci+1}) rowspan 不一致: "
                        f"{ors} → {frs}"
                    )

        # 表格内 <img> 数量
        o_imgs = _count_imgs(ot)
        f_imgs = _count_imgs(ft)
        if o_imgs != f_imgs:
            errors.append(
                f"表格 {ti+1} <img> 数不一致: {o_imgs} → {f_imgs}"
            )

    return errors


def _extract_all_tables(md_text: str) -> List[List[List[dict]]]:
    """从 Markdown 提取所有 HTML 表格，返回 tables=[rows=[cells, ...], ...]。

    每个 cell: {"colspan": int, "rowspan": int, "text": str}
    跳过 fenced code block 内的表格。
    """
    tables: List[List[List[dict]]] = []
    fenced_ranges = _fenced_block_ranges(md_text)

    # 用 _TABLE_RE 找出表格块，逐块解析
    for m in _TABLE_RE.finditer(md_text):
        if _in_fenced_range(m.start(), m.end(), fenced_ranges):
            continue
        html = m.group()
        rows = _parse_table_html(html)
        tables.append(rows)

    return tables


def _parse_table_html(html: str) -> List[List[dict]]:
    """解析单个 <table>...</table> HTML 为 rows 列表。

    每个 cell: {"colspan": int, "rowspan": int, "text": str}
    """
    tokens = _tokenize_table(html)
    rows: List[List[dict]] = []
    cur_row: List[dict] = []
    cur_cell = None
    cur_text: List[str] = []

    i = 0
    while i < len(tokens):
        t = tokens[i]

        if t.kind == "tag_open" and t.tag == "tr":
            cur_row = []

        elif t.kind == "tag_open" and t.tag in ("td", "th"):
            cs = _extract_attr_int(t.raw, "colspan")
            rs = _extract_attr_int(t.raw, "rowspan")
            cur_cell = {"colspan": cs, "rowspan": rs, "text": ""}
            cur_text = []

        elif t.kind == "tag_close" and t.tag in ("td", "th"):
            if cur_cell is not None:
                cur_cell["text"] = "".join(cur_text)
                cur_row.append(cur_cell)
                cur_cell = None
                cur_text = []

        elif t.kind == "tag_close" and t.tag == "tr":
            if cur_row:
                rows.append(cur_row)
            cur_row = []

        elif t.kind == "text":
            if cur_cell is not None:
                cur_text.append(t.raw)

        i += 1

    # 未闭合的尾行
    if cur_cell is not None and cur_row is not None:
        cur_cell["text"] = "".join(cur_text)
        cur_row.append(cur_cell)
    if cur_row:
        rows.append(cur_row)

    return rows


def _extract_attr_int(tag_raw: str, attr: str) -> int:
    """从标签原始文本中提取整数属性值，默认 1。"""
    m = re.search(rf'{attr}\s*=\s*["\']?(\d+)', tag_raw, re.IGNORECASE)
    if m:
        try:
            v = int(m.group(1))
            return max(v, 1)
        except (TypeError, ValueError):
            pass
    return 1


def _normalize_cell_text(text: str) -> str:
    """规范化单元格文本用于比较：压缩连续空白。"""
    return re.sub(r"\s+", " ", text).strip()


def _count_imgs(rows: List[List[dict]]) -> int:
    """统计所有单元格中 <img 出现的总次数。"""
    count = 0
    for row in rows:
        for cell in row:
            count += cell.get("text", "").count("<img ")
    return count


# ── 幂等性 ────────────────────────────────────────────────────


def is_idempotent(text: str) -> bool:
    """验证格式化幂等：连续两次 format_tables 输出一致。"""
    first = format_tables(text)
    second = format_tables(first)
    return first == second


# ── manifest 同步 ──────────────────────────────────────────────


def finalize_markdown_formatting(pkg_dir: Path) -> Dict[str, Any]:
    """格式化 canonical Markdown 并同步 manifest。

    仅在表格内容发生变化时执行写入。变化时：
    1. 保存格式化前备份 data/pre_format_md_{hash[:16]}.md
    2. 原地更新 canonical Markdown
    3. 运行 validate_structure 校验结构一致性
    4. 更新 manifest.json 的 formatting 块和 fixes.markdown_sha256

    返回值:
      {"status": "ok"|"unchanged"|"error",
       "md_path": str,
       "source_sha256": str (变化时),
       "formatted_sha256": str (变化时),
       "error": str (出错时)}
    """
    import hashlib
    import json

    result: Dict[str, Any] = {"status": "ok", "md_path": ""}

    manifest_path = pkg_dir / "manifest.json"
    if not manifest_path.exists():
        return {"status": "error", "md_path": "", "error": "manifest.json 不存在"}

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return {"status": "error", "md_path": "", "error": f"manifest 解析失败: {e}"}

    md_rel = manifest.get("files", {}).get("markdown")
    if not md_rel:
        return {"status": "unchanged", "md_path": ""}
    md_path = pkg_dir / md_rel
    if not md_path.exists():
        return {"status": "error", "md_path": str(md_path), "error": "Markdown 不存在"}

    result["md_path"] = str(md_path)
    original_text = md_path.read_text(encoding="utf-8")

    try:
        formatted_text = format_tables(original_text)
    except TableFormatError as e:
        return {"status": "error", "md_path": str(md_path), "error": f"格式化失败: {e}"}

    if formatted_text == original_text:
        # TOC 后处理等步骤可能只修改表格外文本。即使本次没有发生
        # pretty-print，也必须把已有 formatting/fixes hash 同步到当前 MD。
        current_hash = hashlib.sha256(original_text.encode("utf-8")).hexdigest()
        formatting = manifest.get("formatting")
        if (
            isinstance(formatting, dict)
            and formatting.get("status") in ("applied", "verified")
            and formatting.get("formatted_markdown_sha256") != current_hash
        ):
            original_manifest_text = manifest_path.read_text(encoding="utf-8")
            formatting["formatted_markdown_sha256"] = current_hash
            if isinstance(manifest.get("fixes"), dict):
                manifest["fixes"]["markdown_sha256"] = current_hash
            try:
                _atomic_write(
                    manifest_path,
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                )
            except Exception as exc:
                # manifest 单文件原子替换失败时恢复原始字节内容。
                try:
                    _atomic_write(manifest_path, original_manifest_text)
                except Exception as rollback_exc:  # pragma: no cover
                    return {
                        "status": "error",
                        "md_path": str(md_path),
                        "error": f"manifest hash 同步失败且回滚失败: {rollback_exc}",
                    }
                return {
                    "status": "error",
                    "md_path": str(md_path),
                    "error": f"manifest hash 同步失败: {exc}",
                }
            return {
                "status": "ok",
                "md_path": str(md_path),
                "formatting_status": formatting.get("status"),
                "formatted_sha256": current_hash,
                "hash_synced": True,
            }
        return {"status": "unchanged", "md_path": str(md_path)}

    # 计算 hash
    source_hash = hashlib.sha256(original_text.encode("utf-8")).hexdigest()
    formatted_hash = hashlib.sha256(formatted_text.encode("utf-8")).hexdigest()

    # 结构一致性校验（写入前在内存中完成）
    struct_errors = validate_structure(original_text, formatted_text)
    formatting_status = "verified" if not struct_errors else "applied"

    # 保存格式化前备份，并以事务方式提交 Markdown + manifest。
    data_dir = pkg_dir / "data"
    data_dir_created = not data_dir.exists()
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_path = data_dir / f"pre_format_md_{source_hash[:16]}.md"
    original_manifest_text = manifest_path.read_text(encoding="utf-8")
    backup_existed = backup_path.exists()
    if backup_existed and backup_path.read_text(encoding="utf-8") != original_text:
        if data_dir_created and not any(data_dir.iterdir()):
            data_dir.rmdir()
        return {
            "status": "error",
            "md_path": str(md_path),
            "error": f"格式化前备份内容不匹配: {backup_path}",
        }

    # 更新 manifest（内存中），在任何文件替换前完成全部内容构造。
    manifest["formatting"] = {
        "schema_version": 1,
        "mode": "merge_time",
        "status": formatting_status,
        "source_markdown_sha256": source_hash,
        "formatted_markdown_sha256": formatted_hash,
    }
    if "fixes" in manifest:
        manifest["fixes"]["markdown_sha256"] = formatted_hash
    manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

    backup_created = False
    markdown_replaced = False
    manifest_replaced = False
    try:
        if not backup_existed:
            _atomic_write(backup_path, original_text)
            backup_created = True

        _atomic_write(md_path, formatted_text)
        markdown_replaced = True

        _atomic_write(manifest_path, manifest_text)
        manifest_replaced = True
    except Exception as exc:
        rollback_errors = []
        if markdown_replaced:
            try:
                _atomic_write(md_path, original_text)
            except Exception as rollback_exc:  # pragma: no cover - 极端 I/O 故障
                rollback_errors.append(f"Markdown 回滚失败: {rollback_exc}")
        if manifest_replaced:
            try:
                _atomic_write(manifest_path, original_manifest_text)
            except Exception as rollback_exc:  # pragma: no cover - 极端 I/O 故障
                rollback_errors.append(f"manifest 回滚失败: {rollback_exc}")
        if backup_created:
            try:
                backup_path.unlink(missing_ok=True)
            except OSError as rollback_exc:  # pragma: no cover - 极端 I/O 故障
                rollback_errors.append(f"备份清理失败: {rollback_exc}")
        if data_dir_created:
            try:
                if data_dir.exists() and not any(data_dir.iterdir()):
                    data_dir.rmdir()
            except OSError as rollback_exc:  # pragma: no cover - 极端 I/O 故障
                rollback_errors.append(f"data 目录清理失败: {rollback_exc}")
        detail = f"格式化事务失败: {exc}"
        if rollback_errors:
            detail += "；" + "；".join(rollback_errors)
        return {"status": "error", "md_path": str(md_path), "error": detail}

    result.update({
        "source_sha256": source_hash,
        "formatted_sha256": formatted_hash,
        "formatting_status": formatting_status,
        "structure_errors": struct_errors,
    })
    return result


def _atomic_write(path: Path, content: str) -> None:
    """原子写入：先写临时文件，再 os.rename 替换目标。

    确保不产生半写入文件。失败时目标文件保持不变。
    """
    import os
    import tempfile

    parent = str(path.parent)
    suffix = path.suffix
    fd, tmp_path = tempfile.mkstemp(dir=parent, suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, str(path))
        tmp_path = ""
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except FileNotFoundError:
                pass
