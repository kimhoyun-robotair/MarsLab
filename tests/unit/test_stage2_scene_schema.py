"""Structural / schema tests for stage2 scene + loop modules.

These modules carry Isaac Sim imports inside function bodies only; we
assert that the module-level import surface stays P3-safe and that the
public functions advertise the expected signatures so callers (the thin
``scripts/phase1/run_stage2.py`` shim) remain unbroken after the split.
"""

from __future__ import annotations

import importlib
import inspect


def test_stage2_scene_module_is_offline_importable() -> None:
    """Module import must not trigger any ``omni.*`` / ``isaacsim.*`` load."""
    mod = importlib.import_module("marslab.runtime.stage2_scene")
    globs = vars(mod)
    for forbidden in ("omni", "isaacsim", "pxr"):
        assert forbidden not in globs, f"stage2_scene must not import {forbidden} at module scope"


def test_stage2_loop_module_is_offline_importable() -> None:
    """Module import must not trigger any ``omni.*`` / ``isaacsim.*`` load."""
    mod = importlib.import_module("marslab.runtime.stage2_loop")
    globs = vars(mod)
    for forbidden in ("omni", "isaacsim", "pxr"):
        assert forbidden not in globs, f"stage2_loop must not import {forbidden} at module scope"


def test_setup_stage2_scene_signature() -> None:
    """Ensure the public scene constructor still accepts a boot result."""
    from marslab.runtime.stage2_scene import setup_stage2_scene

    sig = inspect.signature(setup_stage2_scene)
    params = list(sig.parameters)
    assert params == ["boot"]


def test_run_stage2_loop_signature() -> None:
    """Contract: loop takes (simulation_app, boot, scene, headless=False)."""
    from marslab.runtime.stage2_loop import run_stage2_loop

    sig = inspect.signature(run_stage2_loop)
    params = sig.parameters
    assert list(params) == ["simulation_app", "boot", "scene", "headless"]
    assert params["headless"].default is False


def test_build_atmosphere_state_from_boot() -> None:
    """The loop's seed helper must faithfully reflect the boot snapshot."""
    from pathlib import Path

    from marslab.runtime.stage2_boot import run_stage2_boot
    from marslab.runtime.stage2_loop import build_atmosphere_state

    repo_root = Path(__file__).resolve().parents[2]
    boot = run_stage2_boot(str(repo_root / "configs" / "mars_env.yaml"))
    state = build_atmosphere_state(boot.atmosphere_init)

    expected_keys = {
        "tau",
        "sun_mode",
        "sun_azimuth_deg",
        "sun_elevation_deg",
        "time_of_sol",
        "direct_intensity",
        "diffuse_fraction",
        "sol_duration_seconds",
    }
    assert set(state) == expected_keys
    assert state["tau"] == boot.atmosphere_init.tau
    assert state["sol_duration_seconds"] == boot.atmosphere_init.sol_duration_seconds
    # Loop owns the mutable dict -- ensure it is not frozen.
    state["tau"] = 0.5
    assert state["tau"] == 0.5

    if boot.atmosphere_init.dynamic.enabled:
        assert state["sun_mode"] == "auto"
    else:
        assert state["sun_mode"] == "manual"
