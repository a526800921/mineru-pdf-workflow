#!/usr/bin/env python3
"""vlm_eval 的单测（P4c）。

零依赖（无真实网络调用）：标准库 unittest + mock。
纯逻辑测试：页分类、响应校验、消息构建、渲染。
"""
import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from lib.vlm_eval import (  # noqa: E402
    _is_image_or_sparse_page,
    validate_vlm_response,
    build_vlm_messages,
    call_vlm_for_page,
    _normalize_vlm_fields,
    parse_segment_name,
    build_section_index,
    section_for_page,
    render_page,
    write_vlm_jsonl,
    VLM_SCHEMA,
)


class TestIsImageOrSparse(unittest.TestCase):
    """页分类逻辑：_is_image_or_sparse_page 的三个分支。"""

    def test_has_image_type(self):
        """content_list 含 image 类型 → True。"""
        cl_page = [{"type": "image", "bbox": [0, 0, 100, 100]}]
        self.assertTrue(_is_image_or_sparse_page("some text here", cl_page))

    def test_sparse_text_less_than_15_tokens(self):
        """PDF token < 15 且无 image → True。"""
        cl_page = [{"type": "paragraph", "content": "hello"}]
        self.assertTrue(_is_image_or_sparse_page("hello world", cl_page))

    def test_text_page_not_image_or_sparse(self):
        """content 含大量文本且无 image → False。"""
        cl_page = [{"type": "paragraph"}]
        text = " ".join(["word"] * 30)
        self.assertFalse(_is_image_or_sparse_page(text, cl_page))

    def test_empty_content_list(self):
        """空 content_list 且无文本 → True（token<15）。"""
        self.assertTrue(_is_image_or_sparse_page("hello", []))
        # 有足够文本 → False
        self.assertFalse(_is_image_or_sparse_page(" ".join(["word"] * 30), []))

    def test_table_type_not_image(self):
        """content_list 只有 table 类型 → 不是 image_or_sparse。"""
        cl_page = [{"type": "table"}]
        text = " ".join(["word"] * 30)
        self.assertFalse(_is_image_or_sparse_page(text, cl_page))


class TestValidateVlmResponse(unittest.TestCase):
    """响应校验：validate_vlm_response 的各类场景。"""

    def test_valid_response(self):
        """完全符合 Schema → (True, [])。"""
        data = {
            "page_summary": "警告页面",
            "visual_elements": [{"type": "icon", "description": "警告图标"}],
            "key_text": ["危险", "注意"],
            "confidence": 0.95,
        }
        is_valid, errors = validate_vlm_response(data)
        self.assertTrue(is_valid)
        self.assertEqual(errors, [])

    def test_missing_field(self):
        """缺少 page_summary → (False, [...] )。"""
        data = {"visual_elements": [], "key_text": [], "confidence": 0.8}
        is_valid, errors = validate_vlm_response(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("page_summary" in e for e in errors))

    def test_wrong_type_confidence(self):
        """confidence 为字符串 → 类型错误。"""
        data = {
            "page_summary": "test",
            "visual_elements": [],
            "key_text": [],
            "confidence": "high",
        }
        is_valid, errors = validate_vlm_response(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("confidence" in e for e in errors))

    def test_confidence_out_of_range(self):
        """confidence > 1 → 范围错误。"""
        data = {
            "page_summary": "test",
            "visual_elements": [],
            "key_text": [],
            "confidence": 1.5,
        }
        is_valid, errors = validate_vlm_response(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("范围" in e for e in errors))

    def test_confidence_none(self):
        """confidence 为 None → 允许（失败行场景）。"""
        data = {
            "page_summary": None,
            "visual_elements": [],
            "key_text": [],
            "confidence": None,
        }
        is_valid, errors = validate_vlm_response(data)
        self.assertTrue(is_valid)

    def test_not_a_dict(self):
        """响应不是 dict → (False, [...] )。"""
        is_valid, errors = validate_vlm_response("not a dict")
        self.assertFalse(is_valid)

    def test_visual_elements_missing_fields(self):
        """visual_elements 内的元素缺少 type 或 description。"""
        data = {
            "page_summary": "test",
            "visual_elements": [{"type": "icon"}],  # 缺少 description
            "key_text": [],
            "confidence": 0.5,
        }
        is_valid, errors = validate_vlm_response(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("description" in e for e in errors))

    def test_visual_elements_not_list_of_dicts(self):
        """visual_elements 内的元素不是 dict。"""
        data = {
            "page_summary": "test",
            "visual_elements": ["icon"],
            "key_text": [],
            "confidence": 0.5,
        }
        is_valid, errors = validate_vlm_response(data)
        # key_text 存在且为 list 无额外校验，但 visual_elements 的校验逻辑在 extra 块中
        self.assertTrue(isinstance(data.get("visual_elements"), list))
        # "icon" 不是 dict，extra 校验会报错
        is_valid, errors = validate_vlm_response(data)
        self.assertFalse(is_valid)
        self.assertTrue(any("不是 object" in e for e in errors))


