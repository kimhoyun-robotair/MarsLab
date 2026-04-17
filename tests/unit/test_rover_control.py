"""Unit tests for marslab.robots.rover_control ramp + clamp helpers."""

import numpy as np
import pytest

from marslab.robots.rover_control import (
    clamp_steer_angles,
    ramp_steer_angles,
    ramp_wheel_velocities,
)


class TestClampSteerAngles:
    """clamp_steer_angles saturates at mechanical limits."""

    def test_within_limits_passthrough(self) -> None:
        angles = np.array([0.1, -0.3, 0.5, -0.5], dtype=np.float32)
        out = clamp_steer_angles(angles, max_angle=0.7)
        np.testing.assert_array_almost_equal(out, angles)
        assert out.dtype == np.float32

    def test_saturates_positive(self) -> None:
        angles = np.array([1.5, 0.0, 0.8, -0.4], dtype=np.float32)
        out = clamp_steer_angles(angles, max_angle=0.7)
        np.testing.assert_array_almost_equal(out, [0.7, 0.0, 0.7, -0.4])

    def test_saturates_negative(self) -> None:
        angles = np.array([-1.5, -0.8, 0.0, 0.1], dtype=np.float32)
        out = clamp_steer_angles(angles, max_angle=0.7)
        np.testing.assert_array_almost_equal(out, [-0.7, -0.7, 0.0, 0.1])

    def test_zero_max_raises(self) -> None:
        with pytest.raises(ValueError, match="max_angle"):
            clamp_steer_angles(np.zeros(4), max_angle=0.0)

    def test_negative_max_raises(self) -> None:
        with pytest.raises(ValueError, match="max_angle"):
            clamp_steer_angles(np.zeros(4), max_angle=-0.1)


class TestRampSteerAngles:
    """ramp_steer_angles limits per-step change, no ramp if limit <= 0."""

    def test_small_delta_full_step(self) -> None:
        current = np.zeros(4, dtype=np.float32)
        target = np.array([0.01, -0.02, 0.01, -0.02], dtype=np.float32)
        out = ramp_steer_angles(current, target, per_step_limit=0.1)
        np.testing.assert_array_almost_equal(out, target)

    def test_large_delta_clamped(self) -> None:
        current = np.zeros(4, dtype=np.float32)
        target = np.array([1.0, -1.0, 0.5, -0.5], dtype=np.float32)
        out = ramp_steer_angles(current, target, per_step_limit=0.1)
        np.testing.assert_array_almost_equal(out, [0.1, -0.1, 0.1, -0.1])

    def test_disabled_when_limit_zero(self) -> None:
        current = np.zeros(4, dtype=np.float32)
        target = np.array([2.0, -2.0, 0.0, 0.0], dtype=np.float32)
        out = ramp_steer_angles(current, target, per_step_limit=0.0)
        np.testing.assert_array_almost_equal(out, target)

    def test_convergence_over_steps(self) -> None:
        """After N steps of ramping, current should reach target."""
        current = np.zeros(4, dtype=np.float32)
        target = np.array([0.5, -0.5, 0.3, -0.3], dtype=np.float32)
        limit = 0.05
        for _ in range(100):
            current = ramp_steer_angles(current, target, per_step_limit=limit)
        np.testing.assert_array_almost_equal(current, target, decimal=5)


class TestRampWheelVelocities:
    """ramp_wheel_velocities: asymmetric accel/decel limiter."""

    def test_small_delta_full_step(self) -> None:
        current = np.zeros(6, dtype=np.float32)
        target = np.full(6, 0.005, dtype=np.float32)
        out = ramp_wheel_velocities(current, target, per_step_limit=0.01, decel_multiplier=1.0)
        np.testing.assert_array_almost_equal(out, target)

    def test_acceleration_clamped(self) -> None:
        current = np.zeros(6, dtype=np.float32)
        target = np.full(6, 1.0, dtype=np.float32)
        out = ramp_wheel_velocities(current, target, per_step_limit=0.1, decel_multiplier=3.0)
        # Accelerating (|tgt| > |cur|) → uses per_step_limit = 0.1.
        np.testing.assert_array_almost_equal(out, np.full(6, 0.1))

    def test_deceleration_uses_multiplier(self) -> None:
        """Braking from +1.0 toward 0.0 uses decel_multiplier*limit per step."""
        current = np.full(6, 1.0, dtype=np.float32)
        target = np.zeros(6, dtype=np.float32)
        out = ramp_wheel_velocities(current, target, per_step_limit=0.1, decel_multiplier=3.0)
        # |tgt|=0 < |cur|=1 → decel: per-step = 0.1*3 = 0.3.  delta clipped to -0.3.
        np.testing.assert_array_almost_equal(out, np.full(6, 0.7))

    def test_mixed_accel_decel_per_element(self) -> None:
        """One wheel accelerating, another decelerating — different limits apply."""
        current = np.array([0.0, 1.0, 0.0, 1.0, 0.0, 1.0], dtype=np.float32)
        target = np.array([1.0, 0.0, 1.0, 0.0, 1.0, 0.0], dtype=np.float32)
        out = ramp_wheel_velocities(current, target, per_step_limit=0.1, decel_multiplier=3.0)
        # Indices 0,2,4 accelerate (+0.1 each). Indices 1,3,5 decelerate (-0.3 each).
        np.testing.assert_array_almost_equal(out, [0.1, 0.7, 0.1, 0.7, 0.1, 0.7])

    def test_disabled_when_limit_zero(self) -> None:
        current = np.zeros(6, dtype=np.float32)
        target = np.full(6, 2.0, dtype=np.float32)
        out = ramp_wheel_velocities(current, target, per_step_limit=0.0)
        np.testing.assert_array_almost_equal(out, target)

    def test_reverse_direction_acceleration(self) -> None:
        """0 → -1.0: magnitude grows → uses accel limit, not decel."""
        current = np.zeros(6, dtype=np.float32)
        target = np.full(6, -1.0, dtype=np.float32)
        out = ramp_wheel_velocities(current, target, per_step_limit=0.1, decel_multiplier=3.0)
        np.testing.assert_array_almost_equal(out, np.full(6, -0.1))

    def test_dtype_preserved(self) -> None:
        current = np.zeros(6, dtype=np.float32)
        target = np.full(6, 0.5, dtype=np.float32)
        out = ramp_wheel_velocities(current, target, per_step_limit=0.1)
        assert out.dtype == np.float32
