"""Unit tests for marslab.robots.drive_api_setup. pxr stubbed."""

from __future__ import annotations

import sys
import types
from typing import Any, Dict, List

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fake pxr module wiring
# ---------------------------------------------------------------------------


class _FakeAttr:
    """Captures ``Set`` calls as ``(name, value)`` tuples on the owning prim."""

    def __init__(self, prim: "_FakePrim", name: str) -> None:
        self._prim = prim
        self._name = name
        prim.attrs[name] = None

    def Set(self, value: Any) -> None:  # noqa: N802 -- USD API name
        self._prim.attrs[self._name] = value


class _FakeDriveTypeAttr:
    def __init__(self, prim: "_FakePrim") -> None:
        self._prim = prim

    def Set(self, value: Any) -> None:  # noqa: N802
        self._prim.drive_type = value


class _FakeDriveAPI:
    """Mimics ``pxr.UsdPhysics.DriveAPI`` for a single angular drive."""

    applied_paths: List[str] = []

    def __init__(self, prim: "_FakePrim", token: str) -> None:
        self._prim = prim
        self._token = token

    @classmethod
    def Apply(cls, prim: "_FakePrim", token: str) -> "_FakeDriveAPI":  # noqa: N802
        prim.has_drive_api = True
        cls.applied_paths.append(prim.path)
        return cls(prim, token)

    def GetTypeAttr(self) -> _FakeDriveTypeAttr | None:  # noqa: N802
        # Returns an attr sentinel regardless; original behaviour lets the
        # caller fall back to CreateTypeAttr if falsy.  We always return a
        # truthy attr for the happy path (mirrors the production runtime code).
        return _FakeDriveTypeAttr(self._prim)

    def CreateTypeAttr(self) -> _FakeDriveTypeAttr:  # noqa: N802
        return _FakeDriveTypeAttr(self._prim)


class _FakePrim:
    def __init__(self, path: str, valid: bool = True) -> None:
        self.path = path
        self.valid = valid
        self.has_drive_api = False
        self.attrs: Dict[str, Any] = {}
        self.drive_type: Any = None

    def IsValid(self) -> bool:  # noqa: N802
        return self.valid

    def HasAPI(self, api_cls: Any, token: str) -> bool:  # noqa: N802
        return self.has_drive_api

    def CreateAttribute(self, name: str, type_name: Any) -> _FakeAttr:  # noqa: N802
        # Return existing _FakeAttr if already created so repeat writes map
        # to the same key in ``attrs``; simpler: just return a fresh wrapper
        # that shares the ``attrs`` dict.
        return _FakeAttr(self, name)


class _FakeStage:
    def __init__(self) -> None:
        self._prims: Dict[str, _FakePrim] = {}

    def GetPrimAtPath(self, path: str) -> _FakePrim:  # noqa: N802
        if path not in self._prims:
            self._prims[path] = _FakePrim(path, valid=True)
        return self._prims[path]