class TestNormalizeVlmFields(unittest.TestCase):
    """字段名标准化。"""

    def test_dot_prefix_keys(self):
        """带 `.` 前缀的字段名 → 标准化为无点号版本。"""
        raw = {".page_summary": "test", ".visual_elements": [], ".key_text": [], ".confidence": 0.9}
        result = _normalize_vlm_fields(raw)
        self.assertEqual(result.get("page_summary"), "test")
        self.assertEqual(result.get("confidence"), 0.9)
        self.assertNotIn(".page_summary", result)

    def test_dot_prefix_not_overwrite_existing(self):
        """已有正确字段名时，点号版本不覆盖。"""
        raw = {"page_summary": "correct", ".page_summary": "wrong"}
        result = _normalize_vlm_fields(raw)
        self.assertEqual(result.get("page_summary"), "correct")

    def test_visual_elements_text_to_description(self):
        """visual_elements 子元素从 text → description。"""
        raw = {
            "page_summary": "test",
            "visual_elements": [{"type": "icon", "text": "warning"}],
            "key_text": [],
            "confidence": 0.5,
        }
        result = _normalize_vlm_fields(raw)
        ve = result["visual_elements"][0]
        self.assertEqual(ve.get("description"), "warning")

    def test_not_a_dict(self):
        """非 dict 输入不被修改。"""
        self.assertEqual(_normalize_vlm_fields("hello"), "hello")
        self.assertEqual(_normalize_vlm_fields(None), None)


