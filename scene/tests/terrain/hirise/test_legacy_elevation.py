import numpy as np
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]

from marslab_scene.terrain.elevation import (
    NoValidElevationError,
    compute_z_reference,
    denormalize_elevation,
    normalize_elevation,
)
from marslab_scene.terrain.hirise.config import ElevationConfig
from marslab_scene.terrain.hirise.dem.nodata import build_valid_mask


def test_min_zero_normalization() -> None:
    array = np.array([[10.0, 20.0], [30.0, 40.0]])
    valid_mask = build_valid_mask(array, nodata=None)

    result = normalize_elevation(array, valid_mask, ElevationConfig(normalization="min_zero"))

    assert result.z_reference_m == 10.0
    np.testing.assert_allclose(result.local_z, np.array([[0.0, 10.0], [20.0, 30.0]]))
    assert result.raw_min_m == 10.0
    assert result.raw_max_m == 40.0
    assert result.local_min_m == 0.0
    assert result.local_max_m == 30.0


def test_mean_zero_normalization() -> None:
    array = np.array([[10.0, 20.0], [30.0, 40.0]])
    valid_mask = build_valid_mask(array, nodata=None)

    result = normalize_elevation(array, valid_mask, ElevationConfig(normalization="mean_zero"))

    assert result.z_reference_m == 25.0
    np.testing.assert_allclose(result.local_z, np.array([[-15.0, -5.0], [5.0, 15.0]]))


def test_median_zero_normalization() -> None:
    array = np.array([[1.0, 2.0, 100.0]])
    valid_mask = build_valid_mask(array, nodata=None)

    result = normalize_elevation(array, valid_mask, ElevationConfig(normalization="median_zero"))

    assert result.z_reference_m == 2.0
    np.testing.assert_allclose(result.local_z, np.array([[-1.0, 0.0, 98.0]]))


def test_percentile_zero_normalization() -> None:
    array = np.array([[0.0, 10.0, 20.0, 30.0, 40.0]])
    valid_mask = build_valid_mask(array, nodata=None)

    result = normalize_elevation(
        array,
        valid_mask,
        ElevationConfig(normalization="percentile_zero", reference_percentile=25.0),
    )

    assert result.z_reference_m == 10.0
    np.testing.assert_allclose(result.local_z, np.array([[-10.0, 0.0, 10.0, 20.0, 30.0]]))


def test_manual_reference_normalization() -> None:
    array = np.array([[10.0, 20.0]])
    valid_mask = build_valid_mask(array, nodata=None)

    result = normalize_elevation(
        array,
        valid_mask,
        ElevationConfig(
            normalization="manual",
            manual_reference_m=12.0,
            vertical_scale=2.0,
            z_offset_m=1.0,
        ),
    )

    assert result.z_reference_m == 12.0
    np.testing.assert_allclose(result.local_z, np.array([[-3.0, 17.0]]))


def test_absolute_mode_preserves_values() -> None:
    array = np.array([[-2980.0, -2123.0]])
    valid_mask = build_valid_mask(array, nodata=None)

    result = normalize_elevation(array, valid_mask, ElevationConfig(normalization="absolute"))

    assert result.z_reference_m == 0.0
    np.testing.assert_allclose(result.local_z, array)


def test_nodata_excluded_from_stats() -> None:
    array = np.array([[-9999.0, 10.0, 20.0]])
    valid_mask = build_valid_mask(array, nodata=-9999.0)

    result = normalize_elevation(array, valid_mask, ElevationConfig(normalization="min_zero"))

    assert result.raw_min_m == 10.0
    assert result.raw_max_m == 20.0
    assert result.z_reference_m == 10.0


def test_denormalize_roundtrip() -> None:
    array = np.array([[10.0, 20.0, 30.0]])
    valid_mask = build_valid_mask(array, nodata=None)
    result = normalize_elevation(
        array,
        valid_mask,
        ElevationConfig(normalization="mean_zero", vertical_scale=2.0, z_offset_m=5.0),
    )

    raw = denormalize_elevation(result.local_z, result)

    np.testing.assert_allclose(raw, array)


def test_compute_z_reference_raises_without_valid_pixels() -> None:
    array = np.array([[np.nan, -9999.0]])
    valid_mask = build_valid_mask(array, nodata=-9999.0)

    with pytest.raises(NoValidElevationError):
        compute_z_reference(array, valid_mask, ElevationConfig())
