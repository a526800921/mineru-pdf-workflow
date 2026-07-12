"""测试 markdown_table_formatter — HTML 表格 pretty-print 格式化器。

覆盖:
- 简单表格、含 colspan/rowspan 表格、含图片表格
- 空单元格
- 幂等性
- malformed HTML 失败
- 无表格文本直通
- validate_structure
"""

import pytest
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
import markdown_table_formatter as formatter
from markdown_table_formatter import (
    format_tables,
    validate_structure,
    is_idempotent,
    TableFormatError,
    finalize_markdown_formatting,
)


# ── 简单表格 ──────────────────────────────────────────────────

def test_simple_table():
    md = "## 标题\n\n<table><tr><td>a</td><td>b</td></tr><tr><td>1</td><td>2</td></tr></table>"
    result = format_tables(md)
    assert result == (
        "## 标题\n\n"
        "<table>\n"
        "  <tr>\n"
        "    <td>a</td>\n"
        "    <td>b</td>\n"
        "  </tr>\n"
        "  <tr>\n"
        "    <td>1</td>\n"
        "    <td>2</td>\n"
        "  </tr>\n"
        "</table>"
    )


def test_empty_cell():
    md = "<table><tr><td></td><td>x</td></tr></table>"
    result = format_tables(md)
    assert result == (
        "<table>\n"
        "  <tr>\n"
        "    <td></td>\n"
        "    <td>x</td>\n"
        "  </tr>\n"
        "</table>"
    )


def test_colspan():
    md = "<table><tr><td colspan=\"2\">a</td><td>b</td></tr></table>"
    result = format_tables(md)
    assert "colspan=\"2\"" in result
    assert result == (
        "<table>\n"
        "  <tr>\n"
        "    <td colspan=\"2\">a</td>\n"
        "    <td>b</td>\n"
        "  </tr>\n"
        "</table>"
    )


def test_rowspan():
    md = "<table><tr><td rowspan=\"2\">a</td><td>b</td></tr><tr><td>c</td></tr></table>"
    result = format_tables(md)
    assert "rowspan=\"2\"" in result
    assert result == (
        "<table>\n"
        "  <tr>\n"
        "    <td rowspan=\"2\">a</td>\n"
        "    <td>b</td>\n"
        "  </tr>\n"
        "  <tr>\n"
        "    <td>c</td>\n"
        "  </tr>\n"
        "</table>"
    )


def test_rowspan_and_colspan():
    md = "<table><tr><td rowspan=\"2\" colspan=\"3\">a</td></tr><tr></tr></table>"
    result = format_tables(md)
    assert "rowspan=\"2\"" in result
    assert "colspan=\"3\"" in result


# ── 图片 ──────────────────────────────────────────────────────

def test_image_in_cell():
    md = '<table><tr><td><img src="img/a.jpg"/></td></tr></table>'
    result = format_tables(md)
    assert '<img src="img/a.jpg"/>' in result
    assert result == (
        "<table>\n"
        "  <tr>\n"
        '    <td><img src="img/a.jpg"/></td>\n'
        "  </tr>\n"
        "</table>"
    )


def test_image_with_rowspan():
    md = (
        '<table><tr>'
        '<td rowspan="2"><img src="a.jpg"/></td>'
        '<td colspan="2">text</td>'
        '<td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td><td></td>'
        '</tr><tr>'
        '<td><img src="b.jpg"/></td><td colspan="8">启动</td>'
        '</tr></table>'
    )
    result = format_tables(md)
    assert 'a.jpg' in result
    assert 'b.jpg' in result
    assert 'rowspan="2"' in result
    assert 'colspan="2"' in result
    assert 'colspan="8"' in result
    # 验证结构
    errors = validate_structure(md, result)
    assert not errors


# ── th 标签 ───────────────────────────────────────────────────

