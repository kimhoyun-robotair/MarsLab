"""Stage 2 infinite render loop (Isaac Sim-dependent).

Owns the mutable per-frame atmosphere state, spawns the GUI panel (when not
headless), and drives the dynamic sun sweep / tau slider updates. Isaac Sim
imports stay lazy so the module is importable offline. Naming mirrors the
Stage 3 extraction (``setup_*_scene`` + ``run_*_loop``); the two loop
modules deliberately do not share a base class to avoid premature
abstraction.
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, Dict

from marslab.runtime.stage2_boot import StageTwoAtmosphereInit, StageTwoBootResult
from marslab.runtime.stage2_scene import StageTwoScene

_LOG = logging.getLogger(__name__)

# The physics tick used by the sun-sweep cadence lives in
# :class:`StageTwoAtmosphereInit.physics_dt`, populated from the pydantic
# ``MarsEnvConfig.physics_dt`` default. Zero hardcoded Mars constants in
# Python source: every value flows through the YAML config + schema.


def build_atmosphere_state(atmo: StageTwoAtmosphereInit) -> Dict[str, Any]:
    """Seed the mutable per-frame atmosphere state from the boot snapshot.

    The returned dict is owned by the render loop and is the single
    source of truth for per-frame sun / tau updates. The GUI panel reads
    and writes it in place.

    Args:
        atmo: Frozen static atmosphere snapshot from the boot stage.

    Returns:
        Mutable dict with the keys consumed by the render loop:
        ``tau``, ``sun_mode``, ``sun_azimuth_deg``, ``sun_elevation_deg``,
        ``time_of_sol``, ``direct_intensity``, ``diffuse_fraction``,
        ``sol_duration_seconds``.
    """
    return {
        "tau": atmo.tau,
        "sun_mode": "auto" if atmo.dynamic.enabled else "manual",
        "sun_azimuth_deg": atmo.sun_azimuth_deg,
        "sun_elevation_deg": atmo.sun_elevation_deg,
        "time_of_sol": 0.0,
        "direct_intensity": atmo.direct_intensity,
        "diffuse_fraction": atmo.diffuse_fraction,
        "sol_duration_seconds": atmo.sol_duration_seconds,
    }


def run_stage2_loop(
    simulation_app: Any,
    boot: StageTwoBootResult,
    scene: StageTwoScene,
    headless: bool = False,
) -> None:
    """Run the GUI panel + infinite render loop until Kit exits.

    Args:
        simulation_app: Live ``SimulationApp`` returned by the boot
            helper. This function owns Isaac Sim shutdown: the
            ``finally`` block always calls ``close()``. If ``close()``
            raises, the failure is reported on stderr and the process
            exits with code 1 (bypassing Kit ``atexit`` per
            ``tests/visual_inspection/checklist.md §Kit-SIGSEGV``).
        boot: Offline boot result (needed for dynamic atmosphere config).
        scene: Scene handles produced by :func:`setup_stage2_scene`.
        headless: When ``True``, the GUI atmosphere panel is skipped.
    """
    from marslab.environment.diffuse_fraction import compute_diffuse_fraction
    from marslab.environment.light_intensity import compute_direct_intensity
    from marslab.environment.sky_dome import compute_sky_dome_params
    from marslab.environment.sun_position import compute_sol_sun_position, compute_sun_position
    from marslab.rendering.atmosphere_fog import configure_atmosphere_fog
    from marslab.rendering.sky_renderer import update_sky_dome
    from marslab.rendering.sun_renderer import update_sun_light

    atmo = boot.atmosphere_init
    dyn = atmo.dynamic
    dynamic_enabled = dyn.enabled

    sol_duration = atmo.sol_duration_seconds
    physics_dt = atmo.physics_dt
    update_interval = dyn.update_interval_frames
    time_scale = dyn.time_scale
    sweep_start_az = dyn.sun_sweep.start_azimuth_deg
    sweep_end_az = dyn.sun_sweep.end_azimuth_deg
    sweep_max_el = dyn.sun_sweep.max_elevation_deg

    if dynamic_enabled:
        tau_profile_name = dyn.tau_profile
        _LOG.info(
            "Dynamic atmosphere ON: time_scale=%sx, tau_profile=%s, update_interval=%s",
            time_scale,
            tau_profile_name,
            update_interval,
        )
    else:
        _LOG.info("Dynamic atmosphere OFF (static).")

    atmosphere_state = build_atmosphere_state(atmo)

    atmo_panel = None
    if not headless:
        try:
            from marslab.gui.atmosphere_panel import AtmospherePanel

            atmo_panel = AtmospherePanel(atmosphere_state)
            _LOG.info("Atmosphere control panel created.")
        except Exception as exc:  # noqa: BLE001
            _LOG.warning("GUI panel unavailable (%s), using YAML config.", exc)

    world = scene.world
    stage = scene.stage
    render_config = scene.render_config
    solar_constant = atmo.solar_constant
    hdri_dir = atmo.hdri_dir

    world.reset()
    _LOG.info("Scene ready. Explore in GUI. Ctrl+C to exit.")
    frame = 0
    elapsed = 0.0

    def _step_atmosphere() -> None:
        """Advance the dynamic atmosphere one cadence tick.

        Closes over the outer-loop locals (``elapsed``, render handles,
        env callables). Returns nothing; mutates ``atmosphere_state`` and
        ``elapsed`` in place. Kept local to :func:`run_stage2_loop`; the
        twin mutator in :mod:`marslab.runtime.main_loop` uses a different
        callable-injection layout so the two paths do not share a base.
        """
        nonlocal elapsed

        current_tau = atmosphere_state["tau"]
        dyn_sun_pos = None

        if atmosphere_state["sun_mode"] == "auto" and dynamic_enabled:
            elapsed += physics_dt * update_interval * time_scale
            t = (elapsed % sol_duration) / sol_duration
            atmosphere_state["time_of_sol"] = t

            # ``mode="linear"`` pins the linear azimuth sweep + half-sine
            # elevation envelope semantics that ``SunSweepConfig`` was
            # designed around. ``mode="spherical"`` is opt-in and requires
            # extending ``SunSweepConfig`` with ``latitude_deg`` /
            # ``ls_deg`` first.
            dyn_sun_pos = compute_sol_sun_position(
                time_of_sol_fraction=t,
                start_azimuth_deg=sweep_start_az,
                end_azimuth_deg=sweep_end_az,
                max_elevation_deg=sweep_max_el,
                mode="linear",
            )
            atmosphere_state["sun_azimuth_deg"] = dyn_sun_pos.azimuth_deg
            atmosphere_state["sun_elevation_deg"] = dyn_sun_pos.elevation_deg
        elif atmosphere_state["sun_mode"] == "manual":
            dyn_sun_pos = compute_sun_position(
                azimuth_deg=atmosphere_state["sun_azimuth_deg"],
                elevation_deg=max(0.5, min(89.5, atmosphere_state["sun_elevation_deg"])),
            )

        if dyn_sun_pos is None:
            return

        dyn_intensity = compute_direct_intensity(
            solar_constant, current_tau, dyn_sun_pos.zenith_angle_rad
        )
        dyn_diffuse = compute_diffuse_fraction(current_tau)
        dyn_sky = compute_sky_dome_params(current_tau, hdri_dir)

        atmosphere_state["direct_intensity"] = dyn_intensity
        atmosphere_state["diffuse_fraction"] = dyn_diffuse

        update_sun_light(stage, dyn_sun_pos, dyn_intensity, dyn_diffuse, render_config)
        update_sky_dome(stage, dyn_sky, dyn_diffuse, render_config)
        configure_atmosphere_fog(stage, current_tau, render_config)

        if atmo_panel is not None:
            atmo_panel.update_display()

    try:
        while simulation_app.is_running():
            world.step(render=True)
            frame += 1

            if frame % update_interval != 0:
                continue

            _step_atmosphere()

    except KeyboardInterrupt:
        _LOG.info("KeyboardInterrupt -- shutting down.")
    finally:
        try:
            simulation_app.close()
        except Exception as exc:  # noqa: BLE001
            _LOG.error("simulation_app.close() raised: %s", exc)
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(1)


__all__ = ["build_atmosphere_state", "run_stage2_loop"]