class TestBuildVlmMessages(unittest.TestCase):
    """消息构建。"""

    def test_has_image_and_text(self):
        """构建的消息含 image_url 和 text 内容块。"""
        messages = build_vlm_messages(b"fake_png_bytes")
        self.assertGreater(len(messages), 0)

        # 最后一个 message 应为 user role
        user_msg = messages[-1]
        self.assertEqual(user_msg["role"], "user")

        # content 含 image_url 和 text
        content = user_msg["content"]
        types = [c["type"] for c in content]
        self.assertIn("image_url", types)
        self.assertIn("text", types)

        # image_url 使用 base64 data URI
        img_part = next(c for c in content if c["type"] == "image_url")
        self.assertTrue(img_part["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_no_system_prompt(self):
        """system_prompt=None 时不应有 system message。"""
        messages = build_vlm_messages(b"fake_png_bytes", system_prompt=None)
        roles = [m["role"] for m in messages]
        self.assertNotIn("system", roles)


class TestCallVlmForPage(unittest.TestCase):
    """VLM API 调用（mock，不碰真实网络）。"""

    @patch("openai.OpenAI")
    def test_successful_call(self, mock_openai_class):
        """VLM 返回有效 JSON → 正确解析为 dict。"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = json.dumps({
            "page_summary": "test",
            "visual_elements": [],
            "key_text": [],
            "confidence": 0.9,
        })
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = call_vlm_for_page(mock_client, "qwen3-vl-8b", b"fake_png")
        self.assertIsNotNone(result)
        self.assertEqual(result["page_summary"], "test")
        self.assertEqual(result["confidence"], 0.9)

    @patch("openai.OpenAI")
    def test_api_error_returns_none(self, mock_openai_class):
        """VLM API 异常 → 返回 None。"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        from openai import APIError
        mock_client.chat.completions.create.side_effect = APIError(
            "connection refused", request=None, body=None
        )

        result = call_vlm_for_page(mock_client, "qwen3-vl-8b", b"fake_png")
        self.assertIsNone(result)

    @patch("openai.OpenAI")
    def test_non_json_response_returns_none(self, mock_openai_class):
        """VLM 返回非 JSON → 返回 None。"""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_choice = MagicMock()
        mock_choice.message.content = "just plain text"
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[mock_choice]
        )

        result = call_vlm_for_page(mock_client, "qwen3-vl-8b", b"fake_png")
        self.assertIsNone(result)


class TestParseSegmentName(unittest.TestCase):
    """段名解析（复用 pdf-merge 口径）。"""

    def test_valid_segment(self):
        """标准段名 → (start, end)。"""
        self.assertEqual(parse_segment_name("p0001-0008"), (1, 8))

    def test_large_numbers(self):
        """大数字段名。"""
        self.assertEqual(parse_segment_name("p0185-0191"), (185, 191))

    def test_rerun_excluded(self):
        """-rerun 后缀 → None。"""
        self.assertIsNone(parse_segment_name("p0185-0191-rerun"))

    def test_ds_store(self):
        """.DS_Store → None。"""
        self.assertIsNone(parse_segment_name(".DS_Store"))


class TestBuildSectionIndex(unittest.TestCase):
    """章节索引构建。"""

    def test_empty_md(self):
        """空文本 → 空索引。"""
        self.assertEqual(build_section_index(""), [])

    def test_anchors_with_heading(self):
        """含锚点和 ## → 正确映射。"""
        md = "<!-- pages 1-8 -->\n## 安全注意事项\n内容\n<!-- pages 9-16 -->\n## 规格参数\n内容"
        idx = build_section_index(md)
        self.assertEqual(len(idx), 2)
        self.assertEqual(idx[0], (1, 8, "安全注意事项"))
        self.assertEqual(idx[1], (9, 16, "规格参数"))

    def test_heading_outside_anchor(self):
        """锚点前内容不产生索引项。"""
        md = "前言\n## 安全注意事项\n内容"
        # 无锚点 → 空
        self.assertEqual(build_section_index(md), [])

    def test_missing_heading_in_segment(self):
        """段内无 ## → section 为空串。"""
        md = "<!-- pages 1-8 -->\n无标题内容"
        idx = build_section_index(md)
        self.assertEqual(len(idx), 1)
        self.assertEqual(idx[0][2], "")


class TestSectionForPage(unittest.TestCase):
    """页→章节映射。"""

    def setUp(self):
        self.index = [(1, 8, "安全"), (9, 16, "规格")]

    def test_first_segment(self):
        """第 1 页 → "安全"。"""
        self.assertEqual(section_for_page(self.index, 1), "安全")

    def test_second_segment(self):
        """第 10 页 → "规格"。"""
        self.assertEqual(section_for_page(self.index, 10), "规格")

    def test_beyond_range(self):
        """超出范围 → 空串。"""
        self.assertEqual(section_for_page(self.index, 100), "")

    def test_empty_index(self):
        """空索引 → 空串。"""
        self.assertEqual(section_for_page([], 5), "")


class TestWriteVlmJsonl(unittest.TestCase):
    """JSONL 写入。"""

    def setUp(self):
        self.tmp_dir = Path("/tmp/test_vlm_write")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_write(self):
        """写入多行 JSONL 并可读取回。"""
        rows = [
            {"page": 1, "page_summary": "a", "parse_status": "ok"},
            {"page": 2, "page_summary": "b", "parse_status": "failed", "error": "err"},
        ]
        out = self.tmp_dir / "test.jsonl"
        result = write_vlm_jsonl(rows, out)
        self.assertEqual(result, out)
        self.assertTrue(out.exists())

        lines = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0]["page"], 1)
        self.assertEqual(lines[1]["parse_status"], "failed")

    def test_empty_rows(self):
        """空行列表 → 空文件。"""
        out = self.tmp_dir / "empty.jsonl"
        write_vlm_jsonl([], out)
        self.assertTrue(out.exists())
        self.assertEqual(out.read_text(encoding="utf-8").strip(), "")


class TestRenderPage(unittest.TestCase):
    """fitz 渲染（需要真实 PDF 文件）。"""

    @classmethod
    def setUpClass(cls):
        # 用项目测试 PDF（取春风 150AURA 第一页做快速探针）
        cls.pdf_path = Path("pdf/春风 150AURA/春风 150AURA.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("真实 PDF 不存在，跳过渲染测试")

    def test_render_first_page(self):
        """渲染第 1 页 → 返回非空 PNG 字节。"""
        img = render_page(self.pdf_path, 1)
        self.assertGreater(len(img), 0)
        # PNG 文件头
        self.assertTrue(img.startswith(b"\x89PNG"))

    def test_render_invalid_page(self):
        """无效页码 → IndexError。"""
        with self.assertRaises(IndexError):
            render_page(self.pdf_path, 9999)


if __name__ == "__main__":
    unittest.main()