def test_th_tags():
    md = "<table><tr><th>col1</th><th>col2</th></tr><tr><td>a</td><td>b</td></tr></table>"
    result = format_tables(md)
    assert result == (
        "<table>\n"
        "  <tr>\n"
        "    <th>col1</th>\n"
        "    <th>col2</th>\n"
        "  </tr>\n"
        "  <tr>\n"
        "    <td>a</td>\n"
        "    <td>b</td>\n"
        "  </tr>\n"
        "</table>"
    )


# ── 多表格 ────────────────────────────────────────────────────

def test_multiple_tables():
    md = (
        "text before\n\n"
        "<table><tr><td>t1</td></tr></table>\n\n"
        "text between\n\n"
        "<table><tr><td>t2</td></tr></table>\n\n"
        "text after"
    )
    result = format_tables(md)
    # 表格外文本不变
    assert result.startswith("text before\n\n<table>")
    assert "\n\ntext between\n\n<table>" in result
    assert result.endswith("</table>\n\ntext after")
    # 两个表格都已格式化
    lines = result.split('\n')
    assert '    <td>t1</td>' in lines
    assert '    <td>t2</td>' in lines


# ── 幂等性 ────────────────────────────────────────────────────

def test_idempotent_simple():
    md = "<table><tr><td>a</td></tr></table>"
    first = format_tables(md)
    second = format_tables(first)
    assert first == second


def test_idempotent_formatted_input():
    formatted = "<table>\n  <tr>\n    <td>a</td>\n  </tr>\n</table>"
    result = format_tables(formatted)
    assert result == formatted


# ── 无表格 ────────────────────────────────────────────────────

def test_no_tables():
    md = "plain text\n\n## heading\n\nmore text"
    result = format_tables(md)
    assert result == md


def test_no_tables_unchanged():
    md = "some <b>bold</b> and <i>italic</i> but no table"
    result = format_tables(md)
    assert result == md


# ── malformed HTML ─────────────────────────────────────────────

def test_unclosed_table():
    md = "<table><tr><td>a</td></tr>"
    with pytest.raises(TableFormatError):
        format_tables(md)


def test_unclosed_tr():
    md = "<table><tr><td>a</td></table>"
    with pytest.raises(TableFormatError):
        format_tables(md)


def test_unclosed_td():
    md = "<table><tr><td>a</table>"
    with pytest.raises(TableFormatError):
        format_tables(md)


def test_mismatched_close_tags():
    md = "<table><tr><td>a</td></td></tr></table>"
    with pytest.raises(TableFormatError):
        format_tables(md)


# ── 修复 1: 已格式化外观不绕过 malformed 校验 ───────────────

def test_formatted_but_malformed_raises():
    """已格式化但标签错配的表格必须抛出 TableFormatError。"""
    md = (
        "<table>\n"
        "  <tr>\n"
        "    <td>a</td>\n"
        "  </tr>\n"
        # 多余的 </td> — 闭合标签不匹配
        "</td>\n"
        "</table>"
    )
    with pytest.raises(TableFormatError):
        format_tables(md)


def test_formatted_but_unclosed_raises():
    """已格式化但 <tr> 未闭合的表格必须抛出。"""
    md = (
        "<table>\n"
        "  <tr>\n"
        "    <td>a</td>\n"
        # 缺少 </tr>
        "</table>"
    )
    with pytest.raises(TableFormatError):
        format_tables(md)


# ── 修复 2: fenced code block 内的伪表格不被格式化 ──────────

def test_fenced_code_block_skipped():
    """``` 代码块内的 <table> 不应被格式化。"""
    md = (
        "## 示例\n\n"
        "```html\n"
        "<table><tr><td>code</td></tr></table>\n"
        "```\n\n"
        "真正的表格：\n\n"
        "<table><tr><td>real</td></tr></table>"
    )
    result = format_tables(md)
    # 代码块内应保持不变
    assert "<table><tr><td>code</td></tr></table>" in result
    # 真正的表格被格式化
    assert "    <td>real</td>" in result


