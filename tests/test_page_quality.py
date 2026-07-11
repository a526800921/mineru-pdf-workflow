#!/usr/bin/env python3
"""阶段 3 页级质量检测核心逻辑单测。零依赖外部数据，unittest。"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from lib.page_quality import (  # noqa: E402
    assess_page_quality,
    check_text_coverage,
    check_volume_inflation,
    compare_quality,
    count_empty_td,
    max_td_per_row,
    _normalize_table_text,
    _parse_all_tables,
    detect_native_table_text_omission,
)
try:
    import fitz
except ImportError:
    fitz = None


class TestCountEmptyTd(unittest.TestCase):
    def test_no_table(self):
        self.assertEqual(count_empty_td("纯文本，无表格"), 0)

    def test_no_empty(self):
        md = "<table><tr><td>A</td><td>B</td></tr></table>"
        self.assertEqual(count_empty_td(md), 0)

    def test_some_empty(self):
        md = "<table><tr><td></td><td>B</td><td> </td></tr></table>"
        self.assertEqual(count_empty_td(md), 2)

    def test_empty_with_whitespace(self):
        md = "<table><tr><td>  </td><td>\n\t</td></tr></table>"
        self.assertEqual(count_empty_td(md), 2)

    def test_over_threshold(self):
        md = "<table>" + "<tr>" + "<td></td>" * 100 + "</tr></table>"
        self.assertEqual(count_empty_td(md), 100)


class TestMaxTdPerRow(unittest.TestCase):
    def test_no_table(self):
        self.assertEqual(max_td_per_row("纯文本"), 0)

    def test_single_row(self):
        md = "<table><tr><td>A</td><td>B</td><td>C</td></tr></table>"
        self.assertEqual(max_td_per_row(md), 3)

    def test_multi_row(self):
        md = (
            "<table>"
            "<tr><td>A</td><td>B</td></tr>"
            "<tr><td>X</td><td>Y</td><td>Z</td></tr>"
            "</table>"
        )
        self.assertEqual(max_td_per_row(md), 3)

    def test_with_attributes(self):
        md = '<table><tr class="x"><td colspan="2">A</td><td>B</td></tr></table>'
        self.assertEqual(max_td_per_row(md), 2)


class TestVolumeInflation(unittest.TestCase):
    def test_no_inflation(self):
        self.assertFalse(check_volume_inflation("小文本", "大量PDF原生文字 " * 200))

    def test_inflation_long_text(self):
        md = ("A" * 30000) + ("<table>" + "<tr>" + "<td></td>" * 50 + "</tr></table>" * 50)
        pdf = "短文本"
        self.assertTrue(check_volume_inflation(md, pdf))

    def test_empty_pdf_no_false_positive(self):
        self.assertFalse(check_volume_inflation("<table>" * 100, ""))

    def test_below_min_bytes(self):
        # md > pdf*4 但 md < 20 KiB
        md = "A" * 5000
        pdf = "B" * 100  # pdf 很小，ratio>4
        self.assertFalse(check_volume_inflation(md, pdf))

    def test_exact_threshold(self):
        # md_bytes >= 20480 AND md >= pdf*4
        md = "A" * 20480
        pdf = "B" * 5120  # ratio = 4 exactly
        self.assertTrue(check_volume_inflation(md, pdf))


class TestTextCoverage(unittest.TestCase):
    def test_high_coverage(self):
        low, cov = check_text_coverage(
            "hello world this is a test",
            "hello world this is a test",
        )
        self.assertFalse(low)
        self.assertAlmostEqual(cov, 1.0)

    def test_no_pdf_tokens(self):
        low, cov = check_text_coverage("hello world", "")
        self.assertFalse(low)
        self.assertAlmostEqual(cov, 1.0)

    def test_below_threshold(self):
        # 50+ tokens in PDF, coverage < 50%
        pdf_text = "word " * 60
        md_text = "word " * 20  # only 20/60 = 33%
        low, cov = check_text_coverage(md_text, pdf_text)
        self.assertTrue(low)
        self.assertLess(cov, 0.5)

    def test_borderline_50_tokens(self):
        # exactly 50 tokens, coverage >= 50%
        pdf_text = "word " * 50
        md_text = "word " * 25  # 50%
        low, cov = check_text_coverage(md_text, pdf_text)
        self.assertFalse(low)
        self.assertAlmostEqual(cov, 0.5)

    def test_word_boundary_preserved(self):
        pdf_text = "hello world foo bar"
        md_text = "hello foo world bar"
        low, cov = check_text_coverage(md_text, pdf_text)
        self.assertFalse(low)
        self.assertAlmostEqual(cov, 1.0)

    def test_partial_overlap(self):
        pdf_text = "one two three four five"
        md_text = "one two three"  # 3/5 = 60%
        low, cov = check_text_coverage(md_text, pdf_text)
        self.assertFalse(low)
        self.assertGreater(cov, 0.5)


class TestAssessPageQuality(unittest.TestCase):
    def test_clean_page(self):
        result = assess_page_quality("正常文本内容", "short pdf text")
        self.assertTrue(result["quality_ok"])
        self.assertEqual(result["signals"], [])

    def test_trigger_empty_td(self):
        md = "<table>" + "<tr>" + "<td></td>" * 100 + "</tr></table>"
        pdf = "PDF text " * 20
        result = assess_page_quality(md, pdf)
        self.assertIn("excessive_empty_td", result["signals"])

    def test_trigger_multiple_signals(self):
        md = ("<table>" + "<tr>" + "<td></td>" * 100 + "</tr></table>") * 30
        pdf = "short text"
        result = assess_page_quality(md, pdf)
        self.assertIn("excessive_empty_td", result["signals"])
        self.assertIn("excessive_columns", result["signals"])
        self.assertIn("volume_inflation", result["signals"])

    def test_metrics_shape(self):
        result = assess_page_quality("<p>hello</p>", "PDF text " * 10)
        self.assertIn("empty_td", result["metrics"])
        self.assertIn("max_td_per_row", result["metrics"])
        self.assertIn("md_bytes", result["metrics"])
        self.assertIn("pdf_bytes", result["metrics"])
        self.assertIn("text_coverage", result["metrics"])
        self.assertIn("pdf_tokens", result["metrics"])


class TestCompareQuality(unittest.TestCase):
    """完整 compare_quality 场景覆盖"""

    def _assert_cmp(self, desc, orig, fb, expected):
        got = compare_quality(orig, fb)
        self.assertEqual(got, expected, desc)

    # --- table pages ---
    def test_td_halved_text_kept(self):
        self._assert_cmp(
            "td halved, text kept → fallback",
            {"empty_td": 100, "max_td_per_row": 50, "md_bytes": 50000, "text_coverage": 0.9},
            {"empty_td": 30, "max_td_per_row": 50, "md_bytes": 48000, "text_coverage": 0.9},
            "fallback",
        )

    def test_cols_reduced_text_kept(self):
        self._assert_cmp(
            "cols reduced, text kept → fallback",
            {"empty_td": 100, "max_td_per_row": 50, "md_bytes": 50000, "text_coverage": 0.9},
            {"empty_td": 80, "max_td_per_row": 30, "md_bytes": 48000, "text_coverage": 0.9},
            "fallback",
        )

    def test_both_worse(self):
        self._assert_cmp(
            "both worse → original",
            {"empty_td": 10, "max_td_per_row": 5, "md_bytes": 5000, "text_coverage": 0.8},
            {"empty_td": 15, "max_td_per_row": 5, "md_bytes": 500, "text_coverage": 0.2},
            "original",
        )

    def test_td_improved_coverage_lost(self):
        self._assert_cmp(
            "td improved, coverage lost → review",
            {"empty_td": 100, "max_td_per_row": 50, "md_bytes": 50000, "text_coverage": 0.9},
            {"empty_td": 30, "max_td_per_row": 50, "md_bytes": 48000, "text_coverage": 0.2},
            "review",
        )

    def test_duplicate_empty_cells_removed_and_coverage_improved(self):
        """表格重复空单元格被清理后体积大幅下降，应采纳 fallback。"""
        self._assert_cmp(
            "empty td removed, coverage improved despite smaller md → fallback",
            {
                "empty_td": 16311,
                "max_td_per_row": 8157,
                "md_bytes": 147058,
                "text_coverage": 0.446,
            },
            {
                "empty_td": 0,
                "max_td_per_row": 1,
                "md_bytes": 484,
                "text_coverage": 0.8489,
            },
            "fallback",
        )

    def test_td_not_improved_text_kept(self):
        self._assert_cmp(
            "td not improved, text kept → review",
            {"empty_td": 100, "max_td_per_row": 50, "md_bytes": 50000, "text_coverage": 0.9},
            {"empty_td": 80, "max_td_per_row": 50, "md_bytes": 45000, "text_coverage": 0.9},
            "review",
        )

    # --- non-table pages ---
    def test_no_table_identical(self):
        self._assert_cmp(
            "no table, identical → review",
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 24587, "text_coverage": 0.02},
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 24587, "text_coverage": 0.02},
            "review",
        )

    def test_no_table_text_lost(self):
        self._assert_cmp(
            "no table, text lost → original",
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 24587, "text_coverage": 0.3},
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 442, "text_coverage": 0.1},
            "original",
        )

    def test_no_table_cov_ok_vol_lost(self):
        self._assert_cmp(
            "no table, cov ok vol lost → review",
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 50000, "text_coverage": 0.5},
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 500, "text_coverage": 0.5},
            "review",
        )

    def test_no_table_text_kept(self):
        self._assert_cmp(
            "no table, text kept → review",
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 100, "text_coverage": 1.0},
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 85, "text_coverage": 1.0},
            "review",
        )

    # ── native_table_missing 优先规则 ────────────────────────
    def test_missing_resolved_text_ok(self):
        """字段缺失被 fallback 恢复 → fallback"""
        self._assert_cmp(
            "missing resolved, text OK → fallback",
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 5000, "text_coverage": 0.9,
             "native_table_missing": 2},
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 4800, "text_coverage": 0.9,
             "native_table_missing": 0},
            "fallback",
        )

    def test_missing_resolved_text_lost(self):
        """字段缺失恢复了但文本丢失 → review"""
        self._assert_cmp(
            "missing resolved, text lost → review",
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 5000, "text_coverage": 0.9,
             "native_table_missing": 2},
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 200, "text_coverage": 0.1,
             "native_table_missing": 0},
            "review",
        )

    def test_missing_not_resolved(self):
        """字段缺失未改善 → review"""
        self._assert_cmp(
            "missing not resolved → review",
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 5000, "text_coverage": 0.9,
             "native_table_missing": 2},
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 4800, "text_coverage": 0.9,
             "native_table_missing": 2},
            "review",
        )

    def test_missing_partially_resolved(self):
        """字段缺失部分改善 → review"""
        self._assert_cmp(
            "missing partially resolved → review",
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 5000, "text_coverage": 0.9,
             "native_table_missing": 5},
            {"empty_td": 0, "max_td_per_row": 0, "md_bytes": 4800, "text_coverage": 0.9,
             "native_table_missing": 2},
            "review",
        )

    def test_missing_not_present_fallthrough(self):
        """没有 native_table_missing 时不影响既有逻辑"""
        self._assert_cmp(
            "no missing metrics → existing logic",
            {"empty_td": 100, "max_td_per_row": 50, "md_bytes": 50000, "text_coverage": 0.9},
            {"empty_td": 30, "max_td_per_row": 50, "md_bytes": 48000, "text_coverage": 0.9},
            "fallback",
        )


class TestNativeTableTextOmission(unittest.TestCase):
    """通用表格字段缺失检测。"""

    def setUp(self):
        # 需要真实 PDF 来提取 words，使用 demo20
        self.pdf_path = os.path.join(
            os.path.dirname(__file__), "..", "pdf", "demo20", "demo20.pdf"
        )
        if not os.path.exists(self.pdf_path):
            self.skipTest("demo20.pdf not available")

    def _get_page_md(self, page_1based: int) -> str:
        """读取指定页的 MinerU Markdown（hybrid_auto 子目录）。"""
        md_path = Path(self.pdf_path).parent / "segments" / \
            f"p{page_1based:04d}-{page_1based:04d}" / "demo20" / "hybrid_auto" / "demo20.md"
        if md_path.exists():
            return md_path.read_text(encoding="utf-8", errors="replace")
        return ""

    def test_p16_missing_field_detected(self):
        """p16 的"百公里综合油耗"能被通用规则发现。"""
        doc = fitz.open(self.pdf_path)
        words = doc[15].get_text("words")
        md_text = self._get_page_md(16)
        self.assertTrue(md_text, "p16 md should exist")

        signals, metrics = detect_native_table_text_omission(
            md_text, words, doc[15].rect.width, doc[15].rect.height,
        )
        doc.close()

        self.assertIn("native_table_text_missing", signals)
        self.assertGreater(metrics["native_table_missing"], 0)
        # 具体字段不是白名单，但当前样本中应包含它
        self.assertTrue(
            any("百公里综合油耗" in t for t in metrics.get("missing_text", [])),
            f"missing_text should contain '百公里综合油耗': {metrics.get('missing_text')}",
        )

    def test_p6_no_table_no_false_positive(self):
        """无表格页不触发遗漏检测。"""
        doc = fitz.open(self.pdf_path)
        words = doc[9].get_text("words")  # p10 (no table)
        md_text = self._get_page_md(10)
        doc.close()
        if not md_text:
            self.skipTest("p10 md not available")

        signals, metrics = detect_native_table_text_omission(
            md_text, words, 556, 386,
        )
        # 无 HTML 表格时返回空 signals
        self.assertNotIn("native_table_text_missing", signals)

    def test_p4_body_text_no_false_positive(self):
        """纯正文页（无表格）不误触发。"""
        doc = fitz.open(self.pdf_path)
        words = doc[3].get_text("words")  # p4
        md_text = self._get_page_md(4)
        doc.close()
        if not md_text:
            self.skipTest("p4 md not available")
        signals, metrics = detect_native_table_text_omission(
            md_text, words, 556, 386,
        )
        self.assertNotIn("native_table_text_missing", signals,
                         f"p4 should not trigger: {metrics.get('missing_text')}")

    def test_multi_word_field_no_false_positive(self):
        """多词字段（如 "Max power"）不因拆分误报。"""
        # 构造 mock：PDF words 有 "Max" 和 "power" 在同一行，HTML 单元格为 "Max power"
        mock_html = (
            "<table><tr><td>Max power</td><td>100W</td></tr>"
            "<tr><td>Weight</td><td>50kg</td></tr>"
            "<tr><td>Size</td><td>10cm</td></tr></table>"
        )
        mock_words = [
            (50, 100, 120, 130, "Max", 0, 0, 0),
            (125, 100, 190, 130, "power", 0, 0, 0),
            (300, 100, 350, 130, "100W", 0, 0, 0),
            (50, 140, 120, 170, "Weight", 0, 0, 0),
            (300, 140, 350, 170, "50kg", 0, 0, 0),
            (50, 180, 120, 210, "Size", 0, 0, 0),
            (300, 180, 350, 210, "10cm", 0, 0, 0),
        ]
        signals, metrics = detect_native_table_text_omission(
            mock_html, mock_words, 500, 400,
        )
        self.assertNotIn(
            "native_table_text_missing", signals,
            f"multi-word should not trigger: {metrics.get('missing_text')}",
        )

    def test_rowspan_carried_in_grid(self):
        """rowspan 展开后，后续行对应列继承单元格文本。"""
        html = (
            "<table><tr><td rowspan='2'>A</td><td>B</td></tr>"
            "<tr><td>C</td></tr><tr><td>D</td><td>E</td></tr></table>"
        )
        grid = _parse_all_tables(html)
        self.assertEqual(len(grid), 1, "should be 1 spec table")
        rows = grid[0]
        self.assertEqual(rows[0][0], "A")
        self.assertEqual(rows[1][0], "A", "rowspan should carry A to row 1")
        self.assertEqual(rows[1][1], "C")
        self.assertEqual(rows[2][0], "D", "row 2 no longer affected")

    def test_colspan_expanded_in_grid(self):
        """colspan 展开后单元格出现多次。"""
        html = ("<table><tr><td colspan='3'>X</td></tr>"
                "<tr><td>A</td><td>B</td><td>C</td></tr>"
                "<tr><td>D</td><td>E</td><td>F</td></tr></table>")
        grid = _parse_all_tables(html)
        rows = grid[0]
        self.assertEqual(len(rows), 3, "should be 3 rows")
        self.assertEqual(len(rows[0]), 3, "colspan=3 should expand to 3 cells")
        for cell in rows[0]:
            self.assertEqual(cell, "X")

    def test_normalize_consistency(self):
        """归一化对于已知表格内容的一致性。"""
        md = self._get_page_md(16)
        if not md:
            self.skipTest("p16 md not available")
        tables = _parse_all_tables(md)
        self.assertGreater(len(tables), 0)
        # 收集所有展开后的单元格文本
        all_cells: set[str] = set()
        for grid in tables:
            for row in grid:
                for ct in row:
                    if ct.strip():
                        all_cells.add(_normalize_table_text(ct))
        for known in ["电器装置", "蓄电池", "12V/7Ah", "前照灯", "不可调节"]:
            self.assertIn(
                _normalize_table_text(known),
                all_cells,
                f"'{known}' should be in expanded grid cells",
            )


if __name__ == "__main__":
    unittest.main()
