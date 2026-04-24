"""Unit tests for marslab.sim.world_setup.create_world (Isaac Sim stubbed)."""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest


@pytest.fixture
def fake_world_env(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Install fake ``omni.usd`` + ``isaacsim.core.api`` + ``pxr`` stubs."""

    captured: dict = {
        "world_ctor": None,
        "gravity": None,
        "solver_type": None,
        "stage_attrs": {},
    }

    # ---- omni + omni.usd -------------------------------------------------
    omni_pkg = types.ModuleType("omni")
    omni_usd_pkg = types.ModuleType("omni.usd")

    class _FakeAttr:
        def __init__(self, path: str, name: str, type_name: Any) -> None:
            self.path = path
            self.name = name
            self.type_name = type_name

        def Set(self, value: Any) -> None:
            captured["stage_attrs"][f"{self.path}:{self.name}"] = value

    class _FakePrim:
        def __init__(self, path: str, valid: bool = True) -> None:
            self.path = path
            self._valid = valid

        def IsValid(self) -> bool:
            return self._valid

        def CreateAttribute(self, name: str, type_name: Any) -> _FakeAttr:
            return _FakeAttr(self.path, name, type_name)

    class _FakeStage:
        def __init__(self, valid_prims: bool = True) -> None:
            self._valid_prims = valid_prims

        def GetPrimAtPath(self, path: str) -> _FakePrim:
            return _FakePrim(path, valid=self._valid_prims)

    class _FakeContext:
        def __init__(self, stage_has_physics: bool) -> None:
            self._stage = _FakeStage(valid_prims=stage_has_physics)

        def get_stage(self) -> _FakeStage:
            return self._stage

    def get_context() -> _FakeContext:
        return captured["_context"]  # type: ignore[index]

    captured["_context"] = _FakeContext(stage_has_physics=True)
    omni_usd_pkg.get_context = get_context  # type: ignore[attr-defined]
    omni_pkg.usd = omni_usd_pkg  # type: ignore[attr-defined]

    # ---- isaacsim.core.api.World ----------------------------------------
    isaacsim_pkg = types.ModuleType("isaacsim")
    core_pkg = types.ModuleType("isaacsim.core")
    api_pkg = types.ModuleType("isaacsim.core.api")

    class _FakePhysicsContext:
        def set_gravity(self, g: float) -> None:
            captured["gravity"] = float(g)

        def set_solver_type(self, t: str) -> None:
            captured["solver_type"] = str(t)

    class _FakeWorld:
        def __init__(self, **kwargs: Any) -> None:
            captured["world_ctor"] = dict(kwargs)

        def get_physics_context(self) -> _FakePhysicsContext:
            return _FakePhysicsContext()

    api_pkg.World = _FakeWorld  # type: ignore[attr-defined]

    # ---- pxr.Sdf.ValueTypeNames ----------------------------------------
    pxr_pkg = types.ModuleType("pxr")
    sdf_mod = types.ModuleType("pxr.Sdf")

    class _VT:
        Int = "Int"

    sdf_mod.ValueTypeNames = _VT  # type: ignore[attr-defined]
    pxr_pkg.Sdf = sdf_mod  # type: ignore[attr-defined]

    for name, mod in [
        ("omni", omni_pkg),
        ("omni.usd", omni_usd_pkg),
        ("isaacsim", isaacsim_pkg),
        ("isaacsim.core", core_pkg),
        ("isaacsim.core.api", api_pkg),
        ("pxr", pxr_pkg),
        ("pxr.Sdf", sdf_mod),
    ]:
        monkeypatch.setitem(sys.modules, name, mod)

    return captured


class TestCreateWorld:
    def test_gravity_sign_is_always_negative(self, fake_world_env: dict) -> None:
        from marslab.sim.world_setup import create_world

        create_world(physics_dt=1 / 60.0, gravity=3.72)
        assert fake_world_env["gravity"] == pytest.approx(-3.72)

    def test_gravity_magnitude_normalised_when_caller_passes_negative(
        self, fake_world_env: dict
    ) -> None:
        from marslab.sim.world_setup import create_world

        create_world(physics_dt=1 / 60.0, gravity=-3.72)
        assert fake_world_env["gravity"] == pytest.approx(-3.72)

    def test_world_ctor_receives_physics_dt_for_both_axes(self, fake_world_env: dict) -> None:
        from marslab.sim.world_setup import create_world

        create_world(physics_dt=1 / 120.0, gravity=3.72)
        ctor = fake_world_env["world_ctor"]
        assert ctor["physics_dt"] == pytest.approx(1 / 120.0)
        assert ctor["rendering_dt"] == pytest.approx(1 / 120.0)
        assert ctor["stage_units_in_meters"] == 1.0

    def test_solver_iteration_counts_applied_to_physicsScene(self, fake_world_env: dict) -> None:
        from marslab.sim.world_setup import create_world

        create_world(
            physics_dt=1 / 60.0,
            gravity=3.72,
            solver_position_iteration_count=32,
            solver_velocity_iteration_count=8,
        )
        attrs = fake_world_env["stage_attrs"]
        assert attrs["/physicsScene:physxScene:solverPositionIterationCount"] == 32
        assert attrs["/physicsScene:physxScene:solverVelocityIterationCount"] == 8

    def test_default_solver_counts_match_stage3_runtime(self, fake_world_env: dict) -> None:
        from marslab.sim.world_setup import create_world

        create_world(physics_dt=1 / 60.0, gravity=3.72)
        attrs = fake_world_env["stage_attrs"]
        assert attrs["/physicsScene:physxScene:solverPositionIterationCount"] == 16
        assert attrs["/physicsScene:physxScene:solverVelocityIterationCount"] == 4

    def test_solver_type_passed_through(self, fake_world_env: dict) -> None:
        from marslab.sim.world_setup import create_world

        create_world(physics_dt=1 / 60.0, gravity=3.72, solver_type="PGS")
        assert fake_world_env["solver_type"] == "PGS"
