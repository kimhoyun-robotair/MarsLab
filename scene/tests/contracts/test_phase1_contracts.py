from __future__ import annotations

import hashlib
from pathlib import Path

import marslab_scene
import pytest
import yaml
from marslab_scene.contracts.provenance import Provenance
from pydantic import JsonValue

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def _write_yaml(path: Path, value: dict[str, JsonValue]) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _valid_recipe(tmp_path: Path) -> Path:
    dem_path = tmp_path / "terrain.tif"
    dem_path.write_bytes(b"fixture-dem")
    recipe_path = tmp_path / "scene.yaml"
    _write_yaml(
        recipe_path,
        {
            "schema_version": 1,
            "scene": {"id": "fixture", "compatibility_profile": "canonical"},
            "terrain": {
                "source": {"type": "hirise", "dem": "terrain.tif"},
                "crop": {},
                "mesh": {},
                "texture": {},
                "appearance": {},
                "modifiers": [],
            },
            "layers": {
                "rocks": {"enabled": False},
                "habitat": {"enabled": False},
            },
            "output": {
                "directory": "output",
                "stage": "scene.usda",
                "runtime_package": "scene.usdz",
                "manifest": "manifest.yaml",
            },
        },
    )
    return recipe_path


def _valid_manifest(tmp_path: Path, profile: str = "canonical") -> Path:
    stage_path = tmp_path / "terrain.usda"
    stage_path.write_text("#usda 1.0\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.yaml"
    _write_yaml(
        manifest_path,
        {
            "schema_version": 1,
            "kind": "terrain_artifact",
            "files": {"stage": "terrain.usda", "dem": None},
            "conventions": {"up_axis": "Z", "meters_per_unit": 1.0},
            "provenance": {
                "producer": "marslab_scene",
                "marslab_revision": None,
                "marslab_utils_revision": None,
                "source_files": [],
            },
            "digests": {"terrain.usda": hashlib.sha256(stage_path.read_bytes()).hexdigest()},
            "compatibility_profile": profile,
            "coordinate_frame": None,
        },
    )
    return manifest_path


def test_public_loader_resolves_valid_recipe_when_files_exist(tmp_path: Path) -> None:
    # Given
    recipe_path = _valid_recipe(tmp_path)

    # When
    config = marslab_scene.load_scene_config(recipe_path)

    # Then
    assert config.terrain.source.dem == (tmp_path / "terrain.tif").resolve()


def test_public_loader_rejects_missing_profile_when_recipe_is_loaded(tmp_path: Path) -> None:
    # Given
    recipe_path = _valid_recipe(tmp_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    del data["scene"]["compatibility_profile"]
    _write_yaml(recipe_path, data)

    # When / Then
    with pytest.raises(marslab_scene.SceneConfigError, match="compatibility_profile"):
        marslab_scene.load_scene_config(recipe_path)


def test_public_loader_rejects_unknown_profile_when_recipe_is_loaded(tmp_path: Path) -> None:
    # Given
    recipe_path = _valid_recipe(tmp_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["scene"]["compatibility_profile"] = "future-profile"
    _write_yaml(recipe_path, data)

    # When / Then
    with pytest.raises(marslab_scene.UnknownCompatibilityProfileError):
        marslab_scene.load_scene_config(recipe_path)


def test_public_loader_rejects_unknown_key_when_recipe_is_loaded(tmp_path: Path) -> None:
    # Given
    recipe_path = _valid_recipe(tmp_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["scene"]["unexpected"] = True
    _write_yaml(recipe_path, data)

    # When / Then
    with pytest.raises(marslab_scene.SceneConfigError, match="unexpected"):
        marslab_scene.load_scene_config(recipe_path)


@pytest.mark.parametrize("path_value", ["/tmp/terrain.tif", "file:///tmp/terrain.tif"])
def test_public_loader_rejects_non_relative_input_path(
    tmp_path: Path,
    path_value: str,
) -> None:
    # Given
    recipe_path = _valid_recipe(tmp_path)
    data = yaml.safe_load(recipe_path.read_text(encoding="utf-8"))
    data["terrain"]["source"]["dem"] = path_value
    _write_yaml(recipe_path, data)

    # When / Then
    with pytest.raises(marslab_scene.SceneConfigError, match="relative local path"):
        marslab_scene.load_scene_config(recipe_path)


def test_public_loader_rejects_missing_input_file(tmp_path: Path) -> None:
    # Given
    recipe_path = _valid_recipe(tmp_path)
    (tmp_path / "terrain.tif").unlink()

    # When / Then
    with pytest.raises(marslab_scene.SceneConfigError, match="does not exist"):
        marslab_scene.load_scene_config(recipe_path)


@pytest.mark.parametrize(
    ("field", "value"),
    [("up_axis", "Y"), ("meters_per_unit", 0.01)],
)
def test_manifest_loader_rejects_invalid_world_convention(
    tmp_path: Path,
    field: str,
    value: str | float,
) -> None:
    # Given
    manifest_path = _valid_manifest(tmp_path)
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    data["conventions"][field] = value
    _write_yaml(manifest_path, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match=field):
        marslab_scene.load_terrain_artifact(manifest_path, profile="canonical")


def test_manifest_loader_rejects_absolute_manifest_path(tmp_path: Path) -> None:
    # Given
    manifest_path = _valid_manifest(tmp_path)
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    data["files"]["stage"] = "/tmp/terrain.usda"
    _write_yaml(manifest_path, data)

    # When / Then
    with pytest.raises(marslab_scene.ArtifactManifestError, match="relative POSIX path"):
        marslab_scene.load_terrain_artifact(manifest_path, profile="canonical")


def test_manifest_loader_rejects_profile_mismatch(tmp_path: Path) -> None:
    # Given
    manifest_path = _valid_manifest(tmp_path, profile="marslab_utils_6f30d67")

    # When / Then
    with pytest.raises(marslab_scene.CompatibilityProfileMismatch):
        marslab_scene.load_terrain_artifact(manifest_path, profile="canonical")


def test_terrain_frame_applies_profile_specific_z_contract() -> None:
    # Given
    canonical = marslab_scene.TerrainFrame(
        projected_crs="EPSG:32611",
        raster_affine=(2.0, 0.0, 10.0, 0.0, -2.0, 20.0),
        origin_projected_m=(100.0, 200.0),
        z_reference_m=10.0,
        vertical_scale=2.0,
        z_offset_m=3.0,
        compatibility_profile="canonical",
    )
    legacy = marslab_scene.TerrainFrame(
        projected_crs="EPSG:32611",
        raster_affine=(2.0, 0.0, 10.0, 0.0, -2.0, 20.0),
        origin_projected_m=(100.0, 200.0),
        z_reference_m=10.0,
        vertical_scale=2.0,
        z_offset_m=3.0,
        compatibility_profile="marslab_utils_6f30d67",
    )

    # When
    canonical_z = canonical.rock_z_local(14.0)
    legacy_z = legacy.rock_z_local(14.0)

    # Then
    assert canonical_z == 11.0
    assert legacy_z == 14.0


def test_rock_asset_descriptor_rejects_missing_contract_files(tmp_path: Path) -> None:
    # Given
    manifest = tmp_path / "missing-manifest.yaml"
    stage = tmp_path / "missing-stage.usda"

    # When / Then
    with pytest.raises(ValueError, match="required file does not exist"):
        marslab_scene.RockAssetDescriptor(
            manifest_path=manifest,
            stage_path=stage,
            prototype_ids=("rock-1",),
            native_diameters_m=(1.0,),
        )


def test_habitat_asset_descriptor_rejects_missing_contract_files(tmp_path: Path) -> None:
    # Given
    manifest = tmp_path / "missing-manifest.yaml"
    stage = tmp_path / "missing-stage.usda"

    # When / Then
    with pytest.raises(ValueError, match="required file does not exist"):
        marslab_scene.HabitatAssetDescriptor(
            manifest_path=manifest,
            stage_path=stage,
            centroid_zup_m=(0.0, 0.0, 0.0),
            aabb_min_zup_m=(-1.0, -1.0, 0.0),
            aabb_max_zup_m=(1.0, 1.0, 2.0),
            body_floor_z_m=0.0,
        )


def test_terrain_artifact_rejects_missing_contract_files(tmp_path: Path) -> None:
    # Given
    provenance = Provenance("marslab_scene", None, None, ())

    # When / Then
    with pytest.raises(ValueError, match="required file does not exist"):
        marslab_scene.TerrainArtifact(
            root_dir=tmp_path,
            stage_path=tmp_path / "missing.usda",
            dem_path=None,
            manifest_path=tmp_path / "missing.yaml",
            coordinate_frame=None,
            provenance=provenance,
        )


def test_scene_artifact_rejects_missing_contract_files(tmp_path: Path) -> None:
    # Given
    stage = tmp_path / "terrain.usda"
    manifest = tmp_path / "terrain.yaml"
    stage.write_text("#usda 1.0\n", encoding="utf-8")
    manifest.write_text("schema_version: 1\n", encoding="utf-8")
    provenance = Provenance("marslab_scene", None, None, ())
    terrain = marslab_scene.TerrainArtifact(
        root_dir=tmp_path,
        stage_path=stage,
        dem_path=None,
        manifest_path=manifest,
        coordinate_frame=None,
        provenance=provenance,
    )

    # When / Then
    with pytest.raises(ValueError, match="required file does not exist"):
        marslab_scene.SceneArtifact(
            root_dir=tmp_path,
            stage_path=tmp_path / "missing-scene.usda",
            runtime_package_path=tmp_path / "missing-scene.usdz",
            manifest_path=tmp_path / "missing-scene.yaml",
            terrain=terrain,
            layer_summaries=(),
            provenance=provenance,
        )


def test_layer_summary_rejects_negative_count() -> None:
    # Given / When / Then
    with pytest.raises(ValueError, match="non-negative"):
        marslab_scene.LayerSummary(kind="rocks", count=-1)
