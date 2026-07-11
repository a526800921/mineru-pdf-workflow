#!/usr/bin/env python3
"""TOC 修复模块单元测试：repair_merged 和 _build_merged_toc_block。"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fitz

from lib.toc_repair import repair_merged, _build_merged_toc_block


def _create_test_pdf(toc_entries: list[list] | None, pages: int = 3) -> str:
    """创建含可选 TOC 大纲的测试 PDF。"""
    doc = fitz.open()
    for _ in range(pages):
        doc.new_page()
    if toc_entries:
        doc.set_toc(toc_entries)
    path = tempfile.mktemp(suffix=".pdf")
    doc.save(path)
    doc.close()
    return path


def _create_validate_json(segments: list[dict]) -> str:
    """创建 pdf-validate 输出的 mock JSON。"""
    path = tempfile.mktemp(suffix=".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"status": "completed", "segments": segments}, f, ensure_ascii=False)
    return path


def _create_merged_md(anchors: list[tuple[int, int]], body: str = "") -> str:
    """创建含段级锚点的 mock 合并 Markdown。"""
    lines = []
    for start, end in anchors:
        lines.append(f"<!-- pages {start}-{end} -->")
        lines.append("")
    if body:
        lines.append(body)
    return "\n".join(lines)


class TestRepairMerged(unittest.TestCase):
    """repair_merged 函数测试。"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir)

    def test_no_toc_segments(self):
        """验证无 TOC 段时返回 0。"""
        pdf = _create_test_pdf(None, 3)
        md = self.tmpdir / "merged.md"
        md.write_text("<!-- pages 1-1 -->\n\n正文内容", encoding="utf-8")

        validate = _create_validate_json([
            {
                "name": "p0001-0001", "start_page": 1, "end_page": 1,
                "page_type_summary": {"text": 1, "toc": 0},
                "pages": [{"page": 0, "page_type": "text"}],
            }
        ])

        result = repair_merged(Path(pdf), md, validate)
        self.assertEqual(result, 0)
        os.unlink(pdf)

    def test_no_toc_entries_in_pdf(self):
        """PDF 无 TOC 条目时返回 0。"""
        pdf = _create_test_pdf(None, 3)
        md = self.tmpdir / "merged.md"
        md.write_text("<!-- pages 1-1 -->\n\n正文内容", encoding="utf-8")

        validate = _create_validate_json([
            {
                "name": "p0001-0001", "start_page": 1, "end_page": 1,
                "page_type_summary": {"toc": 1},
                "pages": [{"page": 0, "page_type": "toc"}],
            }
        ])

        # 无 TOC 条目的 PDF → _build_from_outline 返回空 → fallback 也空 → return 0
        result = repair_merged(Path(pdf), md, validate)
        self.assertEqual(result, 0)
        os.unlink(pdf)

    def test_toc_repair_success(self):
        """有 TOC 条目 + 段级锚点时，成功替换 TOC 页内容。"""
        pdf = _create_test_pdf([
            [1, "概述", 1],
            [1, "规格", 1],
        ], 3)
        md = self.tmpdir / "merged.md"
        md.write_text(
            "<!-- pages 1-1 -->\n\n原始目录内容\n\n"
            "<!-- pages 2-2 -->\n\n正文内容\n\n"
            "<!-- pages 3-3 -->\n\n附注",
            encoding="utf-8"
        )

        validate = _create_validate_json([
            {
                "name": "p0001-0001", "start_page": 1, "end_page": 1,
                "page_type_summary": {"toc": 1},
                "pages": [{"page": 0, "page_type": "toc"}],
            },
            {
                "name": "p0002-0002", "start_page": 2, "end_page": 2,
                "page_type_summary": {"text": 1},
                "pages": [{"page": 1, "page_type": "text"}],
            },
            {
                "name": "p0003-0003", "start_page": 3, "end_page": 3,
                "page_type_summary": {"text": 1},
                "pages": [{"page": 2, "page_type": "text"}],
            },
        ])

        result = repair_merged(Path(pdf), md, validate)
        self.assertEqual(result, 1)

        # 验证：原始目录内容被替换为结构化的 TOC
        repaired = md.read_text(encoding="utf-8")
        self.assertIn("概述", repaired)
        self.assertIn("规格", repaired)
        self.assertNotIn("原始目录内容", repaired)

        # 验证：非 TOC 页内容保持不变
        self.assertIn("正文内容", repaired)
        self.assertIn("附注", repaired)

        # 验证：TOC 页使用段级锚点
        self.assertIn("<!-- pages 1-1 -->", repaired)

        os.unlink(pdf)

    def test_toc_at_end_of_document(self):
        """TOC 在文档末尾时处理正确。"""
        pdf = _create_test_pdf([
            [1, "目录", 3],
        ], 3)
        md = self.tmpdir / "merged.md"
        md.write_text(
            "<!-- pages 1-1 -->\n\n第一章正文\n\n"
            "<!-- pages 2-2 -->\n\n第二章正文\n\n"
            "<!-- pages 3-3 -->\n\n原始目录",
            encoding="utf-8"
        )

        validate = _create_validate_json([
            {
                "name": "p0001-0001", "start_page": 1, "end_page": 1,
                "page_type_summary": {"text": 1},
                "pages": [{"page": 0, "page_type": "text"}],
            },
            {
                "name": "p0002-0002", "start_page": 2, "end_page": 2,
                "page_type_summary": {"text": 1},
                "pages": [{"page": 1, "page_type": "text"}],
            },
            {
                "name": "p0003-0003", "start_page": 3, "end_page": 3,
                "page_type_summary": {"toc": 1},
                "pages": [{"page": 2, "page_type": "toc"}],
            },
        ])

        result = repair_merged(Path(pdf), md, validate)
        self.assertEqual(result, 1)

        repaired = md.read_text(encoding="utf-8")
        self.assertIn("目录", repaired)
        self.assertIn("第一章正文", repaired)
        os.unlink(pdf)


class TestBuildMergedTocBlock(unittest.TestCase):
    """_build_merged_toc_block 输出验证。"""

    def test_segment_anchors_not_page_anchors(self):
        """输出使用段级锚点（<!-- pages N-N -->）而非逐页锚点。"""
        by_page = {
            1: [{"title": "概述", "depth": 0, "page": 1}],
            2: [{"title": "规格", "depth": 0, "page": 2}],
        }
        block = _build_merged_toc_block(1, 2, by_page)

        # 必须包含段级锚点
        self.assertIn("<!-- pages 1-1 -->", block)
        self.assertIn("<!-- pages 2-2 -->", block)
        # 不能包含旧逐页锚点格式
        self.assertNotIn("<!-- page 1 -->", block)
        self.assertNotIn("<!-- page 2 -->", block)

    def test_toc_structure(self):
        """输出包含缩进层级和页码。"""
        by_page = {
            1: [
                {"title": "第一章", "depth": 0, "page": 1},
                {"title": "1.1 子项", "depth": 1, "page": 1},
            ],
        }
        block = _build_merged_toc_block(1, 1, by_page)
        self.assertIn("第一章", block)
        self.assertIn("1.1 子项", block)
        # 深度 1 应有缩进
        lines = block.split("\n")
        toc_lines = [l for l in lines if l.strip().startswith("-")]
        indent_line = [l for l in toc_lines if "子项" in l]
        self.assertTrue(any(l.startswith("  -") for l in indent_line))


if __name__ == "__main__":
    unittest.main()
