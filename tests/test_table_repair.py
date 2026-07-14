#!/usr/bin/env python3
"""pdf-table-repair 候选重建纯函数单测（阶段 1）。

零依赖：标准库 unittest。
"""

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


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
_repair = _load_module(os.path.join(_scripts_dir, "pdf-table-repair"))

_build_fix_id = _repair._build_fix_id
_build_table_id = _repair._build_table_id
_classify_repair_types = _repair._classify_repair_types
_compress_excessive_columns = _repair._compress_excessive_columns
_parse_simple_html = _repair._parse_simple_html
_detect_cross_page_candidates = _repair._detect_cross_page_candidates
_generate_draft_for_repair_type = _repair._generate_draft_for_repair_type
_generate_drafts = _repair._generate_drafts
_verify_anchor_uniqueness = _repair._verify_anchor_uniqueness
_compute_expected_hit_count = _repair._compute_expected_hit_count


# ── TestBuildFixId ─────────────────────────────────────


class TestBuildFixId(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_build_fix_id("demo60", 12),
                         "repair-demo60_p0012")

    def test_single_digit(self):
        self.assertEqual(_build_fix_id("春风250Sr", 5),
                         "repair-春风250Sr_p0005")

    def test_large_page(self):
        self.assertEqual(_build_fix_id("pkg", 9999),
                         "repair-pkg_p9999")


# ── TestBuildTableId ──────────────────────────────────


class TestBuildTableId(unittest.TestCase):
    def test_single_page(self):
        self.assertEqual(_build_table_id("demo60", [47]),
                         "demo60_table_p0047")

    def test_cross_page(self):
        self.assertEqual(_build_table_id("春风250Sr", [47, 48]),
                         "春风250Sr_table_p0047-p0048")

    def test_three_consecutive(self):
        self.assertEqual(_build_table_id("test", [13, 14, 15]),
                         "test_table_p0013-p0015")

    def test_empty_list(self):
        tid = _build_table_id("pkg", [])
        self.assertTrue("unknown" in tid)

    def test_single_item_list(self):
        self.assertEqual(_build_table_id("demo20", [12]),
                         "demo20_table_p0012")


# ── TestClassifyRepairTypes ───────────────────────────


class TestClassifyRepairTypes(unittest.TestCase):
    def test_excessive_columns_only(self):
        types = _classify_repair_types(
            ["excessive_columns"], "structural", False)
        self.assertIn("pretty_print", types)
        self.assertEqual(len(types), 1)

    def test_excessive_empty_td_only(self):
        types = _classify_repair_types(
            ["excessive_empty_td"], "structural", False)
        self.assertIn("pretty_print", types)
        self.assertEqual(len(types), 1)

    def test_native_missing_only(self):
        types = _classify_repair_types(
            ["native_table_text_missing"], "native_missing", False)
        self.assertIn("fill_missing_text", types)
        self.assertEqual(len(types), 1)

    def test_text_omission_only(self):
        types = _classify_repair_types(
            ["volume_inflation"], "text_omission", True)
        self.assertIn("structure_warning", types)
        self.assertEqual(len(types), 1)

    def test_mixed_signals(self):
        types = _classify_repair_types(
            ["excessive_columns", "native_table_text_missing"],
            "mixed", False)
        self.assertIn("pretty_print", types)
        self.assertIn("fill_missing_text", types)
        self.assertEqual(len(types), 2)

    def test_all_signals(self):
        types = _classify_repair_types(
            ["excessive_columns", "native_table_text_missing",
             "volume_inflation"],
            "mixed", True)
        self.assertIn("pretty_print", types)
        self.assertIn("fill_missing_text", types)
        self.assertIn("structure_warning", types)
        self.assertEqual(len(types), 3)

    def test_layout_flag_triggers_warning(self):
        types = _classify_repair_types(
            ["excessive_columns"], "mixed", True)
        # layout_flag 为 True → structure_warning
        # excessive_columns → pretty_print
        self.assertIn("pretty_print", types)
        self.assertIn("structure_warning", types)

    def test_no_match(self):
        types = _classify_repair_types(
            ["irrelevant_signal"], "unknown", False)
        self.assertEqual(types, [])


# ── TestParseSimpleHtml ───────────────────────────────


