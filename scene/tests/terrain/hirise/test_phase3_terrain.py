from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from marslab_scene.compat.profiles import resolve_compatibility_policy
from marslab_scene.contracts.terrain import load_terrain_artifact
from marslab_scene.terrain.elevation import normalize_elevation
from marslab_scene.terrain.hirise import HiriseBuildConfig, build_hirise_terrain
from marslab_scene.terrain.hirise.config import CropConfig, ElevationConfig
from marslab_scene.terrain.hirise.mesh.heightfield import build_heightfield_mesh
from rasterio.transform import from_origin

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]

_SOURCE_ROOT = Path("/home/hoyunkim/MarsLab-Utils/HiRISEGen")


def _write_dem(path: Path) -> None:
    array = np.array(
        [
            [100.0, 101.0, 102.0, 103.0, 104.0],
            [105.0, 106.0, -9999.0, 108.0, 109.0],
            [110.0, 111.0, 112.0, 113.0, 114.0],
            [115.0, 116.0, 117.0, 118.0, 119.0],
        ],
        dtype=np.float32,
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=array.shape[1],
        height=array.shape[0],
        count=1,
        dtype=array.dtype,
        crs="EPSG:32612",
        transform=from_origin(500_000.0, 4_100_000.0, 2.5, 2.5),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(array, 1)


def _legacy_numerical_probe() -> dict[str, list[float] | float | int]:
    code = (
        "import json\n"
        "import numpy as np\n"
        "from hirisegen.config import ElevationConfig\n"
        "from hirisegen.dem.elevation import normalize_elevation\n"
        "from hirisegen.mesh.heightfield import build_heightfield_mesh\n"
        "raw=np.array([[100.,101.,102.],[103.,104.,105.]])\n"
        "valid=np.ones_like(raw,dtype=bool)\n"
        "e=normalize_elevation(raw,valid,ElevationConfig(normalization='manual',"
        "manual_reference_m=100.,vertical_scale=1.75,z_offset_m=3.25))\n"
        "m=build_heightfield_mesh(e.local_z,5.,2.5)\n"
        "print(json.dumps({'reference':e.z_reference_m,'minimum':e.local_min_m,"
        "'maximum':e.local_max_m,'vertices':len(m.vertices),'faces':len(m.faces),"
        "'first':m.vertices[0].tolist(),'last':m.vertices[-1].tolist()}))\n"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(_SOURCE_ROOT / "src")
    result = subprocess.run(
        [str(_SOURCE_ROOT / ".venv/bin/python"), "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return json.loads(result.stdout)


def _legacy_pipeline_probe(dem: Path, output: Path) -> dict[str, list[float] | int]:
    code = (
        "import json,os\n"
        "import rasterio\n"
        "from pxr import Usd,UsdGeom\n"
        "from hirisegen.config import *\n"
        "from hirisegen.pipeline import run_export\n"
        "d=os.environ['MARSLAB_PHASE3_DEM'];o=os.environ['MARSLAB_PHASE3_OUT']\n"
        "c=PipelineConfig(input=InputConfig(path=__import__('pathlib').Path(d)),"
        "crop=CropConfig(width_m=10.,height_m=7.5),"
        "elevation=ElevationConfig(normalization='manual',manual_reference_m=100.,"
        "vertical_scale=1.75,z_offset_m=3.25),"
        "mesh=MeshConfig(visual_grid_size=5,collision_grid_size=3,"
        "write_visual_obj=False,write_collision_obj=False),"
        "usd=UsdConfig(output_dir=__import__('pathlib').Path(o)))\n"
        "r=run_export(c);s=Usd.Stage.Open(str(r.scene_path));"
        "m=UsdGeom.Mesh.Get(s,'/World/MarsTerrain/VisualMesh')\n"
        "with rasterio.open(r.cropped_dem_path) as ds:"
        " crop_shape=list(ds.shape);transform=list(ds.transform)[:6]\n"
        "with rasterio.open(__import__('pathlib').Path(o)/'textures/terrain_albedo.png') as ds:"
        " texture=ds.read().tolist()\n"
        "print(json.dumps({'crop_shape':crop_shape,'transform':transform,"
        "'points':[list(p) for p in m.GetPointsAttr().Get()],"
        "'indices':list(m.GetFaceVertexIndicesAttr().Get()),'texture':texture}))\n"
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(_SOURCE_ROOT / "src")
    environment["MARSLAB_PHASE3_DEM"] = str(dem)
    environment["MARSLAB_PHASE3_OUT"] = str(output)
    result = subprocess.run(
        [str(_SOURCE_ROOT / ".venv/bin/python"), "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return json.loads(result.stdout)


def test_numerical_migration_matches_read_only_source() -> None:
    # Given
    raw = np.array([[100.0, 101.0, 102.0], [103.0, 104.0, 105.0]])
    valid = np.ones_like(raw, dtype=np.bool_)
    legacy = _legacy_numerical_probe()

    # When
    elevation = normalize_elevation(
        raw,
        valid,
        ElevationConfig(
            normalization="manual",
            manual_reference_m=100.0,
            vertical_scale=1.75,
            z_offset_m=3.25,
        ),
    )
    mesh = build_heightfield_mesh(elevation.local_z, 5.0, 2.5)

    # Then
    assert elevation.z_reference_m == pytest.approx(legacy["reference"], abs=1e-6)
    assert elevation.local_min_m == pytest.approx(legacy["minimum"], abs=1e-6)
    assert elevation.local_max_m == pytest.approx(legacy["maximum"], abs=1e-6)
    assert len(mesh.vertices) == legacy["vertices"]
    assert len(mesh.faces) == legacy["faces"]
    np.testing.assert_allclose(mesh.vertices[0], legacy["first"], atol=1e-5)
    np.testing.assert_allclose(mesh.vertices[-1], legacy["last"], atol=1e-5)


@pytest.mark.standalone_usd
def test_pipeline_semantics_match_read_only_source(tmp_path: Path) -> None:
    # Given
    dem = tmp_path / "source.tif"
    _write_dem(dem)
    legacy = _legacy_pipeline_probe(dem, tmp_path / "legacy")

    # When
    artifact = build_hirise_terrain(
        HiriseBuildConfig(
            dem_path=dem,
            output_dir=tmp_path / "target",
            crop=CropConfig(width_m=10.0, height_m=7.5),
            elevation=ElevationConfig(
                normalization="manual",
                manual_reference_m=100.0,
                vertical_scale=1.75,
                z_offset_m=3.25,
            ),
            visual_grid_size=5,
            collision_grid_size=3,
        ),
        policy=resolve_compatibility_policy("marslab_utils_6f30d67"),
    )

    # Then
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(artifact.stage_path))
    mesh = UsdGeom.Mesh.Get(stage, "/World/MarsTerrain/VisualMesh")
    with rasterio.open(artifact.dem_path) as dataset:
        assert list(dataset.shape) == legacy["crop_shape"]
        np.testing.assert_allclose(list(dataset.transform)[:6], legacy["transform"], atol=0.0)
    with rasterio.open(artifact.root_dir / "textures/terrain_albedo.png") as dataset:
        np.testing.assert_array_equal(dataset.read(), legacy["texture"])
    np.testing.assert_allclose(mesh.GetPointsAttr().Get(), legacy["points"], atol=1e-5)
    assert list(mesh.GetFaceVertexIndicesAttr().Get()) == legacy["indices"]


@pytest.mark.contract
@pytest.mark.standalone_usd
def test_public_build_returns_relocatable_terrain_artifact(tmp_path: Path) -> None:
    # Given
    dem = tmp_path / "source.tif"
    _write_dem(dem)
    output = tmp_path / "artifact"
    policy = resolve_compatibility_policy("marslab_utils_6f30d67")

    # When
    artifact = build_hirise_terrain(
        HiriseBuildConfig(
            dem_path=dem,
            output_dir=output,
            crop=CropConfig(width_m=10.0, height_m=7.5),
            elevation=ElevationConfig(
                normalization="manual",
                manual_reference_m=100.0,
                vertical_scale=1.75,
                z_offset_m=3.25,
            ),
            visual_grid_size=5,
            collision_grid_size=3,
        ),
        policy=policy,
    )

    # Then
    assert artifact.stage_path.is_file()
    assert artifact.dem_path is not None and artifact.dem_path.is_file()
    manifest = yaml.safe_load(artifact.manifest_path.read_text(encoding="utf-8"))
    assert manifest["semantic_comparison_report"] == "semantic-terrain.json"
    assert manifest["seed"] == 42
    loaded = load_terrain_artifact(artifact.manifest_path, profile=policy.name)
    assert loaded.coordinate_frame == artifact.coordinate_frame

    relocated = tmp_path / "relocated" / "terrain"
    shutil.copytree(artifact.root_dir, relocated)
    relocated_artifact = load_terrain_artifact(relocated / "manifest.yaml", profile=policy.name)
    from pxr import Usd

    stage = Usd.Stage.Open(str(relocated_artifact.stage_path))
    assert stage is not None
    assert stage.GetDefaultPrim().GetPath().pathString == "/World"
    assert stage.GetPrimAtPath("/World/MarsTerrain/VisualMesh").IsValid()
    assert stage.GetPrimAtPath("/World/MarsTerrain/CollisionMesh").IsValid()
    assert "/home/" not in relocated_artifact.stage_path.read_text(encoding="utf-8")


@pytest.mark.contract
def test_public_build_rejects_missing_dem(tmp_path: Path) -> None:
    # Given
    config = HiriseBuildConfig(
        dem_path=tmp_path / "missing.tif",
        output_dir=tmp_path / "artifact",
    )

    # When / Then
    with pytest.raises(FileNotFoundError):
        build_hirise_terrain(
            config,
            policy=resolve_compatibility_policy("canonical"),
        )
