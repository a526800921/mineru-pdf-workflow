"""pdf-run-helper 的事务、范围和幂等 fixture。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "scripts" / "pdf-run-helper"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_package(tmp_path: Path) -> tuple[Path, Path, Path]:
    package = tmp_path / "package"
    (package / "data").mkdir(parents=True)
    allowed = package / "data" / "manual_fixes.jsonl"
    protected = package / "manifest.json"
    source = package / "source.pdf"
    allowed.write_text('{"fix_id":"old"}\n', encoding="utf-8")
    protected.write_text('{"version":1}\n', encoding="utf-8")
    source.write_bytes(b"pdf evidence")
    return package, allowed, protected


def write_helper(tmp_path: Path, body: str) -> Path:
    helper = tmp_path / "dynamic_helper.py"
    helper.write_text(body, encoding="utf-8")
    return helper


def run(package: Path, dynamic: Path, *extra_allow: str) -> subprocess.CompletedProcess[str]:
    log = package.parent / "run.json"
    command = [
        sys.executable,
        str(HELPER),
        "--package",
        str(package),
        "--allow",
        "data/manual_fixes.jsonl",
        "--log",
        str(log),
    ]
    for value in extra_allow:
        command.extend(["--allow", value])
    command.extend(
        [
            "--validate-command",
            json.dumps([sys.executable, str(dynamic), "--package", str(package)]),
            "--",
            sys.executable,
            str(dynamic),
            "--package",
            str(package),
        ]
    )
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def test_success_only_changes_allowlisted_file(tmp_path: Path) -> None:
    package, allowed, protected = make_package(tmp_path)
    before_protected = digest(protected)
    dynamic = write_helper(
        tmp_path,
        """
import os
from pathlib import Path
package = Path(os.environ['PDF_HELPER_PACKAGE'])
if os.environ['PDF_HELPER_MODE'] == 'apply':
    (package / 'data/manual_fixes.jsonl').write_text('{\\"fix_id\\":\\"new\\"}\\n', encoding='utf-8')
""",
    )
    completed = run(package, dynamic)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert allowed.read_text(encoding="utf-8") == '{"fix_id":"new"}\n'
    assert digest(protected) == before_protected
    summary = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert summary["outcome"] == "success"
    assert summary["dry_run_changes"] == []
    assert summary["apply_changes"] == ["data/manual_fixes.jsonl"]


def test_dry_run_mutation_is_rejected_and_restored(tmp_path: Path) -> None:
    package, allowed, protected = make_package(tmp_path)
    before_allowed = digest(allowed)
    before_protected = digest(protected)
    dynamic = write_helper(
        tmp_path,
        """
import os
from pathlib import Path
package = Path(os.environ['PDF_HELPER_PACKAGE'])
(package / 'data/manual_fixes.jsonl').write_text('bad dry run\\n', encoding='utf-8')
""",
    )
    completed = run(package, dynamic)
    assert completed.returncode != 0
    assert digest(allowed) == before_allowed
    assert digest(protected) == before_protected
    summary = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert summary["reason"] == "dry_run_mutated_package"
    assert summary["rollback"] is True
    assert "apply" not in summary


def test_out_of_scope_change_rolls_back_entire_group(tmp_path: Path) -> None:
    package, allowed, protected = make_package(tmp_path)
    before_allowed = digest(allowed)
    before_protected = digest(protected)
    dynamic = write_helper(
        tmp_path,
        """
import os
from pathlib import Path
package = Path(os.environ['PDF_HELPER_PACKAGE'])
if os.environ['PDF_HELPER_MODE'] == 'apply':
    (package / 'data/manual_fixes.jsonl').write_text('partial\\n', encoding='utf-8')
    (package / 'manifest.json').write_text('forbidden\\n', encoding='utf-8')
""",
    )
    completed = run(package, dynamic)
    assert completed.returncode != 0
    assert digest(allowed) == before_allowed
    assert digest(protected) == before_protected
    summary = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert summary["reason"] == "out_of_scope_change"
    assert summary["rollback"] is True
    assert summary["unauthorized_changes"] == ["manifest.json"]


def test_failed_apply_rolls_back_and_second_success_is_idempotent(tmp_path: Path) -> None:
    package, allowed, _ = make_package(tmp_path)
    before_allowed = digest(allowed)
    dynamic = write_helper(
        tmp_path,
        """
