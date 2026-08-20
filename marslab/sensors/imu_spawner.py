"""Create and initialize the rover IMU sensor.
Mars gravity is checked before the prim is attached.
The returned handle is independent of ROS transport."""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from marslab.config.schema.rover_sensors import IMUConfig

_MARS_GRAVITY_MS2 = 3.72
_MARS_GRAVITY_TOL_STRICT = 0.05
_LOG = logging.getLogger(__name__)


class _StageHandle(Protocol):
    def Traverse(self) -> Iterable["_PrimHandle"]: ...


class _PrimHandle(Protocol):
    def IsA(self, schema: type) -> bool: ...


class _IMUHandle(Protocol):
    def initialize(self) -> None: ...


@dataclass(frozen=True, slots=True)
class IMUSpawnHandles:
    """Live IMU handle and its USD prim path."""

    imu: _IMUHandle
    imu_prim_path: str


def _rpy_deg_to_quat_wxyz(rpy_deg: Iterable[float]) -> tuple[float, float, float, float]:
    """Convert ZYX roll-pitch-yaw degrees to a WXYZ quaternion."""
    values = list(rpy_deg)
    if len(values) != 3:
        raise ValueError(
            f"orientation rpy must have 3 entries (roll, pitch, yaw deg); got {values!r}"
        )
    roll, pitch, yaw = (math.radians(float(value)) for value in values)
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    return (
        float(cr * cp * cy + sr * sp * sy),
        float(sr * cp * cy - cr * sp * sy),
        float(cr * sp * cy + sr * cp * sy),
        float(cr * cp * sy - sr * sp * cy),
    )


def _assert_mars_gravity(
    stage: _StageHandle | None,
    expected: float = _MARS_GRAVITY_MS2,
    tol: float = _MARS_GRAVITY_TOL_STRICT,
) -> None:
    """Reject an authored physics scene whose gravity is not Mars gravity."""
    if stage is None or not hasattr(stage, "Traverse"):
        return

    try:
        from pxr import UsdPhysics
    except ImportError:  # pragma: no cover - Isaac runtime supplies pxr
        return

    scene = None
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.Scene):
            scene = UsdPhysics.Scene(prim)
            break
    if scene is None:
        _LOG.warning("IMU gravity assertion skipped: no UsdPhysics.Scene found on stage")
        return

    magnitude_attr = scene.GetGravityMagnitudeAttr()
    magnitude = magnitude_attr.Get() if magnitude_attr is not None else None
    if magnitude is None or not math.isfinite(float(magnitude)):
        _LOG.warning(
            "IMU gravity assertion: UsdPhysics.Scene reports sentinel magnitude (%r); "
            "relying on PhysicsContext.set_gravity instead",
            magnitude,
        )
        return

    magnitude = abs(float(magnitude))
    if not expected - tol <= magnitude <= expected + tol:
        raise ValueError(
            "IMU gravity assertion failed: UsdPhysics.Scene gravity magnitude "
            f"{magnitude:.3f} m/s^2 outside Mars range "
            f"[{expected - tol:.3f}, {expected + tol:.3f}] m/s^2."
        )


def spawn_imu(
    stage: _StageHandle,
    imu_cfg: IMUConfig,
    chassis_path: str,
    frequency_hz: float,
) -> IMUSpawnHandles:
    """Create and initialize one IMU prim from the typed sensor config."""
    from isaacsim.sensors.physics import IMUSensor
    from pxr import Gf, UsdGeom

    _assert_mars_gravity(stage)
    orientation = imu_cfg.local_orientation_rpy_deg
    has_orientation = any(abs(value) > 0.01 for value in orientation)
    if has_orientation:
        qw, qx, qy, qz = _rpy_deg_to_quat_wxyz(orientation)
        xform_path = f"{chassis_path}/imu_xform"
        xform = UsdGeom.Xform.Define(stage, xform_path)
        xform.ClearXformOpOrder()
        xform.AddTranslateOp().Set(Gf.Vec3d(*map(float, imu_cfg.local_translation)))
        xform.AddOrientOp().Set(Gf.Quatf(qw, qx, qy, qz))
        imu_prim_path = f"{xform_path}/imu"
        translation = np.zeros(3, dtype=np.float32)
        _LOG.info("IMU parent Xform: %s rpy_deg=%s", xform_path, orientation)
    else:
        imu_prim_path = f"{chassis_path}/imu"
        translation = np.asarray(imu_cfg.local_translation, dtype=np.float32)

    imu = IMUSensor(
        prim_path=imu_prim_path,
        translation=translation,
        frequency=int(frequency_hz),
    )
    imu.initialize()
    return IMUSpawnHandles(imu=imu, imu_prim_path=imu_prim_path)


__all__ = ["IMUSpawnHandles", "spawn_imu"]