class TestParseSimpleHtml(unittest.TestCase):
    def test_basic_table(self):
        html = "<table><tr><td>a</td><td>b</td></tr></table>"
        rows = _parse_simple_html(html)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0]["text"], "a")
        self.assertEqual(rows[0][1]["text"], "b")

    def test_colspan(self):
        html = "<table><tr><td colspan='2'>wide</td></tr></table>"
        rows = _parse_simple_html(html)
        self.assertEqual(rows[0][0]["colspan"], 2)
        self.assertEqual(rows[0][0]["text"], "wide")

    def test_empty_html(self):
        self.assertEqual(_parse_simple_html(""), [])

    def test_multi_row(self):
        html = ("<table><tr><td>1</td><td>2</td></tr>"
                "<tr><td>3</td><td>4</td></tr></table>")
        rows = _parse_simple_html(html)
        self.assertEqual(len(rows), 2)


# ── TestCompressExcessiveColumns ──────────────────────


class TestCompressExcessiveColumns(unittest.TestCase):
    def test_normal_cols_unchanged(self):
        html = "<table>\n  <tr>\n    <td>a</td>\n    <td>b</td>\n  </tr>\n</table>"
        compressed, warnings = _compress_excessive_columns(html)
        self.assertEqual(compressed, html)
        self.assertEqual(warnings, [])

    def test_excessive_cols_compressed(self):
        # Simulate 8192 columns with identical cells
        cells = "".join("<td></td>" for _ in range(100))
        html = f"<table><tr><td>first</td>{cells}</tr></table>"
        compressed, warnings = _compress_excessive_columns(html)
        self.assertIn("可疑列数", warnings[0])
        # Compressed should be much shorter
        self.assertLess(len(compressed), len(html) // 10)

    def test_empty_html(self):
        compressed, warnings = _compress_excessive_columns("")
        self.assertEqual(compressed, "")
        self.assertEqual(warnings, [])

    def test_repeated_pattern_compressed(self):
        # 30 cells with only 3 unique texts repeating
        cells = ""
        for _ in range(10):
            cells += "<td>A</td><td>B</td><td>C</td>"
        html = f"<table><tr>{cells}</tr></table>"
        compressed, warnings = _compress_excessive_columns(html)
        # Should warn about column count
        self.assertTrue(len(warnings) > 0)

    def test_no_warnings_for_reasonable_cols(self):
        html = ("<table><tr><td>1</td><td>2</td><td>3</td>"
                "<td>4</td></tr></table>")
        _, warnings = _compress_excessive_columns(html)
        self.assertEqual(warnings, [])


# ── TestDetectCrossPage ───────────────────────────────


class TestDetectCrossPage(unittest.TestCase):
    def test_consecutive_pages(self):
        candidates = [
            {"candidate_id": "demo20_p0014", "page": 14},
            {"candidate_id": "demo20_p0015", "page": 15},
            {"candidate_id": "demo20_p0016", "page": 16},
        ]
        result = _detect_cross_page_candidates(candidates)
        found = False
        for sid, pages in result.items():
            if 14 in pages and 16 in pages:
                found = True
        self.assertTrue(found)

    def test_non_consecutive_pages(self):
        candidates = [
            {"candidate_id": "demo60_p0012", "page": 12},
            {"candidate_id": "demo60_p0037", "page": 37},
        ]
        result = _detect_cross_page_candidates(candidates)
        # No groups if only 2 non-consecutive pages
        for pages in result.values():
            self.assertNotIn(12, set(pages) & {37})

    def test_single_page_no_group(self):
        candidates = [
            {"candidate_id": "demo60_p0012", "page": 12},
        ]
        result = _detect_cross_page_candidates(candidates)
        self.assertEqual(result, {})

    def test_empty(self):
        self.assertEqual(_detect_cross_page_candidates([]), {})

    def test_three_consecutive_pages(self):
        candidates = [
            {"candidate_id": "pkg_p0085", "page": 85},
            {"candidate_id": "pkg_p0086", "page": 86},
            {"candidate_id": "pkg_p0087", "page": 87},
            {"candidate_id": "pkg_p0090", "page": 90},
        ]
        result = _detect_cross_page_candidates(candidates)
        group85 = None
        for sid, pages in result.items():
            if 85 in pages:
                group85 = pages
        self.assertIsNotNone(group85)
        self.assertIn(86, group85)
        self.assertIn(87, group85)
        self.assertNotIn(90, group85)


# ── TestGenerateDraftStructure ────────────────────────


class TestGenerateDraftStructure(unittest.TestCase):
    """验证 draft 记录的字段完整性。"""

    def setUp(self):
        self.candidate = {
            "schema_version": 2,
            "candidate_id": "demo60_p0047",
            "page": 47,
            "page_anchor": "<!-- pages 47-47 -->",
            "segment": "p0047-0047",
            "signals": ["excessive_columns", "volume_inflation"],
            "candidate_type": "mixed",
            "layout_or_visual_needs_review": True,
            "table_stats": {
                "row_count": 2, "col_count": 8192,
                "cell_count": 8160, "empty_cell_count": 8158,
            },
            "original_metrics": {
                "empty_td": 0, "max_td_per_row": 8160,
            },
            "missing_text": ["图例", "序号"],
            "original_html": "<table><tr><td>test</td></tr></table>",
            "fallback_html": "",
            "pdf_text": "图例 序号 test content",
            "source": {
                "pdf": "demo60.pdf",
                "markdown_sha256": "abc123",
            },
            "needs_human": True,
        }
        self.source_shas = {
            "pdf_sha256": "pdf_sha",
            "markdown_sha256": "md_sha",
        }
        self.cross_table_ids = {}

    def test_pretty_print_draft_has_all_fields(self):
        draft = _generate_draft_for_repair_type(
            self.candidate, "pretty_print", "demo60",
            self.source_shas, self.cross_table_ids,
        )
        required = [
            "schema_version", "fix_id", "status", "needs_human",
            "pages", "page_anchor", "table_id", "repair_type",
            "source_segment", "source_candidate_id",
            "source_pdf_sha256", "source_markdown_sha256",
            "before_html", "draft_html", "fallback_html",
            "pdf_text", "missing_text", "expected_hit_count", "warnings",
        ]
        for field in required:
            self.assertIn(field, draft, f"缺少必需字段：{field}")
        self.assertEqual(draft["status"], "proposed")
        self.assertTrue(draft["needs_human"])
        self.assertEqual(draft["repair_type"], "pretty_print")

    def test_fill_missing_text_draft(self):
        draft = _generate_draft_for_repair_type(
            self.candidate, "fill_missing_text", "demo60",
            self.source_shas, self.cross_table_ids,
        )
        self.assertEqual(draft["repair_type"], "fill_missing_text")
        self.assertTrue(len(draft["missing_text"]) > 0)

    def test_structure_warning_draft(self):
        draft = _generate_draft_for_repair_type(
            self.candidate, "structure_warning", "demo60",
            self.source_shas, self.cross_table_ids,
        )
        self.assertEqual(draft["repair_type"], "structure_warning")
        self.assertTrue(len(draft["warnings"]) > 0)

    def test_cross_page_table_id_in_warnings(self):
        cross_ids = {"demo60_table_p0047-p0048": [47, 48]}
        draft = _generate_draft_for_repair_type(
            self.candidate, "pretty_print", "demo60",
            self.source_shas, cross_ids,
        )
        self.assertIn("demo60_table_p0047-p0048", draft["table_id"])
        has_cross_warning = any("跨页" in w for w in draft["warnings"])
        self.assertTrue(has_cross_warning)


# ── TestVerifyAnchorUniqueness ────────────────────────


class TestVerifyAnchorUniqueness(unittest.TestCase):
    def test_all_unique(self):
        md = "a\n<!-- pages 1-1 -->\ncontent\n<!-- pages 2-2 -->\ncontent"
        errors = _verify_anchor_uniqueness(md)
        self.assertEqual(errors, [])

    def test_duplicate_anchor(self):
        md = ("<!-- pages 1-1 -->\ncontent\n"
              "<!-- pages 1-1 -->\nduplicate")
        errors = _verify_anchor_uniqueness(md)
        self.assertTrue(len(errors) > 0)
        self.assertIn("重复", errors[0])

    def test_no_anchors(self):
        errors = _verify_anchor_uniqueness("content with no anchors")
        self.assertEqual(errors, [])

    def test_empty_string(self):
        errors = _verify_anchor_uniqueness("")
        self.assertEqual(errors, [])


# ── TestNoOpPrettyPrint ────────────────────────────────


class TestNoOpPrettyPrint(unittest.TestCase):
    def test_already_formatted_table_is_not_actionable_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            html = "<table><tr><td>已格式化</td></tr></table>"
            (root / "doc.md").write_text(
                f"<!-- pages 1-1 -->\n{html}\n", encoding="utf-8")
            candidate = {
                "candidate_id": "pkg_p0001",
                "page": 1,
                "page_anchor": "<!-- pages 1-1 -->",
                "segment": "p0001-0001",
                "signals": ["excessive_columns"],
                "candidate_type": "structural",
                "table_stats": {"row_count": 1, "col_count": 8192},
                "original_html": html,
                "fallback_html": "",
                "missing_text": [],
            }
            manifest = {"files": {"markdown": "doc.md"}}
            drafts = _generate_drafts(root, manifest, [candidate], None)
            self.assertFalse(
                any(d["repair_type"] == "pretty_print" for d in drafts)
            )


# ── TestComputeExpectedHitCount ───────────────────────


class TestComputeExpectedHitCount(unittest.TestCase):
    def test_hit_count_zero(self):
        md = "<!-- pages 1-1 -->\ncontent\n<!-- pages 2-2 -->"
        count = _compute_expected_hit_count(
            md, "<!-- pages 1-1 -->", "<table>new</table>")
        self.assertEqual(count, 0)

    def test_hit_count_one(self):
        md = "<!-- pages 10-10 -->\n<table>old</table>\n<!-- pages 11-11 -->"
        count = _compute_expected_hit_count(
            md, "<!-- pages 10-10 -->", "<table>old</table>")
        self.assertEqual(count, 1)

    def test_hit_count_multiple(self):
        md = ("<!-- pages 5-5 -->\n<table>dup</table>\n"
              "more\n<table>dup</table>\n<!-- pages 6-6 -->")
        count = _compute_expected_hit_count(
            md, "<!-- pages 5-5 -->", "<table>dup</table>")
        self.assertEqual(count, 2)


# ── TestDraftNewFields ────────────────────────────────


class TestDraftNewFields(unittest.TestCase):
    """验证 draft 新增字段的完整性。"""

    def setUp(self):
        self.candidate = {
            "candidate_id": "demo60_p0047",
            "page": 47,
            "page_anchor": "<!-- pages 47-47 -->",
            "segment": "p0047-0047",
            "signals": ["native_table_text_missing"],
            "candidate_type": "native_missing",
            "layout_or_visual_needs_review": False,
            "table_stats": {"row_count": 4, "col_count": 3},
            "missing_text": ["图例"],
            "original_html": "<table><tr><td>A</td></tr></table>",
            "fallback_html": "<table><tr><td>fallback</td></tr></table>",
            "pdf_text": "图例 A",
            "source": {"pdf": "d.pdf", "markdown_sha256": "abc"},
            "needs_human": True,
        }
        self.source_shas = {"pdf_sha256": "ps", "markdown_sha256": "ms"}

    def test_fallback_html_present(self):
        draft = _generate_draft_for_repair_type(
            self.candidate, "fill_missing_text", "demo60",
            self.source_shas, {},
            md_text="<!-- pages 47-47 -->\n<table>A</table>\n<!-- pages 48-48 -->",
        )
        self.assertEqual(draft["fallback_html"],
                         "<table><tr><td>fallback</td></tr></table>")
        self.assertIsInstance(draft["expected_hit_count"], int)
        self.assertIn("图例", draft["missing_text"])

    def test_expected_hit_count_zero_when_no_match(self):
        # before_html="<table><tr><td>A</td></tr></table>" 不在锚点内
        draft = _generate_draft_for_repair_type(
            self.candidate, "pretty_print", "demo60",
            self.source_shas, {},
            md_text="<!-- pages 47-47 -->\nother content\n<!-- pages 48-48 -->",
        )
        self.assertEqual(draft["expected_hit_count"], 0)


if __name__ == "__main__":
    unittest.main()
