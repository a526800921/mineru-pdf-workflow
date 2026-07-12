"""pdf-merge 表格最终化事务回归。"""

import hashlib
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDF_MERGE = ROOT / "scripts" / "pdf-merge"


def _write_package(tmp_path: Path, segment_markdown: str, existing_markdown: str | None = None):
    pkg = tmp_path / "pkg"
    segment = pkg / "segments" / "p0001-0001"
    segment.mkdir(parents=True)
    (pkg / "manifest.json").write_text(
        json.dumps({"files": {"markdown": "pkg.md"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (segment / "page.md").write_text(segment_markdown, encoding="utf-8")
    if existing_markdown is not None:
        (pkg / "pkg.md").write_text(existing_markdown, encoding="utf-8")
    return pkg, segment.parent


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_merge(pkg: Path, segments: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PDF_MERGE_OUTPUT"] = str(pkg / "pkg.md")
    return subprocess.run(
        ["bash", str(PDF_MERGE), str(segments)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )


def test_pdf_merge_malformed_rolls_back_existing_outputs(tmp_path):
    pkg, segments = _write_package(
        tmp_path,
        "<table><tr><td>A</td></tr>\n",
        existing_markdown="ORIGINAL_CANONICAL\n",
    )
    md_hash = _sha256(pkg / "pkg.md")
    manifest_hash = _sha256(pkg / "manifest.json")

    result = _run_merge(pkg, segments)

    assert result.returncode != 0
    assert _sha256(pkg / "pkg.md") == md_hash
    assert _sha256(pkg / "manifest.json") == manifest_hash
    assert (pkg / "pkg.md").read_text(encoding="utf-8") == "ORIGINAL_CANONICAL\n"


def test_pdf_merge_formats_and_is_idempotent(tmp_path):
    pkg, segments = _write_package(
        tmp_path,
        "<table><tr><td>A</td><td>B</td></tr></table>\n",
    )

    first = _run_merge(pkg, segments)
    assert first.returncode == 0, first.stderr
    first_md_hash = _sha256(pkg / "pkg.md")
    first_manifest_hash = _sha256(pkg / "manifest.json")
    assert "\n  <tr>\n" in (pkg / "pkg.md").read_text(encoding="utf-8")

    second = _run_merge(pkg, segments)
    assert second.returncode == 0, second.stderr
    assert _sha256(pkg / "pkg.md") == first_md_hash
    assert _sha256(pkg / "manifest.json") == first_manifest_hash
