import json
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.chunk_utils import export_chunks


def _write_manifest(package: Path, markdown="manual.md", **extra):
    manifest = {"model": "fixture-model", "files": {"markdown": markdown}}
    manifest.update(extra)
    (package / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )


def _write_package(tmp_path: Path, markdown="manual.md") -> Path:
    package = tmp_path / "package"
    package.mkdir()
    # 先写 TOC，确保旧的 glob 顺序选择确实有机会误选它。
    (package / "toc.md").write_text(
        "<!-- pages 1-1 -->\n## 目录\nTOCONLYMARKER\n", encoding="utf-8"
    )
    (package / "manual.md").write_text(
        "<!-- pages 1-1 -->\n## 正文\nMANUALONLYMARKER\n", encoding="utf-8"
    )
    _write_manifest(package, markdown)
    return package


def test_manifest_markdown_is_canonical_source(tmp_path):
    package = _write_package(tmp_path)

    chunks, output_path = export_chunks(package)

    assert output_path == package / "data" / "chunks.jsonl"
    assert len(chunks) == 1
    assert "MANUALONLYMARKER" in chunks[0]["content"]
    assert "TOCONLYMARKER" not in chunks[0]["content"]


@pytest.mark.parametrize(
    "manifest_writer, message",
    [
        (lambda package: (package / "manifest.json").unlink(), "manifest.json 不存在"),
        (
            lambda package: (package / "manifest.json").write_text(
                "not-json", encoding="utf-8"
            ),
            "manifest.json 解析失败",
        ),
        (
            lambda package: _write_manifest(package, markdown=None),
            "files.markdown 未配置",
        ),
    ],
)
def test_manifest_required_and_invalid_fail_without_output(
    tmp_path, manifest_writer, message
):
    package = _write_package(tmp_path)
    manifest_writer(package)

    with pytest.raises((FileNotFoundError, ValueError), match=message):
        export_chunks(package)

    assert not (package / "data" / "chunks.jsonl").exists()


@pytest.mark.parametrize("markdown", ["../manual.md", "/tmp/manual.md", "missing.md"])
def test_markdown_path_must_be_safe_and_existing(tmp_path, markdown):
    package = _write_package(tmp_path, markdown=markdown)

    with pytest.raises((FileNotFoundError, ValueError)):
        export_chunks(package)

    assert not (package / "data" / "chunks.jsonl").exists()


def test_output_contract_is_unchanged(tmp_path):
    package = _write_package(tmp_path)

    chunks, _ = export_chunks(package)

    assert set(chunks[0]) == {"id", "content", "page", "section", "token_count"}
    assert chunks[0]["id"] == "fixture-model@seq_001"
    assert chunks[0]["page"] == "1"
    assert chunks[0]["section"] == "正文"
    assert chunks[0]["token_count"] <= 384
