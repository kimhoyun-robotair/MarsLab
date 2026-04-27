"""Unit tests for the IMU Mars-gravity invariants -- THE critical test.

The hard assertion / soft warning / offset_orientation plumbing now
lives on the unified :mod:`marslab.sensors.sensor_spawner` surface:

* :func:`marslab.sensors.sensor_spawner._assert_mars_gravity`.
* :meth:`marslab.sensors.sensor_spawner.SensorHandles.read_imu` --
  soft warning when z-axis deviates from Mars gravity by more than
  0.5 m/s^2.
* IMU parent-Xform ``local_orientation_rpy_deg`` plumbing + the
  attach-time hard gravity assertion are checked against the full
  :func:`spawn_sensors` entry point using the same stub strategy as
  :mod:`tests.unit.test_sensor_spawner`.

Mock strategy (one sentence): we install minimal stub modules for
``pxr`` / ``pxr.UsdPhysics`` / ``isaacsim.sensors.*`` via
``monkeypatch.setitem(sys.modules, ...)`` so
``marslab.sensors.sensor_spawner`` can be imported and exercised with
zero Isaac-Sim dependencies.
"""

from __future__ import annotations

import logging
import math
import sys
import types
from typing import Any, Dict, List, Optional

import pytest


# ---------------------------------------------------------------------------
# pxr / UsdPhysics stubs (gravity-assertion side)
# ---------------------------------------------------------------------------
class _StubQuatd:
    def __init__(self, w: float, x: float, y: float, z: float) -> None:
        self.values = (float(w), float(x), float(y), float(z))

    def __repr__(self) -> str:  # pragma: no cover - debug aid only
        return f"_StubQuatd{self.values}"


class _StubVec3d:
    def __init__(self, *vals: float) -> None:
        self.values = tuple(float(v) for v in vals)


class _StubQuatf:
    def __init__(self, w: float, x: float, y: float, z: float) -> None:
        self.values = (float(w), float(x), float(y), float(z))


class _StubPhysicsSceneInstance:
    """Stands in for an instantiated ``UsdPhysics.Scene(prim)`` wrapper."""

    def __init__(self, magnitude: Optional[float]) -> None:
        self._magnitude = magnitude

    def GetGravityMagnitudeAttr(self) -> Any:  # noqa: N802 (USD API)
        if self._magnitude is None:
            return None

        class _MagAttr:
            def __init__(self, value: Optional[float]) -> None:
                self._value = value

            def Get(self) -> Optional[float]:  # noqa: N802 (USD API)
                return self._value

        return _MagAttr(self._magnitude)


class _StubPrim:
    def __init__(self, is_scene: bool) -> None:
        self._is_scene = is_scene
        self.valid = True

    def IsA(self, schema: Any) -> bool:  # noqa: N802 (USD API)
        return self._is_scene and schema is _StubPhysicsScene

    def IsValid(self) -> bool:  # noqa: N802 (USD API)
        return self.valid


class _StubPhysicsScene:
    """Callable shim: ``UsdPhysics.Scene(prim)`` -> _StubPhysicsSceneInstance."""

    magnitude: Optional[float] = 3.72

    def __new__(cls, prim: Any) -> _StubPhysicsSceneInstance:  # type: ignore[misc]
        return _StubPhysicsSceneInstance(cls.magnitude)


class _StubStage:
    def __init__(self, has_physics_scene: bool = True) -> None:
        self._prims: List[_StubPrim] = []
        if has_physics_scene:
            self._prims.append(_StubPrim(is_scene=True))
        self._mount = _StubPrim(is_scene=False)

    def Traverse(self) -> List[_StubPrim]:  # noqa: N802 (USD API)
        return list(self._prims)

    def GetPrimAtPath(self, path: str) -> _StubPrim:  # noqa: N802 (USD API)
        return self._mount


# ---------------------------------------------------------------------------
# isaacsim.sensors / pxr.UsdGeom stubs (spawn side)
# ---------------------------------------------------------------------------
class _FakeCamera:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def initialize(self) -> None:
        pass

    def set_focal_length(self, value: float) -> None:
        pass

    def set_clipping_range(self, near: float, far: float) -> None:
        pass


class _FakeLidarRtx:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def initialize(self) -> None:
        pass


class _FakeIMU:
    last_instance: Optional["_FakeIMU"] = None

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        _FakeIMU.last_instance = self

    def initialize(self) -> None:
        pass


class _FakeTranslateOp:
    def __init__(self) -> None:
        self.value: Any = None

    def Set(self, value: Any) -> None:  # noqa: N802 (USD API)
        self.value = value


