"""Attach the Stage 3 rover sensor rig (camera + 3D LiDAR + IMU).

Extracted from ``scripts/phase1/run_stage1.py`` so the Stage 3 runtime
can build the full sensor payload in one call and hand the resulting
handles to the ROS2 sensor-graph builder.

Design notes
------------

* The camera must have its orientation applied on a **parent Xform**,
  not on the Camera prim itself — any ``AddOrientOp`` / ``set_local_pose``
  on the Camera corrupts the RTX depth pipeline.  This is the same
  pattern Stage 1 validated; see ``work_log/rover_generation/``.
* All sensors attach under the moving RigidBodyAPI child path returned
  by :func:`marslab.robots.rover.find_rigid_body_path` — parenting
  under the static outer Xform leaves the sensors frozen in world space.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

import numpy as np


@dataclass
class RoverSensorRig:
    """Bundle of sensor handles/prim paths produced by the rig builder."""

    camera: Any
    camera_prim_path: str
    lidar_3d: Any
    lidar_3d_prim_path: str
    imu: Any
    imu_prim_path: str


def _build_camera(
    stage: Any,
    camera_cfg: Dict[str, Any],
    rigid_body_path: str,
) -> tuple[Any, str]:
    """Attach the RGB+Depth camera to a parent Xform that carries the pose."""
    from isaacsim.sensors.camera import Camera
    from pxr import Gf, UsdGeom

    from marslab.robots.rover import rpy_to_quat

    orient_deg = camera_cfg.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])
    has_orient = any(abs(float(v)) > 0.01 for v in orient_deg)
    local_translation = tuple(camera_cfg["local_translation"])

    if has_orient:
        qw, qx, qy, qz = rpy_to_quat(
            np.radians(float(orient_deg[0])),
            np.radians(float(orient_deg[1])),
            np.radians(float(orient_deg[2])),
        )
        parent_path = f"{rigid_body_path}/stage3_camera_xform"
        parent = UsdGeom.Xform.Define(stage, parent_path)
        parent.ClearXformOpOrder()
        t_op = parent.AddTranslateOp()
        t_op.Set(
            Gf.Vec3d(
                float(local_translation[0]),
                float(local_translation[1]),
                float(local_translation[2]),
            )
        )
        o_op = parent.AddOrientOp()
        o_op.Set(Gf.Quatf(float(qw), float(qx), float(qy), float(qz)))
        camera_prim_path = f"{parent_path}/stage3_camera"
        camera = Camera(
            prim_path=camera_prim_path,
            resolution=tuple(camera_cfg["resolution"]),
            # Translation/orientation live on the parent Xform.
            translation=None,
        )
    else:
        camera_prim_path = f"{rigid_body_path}/stage3_camera"
        camera = Camera(
            prim_path=camera_prim_path,
            resolution=tuple(camera_cfg["resolution"]),
            translation=np.asarray(local_translation, dtype=np.float32),
        )

    camera.initialize()
    # Isaac Sim focal_length is in cm internally; the YAML stores mm.
    camera.set_focal_length(float(camera_cfg["focal_length"]) / 10.0)
    clip = camera_cfg.get("clipping_range", [0.1, 1000.0])
    camera.set_clipping_range(float(clip[0]), float(clip[1]))
    return camera, camera_prim_path


def _build_lidar_3d(
    lidar_cfg: Dict[str, Any],
    rigid_body_path: str,
) -> tuple[Any, str]:
    """Attach the 360° RTX LiDAR (3D point cloud)."""
    from isaacsim.sensors.rtx import LidarRtx

    prim_path = f"{rigid_body_path}/stage3_lidar_3d"
    lidar = LidarRtx(
        prim_path=prim_path,
        config_file_name=str(lidar_cfg["profile"]),
        translation=np.asarray(lidar_cfg["local_translation"], dtype=np.float32),
    )
    lidar.initialize()
    return lidar, prim_path


def _build_imu(
    imu_cfg: Dict[str, Any],
    rigid_body_path: str,
    rate_hz: int,
) -> tuple[Any, str]:
    """Attach the IMU sensor."""
    from isaacsim.sensors.physics import IMUSensor

    prim_path = f"{rigid_body_path}/stage3_imu"
    imu = IMUSensor(
        prim_path=prim_path,
        translation=np.asarray(imu_cfg["local_translation"], dtype=np.float32),
        frequency=int(rate_hz),
    )
    imu.initialize()
    return imu, prim_path


def attach_rover_sensor_rig(
    stage: Any,
    sensors_cfg: Dict[str, Any],
    rigid_body_path: str,
    ros2_rates: Dict[str, int],
) -> RoverSensorRig:
    """Create the full Stage-3 sensor rig under ``rigid_body_path``.

    Args:
        stage: USD stage handle.
        sensors_cfg: The merged ``rover.sensors`` block.  Expected keys:
            ``camera``, ``lidar_3d`` (or legacy ``lidar``), ``imu``.
        rigid_body_path: USD path to the moving RigidBodyAPI prim
            returned by :func:`marslab.robots.rover.find_rigid_body_path`.
        ros2_rates: Rate table from the rover config (Hz per sensor).

    Returns:
        :class:`RoverSensorRig` carrying Isaac-Sim sensor handles and
        the prim paths used by the OmniGraph builder.
    """
    camera_cfg = sensors_cfg["camera"]
    imu_cfg = sensors_cfg["imu"]
    # Backwards compatibility with the Stage 1 ``lidar`` key.
    lidar_3d_cfg = sensors_cfg.get("lidar_3d", sensors_cfg.get("lidar"))
    if lidar_3d_cfg is None:
        raise KeyError("sensors config missing lidar_3d (or legacy 'lidar') entry")

    camera, cam_path = _build_camera(stage, camera_cfg, rigid_body_path)
    lidar3d, lidar3d_path = _build_lidar_3d(lidar_3d_cfg, rigid_body_path)
    imu, imu_path = _build_imu(imu_cfg, rigid_body_path, int(ros2_rates.get("imu", 100)))

    return RoverSensorRig(
        camera=camera,
        camera_prim_path=cam_path,
        lidar_3d=lidar3d,
        lidar_3d_prim_path=lidar3d_path,
        imu=imu,
        imu_prim_path=imu_path,
    )
