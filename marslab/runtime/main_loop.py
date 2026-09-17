"""Run the stateful simulation tick loop.
Control, odometry, sensors, atmosphere, and diagnostics share one context.
The loop remains importable without Isaac or ROS bindings."""

from __future__ import annotations

import logging
import math
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Literal, Optional

import numpy as np

from marslab.robots.rover_control import constrain_ackermann_twist

if TYPE_CHECKING:
    from marslab.ros2_bridge.depth_publisher import DepthPublisher
    from marslab.ros2_bridge.imu_noise_publisher import ImuNoiseContext
    from marslab.ros2_bridge.lidar_scan_publisher import LidarScanPublisher
    from marslab.ros2_bridge.odometry_publisher import GroundTruthPosePublisherContext
    from marslab.ros2_bridge.wheel_odometry_publisher import WheelOdometryContext
    from marslab.sensors.imu_spawner import IMUSample

logger = logging.getLogger(__name__)
_STEERING_STOP_WINDOW_SECONDS = 0.2


@dataclass
class ControlState:
    """Drive / steer ramp state mutated per physics step."""

    current_drive_targets: np.ndarray
    current_steer_targets: np.ndarray
    step_count: int = 0
    latest_twist: Dict[str, float] = field(default_factory=lambda: {"v": 0.0, "w": 0.0})
    last_command_sequence: float = 0
    last_command_time: float | None = None
    command_timed_out: bool = False
    brake_positions: np.ndarray | None = None
    steering_phase: Literal["drive", "brake", "align"] = "drive"
    steering_goal: np.ndarray | None = None
    drive_basis: np.ndarray | None = None
    drive_twist_basis: tuple[float, float] = (0.0, 0.0)
    settled_steps: int = 0
    brake_motion_samples: list[tuple[float, np.ndarray]] = field(default_factory=list)


@dataclass
class EpisodeState:
    """Stop begins a new time domain; Pause preserves the current one."""

    index: int = 0
    stop_pending: bool = False
    restart_pending: bool = False
    reinitializing: bool = False
    last_physics_step: int = -1
    last_stamp_ns: int | None = None
    last_imu_stamp_ns: int | None = None
    stale_imu_reported: bool = False


@dataclass
class AtmosphereLoopState:
    """Dynamic atmosphere + HDRI carry-over state."""

    atmosphere_dict: Dict[str, Any]
    sol_duration: float
    solar_constant: float
    elapsed: float = 0.0
    time_scale: float = 1.0
    sweep_start_az: float = 90.0
    sweep_end_az: float = 270.0
    sweep_max_el: float = 60.0
    auto_peak_el: float = 0.0
    last_auto_angles: tuple[float, float] | None = None
    update_interval: int = 60
    hdri_dir: str = ""
    sky_dome_config: Any = None
    pending_physics_seconds: float = 0.0


@dataclass
class LoopContext:
    """Everything :func:`run_main_loop` reads or mutates."""

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
    steering_axle_offset: float
    v_max: float
    w_max: float
    physics_dt: float
    negate_steer: bool
    debug_logging: bool
    max_wheel_accel_rate: float
    decel_multiplier: float
    max_steer_angle: float
    steer_ramp_rate: float
    steering_alignment_tolerance: float
    steering_stop_speed: float
    command_timeout: float
    brake_stiffness: float
    control: ControlState
    atmosphere: AtmosphereLoopState
    odom_ctx: Optional["GroundTruthPosePublisherContext"]
    wheel_odom_ctx: Optional["WheelOdometryContext"]
    render_config: Any
    ackermann_fn: Callable[..., Any]
    spin_once: Optional[Callable[..., None]] = None
    imu_noise_ctx: Optional["ImuNoiseContext"] = None
    depth_publisher: DepthPublisher | None = None
    lidar_scan_publisher: LidarScanPublisher | None = None
    update_sun_fn: Optional[Callable[..., None]] = None
    update_sky_fn: Optional[Callable[..., None]] = None
    configure_fog_fn: Optional[Callable[..., None]] = None
    compute_sun_fn: Optional[Callable[..., Any]] = None
    compute_sol_sun_fn: Optional[Callable[..., Any]] = None
    compute_direct_fn: Optional[Callable[..., float]] = None
    compute_diffuse_fn: Optional[Callable[..., float]] = None
    compute_sky_dome_fn: Optional[Callable[..., Any]] = None
    atmo_panel_update: Optional[Callable[[], None]] = None
    reset_articulation: Optional[Callable[[], None]] = None
    reset_depth_acquisition: Optional[Callable[[], None]] = None
    read_imu_sample: Optional[Callable[[], "IMUSample | None"]] = None
    publish_raw_imu: Optional[Callable[..., None]] = None
    episode: EpisodeState = field(default_factory=EpisodeState)


