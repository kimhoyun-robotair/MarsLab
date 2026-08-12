#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypedDict

STAGE_PATTERN = re.compile(r"^- \[[ x]\] \d+\. (S\d{2})\b", re.MULTILINE)
SOURCE_ITEM_PATTERN = re.compile(r"^(\d+)\. ", re.MULTILINE)
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class EvidenceRecord(TypedDict):
    path: str
    sha256: str


class UserResult(EvidenceRecord):
    exit_code: int


class StageRecord(TypedDict):
    schema_version: int
    stage_id: str
    commit_sha: str
    automated_evidence: list[EvidenceRecord]
    user_command: str
    user_result: UserResult
    approval_text: str
    approval_time: str
    next_stage_eligibility: str | None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    stages: int
    approvals: int
    commits: int
    unmapped_requirements: list[str]
    ordering_violations: list[str]
    stale_approvals: list[str]
    integrity_errors: list[str]
    next_stage_eligible: str | None
    verdict: str


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> StageRecord:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_evidence(
    evidence_dir: Path, stage_id: str, records: list[EvidenceRecord]
) -> list[str]:
    errors: list[str] = []
    for record in records:
        relative = Path(record["path"])
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"{stage_id}: invalid evidence path {relative}")
            continue
        artifact = evidence_dir / relative
        if not artifact.is_file():
            errors.append(f"{stage_id}: missing evidence {relative}")
        elif _sha256(artifact) != record["sha256"]:
            errors.append(f"{stage_id}: evidence hash mismatch {relative}")
    return errors


def _read_ledger(path: Path) -> list[StageRecord]:
    records: list[StageRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        if parsed.get("event") != "stage-approved":
            continue
        records.append(parsed)
    return records


def validate(plan: Path, source: Path, evidence_dir: Path) -> ValidationReport:
    planned_stages = STAGE_PATTERN.findall(plan.read_text(encoding="utf-8"))
    source_text = source.read_text(encoding="utf-8")
    ordered_section = source_text.split("## 16.", maxsplit=1)[-1].split("\n## ", maxsplit=1)[0]
    source_items = SOURCE_ITEM_PATTERN.findall(ordered_section)
    unmapped_requirements: list[str] = []
    if len(source_items) != len(planned_stages):
        unmapped_requirements.append(
            f"source items={len(source_items)} planned stages={len(planned_stages)}"
        )
    ledger_path = evidence_dir / "ledger.jsonl"
    ledger_records = _read_ledger(ledger_path) if ledger_path.is_file() else []
    integrity_errors: list[str] = []
    ordering_violations: list[str] = []
    stale_approvals: list[str] = []

    for index, stage_id in enumerate(planned_stages):
        manifest_path = evidence_dir / f"task-{index + 1}" / "manifest.json"
        if not manifest_path.is_file():
            break
        manifest = _load_json(manifest_path)
        if manifest.get("stage_id") != stage_id:
            ordering_violations.append(
                f"task-{index + 1}: expected {stage_id}, found {manifest.get('stage_id')}"
            )
            continue
        if manifest.get("schema_version") != 1:
            integrity_errors.append(f"{stage_id}: unsupported schema version")
        if not SHA_PATTERN.fullmatch(str(manifest.get("commit_sha", ""))):
            integrity_errors.append(f"{stage_id}: invalid commit SHA")
        if not manifest.get("user_command"):
            integrity_errors.append(f"{stage_id}: user command is missing")
        if manifest.get("approval_text") != f"APPROVE {stage_id}":
            stale_approvals.append(f"{stage_id}: approval text does not match stage")
        if not manifest.get("approval_time"):
            stale_approvals.append(f"{stage_id}: approval time is missing")
        user_result = manifest.get("user_result", {})
        if user_result.get("exit_code") != 0:
            integrity_errors.append(f"{stage_id}: user result did not exit zero")
        evidence_records = [*manifest.get("automated_evidence", []), user_result]
        integrity_errors.extend(_validate_evidence(evidence_dir, stage_id, evidence_records))
        expected_next = planned_stages[index + 1] if index + 1 < len(planned_stages) else None
        if manifest.get("next_stage_eligibility") != expected_next:
            ordering_violations.append(
                f"{stage_id}: expected next stage {expected_next}, "
                f"found {manifest.get('next_stage_eligibility')}"
            )
        if index >= len(ledger_records) or ledger_records[index] != {
            **manifest,
            "event": "stage-approved",
        }:
            integrity_errors.append(f"{stage_id}: ledger record does not match manifest")

    approvals = min(
        len(ledger_records),
        sum(
            (evidence_dir / f"task-{index + 1}" / "manifest.json").is_file()
            for index in range(len(planned_stages))
        ),
    )
    if len(ledger_records) != approvals:
        ordering_violations.append(
            f"approved ledger records={len(ledger_records)} manifests={approvals}"
        )
    next_stage = planned_stages[approvals] if approvals < len(planned_stages) else None
    errors = unmapped_requirements or integrity_errors or ordering_violations or stale_approvals
    return ValidationReport(
        stages=len(planned_stages),
        approvals=approvals,
        commits=approvals,
        unmapped_requirements=unmapped_requirements,
        ordering_violations=ordering_violations,
        stale_approvals=stale_approvals,
        integrity_errors=integrity_errors,
        next_stage_eligible=next_stage,
        verdict="REJECT" if errors else "APPROVE",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args()

    report = validate(args.plan, args.source, args.evidence_dir)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(report.verdict)
    return 0 if report.verdict == "APPROVE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
