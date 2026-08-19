"""Main-loop extraction for the monolithic Stage 3 runtime.

Public entry point :func:`run_main_loop` consumes a :class:`LoopContext`
bundling every object and scalar the inline loop closed over.
Mutable ramp / atmosphere state is carried in :class:`ControlState` /
:class:`AtmosphereLoopState` (mutated in place).  Odometry publishing is
delegated to :func:`marslab.ros2_bridge.odometry_publisher.publish_odometry`
via the :class:`~marslab.ros2_bridge.odometry_publisher.OdometryPublisherContext`
carried on :attr:`LoopContext.odom_ctx` -- a single source of truth that
honours the ``publish_tf`` gate so exactly one component owns
``odom -> base_link`` on ``/tf``.
Isaac Sim / ``rclpy`` symbols enter via the context only -- the module
itself is offline-importable (no Isaac Sim imports at module scope).
A normal exit after at least one iteration or ``KeyboardInterrupt`` returns
``0``. An app that is already stopped at loop entry returns ``1``. The caller
owns ``simulation_app.close()``. ``marslab/main.py`` is the live Stage 3
runtime entry point.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional

import numpy as np

if TYPE_CHECKING:
    # Type-only import: keeps the runtime offline-importable because the
    # publisher module's ``rclpy`` / ``tf2_ros`` / ``nav_msgs`` imports
    # are themselves function-local.
    from marslab.ros2_bridge.imu_noise_publisher import ImuNoiseContext
    from marslab.ros2_bridge.odometry_publisher import OdometryPublisherContext
    from marslab.ros2_bridge.wheel_odometry_publisher import WheelOdometryContext

logger = logging.getLogger(__name__)

#: Default number of physics steps during which per-step exceptions are
#: promoted to ``logger.error`` output. Steps beyond this grace window
#: intentionally silence the per-frame chatter to keep long runs readable.
#:
#: Honest caveat: a critical failure surfacing *after* step 120 (e.g.
#: IMU gravity drift, articulation desync) is still not observable from
#: this helper alone -- callers that need mid-run invariants must add
#: dedicated periodic assertions (see
#: ``tests/unit/test_imu_gravity_assertion.py``).
_DEFAULT_GRACE_STEPS = 120


def _log_once(
    target_logger: logging.Logger,
    exc: BaseException,
    category: str,
    step_count: int,
    grace_steps: int = _DEFAULT_GRACE_STEPS,
) -> None:
    """Log an exception during the grace period and stay silent afterwards.

    Consolidates the shotgun-surgery ``except Exception: print(..., step<120)``
    pattern previously duplicated across the main loop (joint target set,
    articulation probe, IMU fetch, velocity query, odom publish).

    Args:
        target_logger: Module logger (typically ``logging.getLogger(__name__)``).
            The ``target_`` prefix avoids shadowing the module-level
            ``logger`` binding for clarity at call sites.
        exc: The caught exception instance.
        category: Short snake_case label identifying the failure site
            (e.g. ``"joint_target_set_failed"``).
        step_count: Current simulation step count. Used to gate logging via
            ``grace_steps``.
        grace_steps: Number of leading steps during which the failure is
            emitted at ``ERROR`` level. After this many steps the helper
            silently returns so that long runs are not flooded by a single
            recurring failure. Defaults to :data:`_DEFAULT_GRACE_STEPS`.
    """
    if step_count < grace_steps:
        target_logger.error("%s (step=%d): %r", category, step_count, exc)


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
        step_count: Monotonic physics-step counter; the debug-log stride
            uses ``step_count % 60 == 0`` as its emit condition.
        latest_twist: Most recent ``(v, w)`` values seen on ``cmd_vel``.
            Keys ``"v"`` and ``"w"`` -- kept as a dict for backward
            compatibility with the GUI panel that reads/writes the same
            mutable state.
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

    ``sol_duration`` and ``solar_constant`` are required constructor
    arguments: callers must source them from the pydantic
    :class:`marslab.config.schema.MarsEnvConfig` rather than duplicate
    the Mars physics constants (``88642.0`` s, ``589.0`` W/m^2) here.

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
class VehicleGeometry:
    """Static rover kinematics consumed by the Ackermann controller.

    Extracted from :class:`LoopContext`. These values are computed once
    from URDF / scenario YAML and never mutate at runtime.

    Attributes:
        wheelbase: Distance between front and rear axles (m).
        track_steer: Track width at the steering axles (m).
        track_middle: Track width at the middle (driven) axles (m).
        wheel_radius: Drive wheel radius (m).
    """

    wheelbase: float
    track_steer: float
    track_middle: float
    wheel_radius: float


@dataclass
class ControlLimits:
    """Ramp-rate and saturation envelope for cmd_vel → joint targets.

    Extracted from :class:`LoopContext`. These are controller-tunable
    bounds separate from the static vehicle geometry.

    Attributes:
        v_max: Linear velocity saturation (m/s, symmetric).
        w_max: Angular velocity saturation (rad/s, symmetric).
        max_wheel_accel_rate: Drive wheel acceleration limit (rad/s^2).
            A non-positive value disables the ramp.
        decel_multiplier: Multiplier on ``max_wheel_accel_rate`` applied
            when decelerating (``|target| < |current|``).
        max_steer_angle: Steering-joint clamp (rad, symmetric).
        steer_ramp_rate: Steering-joint ramp rate (rad/s). Non-positive
            disables steering ramp.
        negate_steer: If ``True``, flip the sign of commanded steering
            angles before clamping (URDF-specific convention).
    """

    v_max: float
    w_max: float
    max_wheel_accel_rate: float
    decel_multiplier: float
    max_steer_angle: float
    steer_ramp_rate: float
    negate_steer: bool = False


@dataclass
class AtmosphereCallables:
    """Optional atmosphere / rendering callbacks shared across the loop.

    Extracted from :class:`LoopContext`. Every field defaults to ``None``
    so ``--no-atmosphere`` / headless unit-test callers can construct
    the context without stubbing the entire rendering pipeline.

    Attributes:
        update_sun_fn: Pushes new sun position/intensity into the stage.
        update_sky_fn: Pushes new HDRI parameters into the sky dome.
        configure_fog_fn: Re-applies the Beer's-law fog with a new tau.
        compute_sun_fn: Manual-mode solar position resolver.
        compute_sol_sun_fn: Auto-mode solar position resolver
            (time-of-sol sweep).
        compute_direct_intensity_fn: Direct (beam) irradiance
            (Kasten-Young Beer's law).
        compute_diffuse_fraction_fn: Diffuse fraction ``f_d(tau)``.
        compute_sky_dome_fn: Butterscotch HDRI parameter resolver.
        atmo_panel_update: GUI panel refresh hook.
    """

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
    """Everything :func:`run_main_loop` reads or mutates.

    Grouped by lifecycle:

    *   Isaac Sim singletons: ``simulation_app``, ``world``, ``stage``.
    *   Robot handles: ``articulation``, ``imu``.
    *   Joint index arrays: ``drive_indices``, ``steer_indices``.
    *   Vehicle geometry & control limits: ``wheelbase``, ``track_steer``,
        ``track_middle``, ``wheel_radius``, ``v_max``, ``w_max``, ramp rates.
    *   Physics tick: ``physics_dt``.
    *   Mutable state: ``control``, ``atmosphere``, ``odom_ctx``.
    *   Callables: ``ackermann_fn``, ``spin_once``, ``update_sun_fn``,
        ``update_sky_fn``, ``configure_fog_fn``, ``compute_sun_fn``,
        ``compute_sol_sun_fn``, ``compute_direct_intensity_fn``,
        ``compute_diffuse_fraction_fn``, ``compute_sky_dome_fn``,
        ``atmo_panel_update``.

    Decomposition
    -------------
    The flat dataclass exposes 35 fields (11 of them ``Callable``
    hooks), which lends itself to a god-object reading. Three composed
    sub-views give consumers a narrower surface:

    * :class:`VehicleGeometry` -- static rover kinematics.
    * :class:`ControlLimits` -- ramp / saturation envelope.
    * :class:`AtmosphereCallables` -- optional rendering callbacks.

    To keep backward compatibility with existing callers (and the
    byte-level signature tests), the flat attributes remain on
    :class:`LoopContext`; the sub-dataclass views are exposed as
    read-only ``@property`` accessors that construct fresh instances on
    demand.  New code should prefer ``ctx.geometry.wheel_radius`` etc.,
    but ``ctx.wheel_radius`` stays valid.
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
    odom_ctx: Optional["OdometryPublisherContext"]
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

    # --- Sub-dataclass views ------------------------------------------------

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
    wire every ``DynamicAtmosphereConfig`` + ``AtmosphereInit``
    field into a mutable loop state.  Keeps
    ``marslab/main.py`` focused on Stage-3 orchestration.

    Args:
        atmo_init: :class:`marslab.runtime.atmosphere_boot.AtmosphereInit`
            produced by :func:`boot_atmosphere`.
        tau: Initial dust optical depth value (mirrored into the live
            ``atmosphere_dict`` so the GUI panel sees it on startup).

    Returns:
        Fully populated :class:`AtmosphereLoopState` ready to pass into
        a :class:`LoopContext`.
    """
    dyn = atmo_init.dynamic
    # ``sol_duration_seconds`` is required by ``AtmospherePanel`` when
    # toggled to Auto mode.
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
        ctx: Pre-initialized :class:`LoopContext` assembled by the
            :mod:`marslab.main` after Isaac Sim boot and
            ``world.reset()``.

    Returns:
        ``0`` on normal exit after at least one iteration or
        ``KeyboardInterrupt``; ``1`` when the app is already stopped at loop
        entry. The caller owns the ``simulation_app.close()`` call.

    Raises:
        Exception: Any exception other than :class:`KeyboardInterrupt`
            raised outside the per-step ``try`` blocks. The caller's
            ``finally`` is expected to tear Isaac Sim down.
    """
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

            # Rover-step block. ``ctx.articulation is None`` is the
            # ``--no-rover`` scene-only path (atmosphere + AtmospherePanel
            # only); skipping here keeps the joint set / Ackermann math /
            # debug log all gated behind the same flag.
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
                _publish_odometry(ctx, ctl.step_count)

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


def _publish_odometry(ctx: LoopContext, step_count: int) -> None:
    """Delegate odometry publish to the canonical ``publish_odometry``.

    The previous inline implementation duplicated
    :func:`marslab.ros2_bridge.odometry_publisher.publish_odometry` and
    silently bypassed the ``tf_broadcaster is None`` gate, raising
    ``AttributeError("'NoneType' object has no attribute 'sendTransform'")``
    every step once the rclpy odom TF defaulted off. Routing through the
    publisher makes that gate the single source of truth and keeps the
    math (``compute_odom_delta`` / ``world_twist_to_body``) in one place.

    Velocity-fetch failure is preserved as the ``velocity_query_failed``
    grace-window log; the outer ``odom_publish_failed`` category covers
    any unexpected exception so the runtime log line spelling stays
    bit-equal with prior runs.
    """
    odom_ctx = ctx.odom_ctx
    if odom_ctx is None:
        return

    # Function-local import keeps the offline-importable property of
    # ``main_loop``: ``odometry_publisher`` itself defers
    # ``rclpy``/``tf2_ros``/``nav_msgs`` to its own function bodies, but
    # importing it at module scope would still drag in the typing-only
    # references at unit-test time on a host without ROS 2.
    from marslab.ros2_bridge.odometry_publisher import publish_odometry

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

        # Velocity query is best-effort.  When it fails the publisher
        # still emits a well-formed Odometry with zero twist instead of
        # skipping the message altogether (same external contract as the
        # prior inline path -- which also defaulted twist fields to 0.0
        # via the ROS message constructor when the inner try raised).
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

        publish_odometry(
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
            # ``mode="linear"`` preserves the SunSweepConfig envelope
            # semantics used by the live simulation. Upgrading to the
            # spherical default requires plumbing ``latitude_deg`` /
            # ``ls_deg`` through SunSweepConfig first.
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
