from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from marslab.validation.lightweight import (
    validate_rover_file,
    validate_rover_manifest,
    validate_usdz_package,
)
from marslab.validation.models import RoverFacts, SceneFacts, ValidationReport
from marslab.validation.semantic import evaluate_rover_facts, evaluate_scene_facts

FactValue = str | int | float | None | tuple[str, ...] | frozenset[str]


def _codes(report: ValidationReport) -> set[str]:
    return {item.code for item in report.diagnostics}


def _scene(**overrides: FactValue) -> SceneFacts:
    valid = SceneFacts(
        default_prim="/World",
        up_axis="Z",
        meters_per_unit=1.0,
        prim_count=4,
        mesh_paths=("/World/Terrain",),
        collision_paths=("/World/Terrain",),
        physics_scene_paths=("/World/PhysicsScene",),
        layer_ids=("scene.usda",),
        asset_ids=(),
        unresolved_ids=(),
    )
    return replace(valid, **overrides)


def _rover(**overrides: FactValue) -> RoverFacts:
    valid = RoverFacts(
        default_prim="/Rover",
        up_axis="Z",
        meters_per_unit=1.0,
        prim_names=frozenset({"Rover", "Body_Chassis", "LF_DRIVE", "LF_STEER"}),
        articulation_paths=("/Rover/Body_Chassis",),
        layer_ids=("rover.usda",),
        asset_ids=(),
        unresolved_ids=(),
    )
    return replace(valid, **overrides)


def test_corrupt_zip_reports_typed_diagnostic(tmp_path: Path) -> None:
    bad = tmp_path / "scene.usdz"
    bad.write_bytes(b"not a zip")

    report = validate_usdz_package(bad)

    assert "scene.zip.corrupt" in _codes(report)


def test_corrupt_rover_usd_reports_before_openusd(tmp_path: Path) -> None:
    bad = tmp_path / "rover.usd"
    bad.write_bytes(b"not usd")

    report = validate_rover_file(bad)

    assert "rover.file.corrupt" in _codes(report)


def test_obviously_malformed_header_valid_usda_reports_before_openusd(tmp_path: Path) -> None:
    bad = tmp_path / "rover.usda"
    bad.write_bytes(b"#usda 1.0\nthis is not valid usd syntax {{{\n")

    report = validate_rover_file(bad)

    assert "rover.file.corrupt" in _codes(report)


_ISAAC_PYTHON = Path(os.environ.get("ISAAC_SIM_PATH", str(Path.home() / "isaacsim"))) / "python.sh"


