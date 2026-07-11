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

from lib.toc_repair import (
    repair_merged,
    _build_merged_toc_block,
    _extract_entries_from_page,
    _assign_to_toc_pages,
    _compute_depths,
)


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


class TestPhysicalPageAttribution(unittest.TestCase):
    """阶段1：目录条目物理页归属（完整行/词边界匹配 + 提取即归属）。

    真实回归用 demo20；词边界机制用 Latin 合成 PDF——CJK 字体在字符间插空格会
    破坏点线正则，Latin 文本稳定复现 '前制动手柄/制动'、'停放检查/停放' 前缀冲突。
    """

    DEMO20 = Path(__file__).parent / ".." / "pdf" / "demo20" / "demo20.pdf"

    def _prefix_conflict_pdf(
        self, longer: str, shorter: str, longer_pg: int, shorter_pg: int
    ) -> str:
        """合成两页 PDF：index0 仅含更长标题(短标题的前缀)，index1 含独立短标题。

        镜像 '前制动手柄(p2)/制动(p4)'、'停放检查/停放' 跨页前缀冲突。
        """
        doc = fitz.open()
        pa = doc.new_page(width=400, height=600)
        pa.insert_text((72, 100), f"{longer}........", fontsize=12)
        pa.insert_text((72, 130), f"........{longer_pg}", fontsize=12)
        pb = doc.new_page(width=400, height=600)
        pb.insert_text((72, 100), f"{shorter}........", fontsize=12)
        pb.insert_text((72, 130), f"........{shorter_pg}", fontsize=12)
        path = tempfile.mktemp(suffix=".pdf")
        doc.save(path)
        doc.close()
        return path

    # ── demo20 真实回归 ──────────────────────────────────────────────

    def test_extract_carries_physical_toc_page(self):
        """提取即归属：条目带物理目录页(1-based) toc_page 字段。"""
        if not self.DEMO20.exists():
            self.skipTest("demo20.pdf not available")
        doc = fitz.open(str(self.DEMO20))
        try:
            p4 = _extract_entries_from_page(doc, 3)  # 物理页4 = index3
            zhidong = [e for e in p4 if e["title"] == "制动"]
            self.assertTrue(zhidong, "p4 应提取独立'制动'条目")
            self.assertEqual(zhidong[0].get("toc_page"), 4)
        finally:
            doc.close()

    def test_carried_toc_page_beats_substring(self):
        """Step 0 红基线绿版：'制动'归物理页4，不因子串落到含'前制动手柄'的p2。"""
        if not self.DEMO20.exists():
            self.skipTest("demo20.pdf not available")
        doc = fitz.open(str(self.DEMO20))
        try:
            entries = []
            for pi in range(1, 8):
                entries.extend(_extract_entries_from_page(doc, pi))
            _compute_depths(entries)
            assigned = _assign_to_toc_pages(entries, doc, list(range(2, 9)))
            pages_with = [
                p for p, rows in assigned.items()
                if any(e["title"] == "制动" for e in rows)
            ]
            self.assertEqual(pages_with, [4])
            self.assertFalse(
                any(e["title"] == "制动" for e in assigned[2]),
                "p2 不得含'制动'(子串误匹配'前制动手柄')",
            )
        finally:
            doc.close()

    # ── 词边界机制（Latin 合成）───────────────────────────────────────

    def test_wholeline_match_when_no_carried_page(self):
        """无 toc_page(模拟内置大纲)时用完整行匹配唯一归属，不用裸子串。"""
        path = self._prefix_conflict_pdf("Brakelever", "Brake", 34, 130)
        doc = fitz.open(path)
        try:
            entries = [{"title": "Brake", "page": 130, "depth": 0}]  # 无 toc_page
            assigned = _assign_to_toc_pages(entries, doc, [1, 2])
            pages = [p for p, rows in assigned.items() if rows]
            self.assertEqual(
                pages, [2], "'Brake'应完整行匹配 page2，而非子串命中 page1"
            )
        finally:
            doc.close()
            os.unlink(path)

    def test_prefix_conflict_park_parking(self):
        """停放/停放检查前缀冲突镜像：'Park'不被'Parking'子串吸附。"""
        path = self._prefix_conflict_pdf("Parking", "Park", 50, 200)
        doc = fitz.open(path)
        try:
            entries = [{"title": "Park", "page": 200, "depth": 0}]
            assigned = _assign_to_toc_pages(entries, doc, [1, 2])
            pages = [p for p, rows in assigned.items() if rows]
            self.assertEqual(pages, [2])
        finally:
            doc.close()
            os.unlink(path)

    def test_unmatched_entry_not_force_assigned(self):
        """无法唯一归属的条目进入 review，不被强制分配(移除字符集模糊回退)。"""
        path = self._prefix_conflict_pdf("Brakelever", "Brake", 34, 130)
        doc = fitz.open(path)
        try:
            entries = [{"title": "Nonexistent", "page": 9, "depth": 0}]
            assigned = _assign_to_toc_pages(entries, doc, [1, 2])
            total = sum(len(rows) for rows in assigned.values())
            self.assertEqual(total, 0, "无法唯一归属不得强制分配到任意页")
        finally:
            doc.close()
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