def test_fenced_tilde_skipped():
    """~~~ 围栏代码块同样跳过。"""
    md = (
        "~~~\n"
        "<table><tr><td>a</td></tr></table>\n"
        "~~~\n"
    )
    result = format_tables(md)
    assert result == md  # 全部跳过


def test_multiple_fenced_blocks():
    """多个代码块中的表格全部跳过。"""
    md = (
        "```\n<table><tr><td>1</td></tr></table>\n```\n"
        "<table><tr><td>A</td></tr></table>\n"
        "```\n<table><tr><td>2</td></tr></table>\n```\n"
        "<table><tr><td>B</td></tr></table>"
    )
    result = format_tables(md)
    # 代码块内的两个都保持原样
    assert "<table><tr><td>1</td></tr></table>" in result
    assert "<table><tr><td>2</td></tr></table>" in result
    # 外部的两个被格式化
    assert "    <td>A</td>" in result
    assert "    <td>B</td>" in result


def test_fenced_with_language_tag():
    """```python 等语言标记也应跳过。"""
    md = (
        "```html\n"
        "<table><tr><td>x</td></tr></table>\n"
        "```\n"
    )
    result = format_tables(md)
    assert result == md


def test_unclosed_fence_skipped():
    """未闭合的 fence 延伸到文末，内中的表格应跳过。"""
    md = (
        "```html\n"
        "<table><tr><td>a</td></tr></table>\n"
        # fence 未闭合
    )
    result = format_tables(md)
    assert result == md  # 表格在未闭合 fence 内，跳过


# ── validate_structure ─────────────────────────────────────────

def test_validate_structure_pass():
    orig = "<table><tr><td>a</td><td>b</td></tr><tr><td>1</td><td>2</td></tr></table>"
    formatted = format_tables(orig)
    errors = validate_structure(orig, formatted)
    assert errors == []


def test_validate_structure_count_mismatch():
    orig = "<table><tr><td>a</td></tr></table><table><tr><td>b</td></tr></table>"
    bad = "<table><tr><td>a</td></tr></table>"
    errors = validate_structure(orig, bad)
    assert len(errors) > 0


# ── 修复 3: validate_structure 逐格校验 ──────────────────────

def test_validate_structure_cell_text_mismatch():
    """单元格文本不一致应被检测。"""
    orig = "<table><tr><td>foo</td></tr></table>"
    bad = "<table><tr><td>bar</td></tr></table>"
    errors = validate_structure(orig, bad)
    assert len(errors) > 0
    assert any("文本不一致" in e for e in errors)


def test_validate_structure_colspan_mismatch():
    """colspan 不一致应被检测。"""
    orig = '<table><tr><td colspan="2">a</td></tr></table>'
    bad = '<table><tr><td colspan="3">a</td></tr></table>'
    errors = validate_structure(orig, bad)
    assert len(errors) > 0
    assert any("colspan" in e for e in errors)


def test_validate_structure_rowspan_mismatch():
    """rowspan 不一致应被检测。"""
    orig = '<table><tr><td rowspan="2">a</td></tr><tr><td>b</td></tr></table>'
    bad = '<table><tr><td rowspan="1">a</td></tr><tr><td>b</td></tr></table>'
    errors = validate_structure(orig, bad)
    assert len(errors) > 0
    assert any("rowspan" in e for e in errors)


def test_validate_structure_per_row_col_count():
    """逐行列数不一致应被检测。"""
    orig = "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>"
    bad = "<table><tr><td>a</td></tr><tr><td>c</td><td>d</td></tr></table>"
    errors = validate_structure(orig, bad)
    assert len(errors) > 0
    assert any("列数不一致" in e for e in errors)


