"""Single orchestrator facade for Stage-3 sensor spawn.

This module centralises the camera / LiDAR-3D / LiDAR-2D / IMU
instantiation that previously lived inline in
``scripts/phase1/run_stage3_monolithic_new.py``

The logic is a verbatim port of the original block — only the
function-local imports were moved here so the runtime script no longer
needs the three ``isaacsim.sensors.*`` top-level references.  The
``isaacsim.*`` / ``pxr.*`` imports are kept inside :func:`spawn_sensors`
so that importing this module does not require Isaac Sim to be running
(P3 offline-first testing).

Per R4-2 of the MarsLab refactoring plan, this file is the only place
that knows how the four physical sensors are attached to the rover.
The :class:`SensorHandles` dataclass exposes both the live sensor
objects (needed to feed ``get_current_frame`` / ``initialize`` call
sites further down in the runtime) and their USD prim paths (needed
later by the OmniGraph sensor_graph orchestrator).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class SensorHandles:
    """Populated sensor objects and their USD prim paths.

    Attributes:
        camera: Live :class:`isaacsim.sensors.camera.Camera` handle.
        lidar_3d: Live :class:`isaacsim.sensors.rtx.LidarRtx` handle
            for the 3D Velodyne-style rotary LiDAR.
        lidar_2d: Live :class:`isaacsim.sensors.rtx.LidarRtx` handle
            for the 2D LaserScan LiDAR, or ``None`` if
            ``sensors_cfg["lidar_2d"]`` is absent.
        imu: Live :class:`isaacsim.sensors.physics.IMUSensor` handle.
        camera_prim_path: Full USD prim path of the camera — either
            ``{rigid_body_path}/stage1_camera`` or, if the camera has
            non-zero RPY, nested under a parent Xform.
        lidar_3d_prim_path: USD prim path of the 3D LiDAR.
        lidar_2d_prim_path: USD prim path of the 2D LiDAR, or ``None``
            if the 2D LiDAR was not spawned.
        imu_prim_path: USD prim path of the IMU.
    """

    camera: Any
    lidar_3d: Any
    lidar_2d: Optional[Any]
    imu: Any
    camera_prim_path: str
    lidar_3d_prim_path: str
    lidar_2d_prim_path: Optional[str]
    imu_prim_path: str


def spawn_sensors(
    stage: Any,
    sensors_cfg: Dict[str, Any],
    ros2_cfg: Dict[str, Any],
    rigid_body_path: str,
) -> SensorHandles:
    """Spawn the rover's camera, 3D LiDAR, optional 2D LiDAR, and IMU.

    The behaviour is bit-identical to the previous inline block in
    ``run_stage3_monolithic_new.py`` §7.17:

    * Camera orientation is applied via a **parent Xform** when any
      ``local_orientation_rpy_deg`` component exceeds ``0.01`` deg.
      Placing xformOps on the Camera prim itself corrupts the RTX
      depth pipeline (vertical striping), so the translation +
      orientation live on a dedicated ``stage1_camera_xform`` parent
      and the camera prim has no xformOps of its own.
    * 3D LiDAR uses the profile *name* (e.g. ``"Example_Rotary"``) via
      :class:`isaacsim.sensors.rtx.LidarRtx.config_file_name`, never a
      filesystem path.
    * 2D LiDAR is only spawned if ``sensors_cfg.get("lidar_2d")`` is
      truthy, mirroring the optional-block guard.
    * IMU frequency is sourced from ``ros2_cfg["rates"]["imu"]`` so the
      sensor's internal integration aligns with the ROS2 publish rate.

    Args:
        stage: Live USD stage (from ``omni.usd.get_context().get_stage()``
            in the runtime script).
        sensors_cfg: ``scenario["rover"]["sensors"]`` block.  Must
            contain ``camera``, ``imu``, and either ``lidar_3d`` or
            ``lidar`` (legacy key).  ``lidar_2d`` is optional.
        ros2_cfg: ``scenario["ros2"]`` block — only ``rates.imu`` is
            read here.
        rigid_body_path: USD prim path of the rover's rigid body (IMU /
            LiDAR / camera are attached under this path).

    Returns:
        Fully initialised :class:`SensorHandles`.

    Raises:
        KeyError: If required cfg keys (``camera``, ``imu``,
            ``lidar_3d``/``lidar``) are missing.
    """
    # Function-local imports: these modules require the Kit app to be
    # live, so importing them at module scope would break offline
    # unit tests.  ``rpy_to_quat`` is imported from
    # ``marslab.robots.rover`` on purpose — it is a re-export of
    # ``marslab.math.quaternion.rpy_to_quat`` that keeps the existing
    # import surface (see marslab/robots/rover.py L39).
    import numpy as np
    from isaacsim.sensors.camera import Camera
    from isaacsim.sensors.physics import IMUSensor
    from isaacsim.sensors.rtx import LidarRtx
    from pxr import Gf, UsdGeom

    from marslab.robots.rover import rpy_to_quat

    camera_cfg, imu_cfg = sensors_cfg["camera"], sensors_cfg["imu"]
    # Stage-3 uses "lidar_3d"; Stage-1 phase1.yaml used "lidar". Accept both.
    lidar_cfg = sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar")

    # Camera orientation strategy: ANY xformOp modification on the Camera
    # prim itself corrupts the RTX depth pipeline (vertical striping).
    # Tested and failed: constructor orientation, AddOrientOp, set_local_pose.
    # Fix: place translation + orientation on a PARENT Xform prim. The Camera
    # prim has no xformOps of its own, but inherits the correct world-space
    # transform from the parent chain.
    cam_orient_deg = camera_cfg.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])
    has_cam_orient = any(abs(v) > 0.01 for v in cam_orient_deg)

    if has_cam_orient:
        cam_qw, cam_qx, cam_qy, cam_qz = rpy_to_quat(
            np.radians(float(cam_orient_deg[0])),
            np.radians(float(cam_orient_deg[1])),
            np.radians(float(cam_orient_deg[2])),
        )
        camera_xform_path = f"{rigid_body_path}/stage1_camera_xform"
        camera_xform = UsdGeom.Xform.Define(stage, camera_xform_path)
        camera_xform.ClearXformOpOrder()
        cx_translate = camera_xform.AddTranslateOp()
        cx_translate.Set(Gf.Vec3d(*[float(x) for x in camera_cfg["local_translation"]]))
        cx_orient = camera_xform.AddOrientOp()
        cx_orient.Set(Gf.Quatf(float(cam_qw), float(cam_qx), float(cam_qy), float(cam_qz)))
        camera_prim_path = f"{camera_xform_path}/stage1_camera"
        print(
            f"[run_stage3_mono] Camera parent Xform: {camera_xform_path} "
            f"rpy_deg={cam_orient_deg}",
            flush=True,
        )
    else:
        camera_prim_path = f"{rigid_body_path}/stage1_camera"

    camera = Camera(
        prim_path=camera_prim_path,
        resolution=tuple(camera_cfg["resolution"]),
        # Translation/orientation on parent Xform if oriented, else on Camera.
        translation=(
            None
            if has_cam_orient
            else np.asarray(camera_cfg["local_translation"], dtype=np.float32)
        ),
    )
    camera.initialize()
    camera.set_focal_length(float(camera_cfg["focal_length"]) / 10.0)
    camera.set_clipping_range(
        float(camera_cfg["clipping_range"][0]), float(camera_cfg["clipping_range"][1])
    )

    lidar_prim_path = f"{rigid_body_path}/stage1_lidar"
    lidar_3d = LidarRtx(
        prim_path=lidar_prim_path,
        config_file_name=lidar_cfg["profile"],
        translation=np.asarray(lidar_cfg["local_translation"], dtype=np.float32),
    )
    lidar_3d.initialize()

    # 2D LiDAR (LaserScan) — optional, mirrors the 3D LiDAR pipeline.
    # config_file_name receives the Isaac-Sim bundled profile *name* only
    # (e.g. "Example_Rotary_2D"), never a filesystem path (§10.8 regression).
    lidar_2d_cfg = sensors_cfg.get("lidar_2d")
    lidar_2d: Optional[Any] = None
    lidar_2d_prim_path: Optional[str] = None
    if lidar_2d_cfg is not None:
        lidar_2d_prim_path = f"{rigid_body_path}/stage1_lidar_2d"
        lidar_2d = LidarRtx(
            prim_path=lidar_2d_prim_path,
            config_file_name=lidar_2d_cfg["profile"],
            translation=np.asarray(lidar_2d_cfg["local_translation"], dtype=np.float32),
        )
        lidar_2d.initialize()
        print(
            f"[run_stage3_mono] 2D LiDAR attached at {lidar_2d_prim_path} "
            f"profile='{lidar_2d_cfg['profile']}'",
            flush=True,
        )

    imu_prim_path = f"{rigid_body_path}/stage1_imu"
    imu = IMUSensor(
        prim_path=imu_prim_path,
        translation=np.asarray(imu_cfg["local_translation"], dtype=np.float32),
        frequency=int(ros2_cfg["rates"]["imu"]),
    )
    imu.initialize()

    return SensorHandles(
        camera=camera,
        lidar_3d=lidar_3d,
        lidar_2d=lidar_2d,
        imu=imu,
        camera_prim_path=camera_prim_path,
        lidar_3d_prim_path=lidar_prim_path,
        lidar_2d_prim_path=lidar_2d_prim_path,
        imu_prim_path=imu_prim_path,
    )


__all__ = ["SensorHandles", "spawn_sensors"]
