"""Structural / schema tests for stage2 scene + main_loop (P3-safe surface)."""

from __future__ import annotations

import importlib
import inspect


def test_stage2_scene_module_is_offline_importable() -> None:
    """Module import must not trigger any ``omni.*`` / ``isaacsim.*`` load."""
    mod = importlib.import_module("marslab.runtime.stage2_scene")
    globs = vars(mod)
    for forbidden in ("omni", "isaacsim", "pxr"):
        assert forbidden not in globs, f"stage2_scene must not import {forbidden} at module scope"


def test_setup_stage2_scene_signature() -> None:
    """Ensure the public scene constructor still accepts a boot result."""
    from marslab.runtime.stage2_scene import setup_stage2_scene

    sig = inspect.signature(setup_stage2_scene)
    params = list(sig.parameters)
    assert params == ["boot"]


def test_build_atmosphere_loop_state_from_boot(tmp_path) -> None:
    """``build_atmosphere_loop_state`` must reflect the boot snapshot.

    Inherits the contract previously enforced against the deleted
    ``stage2_loop.build_atmosphere_state``: the eight-key atmosphere dict
    is the canonical handoff between the boot stage and the GUI panel.
    """
    import yaml

    from marslab.runtime.main_loop import build_atmosphere_loop_state
    from marslab.runtime.stage2_boot import run_stage2_boot

    flat = tmp_path / "minimal_flat.yaml"
    flat.write_text(
        yaml.safe_dump(
            {
                "mars_env": {"seed": 42},
                "terrain": {
                    "source": "procedural",
                    "procedural_preset": "crater",
                    "terrain_size": [256, 256],
                    "terrain_resolution": 1.0,
                },
                "rendering": {"mode": "ray_tracing"},
            }
        )
    )
    boot = run_stage2_boot(str(flat))
    loop_state = build_atmosphere_loop_state(boot.atmosphere_init, boot.atmosphere_init.tau)
    state = loop_state.atmosphere_dict

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
