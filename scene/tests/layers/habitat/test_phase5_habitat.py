from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import rasterio
from marslab_scene.compat.profiles import resolve_compatibility_policy
from marslab_scene.config.models import HabitatEnabled, HabitatPlacement
from marslab_scene.contracts.provenance import Provenance
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.layers.habitat import place_habitat
from marslab_scene.layers.habitat.flatness import FlatnessSearchError, find_flattest_anchor
from marslab_scene.layers.habitat.placement import HabitatPlacementError
from marslab_scene.terrain.frame import TerrainFrame
from rasterio.transform import from_origin

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]

_SOURCE_ROOT = Path("/home/hoyunkim/MarsLab-Utils/HabitatGen")
_ASSET_MANIFEST = Path(__file__).parents[2] / "fixtures/assets/habitats/manifest.yaml"


def _dem_values() -> np.ndarray:
    values = np.fromfunction(lambda row, column: (row + column) % 2 * 20.0, (9, 9))
    values[1:4, 1:4] = 10.0
    values[4:9, 4:9] = 30.0
    values[4, 4] = 31.0
    values[0, 8] = -9999.0
    return values.astype(np.float32)


def _write_dem(path: Path) -> None:
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=9,
        height=9,
        count=1,
        dtype="float32",
        crs="EPSG:32612",
        transform=from_origin(1_000.0, 2_000.0, 2.0, 3.0),
        nodata=-9999.0,
    ) as dataset:
        dataset.write(_dem_values(), 1)


def _frame(profile: str) -> TerrainFrame:
    return TerrainFrame(
        projected_crs="EPSG:32612",
        raster_affine=(2.0, 0.0, 1_000.0, 0.0, -3.0, 2_000.0),
        origin_projected_m=(1_004.0, 1_995.0),
        z_reference_m=5.0,
        vertical_scale=1.5,
        z_offset_m=2.0,
        compatibility_profile=profile,
    )


def _artifact(tmp_path: Path, profile: str) -> TerrainArtifact:
    root = tmp_path / profile
    root.mkdir()
    dem = root / "terrain.tif"
    stage = root / "terrain.usda"
    manifest = root / "manifest.yaml"
    _write_dem(dem)
    stage.write_text("#usda 1.0\n", encoding="utf-8")
    manifest.write_text("kind: terrain_artifact\n", encoding="utf-8")
    return TerrainArtifact(
        root_dir=root,
        stage_path=stage,
        dem_path=dem,
        manifest_path=manifest,
        coordinate_frame=_frame(profile),
        provenance=Provenance(
            producer="test",
            marslab_revision=None,
            marslab_utils_revision=None,
            source_files=(dem,),
        ),
    )


def _config(
    mode: str = "flattest",
    *,
    x: float | None = None,
    y: float | None = None,
) -> HabitatEnabled:
    config = HabitatEnabled(
        enabled=True,
        asset=Path("asset.yaml"),
        placement=HabitatPlacement(
            mode=mode,
            x=x,
            y=y,
            z_align="body_floor_to_surface",
            z_offset_m=-0.5,
        ),
    )
    return config.model_copy(update={"asset": _ASSET_MANIFEST})