@pytest.mark.skipif(not _ISAAC_PYTHON.is_file(), reason="Isaac Sim is not installed")
def test_cli_returns_nonzero_after_semantic_failure_and_isaac_shutdown(tmp_path: Path) -> None:
    rover = tmp_path / "empty.usda"
    rover.write_text("#usda 1.0\n", encoding="utf-8")
    output = tmp_path / "json"
    root = Path.cwd()

    completed = subprocess.run(
        [
            str(root / "marslab/isaac_python.sh"),
            "-m",
            "marslab.validation.assets",
            "--require-ros-companion",
            "--rover-manifest",
            str(root / "assets/robots/rover/manifest.json"),
            "--rover-usd",
            str(rover),
            "--rover-yaml",
            str(root / "configs/rover_m2020.yaml"),
            "--json-dir",
            str(output),
            "--scene",
            str(root / "assets/scene/jezero_plain/jezero_plain.usdz"),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    report = json.loads((output / "validate-rover.json").read_text(encoding="utf-8"))

    assert completed.returncode != 0
    assert report["ok"] is False
    assert "rover.default_prim.missing" in {item["code"] for item in report["diagnostics"]}
    assert "Simulation App Shutting Down" in completed.stdout


def test_zip_path_traversal_is_rejected(tmp_path: Path) -> None:
    bad = tmp_path / "scene.usdz"
    with zipfile.ZipFile(bad, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("../escape.usda", "#usda 1.0")

    report = validate_usdz_package(bad)

    assert "scene.zip.unsafe_member" in _codes(report)


def test_scene_semantic_contract_reports_each_structural_failure() -> None:
    report = evaluate_scene_facts(
        Path("bad.usda"),
        _scene(
            default_prim=None,
            up_axis="Y",
            meters_per_unit=0.01,
            mesh_paths=(),
            collision_paths=(),
            unresolved_ids=("missing.png",),
        ),
    )

    assert {
        "scene.default_prim.missing",
        "scene.up_axis.invalid",
        "scene.units.invalid",
        "scene.mesh.missing",
        "scene.collision.missing",
        "scene.dependency.unresolved",
    } <= _codes(report)


def test_rover_semantic_contract_reports_structure_failures() -> None:
    report = evaluate_rover_facts(
        Path("bad.usda"),
        _rover(articulation_paths=(), prim_names=frozenset({"Rover"})),
        drive_joints=("LF_DRIVE",),
        steer_joints=("LF_STEER",),
        sensor_mounts=("Body_Chassis",),
    )

    assert {
        "rover.articulation.missing",
        "rover.chassis.missing",
        "rover.joint.missing",
        "rover.mount.missing",
    } <= _codes(report)


def _git_init(path: Path) -> str:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "test@example.invalid"], check=True
    )
    subprocess.run(["git", "-C", str(path), "config", "user.name", "Test"], check=True)
    tracked = path / "mesh.bin"
    tracked.write_bytes(b"mesh")
    subprocess.run(["git", "-C", str(path), "add", "mesh.bin"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def _manifest(repo: Path, commit: str, *, include_urdf: bool = True) -> Path:
    (repo / ".git").mkdir(exist_ok=True)
    rover = repo / "assets/robots/rover"
    rover.mkdir(parents=True)
    usd = rover / "m2020.usd"
    usd.write_bytes(b"usd")
    companion = repo / "assets/m2020-urdf-models"
    if include_urdf:
        (companion / "rover").mkdir(parents=True, exist_ok=True)
        (companion / "rover/m2020.urdf").write_text("<robot/>", encoding="utf-8")
    data = {
        "schema_version": 1,
        "bundle_files": {"m2020.usd": hashlib.sha256(b"usd").hexdigest()},
        "submodule": {
            "path": "assets/m2020-urdf-models",
            "commit": commit,
            "ros_companion_urdf": "rover/m2020.urdf",
            "files": {"mesh.bin": hashlib.sha256(b"mesh").hexdigest()},
        },
    }
    path = rover / "manifest.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_uninitialized_submodule_is_actionable(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, "0" * 40)

    report = validate_rover_manifest(manifest, require_ros_companion=True)

    assert "rover.submodule.uninitialized" in _codes(report)


def test_wrong_submodule_commit_is_rejected(tmp_path: Path) -> None:
    commit = _git_init(tmp_path / "assets/m2020-urdf-models")
    manifest = _manifest(tmp_path, "f" * 40)

    report = validate_rover_manifest(manifest, require_ros_companion=True)

    assert commit != "f" * 40
    assert "rover.submodule.commit_mismatch" in _codes(report)


def test_missing_urdf_and_mesh_are_rejected(tmp_path: Path) -> None:
    commit = _git_init(tmp_path / "assets/m2020-urdf-models")
    manifest = _manifest(tmp_path, commit, include_urdf=False)
    (tmp_path / "assets/m2020-urdf-models/mesh.bin").unlink()

    report = validate_rover_manifest(manifest, require_ros_companion=True)

    assert {"rover.ros.urdf_missing", "rover.manifest.file_missing"} <= _codes(report)


def test_manifest_path_escape_is_rejected(tmp_path: Path) -> None:
    commit = _git_init(tmp_path / "assets/m2020-urdf-models")
    manifest = _manifest(tmp_path, commit)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["bundle_files"] = {"../../../escape": "0" * 64}
    manifest.write_text(json.dumps(data), encoding="utf-8")

    report = validate_rover_manifest(manifest, require_ros_companion=False)

    assert "rover.manifest.unsafe_path" in _codes(report)


def test_manifest_symlink_is_rejected(tmp_path: Path) -> None:
    commit = _git_init(tmp_path / "assets/m2020-urdf-models")
    manifest = _manifest(tmp_path, commit)
    rover_usd = manifest.parent / "m2020.usd"
    rover_usd.unlink()
    rover_usd.symlink_to(tmp_path / "assets/m2020-urdf-models/mesh.bin")

    report = validate_rover_manifest(manifest, require_ros_companion=False)

    assert "rover.manifest.unsafe_path" in _codes(report)
