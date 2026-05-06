"""Unit tests for marslab.robots.rover_control.

The module exposes a single public helper, :func:`ackermann_command`.
The per-step ramp / clamp limiters live inline in
``marslab.runtime.main_loop`` (single-source: the runtime owns the
ramp state across ticks); their tests live with that module.
"""

import numpy as np
import pytest

from marslab.robots.rover_control import ackermann_command


class TestAckermannCommand:
    """ackermann_command returns expected steer + velocity arrays."""

    @pytest.fixture
    def geometry(self) -> dict:
        return {
            "wheelbase": 2.0,
            "track_steer": 1.6,
            "track_middle": 1.6,
            "wheel_radius": 0.25,
        }

    def test_straight_drive_returns_zero_steer(self, geometry: dict) -> None:
        steer, vel = ackermann_command(v=1.0, w=0.0, **geometry)
        np.testing.assert_array_almost_equal(steer, np.zeros(4))
        np.testing.assert_array_almost_equal(vel, np.full(6, 1.0 / geometry["wheel_radius"]))

    def test_turning_returns_nonzero_steer(self, geometry: dict) -> None:
        steer, vel = ackermann_command(v=1.0, w=0.5, **geometry)
        # All four steerable wheels must produce nonzero angles when w != 0.
        assert np.all(np.abs(steer) > 1e-6)
        # Per-wheel velocities must all be finite and nonzero.
        assert np.all(np.isfinite(vel))
        assert np.all(np.abs(vel) > 1e-6)

    def test_negative_geometry_raises(self) -> None:
        with pytest.raises(ValueError, match="wheelbase"):
            ackermann_command(1.0, 0.0, wheelbase=0.0, track_steer=1.0, track_middle=1.0, wheel_radius=0.25)
        with pytest.raises(ValueError, match="track_steer"):
            ackermann_command(1.0, 0.0, wheelbase=2.0, track_steer=0.0, track_middle=1.0, wheel_radius=0.25)
        with pytest.raises(ValueError, match="track_middle"):
            ackermann_command(1.0, 0.0, wheelbase=2.0, track_steer=1.0, track_middle=0.0, wheel_radius=0.25)
        with pytest.raises(ValueError, match="wheel_radius"):
            ackermann_command(1.0, 0.0, wheelbase=2.0, track_steer=1.0, track_middle=1.0, wheel_radius=0.0)

    def test_dtype_float32(self, geometry: dict) -> None:
        steer, vel = ackermann_command(v=0.5, w=0.2, **geometry)
        assert steer.dtype == np.float32
        assert vel.dtype == np.float32
