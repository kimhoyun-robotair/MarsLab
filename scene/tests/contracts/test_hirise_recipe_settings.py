from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from marslab_scene import build_scene
from marslab_scene.config.loader import load_scene_config
from marslab_scene.errors import SceneConfigError
from pxr import Usd, UsdGeom, UsdPhysics
from rasterio.transform import from_origin

pytestmark = [pytest.mark.contract, pytest.mark.standalone_usd]


def _recipe(tmp_path: Path) -> Path:
    dem = tmp_path / "source.tif"
    with rasterio.open(
        dem,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        dtype="float32",
        crs="EPSG:32612",
        transform=from_origin(0.0, 8.0, 2.0, 2.0),
    ) as dataset:
        dataset.write(np.arange(16, dtype=np.float32).reshape(4, 4), 1)
    path = tmp_path / "recipe.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "scene": {"id": "typed-hirise", "compatibility_profile": "canonical"},
                "terrain": {
                    "source": {"type": "hirise", "dem": "source.tif"},
                    "crop": {"width_m": 6.0, "height_m": 6.0, "allow_partial": True},
                    "elevation": {
                        "normalization": "manual",
                        "manual_reference_m": 2.0,
                        "vertical_scale": 2.0,
                        "z_offset_m": 3.0,
                    },
                    "mesh": {"visual_grid_size": 5, "collision_grid_size": 3},
                    "texture": {
                        "enabled": True,
                        "mode": "solid",
                        "solid_color": [0.2, 0.4, 0.6],
                        "max_texture_size_px": 64,
                    },
                    "appearance": {"enabled": False, "mode": "none"},
                    "modifiers": [],
                },
                "layers": {"rocks": {"enabled": False}, "habitat": {"enabled": False}},
                "output": {
                    "directory": "published",
                    "stage": "scene.usda",
                    "runtime_package": "scene.usdz",
                    "manifest": "manifest.yaml",
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def _appearance_recipe(tmp_path: Path) -> Path:
    path = _recipe(tmp_path)
    ortho = np.stack(
        [
            np.arange(16, dtype=np.uint8).reshape(4, 4) * 8,
            np.full((4, 4), 60, dtype=np.uint8),
            np.full((4, 4), 30, dtype=np.uint8),
        ]
    )
    with rasterio.open(
        tmp_path / "ortho.tif",
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=3,
        dtype="uint8",
        crs="EPSG:32612",
        transform=from_origin(0.0, 8.0, 2.0, 2.0),
    ) as dataset:
        dataset.write(ortho)
    mastcam = np.zeros((3, 6, 4), dtype=np.uint8)
    mastcam[:, :2, :] = np.array([70, 35, 22], dtype=np.uint8)[:, None, None]
    mastcam[:, 2:4, :] = np.array([150, 82, 42], dtype=np.uint8)[:, None, None]
    mastcam[:, 4:, :] = np.array([220, 178, 118], dtype=np.uint8)[:, None, None]
    with rasterio.open(
        tmp_path / "mastcam.png",
        "w",
        driver="PNG",
        width=4,
        height=6,
        count=3,
        dtype="uint8",
    ) as dataset:
        dataset.write(mastcam)
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    document["terrain"]["appearance"] = {
        "enabled": True,
        "mode": "orthomosaic_mastcam_palette",
        "orthomosaic": {"path": "ortho.tif", "band_mode": "rgb"},
        "mastcam_reference": {
            "path": "mastcam.png",
            "robust_percentiles": [0.0, 50.0, 100.0],
        },
        "upscaling": {"target_m_per_px": 1.0, "max_texture_size_px": 64},
        "detail_variation": {"seed": 7, "strength": 0.0},
    }
    document["output"]["directory"] = "published-appearance"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    return path


def test_public_recipe_honors_nondefault_hirise_settings(tmp_path: Path) -> None:
    # Given
    recipe = _recipe(tmp_path)

    # When
    artifact = build_scene(recipe)

    # Then
    terrain_manifest = yaml.safe_load(
        (artifact.root_dir / "terrain/manifest.yaml").read_text(encoding="utf-8")
    )
    assert terrain_manifest["coordinate_frame"]["vertical_scale"] == 2.0
    assert terrain_manifest["coordinate_frame"]["z_offset_m"] == 3.0
    report = yaml.safe_load(
        (artifact.root_dir / "terrain/semantic-terrain.json").read_text(encoding="utf-8")
    )
    assert report["crop_shape"] == [3, 3]
    assert report["visual_vertices"] == 25
    assert report["collision_vertices"] == 9
    stage = Usd.Stage.Open(str(artifact.root_dir / "terrain/terrain.usda"))
    points = UsdGeom.Mesh.Get(stage, "/World/MarsTerrain/VisualMesh").GetPointsAttr().Get()
    assert min(float(point[2]) for point in points) == pytest.approx(9.0)
    with rasterio.open(artifact.root_dir / "terrain/textures/terrain_albedo.png") as texture:
        assert tuple(int(value) for value in texture.read()[:, 0, 0]) == (51, 102, 153)


def test_public_recipe_honors_nondefault_appearance_settings(tmp_path: Path) -> None:
    # Given
    recipe = _appearance_recipe(tmp_path)

    # When
    artifact = build_scene(recipe)

    # Then
    manifest = yaml.safe_load(
        (artifact.root_dir / "terrain/manifest.yaml").read_text(encoding="utf-8")
    )
    enhanced = artifact.root_dir / "terrain/textures/terrain_albedo_mars_enhanced.png"
    with rasterio.open(enhanced) as texture:
        assert (texture.width, texture.height) == (6, 6)
    assert manifest["seed"] == 7


def test_public_recipe_preserves_active_hirise_pipeline_settings(tmp_path: Path) -> None:
    # Given
    recipe = _recipe(tmp_path)
    band_one = np.arange(16, dtype=np.float32).reshape(4, 4)
    band_two = np.array(
        [
            [50.0, 51.0, 52.0, 53.0],
            [54.0, -9999.0, 56.0, 57.0],
            [58.0, 59.0, 60.0, 61.0],
            [62.0, 63.0, 64.0, 65.0],
        ],
        dtype=np.float32,
    )
    with rasterio.open(
        tmp_path / "source.tif",
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=2,
        dtype="float32",
        crs="EPSG:32612",
        transform=from_origin(0.0, 8.0, 2.0, 2.0),
    ) as dataset:
        dataset.write(band_one, 1)
        dataset.write(band_two, 2)
    document = yaml.safe_load(recipe.read_text(encoding="utf-8"))
    document["terrain"].update(
        {
            "input": {"band": 2, "nodata_override": -9999.0},
            "resample": {"method": "nearest"},
            "processing": {"fill_nodata": "zero"},
            "physics": {
                "gravity_mps2": 1.234,
                "collision_approximation": "meshSimplification",
                "static_friction": 0.42,
                "dynamic_friction": 0.31,
                "restitution": 0.17,
            },
        }
    )
    recipe.write_text(yaml.safe_dump(document), encoding="utf-8")

    # When
    artifact = build_scene(recipe)

    # Then
    stage = Usd.Stage.Open(str(artifact.root_dir / "terrain/terrain.usda"))
    points = UsdGeom.Mesh.Get(stage, "/World/MarsTerrain/VisualMesh").GetPointsAttr().Get()
    assert min(float(point[2]) for point in points) == pytest.approx(-1.0)
    assert float(points[1][2]) == pytest.approx(111.0)
    assert max(float(point[2]) for point in points) == pytest.approx(129.0)
    physics_scene = UsdPhysics.Scene.Get(stage, "/World/PhysicsScene")
    assert physics_scene.GetGravityMagnitudeAttr().Get() == pytest.approx(1.234)
    collision = UsdPhysics.MeshCollisionAPI.Get(
        stage,
        "/World/MarsTerrain/CollisionMesh",
    )
    assert collision.GetApproximationAttr().Get() == "meshSimplification"
    material = UsdPhysics.MaterialAPI.Get(stage, "/World/MarsTerrain/PhysicsMaterial")
    assert material.GetStaticFrictionAttr().Get() == pytest.approx(0.42)
    assert material.GetDynamicFrictionAttr().Get() == pytest.approx(0.31)
    assert material.GetRestitutionAttr().Get() == pytest.approx(0.17)


def test_hirise_recipe_rejects_unknown_and_invalid_settings(tmp_path: Path) -> None:
    # Given
    recipe = _recipe(tmp_path)
    document = yaml.safe_load(recipe.read_text(encoding="utf-8"))
    document["terrain"]["mesh"]["unknown"] = 1
    recipe.write_text(yaml.safe_dump(document), encoding="utf-8")

    # When / Then
    with pytest.raises(SceneConfigError, match="unknown"):
        load_scene_config(recipe)


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("input", {"band": 0}),
        ("resample", {"method": "lanczos"}),
        ("processing", {"fill_nodata": "interpolate"}),
        ("physics", {"gravity_mps2": 0.0}),
        ("physics", {"collision_approximation": "convexHull"}),
        ("physics", {"unknown": 1}),
    ],
)
def test_hirise_recipe_rejects_invalid_active_pipeline_settings(
    tmp_path: Path,
    section: str,
    value: dict[str, float | int | str],
) -> None:
    # Given
    recipe = _recipe(tmp_path)
    document = yaml.safe_load(recipe.read_text(encoding="utf-8"))
    document["terrain"][section] = value
    recipe.write_text(yaml.safe_dump(document), encoding="utf-8")

    # When / Then
    with pytest.raises(SceneConfigError):
        load_scene_config(recipe)
