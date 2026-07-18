import importlib.machinery
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "pdf-export-ingest"
LOADER = importlib.machinery.SourceFileLoader("pdf_export_ingest", str(MODULE_PATH))
SPEC = importlib.util.spec_from_loader("pdf_export_ingest", LOADER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def stable_row(record_id: str, value: str = "150A") -> dict[str, str]:
    return {
        "record_id": record_id,
        "source_pdf": "manual.pdf",
        "model": "model",
        "section_path": "参数",
        "key": "型式",
        "value": value,
        "unit": "",
        "evidence_text": "型式: 150A",
        "source_row_hash": "source-hash",
        "review_status": "approved",
        "ingest_status": "ready",
    }


def test_carries_legacy_candidate_fields_without_mutating_ready(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    legacy = stable_row("r1")
    legacy.update({"candidate_id": "candidate-r1", "candidate_hash": "candidate-hash-r1"})
    (data / "ingest_batch.jsonl").write_text(
        json.dumps(legacy, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    current = stable_row("r1")

    result = MODULE.carry_legacy_candidate_fields(tmp_path, [current])

    assert current.get("candidate_id") is None
    assert current.get("candidate_hash") is None
    assert result[0]["candidate_id"] == "candidate-r1"
    assert result[0]["candidate_hash"] == "candidate-hash-r1"


def test_rejects_legacy_candidate_reuse_when_stable_content_changed(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    legacy = stable_row("r1")
    legacy.update({"candidate_id": "candidate-r1", "candidate_hash": "candidate-hash-r1"})
    (data / "ingest_batch.jsonl").write_text(
        json.dumps(legacy, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    current = stable_row("r1", value="150B")

    with pytest.raises(ValueError, match="稳定字段不一致"):
        MODULE.carry_legacy_candidate_fields(tmp_path, [current])


def test_keeps_record_without_legacy_candidate_fields_empty(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    legacy = stable_row("r1")
    (data / "ingest_batch.jsonl").write_text(
        json.dumps(legacy, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    current = stable_row("r1")

    result = MODULE.carry_legacy_candidate_fields(tmp_path, [current])

    assert "candidate_id" not in result[0]
    assert "candidate_hash" not in result[0]
