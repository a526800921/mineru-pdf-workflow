#!/usr/bin/env python3
"""pdf-table-fix 候选扫描新增纯函数单测（阶段 1）。

零依赖：标准库 unittest。
"""

import importlib.util
import os
import unittest


def _load_module(filepath: str):
    """从文件路径加载 Python 模块（支持无扩展名的脚本）。"""
    from importlib.machinery import SourceFileLoader
    name = os.path.basename(filepath).replace("-", "_")
    loader = SourceFileLoader(name, filepath)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


_scripts_dir = os.path.join(os.path.dirname(__file__), "..", "scripts")
_table_fix = _load_module(os.path.join(_scripts_dir, "pdf-table-fix"))

_compute_page_anchor = _table_fix._compute_page_anchor
_build_candidate_id = _table_fix._build_candidate_id
_determine_candidate_type = _table_fix._determine_candidate_type
_extract_original_metrics = _table_fix._extract_original_metrics
_extract_missing_text = _table_fix._extract_missing_text
_compute_table_stats = _table_fix._compute_table_stats


class TestComputePageAnchor(unittest.TestCase):
    def test_page_1(self):
        self.assertEqual(_compute_page_anchor(1), "<!-- pages 1-1 -->")

    def test_page_99(self):
        self.assertEqual(_compute_page_anchor(99), "<!-- pages 99-99 -->")


class TestBuildCandidateId(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_build_candidate_id("demo60", 12), "demo60_p0012")

    def test_single_digit(self):
        self.assertEqual(_build_candidate_id("test", 5), "test_p0005")

    def test_large_page(self):
        self.assertEqual(_build_candidate_id("pkg", 9999), "pkg_p9999")


class TestDetermineCandidateType(unittest.TestCase):
    def test_native_missing_only(self):
        ct, lo = _determine_candidate_type(["native_table_text_missing"])
        self.assertEqual(ct, "native_missing")
        self.assertFalse(lo)

    def test_structural_only(self):
        ct, lo = _determine_candidate_type(["excessive_empty_td"])
        self.assertEqual(ct, "structural")
        self.assertFalse(lo)

    def test_text_omission_only(self):
        ct, lo = _determine_candidate_type(["volume_inflation"])
        self.assertEqual(ct, "text_omission")
        self.assertTrue(lo)

    def test_mixed_structural_text(self):
        ct, lo = _determine_candidate_type(
            ["excessive_columns", "volume_inflation"]
        )
        self.assertEqual(ct, "mixed")
        self.assertTrue(lo)

    def test_native_plus_text(self):
        ct, lo = _determine_candidate_type(
            ["native_table_text_missing", "text_coverage_low"]
        )
        self.assertEqual(ct, "native_missing")
        self.assertTrue(lo)

    def test_all_signals(self):
        ct, lo = _determine_candidate_type(
            ["native_table_text_missing", "excessive_empty_td",
             "volume_inflation", "text_coverage_low"]
        )
        self.assertEqual(ct, "mixed")
        self.assertTrue(lo)

    def test_empty_signals(self):
        ct, lo = _determine_candidate_type([])
        self.assertEqual(ct, "unknown")
        self.assertFalse(lo)

    def test_irrelevant_signals(self):
        ct, lo = _determine_candidate_type(["some_other_signal"])
        self.assertEqual(ct, "unknown")
        self.assertFalse(lo)


class TestExtractOriginalMetrics(unittest.TestCase):
    def test_full_metrics(self):
        fb = {
            "original_metrics": {
                "empty_td": 10,
                "max_td_per_row": 5,
                "md_bytes": 1000,
                "pdf_bytes": 500,
                "text_coverage": 0.85,
                "pdf_tokens": 120,
            }
        }
        r = _extract_original_metrics(fb)
        self.assertEqual(r["empty_td"], 10)
        self.assertEqual(r["max_td_per_row"], 5)
        self.assertEqual(r["md_bytes"], 1000)
        self.assertEqual(r["pdf_bytes"], 500)
        self.assertEqual(r["text_coverage"], 0.85)
        self.assertEqual(r["pdf_tokens"], 120)

    def test_missing_fields(self):
        fb = {"original_metrics": {"empty_td": 3}}
        r = _extract_original_metrics(fb)
        self.assertEqual(r["empty_td"], 3)
        self.assertEqual(r["max_td_per_row"], 0)
        self.assertEqual(r["md_bytes"], 0)
        self.assertEqual(r["text_coverage"], 1.0)

    def test_no_metrics(self):
        r = _extract_original_metrics({})
        self.assertEqual(r["empty_td"], 0)

    def test_non_dict_metrics(self):
        r = _extract_original_metrics({"original_metrics": "bad"})
        self.assertEqual(r["empty_td"], 0)


class TestExtractMissingText(unittest.TestCase):
    def test_with_missing(self):
        fb = {
            "original_metrics": {
                "missing_text": ["AURA", "CF150T-32"]
            }
        }
        r = _extract_missing_text(fb)
        self.assertEqual(r, ["AURA", "CF150T-32"])

    def test_empty_list(self):
        fb = {"original_metrics": {"missing_text": []}}
        r = _extract_missing_text(fb)
        self.assertEqual(r, [])

    def test_no_missing_text_field(self):
        fb = {"original_metrics": {}}
        r = _extract_missing_text(fb)
        self.assertEqual(r, [])

    def test_no_metrics(self):
        r = _extract_missing_text({})
        self.assertEqual(r, [])


class TestComputeTableStats(unittest.TestCase):
    def test_valid_html(self):
        html = ("<table><tr><td>a</td><td>b</td></tr>"
                "<tr><td>c</td><td>d</td></tr></table>")
        r = _compute_table_stats(html)
        self.assertIsNotNone(r)
        self.assertEqual(r["row_count"], 2)
        self.assertEqual(r["col_count"], 2)
        self.assertEqual(r["cell_count"], 4)
        self.assertEqual(r["parse_status"], "ok")

    def test_empty_html(self):
        r = _compute_table_stats("")
        self.assertIsNone(r)

    def test_none_html(self):
        r = _compute_table_stats(None)
        self.assertIsNone(r)

    def test_malformed_html(self):
        r = _compute_table_stats("<table><tr><td>broken")
        self.assertIsNotNone(r)
        # parse_table_html 仍会解析出部分结果，parse_status 为 malformed
        self.assertIn(r["parse_status"], ("malformed", "ok"))


if __name__ == "__main__":
    unittest.main()
