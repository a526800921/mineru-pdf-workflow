import csv
import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pdf-parent-context-review"
ENRICH_SCRIPT = ROOT / "scripts" / "pdf-enrich-parent-context"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def run_script(package: Path, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(package), command],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def make_package(tmp_path: Path) -> tuple[Path, Path]:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    fields = [
        "candidate_id", "record_id", "section_path", "key", "parent_key",
        "review_status", "ingest_status",
    ]
    rows = [
        {"candidate_id": "c1", "record_id": "r1", "section_path": "操作部件 / 锁具",
         "key": "油箱盖", "parent_key": "", "review_status": "approved", "ingest_status": "ready"},
        {"candidate_id": "c2", "record_id": "r2", "section_path": "参数",
         "key": "燃油箱容量", "parent_key": "", "review_status": "approved", "ingest_status": "ready"},
        {"candidate_id": "c3", "record_id": "r3", "section_path": "操作部件 / 锁具",
         "key": "锁具", "parent_key": "", "review_status": "approved", "ingest_status": "ready"},
        {"candidate_id": "c4", "record_id": "r4", "section_path": "操作部件 / 锁具",
         "key": "座垫锁", "parent_key": "", "review_status": "approved", "ingest_status": "skipped"},
        {"candidate_id": "c5", "record_id": "r5", "section_path": "操作部件 / 锁具",
         "key": "方向锁", "parent_key": "", "review_status": "approved", "ingest_status": "ready"},
    ]
    write_csv(data / "ingest_ready.csv", fields, rows)
    return package, data


def test_suggest_is_review_only_and_conservative(tmp_path: Path) -> None:
    package, data = make_package(tmp_path)
    original_hash = hashlib.sha256((data / "ingest_ready.csv").read_bytes()).hexdigest()

    result = run_script(package, "suggest")

    assert result.returncode == 0, result.stderr
    assert hashlib.sha256((data / "ingest_ready.csv").read_bytes()).hexdigest() == original_hash
    _, suggestions = read_csv(data / "parent_context_suggestions.csv")
    by_id = {row["candidate_id"]: row for row in suggestions}
    assert by_id["c1"]["suggested_parent_key"] == "锁具"
    assert by_id["c1"]["confidence"] == "low"
    assert by_id["c2"]["suggested_parent_key"] == ""
    assert by_id["c3"]["suggested_parent_key"] == ""
    assert by_id["c4"]["suggested_parent_key"] == ""
    assert "生成待确认建议：2" in (data / "parent-context-review-suggestion-report.md").read_text(encoding="utf-8")


def test_apply_only_approved_suggestions_to_override(tmp_path: Path) -> None:
    package, data = make_package(tmp_path)
    assert run_script(package, "suggest").returncode == 0
    fields, suggestions = read_csv(data / "parent_context_suggestions.csv")
    for row in suggestions:
        if row["candidate_id"] == "c1":
            row["decision"] = "approve"
        elif row["candidate_id"] in {"c2", "c3"}:
            row["decision"] = "reject"
    write_csv(data / "parent_context_suggestions.csv", fields, suggestions)

    result = run_script(package, "apply")

    assert result.returncode == 0, result.stderr
    _, overrides = read_csv(data / "parent_context_overrides.csv")
    assert overrides == [{
        "candidate_id": "c1",
        "record_id": "",
        "parent_key": "锁具",
        "context_source": "section_path_fallback",
        "notes": "使用 section_path 末级标题作为待确认父级：锁具",
    }]
    enrich = subprocess.run(
        [sys.executable, str(ENRICH_SCRIPT), str(package)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert enrich.returncode == 0, enrich.stderr
    _, ingest_rows = read_csv(data / "ingest_ready.csv")
    assert next(row for row in ingest_rows if row["candidate_id"] == "c1")["parent_key"] == "锁具"
    assert "待处理：2" in (data / "parent-context-review-apply-report.md").read_text(encoding="utf-8")


def test_apply_rejects_self_reference_without_writing_override(tmp_path: Path) -> None:
    package, data = make_package(tmp_path)
    assert run_script(package, "suggest").returncode == 0
    fields, suggestions = read_csv(data / "parent_context_suggestions.csv")
    for row in suggestions:
        if row["candidate_id"] == "c3":
            row["decision"] = "approve"
            row["suggested_parent_key"] = "锁具"
    write_csv(data / "parent_context_suggestions.csv", fields, suggestions)

    result = run_script(package, "apply")

    assert result.returncode != 0
    assert "parent_key 不得与 key 相同" in result.stderr
    assert not (data / "parent_context_overrides.csv").exists()
