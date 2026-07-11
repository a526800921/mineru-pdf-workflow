#!/usr/bin/env python3
"""阶段 3 页级质量检测核心逻辑单测。零依赖外部数据，unittest。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from lib.page_quality import (  # noqa: E402
    assess_page_quality,
    check_text_coverage,
    check_volume_inflation,
    compare_quality,
    count_empty_td,
    max_td_per_row,
)


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


if __name__ == "__main__":
    unittest.main()
