#!/usr/bin/env python3
"""review_report 页级质量复核段单测。零依赖真实 PDF/MinerU，unittest。"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from lib.review_report import generate_review_report  # noqa: E402


def _minimal_validate_report() -> dict:
    """一个全通过的最小 pdf-validate JSON 报告。"""
    return {
        "status": "completed",
        "segments": [
            {
                "name": "p0016-0016", "start_page": 16, "end_page": 16,
                "status": "passed", "coverage": 0.95, "rerunnable": False,
                "decision": "pass", "pages": [],
            }
        ],
    }


class TestPageFallbackReview(unittest.TestCase):
    def _gen(self, page_fallback: dict | None) -> str:
        """构造临时输出包，写 manifest + validate 报告，生成 review.md 并返回内容。"""
        tmp = tempfile.mkdtemp()
        pkg = Path(tmp)
        segments = pkg / "segments"
        segments.mkdir()
        manifest = {"segmentation": {"segment_size": 1}}
        if page_fallback is not None:
            manifest["page_fallback"] = page_fallback
        (pkg / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        )
        vt = pkg / "validate.json"
        vt.write_text(json.dumps(_minimal_validate_report()), encoding="utf-8")
        out = pkg / "review.md"
        generate_review_report(
            validate_json_path=str(vt),
            review_output_path=str(out),
            threshold=0.82,
            pdf_path=str(pkg / "dummy.pdf"),
            segments_dir=str(segments),
        )
        return out.read_text(encoding="utf-8")

    def test_native_review_surfaced(self):
        """selected=review 的原生检测页出现在页级质量复核段。"""
        content = self._gen({
            "16": {
                "selected": "review",
                "detector": "pdf_native",
                "quality_signals": ["native_table_text_missing"],
                "missing_text": ["百公里综合油耗"],
                "fb_status": "completed",
            }
        })
        self.assertIn("页级质量复核", content)
        self.assertIn("pdf_native", content)
        self.assertIn("百公里综合油耗", content)
        self.assertIn("| 16 |", content)

    def test_fallback_selected_excluded(self):
        """selected=fallback 的页不进入复核段（已采纳，无需人工）。"""
        content = self._gen({
            "12": {
                "selected": "fallback",
                "detector": "page_quality",
                "quality_signals": ["excessive_empty_td"],
                "missing_text": [],
                "fb_status": "completed",
            }
        })
        self.assertNotIn("页级质量复核", content)

    def test_failed_included(self):
        """fb_status=failed 的页进入复核段。"""
        content = self._gen({
            "9": {
                "selected": "review",
                "detector": "page_quality",
                "quality_signals": ["text_coverage_low"],
                "missing_text": [],
                "fb_status": "failed",
            }
        })
        self.assertIn("页级质量复核", content)
        self.assertIn("| 9 |", content)
        self.assertIn("failed", content)

    def test_no_page_fallback_no_section(self):
        """无 page_fallback 时不生成复核段。"""
        content = self._gen(None)
        self.assertNotIn("页级质量复核", content)

    def test_mixed_only_review_listed(self):
        """混合场景：只列 review/failed，fallback 页排除。"""
        content = self._gen({
            "12": {"selected": "fallback", "detector": "page_quality",
                   "quality_signals": ["excessive_empty_td"], "missing_text": [],
                   "fb_status": "completed"},
            "16": {"selected": "review", "detector": "pdf_native",
                   "quality_signals": ["native_table_text_missing"],
                   "missing_text": ["百公里综合油耗"], "fb_status": "completed"},
        })
        self.assertIn("| 16 |", content)
        self.assertNotIn("| 12 |", content)


if __name__ == "__main__":
    unittest.main()
