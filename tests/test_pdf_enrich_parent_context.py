import csv
import hashlib
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pdf-enrich-parent-context"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def run_script(package: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(package)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_fills_only_blank_parent_and_moves_column_before_key(tmp_path: Path) -> None:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    fields = ["record_id", "key", "value", "review_status", "ingest_status", "parent_key"]
    rows = [
        {"record_id": "r1", "key": "型式", "value": "150A", "review_status": "approved",
         "ingest_status": "ready", "parent_key": ""},
        {"record_id": "r2", "key": "整数排量", "value": "149", "review_status": "approved",
         "ingest_status": "ready", "parent_key": "发动机"},
        {"record_id": "r3", "key": "备注", "value": "—", "review_status": "rejected",
         "ingest_status": "skipped", "parent_key": ""},
    ]
    ingest = data / "ingest_ready.csv"
    write_csv(ingest, fields, rows)
    write_csv(data / "parent_context_overrides.csv",
              ["record_id", "parent_key", "context_source", "notes"],
              [{"record_id": "r1", "parent_key": "发动机", "context_source": "human_review",
                "notes": "表头分类"}])

    result = run_script(package)

    assert result.returncode == 0, result.stderr
    output_fields, output_rows = read_csv(ingest)
    assert output_fields.index("parent_key") < output_fields.index("key")
    assert output_rows[0]["parent_key"] == "发动机"
    assert output_rows[1]["parent_key"] == "发动机"
    assert output_rows[2]["parent_key"] == ""
    assert [row["record_id"] for row in output_rows] == ["r1", "r2", "r3"]
    report = (data / "parent-context-enrichment-report.md").read_text(encoding="utf-8")
    assert "本轮补全：1" in report
    assert "仍为空：1" in report


def test_existing_parent_conflict_fails_without_mutating_input(tmp_path: Path) -> None:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    fields = ["record_id", "key", "parent_key"]
    write_csv(data / "ingest_ready.csv", fields,
              [{"record_id": "r1", "key": "型式", "parent_key": "发动机"}])
    write_csv(data / "parent_context_overrides.csv",
              ["record_id", "parent_key", "context_source", "notes"],
              [{"record_id": "r1", "parent_key": "车架", "context_source": "human_review",
                "notes": "冲突"}])
    original_hash = hashlib.sha256((data / "ingest_ready.csv").read_bytes()).hexdigest()

    result = run_script(package)

    assert result.returncode != 0
    assert "试图覆盖已有 parent_key" in result.stderr
    assert hashlib.sha256((data / "ingest_ready.csv").read_bytes()).hexdigest() == original_hash
    assert not (data / "parent-context-enrichment-report.md").exists()


def test_is_idempotent_without_new_overrides(tmp_path: Path) -> None:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    fields = ["record_id", "key", "parent_key"]
    write_csv(data / "ingest_ready.csv", fields,
              [{"record_id": "r1", "key": "型式", "parent_key": "发动机"}])

    first = run_script(package)
    first_bytes = (data / "ingest_ready.csv").read_bytes()
    second = run_script(package)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert (data / "ingest_ready.csv").read_bytes() == first_bytes


def test_preserves_duplicate_record_ids_without_overrides(tmp_path: Path) -> None:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    fields = ["record_id", "key", "parent_key"]
    rows = [
        {"record_id": "same", "key": "型式", "parent_key": ""},
        {"record_id": "same", "key": "整数排量", "parent_key": ""},
    ]
    write_csv(data / "ingest_ready.csv", fields, rows)

    result = run_script(package)

    assert result.returncode == 0, result.stderr
    output_fields, output_rows = read_csv(data / "ingest_ready.csv")
    assert output_fields.index("parent_key") < output_fields.index("key")
    assert [row["record_id"] for row in output_rows] == ["same", "same"]


def test_duplicate_record_ids_with_overrides_still_fail(tmp_path: Path) -> None:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    fields = ["record_id", "key", "parent_key"]
    write_csv(data / "ingest_ready.csv", fields, [
        {"record_id": "same", "key": "型式", "parent_key": ""},
        {"record_id": "same", "key": "整数排量", "parent_key": ""},
    ])
    write_csv(data / "parent_context_overrides.csv",
              ["record_id", "parent_key", "context_source", "notes"],
              [{"record_id": "same", "parent_key": "发动机",
                "context_source": "human_review", "notes": "表头分类"}])

    result = run_script(package)

    assert result.returncode != 0
    assert "不唯一" in result.stderr


def test_candidate_id_override_targets_one_of_duplicate_record_ids(tmp_path: Path) -> None:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    fields = ["candidate_id", "record_id", "key", "parent_key"]
    write_csv(data / "ingest_ready.csv", fields, [
        {"candidate_id": "c1", "record_id": "same", "key": "型式", "parent_key": ""},
        {"candidate_id": "c2", "record_id": "same", "key": "整数排量", "parent_key": ""},
    ])
    write_csv(data / "parent_context_overrides.csv",
              ["candidate_id", "parent_key", "context_source", "notes"],
              [{"candidate_id": "c2", "parent_key": "发动机",
                "context_source": "human_review", "notes": "同表分类"}])

    result = run_script(package)

    assert result.returncode == 0, result.stderr
    _, output_rows = read_csv(data / "ingest_ready.csv")
    assert [row["parent_key"] for row in output_rows] == ["", "发动机"]


def test_candidate_id_override_conflict_is_atomic(tmp_path: Path) -> None:
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    fields = ["candidate_id", "record_id", "key", "parent_key"]
    write_csv(data / "ingest_ready.csv", fields,
              [{"candidate_id": "c1", "record_id": "r1", "key": "型式", "parent_key": "发动机"}])
    write_csv(data / "parent_context_overrides.csv",
              ["candidate_id", "parent_key", "context_source", "notes"],
              [{"candidate_id": "c1", "parent_key": "车架",
                "context_source": "human_review", "notes": "冲突"}])
    original_hash = hashlib.sha256((data / "ingest_ready.csv").read_bytes()).hexdigest()

    result = run_script(package)

    assert result.returncode != 0
    assert "试图覆盖已有 parent_key" in result.stderr
    assert hashlib.sha256((data / "ingest_ready.csv").read_bytes()).hexdigest() == original_hash
