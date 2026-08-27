from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import marslab_scene
import pytest
import yaml
from marslab_scene.assets import load_habitat_asset, load_rock_asset
from pydantic import JsonValue

pytestmark = [pytest.mark.contract, pytest.mark.standalone_usd]

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "assets"


def _copy_bundle(tmp_path: Path, name: str) -> Path:
    destination = tmp_path / name
    shutil.copytree(_FIXTURES / name, destination)
    return destination / "manifest.yaml"


def _read_manifest(path: Path) -> dict[str, JsonValue]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_manifest(path: Path, value: dict[str, JsonValue]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_rock_loader_rejects_missing_declared_file(tmp_path: Path) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "rocks")
    (manifest.parent / "prototypes" / "rock_one.usda").unlink()

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match="does not exist"):
        load_rock_asset(manifest)


def test_asset_loader_rejects_absolute_manifest_path(tmp_path: Path) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "habitats")
    data = _read_manifest(manifest)
    data["files"]["stage"] = "/tmp/habitat.usda"
    _write_manifest(manifest, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match="relative POSIX path"):
        load_habitat_asset(manifest)


@pytest.mark.parametrize(("field", "value"), [("up_axis", "Y"), ("meters_per_unit", 0.01)])
def test_asset_loader_rejects_bad_world_convention(
    tmp_path: Path,
    field: str,
    value: str | float,
) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "rocks")
    data = _read_manifest(manifest)
    data["conventions"][field] = value
    _write_manifest(manifest, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match=field):
        load_rock_asset(manifest)


def test_asset_loader_rejects_checksum_mismatch(tmp_path: Path) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "habitats")
    (manifest.parent / "textures" / "habitat.ppm").write_text("changed", encoding="utf-8")

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match="digest mismatch"):
        load_habitat_asset(manifest)


@pytest.mark.parametrize("field", ["provenance", "license"])
def test_asset_loader_rejects_missing_attribution_field(tmp_path: Path, field: str) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "rocks")
    data = _read_manifest(manifest)
    del data[field]
    _write_manifest(manifest, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match=field):
        load_rock_asset(manifest)


@pytest.mark.parametrize("field", ["geometry_prim", "material_prim", "collision_prim"])
def test_rock_loader_rejects_missing_declared_prim(tmp_path: Path, field: str) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "rocks")
    data = _read_manifest(manifest)
    data["prototypes"][0][field] = "/World/RockPrototypes/rock_one/Missing"
    _write_manifest(manifest, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match=field):
        load_rock_asset(manifest)


def test_rock_loader_rejects_absolute_usd_reference(tmp_path: Path) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "rocks")
    stage_path = manifest.parent / "rock_library.usda"
    stage_path.write_text(
        stage_path.read_text(encoding="utf-8").replace(
            "@prototypes/rock_one.usda@",
            "@/tmp/rock_one.usda@",
        ),
        encoding="utf-8",
    )
    data = _read_manifest(manifest)
    data["digests"]["rock_library.usda"] = hashlib.sha256(stage_path.read_bytes()).hexdigest()
    _write_manifest(manifest, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match="relative USD asset path"):
        load_rock_asset(manifest)


def test_rock_loader_rejects_prototype_path_that_disagrees_with_stable_id(tmp_path: Path) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "rocks")
    data = _read_manifest(manifest)
    data["prototypes"][0]["prim_path"] = "/World/RockPrototypes/Missing"
    _write_manifest(manifest, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match="prim_path"):
        load_rock_asset(manifest)


def test_rock_loader_rejects_texture_that_is_not_bound_under_prototype(tmp_path: Path) -> None:
    # Given
    manifest = _copy_bundle(tmp_path, "rocks")
    data = _read_manifest(manifest)
    data["prototypes"][0]["texture"] = "LICENSES/README.md"
    _write_manifest(manifest, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match="texture"):
        load_rock_asset(manifest)
