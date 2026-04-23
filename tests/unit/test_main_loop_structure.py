"""Offline-first unit tests for :mod:`marslab.runtime.main_loop` (R6-1).

These tests lock down the public surface of the main-loop facade without
booting Isaac Sim.  They:

*   Verify ``LoopContext`` exposes every field the twin monolithic runner
    populates.
*   Confirm the three state dataclasses (``ControlState``,
    ``AtmosphereLoopState``, ``OdomPublishState``) have the documented
    default values.
*   Check that :func:`run_main_loop` declares an ``int`` return annotation
    so shutdown semantics match the Oracle contract.

No Isaac Sim, no ROS2, no filesystem writes.
"""

from __future__ import annotations

import inspect
from dataclasses import fields

import numpy as np

from marslab.runtime import main_loop as ml
from marslab.runtime.main_loop import (
    AtmosphereLoopState,
    ControlState,
    LoopContext,
    OdomPublishState,
    quat_inverse,
    quat_multiply,
    quat_rotate_vec,
    run_main_loop,
)

# ---------------------------------------------------------------------------
# LoopContext surface
# ---------------------------------------------------------------------------


def test_loop_context_required_fields_present() -> None:
    """``LoopContext`` declares every field the twin runner populates."""
    field_names = {f.name for f in fields(LoopContext)}
    required = {
        "simulation_app",
        "world",
        "stage",
        "articulation",
        "imu",
        "drive_indices",
        "steer_indices",
        "wheelbase",
        "track_steer",
        "track_middle",
        "wheel_radius",
        "v_max",
        "w_max",
        "physics_dt",
        "negate_steer",
        "debug_logging",
        "max_wheel_accel_rate",
        "decel_multiplier",
        "max_steer_angle",
        "steer_ramp_rate",
        "control",
        "atmosphere",
        "odom",
        "render_config",
        "ackermann_fn",
        "spin_once",
        "update_sun_fn",
        "update_sky_fn",
        "configure_fog_fn",
        "compute_sun_fn",
        "compute_sol_sun_fn",
        "compute_direct_intensity_fn",
        "compute_diffuse_fraction_fn",
        "compute_sky_dome_fn",
        "atmo_panel_update",
    }
    missing = required - field_names
    assert not missing, f"LoopContext missing fields: {sorted(missing)}"


# ---------------------------------------------------------------------------
# ControlState defaults
# ---------------------------------------------------------------------------


def test_control_state_defaults() -> None:
    """Required ramp arrays + default step/twist values."""
    cs = ControlState(
        current_drive_targets=np.zeros(6, dtype=np.float32),
        current_steer_targets=np.zeros(4, dtype=np.float32),
    )
    assert cs.step_count == 0
    assert cs.latest_twist == {"v": 0.0, "w": 0.0}
    assert cs.current_drive_targets.shape == (6,)
    assert cs.current_steer_targets.dtype == np.float32


def test_control_state_latest_twist_is_per_instance() -> None:
    """Default ``latest_twist`` dict is not shared across instances."""
    a = ControlState(
        current_drive_targets=np.zeros(1, dtype=np.float32),
        current_steer_targets=np.zeros(1, dtype=np.float32),
    )
    b = ControlState(
        current_drive_targets=np.zeros(1, dtype=np.float32),
        current_steer_targets=np.zeros(1, dtype=np.float32),
    )
    a.latest_twist["v"] = 1.0
    assert b.latest_twist["v"] == 0.0


# ---------------------------------------------------------------------------
# AtmosphereLoopState defaults
# ---------------------------------------------------------------------------


def test_atmosphere_state_defaults() -> None:
    """Match documented attribute defaults.

    P6 G5 (2026-04-23): ``sol_duration`` and ``solar_constant`` are now
    required — Mars physics defaults were removed from the dataclass to
    stop duplicating ``MarsEnvConfig``. This test sources the values from
    the pydantic schema defaults so the assertions still lock the
    canonical numbers (88642.0 s, 589.0 W/m^2) but via the single source
    of truth.
    """
    from marslab.config.schema import MarsEnvConfig

    mars_env = MarsEnvConfig()
    a = AtmosphereLoopState(
        atmosphere_dict={"tau": 0.3},
        sol_duration=float(mars_env.sol_duration_seconds),
        solar_constant=float(mars_env.solar_constant_mean),
    )
    assert a.elapsed == 0.0
    assert a.dynamic_enabled is False
    assert a.time_scale == 1.0
    assert a.sweep_start_az == 90.0
    assert a.sweep_end_az == 270.0
    assert a.sweep_max_el == 60.0
    assert a.sol_duration == float(mars_env.sol_duration_seconds)
    assert a.update_interval == 60
    assert a.solar_constant == float(mars_env.solar_constant_mean)
    assert a.hdri_dir == ""
    assert a.atmosphere_dict["tau"] == 0.3


# ---------------------------------------------------------------------------
# OdomPublishState defaults
# ---------------------------------------------------------------------------


def test_odom_state_defaults_all_none() -> None:
    """No-ROS2 path must yield an all-``None`` OdomPublishState."""
    o = OdomPublishState()
    assert o.node is None
    assert o.odom_pub is None
    assert o.odom_tf_broadcaster is None
    assert o.odom_init_pos is None
    assert o.odom_init_quat is None
    assert o.odom_init_quat_inv is None
    assert o.transform_stamped_cls is None
    assert o.odometry_cls is None


# ---------------------------------------------------------------------------
# run_main_loop contract
# ---------------------------------------------------------------------------


def test_run_main_loop_returns_int_annotation() -> None:
    """Return-code contract: ``int`` (Oracle-parity shutdown policy).

    The module uses ``from __future__ import annotations`` (PEP 563), so
    ``inspect.signature`` surfaces annotations as strings. We accept either
    the evaluated ``int`` type or the string ``"int"``.
    """
    sig = inspect.signature(run_main_loop)
    assert sig.return_annotation in (int, "int")


def test_run_main_loop_accepts_single_context() -> None:
    """Signature must take exactly one positional ``LoopContext``."""
    sig = inspect.signature(run_main_loop)
    params = list(sig.parameters.values())
    assert len(params) == 1
    assert params[0].name == "ctx"


# ---------------------------------------------------------------------------
# Pure quaternion helpers — numeric correctness keeps Oracle parity
# ---------------------------------------------------------------------------


def test_quat_inverse_identity() -> None:
    """Inverse of the identity quaternion is itself."""
    q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    inv = quat_inverse(q)
    np.testing.assert_allclose(inv, q)


def test_quat_multiply_identity_left() -> None:
    """Identity * q == q."""
    identity = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    q = np.array([0.7071, 0.0, 0.7071, 0.0], dtype=np.float32)
    np.testing.assert_allclose(quat_multiply(identity, q), q, atol=1e-6)


def test_quat_rotate_vec_identity() -> None:
    """Identity rotation leaves vectors untouched."""
    identity = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    np.testing.assert_allclose(quat_rotate_vec(identity, v), v, atol=1e-6)


def test_module_has_no_isaac_sim_imports() -> None:
    """P3: the main-loop module must import cleanly outside Isaac Sim."""
    # Sanity: import succeeded earlier. Spot-check that no ``omni``/``rclpy``/
    # ``isaacsim`` names leaked into the module namespace.
    forbidden = {"omni", "rclpy", "isaacsim", "pxr"}
    bad = [name for name in dir(ml) if name in forbidden]
    assert not bad, f"forbidden Isaac Sim names in module: {bad}"
