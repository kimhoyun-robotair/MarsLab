"""Offline unit tests for ``marslab.runtime.loop_context.build_loop_context``.

Isaac Sim handles are substituted with :class:`unittest.mock.MagicMock`
so the dataclass-assembly logic itself is exercised without an Isaac
Sim runtime.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from marslab.runtime.loop_context import build_loop_context
from marslab.runtime.main_loop import AtmosphereLoopState, LoopContext


def _make_atmosphere_state() -> AtmosphereLoopState:
    return AtmosphereLoopState(
        atmosphere_dict={"tau": 0.5},
        sol_duration=88642.0,
        solar_constant=589.0,
    )


def _full_control_cfg() -> dict:
    return {
        "wheelbase": 2.7,
        "track_steer": 1.5,
        "track_middle": 1.5,
        "wheel_radius": 0.265,
        "max_linear_velocity": 0.5,
        "max_angular_velocity": 0.4,
        "negate_steer": True,
        "debug_logging": False,
        "max_wheel_accel_rate": 1.0,
        "decel_multiplier": 2.0,
        "max_steer_angle": 0.6,
        "steer_ramp_rate": 1.5,
    }


def _build_minimal(**overrides) -> LoopContext:
    """Helper: build a LoopContext with all required fields stubbed."""
    base = dict(
        simulation_app=MagicMock(),
        world=MagicMock(),
        stage=MagicMock(),
        articulation=MagicMock(),
        imu=MagicMock(),
        drive_indices=[0, 1, 2, 3, 4, 5],
        steer_indices=[6, 7, 8, 9],
        control_cfg=_full_control_cfg(),
        physics_dt=1.0 / 60.0,
        atmosphere=_make_atmosphere_state(),
        render_config=MagicMock(),
        ackermann_fn=lambda *args, **kwargs: (np.zeros(4), np.zeros(6)),
        bridge=None,
    )
    base.update(overrides)
    return build_loop_context(**base)


def test_build_loop_context_populates_all_fields() -> None:
    """All declared LoopContext fields are populated from the inputs."""
    ctx = _build_minimal()

    # Vehicle geometry ------------------------------------------------------
    assert ctx.wheelbase == 2.7
    assert ctx.track_steer == 1.5
    assert ctx.track_middle == 1.5
    assert ctx.wheel_radius == 0.265

    # Limits ----------------------------------------------------------------
    assert ctx.v_max == 0.5
    assert ctx.w_max == 0.4
    assert ctx.max_wheel_accel_rate == 1.0
    assert ctx.decel_multiplier == 2.0
    assert ctx.max_steer_angle == 0.6
    assert ctx.steer_ramp_rate == 1.5
    assert ctx.negate_steer is True
    assert ctx.debug_logging is False

    # State -----------------------------------------------------------------
    assert ctx.control.current_drive_targets.shape == (6,)
    assert ctx.control.current_steer_targets.shape == (4,)
    assert ctx.control.latest_twist == {"v": 0.0, "w": 0.0}
    assert ctx.atmosphere.atmosphere_dict["tau"] == 0.5
    assert ctx.physics_dt == 1.0 / 60.0


def test_build_loop_context_without_bridge_disables_odom_ctx() -> None:
    """``bridge=None`` -> ``odom_ctx is None`` and twist comes from a stub."""
    ctx = _build_minimal(bridge=None)
    assert ctx.odom_ctx is None
    assert ctx.control.latest_twist == {"v": 0.0, "w": 0.0}


def test_build_loop_context_with_bridge_wires_odom_and_twist() -> None:
    """``bridge`` argument forwards ``odom_ctx`` + shares ``twist_state``."""
    twist = {"v": 1.0, "w": 0.25}
    bridge = SimpleNamespace(odom_ctx=MagicMock(), twist_state=twist)
    ctx = _build_minimal(bridge=bridge)
    assert ctx.odom_ctx is bridge.odom_ctx
    assert ctx.control.latest_twist is twist


def test_build_loop_context_default_optional_fields() -> None:
    """Optional callable fields default to ``None`` when not supplied."""
    ctx = _build_minimal()
    assert ctx.spin_once is None
    assert ctx.update_sun_fn is None
    assert ctx.update_sky_fn is None
    assert ctx.configure_fog_fn is None
    assert ctx.compute_sun_fn is None
    assert ctx.compute_sol_sun_fn is None
    assert ctx.compute_direct_intensity_fn is None
    assert ctx.compute_diffuse_fraction_fn is None
    assert ctx.compute_sky_dome_fn is None
    assert ctx.atmo_panel_update is None


def test_build_loop_context_populates_optional_callables() -> None:
    """Every optional callable lands on the matching context attribute."""
    fn_spin = MagicMock()
    fn_sun = MagicMock()
    fn_sky = MagicMock()
    fn_fog = MagicMock()
    fn_compute_sun = MagicMock()
    fn_compute_sol = MagicMock()
    fn_direct = MagicMock()
    fn_diffuse = MagicMock()
    fn_sky_dome = MagicMock()
    fn_panel = MagicMock()

    ctx = _build_minimal(
        spin_once=fn_spin,
        update_sun_fn=fn_sun,
        update_sky_fn=fn_sky,
        configure_fog_fn=fn_fog,
        compute_sun_fn=fn_compute_sun,
        compute_sol_sun_fn=fn_compute_sol,
        compute_direct_intensity_fn=fn_direct,
        compute_diffuse_fraction_fn=fn_diffuse,
        compute_sky_dome_fn=fn_sky_dome,
        atmo_panel_update=fn_panel,
    )
    assert ctx.spin_once is fn_spin
    assert ctx.update_sun_fn is fn_sun
    assert ctx.update_sky_fn is fn_sky
    assert ctx.configure_fog_fn is fn_fog
    assert ctx.compute_sun_fn is fn_compute_sun
    assert ctx.compute_sol_sun_fn is fn_compute_sol
    assert ctx.compute_direct_intensity_fn is fn_direct
    assert ctx.compute_diffuse_fraction_fn is fn_diffuse
    assert ctx.compute_sky_dome_fn is fn_sky_dome
    assert ctx.atmo_panel_update is fn_panel


def test_build_loop_context_publish_odom_tf_independence() -> None:
    """The factory does not consult ``publish_odom_tf`` -- bridge owns it.

    The ``odom_ctx`` returned to the loop is whatever
    :func:`init_rclpy_side` produced; the loop context factory only
    forwards the reference.  Verified by passing two distinct mock
    bridges and asserting both flow through unchanged.
    """
    bridge_a = SimpleNamespace(odom_ctx=MagicMock(name="odom_a"), twist_state={"v": 0.0, "w": 0.0})
    bridge_b = SimpleNamespace(odom_ctx=None, twist_state={"v": 0.0, "w": 0.0})
    ctx_a = _build_minimal(bridge=bridge_a)
    ctx_b = _build_minimal(bridge=bridge_b)
    assert ctx_a.odom_ctx is bridge_a.odom_ctx
    assert ctx_b.odom_ctx is None


def test_build_loop_context_indices_are_forwarded() -> None:
    """Drive/steer index lists land on the context unmodified."""
    ctx = _build_minimal(drive_indices=[10, 11, 12], steer_indices=[20, 21])
    assert ctx.drive_indices == [10, 11, 12]
    assert ctx.steer_indices == [20, 21]
    assert ctx.control.current_drive_targets.shape == (3,)
    assert ctx.control.current_steer_targets.shape == (2,)
