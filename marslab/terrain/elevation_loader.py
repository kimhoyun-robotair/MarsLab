"""Terrain elevation loader -- procedural, cave, or HiRISE DEM sources.

Used by the ``marslab.main`` runtime and the scenario tooling so they
share a single offline elevation-loading path. No Isaac Sim dependency;
imports are kept lazy so that cave/procedural paths do not pull heavy
geometry libraries unless used.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional, Tuple

import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def load_terrain_elevation(
    terrain_cfg: Dict[str, Any],
    repo_root: Optional[str] = None,
) -> Tuple[np.ndarray, Dict[str, Any], float]:
    """Load the scenario terrain elevation grid.

    Args:
        terrain_cfg: The ``terrain`` block from a scenario config.  The
            expected keys depend on ``source``:
              * ``procedural``: ``procedural_preset``, ``terrain_size``,
                ``terrain_resolution``, ``seed``, plus preset-specific
                parameters (e.g. ``canyon_*`` for the canyon preset).
              * cave (``procedural`` + preset ``cave``): ``cave`` dict
                with half-ellipse tube parameters.
              * ``hirise``: ``converted_dem_dir`` (relative to repo)
                and optional ``dem_crop: {row, col, height, width}``.
        repo_root: Absolute path to repository root.  Used to resolve
            relative ``converted_dem_dir`` for HiRISE source.  Defaults
            to :data:`REPO_ROOT`.

    Returns:
        Tuple of ``(elevation, metadata, resolution_m)``:
            * ``elevation`` is shape ``(H, W)`` float32 in metres.
            * ``metadata`` is an arbitrary dict describing the source.
              For cave the metadata dict carries the full generator
              payload under ``metadata["_cave_data"]`` so downstream
              scene builders pick it up without a second generation
              pass. The same payload is mirrored onto
              ``terrain_cfg["_cave_data"]`` because the active stage-2
              consumer (``marslab.runtime.stage2_scene``) reads from
              the input config dict; both writes go to the same object
              so they cannot drift.
            * ``resolution_m`` is metres per grid cell.

    Raises:
        ValueError: If ``source`` is missing or unknown, or if required
            per-source config fields are absent.
        FileNotFoundError: If a referenced DEM directory does not exist.
    """
    root = os.path.abspath(repo_root) if repo_root else REPO_ROOT
    source = terrain_cfg.get("source", "procedural")
    resolution = float(terrain_cfg.get("terrain_resolution", 1.0))

    if source == "procedural":
        preset = terrain_cfg.get("procedural_preset", "flat")
        if preset == "cave":
            elevation, metadata, res, cave_data = _load_cave(terrain_cfg, resolution)
            # ``cave_data`` is published to two locations: ``metadata`` is
            # the canonical key for callers that consume the loader's
            # return value (tests, scenario tooling), and ``terrain_cfg``
            # is the path the stage-2 scene builder
            # (``marslab.runtime.stage2_scene``) reads from. Both writes
            # share the same object reference so the two views cannot
            # diverge.
            metadata["_cave_data"] = cave_data
            terrain_cfg["_cave_data"] = cave_data
            return elevation, metadata, res
        return _load_procedural(terrain_cfg, preset, resolution)

    if source == "hirise":
        return _load_hirise(terrain_cfg, root, resolution)

    raise ValueError(f"Unknown terrain source: {source!r}")


def _load_cave(
    terrain_cfg: Dict[str, Any], resolution: float
) -> Tuple[np.ndarray, Dict[str, Any], float, Dict[str, Any]]:
    """Generate a cave elevation grid.

    Returns the standard ``(elevation, metadata, resolution)`` triple
    plus the full ``cave_data`` payload as a fourth element. The caller
    decides where to attach ``cave_data`` (``metadata`` is the canonical
    target so that the loader does not mutate its input dict).
    """
    from marslab.config.schema.terrain import CaveConfig
    from marslab.terrain.cave.orchestrator import generate_cave_mesh

    size = tuple(terrain_cfg.get("terrain_size", [256, 256]))
    seed = int(terrain_cfg.get("seed", 42))
    cave_cfg = dict(terrain_cfg.get("cave", {}))
    # ``terrain_size`` and ``terrain_resolution`` live at the terrain
    # block level; inject them into the cave block so ``CaveConfig``
    # carries the full set of generator inputs.
    cave_cfg.setdefault("domain_size", tuple(size))
    cave_cfg.setdefault("resolution", float(resolution))
    cfg = CaveConfig.model_validate(cave_cfg)
    cave_data = generate_cave_mesh(seed, cfg)
    elevation = cave_data["surface_elevation"]
    metadata = cave_data["metadata"]
    return elevation, metadata, resolution, cave_data


def _load_procedural(
    terrain_cfg: Dict[str, Any], preset: str, resolution: float
) -> Tuple[np.ndarray, Dict[str, Any], float]:
    """Generate a procedural (flat/crater/hills/rocky_plain/canyon) elevation grid."""
    from marslab.terrain.procedural_generator import generate_terrain

    size = tuple(terrain_cfg.get("terrain_size", [256, 256]))
    seed = int(terrain_cfg.get("seed", 42))
    # Currently only ``canyon_*`` keys are supported as procedural-preset
    # overrides; future presets should follow the same prefix scheme so
    # the dispatch stays a single per-preset prefix filter.
    preset_params = {k: v for k, v in terrain_cfg.items() if k.startswith("canyon_")}
    elevation, metadata = generate_terrain(
        preset,
        size,
        resolution,
        seed,
        kwargs=preset_params,
    )
    return elevation, metadata, resolution


def _load_hirise(
    terrain_cfg: Dict[str, Any], root: str, resolution: float
) -> Tuple[np.ndarray, Dict[str, Any], float]:
    """Load a pre-converted HiRISE DEM and apply an optional crop window."""
    from marslab.terrain.dem_loader import crop_dem, load_converted_dem

    converted_dir = terrain_cfg.get("converted_dem_dir")
    if converted_dir is None:
        raise ValueError("terrain.converted_dem_dir required for source='hirise'")

    dem_dir = converted_dir if os.path.isabs(converted_dir) else os.path.join(root, converted_dir)
    elevation, metadata = load_converted_dem(dem_dir)
    resolution = float(metadata.get("resolution_x", resolution))

    crop = terrain_cfg.get("dem_crop")
    if crop is not None:
        elevation, metadata = crop_dem(
            elevation,
            metadata,
            row=int(crop["row"]),
            col=int(crop["col"]),
            height=int(crop["height"]),
            width=int(crop["width"]),
        )
    return elevation, metadata, resolution
