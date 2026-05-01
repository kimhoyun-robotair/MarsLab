"""Offline-first unit tests for the marslab.runtime.main_loop facade."""

from __future__ import annotations

import inspect
from dataclasses import fields

import numpy as np

from marslab.quaternion import quat_inverse, quat_multiply, quat_rotate_vec
from marslab.runtime import main_loop as ml
from marslab.runtime.main_loop import (
    AtmosphereLoopState,
    ControlState,
    LoopContext,
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
        "odom_ctx",
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

    ``sol_duration`` and ``solar_constant`` are required: Mars physics
    defaults were removed from the dataclass to stop duplicating
    ``MarsEnvConfig``. This test sources the values from the pydantic
    schema defaults so the assertions still lock the canonical numbers
    (88642.0 s, 589.0 W/m^2) but via the single source of truth.
    """
    from marslab.config.schema import MarsEnvConfig

    mars_env = MarsEnvConfig()
    a = AtmosphereLoopState(
        atmosphere_dict={"tau": 0.3},
        sol_duration=float(mars_env.sol_duration_seconds),
        solar_constant=float(mars_env.solar_constant),
    )
    assert a.elapsed == 0.0
    assert a.dynamic_enabled is False
    assert a.time_scale == 1.0
    assert a.sweep_start_az == 90.0
    assert a.sweep_end_az == 270.0
    assert a.sweep_max_el == 60.0
    assert a.sol_duration == float(mars_env.sol_duration_seconds)
    assert a.update_interval == 60
    assert a.solar_constant == float(mars_env.solar_constant)
    assert a.hdri_dir == ""
    assert a.atmosphere_dict["tau"] == 0.3


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


# ---------------------------------------------------------------------------
# LoopContext god-object decomposition regression
# ---------------------------------------------------------------------------


def _make_minimal_ctx() -> LoopContext:
    """Build a LoopContext populated with stand-in values for property tests."""

    def _ackermann(*_args, **_kwargs):  # pragma: no cover - not invoked
        return np.zeros(4), np.zeros(6)

    return LoopContext(
        simulation_app=object(),
        world=object(),
        stage=object(),
        articulation=object(),
        imu=object(),
        drive_indices=[0, 1, 2, 3, 4, 5],
        steer_indices=[6, 7, 8, 9],
        wheelbase=1.23,
        track_steer=0.98,
        track_middle=1.05,
        wheel_radius=0.26,
        v_max=1.5,
        w_max=1.2,
        physics_dt=1.0 / 60.0,
        negate_steer=True,
        debug_logging=False,
        max_wheel_accel_rate=0.4,
        decel_multiplier=0.9,
        max_steer_angle=0.7,
        steer_ramp_rate=2.1,
        control=ControlState(
            current_drive_targets=np.zeros(6, dtype=np.float32),
            current_steer_targets=np.zeros(4, dtype=np.float32),
        ),
        atmosphere=AtmosphereLoopState(
            atmosphere_dict={"tau": 0.3},
            sol_duration=88642.0,
            solar_constant=589.0,
        ),
        odom_ctx=None,
        render_config=object(),
        ackermann_fn=_ackermann,
    )


def test_loop_context_geometry_view() -> None:
    """``ctx.geometry`` is a :class:`VehicleGeometry` re-export.

    Values must round-trip from the flat fields so legacy callers
    (``ctx.wheelbase``) stay bit-equal to the decomposed view
    (``ctx.geometry.wheelbase``).
    """
    from marslab.runtime.main_loop import VehicleGeometry

    ctx = _make_minimal_ctx()
    geom = ctx.geometry
    assert isinstance(geom, VehicleGeometry)
    assert geom.wheelbase == ctx.wheelbase
    assert geom.track_steer == ctx.track_steer
    assert geom.track_middle == ctx.track_middle
    assert geom.wheel_radius == ctx.wheel_radius


def test_loop_context_control_limits_view() -> None:
    """``ctx.control_limits`` is a :class:`ControlLimits` re-export."""
    from marslab.runtime.main_loop import ControlLimits

    ctx = _make_minimal_ctx()
    lim = ctx.control_limits
    assert isinstance(lim, ControlLimits)
    assert lim.v_max == ctx.v_max
    assert lim.w_max == ctx.w_max
    assert lim.max_wheel_accel_rate == ctx.max_wheel_accel_rate
    assert lim.decel_multiplier == ctx.decel_multiplier
    assert lim.max_steer_angle == ctx.max_steer_angle
    assert lim.steer_ramp_rate == ctx.steer_ramp_rate
    assert lim.negate_steer == ctx.negate_steer


def test_loop_context_atmosphere_callables_view() -> None:
    """``ctx.atmosphere_callables`` collects the 9 optional hooks."""
    from marslab.runtime.main_loop import AtmosphereCallables

    ctx = _make_minimal_ctx()
    hooks = ctx.atmosphere_callables
    assert isinstance(hooks, AtmosphereCallables)
    # All default to None for the minimal context.
    for field_name in (
        "update_sun_fn",
        "update_sky_fn",
        "configure_fog_fn",
        "compute_sun_fn",
        "compute_sol_sun_fn",
        "compute_direct_intensity_fn",
        "compute_diffuse_fraction_fn",
        "compute_sky_dome_fn",
        "atmo_panel_update",
    ):
        assert getattr(hooks, field_name) is None


def test_loop_context_legacy_flat_access_still_works() -> None:
    """Back-compat: flat attributes remain accessible on LoopContext.

    The decomposition must not break existing callers that read
    ``ctx.wheel_radius`` / ``ctx.wheelbase`` / ``ctx.v_max`` directly
    (notably ``marslab/main.py`` and every byte-identity md5
    pin in the test suite).
    """
    ctx = _make_minimal_ctx()
    # Spot-check representative fields from each logical cluster.
    assert ctx.wheel_radius == 0.26
    assert ctx.v_max == 1.5
    assert ctx.negate_steer is True
    assert ctx.update_sun_fn is None
