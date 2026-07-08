#!/usr/bin/env python3
"""表格结构自检指标计算（P4b）。

从表格 HTML（MinerU content_list.json v1 的 `table_body` 字段）自身结构推断
解析健全性——零 ground truth、零成本。列数不一致、HTML 解析失败等信号用于
定位破损表格。属启发式（非 TEDS 精度评测），`col_consistent` 仅作破损信号。

零依赖：仅用标准库 html.parser。
"""
import csv
import json
import re
from html.parser import HTMLParser
from pathlib import Path


class _TableStructParser(HTMLParser):
    """收集表格为 rows=[[cell, ...], ...]，每个 cell 记录 colspan/rowspan/text。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._cur_row = None
        self._cur_cell = None
        self._cur_text = []

    @staticmethod
    def _span(attrs, name):
        d = dict(attrs)
        try:
            v = int(d.get(name, 1) or 1)
        except (TypeError, ValueError):
            v = 1
        return max(v, 1)

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._cur_row = []
        elif tag in ("td", "th") and self._cur_row is not None:
            self._cur_cell = {
                "colspan": self._span(attrs, "colspan"),
                "rowspan": self._span(attrs, "rowspan"),
            }
            self._cur_text = []

    def handle_data(self, data):
        if self._cur_cell is not None:
            self._cur_text.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cur_cell is not None:
            self._cur_cell["text"] = "".join(self._cur_text).strip()
            self._cur_row.append(self._cur_cell)
            self._cur_cell = None
            self._cur_text = []
        elif tag == "tr" and self._cur_row is not None:
            self.rows.append(self._cur_row)
            self._cur_row = None

    def close(self):
        super().close()
        # 容错：未闭合的 tr/td
        if self._cur_cell is not None and self._cur_row is not None:
            self._cur_cell["text"] = "".join(self._cur_text).strip()
            self._cur_row.append(self._cur_cell)
        if self._cur_row is not None:
            self.rows.append(self._cur_row)


def _logical_row_widths(rows: list) -> list:
    """按二维网格模型计算每行逻辑列数：colspan 横向展开 + rowspan 向下占位。

    启发式：让规整的合并单元格表（rowspan/colspan）列数保持一致，仅真正错位
    的行才判为不一致，避免把合法合并表误报为破损。
    """
    occupied = set()  # 被上方 rowspan 占据的 (row_idx, col_idx)
    widths = []
    for r, row in enumerate(rows):
        col = 0
        ci = 0
        while ci < len(row) or (r, col) in occupied:
            if (r, col) in occupied:
                col += 1
                continue
            cell = row[ci]
            cs = cell["colspan"]
            rs = cell["rowspan"]
            for cc in range(col, col + cs):
                for rr in range(r + 1, r + rs):
                    occupied.add((rr, cc))
            col += cs
            ci += 1
        widths.append(col)
    return widths


# 段名口径：复用 pdf-merge 的正则，严格匹配 ^pXXXX-YYYY$（1-based 页范围）
_SEGMENT_RE = re.compile(r"^p(\d{4,})-(\d{4,})$")
# 合并 Markdown 页锚点（pdf-read-page 同源口径）
_ANCHOR_RE = re.compile(r"^<!-- pages (\d+)-(\d+) -->\s*$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_segment_name(name: str):
    """解析段目录名 pXXXX-YYYY，返回 (start_page, end_page)（1-based）或 None。

    复用 pdf-merge 的段名口径：严格 ^pXXXX-YYYY$，排除 `p0185-0191-rerun` 等带
    后缀的遗留/临时目录与 `.DS_Store` 等非段目录——否则会把已被覆盖的旧段与
    rerun 目录重复计数（春风 150AURA 实测：全扫得 121 表，merge 口径为 115）。
    """
    m = _SEGMENT_RE.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def build_section_index(md_text: str) -> list:
    """解析合并 Markdown，返回 [(seg_start, seg_end, section_title), ...]。

    section 取每个页锚点区间内第一个 ## 标题（段级近似）。合并 md 按 8 页一段的
    `<!-- pages N-M -->` 锚点分节，节内无页级边界，故 section 精度到段级、缺省空串。
    """
    if not md_text:
        return []
    anchors = [
        (m.start(), int(m.group(1)), int(m.group(2)))
        for m in _ANCHOR_RE.finditer(md_text)
    ]
    index = []
    for i, (pos, s, e) in enumerate(anchors):
        next_pos = anchors[i + 1][0] if i + 1 < len(anchors) else len(md_text)
        seg_text = md_text[pos:next_pos]
        hm = _H2_RE.search(seg_text)
        index.append((s, e, hm.group(1).strip() if hm else ""))
    return index


def section_for_page(index: list, page: int) -> str:
    """在 build_section_index 的结果中查 page 所属 section，缺省空串。"""
    for s, e, title in index:
        if s <= page <= e:
            return title
    return ""


def parse_table_html(html: str) -> dict:
    """解析表格 HTML，返回结构自检指标 dict。

    键：row_count / col_count / cell_count / empty_cell_count /
        empty_cell_ratio / merged_cell_count / col_consistent / parse_status
    """
    parse_error = False
    rows = []
    try:
        p = _TableStructParser()
        p.feed(html or "")
        p.close()
        rows = p.rows
    except Exception:
        parse_error = True

    cells = [c for row in rows for c in row]
    cell_count = len(cells)
    empty_cell_count = sum(1 for c in cells if not c["text"])
    merged_cell_count = sum(1 for c in cells if c["colspan"] > 1 or c["rowspan"] > 1)

    # 每行展开后的逻辑列数（colspan 横向展开 + rowspan 向下占位）
    row_widths = _logical_row_widths(rows)
    col_count = max(row_widths) if row_widths else 0
    col_consistent = bool(row_widths) and len(set(row_widths)) == 1

    empty_cell_ratio = round(empty_cell_count / cell_count, 3) if cell_count else 0.0

    if parse_error:
        parse_status = "malformed"
    elif cell_count == 0:
        parse_status = "empty"
    elif not col_consistent:
        parse_status = "malformed"
    else:
        parse_status = "ok"

    return {
        "row_count": len(rows),
        "col_count": col_count,
        "cell_count": cell_count,
        "empty_cell_count": empty_cell_count,
        "empty_cell_ratio": empty_cell_ratio,
        "merged_cell_count": merged_cell_count,
        "col_consistent": col_consistent,
        "parse_status": parse_status,
    }


CSV_FIELDS = [
    "table_id", "page", "section", "row_count", "col_count", "cell_count",
    "empty_cell_count", "empty_cell_ratio", "merged_cell_count",
    "col_consistent", "parse_status",
]


def _find_v1_content_list(seg_dir: Path):
    """在段目录内找 v1 content_list.json（排除 v2）。

    v1 的 table 元素带 `table_body`（HTML 结构），v2 只有纯文本 `content`。
    文件名 `*_content_list.json` 天然不含 v2 的 `*_content_list_v2.json`。
    """
    for f in sorted(seg_dir.rglob("*_content_list.json")):
        if f.name.endswith("_content_list_v2.json"):
            continue
        return f
    return None


def eval_package_tables(package_dir, output_path=None):
    """对输出包所有 table 元素做结构自检，写 data/table_accuracy.csv。

    选段复用 pdf-merge 口径（parse_segment_name，排除 rerun/临时目录）。
    全局页码 = 段起始页(1-based) + page_idx(段内 0-based)。
    返回 (rows, out_path)。非法输入（无 segments / 无 content_list）抛
    FileNotFoundError，不产出半成品 CSV。
    """
    package_dir = Path(package_dir)
    segments_dir = package_dir / "segments"
    if not segments_dir.is_dir():
        raise FileNotFoundError(f"找不到分段目录：{segments_dir}")

    # 合并 Markdown（可选，用于 section 段级定位）
    md_path = package_dir / f"{package_dir.name}.md"
    md_text = md_path.read_text(encoding="utf-8") if md_path.exists() else ""
    section_index = build_section_index(md_text)

    # 选段：复用 pdf-merge 段名口径，按起始页排序
    segments = []
    for child in sorted(segments_dir.iterdir()):
        if not child.is_dir():
            continue
        parsed = parse_segment_name(child.name)
        if parsed is None:
            continue
        segments.append((parsed[0], parsed[1], child))
    segments.sort(key=lambda x: x[0])

    rows = []
    content_lists_found = 0
    for start, _end, seg_dir in segments:
        cl = _find_v1_content_list(seg_dir)
        if cl is None:
            continue
        content_lists_found += 1
        items = json.loads(cl.read_text(encoding="utf-8"))
        if not isinstance(items, list):
            continue
        page_table_seq = {}  # 全局页码 -> 该页已出现表数（页内表序 1-based）
        for it in items:
            if not isinstance(it, dict) or it.get("type") != "table":
                continue
            try:
                page_idx = int(it.get("page_idx", 0))
            except (TypeError, ValueError):
                page_idx = 0
            global_page = start + page_idx
            seq = page_table_seq.get(global_page, 0) + 1
            page_table_seq[global_page] = seq
            body = it.get("table_body") or ""
            metrics = parse_table_html(body)
            rows.append({
                "table_id": f"p{global_page:04d}_t{seq:02d}",
                "page": global_page,
                "section": section_for_page(section_index, global_page),
                **{k: metrics[k] for k in (
                    "row_count", "col_count", "cell_count", "empty_cell_count",
                    "empty_cell_ratio", "merged_cell_count", "col_consistent",
                    "parse_status")},
            })

    if content_lists_found == 0:
        raise FileNotFoundError(
            f"分段目录下未找到任何 content_list.json（v1）：{segments_dir}")

    rows.sort(key=lambda r: (r["page"], r["table_id"]))

    out_path = (Path(output_path) if output_path
                else package_dir / "data" / "table_accuracy.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows, out_path
