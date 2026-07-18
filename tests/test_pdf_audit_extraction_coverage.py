import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pdf-audit-extraction-coverage"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_package(tmp_path: Path, *, header_rows: int | None, include_first_candidate: bool) -> Path:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    (package / "fixture.md").write_text(
        "<!-- pages 15-15 -->\n"
        "<table>\n<tbody>\n"
        "<tr><td colspan=\"2\">点火控制方式</td><td>ECU 点火</td></tr>\n"
        "<tr><td colspan=\"2\">润滑系统</td><td>压力+飞溅润滑</td></tr>\n"
        "</tbody>\n</table>\n",
        encoding="utf-8",
    )
    (package / "manifest.json").write_text(
        json.dumps({"files": {"markdown": "fixture.md", "pdf": "fixture.pdf"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    draft_fields = [
        "source_pdf", "model", "section_path", "key", "value", "unit",
        "page_start", "page_end", "evidence_text", "confidence", "status", "notes",
        "source_block_id", "table_id", "row_index", "parent_key", "key_role",
    ]
    rows = [{
        "source_pdf": "fixture.pdf", "model": "fixture", "section_path": "参数",
        "key": "点火控制方式" if include_first_candidate else "润滑系统",
        "value": "ECU 点火" if include_first_candidate else "压力+飞溅润滑",
        "unit": "", "page_start": "15", "page_end": "15", "evidence_text": "",
        "confidence": "medium", "status": "draft", "notes": "",
        "source_block_id": "html_table:1", "table_id": "html_table:1",
        "row_index": "1" if include_first_candidate else "1", "parent_key": "", "key_role": "business_key",
    }]
    if include_first_candidate:
        rows.append({**rows[0], "key": "润滑系统", "value": "压力+飞溅润滑", "row_index": "2"})
    write_csv(data / "quick_lookup_draft.csv", draft_fields, rows)
    if header_rows is not None:
        (data / "extraction_overrides.json").write_text(
            json.dumps({"tables": {"html_table:1": {
                "header_rows": header_rows, "key_column": 0, "value_columns": {"值": 2},
            }}}, ensure_ascii=False), encoding="utf-8",
        )
    return package


def run(package: Path, gate: bool = False) -> subprocess.CompletedProcess[str]:
    args = [sys.executable, str(SCRIPT), str(package)]
    if gate:
        args.append("--gate")
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False)


def read_coverage(package: Path) -> list[dict[str, str]]:
    with (package / "data" / "extraction_coverage.csv").open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_reports_no_header_first_row_as_missing_and_gate_blocks(tmp_path: Path) -> None:
    package = make_package(tmp_path, header_rows=None, include_first_candidate=False)

    result = run(package)

    assert result.returncode == 0, result.stderr
    rows = read_coverage(package)
    assert rows[0]["source_text"] == "点火控制方式 | ECU 点火"
    assert rows[0]["coverage_status"] == "missing_candidate"
    assert rows[1]["coverage_status"] == "covered"
    report = (package / "data" / "extraction-coverage-report.md").read_text(encoding="utf-8")
    assert "## 表级摘要" in report
    assert "html_table:1" in report
    gate = run(package, gate=True)
    assert gate.returncode != 0
    assert "未处置缺口" in gate.stderr


def test_header_rows_zero_covers_first_row_without_missing(tmp_path: Path) -> None:
    package = make_package(tmp_path, header_rows=0, include_first_candidate=True)

    result = run(package, gate=True)

    assert result.returncode == 0, result.stderr
    rows = read_coverage(package)
    assert all(row["coverage_status"] == "covered" for row in rows)


def test_zero_row_index_can_preserve_default_header_mapping(tmp_path: Path) -> None:
    package = make_package(tmp_path, header_rows=None, include_first_candidate=False)
    coverage = package / "data" / "quick_lookup_draft.csv"
    fields = [
        "source_pdf", "model", "section_path", "key", "value", "unit",
        "page_start", "page_end", "evidence_text", "confidence", "status", "notes",
        "source_block_id", "table_id", "row_index", "parent_key", "key_role",
    ]
    write_csv(coverage, fields, [{
        "source_pdf": "fixture.pdf", "model": "fixture", "section_path": "参数",
        "key": "点火控制方式", "value": "ECU 点火", "unit": "", "page_start": "15",
        "page_end": "15", "evidence_text": "", "confidence": "medium", "status": "needs_review",
        "notes": "coverage_supplement", "source_block_id": "html_table:1", "table_id": "html_table:1",
        "row_index": "0.1", "parent_key": "", "key_role": "business_key",
    }])

    result = run(package)

    assert result.returncode == 0, result.stderr
    updated = read_coverage(package)
    assert updated[0]["coverage_status"] == "covered"
    assert updated[0]["candidate_row_indices"] == "0.1"
    assert updated[1]["coverage_status"] == "missing_candidate"


def test_disposition_is_preserved_and_can_resolve_gap(tmp_path: Path) -> None:
    package = make_package(tmp_path, header_rows=None, include_first_candidate=False)
    assert run(package).returncode == 0
    coverage = package / "data" / "extraction_coverage.csv"
    rows = read_coverage(package)
    rows[0]["disposition"] = "non_business"
    rows[0]["notes"] = "fixture 用户确认"
    write_csv(coverage, list(rows[0]), rows)

    result = run(package, gate=True)

    assert result.returncode == 0, result.stderr
    updated = read_coverage(package)
    assert updated[0]["disposition"] == "non_business"
    assert updated[0]["notes"] == "fixture 用户确认"


def test_source_table_mapping_skips_single_row_tables(tmp_path: Path) -> None:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    (package / "fixture.md").write_text(
        "<!-- pages 1-1 -->\n"
        "<table><tr><td colspan=\"2\">章节说明</td></tr></table>\n"
        "<table>\n"
        "<tr><td>项目</td><td>值</td></tr>\n"
        "<tr><td>点火控制方式</td><td>ECU 点火</td></tr>\n"
        "</table>\n",
        encoding="utf-8",
    )
    (package / "manifest.json").write_text(
        json.dumps({"files": {"markdown": "fixture.md", "pdf": "fixture.pdf"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    fields = [
        "source_pdf", "model", "section_path", "key", "value", "unit",
        "page_start", "page_end", "evidence_text", "confidence", "status", "notes",
        "source_block_id", "table_id", "row_index", "parent_key", "key_role",
    ]
    write_csv(data / "quick_lookup_draft.csv", fields, [{
        "source_pdf": "fixture.pdf", "model": "fixture", "section_path": "参数",
        "key": "点火控制方式", "value": "ECU 点火", "unit": "", "page_start": "1",
        "page_end": "1", "evidence_text": "", "confidence": "medium", "status": "draft",
        "notes": "", "source_block_id": "html_table:1", "table_id": "html_table:1",
        "row_index": "1", "parent_key": "", "key_role": "business_key",
    }])
    (data / "extraction_overrides.json").write_text(
        json.dumps({"tables": {"html_table:1": {
            "header_rows": 1, "key_column": 0, "value_columns": {"值": 1},
        }}}, ensure_ascii=False), encoding="utf-8",
    )

    result = run(package, gate=True)

    assert result.returncode == 0, result.stderr
    rows = read_coverage(package)
    assert rows[0]["table_id"] == "html_table:1"
    assert rows[0]["coverage_status"] == "non_business"
    assert rows[1]["table_id"] == "html_table:2"
    assert rows[1]["coverage_status"] == "non_business"
    assert rows[2]["coverage_status"] == "covered"