def _legacy_probe(dem_path: Path) -> dict[str, object]:
    code = """
import json, os
from habitatgen.composer.placement.flatness import find_flattest_anchor
from habitatgen.composer.sampling.dem import sample_dem_z
from habitatgen.composer.placement.transform import compute_transform
r=find_flattest_anchor(os.environ['DEM'],5.,1.25,1.25)
z=sample_dem_z(os.environ['DEM'],r.x_geo,r.y_geo,5.)
t=compute_transform([.25,-.75,-.5],[-1.,-.5,0.],[1.,.5,1.5],
 r.x_geo-1004.,r.y_geo-1995.,z,z_align='body_floor_to_surface',
 asset_body_floor_z=0.,z_offset_m=-.5)
print(json.dumps({'row':r.row,'col':r.col,'x':r.x_geo,'y':r.y_geo,
 'z':z,'translation':[t.tx,t.ty,t.tz],
 'aabb_min':t.aabb_min_in_scene,'aabb_max':t.aabb_max_in_scene,
 'range':r.range_m,'std':r.std_m,'mean':r.mean_z_local_m}))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(_SOURCE_ROOT / "src")
    environment["DEM"] = str(dem_path)
    result = subprocess.run(
        [str(_SOURCE_ROOT / ".venv/bin/python"), "-c", code],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    return json.loads(result.stdout)


def test_legacy_profile_matches_read_only_source_on_nontrivial_fixture(tmp_path: Path) -> None:
    # Given
    terrain = _artifact(tmp_path, "marslab_utils_6f30d67")
    dem_path, _ = terrain.require_sampling_surface()
    expected = _legacy_probe(dem_path)

    # When
    layer = place_habitat(
        terrain,
        _config(),
        policy=resolve_compatibility_policy("marslab_utils_6f30d67"),
    )

    # Then
    assert layer.anchor.dem_row_column == (expected["row"], expected["col"])
    np.testing.assert_allclose(layer.anchor.projected_xy_m, [expected["x"], expected["y"]])
    np.testing.assert_allclose(layer.translation_local_m, expected["translation"], atol=1e-4)
    np.testing.assert_allclose(layer.aabb_min_local_m, expected["aabb_min"], atol=1e-4)
    np.testing.assert_allclose(layer.aabb_max_local_m, expected["aabb_max"], atol=1e-4)
    assert layer.flatness.elevation_range_m == pytest.approx(expected["range"], abs=1e-4)


def test_canonical_profile_uses_independent_resolution_and_alignment_oracle(
    tmp_path: Path,
) -> None:
    # Given
    terrain = _artifact(tmp_path, "canonical")

    # When
    layer = place_habitat(
        terrain,
        _config(),
        policy=resolve_compatibility_policy("canonical"),
    )

    # Then: 2x3 m pixels make the 2x1 m footprint a 3x3 window; its first zero-range
    # candidate is row/column (2, 2), whose center is (1005, 1992.5).
    assert layer.anchor.dem_row_column == (2, 2)
    assert layer.anchor.projected_xy_m == pytest.approx((1_005.0, 1_992.5))
    assert layer.anchor.local_xyz_m == pytest.approx((1.0, -2.5, 9.5), abs=1e-4)
    assert layer.translation_local_m == pytest.approx((1.0, -2.5, 9.0), abs=1e-4)
    assert layer.aabb_min_local_m == pytest.approx((0.0, -3.0, 9.0), abs=1e-4)
    assert layer.aabb_max_local_m == pytest.approx((2.0, -2.0, 10.5), abs=1e-4)
    assert layer.flatness.elevation_range_m == 0.0
    assert layer.rotation_wxyz == (1.0, 0.0, 0.0, 0.0)


def test_profiles_have_deliberately_distinct_expected_anchor_and_transform(tmp_path: Path) -> None:
    # Given / When
    legacy = place_habitat(
        _artifact(tmp_path, "marslab_utils_6f30d67"),
        _config(),
        policy=resolve_compatibility_policy("marslab_utils_6f30d67"),
    )
    canonical = place_habitat(
        _artifact(tmp_path, "canonical"),
        _config(),
        policy=resolve_compatibility_policy("canonical"),
    )

    # Then
    assert legacy.anchor.dem_row_column == (6, 6)
    assert canonical.anchor.dem_row_column == (2, 2)
    assert legacy.translation_local_m == pytest.approx((8.75, -13.75, 24.5), abs=1e-4)
    assert canonical.translation_local_m == pytest.approx((1.0, -2.5, 9.0), abs=1e-4)


@pytest.mark.contract
def test_anchor_boundaries_nodata_and_malformed_settings_fail_closed(tmp_path: Path) -> None:
    # Given
    canonical = _artifact(tmp_path, "canonical")
    legacy = _artifact(tmp_path, "marslab_utils_6f30d67")
    canonical_policy = resolve_compatibility_policy("canonical")
    legacy_policy = resolve_compatibility_policy("marslab_utils_6f30d67")
    dem_path, frame = canonical.require_sampling_surface()

    # When / Then
    with pytest.raises(HabitatPlacementError, match="outside"):
        place_habitat(canonical, _config("absolute", x=990.0, y=2_015.0), policy=canonical_policy)
    clamped = place_habitat(
        legacy,
        _config("absolute", x=990.0, y=2_015.0),
        policy=legacy_policy,
    )
    assert clamped.anchor.dem_row_column == (0, 0)
    with pytest.raises(HabitatPlacementError, match="nodata"):
        place_habitat(canonical, _config("absolute", x=1_017.0, y=1_998.5), policy=canonical_policy)
    with pytest.raises(HabitatPlacementError, match="requires x and y"):
        place_habitat(canonical, _config("absolute"), policy=canonical_policy)
    with pytest.raises(FlatnessSearchError, match="fully-defined"):
        find_flattest_anchor(
            dem_path,
            frame,
            footprint_half_x_m=100.0,
            footprint_half_y_m=100.0,
            policy=canonical_policy,
        )


def test_public_api_authors_no_stage_and_imports_no_asset_generator(tmp_path: Path) -> None:
    # Given
    terrain = _artifact(tmp_path, "canonical")
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    # When
    layer = place_habitat(
        terrain,
        _config("crop_center"),
        policy=resolve_compatibility_policy("canonical"),
    )

    # Then
    after = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    assert after == before
    assert layer.asset_manifest == _ASSET_MANIFEST.resolve()
    assert not any(name.startswith("habitatgen.assetgen") for name in sys.modules)