@pytest.fixture
def fake_pxr(monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
    """Install fake ``pxr`` / ``pxr.Sdf`` / ``pxr.UsdPhysics`` modules."""

    _FakeDriveAPI.applied_paths = []

    pxr_pkg = types.ModuleType("pxr")
    sdf_mod = types.ModuleType("pxr.Sdf")
    usd_physics_mod = types.ModuleType("pxr.UsdPhysics")

    class _VT:
        Float = "Float"

    sdf_mod.ValueTypeNames = _VT  # type: ignore[attr-defined]
    usd_physics_mod.DriveAPI = _FakeDriveAPI  # type: ignore[attr-defined]

    pxr_pkg.Sdf = sdf_mod  # type: ignore[attr-defined]
    pxr_pkg.UsdPhysics = usd_physics_mod  # type: ignore[attr-defined]

    for name, mod in (
        ("pxr", pxr_pkg),
        ("pxr.Sdf", sdf_mod),
        ("pxr.UsdPhysics", usd_physics_mod),
    ):
        monkeypatch.setitem(sys.modules, name, mod)

    return {"pxr": pxr_pkg, "Sdf": sdf_mod, "UsdPhysics": usd_physics_mod}


# ---------------------------------------------------------------------------
# Control-cfg fixtures
# ---------------------------------------------------------------------------


def _make_control_cfg(**overrides: Any) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "drive_joint_names": ["LF_DRIVE", "RF_DRIVE"],
        "steer_joint_names": ["LF_STEER", "RF_STEER"],
        "suspension_joint_names": ["LF_ROCKER", "RF_ROCKER"],
        "drive_damping": 1000.0,
        "drive_max_force": 500000.0,
        "steer_stiffness": 50000.0,
        "steer_damping": 5000.0,
        "steer_max_force": 100000.0,
        "suspension_damping": 0.0,
        "drive_type": "acceleration",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestApplyDriveAPI:
    def test_writes_stiffness_damping_maxforce_and_type(self, fake_pxr: Dict[str, Any]) -> None:
        from marslab.robots.drive_api_setup import _apply_drive_api

        stage = _FakeStage()
        joint_path = "/World/Rover/Body_Chassis/joints/LF_DRIVE"

        ok = _apply_drive_api(
            stage,
            joint_path,
            stiffness=0.0,
            damping=1000.0,
            max_force=500000.0,
            drive_type="acceleration",
        )

        assert ok is True
        prim = stage.GetPrimAtPath(joint_path)
        assert prim.attrs["drive:angular:physics:stiffness"] == pytest.approx(0.0)
        assert prim.attrs["drive:angular:physics:damping"] == pytest.approx(1000.0)
        assert prim.attrs["drive:angular:physics:maxForce"] == pytest.approx(500000.0)
        assert prim.drive_type == "acceleration"


class TestConfigureDrives:
    def test_drive_and_steer_joints_receive_expected_gains(self, fake_pxr: Dict[str, Any]) -> None:
        from marslab.robots.drive_api_setup import configure_drives

        stage = _FakeStage()
        chassis_path = "/World/Rover/Body_Chassis"
        cfg = _make_control_cfg()

        configure_drives(stage, chassis_path, cfg)

        # Drive joints: stiffness=0, damping=drive_damping.
        for name in cfg["drive_joint_names"]:
            prim = stage.GetPrimAtPath(f"{chassis_path}/joints/{name}")
            assert prim.attrs["drive:angular:physics:stiffness"] == pytest.approx(0.0)
            assert prim.attrs["drive:angular:physics:damping"] == pytest.approx(
                cfg["drive_damping"]
            )

        # Steer joints: stiffness=steer_stiffness.
        for name in cfg["steer_joint_names"]:
            prim = stage.GetPrimAtPath(f"{chassis_path}/joints/{name}")
            assert prim.attrs["drive:angular:physics:stiffness"] == pytest.approx(
                cfg["steer_stiffness"]
            )
            assert prim.attrs["drive:angular:physics:damping"] == pytest.approx(
                cfg["steer_damping"]
            )

    def test_joint_paths_use_chassis_joints_composition(self, fake_pxr: Dict[str, Any]) -> None:
        from marslab.robots.drive_api_setup import configure_drives

        stage = _FakeStage()
        chassis_path = "/World/Rover/Body_Chassis"
        cfg = _make_control_cfg()

        configure_drives(stage, chassis_path, cfg)

        expected_drive = f"{chassis_path}/joints/LF_DRIVE"
        expected_steer = f"{chassis_path}/joints/RF_STEER"
        assert expected_drive in stage._prims
        assert expected_steer in stage._prims

    def test_suspension_damping_zero_skips_suspension_joints(
        self, fake_pxr: Dict[str, Any]
    ) -> None:
        """When ``suspension_damping <= 0`` the suspension loop is skipped (L312 branch)."""
        from marslab.robots.drive_api_setup import configure_drives

        stage = _FakeStage()
        chassis_path = "/World/Rover/Body_Chassis"
        cfg = _make_control_cfg(suspension_damping=0.0)

        configure_drives(stage, chassis_path, cfg)

        for name in cfg["suspension_joint_names"]:
            assert f"{chassis_path}/joints/{name}" not in stage._prims


class TestReinforcePdGains:
    def test_kps_kds_populated_at_drive_and_steer_indices_only(
        self, fake_pxr: Dict[str, Any]
    ) -> None:
        from marslab.robots.drive_api_setup import reinforce_pd_gains

        dof_names = [
            "LF_ROCKER",
            "LF_STEER",
            "LF_DRIVE",
            "RF_ROCKER",
            "RF_STEER",
            "RF_DRIVE",
        ]
        cfg = _make_control_cfg()

        captured: Dict[str, Any] = {}

        class _FakeArticulation:
            def set_gains(self, kps: np.ndarray, kds: np.ndarray) -> None:
                captured["kps"] = np.asarray(kps).copy()
                captured["kds"] = np.asarray(kds).copy()
                captured["call_count"] = captured.get("call_count", 0) + 1

        reinforce_pd_gains(_FakeArticulation(), cfg, dof_names)

        assert captured["call_count"] == 1
        kps = captured["kps"]
        kds = captured["kds"]
        assert kps.shape == (1, len(dof_names))
        assert kds.shape == (1, len(dof_names))

        drive_idx = [dof_names.index(n) for n in cfg["drive_joint_names"]]
        steer_idx = [dof_names.index(n) for n in cfg["steer_joint_names"]]

        # Drive joints: kps=0, kds=drive_damping.
        for idx in drive_idx:
            assert kps[0, idx] == pytest.approx(0.0)
            assert kds[0, idx] == pytest.approx(cfg["drive_damping"])
        # Steer joints: kps=steer_stiffness, kds=steer_damping.
        for idx in steer_idx:
            assert kps[0, idx] == pytest.approx(cfg["steer_stiffness"])
            assert kds[0, idx] == pytest.approx(cfg["steer_damping"])
        # All other (suspension, rocker) indices must stay zero.
        other_idx = set(range(len(dof_names))) - set(drive_idx) - set(steer_idx)
        for idx in other_idx:
            assert kps[0, idx] == pytest.approx(0.0)
            assert kds[0, idx] == pytest.approx(0.0)