import os
from pathlib import Path
package = Path(os.environ['PDF_HELPER_PACKAGE'])
if os.environ['PDF_HELPER_MODE'] == 'apply':
    (package / 'data/manual_fixes.jsonl').write_text('partial\\n', encoding='utf-8')
    raise SystemExit(7)
""",
    )
    failed = run(package, dynamic)
    assert failed.returncode != 0
    assert digest(allowed) == before_allowed
    failed_summary = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert failed_summary["reason"] == "apply_failed"

    dynamic.write_text(
        """
import os
from pathlib import Path
package = Path(os.environ['PDF_HELPER_PACKAGE'])
if os.environ['PDF_HELPER_MODE'] == 'apply':
    target = package / 'data/manual_fixes.jsonl'
    if target.read_text(encoding='utf-8') != '{\\"fix_id\\":\\"new\\"}\\n':
        target.write_text('{\\"fix_id\\":\\"new\\"}\\n', encoding='utf-8')
""",
        encoding="utf-8",
    )
    first = run(package, dynamic)
    assert first.returncode == 0, first.stdout + first.stderr
    first_hash = digest(allowed)
    second = run(package, dynamic)
    assert second.returncode == 0, second.stdout + second.stderr
    assert digest(allowed) == first_hash
    summary = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert summary["apply_changes"] == []


def test_validation_failure_rolls_back_after_apply(tmp_path: Path) -> None:
    package, allowed, _ = make_package(tmp_path)
    before_allowed = digest(allowed)
    dynamic = write_helper(
        tmp_path,
        """
import os
from pathlib import Path
package = Path(os.environ['PDF_HELPER_PACKAGE'])
if os.environ['PDF_HELPER_MODE'] == 'apply':
    (package / 'data/manual_fixes.jsonl').write_text('applied then invalid\\n', encoding='utf-8')
elif os.environ['PDF_HELPER_MODE'] == 'validate':
    raise SystemExit(9)
""",
    )
    completed = run(package, dynamic)
    assert completed.returncode != 0
    assert digest(allowed) == before_allowed
    summary = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert summary["reason"] == "validation_failed"
    assert summary["validate"]["exit_code"] == 9
    assert summary["rollback"] is True


def test_validation_mutation_rolls_back(tmp_path: Path) -> None:
    package, allowed, _ = make_package(tmp_path)
    before_allowed = digest(allowed)
    dynamic = write_helper(
        tmp_path,
        """
import os
from pathlib import Path
package = Path(os.environ['PDF_HELPER_PACKAGE'])
if os.environ['PDF_HELPER_MODE'] == 'apply':
    (package / 'data/manual_fixes.jsonl').write_text('valid candidate\\n', encoding='utf-8')
elif os.environ['PDF_HELPER_MODE'] == 'validate':
    (package / 'data/manual_fixes.jsonl').write_text('validation mutated\\n', encoding='utf-8')
""",
    )
    completed = run(package, dynamic)
    assert completed.returncode != 0
    assert digest(allowed) == before_allowed
    summary = json.loads((tmp_path / "run.json").read_text(encoding="utf-8"))
    assert summary["reason"] == "validation_mutated_package"
    assert summary["validate_changes"] == ["data/manual_fixes.jsonl"]


def test_gate_artifacts_cannot_be_allowlisted(tmp_path: Path) -> None:
    package, _, _ = make_package(tmp_path)
    dynamic = write_helper(tmp_path, "pass\n")
    for filename in (
        "review_overrides.csv",
        "ingest_ready.csv",
        "conflicts.csv",
        "ingest_batch.jsonl",
        "ingest_manifest.json",
    ):
        protected = package / "data" / filename
        protected.write_text("protected\n", encoding="utf-8")
        completed = run(package, dynamic, f"data/{filename}")
        assert completed.returncode == 2
        assert "审批/入库前门禁产物禁止" in completed.stderr


def test_original_evidence_cannot_be_allowlisted(tmp_path: Path) -> None:
    package, _, _ = make_package(tmp_path)
    command = [
        sys.executable,
        str(HELPER),
        "--package",
        str(package),
        "--allow",
        "source.pdf",
        "--validate-command",
        json.dumps([sys.executable, "-c", "pass"]),
        "--",
        sys.executable,
        "-c",
        "pass",
    ]
    completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 2
    assert "原始证据路径禁止授权" in completed.stderr
