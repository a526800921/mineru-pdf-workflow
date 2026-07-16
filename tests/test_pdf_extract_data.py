import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pdf-extract-data"
LOADER = SourceFileLoader("pdf_extract_data", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("pdf_extract_data", LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


MAINTENANCE_MD = """
<!-- pages 86-86 -->
<table>
  <tr><th colspan="2" rowspan="2">项目</th><th colspan="4">磨合期后保养间隔</th></tr>
  <tr><th>小时</th><th>月份</th><th>km</th><th>备注</th></tr>
  <tr><td colspan="6">发动机</td></tr>
  <tr><td rowspan="2">▲■</td><td rowspan="2">空滤器滤芯</td><td>-</td><td>-</td><td>5000</td><td>清洗</td></tr>
  <tr><td>-</td><td>24M</td><td>20000</td><td>更换</td></tr>
</table>
"""

TABLE_OVERRIDE = {
    "header_rows": 2,
    "key_column": 1,
    "marker_column": 0,
    "value_columns": {"小时": 2, "月份": 3, "km": 4, "备注": 5},
    "category_row": "all_cells_equal",
}


def test_maintenance_table_expands_spans_and_preserves_marker():
    tables = MODULE.parse_html_tables_with_spans(MAINTENANCE_MD)
    assert tables[0][0][:6] == ["项目", "项目", "磨合期后保养间隔", "磨合期后保养间隔", "磨合期后保养间隔", "磨合期后保养间隔"]
    assert tables[0][4][:6] == ["▲■", "空滤器滤芯", "-", "24M", "20000", "更换"]

    rows = MODULE.extract_html_table_rows(
        MAINTENANCE_MD,
        [],
        "sample.pdf",
        "sample",
        {1: (86, 86)},
        MODULE.new_block_counters(),
        table_overrides={"html_table:1": TABLE_OVERRIDE},
    )

    assert [row["key"] for row in rows] == ["空滤器滤芯", "空滤器滤芯"]
    assert all(row["key_role"] == "business_key" for row in rows)
    assert rows[0]["value"] == "小时=-；月份=-；km=5000；备注=清洗"
    assert rows[1]["value"] == "小时=-；月份=24M；km=20000；备注=更换"
    assert all("marker=▲■" in row["notes"] for row in rows)
    assert all("▲■ 空滤器滤芯" in row["evidence_text"] for row in rows)
    assert all(row["parent_key"] == "发动机" for row in rows)


def test_maintenance_headers_and_categories_are_not_business_rows():
    rows = MODULE.extract_html_table_rows(
        MAINTENANCE_MD,
        [],
        "sample.pdf",
        "sample",
        {1: (86, 86)},
        MODULE.new_block_counters(),
        table_overrides={"html_table:1": TABLE_OVERRIDE},
    )
    assert not any(row["key"] in {"小时", "项目", "发动机"} for row in rows)


def test_numeric_keys_can_be_suppressed_by_package_policy():
    md = """
<!-- pages 29-29 -->
<table>
  <tr><td>编号</td><td>说明</td></tr>
  <tr><td>10</td><td>前制动手柄</td></tr>
</table>
10：前制动手柄
"""
    html_rows = MODULE.extract_html_table_rows(
        md, [], "sample.pdf", "sample", {1: (29, 29)},
        MODULE.new_block_counters(), numeric_key_policy="skip",
    )
    colon_rows = MODULE.extract_colon_rows(
        md, [], "sample.pdf", "sample", {1: (29, 29)},
        MODULE.new_block_counters(), numeric_key_policy="skip",
    )
    assert html_rows == []
    assert colon_rows == []


def test_colon_classification():
    assert MODULE.classify_colon_line("额定功率", "11.8 kW") == "business_candidate"
    assert MODULE.classify_colon_line("注意", "请勿在行驶中操作") == "non_business"
    assert MODULE.classify_colon_line("联系电话", "400-1234567") == "non_business"
    assert MODULE.classify_colon_line("版本", "1.0") == "ambiguous"


def test_colon_ambiguous_is_retained_for_review():
    md = """
<!-- pages 12-12 -->
版本：1.0
注意：请勿在行驶中操作
额定功率：11.8 kW
"""
    rows = MODULE.extract_colon_rows(
        md, [], "sample.pdf", "sample", {1: (12, 12)}, MODULE.new_block_counters(),
    )

    assert [row["key"] for row in rows] == ["版本", "额定功率"]
    assert rows[0]["status"] == "needs_review"
    assert "colon_class=ambiguous" in rows[0]["notes"]
    assert rows[1]["status"] == "draft"
    assert "colon_class=business_candidate" in rows[1]["notes"]


def test_pair_groups_expand_multiple_pairs():
    md = """
<!-- pages 20-20 -->
<table>
  <tr><th>项目 A</th><th>值 A</th><th>项目 B</th><th>值 B</th></tr>
  <tr><td>前制动</td><td>手柄</td><td>后制动</td><td>踏板</td></tr>
</table>
"""
    override = {
        "header_rows": 1,
        "pair_groups": [
            {"key_column": 0, "value_columns": {"说明": 1}},
            {"key_column": 2, "value_columns": {"说明": 3}},
        ],
    }
    rows = MODULE.extract_html_table_rows(
        md, [], "sample.pdf", "sample", {1: (20, 20)}, MODULE.new_block_counters(),
        table_overrides={"html_table:1": override},
    )

    assert [row["key"] for row in rows] == ["前制动", "后制动"]
    assert [row["row_index"] for row in rows] == ["1.1", "1.2"]
    assert [row["value"] for row in rows] == ["说明=手柄", "说明=踏板"]
    assert all(row["status"] == "needs_review" for row in rows)
    assert all("pair_group=" in row["notes"] for row in rows)
    assert rows[0]["source_block_id"] == rows[1]["source_block_id"]


def test_pair_groups_out_of_range_columns_are_skipped():
    md = """
<table><tr><th>项目</th><th>值</th></tr><tr><td>A</td><td>B</td></tr></table>
"""
    override = {
        "pair_groups": [{"key_column": 0, "value_columns": {"说明": 8}}],
    }
    rows = MODULE.extract_html_table_rows(
        md, [], "sample.pdf", "sample", {}, MODULE.new_block_counters(),
        table_overrides={"html_table:1": override},
    )

    assert rows == []