def _apply_ramp(
    command: np.ndarray,
    current: np.ndarray,
    per_step_limit: float,
    decel_multiplier: float,
    ramp_enabled: bool,
) -> np.ndarray:
    """Ramp one common scale so wheel-speed ratios survive acceleration."""
    if not ramp_enabled:
        current[...] = command
        return current
    delta = command - current
    largest_delta = float(np.max(np.abs(delta)))
    is_decel = np.max(np.abs(command)) < np.max(np.abs(current))
    step_limit = per_step_limit * (decel_multiplier if is_decel else 1.0)
    if largest_delta <= step_limit:
        current[...] = command
    else:
        current[...] += delta * (step_limit / largest_delta)
    return current


def _coordinate_steering(
    ctx: LoopContext,
    steer_angles: np.ndarray,
    wheel_velocities: np.ndarray,
    v: float,
    w: float,
    steer_per_step_limit: float,
    simulation_time: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Stop before changing wheel geometry, then drive after measured alignment."""
    ctl = ctx.control
    held = ctl.current_steer_targets
    zero_drive = np.zeros_like(wheel_velocities)
    if not np.any(wheel_velocities):
        ctl.steering_phase = "drive"
        ctl.steering_goal = held.copy()
        ctl.drive_basis = None
        ctl.drive_twist_basis = (0.0, 0.0)
        ctl.settled_steps = 0
        ctl.brake_motion_samples.clear()
        return held.copy(), zero_drive

    measured_steer = ctx.articulation.get_joint_positions(joint_indices=ctx.steer_indices)
    measured_drive = ctx.articulation.get_joint_velocities(joint_indices=ctx.drive_indices)
    drive_positions = ctx.articulation.get_joint_positions(joint_indices=ctx.drive_indices)
    if measured_steer is None or measured_drive is None or drive_positions is None:
        raise RuntimeError("Steering coordination requires live joint feedback")
    measured_steer = np.asarray(measured_steer).reshape(-1)
    measured_drive = np.asarray(measured_drive).reshape(-1)
    drive_positions = np.asarray(drive_positions).reshape(-1)
    if not all(np.isfinite(values).all() for values in (measured_steer, measured_drive, drive_positions)):
        raise RuntimeError("Steering coordination received nonfinite joint feedback")

    tolerance = ctx.steering_alignment_tolerance
    if ctl.steering_goal is None:
        ctl.steering_goal = held.copy()
    requested_change = np.max(np.abs(steer_angles - ctl.steering_goal)) > tolerance
    tracking_error = np.max(np.abs(measured_steer - ctl.steering_goal)) > tolerance
    if ctl.steering_phase == "drive" and (
        requested_change or tracking_error or ctl.drive_basis is None
    ):
        ctl.steering_phase = "brake"
        ctl.settled_steps = 0
        ctl.brake_motion_samples.clear()

    if ctl.steering_phase == "brake":
        stopped = False
        history = ctl.brake_motion_samples
        if np.any(ctl.current_drive_targets):
            history.clear()
        elif not history or simulation_time > history[-1][0]:
            history.append((simulation_time, drive_positions.copy()))
            while len(history) > 2 and history[1][0] <= simulation_time - _STEERING_STOP_WINDOW_SECONDS:
                history.pop(0)
            duration = simulation_time - history[0][0]
            if duration >= _STEERING_STOP_WINDOW_SECONDS - 1e-9:
                # Position excursion rejects motion without relying on noisy solver velocities.
                positions = np.unwrap(np.stack([sample[1] for sample in history]), axis=0)
                stopped = bool(np.max(np.ptp(positions, axis=0)) / duration <= ctx.steering_stop_speed)
        ctl.settled_steps = ctl.settled_steps + 1 if stopped else 0
        if ctl.settled_steps < 3:
            return held.copy(), zero_drive
        ctl.steering_phase = "align"
        ctl.settled_steps = 0
        history.clear()
        ctl.steering_goal = steer_angles.copy()
        magnitude = float(np.max(np.abs(wheel_velocities)))
        ctl.drive_basis = wheel_velocities / magnitude
        ctl.drive_twist_basis = (v / magnitude, w / magnitude)

    if ctl.steering_phase == "align":
        if np.max(np.abs(steer_angles - ctl.steering_goal)) > tolerance:
            ctl.steering_goal = steer_angles.copy()
            magnitude = float(np.max(np.abs(wheel_velocities)))
            ctl.drive_basis = wheel_velocities / magnitude
            ctl.drive_twist_basis = (v / magnitude, w / magnitude)
            ctl.settled_steps = 0
        ramped = held + np.clip(
            ctl.steering_goal - held, -steer_per_step_limit, steer_per_step_limit
        )
        aligned = np.max(np.abs(ramped - ctl.steering_goal)) < 1e-6 and (
            np.max(np.abs(measured_steer - ctl.steering_goal)) <= tolerance
        )
        ctl.settled_steps = ctl.settled_steps + 1 if aligned else 0
        if ctl.settled_steps >= 3:
            ctl.steering_phase = "drive"
            ctl.settled_steps = 0
        return ramped, zero_drive

    # Small intent changes keep the committed steering geometry and speed ratios.
    basis = ctl.drive_basis
    if basis is None:
        raise RuntimeError("Driving requires an aligned wheel-speed basis")
    scale = float(np.dot(wheel_velocities, basis) / np.dot(basis, basis))
    limit = float(np.max(np.abs(wheel_velocities)))
    unit_v, unit_w = ctl.drive_twist_basis
    if unit_v:
        limit = min(limit, ctx.v_max / abs(unit_v))
    if unit_w:
        limit = min(limit, ctx.w_max / abs(unit_w))
    return held.copy(), basis * float(np.clip(scale, -limit, limit))


def _apply_wheel_drive_targets(
    ctx: LoopContext, velocities: np.ndarray, drive_indices: np.ndarray
) -> None:
    """Latch wheel angles at rest; release position feedback before driving."""
    control = ctx.control
    hold = ctx.brake_stiffness > 0.0 and not np.any(velocities)
    was_holding = control.brake_positions is not None
    if hold and not was_holding:
        positions = ctx.articulation.get_joint_positions(joint_indices=drive_indices)
        if positions is None or not np.all(np.isfinite(positions)):
            raise RuntimeError("Cannot engage wheel brake without finite measured joint positions")
        control.brake_positions = np.asarray(positions, dtype=np.float32).copy()
        ctx.articulation.set_joint_position_targets(
            control.brake_positions, joint_indices=drive_indices
        )
    if hold != was_holding:
        stiffness = ctx.brake_stiffness if hold else 0.0
        gains = np.full((1, len(drive_indices)), stiffness, dtype=np.float32)
        ctx.articulation.set_gains(kps=gains, joint_indices=drive_indices)
        applied, _ = ctx.articulation.get_gains(joint_indices=drive_indices)
        if not np.allclose(applied, gains):
            raise RuntimeError("Wheel brake stiffness was not applied to the articulation")
        if not hold:
            control.brake_positions = None
        logger.info("Wheel parking brake %s", "engaged" if hold else "released")
    ctx.articulation.set_joint_velocity_targets(velocities, joint_indices=drive_indices)


def build_atmosphere_loop_state(
    atmo_init: Any,
    tau: float,
) -> AtmosphereLoopState:
    """Factory: derive :class:`AtmosphereLoopState` from a boot snapshot."""
    dyn = atmo_init.dynamic
    atmosphere_dict: Dict[str, Any] = {
        "tau": tau,
        "sun_mode": "auto" if dyn.enabled else "manual",
        "sun_azimuth_deg": float(atmo_init.sun_azimuth_deg),
        "sun_elevation_deg": float(atmo_init.sun_elevation_deg),
        "time_of_sol": dyn.initial_sol_fraction,
        "direct_intensity": atmo_init.direct_intensity,
        "diffuse_fraction": atmo_init.diffuse_fraction,
        "sol_duration_seconds": atmo_init.sol_duration_seconds,
    }
    return AtmosphereLoopState(
        atmosphere_dict=atmosphere_dict,
        sol_duration=atmo_init.sol_duration_seconds,
        solar_constant=atmo_init.solar_constant,
        elapsed=dyn.initial_sol_fraction * atmo_init.sol_duration_seconds,
        time_scale=dyn.time_scale,
        sweep_start_az=dyn.sun_sweep.start_azimuth_deg,
        sweep_end_az=dyn.sun_sweep.end_azimuth_deg,
        sweep_max_el=dyn.sun_sweep.max_elevation_deg,
        update_interval=dyn.update_interval_frames,
        hdri_dir=atmo_init.hdri_dir,
        sky_dome_config=atmo_init.sky_dome_config,
    )


def _reset_episode_state(
    ctx: LoopContext, initial_atmosphere: dict[str, Any], initial_elapsed: float
) -> None:
    from marslab.ros2_bridge.imu_noise_publisher import reset_imu_noise
    from marslab.ros2_bridge.wheel_odometry_publisher import reset_wheel_odometry

    state = ctx.episode
    state.index += 1
    state.stop_pending = False
    state.restart_pending = True
    state.last_stamp_ns = None
    state.last_imu_stamp_ns = None
    state.stale_imu_reported = False
    ctx.control.step_count = 0
    ctx.control.current_drive_targets.fill(0.0)
    ctx.control.current_steer_targets.fill(0.0)
    ctx.control.latest_twist.update(v=0.0, w=0.0, sequence=0)
    ctx.control.last_command_sequence = 0
    ctx.control.last_command_time = None
    ctx.control.command_timed_out = False
    ctx.control.brake_positions = None
    ctx.control.steering_phase = "drive"
    ctx.control.steering_goal = None
    ctx.control.drive_basis = None
    ctx.control.drive_twist_basis = (0.0, 0.0)
    ctx.control.settled_steps = 0
    ctx.control.brake_motion_samples.clear()
    if ctx.wheel_odom_ctx is not None:
        reset_wheel_odometry(ctx.wheel_odom_ctx)
    if ctx.imu_noise_ctx is not None:
        reset_imu_noise(ctx.imu_noise_ctx)
    if ctx.reset_depth_acquisition is not None:
        ctx.reset_depth_acquisition()
    if ctx.depth_publisher is not None:
        ctx.depth_publisher.reset()
    if ctx.lidar_scan_publisher is not None:
        ctx.lidar_scan_publisher.reset()
    atmo = ctx.atmosphere
    atmo.atmosphere_dict.clear()
    atmo.atmosphere_dict.update(deepcopy(initial_atmosphere))
    atmo.elapsed = initial_elapsed
    atmo.auto_peak_el = 0.0
    atmo.last_auto_angles = None
    atmo.pending_physics_seconds = 0.0
    _update_atmosphere(ctx, advance_seconds=0.0)
    logger.info("Simulation episode %d reset after Stop", state.index)


def run_main_loop(ctx: LoopContext) -> int:
    """Publish completed physics snapshots and preserve state across Pause."""
    import omni.timeline
    from isaacsim.core.simulation_manager import SimulationManager

    ctl = ctx.control
    atmo = ctx.atmosphere
    episode = ctx.episode
    initial_atmosphere = deepcopy(atmo.atmosphere_dict)
    initial_elapsed = atmo.elapsed
    drive_idx_arr = np.asarray(ctx.drive_indices, dtype=np.int32)
    steer_idx_arr = np.asarray(ctx.steer_indices, dtype=np.int32)
    per_step_limit = ctx.max_wheel_accel_rate * ctx.physics_dt
    steer_per_step_limit = ctx.steer_ramp_rate * ctx.physics_dt
    timeline = omni.timeline.get_timeline_interface()
    callback_name = "marslab_runtime_episode"

    def timeline_event(event: Any) -> None:
        if event.type == int(omni.timeline.TimelineEventType.STOP):
            if not episode.reinitializing:
                episode.stop_pending = True
        elif event.type == int(omni.timeline.TimelineEventType.PAUSE):
            logger.info("Simulation paused at physics step %d", episode.last_physics_step)

    ctx.world.add_timeline_callback(callback_name, timeline_event)
    episode.last_physics_step = SimulationManager.get_num_physics_steps()
    iterations = 0
    try:
        while ctx.simulation_app.is_running():
            iterations += 1
            if ctx.spin_once is not None:
                ctx.spin_once()
            if episode.stop_pending:
                _reset_episode_state(ctx, initial_atmosphere, initial_elapsed)
            if not timeline.is_playing():
                ctx.simulation_app.update()
                continue
            if episode.restart_pending:
                if ctx.reset_articulation is None:
                    raise RuntimeError("Missing articulation reset owner for Stop/Play")
                episode.reinitializing = True
                try:
                    ctx.reset_articulation()
                finally:
                    episode.reinitializing = False
                episode.restart_pending = False
                episode.last_physics_step = SimulationManager.get_num_physics_steps()
                logger.info("Simulation episode %d ready after Play", episode.index)

            before_step = SimulationManager.get_num_physics_steps()
            before_time = SimulationManager.get_simulation_time()
            sequence = ctl.latest_twist.get("sequence", 0)
            if sequence != ctl.last_command_sequence:
                ctl.last_command_sequence = sequence
                ctl.last_command_time = before_time
                ctl.command_timed_out = False
            v = ctl.latest_twist["v"]
            w = ctl.latest_twist["w"]
            if not math.isfinite(v) or not math.isfinite(w):
                logger.error("Non-finite control state; requesting a controlled stop")
                ctl.latest_twist.update(v=0.0, w=0.0)
                v = w = 0.0
            if ctl.last_command_time is None:
                v = w = 0.0
            elif before_time - ctl.last_command_time >= ctx.command_timeout:
                if not ctl.command_timed_out and (v != 0.0 or w != 0.0):
                    logger.warning(
                        "cmd_vel timed out after %.3f simulation seconds", ctx.command_timeout
                    )
                ctl.command_timed_out = True
                v = w = 0.0
            v = float(np.clip(v, -ctx.v_max, ctx.v_max))
            w = float(np.clip(w, -ctx.w_max, ctx.w_max))
            v, w = constrain_ackermann_twist(
                v, w, ctx.wheelbase, ctx.track_steer, ctx.max_steer_angle,
                ctx.steering_axle_offset,
            )
            steer_angles, wheel_vels = ctx.ackermann_fn(
                v, w, ctx.wheelbase, ctx.track_steer, ctx.track_middle, ctx.wheel_radius,
                ctx.steering_axle_offset,
            )
            if ctx.negate_steer:
                steer_angles = -steer_angles
            ramped_steer, wheel_vels = _coordinate_steering(
                ctx, steer_angles, wheel_vels, v, w, steer_per_step_limit, before_time
            )
            ramped_vels = _apply_ramp(
                wheel_vels,
                ctl.current_drive_targets.copy(),
                per_step_limit,
                ctx.decel_multiplier,
                ctx.max_wheel_accel_rate > 0,
            )
            ctx.articulation.set_joint_position_targets(ramped_steer, joint_indices=steer_idx_arr)
            _apply_wheel_drive_targets(ctx, ramped_vels, drive_idx_arr)
            ctx.world.step(render=True)
            after_step = SimulationManager.get_num_physics_steps()
            if episode.stop_pending or after_step <= before_step:
                continue
            completed_time = SimulationManager.get_simulation_time()
            stamp_ns = int(completed_time * 1_000_000_000)
            if episode.last_stamp_ns is not None and stamp_ns <= episode.last_stamp_ns:
                raise RuntimeError("Physics time failed to advance within the current episode")
            episode.last_physics_step = after_step
            episode.last_stamp_ns = stamp_ns
            ctl.current_steer_targets[:] = ramped_steer
            ctl.current_drive_targets[:] = ramped_vels
            previous_step_count = ctl.step_count
            ctl.step_count += after_step - before_step
            _publish_ground_truth_pose(ctx, stamp_ns)
            _publish_wheel_odometry(ctx, stamp_ns)
            if ctx.publish_raw_imu is not None:
                _publish_imu_sample(ctx, stamp_ns)
            if ctx.depth_publisher is not None:
                ctx.depth_publisher.publish_latest()
            if ctx.lidar_scan_publisher is not None:
                ctx.lidar_scan_publisher.publish_latest()
            atmo.pending_physics_seconds += completed_time - before_time
            if ctl.step_count // atmo.update_interval > previous_step_count // atmo.update_interval:
                _update_atmosphere(ctx, advance_seconds=atmo.pending_physics_seconds)
                atmo.pending_physics_seconds = 0.0
            if ctx.debug_logging and ctl.step_count % 60 == 0:
                _debug_log_step(ctx, steer_idx_arr, drive_idx_arr, v, w, steer_angles, ramped_vels)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt -- shutting down.")
        return 0
    finally:
        ctx.world.remove_timeline_callback(callback_name)

    if iterations == 0:
        logger.error("Simulation App was not running before the first simulation step.")
        return 1
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
    """Emit per-stride diagnostic lines."""
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
            logger.debug(
                "[DIAG %d] twist=(%.3f,%.3f) steer_cmd=%s steer_act=%s drive_cmd=%s drive_act=%s",
                ctx.control.step_count,
                v,
                w,
                steer_angles,
                s_pos,
                ramped_vels,
                d_vel,
            )
    except Exception:  # noqa: BLE001
        logger.exception(
            "Articulation diagnostic failed at physics step %d", ctx.control.step_count
        )
    try:
        imu_frame = ctx.imu.get_current_frame()
        if imu_frame is not None and "lin_acc" in imu_frame:
            la = imu_frame["lin_acc"]
            logger.debug(
                "[DIAG %d] imu_acc=(%.4f,%.4f,%.4f)",
                ctx.control.step_count,
                la[0],
                la[1],
                la[2],
            )
    except Exception:  # noqa: BLE001
        logger.exception("IMU diagnostic failed at physics step %d", ctx.control.step_count)


def _publish_ground_truth_pose(ctx: LoopContext, stamp_ns: int) -> None:
    if ctx.odom_ctx is None:
        return
    from marslab.ros2_bridge.odometry_publisher import publish_ground_truth_pose

    poses = ctx.articulation.get_world_poses()
    if poses is None:
        raise RuntimeError("Completed physics step has no ground-truth pose")
    positions, orientations = poses
    linear = ctx.articulation.get_linear_velocities()
    angular = ctx.articulation.get_angular_velocities()
    if linear is None or angular is None:
        raise RuntimeError("Completed physics step has no ground-truth velocity")
    publish_ground_truth_pose(
        ctx.odom_ctx,
        cur_pos_world=positions[0] if positions.ndim == 2 else positions,
        cur_quat_world=orientations[0] if orientations.ndim == 2 else orientations,
        linear_vel_world=linear[0] if linear.ndim == 2 else linear,
        angular_vel_world=angular[0] if angular.ndim == 2 else angular,
        stamp_ns=stamp_ns,
    )


def _publish_wheel_odometry(ctx: LoopContext, stamp_ns: int) -> None:
    if ctx.wheel_odom_ctx is None:
        return
    from marslab.ros2_bridge.wheel_odometry_publisher import publish_wheel_odometry

    velocities = ctx.articulation.get_joint_velocities()
    if velocities is None:
        raise RuntimeError("Completed physics step has no wheel velocities")
    positions = ctx.articulation.get_joint_positions()
    if positions is None:
        raise RuntimeError("Completed physics step has no steering positions")
    publish_wheel_odometry(ctx.wheel_odom_ctx, velocities, positions, stamp_ns=stamp_ns)


def _publish_imu_sample(ctx: LoopContext, physics_stamp_ns: int) -> None:
    if ctx.read_imu_sample is None or ctx.publish_raw_imu is None:
        return
    sample = ctx.read_imu_sample()
    if sample is None:
        return
    previous = ctx.episode.last_imu_stamp_ns
    if previous is not None and sample.stamp_ns <= previous:
        return
    # Native IMU time is float32; allow its quantization relative to the physics clock.
    timestamp_tolerance_ns = max(
        1, math.ceil(float(np.spacing(np.float32(physics_stamp_ns * 1e-9))) * 1e9)
    )
    if sample.stamp_ns > physics_stamp_ns + timestamp_tolerance_ns:
        if not ctx.episode.stale_imu_reported:
            logger.warning("Discarding an IMU sample outside the current simulation time domain")
            ctx.episode.stale_imu_reported = True
        return
    ctx.publish_raw_imu(
        sample.stamp_seconds,
        sample.linear_acceleration,
        sample.angular_velocity,
        sample.orientation_xyzw,
    )
    if ctx.imu_noise_ctx is not None:
        from marslab.ros2_bridge.imu_noise_publisher import publish_imu_with_noise

        publish_imu_with_noise(
            ctx.imu_noise_ctx,
            sample.linear_acceleration,
            sample.angular_velocity,
            orientation_wxyz=sample.orientation_xyzw[[3, 0, 1, 2]],
            stamp_ns=sample.stamp_ns,
        )
    ctx.episode.last_imu_stamp_ns = sample.stamp_ns


def _update_atmosphere(ctx: LoopContext, *, advance_seconds: float | None = None) -> None:
    """Step the dynamic atmosphere sweep and push updates into the stage."""
    atmo = ctx.atmosphere
    state = atmo.atmosphere_dict
    current_tau = state["tau"]
    dyn_sun_pos = None

    if state["sun_mode"] == "auto":
        if ctx.compute_sol_sun_fn is None or ctx.compute_sun_fn is None:
            return
        angles = state["sun_azimuth_deg"], state["sun_elevation_deg"]
        if angles != atmo.last_auto_angles:
            # Anchor both angles before advancing the existing sweep.
            atmo.auto_peak_el = max(atmo.sweep_max_el, angles[1])
            phase = 0.0
            if atmo.auto_peak_el:
                phase = math.asin(angles[1] / atmo.auto_peak_el) / math.pi
            if (atmo.elapsed % atmo.sol_duration) / atmo.sol_duration > 0.5:
                phase = 1.0 - phase
            atmo.elapsed = phase * atmo.sol_duration
            dyn_sun_pos = ctx.compute_sun_fn(*angles)
        else:
            step = (
                ctx.physics_dt * atmo.update_interval
                if advance_seconds is None
                else advance_seconds
            ) * atmo.time_scale
            atmo.elapsed += step
            sweep = ctx.compute_sol_sun_fn(
                time_of_sol_fraction=(atmo.elapsed % atmo.sol_duration) / atmo.sol_duration,
                start_azimuth_deg=atmo.sweep_start_az,
                end_azimuth_deg=atmo.sweep_end_az,
                max_elevation_deg=atmo.auto_peak_el,
                mode="linear",
            )
            azimuth_step = (atmo.sweep_end_az - atmo.sweep_start_az) * step / atmo.sol_duration
            dyn_sun_pos = ctx.compute_sun_fn(
                (angles[0] + azimuth_step) % 360.0, sweep.elevation_deg
            )
        t = (atmo.elapsed % atmo.sol_duration) / atmo.sol_duration
        state["time_of_sol"] = t
        state["sun_azimuth_deg"] = dyn_sun_pos.azimuth_deg
        state["sun_elevation_deg"] = dyn_sun_pos.elevation_deg
        atmo.last_auto_angles = dyn_sun_pos.azimuth_deg, dyn_sun_pos.elevation_deg
    elif state["sun_mode"] == "manual" and ctx.compute_sun_fn is not None:
        atmo.last_auto_angles = None
        dyn_sun_pos = ctx.compute_sun_fn(
            azimuth_deg=state["sun_azimuth_deg"],
            elevation_deg=state["sun_elevation_deg"],
        )

    if dyn_sun_pos is None:
        return

    if (
        ctx.compute_direct_fn is None
        or ctx.compute_diffuse_fn is None
        or ctx.compute_sky_dome_fn is None
    ):
        return

    direct = ctx.compute_direct_fn(atmo.solar_constant, current_tau, dyn_sun_pos.zenith_angle_rad)
    diffuse = ctx.compute_diffuse_fn(current_tau)
    dyn_sky = ctx.compute_sky_dome_fn(
        current_tau,
        atmo.hdri_dir,
        atmo.sky_dome_config,
    )

    state["direct_intensity"] = direct
    state["diffuse_fraction"] = diffuse

    if ctx.update_sun_fn is not None:
        ctx.update_sun_fn(ctx.stage, dyn_sun_pos, direct, ctx.render_config)
    if ctx.update_sky_fn is not None:
        ctx.update_sky_fn(ctx.stage, dyn_sky, diffuse, ctx.render_config)
    if ctx.configure_fog_fn is not None:
        ctx.configure_fog_fn(ctx.stage, current_tau, ctx.render_config)
    if ctx.atmo_panel_update is not None:
        ctx.atmo_panel_update()
