"""Unit tests for DEM pre-conversion (GDAL-free)."""

import json
import os

import numpy as np
import pytest

from marslab.terrain.dem_loader import load_converted_dem, save_converted_dem


@pytest.fixture
def sample_dem_data():
    """Create synthetic elevation + metadata matching dem_loader output format."""
    rng = np.random.default_rng(42)
    elevation = (rng.standard_normal((64, 64)) * 10 - 2500).astype(np.float32)
    metadata = {
        "resolution_x": 1.0,
        "resolution_y": 1.0,
        "origin_x": 0.0,
        "origin_y": 64.0,
        "width": 64,
        "height": 64,
        "crs_wkt": 'GEOGCS["Mars"]',
        "nodata": None,
        "elevation_min": float(np.nanmin(elevation)),
        "elevation_max": float(np.nanmax(elevation)),
    }
    return elevation, metadata


def test_save_and_load_roundtrip(tmp_path, sample_dem_data):
    """Round-trip: save then load produces identical data."""
    elevation, metadata = sample_dem_data
    output_dir = str(tmp_path / "converted")

    save_converted_dem(elevation, metadata, output_dir)
    loaded_elev, loaded_meta = load_converted_dem(output_dir)

    np.testing.assert_array_equal(loaded_elev, elevation)
    assert loaded_elev.dtype == np.float32
    assert loaded_meta["resolution_x"] == metadata["resolution_x"]
    assert loaded_meta["width"] == metadata["width"]
    assert loaded_meta["nodata"] is None


def test_save_creates_output_dir(tmp_path, sample_dem_data):
    """save_converted_dem creates the output directory if it doesn't exist."""
    elevation, metadata = sample_dem_data
    output_dir = str(tmp_path / "nested" / "deep" / "dir")

    save_converted_dem(elevation, metadata, output_dir)

    assert os.path.isfile(os.path.join(output_dir, "elevation.npy"))
    assert os.path.isfile(os.path.join(output_dir, "metadata.json"))


def test_save_rejects_non_2d(tmp_path, sample_dem_data):
    """save_converted_dem raises ValueError for non-2D arrays."""
    _, metadata = sample_dem_data
    bad_elevation = np.zeros((10,), dtype=np.float32)

    with pytest.raises(ValueError, match="2D"):
        save_converted_dem(bad_elevation, metadata, str(tmp_path))


def test_load_missing_npy(tmp_path):
    """load_converted_dem raises FileNotFoundError if elevation.npy is missing."""
    # Only create metadata.json
    with open(str(tmp_path / "metadata.json"), "w") as f:
        json.dump({"resolution_x": 1.0}, f)

    with pytest.raises(FileNotFoundError, match="elevation"):
        load_converted_dem(str(tmp_path))


def test_load_missing_json(tmp_path):
    """load_converted_dem raises FileNotFoundError if metadata.json is missing."""
    # Only create elevation.npy
    np.save(str(tmp_path / "elevation.npy"), np.zeros((4, 4), dtype=np.float32))

    with pytest.raises(FileNotFoundError, match="metadata"):
        load_converted_dem(str(tmp_path))


def test_dtype_float32(tmp_path, sample_dem_data):
    """Loaded elevation is always float32 regardless of saved dtype."""
    elevation, metadata = sample_dem_data
    # Save as float64 to test dtype conversion
    output_dir = str(tmp_path / "f64")
    os.makedirs(output_dir)
    np.save(os.path.join(output_dir, "elevation.npy"), elevation.astype(np.float64))
    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f)

    loaded_elev, _ = load_converted_dem(output_dir)
    assert loaded_elev.dtype == np.float32


def test_nan_preservation(tmp_path):
    """NaN values in elevation are preserved through save/load cycle."""
    elevation = np.array([[1.0, np.nan], [np.nan, 2.0]], dtype=np.float32)
    metadata = {"resolution_x": 1.0, "nodata": None}
    output_dir = str(tmp_path / "nan_test")

    save_converted_dem(elevation, metadata, output_dir)
    loaded_elev, _ = load_converted_dem(output_dir)

    assert np.isnan(loaded_elev[0, 1])
    assert np.isnan(loaded_elev[1, 0])
    assert loaded_elev[0, 0] == 1.0
    assert loaded_elev[1, 1] == 2.0


def test_metadata_json_readable(tmp_path, sample_dem_data):
    """Saved metadata.json is valid JSON readable by stdlib json."""
    elevation, metadata = sample_dem_data
    output_dir = str(tmp_path / "json_test")

    save_converted_dem(elevation, metadata, output_dir)

    with open(os.path.join(output_dir, "metadata.json"), "r") as f:
        loaded = json.load(f)

    assert isinstance(loaded, dict)
    assert "resolution_x" in loaded
    assert "elevation_min" in loaded
