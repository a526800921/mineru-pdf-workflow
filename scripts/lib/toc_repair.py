"""TOC 修复：优先用 PDF 内置大纲，fallback 到文本层 x 坐标。

用法：
  import toc_repair
  toc_repair.repair(pdf_path, segments_dir, validate_tmp)     # 段级（纯 TOC 段覆盖写）
  toc_repair.repair_merged(pdf_path, merged_md, validate_tmp) # 合并级（锚点感知，不丢失非目录页）

产出：
  - 更新 TOC 段的 Markdown，带缩进层级（按物理目录页归属）
  - 输出包根目录写入 toc_tree.json（[{title, target_page, toc_page, depth}, ...]）
  - 输出包根目录写入 toc.md（无锚点连续目录展示视图）
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import fitz
except Exception:
    print("TOC 修复跳过：PyMuPDF 不可用", file=sys.stderr)
    sys.exit(0)

TITLE_DOTS = re.compile(r'^(\S.+?)\s*[.]{3,}\s*$')
DOTS_NUM = re.compile(r'^\s*[.]{3,}\s*(\d+)\s*$')
X_LEVEL_TOLERANCE = 8.0


# ── 方案 A：PDF 内置大纲 ──────────────────────────────────────────

def _build_from_outline(doc) -> list[dict] | None:
    """从 PDF 内置大纲提取 TOC，失败返回 None。"""
    toc = doc.get_toc()
    if not toc:
        return None

    entries = []
    for level, title, page in toc:
        title = title.strip()
        if len(title) < 2:
            continue
        entries.append({
            "title": title,
            "page": page,
            "depth": level - 1,  # get_toc level 是 1-based
        })
    return entries if entries else None


# ── 方案 B：文本层 x 坐标（fallback）──────────────────────────────

def _extract_entries_from_page(doc, page_index: int) -> list[dict]:
    """从单页提取 TOC 条目，返回 [{title, page, x0, toc_page}, ...].

    page 是条目指向页(target)，toc_page 是条目所在物理目录页(1-based)。
    """
    blocks = doc[page_index].get_text("dict")["blocks"]

    text_lines = []
    for b in blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            text = "".join(s.get("text", "") for s in line.get("spans", []))
            y = line["bbox"][1]
            x0 = line["bbox"][0]
            text_lines.append((y, x0, text))

    text_lines.sort(key=lambda t: t[0])
    texts = [t[2] for t in text_lines]
    x0s = [t[1] for t in text_lines]

    entries = []
    prev_key = None
    for i in range(len(texts) - 1):
        title_m = TITLE_DOTS.match(texts[i])
        num_m = DOTS_NUM.match(texts[i + 1])
        if title_m and num_m:
            title = title_m.group(1).strip()
            page_ref = num_m.group(1)
            if len(title) >= 2 and not title.isdigit():
                key = (title, page_ref)
                if key == prev_key:
                    continue
                entries.append({
                    "title": title,
                    "page": int(page_ref),
                    "x0": x0s[i],
                    "toc_page": page_index + 1,  # 物理目录页(1-based)，提取即归属
                })
                prev_key = key

    return entries


def _compute_depths(entries: list[dict]) -> None:
    """原地为 entries 添加 depth 字段，基于 x 坐标聚类。"""
    if not entries:
        return

    x0_values = sorted(set(e["x0"] for e in entries))
    clusters = []
    current_cluster = [x0_values[0]]
    for x in x0_values[1:]:
        if x - current_cluster[-1] <= X_LEVEL_TOLERANCE:
            current_cluster.append(x)
        else:
            clusters.append(sum(current_cluster) / len(current_cluster))
            current_cluster = [x]
    clusters.append(sum(current_cluster) / len(current_cluster))

    for e in entries:
        best_idx = 0
        best_dist = abs(e["x0"] - clusters[0])
        for idx, cx in enumerate(clusters):
            dist = abs(e["x0"] - cx)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        e["depth"] = best_idx


# ── 合并 md 级修复 ─────────────────────────────────────────────────

def _normalize_title(text: str) -> str:
    """规范化标题用于完整行/词边界匹配：去除所有空白。"""
    return re.sub(r'\s', '', text)


def _page_title_keys(doc, page_num: int) -> set:
    """返回某物理页(1-based)所有 TOC 行标题的规范化 key 集合。

    复用 _extract_entries_from_page 的标题解析，保证匹配的是完整目录行标题
    而非页面文本的任意子串——因此 '制动' 不会命中 '前制动手柄'。
    """
    return {
        _normalize_title(e["title"])
        for e in _extract_entries_from_page(doc, page_num - 1)
    }


def _assign_to_toc_pages(
    entries: list[dict], doc, toc_page_nums: list[int]
) -> dict[int, list]:
    """将条目按物理目录页归属。

    归属优先级（见 toc-page-physical-attribution-fix 设计契约）：
    1. 条目自带 toc_page（提取即归属）时直接使用，不回溯猜测；
    2. 否则用规范化完整行/词边界匹配唯一物理页（用于内置大纲等无 toc_page 来源）；
    3. 无法唯一归属（0 页或多页命中）时进入 review，不强制分配、不做字符集模糊回退。
    """
    assigned = {pn: [] for pn in toc_page_nums}

    # 单目录页无归属歧义：条目只能属于该页，直接归属
    if len(toc_page_nums) == 1:
        assigned[toc_page_nums[0]] = list(entries)
        return assigned

    review = []
    page_keys = None  # 完整行匹配所需，仅当存在缺 toc_page 的条目时才懒构建

    for e in entries:
        # 1. 提取即归属：条目已知其物理目录页
        tp = e.get("toc_page")
        if tp in assigned:
            assigned[tp].append(e)
            continue

        # 2. 完整行/词边界匹配到唯一物理页
        if page_keys is None:
            page_keys = {pn: _page_title_keys(doc, pn) for pn in toc_page_nums}
        key = _normalize_title(e["title"])
        hits = [pn for pn in toc_page_nums if key in page_keys[pn]]
        if len(hits) == 1:
            assigned[hits[0]].append(e)
        else:
            # 3. 0 或多页命中 → 无法唯一归属，进入 review（不强制分配）
            review.append(e)

    if review:
        titles = ", ".join(e["title"] for e in review[:5])
        more = "…" if len(review) > 5 else ""
        print(
            f"  TOC 归属 review: {len(review)} 条无法唯一归属物理页，"
            f"不自动分配（{titles}{more}）",
            file=sys.stderr,
        )

    return assigned


def _build_merged_toc_block(
    first_page: int, last_page: int, by_page: dict[int, list]
) -> str:
    """生成合并 md 中替换 TOC 页的文本块，使用段级锚点替代旧的逐页锚点。"""
    lines = []
    for page in range(first_page, last_page + 1):
        lines.append(f"<!-- pages {page}-{page} -->")
        if page == first_page:
            lines.append("## 目录\n")
        for e in by_page.get(page, []):
            indent = "  " * e["depth"]
            lines.append(f"{indent}- {e['title']} {e['page']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def repair_merged(pdf_path: Path, merged_md_path: Path, validate_tmp: str) -> int:
    """在合并 Markdown 上用段级锚点精确替换目录页内容。
    只替换 TOC 页范围的文本，非目录页完全保留。
    使用 `<!-- pages N-M -->` 段级锚点替代旧的 `<!-- page N -->` 逐页锚点。
    """
    with open(validate_tmp) as f:
        report = json.load(f)

    toc_segs = [
        s for s in report["segments"]
        if s.get("page_type_summary", {}).get("toc", 0) > 0
    ]
    if not toc_segs:
        return 0

    doc = fitz.open(str(pdf_path))

    # 方案 A：PDF 内置大纲
    entries = _build_from_outline(doc)
    source = "PDF 内置大纲"

    # 方案 B：文本层 fallback
    if not entries:
        entries = []
        for seg in toc_segs:
            for p in range(seg["start_page"] - 1, min(seg["end_page"], doc.page_count)):
                entries.extend(_extract_entries_from_page(doc, p))
        if entries:
            _compute_depths(entries)
            source = "文本层 x 坐标"

    if not entries:
        doc.close()
        return 0

    # 收集所有 TOC 页号（转成全局 1-based，对齐合并 md 的段级锚点页码）
    all_toc_pages = set()
    for seg in toc_segs:
        for p in seg.get("pages", []):
            if p.get("page_type") == "toc":
                # pages[].page 是文档级 0-based 页索引（pdf-validate 产出）
                all_toc_pages.add(p["page"] + 1)
    if not all_toc_pages:
        doc.close()
        return 0

    first_toc = min(all_toc_pages)
    last_toc = max(all_toc_pages)
    md_text = merged_md_path.read_text(encoding="utf-8")

    # 按实际目录页分配条目
    toc_page_nums = sorted(all_toc_pages)
    by_page = _assign_to_toc_pages(entries, doc, toc_page_nums)
    _backfill_toc_page(by_page)  # 将归属物理页回填到 entries 的 toc_page
    # 已归属有序条目：toc.md/toc_tree 与合并 md 目录块同源，排除未归属条目
    assigned = _ordered_assigned_entries(by_page, toc_page_nums)

    # 构造替换用 TOC 块
    toc_block = _build_merged_toc_block(first_toc, last_toc, by_page)

    # 定位替换范围：用 `<!-- pages {N}-... -->` 段级锚点替代旧的逐页锚点
    seg_anchor_re = re.compile(r"^<!-- pages (\d+)-(\d+) -->\s*$", re.MULTILINE)
    all_seg_anchors = [(int(a), int(b), m.start(), m.end())
                       for m in seg_anchor_re.finditer(md_text)
                       for a, b in [(int(m.group(1)), int(m.group(2)))]]

    # 找到页 first_toc 所在的段级锚点位置（锚点页号 ≤ first_toc ≤ 锚点末页）
    start_anchor = next(
        (s, e, pos, end) for s, e, pos, end in all_seg_anchors
        if s <= first_toc <= e
    )
    idx_start = start_anchor[2]  # pos
    start_anchor_end = start_anchor[3]  # end

    # 找到页 last_toc + 1 所在的段级锚点（锚点范围外则为文件尾）
    next_page = last_toc + 1
    try:
        end_anchor = next(
            (s, e, pos, end) for s, e, pos, end in all_seg_anchors
            if s <= next_page <= e
        )
        idx_end = end_anchor[2]  # pos
    except StopIteration:
        idx_end = -1

    if idx_end != -1:
        new_text = md_text[:idx_start] + toc_block + md_text[idx_end:]
    else:
        # 最后一页无后续锚点，替换到文件尾
        new_text = md_text[:idx_start] + toc_block

    merged_md_path.write_text(new_text, encoding="utf-8")

    # 写入 toc_tree.json（机器权威结构）和 toc.md（无锚点展示视图）
    # 均基于已归属有序条目，与合并 md 目录块严格一致
    _write_toc_tree(merged_md_path.parent, assigned)
    _write_toc_md(merged_md_path.parent, assigned)

    print(
        f"  合并级 TOC 修复: 页码 {first_toc}–{last_toc}, "
        f"{len(assigned)}/{len(entries)} 条目已归属"
        f"（{_depth_distribution(assigned)}），来源: {source}",
        file=sys.stderr,
    )
    doc.close()
    return 1


# ── 公共 ───────────────────────────────────────────────────────────

def _build_markdown(entries: list[dict]) -> str:
    """生成带缩进的 Markdown TOC。"""
    lines = ["## 目录\n"]
    for e in entries:
        indent = "  " * e["depth"]
        lines.append(f"{indent}- {e['title']} {e['page']}")
    return "\n".join(lines) + "\n"


def _build_toc_md(entries: list[dict]) -> str:
    """生成无锚点连续目录展示视图（toc.md）。

    结构与段级 Markdown 一致，仅用途不同：toc.md 是供人工阅读/前端渲染的
    干净展示视图，不含任何 <!-- pages N-M --> 段级锚点，也不重新解析或猜测页码。
    """
    return _build_markdown(entries)


def _write_toc_md(pkg_root: Path, entries: list[dict]):
    """在包根目录写入无锚点展示视图 toc.md（由同一份已归属条目生成）。"""
    (pkg_root / "toc.md").write_text(_build_toc_md(entries), encoding="utf-8")


def _backfill_toc_page(by_page: dict[int, list]) -> None:
    """将归属结果的物理目录页回填到每个条目的 toc_page 字段（原地）。"""
    for pn, rows in by_page.items():
        for e in rows:
            e["toc_page"] = pn


def _ordered_assigned_entries(
    by_page: dict[int, list], toc_page_nums: list[int]
) -> list[dict]:
    """按物理目录页升序展开已归属条目，顺序与合并 md 目录块一致。

    未唯一归属的条目不在 by_page 中，因此自然被排除——保证
    toc.md / toc_tree.json 的条目集合与合并 md 目录块严格一致。
    """
    ordered = []
    for pn in sorted(toc_page_nums):
        ordered.extend(by_page.get(pn, []))
    return ordered


def _depth_distribution(entries: list[dict]) -> str:
    c = Counter(e["depth"] for e in entries)
    return ", ".join(f"{d}级:{c[d]}" for d in sorted(c))


def _write_toc_tree(pkg_root: Path, entries: list[dict]):
    """写机器权威目录结构 toc_tree.json。

    区分 target_page（条目指向正文页）与 toc_page（条目所在物理目录页）；
    未能唯一归属物理页的条目 toc_page 为 null。
    """
    tree_data = [
        {
            "title": e["title"],
            "target_page": e["page"],
            "toc_page": e.get("toc_page"),
            "depth": e["depth"],
        }
        for e in entries
    ]
    tree_path = pkg_root / "toc_tree.json"
    tree_path.write_text(
        json.dumps(tree_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 主入口 ─────────────────────────────────────────────────────────

def repair(pdf_path: Path, segments_dir: Path, validate_tmp: str) -> int:
    """修复所有 TOC 段，返回修复段数。"""
    with open(validate_tmp) as f:
        report = json.load(f)

    toc_segs = [
        s for s in report["segments"]
        if s.get("page_type_summary", {}).get("toc", 0) > 0
    ]
    if not toc_segs:
        return 0

    doc = fitz.open(str(pdf_path))
    fixed = 0

    # 方案 A：内置大纲
    entries = _build_from_outline(doc)
    source = "PDF 内置大纲"

    # 方案 B：文本层 fallback
    if not entries:
        entries = []
        for seg in toc_segs:
            for p in range(seg["start_page"] - 1, min(seg["end_page"], doc.page_count)):
                entries.extend(_extract_entries_from_page(doc, p))
        if entries:
            _compute_depths(entries)
            source = "文本层 x 坐标"
        else:
            doc.close()
            return 0

    if not entries:
        doc.close()
        return 0

    # 收集所有物理目录页，按物理页归属条目（与 repair_merged 同一规则）
    toc_page_nums = sorted({
        p["page"] + 1
        for seg in toc_segs
        for p in seg.get("pages", [])
        if p.get("page_type") == "toc"
    })
    by_page = _assign_to_toc_pages(entries, doc, toc_page_nums) if toc_page_nums else None
    if by_page:
        _backfill_toc_page(by_page)
        tree_entries = _ordered_assigned_entries(by_page, toc_page_nums)
    else:
        tree_entries = entries

    # 写回纯 TOC 段的 Markdown（每段只写归属该段物理页的条目，避免整本目录重复；
    # 跳过混合段：有非目录页，避免覆盖丢失内容）
    for seg in toc_segs:
        total_pages = seg["end_page"] - seg["start_page"] + 1
        toc_pages = seg.get("page_type_summary", {}).get("toc", 0)
        if toc_pages < total_pages:
            print(
                f"  {seg['name']}: 跳过混合段（{toc_pages}/{total_pages} 页目录），"
                f"保留 MinerU 原始输出",
                file=sys.stderr,
            )
            continue
        seg_dir = segments_dir / seg["name"]
        md_files = sorted(seg_dir.rglob("*.md"))
        if not md_files:
            continue
        if by_page:
            seg_entries = [
                e for pn in range(seg["start_page"], seg["end_page"] + 1)
                for e in by_page.get(pn, [])
            ]
        else:
            # 无物理页信息时回退到全部条目（保持旧行为，不丢目录）
            seg_entries = entries
        md_path = md_files[0]
        md_path.write_text(_build_markdown(seg_entries), encoding="utf-8")
        fixed += 1

    # 写入 toc_tree.json（已归属有序条目，与段级/合并级目录一致）
    _write_toc_tree(segments_dir.parent, tree_entries)

    print(f"  {fixed} 个 TOC 段: {len(tree_entries)} 条目（{_depth_distribution(tree_entries)}），来源: {source}", file=sys.stderr)
    doc.close()
    return fixed


def verify_entry_recall(pdf_path: Path, segments_dir: Path, validate_tmp: str) -> int:
    """TOC 再验证：条目召回率。"""
    with open(validate_tmp) as f:
        vreport = json.load(f)

    toc_segs = [
        s for s in vreport["segments"]
        if s.get("page_type_summary", {}).get("toc", 0) > 0
    ]
    if not toc_segs:
        return 0

    doc = fitz.open(str(pdf_path))

    # 优先用大纲
    entries = _build_from_outline(doc)
    if not entries:
        entries = []
        for seg in toc_segs:
            for p in range(seg["start_page"] - 1, min(seg["end_page"], doc.page_count)):
                entries.extend(_extract_entries_from_page(doc, p))

    if not entries:
        doc.close()
        return 0

    titles = {e["title"] for e in entries}
    updated = 0

    for seg in toc_segs:
        seg_dir = segments_dir / seg["name"]
        md_files = sorted(seg_dir.rglob("*.md"))
        if not md_files:
            continue
        md_text = md_files[0].read_text(encoding="utf-8", errors="replace")

        found = sum(1 for t in titles if t in md_text)
        recall = found / len(titles)
        new_coverage = round(recall, 4)
        new_status = "passed" if recall >= 0.9 else "suspicious"
        new_decision = "pass" if recall >= 0.9 else "review_only"

        print(f"  {seg['name']}: 条目召回 {found}/{len(titles)} ({recall:.0%}) → {new_status}", file=sys.stderr)

        seg["coverage"] = new_coverage
        seg["status"] = new_status
        seg["decision"] = new_decision
        seg["reason"] = "toc_entry_recall"
        seg["rerunnable"] = False
        for p in seg.get("pages", []):
            p["coverage"] = new_coverage
            p["status"] = new_status
            p["decision"] = new_decision
            p["reason"] = "toc_entry_recall"
        updated += 1

    doc.close()

    if updated:
        with open(validate_tmp, "w") as f:
            json.dump(vreport, f, ensure_ascii=False)
        all_ok = all(s["status"] == "passed" for s in vreport["segments"])
        print(f"TOC 再验证完成: {updated} 段，{'全部通过' if all_ok else '仍有未通过'}", file=sys.stderr)

    return updated