class _FakeOrientOp:
    def __init__(self) -> None:
        self.value: Any = None

    def Set(self, value: Any) -> None:  # noqa: N802 (USD API)
        self.value = value


class _FakeXform:
    def __init__(self, path: str, captured: Dict[str, Any]) -> None:
        self.path = path
        self._captured = captured

    def ClearXformOpOrder(self) -> None:  # noqa: N802 (USD API)
        self._captured.setdefault("xform_clear_called", 0)
        self._captured["xform_clear_called"] += 1

    def AddTranslateOp(self) -> _FakeTranslateOp:  # noqa: N802
        op = _FakeTranslateOp()
        self._captured.setdefault("xform_translate_ops", []).append((self.path, op))
        return op

    def AddOrientOp(self) -> _FakeOrientOp:  # noqa: N802
        op = _FakeOrientOp()
        self._captured.setdefault("xform_orient_ops", []).append((self.path, op))
        return op


def _install_spawn_stubs(
    monkeypatch: pytest.MonkeyPatch, magnitude: Optional[float] = 3.72
) -> Dict[str, Any]:
    """Wire ``pxr`` + ``isaacsim.sensors.*`` stubs suitable for ``spawn_sensors``."""
    captured: Dict[str, Any] = {"xform_define_calls": []}

    class _FakeXformFactory:
        @staticmethod
        def Define(stage: Any, path: str) -> _FakeXform:  # noqa: N802
            captured["xform_define_calls"].append((stage, path))
            return _FakeXform(path, captured)

    # pxr --------------------------------------------------------------
    gf_mod = types.ModuleType("pxr.Gf")
    gf_mod.Quatd = _StubQuatd  # type: ignore[attr-defined]
    gf_mod.Quatf = _StubQuatf  # type: ignore[attr-defined]
    gf_mod.Vec3d = _StubVec3d  # type: ignore[attr-defined]

    usd_physics_mod = types.ModuleType("pxr.UsdPhysics")
    _StubPhysicsScene.magnitude = magnitude
    usd_physics_mod.Scene = _StubPhysicsScene  # type: ignore[attr-defined]

    usd_geom_mod = types.ModuleType("pxr.UsdGeom")
    usd_geom_mod.Xform = _FakeXformFactory  # type: ignore[attr-defined]

    sdf_mod = types.ModuleType("pxr.Sdf")

    pxr_pkg = types.ModuleType("pxr")
    pxr_pkg.Gf = gf_mod  # type: ignore[attr-defined]
    pxr_pkg.UsdPhysics = usd_physics_mod  # type: ignore[attr-defined]
    pxr_pkg.UsdGeom = usd_geom_mod  # type: ignore[attr-defined]
    pxr_pkg.Sdf = sdf_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pxr", pxr_pkg)
    monkeypatch.setitem(sys.modules, "pxr.Gf", gf_mod)
    monkeypatch.setitem(sys.modules, "pxr.UsdPhysics", usd_physics_mod)
    monkeypatch.setitem(sys.modules, "pxr.UsdGeom", usd_geom_mod)
    monkeypatch.setitem(sys.modules, "pxr.Sdf", sdf_mod)

    # isaacsim.sensors.* ----------------------------------------------
    cam_mod = types.ModuleType("isaacsim.sensors.camera")
    cam_mod.Camera = _FakeCamera  # type: ignore[attr-defined]
    rtx_mod = types.ModuleType("isaacsim.sensors.rtx")
    rtx_mod.LidarRtx = _FakeLidarRtx  # type: ignore[attr-defined]
    phys_mod = types.ModuleType("isaacsim.sensors.physics")
    phys_mod.IMUSensor = _FakeIMU  # type: ignore[attr-defined]

    isaacsim_pkg = sys.modules.get("isaacsim") or types.ModuleType("isaacsim")
    sensors_pkg = types.ModuleType("isaacsim.sensors")

    monkeypatch.setitem(sys.modules, "isaacsim", isaacsim_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors", sensors_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.camera", cam_mod)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.rtx", rtx_mod)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.physics", phys_mod)

    for mod_name in (
        "marslab.sensors",
        "marslab.sensors.sensor_spawner",
    ):
        sys.modules.pop(mod_name, None)

    return captured


