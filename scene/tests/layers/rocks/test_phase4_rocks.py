from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
import rasterio
from marslab_scene.assets.rocks import load_rock_asset
from marslab_scene.compat.profiles import resolve_compatibility_policy
from marslab_scene.config.models import RocksEnabled
from marslab_scene.contracts.provenance import Provenance
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.layers.rocks import place_rocks
from marslab_scene.layers.rocks.input import RockCsvError, load_rock_csv
from marslab_scene.layers.rocks.orientation import quaternions_equivalent
from marslab_scene.layers.rocks.placement import (
    RockPrototype,
    compute_rock_placement,
)
from marslab_scene.terrain.frame import TerrainFrame
from marslab_scene.terrain.sampling import DemSamplingError, sample_raw_dem_batch
from rasterio.transform import from_origin

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]

_SOURCE_ROOT = Path("/home/hoyunkim/MarsLab-Utils/RockyComposer")
_ASSET_MANIFEST = Path(__file__).parents[2] / "fixtures/assets/rocks/manifest.yaml"


def _write_dem(path: Path) -> None:
    values = np.array(
        [
            [100.0, 102.0, 104.0, 106.0],
            [110.0, -9999.0, 114.0, 116.0],
            [120.0, 122.0, 124.0, 126.0],
            [130.0, 132.0, 134.0, 136.0],
        ],
        dtype=np.float32,
    )
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=4,
        height=4,
        count=1,
        dtype="float32",
        crs="EPSG:32612",
        transform=from_origin(500_000.0, 4_100_000.0, 2.5, 2.5),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(values, 1)


def _frame(profile: str) -> TerrainFrame:
    return TerrainFrame(
        projected_crs="EPSG:32612",
        raster_affine=(2.5, 0.0, 500_000.0, 0.0, -2.5, 4_100_000.0),
        origin_projected_m=(500_003.0, 4_099_996.0),
        z_reference_m=100.0,
        vertical_scale=1.75,
        z_offset_m=3.25,
        compatibility_profile=profile,
    )


def _prototypes() -> tuple[RockPrototype, ...]:
    return tuple(
        RockPrototype(
            id=f"rock_{index}",
            native_diameter_m=diameter,
            stable_poses_wxyz=(
                (1.0, 0.0, 0.0, 0.0),
                (2**-0.5, -(2**-0.5), 0.0, 0.0),
            ),
        )
        for index, diameter in enumerate((0.5, 1.0, 2.0, 4.0))
    )


def _legacy_probe(diameters: np.ndarray, seed: int) -> dict[str, object]:
    code = """
import json, os
import numpy as np
from rockycomposer.library.proto_meta import ProtoMeta
from rockycomposer.placement.selection import select_prototypes_batch
from rockycomposer.placement.orientation import random_stable_pose_quats_batch
vertices=np.array([(0.,0.,0.),(1.,0.,0.),(0.,1.,0.),(0.,0.,1.)],dtype=np.float32)
faces=np.array([(0,2,1),(0,3,1),(1,3,2),(2,3,0)],dtype=np.int32)
protos=[ProtoMeta(name=f'rock_{i}',prim_path=f'/World/RockPrototypes/rock_{i}',
 mesh_bbox=(d,d,d),native_diameter=d,stable_face_indices=np.array([0,1],dtype=np.int32),
 density_kg_m3=2600.,mesh_vertices=vertices,mesh_faces=faces)
 for i,d in enumerate((0.5,1.,2.,4.))]
rng=np.random.default_rng(int(os.environ['ROCK_SEED']))
indices,scales,clamped=select_prototypes_batch(
 np.asarray(json.loads(os.environ['ROCK_DIAMETERS']),dtype=np.float64),protos,rng,k=3,
 scale_clamp=(0.5,2.0))
quats=random_stable_pose_quats_batch(protos,indices,rng)
print(json.dumps({'indices':indices.tolist(),'scales':scales.tolist(),
 'clamped':clamped.tolist(),'quats':quats.tolist()}))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(_SOURCE_ROOT / "src")
    environment["ROCK_SEED"] = str(seed)
    environment["ROCK_DIAMETERS"] = json.dumps(diameters.tolist())
    result = subprocess.run(
        [str(_SOURCE_ROOT / ".venv/bin/python"), "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return json.loads(result.stdout)


def _legacy_position_probe(dem: Path, projected_xy_m: np.ndarray) -> np.ndarray:
    code = """
import json, os
import numpy as np
from pathlib import Path
from rockycomposer.pipeline import _apply_terrain_frame_transform
from rockycomposer.sampling.dem import RasterSampler
xy=np.asarray(json.loads(os.environ['ROCK_XY']),dtype=np.float64)
raw=RasterSampler(Path(os.environ['ROCK_DEM'])).sample_z_batch(xy)
positions=np.column_stack((xy,raw))
_apply_terrain_frame_transform(positions,{
 'frame':{'type':'local_enu'},'crop':{'origin_x_geo':500003.,'origin_y_geo':4099996.},
 'elevation':{'z_reference_m':100.,'vertical_scale':1.75,'z_offset_m':3.25}})
