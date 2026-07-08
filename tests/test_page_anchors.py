#!/usr/bin/env python3
"""per-page-anchors 阶段 1 单测（方案 A′ + X）。零依赖，unittest。"""
import glob
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from lib.page_anchors import (  # noqa: E402
    fingerprint,
    group_by_page,
    insert_page_anchors,
    locate_pages,
    strip_page_anchors,
)

_PKG = os.path.join(os.path.dirname(__file__), "..", "pdf", "春风 150AURA")


def _anchors(md):
    return [int(m) for m in re.findall(r"<!-- page (\d+) -->", md)]


class TestFingerprint(unittest.TestCase):
    def test_text_table_image(self):
        self.assertEqual(fingerprint({"type": "text", "text": " 你好 世界 "}), "你好世界")
        self.assertEqual(fingerprint({"type": "table", "table_body": "<table><tr><td>A</td>"}),
                         "<table><tr><td>A</td>")
        self.assertEqual(fingerprint({"type": "image", "img_path": "images/x.jpg"}), "images/x.jpg")

    def test_group_by_page(self):
        items = [{"type": "text", "text": "a", "page_idx": 0},
                 {"type": "text", "text": "b", "page_idx": 1},
                 {"type": "text", "text": "c", "page_idx": 0}]
        g = group_by_page(items)
        self.assertEqual(sorted(g), [0, 1])
        self.assertEqual([b["text"] for b in g[0]], ["a", "c"])


class TestInsert(unittest.TestCase):
    def test_two_page_exact(self):
        items = [{"type": "text", "text": "第一页开头", "page_idx": 0},
                 {"type": "text", "text": "第一页结尾", "page_idx": 0},
                 {"type": "text", "text": "第二页开头", "page_idx": 1},
                 {"type": "text", "text": "第二页结尾", "page_idx": 1}]
        md = "第一页开头\n\n第一页结尾\n\n第二页开头\n\n第二页结尾\n"
        result, warns = insert_page_anchors(md, items, 9)
        self.assertIn("<!-- page 9 -->\n第一页开头", result)
        self.assertIn("<!-- page 10 -->\n第二页开头", result)
        self.assertEqual(warns, [])
        self.assertEqual(_anchors(result), [9, 10])

    def test_content_unchanged(self):
        items = [{"type": "text", "text": "页一", "page_idx": 0},
                 {"type": "text", "text": "页二", "page_idx": 1}]
        md = "页一\n\n页二\n"
        result, _ = insert_page_anchors(md, items, 1)
        self.assertEqual(strip_page_anchors(result), md)  # 正文零改动不变量

    def test_first_miss_last_hit(self):
        # page1 首块被 toc_repair 改过（指纹找不到），尾块仍在 → tail 命中
        items = [{"type": "text", "text": "页零内容", "page_idx": 0},
                 {"type": "text", "text": "原始首块无法匹配", "page_idx": 1},
                 {"type": "text", "text": "页一尾块", "page_idx": 1}]
        md = "页零内容\n\n改过的首块\n\n页一尾块\n"
        result, warns = insert_page_anchors(md, items, 1)
        self.assertEqual(_anchors(result), [1, 2])
        self.assertTrue(any("tail_page:2" in w for w in warns))
        self.assertEqual(strip_page_anchors(result), md)

    def test_majority_miss_fallback(self):
        items = [{"type": "text", "text": "完全对不上A", "page_idx": 0},
                 {"type": "text", "text": "完全对不上B", "page_idx": 1}]
        md = "实际内容毫不相关\n"
        result, warns = insert_page_anchors(md, items, 1)
        self.assertEqual(result, md)  # 整段回退，正文不动
        self.assertTrue(any("segment_fallback" in w for w in warns))
        self.assertEqual(_anchors(result), [])

    def test_blank_page_sequential(self):
        # page_idx 1 无内容块（纯空白页）→ 顺序补，锚点严格连续
        items = [{"type": "text", "text": "第一页", "page_idx": 0},
                 {"type": "text", "text": "第三页", "page_idx": 2}]
        md = "第一页\n\n第三页\n"
        result, warns = insert_page_anchors(md, items, 5)
        self.assertEqual(_anchors(result), [5, 6, 7])
        self.assertTrue(any("blank_page:6" in w for w in warns))
        self.assertEqual(strip_page_anchors(result), md)

    def test_absolute_page_from_seg_start(self):
        items = [{"type": "text", "text": "唯一页", "page_idx": 0}]
        result, _ = insert_page_anchors("唯一页\n", items, 17)
        self.assertEqual(_anchors(result), [17])

    def test_locate_returns_offsets(self):
        items = [{"type": "text", "text": "甲", "page_idx": 0},
                 {"type": "text", "text": "乙", "page_idx": 1}]
        anchors, warns = locate_pages("甲\n\n乙\n", items, 1)
        self.assertEqual([p for _, p in anchors], [1, 2])
        self.assertEqual(warns, [])


