"""Unit tests for marslab.terrain.dem_loader."""

import os

import numpy as np
import pytest
from osgeo import gdal, osr

from marslab.terrain.dem_loader import load_hirise_dem


@pytest.fixture
def synthetic_dem(tmp_path):
    """Create a small synthetic GeoTIFF DEM for testing."""
    filepath = str(tmp_path / "test_dem.tif")
    driver = gdal.GetDriverByName("GTiff")
    rows, cols = 64, 64
    ds = driver.Create(filepath, cols, rows, 1, gdal.GDT_Float32)

    # 1 m/pixel resolution, origin at (0, 64)
    ds.SetGeoTransform((0.0, 1.0, 0.0, 64.0, 0.0, -1.0))

    srs = osr.SpatialReference()
    srs.SetWellKnownGeogCS("WGS84")
    ds.SetProjection(srs.ExportToWkt())

    band = ds.GetRasterBand(1)
    elevation = np.random.default_rng(42).uniform(-2500, -2400, (rows, cols)).astype(np.float32)
    band.WriteArray(elevation)
    band.SetNoDataValue(-99999.0)
    band.FlushCache()
    ds = None

    return filepath, elevation


@pytest.fixture
def synthetic_dem_with_nodata(tmp_path):
    """Create a DEM with some nodata pixels."""
    filepath = str(tmp_path / "nodata_dem.tif")
    driver = gdal.GetDriverByName("GTiff")
    rows, cols = 32, 32
    ds = driver.Create(filepath, cols, rows, 1, gdal.GDT_Float32)
    ds.SetGeoTransform((0.0, 2.0, 0.0, 64.0, 0.0, -2.0))

    srs = osr.SpatialReference()
    srs.SetWellKnownGeogCS("WGS84")
    ds.SetProjection(srs.ExportToWkt())

    band = ds.GetRasterBand(1)
    nodata_val = -99999.0
    elevation = np.full((rows, cols), -2450.0, dtype=np.float32)
    elevation[0, 0] = nodata_val
    elevation[15, 15] = nodata_val
    band.WriteArray(elevation)
    band.SetNoDataValue(nodata_val)
    band.FlushCache()
    ds = None

    return filepath, nodata_val


# --- Shape and dtype ---


def test_load_correct_shape(synthetic_dem):
    """Loaded array matches GeoTIFF dimensions."""
    filepath, _ = synthetic_dem
    elevation, meta = load_hirise_dem(filepath)
    assert elevation.shape == (64, 64)


def test_load_dtype_float32(synthetic_dem):
    """Output array is float32."""
    filepath, _ = synthetic_dem
    elevation, _ = load_hirise_dem(filepath)
    assert elevation.dtype == np.float32


# --- Elevation range ---


def test_load_elevation_range(synthetic_dem):
    """Elevation min/max in metadata match actual array within 0.1m."""
    filepath, original = synthetic_dem
    _, meta = load_hirise_dem(filepath)
    assert abs(meta["elevation_min"] - float(np.nanmin(original))) < 0.1
    assert abs(meta["elevation_max"] - float(np.nanmax(original))) < 0.1


# --- Metadata ---


def test_load_metadata_keys(synthetic_dem):
    """All expected metadata keys are present."""
    filepath, _ = synthetic_dem
    _, meta = load_hirise_dem(filepath)
    expected_keys = {
        "resolution_x",
        "resolution_y",
        "origin_x",
        "origin_y",
        "width",
        "height",
        "crs_wkt",
        "nodata",
        "elevation_min",
        "elevation_max",
    }
    assert expected_keys == set(meta.keys())


def test_load_metadata_resolution(synthetic_dem):
    """Resolution values match GeoTransform."""
    filepath, _ = synthetic_dem
    _, meta = load_hirise_dem(filepath)
    assert meta["resolution_x"] == 1.0
    assert meta["resolution_y"] == 1.0


def test_load_metadata_dimensions(synthetic_dem):
    """Width and height match GeoTIFF dimensions."""
    filepath, _ = synthetic_dem
    _, meta = load_hirise_dem(filepath)
    assert meta["width"] == 64
    assert meta["height"] == 64


# --- Nodata handling ---


def test_load_nodata_becomes_nan(synthetic_dem_with_nodata):
    """Nodata pixels are replaced with NaN."""
    filepath, nodata_val = synthetic_dem_with_nodata
    elevation, _ = load_hirise_dem(filepath)
    assert np.isnan(elevation[0, 0])
    assert np.isnan(elevation[15, 15])
    assert not np.isnan(elevation[1, 1])


# --- Error handling ---


def test_load_file_not_found():
    """Missing file raises FileNotFoundError with path."""
    with pytest.raises(FileNotFoundError, match="not_exist.tif"):
        load_hirise_dem("not_exist.tif")


def test_load_invalid_file(tmp_path):
    """Non-GeoTIFF file raises ValueError."""
    bad_file = tmp_path / "bad.tif"
    bad_file.write_text("this is not a geotiff")
    with pytest.raises(ValueError, match="GDAL cannot open"):
        load_hirise_dem(str(bad_file))


# --- Optional: real HiRISE DEM test ---

REAL_DEM_PATH = "assets/mars_assets/DEM/jezero_crater.tif"


@pytest.mark.skipif(
    not os.path.isfile(REAL_DEM_PATH),
    reason="HiRISE DTM not downloaded",
)
def test_load_real_hirise_dem():
    """Validate real HiRISE DEM loads correctly."""
    elevation, meta = load_hirise_dem(REAL_DEM_PATH)
    assert elevation.ndim == 2
    assert meta["resolution_x"] > 0
    assert -3000 < meta["elevation_min"] < -2000
    assert -3000 < meta["elevation_max"] < -2000
