"""Unit tests for :mod:`marslab.sensors.sensor_spawner`.

Isaac Sim is unavailable in the unit-test environment, so
``isaacsim.sensors.*`` and ``pxr`` are stubbed via ``sys.modules``
monkeypatching.  The tests exercise the orchestrator logic end-to-end:

* all four sensors active → every :class:`SensorHandles` field populated,
* ``lidar_2d`` absent → the 2D slot stays ``None``,
* camera with non-zero RPY → parent Xform path is constructed and the
  Camera prim is nested under it,
* camera with zero RPY → Camera prim path is a direct child of the
  rigid body,
* IMU frequency passed through from ``ros2_cfg["rates"]["imu"]``.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_stub_modules(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Install stub ``isaacsim.sensors.*`` + ``pxr`` in ``sys.modules``.

    Returns a ``captured`` dict the tests inspect to assert on call args.
    """
    captured: Dict[str, Any] = {
        "camera_calls": [],
        "camera_init_count": 0,
        "camera_focal_calls": [],
        "camera_clip_calls": [],
        "lidar_rtx_calls": [],
        "lidar_init_count": 0,
        "imu_calls": [],
        "imu_init_count": 0,
        "xform_define_calls": [],
        "xform_translate_sets": [],
        "xform_orient_sets": [],
        "xform_clear_called": 0,
    }

    # -- isaacsim.sensors.camera.Camera ----------------------------------
    class FakeCamera:
        def __init__(self, **kwargs: Any) -> None:
            captured["camera_calls"].append(kwargs)
            self.kwargs = kwargs

        def initialize(self) -> None:
            captured["camera_init_count"] += 1

        def set_focal_length(self, value: float) -> None:
            captured["camera_focal_calls"].append(value)

        def set_clipping_range(self, near: float, far: float) -> None:
            captured["camera_clip_calls"].append((near, far))

    cam_mod = types.ModuleType("isaacsim.sensors.camera")
    cam_mod.Camera = FakeCamera  # type: ignore[attr-defined]

    # -- isaacsim.sensors.physics.IMUSensor ------------------------------
    class FakeIMU:
        def __init__(self, **kwargs: Any) -> None:
            captured["imu_calls"].append(kwargs)
            self.kwargs = kwargs

        def initialize(self) -> None:
            captured["imu_init_count"] += 1

    phys_mod = types.ModuleType("isaacsim.sensors.physics")
    phys_mod.IMUSensor = FakeIMU  # type: ignore[attr-defined]

    # -- isaacsim.sensors.rtx.LidarRtx -----------------------------------
    class FakeLidarRtx:
        def __init__(self, **kwargs: Any) -> None:
            captured["lidar_rtx_calls"].append(kwargs)
            self.kwargs = kwargs

        def initialize(self) -> None:
            captured["lidar_init_count"] += 1

    rtx_mod = types.ModuleType("isaacsim.sensors.rtx")
    rtx_mod.LidarRtx = FakeLidarRtx  # type: ignore[attr-defined]

    # Ensure parent package entries exist so ``from isaacsim.sensors.rtx
    # import ...`` resolves cleanly.
    isaacsim_pkg = sys.modules.get("isaacsim") or types.ModuleType("isaacsim")
    sensors_pkg = types.ModuleType("isaacsim.sensors")

    monkeypatch.setitem(sys.modules, "isaacsim", isaacsim_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors", sensors_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.camera", cam_mod)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.physics", phys_mod)
    monkeypatch.setitem(sys.modules, "isaacsim.sensors.rtx", rtx_mod)

    # -- pxr.Gf + pxr.UsdGeom.Xform --------------------------------------
    class FakeVec3d:
        def __init__(self, *vals: float) -> None:
            self.vals = tuple(vals)

    class FakeQuatf:
        def __init__(self, w: float, x: float, y: float, z: float) -> None:
            self.values = (w, x, y, z)

    gf_mod = types.ModuleType("pxr.Gf")
    gf_mod.Vec3d = FakeVec3d  # type: ignore[attr-defined]
    gf_mod.Quatf = FakeQuatf  # type: ignore[attr-defined]

    class FakeTranslateOp:
        def Set(self, value: Any) -> None:  # noqa: N802 (USD API)
            captured["xform_translate_sets"].append(value)

    class FakeOrientOp:
        def Set(self, value: Any) -> None:  # noqa: N802 (USD API)
            captured["xform_orient_sets"].append(value)

    class FakeXform:
        def __init__(self, path: str) -> None:
            self.path = path

        def ClearXformOpOrder(self) -> None:  # noqa: N802 (USD API)
            captured["xform_clear_called"] += 1

        def AddTranslateOp(self) -> FakeTranslateOp:  # noqa: N802
            return FakeTranslateOp()

        def AddOrientOp(self) -> FakeOrientOp:  # noqa: N802
            return FakeOrientOp()

    class FakeXformFactory:
        @staticmethod
        def Define(stage: Any, path: str) -> FakeXform:  # noqa: N802
            captured["xform_define_calls"].append((stage, path))
            return FakeXform(path)

    usd_geom_mod = types.ModuleType("pxr.UsdGeom")
    usd_geom_mod.Xform = FakeXformFactory  # type: ignore[attr-defined]

    # ``Sdf`` is unused by sensor_spawner, but importing the package
    # ``marslab.sensors`` (triggered by the ``from marslab.sensors.sensor_spawner``
    # statement) executes ``marslab/sensors/__init__.py`` which in turn
    # imports ``marslab.sensors.lidar`` — the latter has a top-level
    # ``from pxr import Gf, Sdf, UsdGeom``.  Provide a placeholder so the
    # package import resolves offline.
    sdf_mod = types.ModuleType("pxr.Sdf")

    pxr_pkg = types.ModuleType("pxr")
    pxr_pkg.Gf = gf_mod  # type: ignore[attr-defined]
    pxr_pkg.UsdGeom = usd_geom_mod  # type: ignore[attr-defined]
    pxr_pkg.Sdf = sdf_mod  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "pxr", pxr_pkg)
    monkeypatch.setitem(sys.modules, "pxr.Gf", gf_mod)
    monkeypatch.setitem(sys.modules, "pxr.UsdGeom", usd_geom_mod)
    monkeypatch.setitem(sys.modules, "pxr.Sdf", sdf_mod)

    # Reset cached sensor package imports so function-local imports pick
    # up the stubbed modules on every test.  ``marslab.sensors`` itself
    # is cleared because its ``__init__`` imports ``marslab.sensors.lidar``
    # which in turn pulls ``pxr`` — those must be re-resolved against the
    # stubs inside this fixture.
    for mod in (
        "marslab.sensors",
        "marslab.sensors.sensor_spawner",
        "marslab.sensors.camera",
        "marslab.sensors.imu",
        "marslab.sensors.lidar",
    ):
        sys.modules.pop(mod, None)
    return captured


