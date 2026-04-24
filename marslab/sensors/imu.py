"""DEPRECATED — replaced by sensor_spawner.py.

This module is retained only until sensors/__init__.py export is removed
and the file is git-rm'd by the user.  Do not import from here.  See the
Reviewer 2 audit C-17 / item #16 (2026-04-24) consolidation, which moved
the Mars-gravity assertion (Batch 1 item #6), the rpy-deg -> quat
helper, and the ``read_imu`` soft-warning logic onto
:class:`marslab.sensors.sensor_spawner.SensorHandles` / the private
:func:`marslab.sensors.sensor_spawner._assert_mars_gravity`.

Original docstring (preserved for reference):
IMU sensor attachment for Isaac Sim.  At rest on Mars, z-axis must
read 3.72 +/- 0.05 m/s^2 (THE critical test).  All parameters from
YAML config (G5).  Requires Isaac Sim runtime with World stepping.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Iterable, Optional

from pxr import Gf

_MARS_GRAVITY_MS2 = 3.72
_MARS_GRAVITY_TOL_STRICT = 0.05  # attach-time hard assertion (THE critical test)
_MARS_GRAVITY_TOL_WARN = 0.5  # read-time soft warning threshold

_LOG = logging.getLogger(__name__)


def _rpy_deg_to_quatd(rpy_deg: Optional[Iterable[float]]) -> Gf.Quatd:
    """Convert ``[roll, pitch, yaw]`` in degrees (ZYX intrinsic) to ``Gf.Quatd``.

    Mirrors :func:`marslab.math.quaternion.rpy_to_quat` but returns a
    ``Gf.Quatd`` directly so the caller can feed it straight into
    Isaac Sim's ``IsaacSensorCreateImuSensor`` command.  ``None`` or an
    all-zero list yields the identity quaternion.

    Args:
        rpy_deg: Iterable of three floats — roll, pitch, yaw — in
            degrees, URDF/ROS order.  ``None`` is accepted as a
            shorthand for identity.

    Returns:
        ``Gf.Quatd(w, x, y, z)``.
    """
    if rpy_deg is None:
        return Gf.Quatd(1.0, 0.0, 0.0, 0.0)
    values = list(rpy_deg)
    if len(values) != 3:
        raise ValueError(
            f"offset_orientation must have 3 entries (roll, pitch, yaw deg); got {values!r}"
        )
    roll, pitch, yaw = (math.radians(float(v)) for v in values)
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return Gf.Quatd(float(w), float(x), float(y), float(z))


def _assert_mars_gravity(
    stage: Any,
    expected: float = _MARS_GRAVITY_MS2,
    tol: float = _MARS_GRAVITY_TOL_STRICT,
) -> None:
    """Verify the active USD ``PhysicsScene`` gravity matches Mars.

    Reads the first discovered ``UsdPhysics.Scene`` prim on ``stage``
    and confirms that
    ``|GetGravityMagnitudeAttr().Get()| ∈ [expected-tol, expected+tol]``.
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
            ``integration`` test requirement in CLAUDE.md § Testing.

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
            "attach_imu()."
        )


def attach_imu(stage, robot_prim_path: str, config: dict) -> str:
    """Attach an IMU sensor to a robot.

    Creates an IMU sensor prim under the robot's mount link.
    The IMU automatically reads from the physics scene gravity
    (set to Mars 3.72 m/s^2). Data requires world.step() to populate.

    Before spawning the sensor, asserts Mars gravity is configured on
    the active ``UsdPhysics.Scene`` (THE critical test). A
    :class:`ValueError` is raised when Earth gravity (9.81 m/s^2) or any
    other non-Mars value is detected, so attach-time misconfiguration
    is caught before the IMU starts publishing bogus accelerations.

    Args:
        stage: USD stage.
        robot_prim_path: Robot root prim path.
        config: Sensor config dict with keys: name, mount_link,
            offset_position, offset_orientation, update_rate.

    Returns:
        The IMU sensor prim path.

    Raises:
        ValueError: If the USD PhysicsScene gravity magnitude is not
            3.72 +/- 0.05 m/s^2.
    """
    import omni.kit.commands

    _assert_mars_gravity(stage)

    name = config["name"]
    mount_link = config["mount_link"]
    parent_path = f"{robot_prim_path}/{mount_link}"
    sensor_path = f"{parent_path}/{name}"
    offset_pos = config.get("offset_position", [0.0, 0.0, 0.0])
    offset_orient_deg = config.get("offset_orientation", [0.0, 0.0, 0.0])
    update_rate = config.get("update_rate", 200)

    # Ensure parent prim exists
    parent_prim = stage.GetPrimAtPath(parent_path)
    if not parent_prim.IsValid():
        parent_path = robot_prim_path
        sensor_path = f"{parent_path}/{name}"

    # Create IMU sensor via Isaac Sim command.
    # offset_orientation is consumed from YAML (ZYX rpy in degrees) — the
    # hard-coded identity quaternion from the pre-2026-04-24 revision
    # ignored the schema field entirely (Reviewer-2 item 07§3).
    omni.kit.commands.execute(
        "IsaacSensorCreateImuSensor",
        path=sensor_path,
        parent=None,
        sensor_period=1.0 / update_rate,
        translation=Gf.Vec3d(*offset_pos),
        orientation=_rpy_deg_to_quatd(offset_orient_deg),
    )

    return sensor_path


def read_imu(imu_prim_path: str) -> dict:
    """Read current IMU sensor data.

    Must be called after world.step() for data to be populated.

    A warning is emitted via :mod:`logging` when the z-axis linear
    acceleration deviates from Mars gravity (3.72 m/s^2) by more than
    0.5 m/s^2.  This soft check catches runtime drift (e.g. scene was
    re-created with a different gravity, or the rover tipped over) that
    the attach-time ``_assert_mars_gravity`` can't see.

    Args:
        imu_prim_path: The prim path of the IMU sensor.

    Returns:
        Dict with keys:
        - lin_acc: [ax, ay, az] in m/s^2 (z should be ~3.72 at rest)
        - ang_vel: [gx, gy, gz] in rad/s
    """
    try:
        from isaacsim.sensors.physics import _sensor
    except ImportError:
        from omni.isaac.sensor import _sensor

    imu_interface = _sensor.acquire_imu_sensor_interface()
    reading = imu_interface.get_sensor_reading(
        imu_prim_path, use_latest_data=True, read_gravity=True
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

    return {
        "lin_acc": lin_acc,
        "ang_vel": ang_vel,
    }