def test_validate_structure_img_count_mismatch():
    """图片数量不一致应被检测。"""
    orig = '<table><tr><td><img src="a.jpg"/></td></tr></table>'
    bad = '<table><tr><td></td></tr></table>'
    errors = validate_structure(orig, bad)
    assert len(errors) > 0
    assert any("img" in e for e in errors)


def test_validate_structure_empty_cell_text():
    """空单元格文本比较应通过（不报错）。"""
    orig = "<table><tr><td></td><td>x</td></tr></table>"
    formatted = format_tables(orig)
    errors = validate_structure(orig, formatted)
    assert errors == []


def test_validate_structure_unicode_cell_text():
    """Unicode 单元格内容应正确比较。"""
    orig = "<table><tr><td>单缸,四冲程</td></tr></table>"
    formatted = format_tables(orig)
    errors = validate_structure(orig, formatted)
    assert errors == []


def test_validate_structure_with_th():
    """th 标签的 colspan/rowspan/文本都应验证。"""
    orig = '<table><tr><th colspan="2">Header</th></tr><tr><td>a</td><td>b</td></tr></table>'
    formatted = format_tables(orig)
    errors = validate_structure(orig, formatted)
    assert errors == []


# ── 边界 ──────────────────────────────────────────────────────

def test_table_with_markdown_header():
    """表格前后的 markdown 头部不应被修改。"""
    md = "## 参数\n\n<table><tr><td>a</td></tr></table>\n\n## 尺寸"
    result = format_tables(md)
    assert result.startswith("## 参数\n\n<table>")
    assert result.endswith("</table>\n\n## 尺寸")


def test_cell_with_special_chars():
    """单元格内的特殊字符保持。"""
    md = "<table><tr><td>Kw / 9750 rpm</td><td>22 N·m / 7500 rpm</td></tr></table>"
    result = format_tables(md)
    assert "Kw / 9750 rpm" in result
    assert "22 N·m / 7500 rpm" in result


def test_cell_with_unicode():
    """单元格内的 Unicode 保持。"""
    md = "<table><tr><td>单缸,四冲程,水冷,立式</td></tr></table>"
    result = format_tables(md)
    assert "单缸,四冲程,水冷,立式" in result


# ── 真实 fixture ──────────────────────────────────────────────

def test_real_fixture_all_87_tables():
    """春风250Sr 真实 fixture：87 个表格全部可格式化。"""
    p = Path(__file__).resolve().parent.parent / "pdf" / "春风250Sr" / "春风250Sr.md"
    if not p.exists():
        pytest.skip("真实 fixture 不存在")
    text = p.read_text(encoding="utf-8")
    result = format_tables(text)
    # 表格数量一致
    assert result.count("<table>") == text.count("<table>")
    assert result.count("</table>") == text.count("</table>")
    # 所有表格均为多行格式
    for part in result.split("<table>")[1:]:
        assert part.startswith("\n"), "table open 后应为换行"
    # 幂等
    assert format_tables(result) == result


def test_real_fixture_structure():
    """春风250Sr：结构校验通过。"""
    p = Path(__file__).resolve().parent.parent / "pdf" / "春风250Sr" / "春风250Sr.md"
    if not p.exists():
        pytest.skip("真实 fixture 不存在")
    text = p.read_text(encoding="utf-8")
    result = format_tables(text)
    errors = validate_structure(text, result)
    assert not errors, f"结构校验失败: {errors}"


def test_real_fixture_non_table_text_unchanged():
    """春风250Sr：表格外的所有文本不变。"""
    import re

    p = Path(__file__).resolve().parent.parent / "pdf" / "春风250Sr" / "春风250Sr.md"
    if not p.exists():
        pytest.skip("真实 fixture 不存在")
    text = p.read_text(encoding="utf-8")
    result = format_tables(text)

    def non_table_regions(md):
        regions, pos = [], 0
        for m in re.finditer(r'<table>.*?</table>', md, re.DOTALL):
            if m.start() > pos:
                regions.append(md[pos:m.start()])
            pos = m.end()
        if pos < len(md):
            regions.append(md[pos:])
        return regions

    orig = non_table_regions(text)
    fmt = non_table_regions(result)
    for i, (o, f) in enumerate(zip(orig, fmt)):
        assert o == f, f"非表格区域 {i} 不一致"


