#!/usr/bin/env python3
"""逐页锚点生成（per-page-anchors 阶段 1，方案 A′ + X）。

对一个分段的原生 Markdown，依据同段 content_list.json 的 `page_idx` 分组，用
首尾双指纹在原生 md 上定位每页边界，插入 `<!-- page N -->`（绝对 PDF 页码）。

- A′：不重建正文，只插注释锚点 —— 后处理成果（`toc_repair` 等）与正文内容零改动。
- X（宁缺毋误）：首/尾任一指纹命中即定位；个别页失配用相邻锚点近似补并记
  warning；某页无内容块（纯空白页）顺序补；段内多数页失配 → 整段回退，只保留
  段级锚点。

零依赖：仅标准库。
"""
import re

# 逐页锚点行（含行尾换行），用于 strip 校验「正文零改动」不变量。
PAGE_ANCHOR_LINE_RE = re.compile(r"<!-- page \d+ -->\n")
_FP_LEN = 40  # 指纹取去空白后前 40 字符


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _norm_with_index(text: str):
    """返回 (norm_str, index)：index[i] = norm 第 i 个字符在原文中的偏移。"""
    chars, index = [], []
    for i, ch in enumerate(text):
        if not ch.isspace():
            chars.append(ch)
            index.append(i)
    return "".join(chars), index


def fingerprint(block: dict) -> str:
    """块指纹：table→table_body，image→img_path，其余→text，去空白取前 40 字符。"""
    t = block.get("type")
    if t == "table":
        return _norm(block.get("table_body", ""))[:_FP_LEN]
    if t == "image":
        return _norm(block.get("img_path", ""))[:_FP_LEN]
    return _norm(block.get("text", ""))[:_FP_LEN]


def group_by_page(items: list) -> dict:
    """按 page_idx 分组，返回 {page_idx: [blocks 按原序]}。"""
    pages = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        try:
            pidx = int(it.get("page_idx", 0))
        except (TypeError, ValueError):
            pidx = 0
        pages.setdefault(pidx, []).append(it)
    return pages


def _line_start(text: str, pos: int) -> int:
    """返回 pos 所在行的行首偏移（首行返回 0）。"""
    return text.rfind("\n", 0, pos) + 1


def locate_pages(seg_md: str, items: list, seg_start: int, seg_end: int = None):
    """定位段内每页的插入偏移。

    返回 (anchors, warnings)：
      anchors = [(insert_offset, abs_page), ...]（未排序）
      warnings = ['tail_page:N', 'miss_page:N', 'blank_page:N',
                  'page_idx_out_of_range: ...', ...]
    段内多数页首尾都失配 → 返回 ([], ['segment_fallback: m/t unmatched', ...])。

    seg_end（段声明末页，1-based）给定时：
      - 页数以段声明范围（seg_end-seg_start+1）为准，尾部缺口页补 blank 而非静默丢失；
      - page_idx 超出声明范围的块记 page_idx_out_of_range warning，不产越界锚点。
    未给 seg_end 时退回 max(page_idx)+1（向后兼容）。

    近似页（tail/miss/blank，无法精确定位起点）统一放「下一个 exact 锚点」处：
    近似页 read region 读空=诚实「无法定位」，前一可靠页 region 得以保全（修复 M-1）。
    """
    md_norm, index = _norm_with_index(seg_md)
    pages = group_by_page(items)
    if not pages:
        return [], []

    max_idx = max(pages)
    declared = (seg_end - seg_start + 1) if seg_end is not None else max_idx + 1
    total = max(declared, 1)
    range_warnings = []
    if seg_end is not None and max_idx > total - 1:
        range_warnings.append(
            f"page_idx_out_of_range: max_idx={max_idx} > declared_last={total - 1}")

    cursor = 0  # md_norm 上的前向单调游标
    located = []  # (abs_page, offset|None, quality)；仅 exact 带精确 offset
    for pidx in range(total):
        abs_page = seg_start + pidx
        blocks = pages.get(pidx, [])
        if not blocks:
            located.append((abs_page, None, "blank"))
            continue
        first_fp = fingerprint(blocks[0])
        fh = md_norm.find(first_fp, cursor) if first_fp else -1
        if fh >= 0:
            located.append((abs_page, _line_start(seg_md, index[fh]), "exact"))
            cursor = fh + len(first_fp)
            continue
        # 首块失配 → 试尾块：尾命中确认该页存在但起点不精确 → 归为近似（off 待定）
        last_fp = fingerprint(blocks[-1])
        lh = md_norm.find(last_fp, cursor) if last_fp else -1
        if lh >= 0:
            located.append((abs_page, None, "tail"))
            cursor = lh + len(last_fp)
            continue
        located.append((abs_page, None, "miss"))

    miss = sum(1 for _, _, q in located if q == "miss")
    if miss > total / 2:
        return [], [f"segment_fallback: {miss}/{total} unmatched"] + range_warnings

    # 近似页放「下一个 exact 锚点」处；无后续 exact（段尾近似）则放段末。
    n = len(located)
    next_exact = [len(seg_md)] * n
    nxt = len(seg_md)
    for i in range(n - 1, -1, -1):
        if located[i][2] == "exact":
            nxt = located[i][1]
        next_exact[i] = nxt

    anchors, warnings = [], list(range_warnings)
    for i, (abs_page, off, q) in enumerate(located):
        if q == "exact":
            anchors.append((off, abs_page))
        else:
            anchors.append((next_exact[i], abs_page))
            warnings.append(f"{q}_page:{abs_page}")
    return anchors, warnings


def insert_page_anchors(seg_md: str, items: list, seg_start: int, seg_end: int = None):
    """在段的原生 md 内插入逐页锚点，返回 (md_with_anchors, warnings)。

    整段回退时返回原 md 不动 + segment_fallback warning。
    正文零改动：插入的仅为 `<!-- page N -->\\n` 注释行。seg_end 见 locate_pages。
    """
    anchors, warnings = locate_pages(seg_md, items, seg_start, seg_end)
    if not anchors:
        return seg_md, warnings
    # 从后往前插，避免前面的插入移动后面的 offset；同 offset 按 page 降序插
    # （降序插使小 page 最终排在上方，锚点自上而下递增）。
    result = seg_md
    for off, page in sorted(anchors, key=lambda a: (a[0], a[1]), reverse=True):
        result = f"{result[:off]}<!-- page {page} -->\n{result[off:]}"
    return result, warnings


def strip_page_anchors(md: str) -> str:
    """移除所有逐页锚点行，用于「正文零改动」校验。"""
    return PAGE_ANCHOR_LINE_RE.sub("", md)
