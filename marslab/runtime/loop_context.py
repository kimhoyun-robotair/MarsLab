"""Build the live loop context from typed config and completed runtime phases.

Runtime-only imports occur after SimulationApp boot. The main entrypoint only
passes the live handles and typed phase results to this boundary.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any, Callable

import numpy as np

from marslab.config import MarsLabConfig
from marslab.runtime.assembly import PreResetAssembly
from marslab.runtime.atmosphere_boot import AtmosphereInit
from marslab.runtime.main_loop import ControlState, LoopContext
from marslab.runtime.post_reset import PostResetAssembly


def build_loop_context(
    *,
    simulation_app: Any,
    world: Any,
    stage: Any,
    config: MarsLabConfig,
    atmosphere_init: AtmosphereInit,
    pre_reset: PreResetAssembly,
    post_reset: PostResetAssembly,
) -> LoopContext:
    control_config = config.rover.control
    bridge = post_reset.bridge
    spin_once: Callable[[], None] | None = None
    if bridge is not None:
        rclpy = import_module("rclpy")

        def spin_bridge() -> None:
            rclpy.spin_once(bridge.node, timeout_sec=0.0)

        spin_once = spin_bridge

    update_sun_fn = update_sky_fn = configure_fog_fn = None
    compute_sun_fn = compute_sol_sun_fn = compute_direct_intensity_fn = None
    compute_diffuse_fraction_fn = compute_sky_dome_fn = None
    if config.runtime.atmosphere_enabled:
        sun_renderer = import_module("marslab.rendering.sun_renderer")
        update_sun_fn = sun_renderer.update_sun_light
        update_sky_fn = import_module("marslab.rendering.sky_renderer").update_sky_dome
        configure_fog_fn = import_module(
            "marslab.rendering.atmosphere_fog"
        ).configure_atmosphere_fog
        sun_position = import_module("marslab.environment.sun_position")
        compute_sun_fn = sun_position.compute_sun_position
        compute_sol_sun_fn = sun_position.compute_sol_sun_position
        compute_direct_intensity_fn = import_module(
            "marslab.environment.light_intensity"
        ).compute_direct_intensity
        compute_diffuse_fraction_fn = import_module(
            "marslab.environment.diffuse_fraction"
        ).compute_diffuse_fraction_1d_approx
        compute_sky_dome_fn = import_module("marslab.environment.sky_dome").compute_sky_dome_params

    return LoopContext(
        simulation_app=simulation_app,
        world=world,
        stage=stage,
        articulation=post_reset.articulation,
        imu=pre_reset.sensors.imu,
        drive_indices=post_reset.drive_indices,
        steer_indices=post_reset.steer_indices,
        wheelbase=float(control_config.wheelbase),
        track_steer=float(control_config.track_steer),
        track_middle=float(control_config.track_middle),
        wheel_radius=float(control_config.wheel_radius),
        v_max=float(control_config.max_linear_velocity),
        w_max=float(control_config.max_angular_velocity),
        physics_dt=atmosphere_init.physics_dt,
        negate_steer=control_config.negate_steer,
        debug_logging=control_config.debug_logging,
        max_wheel_accel_rate=float(control_config.max_wheel_accel_rate),
        decel_multiplier=float(control_config.decel_multiplier),
        max_steer_angle=float(control_config.max_steer_angle),
        steer_ramp_rate=float(control_config.steer_ramp_rate),
        control=ControlState(
            current_drive_targets=np.zeros(len(post_reset.drive_indices), dtype=np.float32),
            current_steer_targets=np.zeros(len(post_reset.steer_indices), dtype=np.float32),
            latest_twist=bridge.twist_state if bridge is not None else {"v": 0.0, "w": 0.0},
        ),
        atmosphere=post_reset.atmosphere,
        odom_ctx=bridge.odom_ctx if bridge is not None else None,
        wheel_odom_ctx=bridge.wheel_odom_ctx if bridge is not None else None,
        imu_noise_ctx=bridge.imu_noise_ctx if bridge is not None else None,
        render_config=config.rendering,
        ackermann_fn=import_module("marslab.robots.rover_control").ackermann_command,
        spin_once=spin_once,
        update_sun_fn=update_sun_fn,
        update_sky_fn=update_sky_fn,
        configure_fog_fn=configure_fog_fn,
        compute_sun_fn=compute_sun_fn,
        compute_sol_sun_fn=compute_sol_sun_fn,
        compute_direct_intensity_fn=compute_direct_intensity_fn,
        compute_diffuse_fraction_fn=compute_diffuse_fraction_fn,
        compute_sky_dome_fn=compute_sky_dome_fn,
        atmo_panel_update=(
            post_reset.atmosphere_panel.update_display
            if post_reset.atmosphere_panel is not None
            else None
        ),
    )


__all__ = ["build_loop_context"]
