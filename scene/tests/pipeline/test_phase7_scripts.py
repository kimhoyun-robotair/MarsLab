from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from marslab_scene import build_scene
from marslab_scene.assets import io as asset_io
from marslab_scene.config import json_value
from marslab_scene.contracts import terrain as terrain_contract
from marslab_scene.usd import _manifest as scene_manifest
from marslab_scene.usd.validation import validate_runtime_package

pytestmark = [pytest.mark.contract, pytest.mark.standalone_usd]

_REPOSITORY_ROOT = Path(__file__).parents[3]
_SMOKE_RECIPE = _REPOSITORY_ROOT / "configs/scene/smoke.yaml"


def test_json_boundaries_reuse_adapter_loaded_before_usd_runtime() -> None:
    # Given / When / Then
    assert asset_io.JSON_VALUE_ADAPTER is json_value.JSON_VALUE_ADAPTER
    assert terrain_contract.JSON_VALUE_ADAPTER is json_value.JSON_VALUE_ADAPTER
    assert scene_manifest.JSON_VALUE_ADAPTER is json_value.JSON_VALUE_ADAPTER


def _run_script(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(_REPOSITORY_ROOT / "scene")
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )


def test_public_build_uses_recipe_and_records_output_override(tmp_path: Path) -> None:
    # Given
    output = tmp_path / "scene"

    # When
    artifact = build_scene(_SMOKE_RECIPE, output_dir=output)

    # Then
    manifest = artifact.manifest_path.read_text(encoding="utf-8")
    assert artifact.runtime_package_path.is_file()
    assert "output_override_applied: true" in manifest
    assert str(tmp_path) not in manifest


def test_runtime_package_validator_observes_terrain_and_dependency_closure(
    tmp_path: Path,
) -> None:
    # Given
    artifact = build_scene(_SMOKE_RECIPE, output_dir=tmp_path / "scene")

    # When
    report = validate_runtime_package(artifact.runtime_package_path)

    # Then
    assert report.default_prim == "/World"
    assert report.terrain_mesh_paths == (
        "/World/MarsTerrain/VisualMesh",
        "/World/MarsTerrain/CollisionMesh",
    )
    assert report.unresolved_dependencies == ()


def test_build_script_reports_existing_output_and_force_backup(tmp_path: Path) -> None:
    # Given
    output = tmp_path / "scene"
    script = "scripts/scene/build_scene.py"
    first = _run_script(script, "--config", str(_SMOKE_RECIPE), "--output-dir", str(output))

    # When
    rejected = _run_script(script, "--config", str(_SMOKE_RECIPE), "--output-dir", str(output))
    forced = _run_script(
        script,
        "--config",
        str(_SMOKE_RECIPE),
        "--output-dir",
        str(output),
        "--force",
    )

    # Then
    assert first.returncode == 0
    assert rejected.returncode != 0
    assert forced.returncode == 0
    completion = json.loads(forced.stdout)
    assert completion["published_path"] == str(output.resolve())
    assert Path(completion["previous_output_backup"]).is_dir()


def test_scripts_expose_help_and_invalid_recipe_is_nonzero(tmp_path: Path) -> None:
    # Given
    scripts = (
        "scripts/scene/build_scene.py",
        "scripts/scene/validate_assets.py",
        "scripts/scene/validate_scene.py",
        "scripts/scene/smoke_isaac.py",
    )
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("schema_version: 1\n", encoding="utf-8")

    # When
    help_results = tuple(_run_script(script, "--help") for script in scripts)
    rejected = _run_script("scripts/scene/build_scene.py", "--config", str(invalid))

    # Then
    assert all(result.returncode == 0 for result in help_results)
    assert rejected.returncode != 0


def test_asset_and_scene_validation_scripts_drive_real_public_validators(
    tmp_path: Path,
) -> None:
    # Given
    artifact = build_scene(_SMOKE_RECIPE, output_dir=tmp_path / "scene")

    # When
    assets = _run_script(
        "scripts/scene/validate_assets.py",
        "--fixture",
        "scene/tests/fixtures",
    )
    scene = _run_script(
        "scripts/scene/validate_scene.py",
        "--scene",
        str(artifact.runtime_package_path),
    )

    # Then
    assert assets.returncode == 0
    assert json.loads(assets.stdout)["input_tier"] == "synthetic"
    assert scene.returncode == 0
    assert json.loads(scene.stdout)["terrain_mesh_count"] == 2