def _install_physics_sensor_stub(monkeypatch: pytest.MonkeyPatch, lin_acc_z: float) -> None:
    """Stub ``isaacsim.sensors.physics._sensor`` so ``read_imu`` returns ``lin_acc_z``."""

    class _Reading:
        def __init__(self, z: float) -> None:
            self.lin_acc_x = 0.0
            self.lin_acc_y = 0.0
            self.lin_acc_z = z
            self.ang_vel_x = 0.0
            self.ang_vel_y = 0.0
            self.ang_vel_z = 0.0

    class _Interface:
        def get_sensor_reading(self, *_a: Any, **_k: Any) -> _Reading:
            return _Reading(lin_acc_z)

    sensor_mod = types.ModuleType("isaacsim.sensors.physics._sensor")
    sensor_mod.acquire_imu_sensor_interface = lambda: _Interface()  # type: ignore[attr-defined]

    sensors_physics_pkg = sys.modules.get("isaacsim.sensors.physics") or types.ModuleType(
        "isaacsim.sensors.physics"
    )
    sensors_physics_pkg._sensor = sensor_mod  # type: ignore[attr-defined]

    isaacsim_pkg = sys.modules.get("isaacsim") or types.ModuleType("isaacsim")
    sensors_pkg = sys.modules.get("isaacsim.sensors") or types.ModuleType("isaacsim.sensors")

    monkeypatch.setitem(sys.modules, "isaacsim", isaacsim_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors", sensors_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.physics", sensors_physics_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.physics._sensor", sensor_mod)


def _base_cfgs() -> Dict[str, Any]:
    sensors_cfg: Dict[str, Any] = {
        "camera": {
            "resolution": [1280, 720],
            "focal_length": 24.0,
            "clipping_range": [0.1, 1000.0],
            "local_translation": [0.5, 0.0, 1.2],
            "local_orientation_rpy_deg": [0.0, 0.0, 0.0],
        },
        "lidar_3d": {
            "profile": "Example_Rotary",
            "local_translation": [0.0, 0.0, 1.5],
        },
        "imu": {
            "local_translation": [0.0, 0.0, 0.4],
            "local_orientation_rpy_deg": [0.0, 0.0, 0.0],
        },
    }
    ros2_cfg = {"rates": {"imu": 200}, "namespace": "rover"}
    return {"sensors_cfg": sensors_cfg, "ros2_cfg": ros2_cfg}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestAssertMarsGravity:
    def test_assert_mars_gravity_passes_with_3_72(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """3.72 m/s^2 is inside the 0.05 tolerance and must not raise."""
        _install_spawn_stubs(monkeypatch, magnitude=3.72)
        from marslab.sensors.sensor_spawner import _assert_mars_gravity

        _assert_mars_gravity(_StubStage())

    def test_assert_mars_gravity_raises_with_earth_gravity(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """9.81 m/s^2 (Earth) must raise ``ValueError`` — THE critical test."""
        _install_spawn_stubs(monkeypatch, magnitude=9.81)
        from marslab.sensors.sensor_spawner import _assert_mars_gravity

        with pytest.raises(ValueError) as exc_info:
            _assert_mars_gravity(_StubStage())
        msg = str(exc_info.value)
        assert "9.810" in msg or "9.81" in msg
        assert "3.72" in msg
        assert "Mars" in msg

    def test_assert_mars_gravity_none_stage_is_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``stage=None`` is the offline-unit-test escape hatch — no raise."""
        _install_spawn_stubs(monkeypatch, magnitude=9.81)  # would fail if checked
        from marslab.sensors.sensor_spawner import _assert_mars_gravity

        _assert_mars_gravity(None)

    def test_assert_mars_gravity_sentinel_magnitude_is_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``-inf`` sentinel (Isaac Sim default) warns and returns without raising."""
        _install_spawn_stubs(monkeypatch, magnitude=float("-inf"))
        from marslab.sensors.sensor_spawner import _assert_mars_gravity

        _assert_mars_gravity(_StubStage())


class TestReadImuRangeWarning:
    def test_read_imu_range_warning_on_wrong_gravity(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Earth-gravity reading (9.81) emits a WARNING mentioning 3.72."""
        _install_spawn_stubs(monkeypatch, magnitude=3.72)
        _install_physics_sensor_stub(monkeypatch, lin_acc_z=9.81)
        from marslab.sensors.sensor_spawner import SensorHandles

        handles = SensorHandles(
            camera=None,
            lidar_3d=None,
            lidar_2d=None,
            imu=object(),
            camera_prim_path="/World/Rover/camera",
            lidar_3d_prim_path="/World/Rover/lidar_3d",
            lidar_2d_prim_path=None,
            imu_prim_path="/World/Rover/imu",
        )

        caplog.set_level(logging.WARNING)
        caplog.set_level(logging.WARNING, logger="marslab.sensors.sensor_spawner")
        logging.getLogger("marslab.sensors.sensor_spawner").propagate = True
        data = handles.read_imu()
        assert data["lin_acc"][2] == pytest.approx(9.81)
        msgs = [rec.getMessage() for rec in caplog.records]
        assert any(
            "deviates from Mars gravity" in m and "3.72" in m for m in msgs
        ), f"expected warning not found in {msgs!r}"

    def test_read_imu_no_warning_at_mars_gravity(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Reading of ~3.72 must NOT emit the deviation warning."""
        _install_spawn_stubs(monkeypatch, magnitude=3.72)
        _install_physics_sensor_stub(monkeypatch, lin_acc_z=3.74)
        from marslab.sensors.sensor_spawner import SensorHandles

        handles = SensorHandles(
            camera=None,
            lidar_3d=None,
            lidar_2d=None,
            imu=object(),
            camera_prim_path="/World/Rover/camera",
            lidar_3d_prim_path="/World/Rover/lidar_3d",
            lidar_2d_prim_path=None,
            imu_prim_path="/World/Rover/imu",
        )

        caplog.set_level(logging.WARNING, logger="marslab.sensors.sensor_spawner")
        handles.read_imu()
        assert not any("deviates from Mars gravity" in rec.message for rec in caplog.records)


class TestIMUOrientationAndAttachTimeAssertion:
    def test_imu_offset_orientation_applied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Non-zero IMU ``local_orientation_rpy_deg`` builds a parent Xform.

        The pre-consolidation Path A hard-coded ``Gf.Quatd(1, 0, 0, 0)``; the
        modern Path B applies the orientation via a dedicated parent Xform
        (matching the camera pattern) so the rover YAML is uniform.  45 deg
        yaw must produce ``(cos 22.5, 0, 0, sin 22.5)`` within FP tolerance.
        """
        captured = _install_spawn_stubs(monkeypatch, magnitude=3.72)
        from marslab.sensors.sensor_spawner import spawn_sensors

        cfgs = _base_cfgs()
        cfgs["sensors_cfg"]["imu"]["local_orientation_rpy_deg"] = [0.0, 0.0, 45.0]

        handles = spawn_sensors(
            stage=_StubStage(),
            sensors_cfg=cfgs["sensors_cfg"],
            ros2_cfg=cfgs["ros2_cfg"],
            rigid_body_path="/World/Rover",
        )

        # Parent Xform path defined at the expected location, IMU nested beneath.
        defined_paths = [p for _, p in captured["xform_define_calls"]]
        assert "/World/Rover/imu_xform" in defined_paths
        assert handles.imu_prim_path == "/World/Rover/imu_xform/imu"

        # Orient op received the expected quaternion (cos 22.5, 0, 0, sin 22.5).
        imu_orient_ops = [
            op for path, op in captured.get("xform_orient_ops", []) if "imu_xform" in path
        ]
        assert len(imu_orient_ops) == 1
        quat = imu_orient_ops[0].value
        assert isinstance(quat, _StubQuatf)
        w, x, y, z = quat.values
        assert math.isclose(w, math.cos(math.radians(22.5)), abs_tol=1e-9)
        assert math.isclose(x, 0.0, abs_tol=1e-9)
        assert math.isclose(y, 0.0, abs_tol=1e-9)
        assert math.isclose(z, math.sin(math.radians(22.5)), abs_tol=1e-9)

    def test_imu_orientation_defaults_to_identity(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Zero ``local_orientation_rpy_deg`` keeps the IMU as a direct child."""
        captured = _install_spawn_stubs(monkeypatch, magnitude=3.72)
        from marslab.sensors.sensor_spawner import spawn_sensors

        cfgs = _base_cfgs()
        # Key already [0, 0, 0] in _base_cfgs — no parent Xform expected.

        handles = spawn_sensors(
            stage=_StubStage(),
            sensors_cfg=cfgs["sensors_cfg"],
            ros2_cfg=cfgs["ros2_cfg"],
            rigid_body_path="/World/Rover",
        )

        assert handles.imu_prim_path == "/World/Rover/imu"
        # No IMU parent Xform should have been defined.
        assert not any("imu_xform" in p for _, p in captured["xform_define_calls"])

    def test_spawn_sensors_raises_on_earth_gravity_scene(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``spawn_sensors`` refuses to attach the IMU when gravity is 9.81 m/s^2."""
        _install_spawn_stubs(monkeypatch, magnitude=9.81)
        from marslab.sensors.sensor_spawner import spawn_sensors

        cfgs = _base_cfgs()
        with pytest.raises(ValueError, match="Mars"):
            spawn_sensors(
                stage=_StubStage(),
                sensors_cfg=cfgs["sensors_cfg"],
                ros2_cfg=cfgs["ros2_cfg"],
                rigid_body_path="/World/Rover",
            )