print(json.dumps(positions.tolist()))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(_SOURCE_ROOT / "src")
    environment["ROCK_DEM"] = str(dem)
    environment["ROCK_XY"] = json.dumps(projected_xy_m.tolist())
    result = subprocess.run(
        [str(_SOURCE_ROOT / ".venv/bin/python"), "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return np.asarray(json.loads(result.stdout), dtype=np.float64)


def test_legacy_selection_scale_and_orientation_match_read_only_source() -> None:
    # Given
    diameters = np.array([0.2, 0.9, 2.6, 6.0], dtype=np.float64)
    legacy = _legacy_probe(diameters, seed=42)

    # When
    target = compute_rock_placement(
        diameters,
        _prototypes(),
        seed=42,
        top_k=3,
        scale_clamp=(0.5, 2.0),
    )

    # Then
    np.testing.assert_array_equal(target.prototype_indices, legacy["indices"])
    np.testing.assert_allclose(target.scales, legacy["scales"], atol=1e-5)
    assert target.clamped.tolist() == legacy["clamped"]
    expected_quats = np.asarray(legacy["quats"], dtype=np.float64)
    assert all(
        quaternions_equivalent(actual, expected, atol=1e-5)
        for actual, expected in zip(target.orientations_wxyz, expected_quats, strict=True)
    )


def test_legacy_positions_match_read_only_source_on_same_dem(tmp_path: Path) -> None:
    # Given
    dem = tmp_path / "terrain.tif"
    _write_dem(dem)
    xy = np.array(
        [[500005.0, 4_099_995.0], [500007.5, 4_099_992.5]],
        dtype=np.float64,
    )
    expected = _legacy_position_probe(dem, xy)
    frame = _frame("marslab_utils_6f30d67")

    # When
    samples = sample_raw_dem_batch(dem, xy)
    actual = np.asarray(
        [
            (*frame.projected_to_local_xy(x, y), frame.rock_z_local(raw_z))
            for (x, y), raw_z in zip(xy, samples.raw_z_m, strict=True)
        ],
        dtype=np.float64,
    )

    # Then
    np.testing.assert_allclose(actual, expected, atol=1e-5)


def test_public_place_rocks_returns_deterministic_layer_and_filters_invalid_samples(
    tmp_path: Path,
) -> None:
    # Given
    artifact_root = tmp_path / "artifact"
    artifact_root.mkdir()
    dem = artifact_root / "terrain.tif"
    _write_dem(dem)
    csv_path = tmp_path / "rocks.csv"
    csv_path.write_text(
        "x,y,diameter_m\n500005.0,4099995.0,0.8\n500007.5,4099992.5,1.2\n"
        "500002.5,4099997.5,0.7\n499999.0,4099997.5,1.0\n",
        encoding="utf-8",
    )
    stage = artifact_root / "terrain.usda"
    manifest = artifact_root / "manifest.yaml"
    stage.write_text("#usda 1.0\n", encoding="utf-8")
    manifest.write_text("kind: terrain_artifact\n", encoding="utf-8")
    artifact = TerrainArtifact(
        root_dir=artifact_root,
        stage_path=stage,
        dem_path=dem,
        manifest_path=manifest,
        coordinate_frame=_frame("canonical"),
        provenance=Provenance(
            producer="test",
            marslab_revision=None,
            marslab_utils_revision=None,
            source_files=(dem,),
        ),
    )
    config = RocksEnabled(
        enabled=True,
        asset=Path("asset.yaml"),
        placements=Path("rocks.csv"),
        seed=42,
        top_k=3,
        scale_clamp=(0.5, 2.0),
    ).model_copy(update={"asset": _ASSET_MANIFEST, "placements": csv_path})
    policy = resolve_compatibility_policy("canonical")

    # When
    first = place_rocks(artifact, config, policy=policy)
    second = place_rocks(artifact, config, policy=policy)

    # Then
    assert first.positions_local_m.shape == (2, 3)
    np.testing.assert_array_equal(first.positions_local_m, second.positions_local_m)
    np.testing.assert_array_equal(first.prototype_indices, second.prototype_indices)
    np.testing.assert_array_equal(first.orientations_wxyz, second.orientations_wxyz)
    np.testing.assert_allclose(first.positions_local_m[:, 2], [45.25, 66.25], atol=1e-5)
    assert first.asset_manifest == load_rock_asset(_ASSET_MANIFEST).manifest_path
    assert first.placement_source == csv_path
    assert first.stats.csv_count == 4
    assert first.stats.placed_count == 2
    assert first.stats.skipped_nodata == 1
    assert first.stats.skipped_out_of_bounds == 1
    assert not any(artifact_root.glob("*rock*.usd*"))


def test_profile_specific_z_values_have_independent_expected_values() -> None:
    # Given / When
    legacy = _frame("marslab_utils_6f30d67").rock_z_local(110.0)
    canonical = _frame("canonical").rock_z_local(110.0)

    # Then
    assert legacy == pytest.approx(23.1875, abs=1e-5)
    assert canonical == pytest.approx(20.75, abs=1e-5)
    assert legacy != canonical


def test_quaternion_comparison_treats_sign_as_equivalent() -> None:
    # Given
    quaternion = np.array([0.5, 0.5, -0.5, 0.5], dtype=np.float64)

    # When / Then
    assert quaternions_equivalent(quaternion, -quaternion, atol=1e-5)


@pytest.mark.contract
def test_csv_and_dem_boundaries_fail_closed(tmp_path: Path) -> None:
    # Given
    malformed = tmp_path / "malformed.csv"
    malformed.write_text("x,y,diameter\n1,nan,2\n", encoding="utf-8")
    missing = tmp_path / "missing.csv"
    dem = tmp_path / "terrain.tif"
    _write_dem(dem)

    # When / Then
    with pytest.raises(RockCsvError, match="finite"):
        load_rock_csv(malformed)
    with pytest.raises(RockCsvError, match="not found"):
        load_rock_csv(missing)
    with pytest.raises(DemSamplingError, match="shape"):
        sample_raw_dem_batch(dem, np.array([1.0, 2.0]))
