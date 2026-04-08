"""Unit tests for marslab.terrain.procedural_generator."""

import numpy as np
import pytest

from marslab.terrain.procedural_generator import generate_terrain


@pytest.mark.parametrize("preset", ["flat", "crater", "hills"])
def test_shape_matches_size(preset):
    """Output shape matches requested size."""
    elev, _ = generate_terrain(preset, (128, 64), 1.0, seed=42)
    assert elev.shape == (128, 64)


@pytest.mark.parametrize("preset", ["flat", "crater", "hills"])
def test_dtype_float32(preset):
    elev, _ = generate_terrain(preset, (64, 64), 1.0, seed=42)
    assert elev.dtype == np.float32


@pytest.mark.parametrize("preset", ["flat", "crater", "hills"])
def test_elevation_range_physical(preset):
    """Elevation is within Mars-like range."""
    _, meta = generate_terrain(preset, (256, 256), 1.0, seed=42)
    assert -3000 < meta["elevation_min"] < 0
    assert -3000 < meta["elevation_max"] < 0


@pytest.mark.parametrize("preset", ["flat", "crater", "hills"])
def test_metadata_keys(preset):
    """All expected metadata keys present."""
    _, meta = generate_terrain(preset, (64, 64), 1.0, seed=42)
    expected = {
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
    assert expected == set(meta.keys())


def test_flat_low_variance():
    """Flat terrain has low elevation variance (< 10m std)."""
    elev, _ = generate_terrain("flat", (256, 256), 1.0, seed=42)
    assert np.std(elev) < 10.0


def test_crater_center_lowest():
    """Crater center is lower than rim."""
    elev, _ = generate_terrain("crater", (256, 256), 1.0, seed=42)
    center = elev[128, 128]
    rim_samples = [elev[128, 180], elev[180, 128], elev[128, 76], elev[76, 128]]
    assert all(center < r for r in rim_samples)


def test_hills_higher_variance_than_flat():
    """Hills have more variation than flat."""
    flat, _ = generate_terrain("flat", (256, 256), 1.0, seed=42)
    hills, _ = generate_terrain("hills", (256, 256), 1.0, seed=42)
    assert np.std(hills) > np.std(flat)


@pytest.mark.parametrize("preset", ["flat", "crater", "hills"])
def test_seed_determinism(preset):
    """Same seed produces identical output."""
    e1, _ = generate_terrain(preset, (64, 64), 1.0, seed=42)
    e2, _ = generate_terrain(preset, (64, 64), 1.0, seed=42)
    assert np.array_equal(e1, e2)


def test_different_seeds_differ():
    """Different seeds produce different output."""
    e1, _ = generate_terrain("flat", (64, 64), 1.0, seed=42)
    e2, _ = generate_terrain("flat", (64, 64), 1.0, seed=99)
    assert not np.array_equal(e1, e2)


def test_unknown_preset_raises():
    with pytest.raises(ValueError, match="Unknown preset"):
        generate_terrain("volcano", (64, 64), 1.0, seed=42)


def test_metadata_resolution():
    _, meta = generate_terrain("flat", (64, 64), 2.5, seed=42)
    assert meta["resolution_x"] == 2.5
    assert meta["resolution_y"] == 2.5
    assert meta["width"] == 64
    assert meta["height"] == 64
