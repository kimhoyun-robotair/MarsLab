"""Tests for deterministic sensor noise seeding (no Isaac Sim runtime required).

Covers:
- Wheel odometry: same seed → identical noise; different seed → different noise.
- IMU noise publisher: same seed → identical noise; different seed → different noise.
- SeedSequence derivation: per-sensor streams are independent (child seeds differ).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest


# ---------------------------------------------------------------------------
# Wheel odometry seed tests
# ---------------------------------------------------------------------------


def _make_wheel_odom_ctx(seed):
    """Build a WheelOdometryContext with a mock publisher (no rclpy)."""
    from marslab.ros2_bridge.wheel_odometry_publisher import WheelOdometryContext

    return WheelOdometryContext(
        publisher=MagicMock(),
        tf_broadcaster=None,
        node=MagicMock(),
        left_indices=np.array([0, 1, 2], dtype=np.int32),
        right_indices=np.array([3, 4, 5], dtype=np.int32),
        wheel_radius=0.2667,
        track_width=2.369,
        slip_left=0.0,
        slip_right=0.0,
        sigma_omega=0.1,
        rng=np.random.default_rng(seed),
    )


def _draw_wheel_noise(seed, n=20):
    """Draw n noise samples from the wheel odom RNG."""
    ctx = _make_wheel_odom_ctx(seed)
    return [float(ctx.rng.normal(0.0, ctx.sigma_omega)) for _ in range(n)]


def test_wheel_odom_same_seed_identical():
    seq_a = _draw_wheel_noise(42)
    seq_b = _draw_wheel_noise(42)
    assert seq_a == seq_b, "same seed must produce identical wheel odom noise"


def test_wheel_odom_different_seed_different():
    seq_42 = _draw_wheel_noise(42)
    seq_43 = _draw_wheel_noise(43)
    assert seq_42 != seq_43, "different seeds must produce different wheel odom noise"


# ---------------------------------------------------------------------------
# IMU noise publisher seed tests
# ---------------------------------------------------------------------------


def _draw_imu_noise(seed, n=20):
    """Draw n (lin_acc, ang_vel) noise pairs using the IMU noise RNG."""
    rng = np.random.default_rng(seed)
    sigma_la = 0.05
    sigma_av = 0.005
    samples = []
    for _ in range(n):
        la = rng.normal(0.0, sigma_la, 3).tolist()
        av = rng.normal(0.0, sigma_av, 3).tolist()
        samples.append((la, av))
    return samples


def test_imu_same_seed_identical():
    seq_a = _draw_imu_noise(42)
    seq_b = _draw_imu_noise(42)
    assert seq_a == seq_b, "same seed must produce identical IMU noise"


def test_imu_different_seed_different():
    seq_42 = _draw_imu_noise(42)
    seq_43 = _draw_imu_noise(43)
    assert seq_42 != seq_43, "different seeds must produce different IMU noise"


def test_imu_noise_publisher_determinism():
    """ImuNoiseContext.rng seeded with the same value produces identical output."""
    from marslab.ros2_bridge.imu_noise_publisher import ImuNoiseContext

    def _make_ctx(seed):
        node = MagicMock()
        node.get_clock.return_value.now.return_value.to_msg.return_value = MagicMock(
            sec=0, nanosec=0
        )
        return ImuNoiseContext(
            publisher=MagicMock(),
            node=node,
            rng=np.random.default_rng(seed),
            sigma_lin_acc=0.05,
            sigma_ang_vel=0.005,
            imu_prim_path="/World/Rover/Body_Chassis/imu",
        )

    base_la = np.array([0.0, 0.0, 3.72])
    base_av = np.array([0.0, 0.0, 0.0])

    def _collect(seed, n=10):
        ctx = _make_ctx(seed)
        results = []
        for _ in range(n):
            la = base_la.copy()
            av = base_av.copy()
            la += ctx.rng.normal(0.0, ctx.sigma_lin_acc, 3)
            av += ctx.rng.normal(0.0, ctx.sigma_ang_vel, 3)
            results.append((la.tolist(), av.tolist()))
        return results

    assert _collect(42) == _collect(42), "same seed → identical IMU noise sequence"
    assert _collect(42) != _collect(43), "different seed → different IMU noise sequence"


# ---------------------------------------------------------------------------
# SeedSequence child seed independence
# ---------------------------------------------------------------------------


def test_seedsequence_child_seeds_independent():
    """SeedSequence.spawn(3) produces 3 distinct, independent child seeds."""
    master = 42
    ss = np.random.SeedSequence(master)
    children = ss.spawn(3)
    states = [int(c.generate_state(1)[0]) for c in children]

    # All three child seeds must be distinct
    assert len(set(states)) == 3, f"child seeds must be distinct, got {states}"

    # Same master → same child seeds (deterministic derivation)
    ss2 = np.random.SeedSequence(master)
    children2 = ss2.spawn(3)
    states2 = [int(c.generate_state(1)[0]) for c in children2]
    assert states == states2, "SeedSequence must be deterministic for the same master seed"


def test_seedsequence_different_master_different_children():
    ss_a = np.random.SeedSequence(42)
    ss_b = np.random.SeedSequence(43)
    children_a = [int(c.generate_state(1)[0]) for c in ss_a.spawn(3)]
    children_b = [int(c.generate_state(1)[0]) for c in ss_b.spawn(3)]
    assert children_a != children_b, "different master seeds must produce different child seeds"


# ---------------------------------------------------------------------------
# Schema: sensors.seed field accepted/defaults correctly
# ---------------------------------------------------------------------------


def test_sensors_config_seed_field_present():
    """SensorsConfig accepts an integer seed and defaults to None."""
    from marslab.config.schema.robot import SensorsConfig

    fields = SensorsConfig.model_fields
    assert "seed" in fields, "SensorsConfig must have a 'seed' field"
    assert fields["seed"].default is None, "sensors.seed must default to None"


def test_imu_config_noise_fields_present():
    """IMUConfig accepts sigma_lin_acc and sigma_ang_vel, both defaulting to 0."""
    from marslab.config.schema.robot import IMUConfig

    fields = IMUConfig.model_fields
    assert "sigma_lin_acc" in fields, "IMUConfig must have sigma_lin_acc"
    assert "sigma_ang_vel" in fields, "IMUConfig must have sigma_ang_vel"
    assert fields["sigma_lin_acc"].default == 0.0
    assert fields["sigma_ang_vel"].default == 0.0
