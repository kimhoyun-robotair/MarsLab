from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "verify_refactor_ledger.py"


def _write_fixture(evidence_dir: Path, *, artifact_hash: str | None = None) -> None:
    artifact = evidence_dir / "agent" / "task-1" / "pytest.txt"
    artifact.parent.mkdir(parents=True)
    artifact.write_text("1 passed\n", encoding="utf-8")
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = {
        "schema_version": 1,
        "stage_id": "S01",
        "commit_sha": "a" * 40,
        "automated_evidence": [
            {"path": "agent/task-1/pytest.txt", "sha256": artifact_hash or digest}
        ],
        "user_command": "marslab/isaac_python.sh marslab/main.py --help",
        "user_result": {"exit_code": 0, "path": "agent/task-1/pytest.txt", "sha256": digest},
        "approval_text": "APPROVE S01",
        "approval_time": "2026-08-12T20:00:00+09:00",
        "next_stage_eligibility": "S02",
    }
    task_dir = evidence_dir / "task-1"
    task_dir.mkdir(parents=True)
    manifest_path = task_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    ledger_record = {**manifest, "event": "stage-approved"}
    (evidence_dir / "ledger.jsonl").write_text(json.dumps(ledger_record) + "\n", encoding="utf-8")


def _run_validator(tmp_path: Path) -> subprocess.CompletedProcess[str]:
    plan = tmp_path / "plan.md"
    plan.write_text("- [ ] 1. S01 - first\n- [ ] 2. S02 - second\n", encoding="utf-8")
    source = tmp_path / "source.md"
    source.write_text("## 16. order\n1. first\n2. second\n", encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--plan",
            str(plan),
            "--source",
            str(source),
            "--evidence-dir",
            str(tmp_path / "evidence"),
            "--json-out",
            str(tmp_path / "report.json"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_valid_approved_stage_is_next_stage_eligible(tmp_path: Path) -> None:
    # Given: one approved stage with content-addressed agent and user evidence.
    _write_fixture(tmp_path / "evidence")

    # When: the ledger validator checks the partial gate chain.
    result = _run_validator(tmp_path)

    # Then: the chain is accepted and S02 is eligible.
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stderr
    assert report["verdict"] == "APPROVE"
    assert report["next_stage_eligible"] == "S02"


def test_tampered_evidence_is_rejected(tmp_path: Path) -> None:
    # Given: a manifest whose automated-evidence digest is not truthful.
    _write_fixture(tmp_path / "evidence", artifact_hash="0" * 64)

    # When: the ledger validator checks the chain.
    result = _run_validator(tmp_path)

    # Then: the process fails and identifies the integrity error structurally.
    report = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert result.returncode == 1
    assert report["verdict"] == "REJECT"
    assert report["integrity_errors"]
