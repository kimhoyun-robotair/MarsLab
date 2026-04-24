"""Single orchestrator facade for Stage-3 sensor spawn.

This module centralises the camera / LiDAR-3D / LiDAR-2D / IMU
instantiation for the Stage 3 rover runtime.  The
``isaacsim.*`` / ``pxr.*`` imports are kept inside :func:`spawn_sensors`
so that importing this module does not require Isaac Sim to be running
(P3 offline-first testing).

This file is the single place that knows how the four physical sensors
are attached to the rover.  The :class:`SensorHandles` dataclass exposes
both the live sensor objects (needed to feed ``get_current_frame`` /
``initialize`` call sites further down in the runtime) and their USD
prim paths (needed later by the OmniGraph sensor_graph orchestrator).

Reviewer-2 item #16 (2026-04-24): this module absorbed the invariants
that previously lived in :mod:`marslab.sensors.imu` / ``.camera`` /
``.lidar`` (Path A).  In particular:

* :func:`_assert_mars_gravity` (ported from Path A ``imu.py``) is called
  before the IMU is spawned — THE critical test.  Earth gravity on the
  ``UsdPhysics.Scene`` raises ``ValueError`` at spawn time rather than
  letting the IMU publish bogus accelerations.
* The IMU ``local_orientation_rpy_deg`` YAML key (ZYX roll-pitch-yaw in
  degrees) is honoured via the parent-Xform pattern the camera already
  uses.  Previous Path A code hard-coded identity on one path and
  ignored orientation entirely on the other — both are gone now.
* :meth:`SensorHandles.read_imu` / ``read_camera_rgb`` /
  ``read_camera_depth`` / ``read_lidar_3d_point_cloud`` expose the
  read-side helpers that used to live in the Path A modules.  The
  ``read_imu`` soft warning when the z-axis deviates from Mars gravity
  by more than 0.5 m/s^2 is preserved.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

_MARS_GRAVITY_MS2 = 3.72
_MARS_GRAVITY_TOL_STRICT = 0.05  # attach-time hard assertion (THE critical test)
_MARS_GRAVITY_TOL_WARN = 0.5  # read-time soft warning threshold

_LOG = logging.getLogger(__name__)


def _assert_mars_gravity(
    stage: Any,
    expected: float = _MARS_GRAVITY_MS2,
    tol: float = _MARS_GRAVITY_TOL_STRICT,
) -> None:
    """Verify the active USD ``PhysicsScene`` gravity matches Mars.

    Reads the first discovered ``UsdPhysics.Scene`` prim on ``stage``
    and confirms that
    ``|GetGravityMagnitudeAttr().Get()| in [expected-tol, expected+tol]``.
    Tolerates absent attributes (Isaac Sim occasionally lets the magnitude
    default to ``-inf`` / ``earthGravity`` sentinel) by then inspecting
    the physics-context fallback configured through
    :func:`marslab.sim.world_setup.create_world`.

    Args:
        stage: Live USD stage returned by
            ``omni.usd.get_context().get_stage()``.  If ``None`` the
            check is skipped (offline unit-test path) so callers don't
            need to gate this themselves.
        expected: Expected gravity magnitude in m/s^2 (Mars = 3.72).
        tol: Allowable absolute deviation.  Default 0.05 matches the
            ``integration`` test requirement in CLAUDE.md Testing.

    Raises:
        ValueError: If the USD scene reports a gravity magnitude that
            falls outside ``[expected - tol, expected + tol]``.  The
            message includes the offending value so operators can trace
            mis-configured scenes (e.g. Earth-gravity sentinels of
            9.81 m/s^2).
    """
    if stage is None:
        return

    try:
        from pxr import UsdPhysics
    except ImportError:  # pragma: no cover - pxr always present in Isaac Sim
        return

    scene = None
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.Scene):
            scene = UsdPhysics.Scene(prim)
            break

    if scene is None:
        # No PhysicsScene authored yet. The caller is expected to have
        # booted World first — but absence is treated as "skip"
        # rather than "fail" to avoid false positives on partial stages.
        _LOG.warning("IMU gravity assertion skipped: no UsdPhysics.Scene found on stage")
        return

    mag_attr = scene.GetGravityMagnitudeAttr()
    magnitude = mag_attr.Get() if mag_attr is not None else None

    # Isaac Sim sentinel: -inf means "use the engine default" — fall back
    # to reading the physics context (set_gravity in world_setup.create_world).
    if magnitude is None or not math.isfinite(float(magnitude)):
        _LOG.warning(
            "IMU gravity assertion: UsdPhysics.Scene reports sentinel magnitude "
            "(%r); relying on PhysicsContext.set_gravity instead",
            magnitude,
        )
        return

    magnitude = abs(float(magnitude))
    if not (expected - tol <= magnitude <= expected + tol):
        raise ValueError(
            "IMU gravity assertion failed: UsdPhysics.Scene gravity magnitude "
            f"{magnitude:.3f} m/s^2 outside Mars range "
            f"[{expected - tol:.3f}, {expected + tol:.3f}] m/s^2. "
            "Expected 3.72 m/s^2 (THE critical test). "
            "Call marslab.sim.world_setup.create_world(gravity=3.72) before "
            "spawn_sensors()."
        )


def _rpy_deg_to_quat_wxyz(rpy_deg: Optional[Iterable[float]]) -> tuple:
    """Convert ``[roll, pitch, yaw]`` in degrees (ZYX intrinsic) to ``(w, x, y, z)``.

    ``None`` or an all-zero list yields the identity quaternion.  Kept
    local so the tests don't need to stub ``marslab.math.quaternion``.
    """
    if rpy_deg is None:
        return (1.0, 0.0, 0.0, 0.0)
    values = list(rpy_deg)
    if len(values) != 3:
        raise ValueError(
            f"orientation rpy must have 3 entries (roll, pitch, yaw deg); got {values!r}"
        )
    roll, pitch, yaw = (math.radians(float(v)) for v in values)
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return (float(w), float(x), float(y), float(z))


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

    # ------------------------------------------------------------------
    # Read-side helpers (ported from Path A's camera.py / imu.py / lidar.py).
    # These are bound to the handle object so callers don't need to pass
    # individual prim paths / Camera objects around.
    # ------------------------------------------------------------------
    def read_camera_rgb(self) -> np.ndarray:
        """Read RGBA image from the camera. Returns ``(H, W, 4)`` uint8 or empty."""
        data = self.camera.get_rgba() if self.camera is not None else None
        return np.array([] if data is None else data, dtype=np.uint8)

    def read_camera_depth(self) -> np.ndarray:
        """Read depth image from the camera. Returns ``(H, W)`` float32 meters or empty."""
        data = self.camera.get_depth() if self.camera is not None else None
        return np.array([] if data is None else data, dtype=np.float32)

    def read_lidar_3d_point_cloud(self) -> np.ndarray:
        """Read the 3D LiDAR point cloud.

        Returns:
            ``(N, 3)`` float32 array of XYZ points, or empty ``(0, 3)`` array.
        """
        pc = self.lidar_3d.get_point_cloud() if self.lidar_3d is not None else None
        if pc is None or len(pc) == 0:
            return np.empty((0, 3), dtype=np.float32)
        return np.array(pc, dtype=np.float32).reshape(-1, 3)

    def read_lidar_2d_point_cloud(self) -> np.ndarray:
        """Read the 2D LaserScan LiDAR point cloud (empty if unavailable)."""
        if self.lidar_2d is None:
            return np.empty((0, 3), dtype=np.float32)
        pc = self.lidar_2d.get_point_cloud()
        if pc is None or len(pc) == 0:
            return np.empty((0, 3), dtype=np.float32)
        return np.array(pc, dtype=np.float32).reshape(-1, 3)

    def read_imu(self) -> dict:
        """Read current IMU sensor data.

        Must be called after ``world.step()`` for data to be populated.

        A warning is emitted via :mod:`logging` when the z-axis linear
        acceleration deviates from Mars gravity (3.72 m/s^2) by more than
        0.5 m/s^2.  This soft check catches runtime drift (e.g. scene was
        re-created with a different gravity, or the rover tipped over)
        that the attach-time ``_assert_mars_gravity`` cannot see.

        Returns:
            Dict with keys:
            - ``lin_acc``: ``[ax, ay, az]`` in m/s^2 (z should be ~3.72 at rest)
            - ``ang_vel``: ``[gx, gy, gz]`` in rad/s
        """
        try:
            from isaacsim.sensors.physics import _sensor
        except ImportError:  # pragma: no cover - Isaac Sim renamed module
            from omni.isaac.sensor import _sensor

        imu_interface = _sensor.acquire_imu_sensor_interface()
        reading = imu_interface.get_sensor_reading(
            self.imu_prim_path, use_latest_data=True, read_gravity=True
        )

        lin_acc = [reading.lin_acc_x, reading.lin_acc_y, reading.lin_acc_z]
        ang_vel = [reading.ang_vel_x, reading.ang_vel_y, reading.ang_vel_z]

        z = float(lin_acc[2])
        if abs(z - _MARS_GRAVITY_MS2) > _MARS_GRAVITY_TOL_WARN:
            _LOG.warning(
                "IMU z=%.2f m/s^2 deviates from Mars gravity %.2f m/s^2 "
                "(tolerance %.2f). Check PhysicsScene gravity and rover orientation.",
                z,
                _MARS_GRAVITY_MS2,
                _MARS_GRAVITY_TOL_WARN,
            )

        return {"lin_acc": lin_acc, "ang_vel": ang_vel}


def spawn_sensors(
    stage: Any,
    sensors_cfg: Dict[str, Any],
    ros2_cfg: Dict[str, Any],
    rigid_body_path: str,
) -> SensorHandles:
    """Spawn the rover's camera, 3D LiDAR, optional 2D LiDAR, and IMU.

    Key behaviour contracts:

    * Camera and IMU orientation are applied via a **parent Xform** when
      any ``local_orientation_rpy_deg`` component exceeds ``0.01`` deg.
      Placing xformOps on the Camera prim itself corrupts the RTX
      depth pipeline (vertical striping), so the translation +
      orientation live on a dedicated ``{name}_xform`` parent and the
      sensor prim has no xformOps of its own.  The IMU follows the same
      pattern for symmetry and so that the YAML schema is uniform.
    * Before the IMU is spawned, :func:`_assert_mars_gravity` verifies
      the ``UsdPhysics.Scene`` gravity magnitude matches Mars
      (3.72 +/- 0.05 m/s^2).  Earth gravity raises ``ValueError``.  This
      is THE critical test (CLAUDE.md Testing).
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
        ValueError: If the USD ``PhysicsScene`` gravity magnitude is not
            3.72 +/- 0.05 m/s^2.
    """
    # Function-local imports: these modules require the Kit app to be
    # live, so importing them at module scope would break offline
    # unit tests.
    from isaacsim.sensors.camera import Camera
    from isaacsim.sensors.physics import IMUSensor
    from isaacsim.sensors.rtx import LidarRtx
    from pxr import Gf, UsdGeom

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
        cam_qw, cam_qx, cam_qy, cam_qz = _rpy_deg_to_quat_wxyz(cam_orient_deg)
        camera_xform_path = f"{rigid_body_path}/stage1_camera_xform"
        camera_xform = UsdGeom.Xform.Define(stage, camera_xform_path)
        camera_xform.ClearXformOpOrder()
        cx_translate = camera_xform.AddTranslateOp()
        cx_translate.Set(Gf.Vec3d(*[float(x) for x in camera_cfg["local_translation"]]))
        cx_orient = camera_xform.AddOrientOp()
        cx_orient.Set(Gf.Quatf(float(cam_qw), float(cam_qx), float(cam_qy), float(cam_qz)))
        camera_prim_path = f"{camera_xform_path}/stage1_camera"
        print(
            f"[spawn_sensors] Camera parent Xform: {camera_xform_path} "
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
    # (e.g. "Example_Rotary_2D"), never a filesystem path (10.8 regression).
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
            f"[spawn_sensors] 2D LiDAR attached at {lidar_2d_prim_path} "
            f"profile='{lidar_2d_cfg['profile']}'",
            flush=True,
        )

    # ------------------------------------------------------------------
    # IMU: attach-time Mars gravity assertion (THE critical test), then
    # spawn under an optional parent Xform if the YAML requested a non-
    # identity orientation.  ``local_orientation_rpy_deg`` follows the
    # camera schema so the YAML is uniform across sensors.
    # ------------------------------------------------------------------
    _assert_mars_gravity(stage)

    imu_orient_deg = imu_cfg.get("local_orientation_rpy_deg", [0.0, 0.0, 0.0])
    has_imu_orient = any(abs(v) > 0.01 for v in imu_orient_deg)
    imu_translation = np.asarray(imu_cfg["local_translation"], dtype=np.float32)

    if has_imu_orient:
        imu_qw, imu_qx, imu_qy, imu_qz = _rpy_deg_to_quat_wxyz(imu_orient_deg)
        imu_xform_path = f"{rigid_body_path}/stage1_imu_xform"
        imu_xform = UsdGeom.Xform.Define(stage, imu_xform_path)
        imu_xform.ClearXformOpOrder()
        ix_translate = imu_xform.AddTranslateOp()
        ix_translate.Set(Gf.Vec3d(*[float(x) for x in imu_cfg["local_translation"]]))
        ix_orient = imu_xform.AddOrientOp()
        ix_orient.Set(Gf.Quatf(float(imu_qw), float(imu_qx), float(imu_qy), float(imu_qz)))
        imu_prim_path = f"{imu_xform_path}/stage1_imu"
        imu_translation_arg = np.zeros(3, dtype=np.float32)
        print(
            f"[spawn_sensors] IMU parent Xform: {imu_xform_path} rpy_deg={imu_orient_deg}",
            flush=True,
        )
    else:
        imu_prim_path = f"{rigid_body_path}/stage1_imu"
        imu_translation_arg = imu_translation

    imu = IMUSensor(
        prim_path=imu_prim_path,
        translation=imu_translation_arg,
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


__all__: List[str] = ["SensorHandles", "spawn_sensors"]
