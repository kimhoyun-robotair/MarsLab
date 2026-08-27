from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest
import yaml
from marslab_scene.compat.profiles import resolve_compatibility_policy
from marslab_scene.config.models import OutputSettings
from marslab_scene.contracts.layers import HabitatLayer, RockLayer
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.usd.builder import SceneBuilder
from marslab_scene.usd.validation import validate_scene_manifest
from pxr import Sdf, Usd, UsdGeom, UsdUtils

pytestmark = [pytest.mark.contract, pytest.mark.standalone_usd]


def test_scene_builder_authors_exact_hierarchy_and_instancer_contract(
    terrain_artifact: TerrainArtifact,
    rock_layer: RockLayer,
    habitat_layer: HabitatLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    builder = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
    )

    # When
    artifact = builder.build(terrain=terrain_artifact, layers=(rock_layer, habitat_layer))

    # Then
    stage = Usd.Stage.Open(str(artifact.stage_path))
    assert stage.GetDefaultPrim().GetPath().pathString == "/World"
    assert UsdGeom.GetStageUpAxis(stage) == "Z"
    assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0
    assert stage.GetRootLayer().subLayerPaths == ["terrain/terrain.usda"]
    assert [prim.GetPath().pathString for prim in stage.GetPseudoRoot().GetChildren()] == ["/World"]
    assert [prim.GetPath().pathString for prim in stage.GetPrimAtPath("/World").GetChildren()] == [
        "/World/MarsTerrain",
        "/World/RockLib",
        "/World/Rocks",
        "/World/Habitat",
    ]
    instancer = UsdGeom.PointInstancer.Get(stage, "/World/Rocks/Instancer")
    assert list(instancer.GetPositionsAttr().Get()) == [(1.0, 2.0, 3.0)]
    assert list(instancer.GetProtoIndicesAttr().Get()) == [0]
    assert list(instancer.GetScalesAttr().Get()) == [(1.25, 1.25, 1.25)]
    assert len(instancer.GetOrientationsAttr().Get()) == 1
    assert UsdGeom.Imageable(stage.GetPrimAtPath("/World/RockLib")).GetVisibilityAttr().Get() == (
        UsdGeom.Tokens.invisible
    )
    habitat_transform = UsdGeom.Xformable(stage.GetPrimAtPath("/World/Habitat"))
    matrix = habitat_transform.ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    assert tuple(matrix.ExtractTranslation()) == pytest.approx((4.0, 5.0, 6.0))
    root_layer = Sdf.Layer.FindOrOpen(str(artifact.stage_path))
    assert set(root_layer.GetExternalReferences()) == {
        "terrain/terrain.usda",
        "rocks/rock_library.usda",
        "habitats/habitat.usda",
    }
    manifest = yaml.safe_load(artifact.manifest_path.read_text(encoding="utf-8"))
    assert manifest["compatibility_profile"] == "canonical"
    assert manifest["layers"] == [
        {"count": 1, "kind": "rocks"},
        {"count": 1, "kind": "habitat"},
    ]
    assert manifest["files"]["semantic_comparison_report"] == "semantic-scene.json"
    report = artifact.root_dir / manifest["files"]["semantic_comparison_report"]
    assert (
        manifest["semantic_comparison_report_digest"]
        == hashlib.sha256(report.read_bytes()).hexdigest()
    )
    assert validate_scene_manifest(artifact.manifest_path).compatibility_profile == "canonical"
    assert "/home/" not in artifact.manifest_path.read_text(encoding="utf-8")


def test_scene_builder_rejects_duplicate_layer_kinds(
    terrain_artifact: TerrainArtifact,
    rock_layer: RockLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    builder = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
    )

    # When / Then
    with pytest.raises(ValueError, match="duplicate rock layer"):
        builder.build(terrain=terrain_artifact, layers=(rock_layer, rock_layer))
    assert not output_settings.directory.exists()


def test_working_layout_and_standalone_usdz_relocate_independently(
    tmp_path: Path,
    terrain_artifact: TerrainArtifact,
    rock_layer: RockLayer,
    habitat_layer: HabitatLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    artifact = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
    ).build(terrain=terrain_artifact, layers=(rock_layer, habitat_layer))

    # When
    relocated_layout = tmp_path / "other-checkout/layout"
    shutil.copytree(artifact.root_dir, relocated_layout)
    package_only = tmp_path / "empty-runtime/scene.usdz"
    package_only.parent.mkdir()
    shutil.copy2(artifact.runtime_package_path, package_only)

    # Then
    working_stage = Usd.Stage.Open(str(relocated_layout / "scene.usda"))
    package_stage = Usd.Stage.Open(str(package_only))
    assert working_stage.GetPrimAtPath("/World/MarsTerrain/VisualMesh").IsValid()
    assert package_stage.GetPrimAtPath("/World/MarsTerrain/VisualMesh").IsValid()
    assert package_stage.GetPrimAtPath("/World/RockLib/RockPrototypes/rock_one").IsValid()
    assert package_stage.GetPrimAtPath("/World/Habitat/Body").IsValid()
    _, _, unresolved = UsdUtils.ComputeAllDependencies(str(package_only))
    assert not unresolved
    assert not (package_only.parent / "terrain").exists()
    assert not (package_only.parent / "rocks").exists()
    assert not (package_only.parent / "habitats").exists()


@pytest.mark.parametrize("enabled_kind", ["terrain", "habitat"])
def test_enabled_layer_combinations_keep_stable_hierarchy(
    enabled_kind: str,
    terrain_artifact: TerrainArtifact,
    habitat_layer: HabitatLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    layers = () if enabled_kind == "terrain" else (habitat_layer,)

    # When
    artifact = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
    ).build(terrain=terrain_artifact, layers=layers)

    # Then
    stage = Usd.Stage.Open(str(artifact.stage_path))
    expected = ["MarsTerrain"] if enabled_kind == "terrain" else ["MarsTerrain", "Habitat"]
    assert [prim.GetName() for prim in stage.GetPrimAtPath("/World").GetChildren()] == expected


def test_terrain_owned_physics_and_material_children_are_preserved_before_layers(
    terrain_artifact: TerrainArtifact,
    rock_layer: RockLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    terrain_artifact.stage_path.write_text(
        terrain_artifact.stage_path.read_text(encoding="utf-8").replace(
            '    def Xform "MarsTerrain"',
            '    def Scope "PhysicsScene" {}\n'
            '    def Scope "Looks" {}\n'
            '    def Xform "MarsTerrain"',
        ),
        encoding="utf-8",
    )

    # When
    artifact = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
    ).build(terrain=terrain_artifact, layers=(rock_layer,))

    # Then
    stage = Usd.Stage.Open(str(artifact.stage_path))
    assert [prim.GetName() for prim in stage.GetPrimAtPath("/World").GetChildren()] == [
        "PhysicsScene",
        "Looks",
        "MarsTerrain",
        "RockLib",
        "Rocks",
    ]
