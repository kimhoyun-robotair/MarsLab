from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Literal, assert_never

import pytest
from pydantic import JsonValue, TypeAdapter

pytestmark = [pytest.mark.isaac_runtime, pytest.mark.marslab_runtime]

_JSON_ADAPTER = TypeAdapter(JsonValue)
_REPOSITORY_ROOT = Path(__file__).parents[3]


def _input_tier() -> Literal["synthetic", "canonical", "paper"]:
    value = os.environ.get("MARSLAB_SCENE_INPUT_TIER", "synthetic")
    match value:
        case "synthetic" | "canonical" | "paper":
            return value
        case unreachable:
            assert_never(unreachable)


def test_actual_isaac_and_marslab_assembly_load_final_scene() -> None:
    # Given
    scene = os.environ.get("MARSLAB_SCENE_RUNTIME_PACKAGE")
    base_config = os.environ.get("MARSLAB_BASE_RUNTIME_CONFIG")
    report_path = os.environ.get("MARSLAB_RUNTIME_REPORT")
    if scene is None or base_config is None or report_path is None:
        pytest.skip("actual runtime inputs were not provided")

    # When
    completed = subprocess.run(
        [
            str(_REPOSITORY_ROOT / "marslab/isaac_python.sh"),
            str(_REPOSITORY_ROOT / "scripts/scene/smoke_isaac.py"),
            "--scene",
            scene,
            "--base-runtime-config",
            base_config,
            "--report",
            report_path,
            "--input-tier",
            _input_tier(),
        ],
        cwd=_REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    report = _JSON_ADAPTER.validate_python(
        json.loads(Path(report_path).read_text(encoding="utf-8"))
    )

    # Then
    assert completed.returncode == 0, completed.stderr
    assert isinstance(report, dict)
    assert report["status"] == "PASS"
    assert report["simulation_app_started"] is True
    assert report["world_initialized"] is True
    assert report["marslab_assembly_invoked"] is True
    assert report["runtime_updates_completed"] >= 1
    assert report["terrain_mesh_paths"]
    assert not report["unresolved_dependencies"]
