#!/usr/bin/env python3
"""table_eval.parse_table_html 的结构自检单测（P4b）。

零依赖：标准库 unittest，可 `python3 tests/test_table_eval.py` 运行。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from lib.table_eval import (  # noqa: E402
    parse_table_html,
    parse_segment_name,
    build_section_index,
    section_for_page,
)


class TestParseTableHtml(unittest.TestCase):
    def test_regular_grid(self):
        """规整 2x2 表：行列自洽、无空单元格、status=ok。"""
        html = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></table>"
        r = parse_table_html(html)
        self.assertEqual(r["row_count"], 2)
        self.assertEqual(r["col_count"], 2)
        self.assertEqual(r["cell_count"], 4)
        self.assertEqual(r["empty_cell_count"], 0)
        self.assertEqual(r["empty_cell_ratio"], 0.0)
        self.assertEqual(r["merged_cell_count"], 0)
        self.assertIs(r["col_consistent"], True)
        self.assertEqual(r["parse_status"], "ok")

    def test_colspan_expands_to_consistent(self):
        """首行 colspan=2，展开后与两列行一致 → consistent、status=ok。"""
        html = ("<table><tr><td colspan='2'>merged</td></tr>"
                "<tr><td>c</td><td>d</td></tr></table>")
        r = parse_table_html(html)
        self.assertEqual(r["col_count"], 2)
        self.assertEqual(r["cell_count"], 3)
        self.assertEqual(r["merged_cell_count"], 1)
        self.assertIs(r["col_consistent"], True)
        self.assertEqual(r["parse_status"], "ok")

    def test_rowspan_placeholder_keeps_consistent(self):
        """rowspan 合并：下方行被占位，逻辑列数应仍一致（不误报破损）。"""
        html = ("<table><tr><td rowspan='2'>A</td><td>B</td></tr>"
                "<tr><td>C</td></tr></table>")
        r = parse_table_html(html)
        self.assertEqual(r["col_count"], 2)
        self.assertEqual(r["cell_count"], 3)
        self.assertEqual(r["merged_cell_count"], 1)
        self.assertIs(r["col_consistent"], True)
        self.assertEqual(r["parse_status"], "ok")

    def test_inconsistent_columns_malformed(self):
        """真实列数不一致（无 span）→ col_consistent=False、status=malformed。"""
        html = ("<table><tr><td>a</td><td>b</td></tr>"
                "<tr><td>c</td><td>d</td><td>e</td></tr></table>")
        r = parse_table_html(html)
        self.assertEqual(r["col_count"], 3)
        self.assertIs(r["col_consistent"], False)
        self.assertEqual(r["parse_status"], "malformed")

    def test_empty_table(self):
        """无单元格 → status=empty、col_count=0。"""
        r = parse_table_html("<table></table>")
        self.assertEqual(r["row_count"], 0)
        self.assertEqual(r["col_count"], 0)
        self.assertEqual(r["cell_count"], 0)
        self.assertEqual(r["empty_cell_ratio"], 0.0)
        self.assertIs(r["col_consistent"], False)
        self.assertEqual(r["parse_status"], "empty")

    def test_empty_cell_ratio(self):
        """单行两格一空 → empty_cell_ratio=0.5，单行仍 consistent。"""
        html = "<table><tr><td>a</td><td></td></tr></table>"
        r = parse_table_html(html)
        self.assertEqual(r["cell_count"], 2)
        self.assertEqual(r["empty_cell_count"], 1)
        self.assertEqual(r["empty_cell_ratio"], 0.5)
        self.assertEqual(r["parse_status"], "ok")

    def test_th_counted_as_cell(self):
        """<th> 表头单元格也计入 cell_count。"""
        html = ("<table><tr><th>h1</th><th>h2</th></tr>"
                "<tr><td>a</td><td>b</td></tr></table>")
        r = parse_table_html(html)
        self.assertEqual(r["cell_count"], 4)
        self.assertEqual(r["col_count"], 2)
        self.assertIs(r["col_consistent"], True)

    def test_real_sample_危险_notice(self):
        """真实样本（p0177-0184 单列告警表）：单列多行、consistent、status=ok。"""
        html = ("<table><tr><td>⚠危险</td></tr>"
                "<tr><td>接触化学物质风险提示。</td></tr></table>")
        r = parse_table_html(html)
        self.assertEqual(r["col_count"], 1)
        self.assertEqual(r["row_count"], 2)
        self.assertIs(r["col_consistent"], True)
        self.assertEqual(r["parse_status"], "ok")


class TestSelectSegments(unittest.TestCase):
    """选段口径：复用 pdf-merge 段名正则，排除 rerun/临时目录。"""

    def test_valid_segment_name(self):
        self.assertEqual(parse_segment_name("p0001-0008"), (1, 8))
        self.assertEqual(parse_segment_name("p0185-0191"), (185, 191))

    def test_rerun_suffix_excluded(self):
        """p0185-0191-rerun 是遗留脏目录，必须排除（否则重复计数）。"""
        self.assertIsNone(parse_segment_name("p0185-0191-rerun"))

    def test_non_segment_names_excluded(self):
        self.assertIsNone(parse_segment_name(".DS_Store"))
        self.assertIsNone(parse_segment_name("images"))
        self.assertIsNone(parse_segment_name("p1-2"))  # 不足 4 位


class TestSectionIndex(unittest.TestCase):
    """section 定位：合并 md 按页锚点就近取 ##（段级近似，缺省空串）。"""

    MD = (
        "<!-- pages 1-8 -->\n"
        "## 前言\n\n正文内容\n"
        "<!-- pages 9-16 -->\n"
        "正文无标题段落\n"
    )

    def test_page_in_segment_with_heading(self):
        idx = build_section_index(self.MD)
        self.assertEqual(section_for_page(idx, 3), "前言")
        self.assertEqual(section_for_page(idx, 8), "前言")

    def test_segment_without_heading_returns_empty(self):
        idx = build_section_index(self.MD)
        self.assertEqual(section_for_page(idx, 12), "")

    def test_page_outside_all_anchors_returns_empty(self):
        idx = build_section_index(self.MD)
        self.assertEqual(section_for_page(idx, 99), "")

    def test_no_anchors_returns_empty(self):
        idx = build_section_index("## 标题\n无页锚点\n")
        self.assertEqual(section_for_page(idx, 1), "")


if __name__ == "__main__":
    unittest.main()
