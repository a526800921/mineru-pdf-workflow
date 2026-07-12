#!/usr/bin/env python3
"""pdf-table-fix 候选扫描新增纯函数单测（阶段 1）。

零依赖：标准库 unittest。
"""

import importlib.util
import os
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


# ── 阶段 1 回滚：同步失败清零测试 ──

_HASH_FILE_FN = _table_fix._hash_file
_SYNC_MANIFEST_FN = _table_fix._sync_manifest


class TestSyncManifestRollback(unittest.TestCase):
    """验证 _sync_manifest 在 rename 失败时不留下半成品。"""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.mkdtemp()
        self.pkg = Path(self._tmp)
        # 准备最小 manifest
        self.manifest_path = self.pkg / "manifest.json"
        self.manifest_path.write_text(
            '{"model":"test","files":{"markdown":"test.md"}}', encoding="utf-8")
        # 准备 data 目录
        (self.pkg / "data").mkdir(exist_ok=True)
        # 写一个候选临时文件
        self.tmp_candidates = self.pkg / "data" / "table_candidates.jsonl.tmp"
        self.tmp_candidates.write_text(
            '{"schema_version":2,"candidate_id":"test_p0001","needs_human":true}\n',
            encoding="utf-8")
        self.final_candidates = self.pkg / "data" / "table_candidates.jsonl"
        self.manifest_hash_before = _HASH_FILE_FN(self.manifest_path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_candidates_rename_fails_no_half_state(self):
        """candidates rename 失败后：无最终文件残留，manifest 不变。"""
        # 让 final_candidates 为目录 → rename 失败
        self.final_candidates.mkdir(exist_ok=True)

        with self.assertRaises(OSError):
            _SYNC_MANIFEST_FN(
                self.pkg, "data/table_candidates.jsonl",
                self.tmp_candidates, self.final_candidates,
            )

        # tmp 已清理
        self.assertFalse(self.tmp_candidates.exists(),
                         "tmp candidates 应被清理")
        # manifest 未被修改（还是旧 hash）
        self.assertEqual(_HASH_FILE_FN(self.manifest_path),
                         self.manifest_hash_before)
        # 半成品不存在：目录还在但里面的东西是我们创建的
        self.assertTrue(self.final_candidates.is_dir(),
                        "目录 target 仍然存在（非我们创建）")

    def test_manifest_rename_fails_rolls_back_candidates(self):
        """manifest rename 失败后：已写入的 candidates 被回滚删除。"""
        import os as _os_module

        # 用 mock 让第 2 次 os.rename 失败（manifest rename）
        orig_rename = _os_module.rename
        call_count = [0]

        def _failing_rename(src, dst):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OSError("Simulated manifest rename failure")
            return orig_rename(src, dst)

        # 直接替换 os.rename 来注入失败
        try:
            _os_module.rename = _failing_rename
            with self.assertRaises(OSError):
                _SYNC_MANIFEST_FN(
                    self.pkg, "data/table_candidates.jsonl",
                    self.tmp_candidates, self.final_candidates,
                )
        finally:
            _os_module.rename = orig_rename

        # tmp 已清理
        self.assertFalse(self.tmp_candidates.exists(),
                         "tmp candidates 应被清理")
        # 已 rename 到最终路径的 candidates 被回滚删除
        self.assertFalse(self.final_candidates.exists(),
                         "final candidates 应被回滚删除")
        # manifest 未被修改
        self.assertEqual(_HASH_FILE_FN(self.manifest_path),
                         self.manifest_hash_before)

    def test_both_succeed_no_cleanup(self):
        """正常路径：两者都成功，产物完整。"""
        _SYNC_MANIFEST_FN(
            self.pkg, "data/table_candidates.jsonl",
            self.tmp_candidates, self.final_candidates,
        )

        # 临时文件已被 rename
        self.assertFalse(self.tmp_candidates.exists())
        # 最终文件存在
        self.assertTrue(self.final_candidates.exists())
        # manifest 已更新
        import json as _json
        m = _json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(m["files"]["table_candidates"],
                         "data/table_candidates.jsonl")
        self.assertTrue(m["hash"]["table_candidates_sha256"])


if __name__ == "__main__":
    unittest.main()
