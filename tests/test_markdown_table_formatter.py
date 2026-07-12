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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "lib"))
from markdown_table_formatter import (
    format_tables,
    validate_structure,
    is_idempotent,
    TableFormatError,
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
