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
    repair,
    repair_merged,
    _build_merged_toc_block,
    _extract_entries_from_page,
    _assign_to_toc_pages,
    _compute_depths,
    _write_toc_tree,
    _detect_page_numbering,
    _normalize_entries,
    _sync_manifest_page_numbering,
    _write_toc_review_evidence,
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
    DEMO20TOC = Path(__file__).parent / ".." / "pdf" / "demo20toc" / "demo20toc.pdf"

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

    def test_control_char_toc_line_extraction(self):
        """目录行含控制字符（\\x08 分隔标题与点线）时仍能提取条目（demo20toc 乱码样本）。"""
        if not self.DEMO20TOC.exists():
            self.skipTest("demo20toc.pdf not available")
        doc = fitz.open(str(self.DEMO20TOC))
        try:
            p2 = _extract_entries_from_page(doc, 1)  # 物理页 2 目录
            titles = {e["title"]: e["page"] for e in p2}
            self.assertGreater(len(p2), 0, "含 \\x08 的目录行应能提取条目")
            self.assertEqual(titles.get("前言"), 7)  # 前言 → 指向页 7
            # 提取的标题不应残留控制字符
            self.assertFalse(
                any("\x08" in e["title"] for e in p2),
                "提取的标题不得残留 \\x08 控制字符",
            )
        finally:
            doc.close()


