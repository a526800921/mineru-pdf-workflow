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
