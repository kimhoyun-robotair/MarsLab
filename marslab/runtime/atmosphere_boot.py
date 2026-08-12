"""Atmosphere-only offline boot preparation (Isaac-Sim-free, terrain-free).

Loads the scenario config and pre-computes every atmospheric parameter
(sun position, direct intensity, diffuse fraction, sky dome params) before
Isaac Sim is launched. Pure Python so the unit test suite can exercise it
without a GPU.

This module intentionally omits terrain loading. The passthrough pipeline
consumes a supplied Scene USDZ package and has no dependency on
``marslab.terrain.*`` at any scope.

Returns a frozen :class:`AtmosphereBootResult` consumed downstream by the
scene + loop stages.

Sun position can be overridden at call time via ``sun_azimuth_deg`` and
``sun_elevation_deg`` kwargs to :func:`boot_atmosphere`, which is how
the CLI flags ``--sun-azimuth-deg`` / ``--sun-elevation-deg`` on
``marslab/main.py`` inject experiment variants without duplicating YAMLs.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from marslab.config.loader import propagate_seeds_in_dict
from marslab.config.schema import DynamicAtmosphereConfig, MarsEnvConfig
from marslab.config.yaml_loader import load_scenario_config

_LOG = logging.getLogger(__name__)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_REQUIRED_SECTIONS: Tuple[str, ...] = ("mars_env", "rendering")


@dataclass(frozen=True)
class AtmosphereInit:
    """Frozen static atmosphere snapshot produced at boot time.

    Consumed by :mod:`marslab.runtime.main_loop` (via
    :func:`build_atmosphere_loop_state`) to seed the mutable per-frame
    ``atmosphere_dict``. Ownership of the mutable state lives in the
    loop module only.

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
    sky_params: Any  # SkyDomeParams (avoid import at module scope to keep offline-first)
    sun_pos: Any  # SunPosition
    hdri_dir: str
    dynamic: DynamicAtmosphereConfig


@dataclass(frozen=True)
class AtmosphereBootResult:
    """Frozen result of :func:`boot_atmosphere`.

    Bundles the merged config dict and the static atmosphere snapshot so
    the scene/loop modules can run without re-reading YAML or reaching
    into ``environment``. Terrain fields are intentionally absent — this
    result is for the passthrough pipeline only.

    Attributes:
        config_path: Absolute path to the YAML that was loaded.
        config: Merged scenario config dict (after ``base_config`` deep-merge).
        mars_cfg: Shortcut to ``config['mars_env']``.
        rendering_cfg: Shortcut to ``config['rendering']``.
        atmosphere_init: Pre-computed static atmosphere snapshot.
        repo_root: Absolute repository root (used by scene for HDRI /
            texture resolution).
    """

    config_path: str
    config: Dict[str, Any]
    mars_cfg: Dict[str, Any]
    rendering_cfg: Dict[str, Any]
    atmosphere_init: AtmosphereInit
    repo_root: str


def boot_atmosphere(
    config_path: str,
    repo_root: str = REPO_ROOT,
    sun_azimuth_deg: float | None = None,
    sun_elevation_deg: float | None = None,
) -> AtmosphereBootResult:
    """Load config and pre-compute the static atmosphere snapshot.

    Does NOT load terrain data. Intended for the passthrough pipeline that
    consumes supplied Scene USDZ packages.

    Args:
        config_path: Path to the scenario YAML config.
        repo_root: Absolute repo root used to resolve relative asset
            paths (texture_dir, HDRI dir). Defaults to the MarsLab repo
            root derived from this module.
        sun_azimuth_deg: When not None, overrides ``mars_env.sun_azimuth_deg``
            from the YAML before any sun-position computation. Used by the
            ``--sun-azimuth-deg`` CLI flag on ``marslab/main.py``.
        sun_elevation_deg: When not None, overrides ``mars_env.sun_elevation_deg``
            from the YAML before any sun-position computation. Used by the
            ``--sun-elevation-deg`` CLI flag on ``marslab/main.py``.

    Returns:
        :class:`AtmosphereBootResult` with every value needed by the scene
        and loop stages (config + atmosphere, no terrain).

    Raises:
        ValueError: If a required config section is absent.
        FileNotFoundError: Propagated from the YAML loader.
    """
    # Late imports keep module-level cost small for unit tests that only
    # exercise config paths.
    from marslab.environment.diffuse_fraction import compute_diffuse_fraction_1d_approx
    from marslab.environment.light_intensity import compute_direct_intensity
    from marslab.environment.sky_dome import compute_sky_dome_params
    from marslab.environment.sun_position import compute_sun_position

    abs_config_path = os.path.abspath(config_path)
    cfg = load_scenario_config(abs_config_path)
    # Enforce ``terrain.seed == mars_env.seed + 1`` on the raw dict path so
    # callers share a single seed-propagation site. When ``terrain`` block is
    # absent (passthrough pipeline), propagate_seeds_in_dict leaves it
    # untouched per its contract.
    cfg = propagate_seeds_in_dict(cfg)
    for key in _REQUIRED_SECTIONS:
        if key not in cfg:
            raise ValueError(f"Config missing required section: '{key}'")
    _LOG.info("Loaded config: %s", abs_config_path)

    mars_cfg = cfg["mars_env"]
    rendering_cfg = cfg["rendering"]

    # Route every scalar through pydantic so defaults live exactly once in
    # :class:`MarsEnvConfig` rather than being duplicated as
    # ``.get(..., literal)`` fallbacks here.
    mars_env_model = MarsEnvConfig(**mars_cfg)
    # Apply CLI sun-position overrides BEFORE any computation so that
    # compute_sun_position / compute_direct_intensity / compute_sky_dome_params
    # all see the overridden values. model_copy(update={...}) returns a new
    # pydantic model instance; MarsEnvConfig does NOT use frozen=True so
    # direct attribute assignment would also work, but model_copy is the
    # pydantic-canonical pattern and avoids triggering validators twice.
    if sun_azimuth_deg is not None:
        mars_env_model = mars_env_model.model_copy(update={"sun_azimuth_deg": sun_azimuth_deg})
    if sun_elevation_deg is not None:
        mars_env_model = mars_env_model.model_copy(update={"sun_elevation_deg": sun_elevation_deg})

    sun_pos = compute_sun_position(
        azimuth_deg=mars_env_model.sun_azimuth_deg,
        elevation_deg=mars_env_model.sun_elevation_deg,
    )
    tau = mars_env_model.dust_optical_depth
    solar_constant = mars_env_model.solar_constant
    direct_intensity = compute_direct_intensity(solar_constant, tau, sun_pos.zenith_angle_rad)
    diffuse_frac = compute_diffuse_fraction_1d_approx(tau)
    hdri_dir = os.path.join(repo_root, rendering_cfg.get("sky_dome_hdri_dir", "assets/mars_sky/"))
    sky_params = compute_sky_dome_params(tau, hdri_dir)
    _LOG.info(
        "Atmosphere: tau=%s, direct=%.1f W/m2, diffuse_frac=%.2f",
        tau,
        direct_intensity,
        diffuse_frac,
    )

    dynamic = mars_env_model.dynamic_atmosphere

    atmosphere_init = AtmosphereInit(
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

    return AtmosphereBootResult(
        config_path=abs_config_path,
        config=cfg,
        mars_cfg=mars_cfg,
        rendering_cfg=rendering_cfg,
        atmosphere_init=atmosphere_init,
        repo_root=repo_root,
    )


__all__ = [
    "REPO_ROOT",
    "AtmosphereInit",
    "AtmosphereBootResult",
    "boot_atmosphere",
]
