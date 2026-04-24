"""Main-loop extraction for the monolithic Stage 3 runtime (R6-1).

Public entry point :func:`run_main_loop` consumes a :class:`LoopContext`
bundling every object and scalar the legacy inline loop closed over. Mutable
ramp / atmosphere state is carried in :class:`ControlState` /
:class:`AtmosphereLoopState` / :class:`OdomPublishState` (mutated in place for
Oracle byte-exact parity). Isaac Sim / ``rclpy`` symbols enter via the
context only — the module itself is offline-importable (P3). Normal exit or
``KeyboardInterrupt`` returns ``0``; the caller owns ``simulation_app.close()``.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from marslab.math.quaternion import quat_inverse, quat_multiply, quat_rotate_vec

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State dataclasses — mutated in place by the loop body.
# ---------------------------------------------------------------------------


@dataclass
class ControlState:
    """Drive / steer ramp state mutated per physics step.

    Attributes:
        current_drive_targets: Per-wheel commanded drive velocity after ramp
            limiting. Shape ``(n_drive,)`` float32.
        current_steer_targets: Per-wheel commanded steer angle after ramp
            limiting. Shape ``(n_steer,)`` float32.
        step_count: Monotonic physics-step counter (also used as a simple
            debug-log stride).
        latest_twist: Most recent ``(v, w)`` values seen on ``cmd_vel``.
            Keys ``"v"`` and ``"w"`` — kept as a dict for Oracle parity.
    """

    current_drive_targets: np.ndarray
    current_steer_targets: np.ndarray
    step_count: int = 0
    latest_twist: Dict[str, float] = field(default_factory=lambda: {"v": 0.0, "w": 0.0})


@dataclass
class AtmosphereLoopState:
    """Dynamic atmosphere + HDRI carry-over state.

    Mirrors the fields the inline ``atmosphere_state`` dict exposed so the
    GUI ``AtmospherePanel`` can keep reading/writing via
    :attr:`atmosphere_dict`.  The dict is the authoritative store; the other
    attributes are scalars the loop carries across steps.

    P6 G5 (2026-04-23): ``sol_duration`` and ``solar_constant`` previously
    defaulted to the Mars physics constants (``88642.0`` s and
    ``589.0`` W/m^2). That duplicated values already owned by
    :class:`marslab.config.schema.MarsEnvConfig`. Both are now required
    constructor arguments — callers must source them from the pydantic
    schema (see ``run_stage3_monolithic_new.py``).

    Attributes:
        atmosphere_dict: The live mutable dict shared with the GUI panel.
            Keys: ``tau``, ``sun_mode``, ``sun_azimuth_deg``,
            ``sun_elevation_deg``, ``time_of_sol``, ``direct_intensity``,
            ``diffuse_fraction``.
        sol_duration: Length of one Mars sol (seconds). Required —
            canonical value in ``MarsEnvConfig.sol_duration_seconds``.
        solar_constant: TOA solar constant ``S0`` (W/m^2). Required —
            canonical value in ``MarsEnvConfig.solar_constant_mean``.
        elapsed: Accumulated simulated sol-seconds used for the auto sweep.
        dynamic_enabled: Mirrors ``DynamicAtmosphereConfig.enabled``.
        time_scale: Sol-time acceleration factor.
        sweep_start_az: Auto-sweep azimuth start (deg).
        sweep_end_az: Auto-sweep azimuth end (deg).
        sweep_max_el: Auto-sweep peak elevation (deg).
        update_interval: Physics-steps between atmosphere refreshes.
        hdri_dir: Absolute path to the sky HDRI directory.
    """

    atmosphere_dict: Dict[str, Any]
    sol_duration: float
    solar_constant: float
    elapsed: float = 0.0
    dynamic_enabled: bool = False
    time_scale: float = 1.0
    sweep_start_az: float = 90.0
    sweep_end_az: float = 270.0
    sweep_max_el: float = 60.0
    update_interval: int = 60
    hdri_dir: str = ""


@dataclass
class OdomPublishState:
    """``rclpy`` publisher + TF broadcaster handles for manual odometry.

    All fields are ``Optional`` so the loop can short-circuit cleanly when
    ``--no-ros2`` was supplied.

    Attributes:
        node: ``rclpy.node.Node`` instance (or ``None``).
        odom_pub: ``nav_msgs/Odometry`` publisher.
        odom_tf_broadcaster: ``tf2_ros.TransformBroadcaster`` for
            ``odom → base_link``.
        odom_init_pos: Rover position at ``world.reset()`` — the odom origin.
        odom_init_quat: Rover orientation at ``world.reset()``.
        odom_init_quat_inv: Pre-computed inverse of the init quaternion.
        transform_stamped_cls: ``geometry_msgs/TransformStamped`` class.
        odometry_cls: ``nav_msgs/Odometry`` class.
    """

    node: Optional[Any] = None
    odom_pub: Optional[Any] = None
    odom_tf_broadcaster: Optional[Any] = None
    odom_init_pos: Optional[np.ndarray] = None
    odom_init_quat: Optional[np.ndarray] = None
    odom_init_quat_inv: Optional[np.ndarray] = None
    transform_stamped_cls: Optional[Any] = None
    odometry_cls: Optional[Any] = None


@dataclass
class LoopContext:
    """Everything :func:`run_main_loop` reads or mutates.

    Grouped by lifecycle:

    *   Isaac Sim singletons: ``simulation_app``, ``world``, ``stage``.
    *   Robot handles: ``articulation``, ``imu``.
    *   Joint index arrays: ``drive_indices``, ``steer_indices``.
    *   Vehicle geometry & control limits: ``wheelbase``, ``track_steer``,
        ``track_middle``, ``wheel_radius``, ``v_max``, ``w_max``, ramp rates.
    *   Physics tick: ``physics_dt``.
    *   Mutable state: ``control``, ``atmosphere``, ``odom``.
    *   Callables: ``ackermann_fn``, ``spin_once``, ``update_sun_fn``,
        ``update_sky_fn``, ``configure_fog_fn``, ``compute_sun_fn``,
        ``compute_sol_sun_fn``, ``compute_direct_intensity_fn``,
        ``compute_diffuse_fraction_fn``, ``compute_sky_dome_fn``,
        ``atmo_panel_update``.
    """

    simulation_app: Any
    world: Any
    stage: Any
    articulation: Any
    imu: Any
    drive_indices: List[int]
    steer_indices: List[int]
    wheelbase: float
    track_steer: float
    track_middle: float
    wheel_radius: float
    v_max: float
    w_max: float
    physics_dt: float
    negate_steer: bool
    debug_logging: bool
    max_wheel_accel_rate: float
    decel_multiplier: float
    max_steer_angle: float
    steer_ramp_rate: float
    control: ControlState
    atmosphere: AtmosphereLoopState
    odom: OdomPublishState
    render_config: Any
    ackermann_fn: Callable[..., Any]
    spin_once: Optional[Callable[..., None]] = None
    update_sun_fn: Optional[Callable[..., None]] = None
    update_sky_fn: Optional[Callable[..., None]] = None
    configure_fog_fn: Optional[Callable[..., None]] = None
    compute_sun_fn: Optional[Callable[..., Any]] = None
    compute_sol_sun_fn: Optional[Callable[..., Any]] = None
    compute_direct_intensity_fn: Optional[Callable[..., float]] = None
    compute_diffuse_fraction_fn: Optional[Callable[..., float]] = None
    compute_sky_dome_fn: Optional[Callable[..., Any]] = None
    atmo_panel_update: Optional[Callable[[], None]] = None


# ---------------------------------------------------------------------------
# Main loop.
# ---------------------------------------------------------------------------


def _apply_ramp(
    command: np.ndarray,
    current: np.ndarray,
    per_step_limit: float,
    decel_multiplier: float,
    ramp_enabled: bool,
) -> np.ndarray:
    """Shared drive-ramp kernel.

    Args:
        command: Target wheel velocities (rad/s).
        current: Last ramped targets, updated in place and returned.
        per_step_limit: Max per-tick change while accelerating.
        decel_multiplier: Multiplier applied when decelerating (``|target| <
            |current|``).
        ramp_enabled: If ``False``, the command passes through unchanged.

    Returns:
        Updated ``current`` array (same object as the input for in-place
        tracking).
    """
    if not ramp_enabled:
        current[...] = command
        return current
    delta = command - current
    is_decel = np.abs(command) < np.abs(current)
    step_lim = np.where(is_decel, per_step_limit * decel_multiplier, per_step_limit)
    delta = np.clip(delta, -step_lim, step_lim)
    current[...] = current + delta
    return current


def build_atmosphere_loop_state(
    atmo_init: Any,
    tau: float,
) -> AtmosphereLoopState:
    """Factory: derive :class:`AtmosphereLoopState` from a boot snapshot.

    Collapses the boilerplate Stage-3 callers used to write inline to
    wire every ``DynamicAtmosphereConfig`` + ``StageTwoAtmosphereInit``
    field into a mutable loop state.  Keeps
    ``scripts/phase1/run_stage4.py`` focused on Stage-3 orchestration.

    Args:
        atmo_init: :class:`marslab.runtime.stage2_boot.StageTwoAtmosphereInit`
            produced by :func:`run_stage2_boot`.
        tau: Initial dust optical depth value (mirrored into the live
            ``atmosphere_dict`` so the GUI panel sees it on startup).

    Returns:
        Fully populated :class:`AtmosphereLoopState` ready to pass into
        a :class:`LoopContext`.
    """
    dyn = atmo_init.dynamic
    # Parity with ``marslab.runtime.stage2_loop.build_atmosphere_state``:
    # ``sol_duration_seconds`` is required by ``AtmospherePanel._format_mode_status``
    # when the panel is toggled to Auto mode. Dropping it here caused a KeyError
    # inside the GUI callback the first time the user clicked the Sun mode
    # button on ``run_stage4.py``.
    atmosphere_dict: Dict[str, Any] = {
        "tau": tau,
        "sun_mode": "auto" if dyn.enabled else "manual",
        "sun_azimuth_deg": float(atmo_init.sun_azimuth_deg),
        "sun_elevation_deg": float(atmo_init.sun_elevation_deg),
        "time_of_sol": 0.0,
        "direct_intensity": atmo_init.direct_intensity,
        "diffuse_fraction": atmo_init.diffuse_fraction,
        "sol_duration_seconds": atmo_init.sol_duration_seconds,
    }
    return AtmosphereLoopState(
        atmosphere_dict=atmosphere_dict,
        sol_duration=atmo_init.sol_duration_seconds,
        solar_constant=atmo_init.solar_constant,
        dynamic_enabled=dyn.enabled,
        time_scale=dyn.time_scale,
        sweep_start_az=dyn.sun_sweep.start_azimuth_deg,
        sweep_end_az=dyn.sun_sweep.end_azimuth_deg,
        sweep_max_el=dyn.sun_sweep.max_elevation_deg,
        update_interval=dyn.update_interval_frames,
        hdri_dir=atmo_init.hdri_dir,
    )


def run_main_loop(ctx: LoopContext) -> int:
    """Drive the Stage 3 monolithic runtime until the sim stops.

    Args:
        ctx: Pre-initialized :class:`LoopContext` assembled by the CLI
            wrapper (``scripts/run_marslab.py``) or the twin monolithic
            runner after Isaac Sim boot and ``world.reset()``.

    Returns:
        ``0`` on normal exit or ``KeyboardInterrupt``. The caller owns the
        ``simulation_app.close()`` call.

    Raises:
        Exception: Any exception other than :class:`KeyboardInterrupt`
            raised outside the per-step ``try`` blocks. The caller's
            ``finally`` is expected to tear Isaac Sim down.
    """
    ctl = ctx.control
    atmo = ctx.atmosphere
    odom = ctx.odom

    drive_idx_arr = np.asarray(ctx.drive_indices, dtype=np.int32)
    steer_idx_arr = np.asarray(ctx.steer_indices, dtype=np.int32)

    per_step_limit = ctx.max_wheel_accel_rate * ctx.physics_dt
    steer_per_step_limit = ctx.steer_ramp_rate * ctx.physics_dt
    drive_ramp_enabled = ctx.max_wheel_accel_rate > 0
    steer_ramp_enabled = ctx.steer_ramp_rate > 0

    try:
        while ctx.simulation_app.is_running():
            if ctx.spin_once is not None:
                ctx.spin_once()

            v_raw = ctl.latest_twist["v"]
            w_raw = ctl.latest_twist["w"]
            v = float(np.clip(v_raw, -ctx.v_max, ctx.v_max))
            w = float(np.clip(w_raw, -ctx.w_max, ctx.w_max))

            steer_angles, wheel_vels = ctx.ackermann_fn(
                v,
                w,
                ctx.wheelbase,
                ctx.track_steer,
                ctx.track_middle,
                ctx.wheel_radius,
            )
            if ctx.negate_steer:
                steer_angles = -steer_angles

            steer_angles = np.clip(steer_angles, -ctx.max_steer_angle, ctx.max_steer_angle)

            if steer_ramp_enabled:
                s_delta = steer_angles - ctl.current_steer_targets
                s_delta = np.clip(s_delta, -steer_per_step_limit, steer_per_step_limit)
                ctl.current_steer_targets = ctl.current_steer_targets + s_delta
                ramped_steer = ctl.current_steer_targets
            else:
                ramped_steer = steer_angles

            ramped_vels = _apply_ramp(
                wheel_vels,
                ctl.current_drive_targets,
                per_step_limit,
                ctx.decel_multiplier,
                drive_ramp_enabled,
            )

            try:
                ctx.articulation.set_joint_position_targets(
                    ramped_steer, joint_indices=steer_idx_arr
                )
                ctx.articulation.set_joint_velocity_targets(
                    ramped_vels, joint_indices=drive_idx_arr
                )
            except Exception as exc:  # noqa: BLE001
                print(
                    f"[run_main_loop] joint target failed: {exc}",
                    file=sys.stderr,
                )

            if ctx.debug_logging and ctl.step_count % 60 == 0:
                _debug_log_step(ctx, steer_idx_arr, drive_idx_arr, v, w, steer_angles, ramped_vels)

            if odom.node is not None and odom.odom_pub is not None:
                _publish_odometry(ctx, ctl.step_count)

            if ctl.step_count % atmo.update_interval == 0 and ctl.step_count > 0:
                _update_atmosphere(ctx)

            ctl.step_count += 1
            ctx.world.step(render=True)
    except KeyboardInterrupt:
        print("[run_main_loop] KeyboardInterrupt -- shutting down.", flush=True)

    return 0


def _debug_log_step(
    ctx: LoopContext,
    steer_idx_arr: np.ndarray,
    drive_idx_arr: np.ndarray,
    v: float,
    w: float,
    steer_angles: np.ndarray,
    ramped_vels: np.ndarray,
) -> None:
    """Emit per-stride diagnostic lines, mirroring the Oracle output."""
    try:
        actual_pos = ctx.articulation.get_joint_positions()
        actual_vel = ctx.articulation.get_joint_velocities()
        if actual_pos is not None and actual_vel is not None:
            s_pos = (
                actual_pos[0, steer_idx_arr] if actual_pos.ndim == 2 else actual_pos[steer_idx_arr]
            )
            d_vel = (
                actual_vel[0, drive_idx_arr] if actual_vel.ndim == 2 else actual_vel[drive_idx_arr]
            )
            print(
                f"[DIAG {ctx.control.step_count}] twist=({v:.3f},{w:.3f}) "
                f"steer_cmd={steer_angles} steer_act={s_pos} "
                f"drive_cmd={ramped_vels} drive_act={d_vel}",
                flush=True,
            )
    except Exception as exc:  # noqa: BLE001
        if ctx.control.step_count < 120:
            print(
                f"[warn] articulation step={ctx.control.step_count} {repr(exc)[:200]}",
                file=sys.stderr,
            )
    try:
        imu_frame = ctx.imu.get_current_frame()
        if imu_frame is not None and "lin_acc" in imu_frame:
            la = imu_frame["lin_acc"]
            print(
                f"[DIAG {ctx.control.step_count}] imu_acc="
                f"({la[0]:.4f},{la[1]:.4f},{la[2]:.4f})",
                flush=True,
            )
    except Exception as exc:  # noqa: BLE001
        if ctx.control.step_count < 120:
            print(
                f"[warn] imu step={ctx.control.step_count} {repr(exc)[:200]}",
                file=sys.stderr,
            )


def _publish_odometry(ctx: LoopContext, step_count: int) -> None:
    """Publish ``odom → base_link`` TF and an ``Odometry`` message."""
    odom = ctx.odom
    try:
        rover_poses_odom = ctx.articulation.get_world_poses()
        if rover_poses_odom is None:
            return
        _rp, _rq = rover_poses_odom
        cur_pos = _rp[0] if _rp.ndim == 2 else _rp
        cur_quat = _rq[0] if _rq.ndim == 2 else _rq

        delta_pos_world = cur_pos - odom.odom_init_pos
        delta_pos_odom = quat_rotate_vec(odom.odom_init_quat_inv, delta_pos_world)
        delta_quat = quat_multiply(odom.odom_init_quat_inv, cur_quat)

        now = odom.node.get_clock().now().to_msg()

        odom_tf = odom.transform_stamped_cls()
        odom_tf.header.stamp = now
        odom_tf.header.frame_id = "odom"
        odom_tf.child_frame_id = "base_link"
        odom_tf.transform.translation.x = float(delta_pos_odom[0])
        odom_tf.transform.translation.y = float(delta_pos_odom[1])
        odom_tf.transform.translation.z = float(delta_pos_odom[2])
        odom_tf.transform.rotation.w = float(delta_quat[0])
        odom_tf.transform.rotation.x = float(delta_quat[1])
        odom_tf.transform.rotation.y = float(delta_quat[2])
        odom_tf.transform.rotation.z = float(delta_quat[3])
        odom.odom_tf_broadcaster.sendTransform(odom_tf)

        odom_msg = odom.odometry_cls()
        odom_msg.header.stamp = now
        odom_msg.header.frame_id = "odom"
        odom_msg.child_frame_id = "base_link"
        odom_msg.pose.pose.position.x = float(delta_pos_odom[0])
        odom_msg.pose.pose.position.y = float(delta_pos_odom[1])
        odom_msg.pose.pose.position.z = float(delta_pos_odom[2])
        odom_msg.pose.pose.orientation.w = float(delta_quat[0])
        odom_msg.pose.pose.orientation.x = float(delta_quat[1])
        odom_msg.pose.pose.orientation.y = float(delta_quat[2])
        odom_msg.pose.pose.orientation.z = float(delta_quat[3])

        try:
            lin_vel = ctx.articulation.get_linear_velocities()
            ang_vel = ctx.articulation.get_angular_velocities()
            if lin_vel is not None and ang_vel is not None:
                lv = lin_vel[0] if lin_vel.ndim == 2 else lin_vel
                av = ang_vel[0] if ang_vel.ndim == 2 else ang_vel
                cur_quat_inv = quat_inverse(cur_quat)
                body_lv = quat_rotate_vec(cur_quat_inv, lv)
                body_av = quat_rotate_vec(cur_quat_inv, av)
                odom_msg.twist.twist.linear.x = float(body_lv[0])
                odom_msg.twist.twist.linear.y = float(body_lv[1])
                odom_msg.twist.twist.linear.z = float(body_lv[2])
                odom_msg.twist.twist.angular.x = float(body_av[0])
                odom_msg.twist.twist.angular.y = float(body_av[1])
                odom_msg.twist.twist.angular.z = float(body_av[2])
        except Exception as exc:  # noqa: BLE001
            logger.error("velocity query failed at step=%d: %r", step_count, exc)
            if step_count < 120:
                print(
                    f"[warn] velocity step={step_count} {repr(exc)[:200]}",
                    file=sys.stderr,
                )

        odom.odom_pub.publish(odom_msg)
    except Exception as odom_exc:  # noqa: BLE001
        logger.error("odom publish failed at step=%d: %r", step_count, odom_exc)
        if step_count < 120:
            print(
                f"[run_main_loop] odom publish failed: {odom_exc}",
                file=sys.stderr,
            )


def _update_atmosphere(ctx: LoopContext) -> None:
    """Step the dynamic atmosphere sweep and push updates into the stage."""
    atmo = ctx.atmosphere
    state = atmo.atmosphere_dict
    current_tau = state["tau"]
    dyn_sun_pos = None

    if state["sun_mode"] == "auto" and atmo.dynamic_enabled:
        atmo.elapsed += ctx.physics_dt * atmo.update_interval * atmo.time_scale
        t = (atmo.elapsed % atmo.sol_duration) / atmo.sol_duration
        state["time_of_sol"] = t
        if ctx.compute_sol_sun_fn is not None:
            dyn_sun_pos = ctx.compute_sol_sun_fn(
                time_of_sol_fraction=t,
                start_azimuth_deg=atmo.sweep_start_az,
                end_azimuth_deg=atmo.sweep_end_az,
                max_elevation_deg=atmo.sweep_max_el,
            )
            state["sun_azimuth_deg"] = dyn_sun_pos.azimuth_deg
            state["sun_elevation_deg"] = dyn_sun_pos.elevation_deg
    elif state["sun_mode"] == "manual" and ctx.compute_sun_fn is not None:
        dyn_sun_pos = ctx.compute_sun_fn(
            azimuth_deg=state["sun_azimuth_deg"],
            elevation_deg=max(0.5, min(89.5, state["sun_elevation_deg"])),
        )

    if dyn_sun_pos is None:
        return

    if (
        ctx.compute_direct_intensity_fn is None
        or ctx.compute_diffuse_fraction_fn is None
        or ctx.compute_sky_dome_fn is None
    ):
        return

    dyn_intensity = ctx.compute_direct_intensity_fn(
        atmo.solar_constant, current_tau, dyn_sun_pos.zenith_angle_rad
    )
    dyn_diffuse = ctx.compute_diffuse_fraction_fn(current_tau)
    dyn_sky = ctx.compute_sky_dome_fn(current_tau, atmo.hdri_dir)

    state["direct_intensity"] = dyn_intensity
    state["diffuse_fraction"] = dyn_diffuse

    if ctx.update_sun_fn is not None:
        ctx.update_sun_fn(ctx.stage, dyn_sun_pos, dyn_intensity, dyn_diffuse, ctx.render_config)
    if ctx.update_sky_fn is not None:
        ctx.update_sky_fn(ctx.stage, dyn_sky, dyn_diffuse, ctx.render_config)
    if ctx.configure_fog_fn is not None:
        ctx.configure_fog_fn(ctx.stage, current_tau, ctx.render_config)
    if ctx.atmo_panel_update is not None:
        ctx.atmo_panel_update()