class TestMergedAndCompatPaths(unittest.TestCase):
    """阶段2：合并与兼容路径接入（toc_tree 字段扩展、toc.md、repair 段级归属）。"""

    DEMO20 = Path(__file__).parent / ".." / "pdf" / "demo20" / "demo20.pdf"

    def test_toc_tree_uses_target_and_toc_page(self):
        """toc_tree.json 每条含 target_page(指向页) 和 toc_page(物理目录页)。"""
        entries = [
            {"title": "前言", "page": 8, "toc_page": 2, "depth": 0},
            {"title": "制动", "page": 130, "toc_page": 4, "depth": 1},
        ]
        with tempfile.TemporaryDirectory() as d:
            _write_toc_tree(Path(d), entries)
            tree = json.load(open(Path(d) / "toc_tree.json", encoding="utf-8"))
        self.assertEqual(
            tree[0], {"title": "前言", "target_page": 8, "toc_page": 2, "depth": 0}
        )
        self.assertEqual(
            tree[1], {"title": "制动", "target_page": 130, "toc_page": 4, "depth": 1}
        )

    def test_build_toc_md_no_anchors(self):
        """toc.md 是无锚点连续列表，保留缩进层级和指向页码。"""
        from lib.toc_repair import _build_toc_md
        entries = [
            {"title": "前言", "page": 8, "toc_page": 2, "depth": 0},
            {"title": "重要的注意事项", "page": 10, "toc_page": 2, "depth": 1},
            {"title": "制动", "page": 130, "toc_page": 4, "depth": 1},
        ]
        md = _build_toc_md(entries)
        self.assertNotIn("<!-- pages", md)
        self.assertIn("## 目录", md)
        self.assertIn("- 前言 8", md)
        self.assertIn("  - 重要的注意事项 10", md)
        self.assertIn("  - 制动 130", md)

    def test_toc_md_matches_toc_tree_order(self):
        """toc.md 条目顺序与 entries(即 toc_tree) 一致。"""
        from lib.toc_repair import _build_toc_md
        entries = [
            {"title": "前言", "page": 8, "toc_page": 2, "depth": 0},
            {"title": "制动", "page": 130, "toc_page": 4, "depth": 1},
        ]
        md = _build_toc_md(entries)
        self.assertLess(md.index("前言 8"), md.index("制动 130"))

    def test_repair_merged_writes_toc_md(self):
        """repair_merged 成功后在包根目录生成无锚点 toc.md。"""
        pdf = _create_test_pdf([[1, "概述", 1], [1, "规格", 2]], 3)
        try:
            with tempfile.TemporaryDirectory() as d:
                md = Path(d) / "merged.md"
                md.write_text(
                    "<!-- pages 1-1 -->\n\n原始目录\n\n"
                    "<!-- pages 2-2 -->\n\n正文\n\n"
                    "<!-- pages 3-3 -->\n\n尾",
                    encoding="utf-8",
                )
                validate = _create_validate_json([
                    {"name": "p0001-0001", "start_page": 1, "end_page": 1,
                     "page_type_summary": {"toc": 1},
                     "pages": [{"page": 0, "page_type": "toc"}]},
                    {"name": "p0002-0002", "start_page": 2, "end_page": 2,
                     "page_type_summary": {"text": 1},
                     "pages": [{"page": 1, "page_type": "text"}]},
                    {"name": "p0003-0003", "start_page": 3, "end_page": 3,
                     "page_type_summary": {"text": 1},
                     "pages": [{"page": 2, "page_type": "text"}]},
                ])
                repair_merged(Path(pdf), md, validate)
                toc_md = Path(d) / "toc.md"
                self.assertTrue(toc_md.exists(), "repair_merged 应生成 toc.md")
                content = toc_md.read_text(encoding="utf-8")
                self.assertNotIn("<!-- pages", content)
                self.assertIn("概述", content)
                os.unlink(validate)
        finally:
            os.unlink(pdf)

    def test_repair_segments_physical_attribution(self):
        """repair() 段级按物理页归属：目录页段只含自己条目，不整本重复。"""
        if not self.DEMO20.exists():
            self.skipTest("demo20.pdf not available")
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            segdir = pkg / "segments"
            segments = []
            for pg in range(2, 9):
                name = f"p{pg:04d}-{pg:04d}"
                md_dir = segdir / name / "demo20" / "auto"
                md_dir.mkdir(parents=True)
                (md_dir / "demo20.md").write_text("原始目录占位", encoding="utf-8")
                segments.append({
                    "name": name, "start_page": pg, "end_page": pg,
                    "page_type_summary": {"toc": 1},
                    "pages": [{"page": pg - 1, "page_type": "toc"}],
                })
            validate = _create_validate_json(segments)
            repair(self.DEMO20, segdir, validate)

            def seg_md(name):
                return (segdir / name / "demo20" / "auto" / "demo20.md").read_text(
                    encoding="utf-8"
                )
            p2 = seg_md("p0002-0002")
            p4 = seg_md("p0004-0004")
            # 用精确条目行匹配（制动 target_page=130），避免"制动"子串命中"前制动手柄"
            self.assertIn("前言 8", p2)
            self.assertNotIn("制动 130", p2)  # 制动条目(→130)在 p4，不得出现在 p2 段
            self.assertIn("制动 130", p4)
            self.assertNotIn("前言 8", p4)  # 前言在 p2，不得出现在 p4 段
            os.unlink(validate)


    def test_unassigned_excluded_keeps_toc_md_tree_merged_consistent(self):
        """未唯一归属条目不进 toc.md/toc_tree，三者与合并 md 目录块一致。"""
        doc = fitz.open()
        pa = doc.new_page(width=400, height=600)
        pa.insert_text((72, 100), "Alpha........")
        pa.insert_text((72, 130), "........5")
        pb = doc.new_page(width=400, height=600)
        pb.insert_text((72, 100), "Gamma........")
        pb.insert_text((72, 130), "........9")
        doc.new_page(width=400, height=600)
        # 内置大纲含 Beta，但物理页无 Beta 行 → Beta 无法唯一归属
        doc.set_toc([[1, "Alpha", 1], [1, "Beta", 2], [1, "Gamma", 3]])
        pdf = tempfile.mktemp(suffix=".pdf")
        doc.save(pdf)
        doc.close()
        try:
            with tempfile.TemporaryDirectory() as d:
                md = Path(d) / "m.md"
                md.write_text(
                    "<!-- pages 1-1 -->\n\ntocA\n\n"
                    "<!-- pages 2-2 -->\n\ntocB\n\n"
                    "<!-- pages 3-3 -->\n\nbody",
                    encoding="utf-8",
                )
                validate = _create_validate_json([
                    {"name": "p0001-0001", "start_page": 1, "end_page": 1,
                     "page_type_summary": {"toc": 1},
                     "pages": [{"page": 0, "page_type": "toc"}]},
                    {"name": "p0002-0002", "start_page": 2, "end_page": 2,
                     "page_type_summary": {"toc": 1},
                     "pages": [{"page": 1, "page_type": "toc"}]},
                    {"name": "p0003-0003", "start_page": 3, "end_page": 3,
                     "page_type_summary": {"text": 1},
                     "pages": [{"page": 2, "page_type": "text"}]},
                ])
                repair_merged(Path(pdf), md, validate)
                toc_md = (Path(d) / "toc.md").read_text(encoding="utf-8")
                tree = json.load(open(Path(d) / "toc_tree.json", encoding="utf-8"))
                merged = md.read_text(encoding="utf-8")
                tree_titles = [e["title"] for e in tree]
                # Beta 未归属：不进 toc.md / toc_tree / 合并 md 目录块
                self.assertNotIn("Beta", toc_md)
                self.assertNotIn("Beta", tree_titles)
                self.assertNotIn("Beta", merged)
                # Alpha/Gamma 已归属：toc.md 与 toc_tree 均含，且集合一致
                self.assertIn("Alpha", toc_md)
                self.assertIn("Gamma", toc_md)
                self.assertEqual(sorted(tree_titles), ["Alpha", "Gamma"])
                os.unlink(validate)
        finally:
            os.unlink(pdf)


    def test_repair_merged_persists_unassigned_to_validate(self):
        """无法归属的 TOC 条目写回 validate 报告 toc_unassigned，供 review.md 展示。"""
        doc = fitz.open()
        pa = doc.new_page(width=400, height=600)
        pa.insert_text((72, 100), "Alpha........")
        pa.insert_text((72, 130), "........1")
        pb = doc.new_page(width=400, height=600)
        pb.insert_text((72, 100), "Gamma........")
        pb.insert_text((72, 130), "........3")
        doc.new_page(width=400, height=600)
        doc.set_toc([[1, "Alpha", 1], [1, "Beta", 2], [1, "Gamma", 3]])
        pdf = tempfile.mktemp(suffix=".pdf")
        doc.save(pdf)
        doc.close()
        try:
            with tempfile.TemporaryDirectory() as d:
                md = Path(d) / "m.md"
                md.write_text(
                    "<!-- pages 1-1 -->\n\na\n\n"
                    "<!-- pages 2-2 -->\n\nb\n\n"
                    "<!-- pages 3-3 -->\n\nc",
                    encoding="utf-8",
                )
                vpath = _create_validate_json([
                    {"name": "p0001-0001", "start_page": 1, "end_page": 1,
                     "page_type_summary": {"toc": 1},
                     "pages": [{"page": 0, "page_type": "toc"}]},
                    {"name": "p0002-0002", "start_page": 2, "end_page": 2,
                     "page_type_summary": {"toc": 1},
                     "pages": [{"page": 1, "page_type": "toc"}]},
                    {"name": "p0003-0003", "start_page": 3, "end_page": 3,
                     "page_type_summary": {"text": 1},
                     "pages": [{"page": 2, "page_type": "text"}]},
                ])
                repair_merged(Path(pdf), md, vpath)
                report = json.load(open(vpath, encoding="utf-8"))
                titles = [e["title"] for e in report.get("toc_unassigned", [])]
                self.assertIn("Beta", titles)  # 未归属 → 进 toc_unassigned
                self.assertNotIn("Alpha", titles)  # 已归属 → 不进
                os.unlink(vpath)
        finally:
            os.unlink(pdf)


