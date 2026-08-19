"""Coordinate the mandatory Camera, 3D LiDAR, and IMU spawners."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt

from marslab.config.schema.rover_sensors import CameraConfig, IMUConfig, Lidar3DConfig
from marslab.sensors.camera_spawner import CameraSpawnHandles, spawn_camera
from marslab.sensors.imu_spawner import IMUSpawnHandles, spawn_imu
from marslab.sensors.lidar_3d_spawner import Lidar3DSpawnHandles, spawn_lidar_3d

_MARS_GRAVITY_MS2 = 3.72
_MARS_GRAVITY_TOL_WARN = 0.5
_LOG = logging.getLogger(__name__)


@dataclass
class SensorHandles:
    """Live sensor objects, prim paths, and on-demand read helpers."""

    camera: Any
    lidar_3d: Any
    imu: Any
    camera_prim_path: str
    lidar_3d_prim_path: str
    imu_prim_path: str
    camera_acquisition: CameraSpawnHandles
    lidar_3d_acquisition: Lidar3DSpawnHandles
    imu_acquisition: IMUSpawnHandles

    def read_camera_rgb(self) -> npt.NDArray[np.uint8]:
        """Read an RGBA image, returning an empty array before a frame exists."""
        data = self.camera.get_rgba() if self.camera is not None else None
        return np.array([] if data is None else data, dtype=np.uint8)

    def read_camera_depth(self) -> npt.NDArray[np.float32]:
        """Read a depth image, returning an empty array before a frame exists."""
        data = self.camera.get_depth() if self.camera is not None else None
        return np.array([] if data is None else data, dtype=np.float32)

    def read_lidar_3d_point_cloud(self) -> npt.NDArray[np.float32]:
        """Read the current 3D LiDAR point cloud on demand."""
        if self.lidar_3d_acquisition is not None:
            return self.lidar_3d_acquisition.read_point_cloud()
        pc = self.lidar_3d.get_point_cloud() if self.lidar_3d is not None else None
        if pc is None or len(pc) == 0:
            return np.empty((0, 3), dtype=np.float32)
        return np.array(pc, dtype=np.float32).reshape(-1, 3)

    def read_imu(self) -> dict[str, list[float]]:
        """Read the current IMU sample and warn when Mars gravity drifts."""
        try:
            from isaacsim.sensors.physics import _sensor
        except ImportError:  # pragma: no cover - compatibility for older Isaac builds
            from omni.isaac.sensor import _sensor

        imu_interface = _sensor.acquire_imu_sensor_interface()
        reading = imu_interface.get_sensor_reading(
            self.imu_prim_path,
            use_latest_data=True,
            read_gravity=True,
        )
        lin_acc = [
            float(reading.lin_acc_x),
            float(reading.lin_acc_y),
            float(reading.lin_acc_z),
        ]
        ang_vel = [
            float(reading.ang_vel_x),
            float(reading.ang_vel_y),
            float(reading.ang_vel_z),
        ]
        if abs(float(lin_acc[2]) - _MARS_GRAVITY_MS2) > _MARS_GRAVITY_TOL_WARN:
            _LOG.warning(
                "IMU z=%.2f m/s^2 deviates from Mars gravity %.2f m/s^2 "
                "(tolerance %.2f). Check PhysicsScene gravity and rover orientation.",
                float(lin_acc[2]),
                _MARS_GRAVITY_MS2,
                _MARS_GRAVITY_TOL_WARN,
            )
        return {"lin_acc": lin_acc, "ang_vel": ang_vel}


def spawn_sensors(
    stage: Any,
    sensors_cfg: dict[str, Any],
    ros2_cfg: dict[str, Any],
    rigid_body_path: str,
) -> SensorHandles:
    """Create one Camera, one 3D LiDAR, and one IMU for the rover."""
    camera_cfg = CameraConfig.model_validate(sensors_cfg["camera"])
    lidar_cfg = Lidar3DConfig.model_validate(sensors_cfg["lidar_3d"])
    imu_cfg = IMUConfig.model_validate(sensors_cfg["imu"])

    camera_handles = spawn_camera(stage, camera_cfg, rigid_body_path)
    lidar_handles = spawn_lidar_3d(stage, lidar_cfg, rigid_body_path)
    imu_handles = spawn_imu(
        stage,
        imu_cfg,
        rigid_body_path,
        float(ros2_cfg["rates"]["imu"]),
    )
    return SensorHandles(
        camera=camera_handles.camera,
        lidar_3d=lidar_handles.lidar,
        imu=imu_handles.imu,
        camera_prim_path=camera_handles.camera_prim_path,
        lidar_3d_prim_path=lidar_handles.lidar_prim_path,
        imu_prim_path=imu_handles.imu_prim_path,
        camera_acquisition=camera_handles,
        lidar_3d_acquisition=lidar_handles,
        imu_acquisition=imu_handles,
    )


__all__ = ["SensorHandles", "spawn_sensors"]
