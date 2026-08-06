import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pdf-extract-data"


def make_package(tmp_path: Path, *, protected: bool) -> Path:
    package = tmp_path / "package"
    data = package / "data"
    (package / "segments").mkdir(parents=True)
    data.mkdir(parents=True)
    (package / "manifest.json").write_text(
        json.dumps({"model": "sample", "files": {"markdown": "sample.md"}},
                   ensure_ascii=False),
        encoding="utf-8",
    )
    (package / "sample.md").write_text("示例正文\n", encoding="utf-8")
    if protected:
        (data / "quick_lookup_draft.csv").write_text(
            "key,value\n已审核,保留\n", encoding="utf-8"
        )
        (data / "review_decisions.jsonl").write_text(
            '{"candidate_id":"c1"}\n', encoding="utf-8"
        )
    return package


def run_script(package: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, str(package)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_rerun_with_review_artifacts_fails_before_writing(tmp_path: Path) -> None:
    package = make_package(tmp_path, protected=True)
    draft = package / "data" / "quick_lookup_draft.csv"
    before = draft.read_bytes()

    result = run_script(package)

    assert result.returncode != 0
    assert "普通重跑已阻断" in result.stderr
    assert draft.read_bytes() == before
    assert not (package / "data" / "verification.csv").exists()
    assert not (package / "data" / "fixtures_result.md").exists()


def test_root_review_artifact_also_blocks_rerun(tmp_path: Path) -> None:
    package = make_package(tmp_path, protected=False)
    review = package / "review.md"
    review.write_text("已审核内容\n", encoding="utf-8")

    result = run_script(package)

    assert result.returncode != 0
    assert "普通重跑已阻断" in result.stderr
    assert review.read_text(encoding="utf-8") == "已审核内容\n"


def test_first_extraction_without_review_artifacts_still_runs(tmp_path: Path) -> None:
    package = make_package(tmp_path, protected=False)

    result = run_script(package)

    assert result.returncode == 0, result.stderr
    assert (package / "data" / "quick_lookup_draft.csv").exists()
    assert (package / "data" / "verification.csv").exists()
    with (package / "data" / "quick_lookup_draft.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        assert list(csv.DictReader(handle)) == []


def test_force_rebuild_is_explicit(tmp_path: Path) -> None:
    package = make_package(tmp_path, protected=True)

    result = run_script(package, "--force-rebuild")

    assert result.returncode == 0, result.stderr
    assert "--force-rebuild" in result.stderr
    assert (package / "data" / "verification.csv").exists()