class TestPageNumbering(unittest.TestCase):
    """页码坐标系检测与标准化。"""

    def test_detect_identity_single_label(self):
        """单 page label → identity。"""
        doc = fitz.open()
        doc.new_page()
        doc.new_page()
        # 显式设置单标签范围
        doc.set_page_labels([
            {"startpage": 0, "prefix": "", "firstpagenum": 1, "style": "D"},
        ])
        entries = [{"title": "T", "page": 1, "depth": 0}]
        numbering = _detect_page_numbering(doc, entries)
        doc.close()
        self.assertEqual(numbering["mapping_type"], "identity")

    def test_detect_unknown_no_labels(self):
        """无 page labels → unknown。"""
        doc = fitz.open()
        doc.new_page()
        entries = [{"title": "T", "page": 1, "depth": 0}]
        numbering = _detect_page_numbering(doc, entries)
        doc.close()
        self.assertEqual(numbering["mapping_type"], "unknown")
        self.assertEqual(numbering["status"], "needs_review")

    def test_detect_constant_offset_two_ranges(self):
        """两段标签、第二段 firstpagenum=1 → constant_offset。
        native_text 来源且 min_page >= body_start → needs_review（歧义）。
        """
        doc = fitz.open()
        for _ in range(10):
            doc.new_page()
        doc.set_page_labels([
            {"startpage": 0, "prefix": "", "firstpagenum": 1, "style": "D"},
            {"startpage": 1, "prefix": "", "firstpagenum": 1, "style": "D"},
        ])
        entries = [{"title": "前言", "page": 2, "depth": 0}]
        numbering = _detect_page_numbering(doc, entries, source="native_text")
        doc.close()
        self.assertEqual(numbering["mapping_type"], "constant_offset")
        self.assertEqual(numbering["printed_to_physical_offset"], 1)
        self.assertEqual(numbering["source_system"], "physical")
        # native_text + min_page(2) >= body_start(2) → 歧义未决
        self.assertEqual(numbering["status"], "needs_review")

    def test_detect_outline_source_verified(self):
        """outline 来源（PyMuPDF 保证物理页） → verified。"""
        doc = fitz.open()
        for _ in range(10):
            doc.new_page()
        doc.set_page_labels([
            {"startpage": 0, "prefix": "", "firstpagenum": 1, "style": "D"},
            {"startpage": 5, "prefix": "", "firstpagenum": 1, "style": "D"},
        ])
        entries = [{"title": "前言", "page": 6, "depth": 0}]
        numbering = _detect_page_numbering(doc, entries, source="outline")
        doc.close()
        self.assertEqual(numbering["mapping_type"], "constant_offset")
        self.assertEqual(numbering["printed_to_physical_offset"], 5)
        self.assertEqual(numbering["source_system"], "physical")
        self.assertEqual(numbering["status"], "verified")

    def test_detect_printed_source_when_small_pages(self):
        """条目页码低于正文起始物理页 → source_system=printed + verified。"""
        doc = fitz.open()
        for _ in range(10):
            doc.new_page()
        doc.set_page_labels([
            {"startpage": 0, "prefix": "", "firstpagenum": 1, "style": "D"},
            {"startpage": 5, "prefix": "", "firstpagenum": 1, "style": "D"},
        ])
        # 条目页码=1 小于 body_start=6 → 明确印刷页
        entries = [{"title": "前言", "page": 1, "depth": 0}]
        numbering = _detect_page_numbering(doc, entries, source="native_text")
        doc.close()
        self.assertEqual(numbering["source_system"], "printed")
        self.assertEqual(numbering["printed_to_physical_offset"], 5)
        self.assertEqual(numbering["status"], "verified")

    def test_detect_ambiguous_high_page_native_text(self):
        """偏移=8, body_start=9: 印刷页 10(→物理18) 不可被误判为物理 10。
        native_text 来源且 min_page >= body_start → needs_review。"""
        doc = fitz.open()
        for _ in range(20):
            doc.new_page()
        doc.set_page_labels([
            {"startpage": 0, "prefix": "", "firstpagenum": 1, "style": "D"},
            {"startpage": 8, "prefix": "", "firstpagenum": 1, "style": "D"},
        ])
        # 模拟文本层提取的条目：印刷页 10（正确物理页=18）
        entries = [{"title": "某章节", "page": 10, "depth": 0}]
        numbering = _detect_page_numbering(doc, entries, source="native_text")
        doc.close()
        self.assertEqual(numbering["printed_to_physical_offset"], 8)
        self.assertEqual(numbering["source_system"], "physical")
        # min_page(10) >= body_start(9) → 无法区分 → needs_review
        self.assertEqual(numbering["status"], "needs_review")

    def test_normalize_identity_no_changes(self):
        """identity 映射 → 条目不变。"""
        entries = [{"title": "T", "page": 5, "depth": 0}]
        numbering = {"mapping_type": "identity"}
        _normalize_entries(entries, numbering)
        self.assertEqual(entries[0]["page"], 5)
        self.assertNotIn("printed_page", entries[0])

    def test_normalize_unknown_no_changes(self):
        """unknown 映射 → 条目不变。"""
        entries = [{"title": "T", "page": 5, "depth": 0}]
        numbering = {"mapping_type": "unknown", "status": "needs_review"}
        _normalize_entries(entries, numbering)
        self.assertEqual(entries[0]["page"], 5)
        self.assertNotIn("printed_page", entries[0])

    def test_normalize_printed_to_physical(self):
        """印刷页条目 → 转为物理页，保留 printed_page。"""
        entries = [{"title": "参数", "page": 5, "depth": 0}]
        numbering = {
            "mapping_type": "constant_offset",
            "printed_to_physical_offset": 8,
            "source_system": "printed",
            "offset_applies_from_physical_page": 9,
        }
        _normalize_entries(entries, numbering)
        self.assertEqual(entries[0]["page"], 13)
        self.assertEqual(entries[0]["printed_page"], 5)

    def test_normalize_physical_records_printed(self):
        """物理页条目 → 保持 page，记录 printed_page。"""
        entries = [{"title": "参数", "page": 13, "depth": 0}]
        numbering = {
            "mapping_type": "constant_offset",
            "printed_to_physical_offset": 8,
            "source_system": "physical",
            "offset_applies_from_physical_page": 9,
        }
        _normalize_entries(entries, numbering)
        self.assertEqual(entries[0]["page"], 13)
        self.assertEqual(entries[0]["printed_page"], 5)

    def test_normalize_front_matter_no_printed_page(self):
        """前件页区域条目（物理页 < 正文起始）不添加 printed_page。"""
        entries = [{"title": "封面", "page": 1, "depth": 0}]
        numbering = {
            "mapping_type": "constant_offset",
            "printed_to_physical_offset": 8,
            "source_system": "physical",
            "offset_applies_from_physical_page": 9,
        }
        _normalize_entries(entries, numbering)
        self.assertEqual(entries[0]["page"], 1)
        self.assertNotIn("printed_page", entries[0])

    def test_write_toc_tree_with_printed_page(self):
        """含 printed_page 的条目写入 toc_tree.json。"""
        entries = [
            {"title": "参数", "page": 13, "toc_page": 2, "depth": 0,
             "printed_page": 5},
        ]
        with tempfile.TemporaryDirectory() as d:
            _write_toc_tree(Path(d), entries)
            tree = json.load(open(Path(d) / "toc_tree.json", encoding="utf-8"))
        self.assertEqual(tree[0]["target_page"], 13)
        self.assertEqual(tree[0]["printed_page"], 5)
        self.assertEqual(tree[0]["toc_page"], 2)

    def test_sync_manifest_no_existing(self):
        """manifest 不存在时 _sync_manifest 安全返回。"""
        with tempfile.TemporaryDirectory() as d:
            numbering = {"mapping_type": "identity", "status": "proposed"}
            # 不应抛出异常
            _sync_manifest_page_numbering(Path(d), numbering)
            self.assertFalse((Path(d) / "manifest.json").exists())

    def test_sync_manifest_preserves_existing_fields(self):
        """同步时不丢失现有 manifest 字段。"""
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            pkg.mkdir(parents=True, exist_ok=True)
            # 写现有 manifest
            original = {"model": "test", "parse_status": "ok", "hash": {"sha256": "abc"}}
            (pkg / "manifest.json").write_text(
                json.dumps(original, ensure_ascii=False), encoding="utf-8"
            )
            # 写 toc 文件
            (pkg / "toc.md").write_text("# TOC\n- item 1", encoding="utf-8")
            (pkg / "toc_tree.json").write_text('[{"title":"T","target_page":1}]', encoding="utf-8")

            numbering = {
                "physical_page_basis": "pdf_1_based",
                "mapping_type": "constant_offset",
                "printed_to_physical_offset": 8,
                "status": "verified",
                "evidence": [{"physical_start": 1, "printed_start": 1}],
            }
            _sync_manifest_page_numbering(pkg, numbering)

            m = json.load(open(pkg / "manifest.json", encoding="utf-8"))
            self.assertEqual(m["model"], "test")
            self.assertEqual(m["parse_status"], "ok")
            self.assertEqual(m["hash"]["sha256"], "abc")
            self.assertEqual(m["page_numbering"]["mapping_type"], "constant_offset")
            self.assertEqual(m["page_numbering"]["printed_to_physical_offset"], 8)
            self.assertIn("toc_md_sha256", m["hash"])
            self.assertIn("toc_tree_json_sha256", m["hash"])

    def test_review_evidence_unknown_mapping(self):
        """unknown 映射 → review.md 包含检测证据。"""
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            numbering = {
                "mapping_type": "unknown",
                "status": "needs_review",
                "evidence": [{"reason": "无 page labels"}],
            }
            _write_toc_review_evidence(pkg, numbering)
            review = (pkg / "review.md").read_text(encoding="utf-8")
            self.assertIn("## 页码坐标系未验证", review)
            self.assertIn("mapping_type", review)
            self.assertIn("needs_review", review)
            self.assertIn("PDF 不含 page labels", review)
            self.assertIn("无 page labels", review)

    def test_review_evidence_ambiguous_native_text(self):
        """偏移歧义 → review.md 含人工确认步骤和证据。"""
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            numbering = {
                "mapping_type": "constant_offset",
                "printed_to_physical_offset": 8,
                "offset_applies_from_physical_page": 9,
                "source_system": "physical",
                "status": "needs_review",
                "evidence": [
                    {"physical_start": 1, "printed_start": 1},
                    {"physical_start": 9, "printed_start": 1},
                    {"reason": "歧义: 文本层提取的条目页码(10)与正文起始物理页(9)重叠"},
                ],
            }
            _write_toc_review_evidence(pkg, numbering)
            review = (pkg / "review.md").read_text(encoding="utf-8")
            self.assertIn("## 页码坐标系未验证", review)
            self.assertIn("constant_offset", review)
            self.assertIn("source_system", review)
            self.assertIn("检测证据", review)

    def test_review_evidence_not_written_when_verified(self):
        """verified 状态不写入 review 证据。"""
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            numbering = {
                "mapping_type": "constant_offset",
                "status": "verified",
            }
            _write_toc_review_evidence(pkg, numbering)
            self.assertFalse((pkg / "review.md").exists())

    def test_review_evidence_idempotent(self):
        """第二次调用不重复追加段落。"""
        with tempfile.TemporaryDirectory() as d:
            pkg = Path(d)
            numbering = {
                "mapping_type": "unknown",
                "status": "needs_review",
                "evidence": [{"reason": "test"}],
            }
            _write_toc_review_evidence(pkg, numbering)
            first = (pkg / "review.md").read_text(encoding="utf-8")
            _write_toc_review_evidence(pkg, numbering)
            second = (pkg / "review.md").read_text(encoding="utf-8")
            self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
