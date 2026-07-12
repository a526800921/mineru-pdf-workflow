"""HTML 表格 pretty-print 格式化器。

对 Markdown 文本中的 <table>...</table> 块进行语义保持的可读性格式化：
- 只调整结构标签的换行和缩进，不改变单元格内容、属性、标签。
- 幂等：重复执行不改变输出 hash。
- 失败策略：malformed HTML 抛出 TableFormatError，不写入半格式化文件。

用法:
  from scripts.lib.markdown_table_formatter import format_tables, TableFormatError

  try:
      formatted = format_tables(markdown_text)
  except TableFormatError as e:
      print(f"格式化失败: {e}")
"""

import re
from dataclasses import dataclass
from typing import List, Tuple


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
    不修改 text。
    """
    # 预检：检测 <table> 存在但 </table> 缺失的 malformed HTML
    _table_open_re = re.compile(r"<table\b[^>]*>", re.IGNORECASE)
    open_count = len(_table_open_re.findall(text))
    close_count = text.lower().count("</table>")
    if open_count != close_count:
        raise TableFormatError(
            f"表格标签不匹配: 发现 {open_count} 个 <table>、"
            f"{close_count} 个 </table>"
        )

    # 找出所有表格块的位置
    blocks: list[tuple[int, int]] = []
    for m in _TABLE_RE.finditer(text):
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


def _format_one_table(html: str) -> str:
    """格式化单个 <table>...</table> 块。"""
    # 第一步：检查是否为已格式化块（幂等判断）
    if _is_formatted(html):
        return html

    tokens = _tokenize_table(html)

    # 第二步：校验标签平衡
    _validate_tags(tokens)

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
    - 标签数量匹配
    - td/th 数量匹配
    """
    errors: List[str] = []

    orig_tables = _TABLE_RE.findall(original)
    fmt_tables = _TABLE_RE.findall(formatted)

    if len(orig_tables) != len(fmt_tables):
        errors.append(
            f"表格数量不一致: {len(orig_tables)} -> {len(fmt_tables)}"
        )
        return errors

    for i, (ot, ft) in enumerate(zip(orig_tables, fmt_tables)):
        # 比较各标签数量
        for tag in ("<table", "</table>", "<tr>", "</tr>", "<td", "</td>",
                     "<th", "</th>"):
            oc = ot.count(tag) if tag[0] == "<" else _count_tag(ot, tag)
            fc = ft.count(tag) if tag[0] == "<" else _count_tag(ft, tag)
            if oc != fc:
                errors.append(
                    f"表格 {i+1} 的 {tag} 数量不一致: {oc} -> {fc}"
                )

    return errors


def _count_tag(text: str, tag: str) -> int:
    """统计标签出现次数。"""
    return len(re.findall(rf"<{tag}\b[^>]*>", text, re.IGNORECASE))


# ── 幂等性 ────────────────────────────────────────────────────


def is_idempotent(text: str) -> bool:
    """验证格式化幂等：连续两次 format_tables 输出一致。"""
    first = format_tables(text)
    second = format_tables(first)
    return first == second
