"""Stage 2 offline boot preparation (Isaac-Sim-free).

Loads the scenario config, resolves DEM paths, and pre-computes every
atmospheric parameter (sun position, direct intensity, diffuse fraction,
sky dome params) before Isaac Sim is launched. Keeping this step pure
Python lets the unit test suite exercise it without a GPU (P3).

Data flow (P2 unidirectional):
    Config YAML -> load_runtime_config_dict -> validate required sections
    -> load_scenario_terrain (offline) -> resolve_dem_paths
    -> static atmosphere pre-compute -> DynamicAtmosphereConfig parse
    -> StageTwoBootResult (frozen dataclass consumed by scene + loop).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np

from marslab.config.schema import DynamicAtmosphereConfig, MarsEnvConfig
from marslab.runtime.config_loader import load_runtime_config_dict
from marslab.terrain.terrain_loader import load_scenario_terrain, resolve_dem_paths

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_REQUIRED_SECTIONS: Tuple[str, ...] = ("mars_env", "terrain", "rendering")


@dataclass(frozen=True)
class StageTwoAtmosphereInit:
    """Frozen static atmosphere snapshot produced at boot time.

    Consumed by :mod:`marslab.runtime.stage2_scene` to build the initial
    sun/sky/fog configuration, and by :mod:`marslab.runtime.stage2_loop`
    to seed the mutable per-frame ``atmosphere_state`` dict. Ownership
    of the mutable state lives in the loop module only.

    Attributes:
        tau: Dust optical depth used for the initial render.
        solar_constant: W/m^2 Mars solar constant (config value).
        sun_azimuth_deg: Static sun azimuth (degrees).
        sun_elevation_deg: Static sun elevation (degrees).
        sol_duration_seconds: Mars sol length in seconds.
        physics_dt: Engine physics tick in seconds (60 Hz default).
        direct_intensity: Direct solar irradiance (Beer's law) in W/m^2.
        diffuse_fraction: COMIMART diffuse fraction [0, 1].
        sky_params: Pre-computed sky dome parameters (color + intensity).
        sun_pos: Pre-computed ``SunPosition`` (azimuth, elevation, zenith).
        hdri_dir: Absolute path to the sky HDRI directory.
        dynamic: Parsed :class:`DynamicAtmosphereConfig` for the loop.
    """

    tau: float
    solar_constant: float
    sun_azimuth_deg: float
    sun_elevation_deg: float
    sol_duration_seconds: float
    physics_dt: float
    direct_intensity: float
    diffuse_fraction: float
    sky_params: Any  # SkyDomeParams (avoid import at module scope for P3)
    sun_pos: Any  # SunPosition
    hdri_dir: str
    dynamic: DynamicAtmosphereConfig


@dataclass(frozen=True)
class StageTwoBootResult:
    """Frozen result of :func:`run_stage2_boot`.

    Bundles the merged config dict, pre-loaded terrain grid, resolved DEM
    paths, and the static atmosphere snapshot so the scene/loop modules
    can run without re-reading YAML or reaching into ``environment``.

    Attributes:
        config_path: Absolute path to the YAML that was loaded.
        config: Merged scenario config dict (after ``base_config`` deep-merge).
        mars_cfg: Shortcut to ``config['mars_env']``.
        terrain_cfg: Shortcut to ``config['terrain']``.
        rendering_cfg: Shortcut to ``config['rendering']``.
        elevation: Terrain elevation grid in metres.
        metadata: Terrain metadata dict from the loader.
        resolution: Grid spacing in m/pixel.
        dem_paths: Canonical DEM asset paths (see
            :func:`marslab.terrain.terrain_loader.resolve_dem_paths`).
        atmosphere_init: Pre-computed static atmosphere snapshot.
        repo_root: Absolute repository root (used by scene for HDRI /
            texture resolution).
    """

    config_path: str
    config: Dict[str, Any]
    mars_cfg: Dict[str, Any]
    terrain_cfg: Dict[str, Any]
    rendering_cfg: Dict[str, Any]
    elevation: np.ndarray
    metadata: Dict[str, Any]
    resolution: float
    dem_paths: Dict[str, Path] = field(default_factory=dict)
    atmosphere_init: StageTwoAtmosphereInit = field(
        default_factory=lambda: None  # type: ignore[arg-type]
    )
    repo_root: str = REPO_ROOT


def run_stage2_boot(config_path: str, repo_root: str = REPO_ROOT) -> StageTwoBootResult:
    """Load config + terrain and pre-compute the static atmosphere.

    Args:
        config_path: Path to the Stage 2 YAML scenario config.
        repo_root: Absolute repo root used to resolve relative asset
            paths (texture_dir, HDRI dir). Defaults to the MarsLab repo
            root derived from this module.

    Returns:
        :class:`StageTwoBootResult` with every value needed by the scene
        and loop stages.

    Raises:
        ValueError: If a required config section is absent.
        FileNotFoundError: Propagated from terrain / DEM loaders.
    """
    # Late imports keep module-level cost small for unit tests that only
    # exercise config + terrain paths.
    from marslab.environment.diffuse_fraction import compute_diffuse_fraction
    from marslab.environment.light_intensity import compute_direct_intensity
    from marslab.environment.sky_dome import compute_sky_dome_params
    from marslab.environment.sun_position import compute_sun_position

    abs_config_path = os.path.abspath(config_path)
    cfg = load_runtime_config_dict(abs_config_path)
    for key in _REQUIRED_SECTIONS:
        if key not in cfg:
            raise ValueError(f"Config missing required section: '{key}'")
    print(f"[run_stage2] Loaded config: {abs_config_path}", flush=True)

    mars_cfg = cfg["mars_env"]
    terrain_cfg = cfg["terrain"]
    rendering_cfg = cfg["rendering"]

    elevation, metadata, resolution = load_scenario_terrain(terrain_cfg, repo_root=repo_root)
    dem_paths = resolve_dem_paths(terrain_cfg, repo_root=repo_root)
    print(
        f"[run_stage2] Terrain: {elevation.shape} @ {resolution} m/px, "
        f"z=[{elevation.min():.1f}, {elevation.max():.1f}] m",
        flush=True,
    )

    # P6 G5 (2026-04-23): route every scalar through pydantic so defaults
    # live exactly once in :class:`MarsEnvConfig` rather than being
    # duplicated as ``.get(..., literal)`` fallbacks here.
    mars_env_model = MarsEnvConfig(**mars_cfg)

    sun_pos = compute_sun_position(
        azimuth_deg=mars_env_model.sun_azimuth_deg,
        elevation_deg=mars_env_model.sun_elevation_deg,
    )
    tau = mars_env_model.dust_optical_depth
    solar_constant = mars_env_model.solar_constant_mean
    direct_intensity = compute_direct_intensity(solar_constant, tau, sun_pos.zenith_angle_rad)
    diffuse_frac = compute_diffuse_fraction(tau)
    hdri_dir = os.path.join(repo_root, rendering_cfg.get("sky_dome_hdri_dir", "assets/sky/hdri/"))
    sky_params = compute_sky_dome_params(tau, hdri_dir)
    print(
        f"[run_stage2] Atmosphere: tau={tau}, direct={direct_intensity:.1f} W/m2, "
        f"diffuse_frac={diffuse_frac:.2f}",
        flush=True,
    )

    dynamic = mars_env_model.dynamic_atmosphere

    atmosphere_init = StageTwoAtmosphereInit(
        tau=tau,
        solar_constant=solar_constant,
        sun_azimuth_deg=mars_env_model.sun_azimuth_deg,
        sun_elevation_deg=mars_env_model.sun_elevation_deg,
        sol_duration_seconds=float(mars_env_model.sol_duration_seconds),
        physics_dt=mars_env_model.physics_dt,
        direct_intensity=direct_intensity,
        diffuse_fraction=diffuse_frac,
        sky_params=sky_params,
        sun_pos=sun_pos,
        hdri_dir=hdri_dir,
        dynamic=dynamic,
    )

    return StageTwoBootResult(
        config_path=abs_config_path,
        config=cfg,
        mars_cfg=mars_cfg,
        terrain_cfg=terrain_cfg,
        rendering_cfg=rendering_cfg,
        elevation=elevation,
        metadata=metadata,
        resolution=resolution,
        dem_paths=dem_paths,
        atmosphere_init=atmosphere_init,
        repo_root=repo_root,
    )


__all__ = [
    "REPO_ROOT",
    "StageTwoAtmosphereInit",
    "StageTwoBootResult",
    "run_stage2_boot",
]
