from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.legacy_parity

SCENE_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = SCENE_ROOT / "tests" / "fixtures" / "legacy_reference"


def test_phase0_documents_exist_when_baseline_is_locked() -> None:
    # Given: the Phase-0 documentation contract.
    required = (
        SCENE_ROOT / "PROVENANCE.md",
        SCENE_ROOT / "PAPER_INPUTS.md",
        SCENE_ROOT / "THIRD_PARTY_NOTICES.md",
        SCENE_ROOT / "LICENSES" / "MarsLab-Utils-MIT.md",
        SCENE_ROOT / "MIGRATION_TEST_MAP.md",
    )

    # When: their filesystem state is inspected.
    missing = [path.relative_to(SCENE_ROOT).as_posix() for path in required if not path.is_file()]

    # Then: no required record is absent.
    assert missing == []


def test_phase0_snapshot_is_self_authenticating_when_loaded() -> None:
    # Given: the committed legacy input and semantic snapshot.
    input_bytes = (FIXTURE_ROOT / "phase0_inputs.json").read_bytes()
    snapshot = json.loads((FIXTURE_ROOT / "phase0_snapshot.json").read_text(encoding="utf-8"))

    # When: consumer-visible digests are recalculated.
    semantic_bytes = json.dumps(
        snapshot["semantic_outputs"], sort_keys=True, separators=(",", ":")
    ).encode()
    observed_input_digest = hashlib.sha256(input_bytes).hexdigest()
    observed_semantic_digest = hashlib.sha256(semantic_bytes).hexdigest()

    # Then: source revision, seed, and both digests are pinned.
    assert snapshot["source_revision"] == "6f30d67f036462c6fb0d520945fde01d90f525d1"
    assert snapshot["seed"] == 42
    assert snapshot["input_sha256"] == observed_input_digest
    assert snapshot["semantic_sha256"] == observed_semantic_digest