def test_real_fixture_idempotent():
    """春风250Sr：幂等性。"""
    p = Path(__file__).resolve().parent.parent / "pdf" / "春风250Sr" / "春风250Sr.md"
    if not p.exists():
        pytest.skip("真实 fixture 不存在")
    text = p.read_text(encoding="utf-8")
    assert is_idempotent(text)


# ── 最终化事务 ────────────────────────────────────────────────

def _write_formatting_fixture(pkg: Path, markdown: str) -> tuple[Path, Path]:
    md_path = pkg / "demo.md"
    manifest_path = pkg / "manifest.json"
    md_path.write_text(markdown, encoding="utf-8")
    manifest_path.write_text(
        json.dumps({"files": {"markdown": "demo.md"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    return md_path, manifest_path


def test_finalize_malformed_keeps_markdown_and_manifest(tmp_path):
    """格式化失败不得覆盖已有 canonical Markdown 或 manifest。"""
    md_path, manifest_path = _write_formatting_fixture(
        tmp_path, "ORIGINAL\n<table><tr><td>A</td></tr>\n"
    )
    original_md = md_path.read_bytes()
    original_manifest = manifest_path.read_bytes()

    result = finalize_markdown_formatting(tmp_path)

    assert result["status"] == "error"
    assert md_path.read_bytes() == original_md
    assert manifest_path.read_bytes() == original_manifest
    assert not (tmp_path / "data").exists()


def test_finalize_write_failure_rolls_back_all_outputs(tmp_path, monkeypatch):
    """Markdown 或 manifest 提交中途失败时，整组派生产物回滚。"""
    md_path, manifest_path = _write_formatting_fixture(
        tmp_path, "<table><tr><td>A</td></tr></table>\n"
    )
    original_md = md_path.read_bytes()
    original_manifest = manifest_path.read_bytes()
    real_atomic_write = formatter._atomic_write
    calls = {"count": 0}

    def fail_manifest_write(path, content):
        calls["count"] += 1
        if calls["count"] == 3:
            raise OSError("injected manifest write failure")
        return real_atomic_write(path, content)

    monkeypatch.setattr(formatter, "_atomic_write", fail_manifest_write)
    result = finalize_markdown_formatting(tmp_path)

    assert result["status"] == "error"
    assert "injected manifest write failure" in result["error"]
    assert md_path.read_bytes() == original_md
    assert manifest_path.read_bytes() == original_manifest
    assert not (tmp_path / "data").exists()


def test_finalize_syncs_hash_when_only_non_table_text_changed(tmp_path):
    """TOC 等表格外修改后，已有 formatting hash 也必须刷新。"""
    md_path, manifest_path = _write_formatting_fixture(
        tmp_path,
        "目录修复后的标题\n\n<table>\n  <tr>\n    <td>A</td>\n  </tr>\n</table>\n",
    )
    stale_hash = "0" * 64
    manifest_path.write_text(
        json.dumps(
            {
                "files": {"markdown": "demo.md"},
                "formatting": {
                    "schema_version": 1,
                    "mode": "merge_time",
                    "status": "verified",
                    "source_markdown_sha256": "1" * 64,
                    "formatted_markdown_sha256": stale_hash,
                },
                "fixes": {"markdown_sha256": stale_hash},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = finalize_markdown_formatting(tmp_path)
    current_hash = __import__("hashlib").sha256(md_path.read_bytes()).hexdigest()
    updated = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert result["status"] == "ok"
    assert result["hash_synced"] is True
    assert updated["formatting"]["formatted_markdown_sha256"] == current_hash
    assert updated["fixes"]["markdown_sha256"] == current_hash
