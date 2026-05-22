"""Factory for assembling :class:`LoopContext` from spawn outputs.

Extracted from ``marslab/main.py`` so the construction is a
single offline-testable function instead of a 23-keyword call inlined
into the entry script.  The dataclass itself lives in
:mod:`marslab.runtime.main_loop` -- keeping the factory separate avoids
a circular import while still presenting a single import-and-call
surface for callers (``marslab.main`` and any future entry
points).

The Isaac Sim handles (``simulation_app``, ``world``, ``stage``,
``articulation``, ``imu``) cannot be exercised offline; the unit test
substitutes :class:`unittest.mock.MagicMock` so the dataclass-assembly
logic itself is verified without an Isaac Sim runtime.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import numpy as np

from marslab.runtime.main_loop import (
    AtmosphereLoopState,
    ControlState,
    LoopContext,
)

if TYPE_CHECKING:
    from marslab.ros2_bridge.context import BridgeContext


def build_loop_context(
    *,
    simulation_app: Any,
    world: Any,
    stage: Any,
    articulation: Any,
    imu: Any,
    drive_indices: List[int],
    steer_indices: List[int],
    control_cfg: Dict[str, Any],
    physics_dt: float,
    atmosphere: AtmosphereLoopState,
    render_config: Any,
    ackermann_fn: Callable[..., Any],
    bridge: Optional["BridgeContext"],
    spin_once: Optional[Callable[..., None]] = None,
    update_sun_fn: Optional[Callable[..., None]] = None,
    update_sky_fn: Optional[Callable[..., None]] = None,
    configure_fog_fn: Optional[Callable[..., None]] = None,
    compute_sun_fn: Optional[Callable[..., Any]] = None,
    compute_sol_sun_fn: Optional[Callable[..., Any]] = None,
    compute_direct_intensity_fn: Optional[Callable[..., float]] = None,
    compute_diffuse_fraction_fn: Optional[Callable[..., float]] = None,
    compute_sky_dome_fn: Optional[Callable[..., Any]] = None,
    atmo_panel_update: Optional[Callable[[], None]] = None,
) -> LoopContext:
    """Assemble a fully populated :class:`LoopContext`.

    Args:
        simulation_app: Isaac Sim ``SimulationApp`` instance.
        world: ``isaacsim.core.api.World`` handle.
        stage: USD stage (typically ``omni.usd.get_context().get_stage()``).
        articulation: ``isaacsim.core.prims.Articulation`` (post-reset).
        imu: IMU sensor handle.
        drive_indices: Drive joint DOF indices (output of
            :func:`marslab.robots.rover.resolve_joint_indices`).
        steer_indices: Steering joint DOF indices.
        control_cfg: ``rover.control`` block from the scenario YAML.
            All ramp / saturation / Ackermann scalar fields are read
            here so callers do not duplicate the ``float(...)`` casts.
        physics_dt: Physics time step (seconds), typically sourced from
            ``AtmosphereInit.physics_dt``.
        atmosphere: Pre-built :class:`AtmosphereLoopState`.
        render_config: Render configuration consumed by atmosphere
            update callbacks.
        ackermann_fn: Ackermann command callable (``v, w, ...``-> joint
            commands).
        bridge: Optional rclpy bridge produced by
            :func:`marslab.ros2_bridge.rclpy_integration.init_rclpy_side`.
            ``None`` disables ROS2 publishing -- both
            :attr:`LoopContext.odom_ctx` and the ``twist_state`` source
            switch over to local stubs.
        spin_once: ``rclpy.spin_once`` adapter the loop drives once per
            tick. Pass ``None`` when ``bridge`` is ``None``.
        update_sun_fn: Renderer hook (sun light push). ``None`` skips
            the call site.
        update_sky_fn: Renderer hook (sky dome push).
        configure_fog_fn: Renderer hook (atmospheric fog).
        compute_sun_fn: Manual-mode sun position resolver.
        compute_sol_sun_fn: Auto-mode sun-sweep resolver.
        compute_direct_intensity_fn: Direct beam irradiance helper.
        compute_diffuse_fraction_fn: Diffuse fraction ``f_d(tau)``.
        compute_sky_dome_fn: Butterscotch HDRI parameter resolver.
        atmo_panel_update: GUI panel refresh hook (``None`` headless).

    Returns:
        A fully-populated :class:`LoopContext`. The ``control`` field is
        constructed in-place with zero-initialised drive / steer ramp
        arrays sized from ``drive_indices`` / ``steer_indices`` and a
        twist source backed by ``bridge.twist_state`` when available.
    """
    twist_state: Dict[str, float] = (
        bridge.twist_state if bridge is not None else {"v": 0.0, "w": 0.0}
    )
    control_state = ControlState(
        current_drive_targets=np.zeros(len(drive_indices), dtype=np.float32),
        current_steer_targets=np.zeros(len(steer_indices), dtype=np.float32),
        latest_twist=twist_state,
    )

    # The six required-positional rover-control scalars below all use
    # ``.get(..., 0.0)`` so the ``--no-rover`` scene-only path (where
    # ``articulation is None``) can pass an empty ``control_cfg`` dict
    # without raising ``KeyError``. The fallbacks are unused in that mode
    # because ``main_loop`` skips the rover-step block when
    # ``ctx.articulation is None``.
    return LoopContext(
        simulation_app=simulation_app,
        world=world,
        stage=stage,
        articulation=articulation,
        imu=imu,
        drive_indices=drive_indices,
        steer_indices=steer_indices,
        wheelbase=float(control_cfg.get("wheelbase", 0.0)),
        track_steer=float(control_cfg.get("track_steer", 0.0)),
        track_middle=float(control_cfg.get("track_middle", 0.0)),
        wheel_radius=float(control_cfg.get("wheel_radius", 0.0)),
        v_max=float(control_cfg.get("max_linear_velocity", 0.0)),
        w_max=float(control_cfg.get("max_angular_velocity", 0.0)),
        physics_dt=physics_dt,
        negate_steer=bool(control_cfg.get("negate_steer", False)),
        debug_logging=bool(control_cfg.get("debug_logging", False)),
        max_wheel_accel_rate=float(control_cfg.get("max_wheel_accel_rate", 0.5)),
        decel_multiplier=float(control_cfg.get("decel_multiplier", 1.0)),
        max_steer_angle=float(control_cfg.get("max_steer_angle", 0.7)),
        steer_ramp_rate=float(control_cfg.get("steer_ramp_rate", 2.0)),
        control=control_state,
        atmosphere=atmosphere,
        odom_ctx=(bridge.odom_ctx if bridge is not None else None),
        render_config=render_config,
        ackermann_fn=ackermann_fn,
        spin_once=spin_once,
        update_sun_fn=update_sun_fn,
        update_sky_fn=update_sky_fn,
        configure_fog_fn=configure_fog_fn,
        compute_sun_fn=compute_sun_fn,
        compute_sol_sun_fn=compute_sol_sun_fn,
        compute_direct_intensity_fn=compute_direct_intensity_fn,
        compute_diffuse_fraction_fn=compute_diffuse_fraction_fn,
        compute_sky_dome_fn=compute_sky_dome_fn,
        atmo_panel_update=atmo_panel_update,
    )


__all__ = ["build_loop_context"]
