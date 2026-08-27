import numpy as np
import pytest

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]

from marslab_scene.terrain.frame import (
    Rep103GridError,
    build_frame_metadata,
    build_local_xy_grid,
    validate_rep103_grid,
)
from marslab_scene.terrain.hirise.dem.resample import resample_elevation


def test_local_grid_x_increases_east() -> None:
    x, _ = build_local_xy_grid(width=5, height=3, size_x_m=40.0, size_y_m=20.0)

    assert x[1, 0] < x[1, 1] < x[1, 2] < x[1, 3] < x[1, 4]
    np.testing.assert_allclose(x[1], np.array([-20.0, -10.0, 0.0, 10.0, 20.0]))


def test_local_grid_y_increases_north() -> None:
    _, y = build_local_xy_grid(width=5, height=3, size_x_m=40.0, size_y_m=20.0)

    assert y[0, 2] > y[1, 2] > y[2, 2]
    np.testing.assert_allclose(y[:, 2], np.array([10.0, 0.0, -10.0]))


def test_grid_center_near_zero_for_odd_grid() -> None:
    x, y = build_local_xy_grid(width=5, height=5, size_x_m=40.0, size_y_m=40.0)

    assert x[2, 2] == 0.0
    assert y[2, 2] == 0.0


def test_grid_bounds_match_crop_size() -> None:
    x, y = build_local_xy_grid(width=5, height=3, size_x_m=40.0, size_y_m=20.0)

    assert x.min() == -20.0
    assert x.max() == 20.0
    assert y.min() == -10.0
    assert y.max() == 10.0


def test_rep103_metadata_values() -> None:
    metadata = build_frame_metadata(frame_id="map")

    assert metadata == {
        "standard": "ROS REP-103",
        "frame_id": "map",
        "type": "local_enu",
        "x_axis": "east",
        "y_axis": "north",
        "z_axis": "up",
        "meters_per_unit": 1.0,
        "yaw_zero": "east",
        "yaw_positive": "counter_clockwise",
    }


def test_validate_rep103_grid_accepts_valid_grid() -> None:
    x, y = build_local_xy_grid(width=5, height=3, size_x_m=40.0, size_y_m=20.0)
    z = np.zeros_like(x)

    validate_rep103_grid(x, y, z)


def test_validate_rep103_grid_rejects_bad_y_direction() -> None:
    x, y = build_local_xy_grid(width=5, height=3, size_x_m=40.0, size_y_m=20.0)
    z = np.zeros_like(x)

    with pytest.raises(Rep103GridError):
        validate_rep103_grid(x, np.flipud(y), z)


def test_resample_nearest_is_deterministic() -> None:
    array = np.array([[0.0, 10.0], [20.0, 30.0]])

    resampled = resample_elevation(array, target_size=3, method="nearest")

    np.testing.assert_allclose(
        resampled,
        np.array([[0.0, 10.0, 10.0], [20.0, 30.0, 30.0], [20.0, 30.0, 30.0]]),
    )


def test_resample_bilinear_preserves_corners_and_center() -> None:
    array = np.array([[0.0, 10.0], [20.0, 30.0]])

    resampled = resample_elevation(array, target_size=3, method="bilinear")

    np.testing.assert_allclose(
        resampled,
        np.array([[0.0, 5.0, 10.0], [10.0, 15.0, 20.0], [20.0, 25.0, 30.0]]),
    )


def test_resample_rejects_invalid_target_size() -> None:
    with pytest.raises(ValueError, match="target_size"):
        resample_elevation(np.ones((2, 2)), target_size=1, method="bilinear")
