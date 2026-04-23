"""Unit tests for :func:`marslab.sim.boot.boot_simulation_app`.

Isaac Sim is not available in the unit-test environment, so we stub
``isaacsim.SimulationApp`` + ``isaacsim.core.utils.extensions`` via
``sys.modules`` monkeypatching and assert on the call sequence.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest


@pytest.fixture
def fake_isaacsim(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Install stub ``isaacsim`` + ``isaacsim.core.utils.extensions``."""

    captured: dict = {
        "sim_app_kwargs": None,
        "sim_app_close_called": False,
        "update_calls": 0,
        "enabled_extensions": [],
    }

    class FakeSimulationApp:
        def __init__(self, config: dict) -> None:
            captured["sim_app_kwargs"] = dict(config)

        def update(self) -> None:
            captured["update_calls"] += 1

        def close(self) -> None:
            captured["sim_app_close_called"] = True

    isaacsim = types.ModuleType("isaacsim")
    isaacsim.SimulationApp = FakeSimulationApp  # type: ignore[attr-defined]

    core_pkg = types.ModuleType("isaacsim.core")
    utils_pkg = types.ModuleType("isaacsim.core.utils")
    ext_pkg = types.ModuleType("isaacsim.core.utils.extensions")

    def enable_extension(name: str) -> None:
        captured["enabled_extensions"].append(name)

    ext_pkg.enable_extension = enable_extension  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "isaacsim", isaacsim)
    monkeypatch.setitem(sys.modules, "isaacsim.core", core_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.core.utils", utils_pkg)
    monkeypatch.setitem(sys.modules, "isaacsim.core.utils.extensions", ext_pkg)
    return captured


class TestBootSimulationApp:
    def test_passes_headless_and_renderer_config(self, fake_isaacsim: dict) -> None:
        from marslab.sim.boot import boot_simulation_app

        boot_simulation_app(headless=True, renderer="RaytracedLighting")
        assert fake_isaacsim["sim_app_kwargs"] == {
            "headless": True,
            "renderer": "RaytracedLighting",
        }

    def test_defaults_match_stage3_runtime(self, fake_isaacsim: dict) -> None:
        from marslab.sim.boot import boot_simulation_app

        boot_simulation_app()
        assert fake_isaacsim["sim_app_kwargs"] == {
            "headless": False,
            "renderer": "RaytracedLighting",
        }

    def test_enables_ros2_bridge_extension_by_default(self, fake_isaacsim: dict) -> None:
        from marslab.sim.boot import boot_simulation_app

        boot_simulation_app()
        assert "isaacsim.ros2.bridge" in fake_isaacsim["enabled_extensions"]

    def test_update_called_after_extension_enable(self, fake_isaacsim: dict) -> None:
        from marslab.sim.boot import boot_simulation_app

        boot_simulation_app()
        assert fake_isaacsim["update_calls"] == 1

    def test_returned_object_is_the_simulation_app(self, fake_isaacsim: dict) -> None:
        from marslab.sim.boot import boot_simulation_app

        sim_app: Any = boot_simulation_app()
        sim_app.close()
        assert fake_isaacsim["sim_app_close_called"] is True

    def test_custom_extension_override(self, fake_isaacsim: dict) -> None:
        from marslab.sim.boot import boot_simulation_app

        boot_simulation_app(ros2_bridge_extension="my.custom.ext")
        assert fake_isaacsim["enabled_extensions"] == ["my.custom.ext"]
