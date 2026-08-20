"""Run the stateful simulation tick loop.
Control, odometry, sensors, atmosphere, and diagnostics share one context.
The loop remains importable without Isaac or ROS bindings."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import numpy as np

if TYPE_CHECKING:
    from marslab.ros2_bridge.imu_noise_publisher import ImuNoiseContext
    from marslab.ros2_bridge.odometry_publisher import GroundTruthPosePublisherContext
    from marslab.ros2_bridge.wheel_odometry_publisher import WheelOdometryContext

logger = logging.getLogger(__name__)

_DEFAULT_GRACE_STEPS = 120


def _log_once(
    target_logger: logging.Logger,
    exc: BaseException,
    category: str,
    step_count: int,
    grace_steps: int = _DEFAULT_GRACE_STEPS,
) -> None:
    """Log an exception during the grace period and stay silent afterwards."""
    if step_count < grace_steps:
        target_logger.error("%s (step=%d): %r", category, step_count, exc)


@dataclass
class ControlState:
    """Drive / steer ramp state mutated per physics step."""

    current_drive_targets: np.ndarray
    current_steer_targets: np.ndarray
    step_count: int = 0
    latest_twist: Dict[str, float] = field(default_factory=lambda: {"v": 0.0, "w": 0.0})


@dataclass
class AtmosphereLoopState:
    """Dynamic atmosphere + HDRI carry-over state."""

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
class VehicleGeometry:
    """Static rover kinematics consumed by the Ackermann controller."""

    wheelbase: float
    track_steer: float
    track_middle: float
    wheel_radius: float


@dataclass
class ControlLimits:
    """Ramp-rate and saturation envelope for cmd_vel → joint targets."""

    v_max: float
    w_max: float
    max_wheel_accel_rate: float
    decel_multiplier: float
    max_steer_angle: float
    steer_ramp_rate: float
    negate_steer: bool = False


@dataclass
class AtmosphereCallables:
    """Optional atmosphere / rendering callbacks shared across the loop."""

    update_sun_fn: Optional[Callable[..., None]] = None
    update_sky_fn: Optional[Callable[..., None]] = None
    configure_fog_fn: Optional[Callable[..., None]] = None
    compute_sun_fn: Optional[Callable[..., Any]] = None
    compute_sol_sun_fn: Optional[Callable[..., Any]] = None
    compute_direct_intensity_fn: Optional[Callable[..., float]] = None
    compute_diffuse_fraction_fn: Optional[Callable[..., float]] = None
    compute_sky_dome_fn: Optional[Callable[..., Any]] = None
    atmo_panel_update: Optional[Callable[[], None]] = None


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
    odom_ctx: Optional["GroundTruthPosePublisherContext"]
    wheel_odom_ctx: Optional["WheelOdometryContext"]
    render_config: Any
    ackermann_fn: Callable[..., Any]
    spin_once: Optional[Callable[..., None]] = None
    imu_noise_ctx: Optional["ImuNoiseContext"] = None
    update_sun_fn: Optional[Callable[..., None]] = None
    update_sky_fn: Optional[Callable[..., None]] = None
    configure_fog_fn: Optional[Callable[..., None]] = None
    compute_sun_fn: Optional[Callable[..., Any]] = None
    compute_sol_sun_fn: Optional[Callable[..., Any]] = None
    compute_direct_intensity_fn: Optional[Callable[..., float]] = None
    compute_diffuse_fraction_fn: Optional[Callable[..., float]] = None
    compute_sky_dome_fn: Optional[Callable[..., Any]] = None
    atmo_panel_update: Optional[Callable[[], None]] = None

    @property
    def geometry(self) -> VehicleGeometry:
        """Read-only :class:`VehicleGeometry` view of the kinematic fields."""
        return VehicleGeometry(
            wheelbase=self.wheelbase,
            track_steer=self.track_steer,
            track_middle=self.track_middle,
            wheel_radius=self.wheel_radius,
        )

    @property
    def control_limits(self) -> ControlLimits:
        """Read-only :class:`ControlLimits` view of the ramp/saturation fields."""
        return ControlLimits(
            v_max=self.v_max,
            w_max=self.w_max,
            max_wheel_accel_rate=self.max_wheel_accel_rate,
            decel_multiplier=self.decel_multiplier,
            max_steer_angle=self.max_steer_angle,
            steer_ramp_rate=self.steer_ramp_rate,
            negate_steer=self.negate_steer,
        )

    @property
    def atmosphere_callables(self) -> AtmosphereCallables:
        """Read-only :class:`AtmosphereCallables` view of the optional hooks."""
        return AtmosphereCallables(
            update_sun_fn=self.update_sun_fn,
            update_sky_fn=self.update_sky_fn,
            configure_fog_fn=self.configure_fog_fn,
            compute_sun_fn=self.compute_sun_fn,
            compute_sol_sun_fn=self.compute_sol_sun_fn,
            compute_direct_intensity_fn=self.compute_direct_intensity_fn,
            compute_diffuse_fraction_fn=self.compute_diffuse_fraction_fn,
            compute_sky_dome_fn=self.compute_sky_dome_fn,
            atmo_panel_update=self.atmo_panel_update,
        )


def _apply_ramp(
    command: np.ndarray,
    current: np.ndarray,
    per_step_limit: float,
    decel_multiplier: float,
    ramp_enabled: bool,
) -> np.ndarray:
    """Shared drive-ramp kernel."""
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
    """Factory: derive :class:`AtmosphereLoopState` from a boot snapshot."""
    dyn = atmo_init.dynamic
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
    """Drive the Stage 3 monolithic runtime until the sim stops."""
    ctl = ctx.control
    atmo = ctx.atmosphere
    odom_ctx = ctx.odom_ctx

    drive_idx_arr = np.asarray(ctx.drive_indices, dtype=np.int32)
    steer_idx_arr = np.asarray(ctx.steer_indices, dtype=np.int32)

    per_step_limit = ctx.max_wheel_accel_rate * ctx.physics_dt
    steer_per_step_limit = ctx.steer_ramp_rate * ctx.physics_dt
    drive_ramp_enabled = ctx.max_wheel_accel_rate > 0
    steer_ramp_enabled = ctx.steer_ramp_rate > 0

    iterations = 0
    try:
        while ctx.simulation_app.is_running():
            iterations += 1
            if ctx.spin_once is not None:
                ctx.spin_once()

            if ctx.articulation is not None:
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
                    _log_once(logger, exc, "joint_target_set_failed", ctl.step_count)

                if ctx.debug_logging and ctl.step_count % 60 == 0:
                    _debug_log_step(
                        ctx, steer_idx_arr, drive_idx_arr, v, w, steer_angles, ramped_vels
                    )

            if odom_ctx is not None and odom_ctx.publisher is not None:
                _publish_ground_truth_pose(ctx, ctl.step_count)

            if ctx.wheel_odom_ctx is not None and ctx.wheel_odom_ctx.publisher is not None:
                _publish_wheel_odometry(ctx, ctl.step_count)

            if ctx.imu_noise_ctx is not None and ctx.imu_noise_ctx.publisher is not None:
                _publish_imu_with_noise(ctx, ctl.step_count)

            if ctl.step_count % atmo.update_interval == 0 and ctl.step_count > 0:
                _update_atmosphere(ctx)

            ctl.step_count += 1
            ctx.world.step(render=True)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt -- shutting down.")
        return 0

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
                "[DIAG %d] twist=(%.3f,%.3f) steer_cmd=%s steer_act=%s "
                "drive_cmd=%s drive_act=%s",
                ctx.control.step_count,
                v,
                w,
                steer_angles,
                s_pos,
                ramped_vels,
                d_vel,
            )
    except Exception as exc:  # noqa: BLE001
        _log_once(logger, exc, "articulation_probe_failed", ctx.control.step_count)
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
    except Exception as exc:  # noqa: BLE001
        _log_once(logger, exc, "imu_frame_fetch_failed", ctx.control.step_count)


def _publish_ground_truth_pose(ctx: LoopContext, step_count: int) -> None:
    """Delegate GT pose publish to the canonical ground-truth publisher."""
    odom_ctx = ctx.odom_ctx
    if odom_ctx is None:
        return

    from marslab.ros2_bridge.odometry_publisher import publish_ground_truth_pose

    try:
        rover_poses_odom = ctx.articulation.get_world_poses()
        if rover_poses_odom is None:
            _log_once(
                logger,
                RuntimeError("get_world_poses returned None"),
                "world_pose_query_failed",
                step_count,
            )
            return
        _rp, _rq = rover_poses_odom
        cur_pos = _rp[0] if _rp.ndim == 2 else _rp
        cur_quat = _rq[0] if _rq.ndim == 2 else _rq

        try:
            lin_vel = ctx.articulation.get_linear_velocities()
            ang_vel = ctx.articulation.get_angular_velocities()
        except Exception as vel_exc:  # noqa: BLE001
            _log_once(logger, vel_exc, "velocity_query_failed", step_count)
            lin_vel = None
            ang_vel = None
        if lin_vel is not None and ang_vel is not None:
            lv = lin_vel[0] if lin_vel.ndim == 2 else lin_vel
            av = ang_vel[0] if ang_vel.ndim == 2 else ang_vel
        else:
            lv = np.zeros(3, dtype=np.float32)
            av = np.zeros(3, dtype=np.float32)

        publish_ground_truth_pose(
            odom_ctx,
            cur_pos_world=cur_pos,
            cur_quat_world=cur_quat,
            linear_vel_world=lv,
            angular_vel_world=av,
        )
    except Exception as odom_exc:  # noqa: BLE001
        _log_once(logger, odom_exc, "odom_publish_failed", step_count)


def _publish_wheel_odometry(ctx: LoopContext, step_count: int) -> None:
    """Integrate wheel joint velocities and publish noisy odometry."""
    wheel_ctx = ctx.wheel_odom_ctx
    if wheel_ctx is None:
        return

    from marslab.ros2_bridge.wheel_odometry_publisher import publish_wheel_odometry

    try:
        jv = ctx.articulation.get_joint_velocities()
        if jv is None:
            _log_once(
                logger,
                RuntimeError("get_joint_velocities returned None"),
                "joint_velocity_query_failed",
                step_count,
            )
            return
        publish_wheel_odometry(wheel_ctx, jv)
    except Exception as exc:  # noqa: BLE001
        _log_once(logger, exc, "wheel_odom_publish_failed", step_count)


def _publish_imu_with_noise(ctx: LoopContext, step_count: int) -> None:
    """Read the PhysX IMU frame, inject seeded Gaussian noise, publish."""
    imu_ctx = ctx.imu_noise_ctx
    if imu_ctx is None:
        return

    from marslab.ros2_bridge.imu_noise_publisher import publish_imu_with_noise

    try:
        from isaacsim.sensors.physics import _sensor as _imu_sensor
    except ImportError:
        try:
            from omni.isaac.sensor import _sensor as _imu_sensor
        except ImportError:
            return

    try:
        imu_interface = _imu_sensor.acquire_imu_sensor_interface()
        reading = imu_interface.get_sensor_reading(
            imu_ctx.imu_prim_path, use_latest_data=True, read_gravity=True
        )
        lin_acc = np.array(
            [reading.lin_acc_x, reading.lin_acc_y, reading.lin_acc_z], dtype=np.float64
        )
        ang_vel = np.array(
            [reading.ang_vel_x, reading.ang_vel_y, reading.ang_vel_z], dtype=np.float64
        )
        publish_imu_with_noise(imu_ctx, lin_acc, ang_vel)
    except Exception as exc:  # noqa: BLE001
        _log_once(logger, exc, "imu_noise_publish_failed", step_count)


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
                mode="linear",
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