class TestRealSegment(unittest.TestCase):
    @unittest.skipUnless(os.path.isdir(_PKG), "需要春风 150AURA 输出包")
    def test_body_segment_8of8(self):
        base = os.path.join(_PKG, "segments", "p0009-0016")
        cl = [f for f in glob.glob(base + "/**/*_content_list.json", recursive=True)
              if not f.endswith("_v2.json")][0]
        md_path = glob.glob(base + "/**/*.md", recursive=True)[0]
        with open(cl, encoding="utf-8") as f:
            items = json.load(f)
        with open(md_path, encoding="utf-8") as f:
            seg_md = f.read()
        result, _ = insert_page_anchors(seg_md, items, 9)
        self.assertEqual(_anchors(result), [9, 10, 11, 12, 13, 14, 15, 16])
        self.assertEqual(strip_page_anchors(result), seg_md)  # 正文零改动


def _read_regions(md):
    """按逐页锚点切分，返回 {page: 该页锚点到下一锚点间的正文}。"""
    parts = re.split(r"<!-- page (\d+) -->\n", md)
    regions = {}
    for i in range(1, len(parts), 2):
        regions[int(parts[i])] = parts[i + 1]
    return regions


class TestM1M2Fix(unittest.TestCase):
    def test_m1_reliable_page_region_not_stolen(self):
        # page10 可靠(exact)、page11 首尾失配(miss)、page12 可靠(exact)
        items = [{"type": "text", "text": "页零可靠内容", "page_idx": 0},
                 {"type": "text", "text": "无法匹配的首块XYZ", "page_idx": 1},
                 {"type": "text", "text": "页二可靠内容", "page_idx": 2}]
        md = "页零可靠内容\n\n实际页一内容\n\n页二可靠内容\n"
        result, warns = insert_page_anchors(md, items, 10, 12)
        regions = _read_regions(result)
        # M-1：可靠页 10 的 read region 不应被近似页偷空
        self.assertIn("页零可靠内容", regions.get(10, ""))
        self.assertTrue(regions[10].strip(), "page10 可靠页 region 被近似页偷空")
        self.assertEqual(_anchors(result), [10, 11, 12])
        self.assertEqual(strip_page_anchors(result), md)

    def test_m2_out_of_range_page_idx(self):
        # page_idx=50 越界（段声明 1-8 共 8 页）→ 不产越界锚点，记 warning
        items = [{"type": "text", "text": "甲", "page_idx": 0},
                 {"type": "text", "text": "乙", "page_idx": 50}]
        md = "甲\n\n乙\n"
        result, warns = insert_page_anchors(md, items, 1, 8)
        self.assertLessEqual(max(_anchors(result)), 8)
        self.assertTrue(any("out_of_range" in w for w in warns))

    def test_m2_tail_gap_no_silent_missing(self):
        # content_list 仅到 page_idx 2，段声明 1-5 共 5 页 → 尾部 4/5 不应静默丢失
        items = [{"type": "text", "text": "页一", "page_idx": 0},
                 {"type": "text", "text": "页三", "page_idx": 2}]
        md = "页一\n\n页三\n"
        result, warns = insert_page_anchors(md, items, 1, 5)
        self.assertEqual(_anchors(result), [1, 2, 3, 4, 5])
        self.assertEqual(strip_page_anchors(result), md)

    def test_all_anchors_on_own_line(self):
        # 段末近似页(page11 首尾失配、其后无 exact);seg_md 以 \n 结尾(pdf-merge 保证)
        # → 段末锚点必须独立成行,不粘正文行尾(回归防护:M-1 修复引入的粘行)
        items = [{"type": "text", "text": "页零可靠内容", "page_idx": 0},
                 {"type": "text", "text": "匹配不上的首块ABC", "page_idx": 1}]
        md = "页零可靠内容\n"
        result, _ = insert_page_anchors(md, items, 10, 11)
        for m in re.finditer(r"<!-- page \d+ -->", result):
            s = m.start()
            self.assertTrue(s == 0 or result[s - 1] == "\n",
                            f"锚点粘正文行尾 at offset {s}: {result[max(0,s-20):s+15]!r}")
        self.assertEqual(strip_page_anchors(result), md)


if __name__ == "__main__":
    unittest.main(verbosity=2)