def _base_cfgs() -> Dict[str, Any]:
    """Return a representative ``sensors_cfg`` + ``ros2_cfg`` pair."""
    sensors_cfg = {
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
        "lidar_2d": {
            "profile": "Example_Rotary_2D",
            "local_translation": [0.0, 0.0, 0.3],
        },
        "imu": {
            "local_translation": [0.0, 0.0, 0.4],
        },
    }
    ros2_cfg = {
        "rates": {"imu": 200},
        "namespace": "rover_0",
    }
    return {"sensors_cfg": sensors_cfg, "ros2_cfg": ros2_cfg}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestSpawnSensors:
    def test_all_four_sensors_populate_every_handle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _make_stub_modules(monkeypatch)
        from marslab.sensors.sensor_spawner import SensorHandles, spawn_sensors

        cfgs = _base_cfgs()
        handles = spawn_sensors(
            stage=object(),
            sensors_cfg=cfgs["sensors_cfg"],
            ros2_cfg=cfgs["ros2_cfg"],
            rigid_body_path="/World/Rover",
        )

        assert isinstance(handles, SensorHandles)
        assert handles.camera is not None
        assert handles.lidar_3d is not None
        assert handles.lidar_2d is not None
        assert handles.imu is not None
        assert handles.camera_prim_path == "/World/Rover/stage1_camera"
        assert handles.lidar_3d_prim_path == "/World/Rover/stage1_lidar"
        assert handles.lidar_2d_prim_path == "/World/Rover/stage1_lidar_2d"
        assert handles.imu_prim_path == "/World/Rover/stage1_imu"

    def test_missing_lidar_2d_leaves_slot_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _make_stub_modules(monkeypatch)
        from marslab.sensors.sensor_spawner import spawn_sensors

        cfgs = _base_cfgs()
        cfgs["sensors_cfg"].pop("lidar_2d")

        handles = spawn_sensors(
            stage=object(),
            sensors_cfg=cfgs["sensors_cfg"],
            ros2_cfg=cfgs["ros2_cfg"],
            rigid_body_path="/World/Rover",
        )

        assert handles.lidar_2d is None
        assert handles.lidar_2d_prim_path is None
        # Only the 3D LiDAR should have been constructed.
        assert len(captured["lidar_rtx_calls"]) == 1
        assert captured["lidar_rtx_calls"][0]["config_file_name"] == "Example_Rotary"

    def test_camera_with_nonzero_rpy_uses_parent_xform(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _make_stub_modules(monkeypatch)
        from marslab.sensors.sensor_spawner import spawn_sensors

        cfgs = _base_cfgs()
        cfgs["sensors_cfg"]["camera"]["local_orientation_rpy_deg"] = [0.0, -15.0, 0.0]

        handles = spawn_sensors(
            stage=object(),
            sensors_cfg=cfgs["sensors_cfg"],
            ros2_cfg=cfgs["ros2_cfg"],
            rigid_body_path="/World/Rover",
        )

        # Parent Xform created under the rigid body and the camera nested
        # one level deeper so no xformOps touch the Camera prim itself.
        assert captured["xform_define_calls"], "parent Xform must be Defined"
        _stage, parent_path = captured["xform_define_calls"][0]
        assert parent_path == "/World/Rover/stage1_camera_xform"
        assert handles.camera_prim_path == ("/World/Rover/stage1_camera_xform/stage1_camera")
        # Xform was zeroed, translated, and oriented exactly once.
        assert captured["xform_clear_called"] == 1
        assert len(captured["xform_translate_sets"]) == 1
        assert len(captured["xform_orient_sets"]) == 1
        # Camera constructor must receive translation=None (parent Xform owns it).
        assert captured["camera_calls"][0]["translation"] is None

    def test_camera_with_zero_rpy_direct_child(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _make_stub_modules(monkeypatch)
        from marslab.sensors.sensor_spawner import spawn_sensors

        cfgs = _base_cfgs()
        # All components are zero ⇒ no parent Xform needed.
        cfgs["sensors_cfg"]["camera"]["local_orientation_rpy_deg"] = [0.0, 0.0, 0.0]

        handles = spawn_sensors(
            stage=object(),
            sensors_cfg=cfgs["sensors_cfg"],
            ros2_cfg=cfgs["ros2_cfg"],
            rigid_body_path="/World/Rover",
        )

        assert handles.camera_prim_path == "/World/Rover/stage1_camera"
        # No parent Xform must be created when the orientation is zero.
        assert captured["xform_define_calls"] == []
        # Translation ends up on the Camera constructor.
        assert captured["camera_calls"][0]["translation"] is not None

    def test_imu_frequency_comes_from_ros2_rates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured = _make_stub_modules(monkeypatch)
        from marslab.sensors.sensor_spawner import spawn_sensors

        cfgs = _base_cfgs()
        cfgs["ros2_cfg"]["rates"]["imu"] = 137  # deliberately odd so we catch typos.

        spawn_sensors(
            stage=object(),
            sensors_cfg=cfgs["sensors_cfg"],
            ros2_cfg=cfgs["ros2_cfg"],
            rigid_body_path="/World/Rover",
        )

        assert len(captured["imu_calls"]) == 1
        assert captured["imu_calls"][0]["frequency"] == 137
