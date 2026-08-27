from collections.abc import Callable
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]
from marslab_scene.terrain.hirise.ingest.dem_info import (
    UnsupportedCrsError,
    UnsupportedRasterTransformError,
    inspect_dem,
    validate_dem_for_mvp,
)
from rasterio.transform import Affine


def test_inspect_dem_returns_basic_metadata(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(width=12, height=8, count=2, dtype="float32")

    info = inspect_dem(path, band=2)

    assert info.path == str(path)
    assert info.width == 12
    assert info.height == 8
    assert info.count == 2
    assert info.to_dict()["band_count"] == 2
    assert info.dtype == "float32"
    assert info.crs_wkt is not None
    assert info.transform == (2.0, 0.0, 100.0, 0.0, -3.0, 200.0)
    assert info.bounds == (100.0, 176.0, 124.0, 200.0)
    assert info.pixel_size_x_m == 2.0
    assert info.pixel_size_y_m == 3.0
    assert info.is_north_up is True
    assert info.estimated_full_raster_size_mb > 0.0


def test_inspect_dem_reports_nodata(synthetic_geotiff_factory: Callable[..., Path]) -> None:
    path = synthetic_geotiff_factory(nodata=-32768.0)

    info = inspect_dem(path)

    assert info.nodata == -32768.0


def test_inspect_dem_rejects_invalid_band(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(count=1)

    with pytest.raises(ValueError, match="Band 2"):
        inspect_dem(path, band=2)


def test_validate_rejects_rotated_transform(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(transform=Affine(2.0, 0.2, 100.0, 0.0, -2.0, 200.0))
    info = inspect_dem(path)

    with pytest.raises(UnsupportedRasterTransformError):
        validate_dem_for_mvp(info)


def test_validate_rejects_non_meter_crs_if_required(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(crs="EPSG:4326")
    info = inspect_dem(path)

    with pytest.raises(UnsupportedCrsError):
        validate_dem_for_mvp(info)


def test_validate_accepts_projected_meter_crs(
    synthetic_geotiff_factory: Callable[..., Path],
) -> None:
    path = synthetic_geotiff_factory(crs="EPSG:32611")
    info = inspect_dem(path)

    validate_dem_for_mvp(info)
