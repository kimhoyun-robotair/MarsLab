import numpy as np
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]

from marslab_scene.terrain.hirise.dem.nodata import NoValidDataError, build_valid_mask, fill_nodata


def test_build_valid_mask_excludes_nodata() -> None:
    array = np.array([[1.0, -9999.0], [2.0, 3.0]])

    mask = build_valid_mask(array, nodata=-9999.0)

    np.testing.assert_array_equal(mask, np.array([[True, False], [True, True]]))


def test_build_valid_mask_excludes_nan_inf() -> None:
    array = np.array([[1.0, np.nan], [np.inf, -np.inf]])

    mask = build_valid_mask(array, nodata=None)

    np.testing.assert_array_equal(mask, np.array([[True, False], [False, False]]))


def test_fill_nodata_mean() -> None:
    array = np.array([[1.0, -9999.0], [3.0, 5.0]])
    valid_mask = build_valid_mask(array, nodata=-9999.0)

    filled = fill_nodata(array, valid_mask, method="mean")

    np.testing.assert_allclose(filled, np.array([[1.0, 3.0], [3.0, 5.0]]))


def test_fill_nodata_zero() -> None:
    array = np.array([[1.0, -9999.0], [3.0, 5.0]])
    valid_mask = build_valid_mask(array, nodata=-9999.0)

    filled = fill_nodata(array, valid_mask, method="zero")

    np.testing.assert_allclose(filled, np.array([[1.0, 0.0], [3.0, 5.0]]))


def test_fill_nodata_nearest() -> None:
    array = np.array([[1.0, -9999.0, 9.0], [4.0, -9999.0, 12.0]])
    valid_mask = build_valid_mask(array, nodata=-9999.0)

    filled = fill_nodata(array, valid_mask, method="nearest")

    assert filled[0, 1] == 1.0
    assert filled[1, 1] == 4.0
    np.testing.assert_allclose(filled[valid_mask], array[valid_mask])


def test_fill_nodata_raises_without_valid_pixels() -> None:
    array = np.array([[-9999.0, np.nan]])
    valid_mask = build_valid_mask(array, nodata=-9999.0)

    with pytest.raises(NoValidDataError):
        fill_nodata(array, valid_mask, method="mean")
