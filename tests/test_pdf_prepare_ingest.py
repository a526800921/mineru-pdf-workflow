import csv
import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pdf-prepare-ingest"
SOURCE_PDF_SHA256 = "a" * 64
LOADER = SourceFileLoader("pdf_prepare_ingest", str(SCRIPT))
SPEC = importlib.util.spec_from_loader("pdf_prepare_ingest", LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def draft_row(**overrides):
    row = {
        "source_pdf": "sample.pdf",
        "model": "sample",
        "section_path": "参数 / 发动机",
        "key": "排量",
        "value": "249 ml",
        "unit": "ml",
        "page_start": "14",
        "page_end": "14",
        "evidence_text": "排量：249 ml",
        "confidence": "high",
        "status": "draft",
        "notes": "colon_line",
        "source_block_id": "paragraph:1",
        "table_id": "",
        "row_index": "",
        "parent_key": "",
        "key_role": "business_key",
    }
    row.update(overrides)
    return row


def one_row(**overrides):
    return MODULE.generate_ingest_rows([draft_row(**overrides)])[0]


def v2_rows(rows):
    return MODULE.generate_ingest_rows(
        rows,
        candidate_identity_version=2,
        source_pdf_sha256=SOURCE_PDF_SHA256,
    )


def v2_row(**overrides):
    defaults = {
        "source_block_id": "html_table:7",
        "table_id": "html_table:7",
        "row_index": "2.1",
    }
    defaults.update(overrides)
    return v2_rows([draft_row(**defaults)])[0]


def decision(row, status, actor, basis, reason="证据与候选一致"):
    return {
        "candidate_id": row["candidate_id"],
        "record_id": row["record_id"],
        "review_status": status,
        "review_actor": actor,
        "decision_basis": basis,
        "review_rule_version": "llm-review-v1",
        "candidate_hash": row["candidate_hash"],
        "reason": reason,
        "reviewed_at": "",
    }


def apply_and_status(rows, decisions):
    MODULE.apply_review_decisions(rows, decisions)
    conflicts = MODULE.build_conflicts(rows)
    MODULE.compute_ingest_status(rows, conflicts)
    return conflicts


def test_llm_approved_requires_exact_evidence_and_reaches_ready():
    row = one_row()
    apply_and_status(rows := [row], {row["candidate_id"]: decision(
        row, "approved", "llm", "evidence_exact",
    )})

    assert row["review_status"] == "approved"
    assert row["review_actor"] == "llm"
    assert row["decision_basis"] == "evidence_exact"
    assert row["ingest_status"] == "ready"


def test_llm_rejected_is_skipped_and_keeps_reason():
    row = one_row(key="页脚", value="公司地址", evidence_text="公司地址：……")
    apply_and_status(rows := [row], {row["candidate_id"]: decision(
        row, "rejected", "llm", "rule_based_non_business", "明确为企业页脚信息",
    )})

    assert row["review_status"] == "rejected"
    assert row["ingest_status"] == "skipped"
    assert "明确为企业页脚信息" in row["notes"]


def test_llm_ambiguous_generates_user_escalation():
    row = one_row(status="needs_review", notes="colon_ambiguous")
    apply_and_status(rows := [row], {row["candidate_id"]: decision(
        row, "needs_review", "llm", "ambiguous", "两种列语义均有可能",
    )})

    queue = MODULE.build_escalation_queue(rows, [])
    assert row["ingest_status"] == "not_ready"
    assert len(queue) == 1
    assert queue[0]["requires_user"] is True
    assert queue[0]["recommended_action"] == "user_confirm"
    assert "review_needs_user" in queue[0]["ambiguity_type"]


def test_pending_draft_is_llm_queue_not_user_escalation():
    row = one_row()
    queue = MODULE.build_escalation_queue([row], [])

    assert len(queue) == 1
    assert queue[0]["requires_user"] is False
    assert queue[0]["recommended_action"] == "llm_review"
    assert queue[0]["ambiguity_type"] == "llm_review_pending"


def test_stale_candidate_hash_is_rejected():
    row = one_row()
    stale = decision(row, "approved", "llm", "evidence_exact")
    stale["candidate_hash"] = "stale"

    with pytest.raises(SystemExit, match="candidate_hash"):
        MODULE.apply_review_decisions([row], {row["candidate_id"]: stale})


def test_llm_cannot_approve_with_ambiguous_basis(tmp_path: Path):
    row = one_row()
    invalid = decision(row, "approved", "llm", "ambiguous")
    path = tmp_path / "review_decisions.jsonl"
    path.write_text(
        json.dumps(invalid, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="evidence_exact"):
        MODULE.read_review_decisions(path)


def test_review_decisions_reject_unknown_fields(tmp_path: Path):
    row = one_row()
    invalid = decision(row, "approved", "llm", "evidence_exact")
    invalid["unexpected"] = "no"
    path = tmp_path / "review_decisions.jsonl"
    path.write_text(json.dumps(invalid, ensure_ascii=False) + "\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="未知字段"):
        MODULE.read_review_decisions(path)


def test_legacy_override_remains_compatible(tmp_path: Path):
    row = one_row()
    path = tmp_path / "review_overrides.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["record_id", "review_status", "notes"])
        writer.writeheader()
        writer.writerow({
            "record_id": row["record_id"],
            "review_status": "approved",
            "notes": "旧格式确认",
        })

    overrides = MODULE.read_overrides(path)
    MODULE.apply_overrides([row], overrides)
    assert row["review_status"] == "approved"
    assert row["review_actor"] == ""
    assert MODULE.INGEST_FIELDS.index("candidate_id") > MODULE.INGEST_FIELDS.index("superseded_by")


def test_duplicate_record_override_is_rejected(tmp_path: Path):
    rows = MODULE.generate_ingest_rows([
        draft_row(source_block_id="paragraph:1"),
        draft_row(source_block_id="paragraph:2"),
    ])
    assert rows[0]["record_id"] == rows[1]["record_id"]
    assert rows[0]["candidate_id"] != rows[1]["candidate_id"]

    path = tmp_path / "review_overrides.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["record_id", "review_status", "notes"])
        writer.writeheader()
        writer.writerow({
            "record_id": rows[0]["record_id"],
            "review_status": "approved",
            "notes": "不应批量套用",
        })

    overrides = MODULE.read_overrides(path)
    with pytest.raises(SystemExit, match="candidate_id"):
        MODULE.apply_overrides(rows, overrides)
    assert all(row["review_status"] == "draft" for row in rows)

    queue = MODULE.build_escalation_queue(rows, [])
    assert len(queue) == 2
    assert all("duplicate_record_identity" in item["ambiguity_type"] for item in queue)


def test_duplicate_record_override_main_keeps_existing_outputs(tmp_path: Path):
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    source_rows = [
        draft_row(source_block_id="paragraph:1"),
        draft_row(source_block_id="paragraph:2"),
    ]
    with (data / "quick_lookup_draft.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(source_rows[0]))
        writer.writeheader()
        writer.writerows(source_rows)

    rows = MODULE.generate_ingest_rows(source_rows)
    (package / "manifest.json").write_text(
        json.dumps({"model": "sample", "page_numbering": {"status": "verified"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    with (data / "review_overrides.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["record_id", "review_status", "notes"])
        writer.writeheader()
        writer.writerow({
            "record_id": rows[0]["record_id"],
            "review_status": "approved",
            "notes": "重复身份",
        })

    sentinel = "previous-ready-output\n"
    (data / "ingest_ready.csv").write_text(sentinel, encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(package)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "candidate_id" in completed.stderr
    assert (data / "ingest_ready.csv").read_text(encoding="utf-8") == sentinel
    assert not (data / "conflicts.csv").exists()


def test_duplicate_candidate_identity_decision_is_rejected(tmp_path: Path):
    row = one_row()
    path = tmp_path / "review_decisions.jsonl"
    payload = decision(row, "approved", "llm", "evidence_exact")
    path.write_text(
        json.dumps(payload, ensure_ascii=False) + "\n"
        + json.dumps(payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="重复 candidate_id"):
        MODULE.read_review_decisions(path)


def test_unknown_candidate_identity_is_rejected():
    row = one_row()
    invalid = decision(row, "approved", "llm", "evidence_exact")
    invalid["candidate_id"] = "unknown-candidate"

    with pytest.raises(SystemExit, match="未知 candidate_id"):
        MODULE.apply_review_decisions([row], {invalid["candidate_id"]: invalid})


def test_user_decision_can_resolve_needs_review_without_record_override():
    row = one_row()
    row["review_status"] = "needs_review"
    row["ingest_status"] = "not_ready"
    apply_and_status([row], {row["candidate_id"]: decision(
        row, "approved", "user", "user_confirmed",
    )})

    assert row["review_status"] == "approved"
    assert row["review_actor"] == "user"
    assert row["ingest_status"] == "ready"


def test_coverage_supplement_without_context_cannot_reach_ready():
    row = one_row(
        section_path="",
        notes="html_table;coverage_supplement",
        status="needs_review",
    )
    apply_and_status([row], {row["candidate_id"]: decision(
        row, "approved", "user", "user_confirmed",
    )})

    assert row["ingest_status"] == "not_ready"
    assert "coverage_supplement_missing_context" in row["notes"]


def test_candidate_identity_stable():
    first = one_row(source_block_id="table:1", row_index="2")
    second = one_row(source_block_id="table:1", row_index="2")

    assert first["candidate_id"] == second["candidate_id"]
    assert first["candidate_hash"] == second["candidate_hash"]
    assert first["record_id"] == second["record_id"]


def test_candidate_v2_context_fields_do_not_change_identity_or_review_hash():
    first = v2_row()
    second = v2_row(
        model="revised-model",
        section_path="参数 / 传动",
        page_start="99",
        page_end="99",
        parent_key="发动机",
        key_role="local_label",
    )

    assert first["candidate_id"] == second["candidate_id"]
    assert first["candidate_hash"] == second["candidate_hash"]
    assert first["record_id"] != second["record_id"]


def test_candidate_v2_source_anchor_distinguishes_raw_table_row_and_pair_slot():
    rows = v2_rows([
        draft_row(source_block_id="html_table:7", table_id="html_table:7", row_index="2.1"),
        draft_row(source_block_id="html_table:7", table_id="html_table:7", row_index="2.2"),
        draft_row(source_block_id="html_table:8", table_id="html_table:8", row_index="2.1"),
    ])

    assert len({row["candidate_id"] for row in rows}) == 3


def test_candidate_v2_collision_is_not_disambiguated_by_business_content():
    rows = v2_rows([
        draft_row(key="M5 螺栓", value="5±1", source_block_id="html_table:117",
                  table_id="html_table:117", row_index="2.0"),
        draft_row(key="M5 螺钉", value="6±1", source_block_id="html_table:117",
                  table_id="html_table:117", row_index="2.0"),
    ])

    assert rows[0]["candidate_id"] == rows[1]["candidate_id"]
    assert "-" not in rows[0]["candidate_id"]
    assert rows[0]["candidate_hash"] != rows[1]["candidate_hash"]

    for row in rows:
        row["review_status"] = "approved"
    MODULE.compute_ingest_status(rows, [])
    assert all(row["ingest_status"] == "not_ready" for row in rows)
    assert all("duplicate_candidate_identity" in row["notes"] for row in rows)


def test_candidate_v2_decision_uses_identity_and_hash_not_record_id_snapshot():
    original = v2_row()
    recorded = decision(original, "approved", "llm", "evidence_exact")
    revised = v2_row(section_path="参数 / 传动")

    assert revised["candidate_id"] == original["candidate_id"]
    assert revised["candidate_hash"] == original["candidate_hash"]
    assert revised["record_id"] != original["record_id"]

    MODULE.apply_review_decisions(
        [revised], {recorded["candidate_id"]: recorded}
    )
    assert revised["review_status"] == "approved"


def test_candidate_v2_requires_source_pdf_sha256():
    with pytest.raises(ValueError, match="source PDF SHA-256"):
        MODULE.generate_ingest_rows(
            [draft_row(source_block_id="html_table:1", table_id="html_table:1", row_index="2")],
            candidate_identity_version=2,
        )


def test_duplicate_candidate_identity_is_escalated():
    rows = MODULE.generate_ingest_rows([
        draft_row(key="同一来源 A", value="1"),
        draft_row(key="同一来源 B", value="2"),
    ])
    assert rows[0]["candidate_id"] == rows[1]["candidate_id"]

    queue = MODULE.build_escalation_queue(rows, [])
    assert len(queue) == 2
    assert all(item["requires_user"] for item in queue)
    assert all("duplicate_candidate_identity" in item["ambiguity_type"] for item in queue)


def test_source_position_collision_is_disambiguated_by_content():
    rows = MODULE.generate_ingest_rows([
        draft_row(key="M5 螺栓，螺母", value="5±1", source_block_id="table:117",
                  table_id="table:117", row_index="1"),
        draft_row(key="M5 螺钉", value="5±1", source_block_id="table:117",
                  table_id="table:117", row_index="1"),
    ])

    assert rows[0]["candidate_id"] != rows[1]["candidate_id"]
    assert all("-" in row["candidate_id"] for row in rows)


def test_prepare_main_writes_audit_fields_and_empty_escalation_queue(tmp_path: Path):
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    source = draft_row()
    draft_path = data / "quick_lookup_draft.csv"
    with draft_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(source))
        writer.writeheader()
        writer.writerow(source)

    manifest = {
        "model": "sample",
        "files": {"markdown": "sample.md"},
        "page_numbering": {"status": "verified"},
    }
    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    prepared = one_row()
    review = decision(prepared, "approved", "llm", "evidence_exact")
    (data / "review_decisions.jsonl").write_text(
        json.dumps(review, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(package)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr

    with (data / "ingest_ready.csv").open(newline="", encoding="utf-8") as f:
        output = list(csv.DictReader(f))
    assert output[0]["ingest_status"] == "ready"
    assert output[0]["review_actor"] == "llm"
    assert output[0]["candidate_id"] == prepared["candidate_id"]
    assert (data / "escalation_queue.jsonl").read_text(encoding="utf-8") == ""


def test_prepare_main_reads_v2_manifest_contract(tmp_path: Path):
    package = tmp_path / "package"
    data = package / "data"
    data.mkdir(parents=True)
    source = draft_row(
        source_block_id="html_table:1", table_id="html_table:1", row_index="2",
    )
    with (data / "quick_lookup_draft.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(source))
        writer.writeheader()
        writer.writerow(source)
    (package / "manifest.json").write_text(
        json.dumps({
            "model": "sample",
            "hash": {"sha256": SOURCE_PDF_SHA256},
            "data_contract": {"candidate_identity_version": 2},
            "page_numbering": {"status": "verified"},
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    prepared = v2_row(
        source_block_id="html_table:1", table_id="html_table:1", row_index="2",
    )
    (data / "review_decisions.jsonl").write_text(
        json.dumps(decision(prepared, "approved", "llm", "evidence_exact"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), str(package)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    with (data / "ingest_ready.csv").open(newline="", encoding="utf-8") as f:
        output = list(csv.DictReader(f))
    assert output[0]["candidate_id"] == prepared["candidate_id"]
    assert output[0]["candidate_hash"] == prepared["candidate_hash"]
    assert output[0]["ingest_status"] == "ready"
