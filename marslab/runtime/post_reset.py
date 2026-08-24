"""Apply articulation, sensor, and bridge setup after world reset.
The phase returns live handles consumed by the main loop.
Runtime imports stay deferred until reset has completed."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import import_module
from typing import NotRequired, Protocol, TypedDict

import numpy as np

from marslab.config.schema.rover import RoverConfig
from marslab.ros2_bridge.context import BridgeContext
from marslab.runtime.assembly import ArticulationHandle, PreResetAssembly
from marslab.runtime.atmosphere_boot import AtmosphereInit
from marslab.runtime.main_loop import AtmosphereLoopState
from marslab.runtime.physics_override_log import format_physics_override_summary

SpawnPosition = tuple[float, float, float]
SensorFrames = list[tuple[str, list[float], list[float]]]
_DOF_NAMES = "dof_names"
_LOG = logging.getLogger(__name__)


class WheelOdomParams(TypedDict):
    left_indices: list[int]
    right_indices: list[int]
    wheel_radius: float
    track_width: float
    slip_left: float
    slip_right: float
    sigma_omega: float
    seed: int | None
    pose_diag: NotRequired[list[float]]
    twist_diag: NotRequired[list[float]]


class ImuNoiseParams(TypedDict):
    imu_prim_path: str
    sigma_lin_acc: float
    sigma_ang_vel: float
    seed: int | None


class WorldHandle(Protocol):
    def step(self, *, render: bool) -> None: ...


class SimulationAppHandle(Protocol):
    def update(self) -> None: ...


class TimelineHandle(Protocol):
    def is_stopped(self) -> bool: ...

    def play(self) -> None: ...


class AtmospherePanelHandle(Protocol):
    def update_display(self) -> None: ...


@dataclass(frozen=True, slots=True)
class PostResetAssembly:
    articulation: ArticulationHandle
    drive_indices: list[int]
    steer_indices: list[int]
    atmosphere: AtmosphereLoopState
    atmosphere_panel: AtmospherePanelHandle | None
    bridge: BridgeContext | None


def _build_wheel_odom_params(
    rover: RoverConfig,
    dof_names: list[str],
) -> WheelOdomParams | None:
    wheel_odometry = rover.wheel_odometry
    if not wheel_odometry.enabled:
        return None

    rover_module = import_module("marslab.robots.rover")
    params: WheelOdomParams = {
        "left_indices": rover_module.resolve_joint_indices(
            dof_names, list(wheel_odometry.left_wheel_joints)
        ),
        "right_indices": rover_module.resolve_joint_indices(
            dof_names, list(wheel_odometry.right_wheel_joints)
        ),
        "wheel_radius": float(rover.control.wheel_radius),
        "track_width": float(wheel_odometry.track_width),
        "slip_left": float(wheel_odometry.slip_left),
        "slip_right": float(wheel_odometry.slip_right),
        "sigma_omega": float(wheel_odometry.sigma_omega),
        "seed": 0,
    }
    if wheel_odometry.pose_diag is not None:
        params["pose_diag"] = list(wheel_odometry.pose_diag)
    if wheel_odometry.twist_diag is not None:
        params["twist_diag"] = list(wheel_odometry.twist_diag)
    return params


def assemble_post_reset(
    *,
    world: WorldHandle,
    simulation_app: SimulationAppHandle,
    pre_reset: PreResetAssembly,
    rover: RoverConfig,
    atmosphere_init: AtmosphereInit,
    headless: bool,
    atmosphere_enabled: bool,
    ros2_enabled: bool,
    wheel_odom_publish_tf: bool,
) -> PostResetAssembly:
    articulation = pre_reset.articulation
    articulation.initialize()
    articulation_setup = import_module("marslab.runtime.articulation_setup")
    rover_module = import_module("marslab.robots.rover")
    drive_setup = import_module("marslab.robots.drive_api_setup")
    control_config = rover.control.model_dump(mode="python")
    articulation_setup.pin_articulation_root_pose(
        articulation,
        pre_reset.spawn_xyz,
        pre_reset.spawn_rpy,
    )
    dof_names = list(getattr(articulation, _DOF_NAMES))
    drive_indices = rover_module.resolve_joint_indices(
        dof_names, list(rover.control.drive_joint_names)
    )
    steer_indices = rover_module.resolve_joint_indices(
        dof_names, list(rover.control.steer_joint_names)
    )
    articulation_setup.zero_steer_joints(articulation, steer_indices)
    articulation_setup.apply_initial_joint_positions(articulation, dof_names, control_config)

    _LOG.info("Warming up physics handle ...")
    for _ in range(10):
        world.step(render=True)
    timeline_module = import_module("omni.timeline")
    timeline: TimelineHandle = timeline_module.get_timeline_interface()
    if timeline.is_stopped():
        timeline.play()
        for _ in range(5):
            world.step(render=True)
    drive_setup.reinforce_pd_gains(
        articulation,
        rover.control,
        rover.suspension,
        dof_names,
    )
    _LOG.info("%s", format_physics_override_summary(rover))

    main_loop = import_module("marslab.runtime.main_loop")
    atmosphere = main_loop.build_atmosphere_loop_state(atmosphere_init, atmosphere_init.tau)
    atmosphere_panel = None
    if not headless and atmosphere_enabled:
        try:
            atmosphere_panel_module = import_module("marslab.gui.atmosphere_panel")
            atmosphere_panel = atmosphere_panel_module.AtmospherePanel(atmosphere.atmosphere_dict)
            for _ in range(5):
                simulation_app.update()
            _LOG.info("Atmosphere control panel created.")
        except Exception as exc:  # noqa: BLE001 - legacy GUI failure boundary
            _LOG.error("GUI panel unavailable (%s); continuing without it.", exc)

    bridge = None
    if ros2_enabled:
        sensor_frames_module = import_module("marslab.runtime.sensor_frames")
        sensor_frames: SensorFrames = sensor_frames_module.sensor_frames_to_tuples(
            sensor_frames_module.build_sensor_frames(rover.sensors.model_dump(mode="python"))
        )
        master_seed = rover.sensors.seed
        if master_seed is not None:
            child_seeds = np.random.SeedSequence(int(master_seed)).spawn(3)
            odom_seed = int(child_seeds[0].generate_state(1)[0])
            imu_seed = int(child_seeds[1].generate_state(1)[0])
        else:
            odom_seed = None
            imu_seed = None
        wheel_odom_params = _build_wheel_odom_params(rover, dof_names)
        if wheel_odom_params is not None and odom_seed is not None:
            wheel_odom_params["seed"] = odom_seed
        imu = rover.sensors.imu
        imu_noise_params: ImuNoiseParams | None = None
        if imu.sigma_lin_acc > 0.0 or imu.sigma_ang_vel > 0.0:
            imu_noise_params = {
                "imu_prim_path": pre_reset.sensors.imu_prim_path,
                "sigma_lin_acc": float(imu.sigma_lin_acc),
                "sigma_ang_vel": float(imu.sigma_ang_vel),
                "seed": imu_seed,
            }
        rclpy_integration = import_module("marslab.ros2_bridge.rclpy_integration")
        bridge = rclpy_integration.init_rclpy_side(
            ros2_cfg=rover.ros2.model_dump(mode="python"),
            sensor_frames=sensor_frames,
            node_name="marslab_main_rover",
            urdf_path=str(rover.urdf_source_path),
            wheel_odom_params=wheel_odom_params,
            imu_noise_params=imu_noise_params,
            wheel_odom_publish_tf=wheel_odom_publish_tf,
        )
    return PostResetAssembly(
        articulation=articulation,
        drive_indices=drive_indices,
        steer_indices=steer_indices,
        atmosphere=atmosphere,
        atmosphere_panel=atmosphere_panel,
        bridge=bridge,
    )


__all__ = ["PostResetAssembly", "assemble_post_reset"]
