"""Top-level terrain loader facade for MarsLab scenarios (R3-A3).

Thin Option-B facade over :mod:`marslab.terrain.elevation_loader` plus a
scenario-wide DEM-path resolver. The goal is to let Stage 2/3 runtime
scripts and scenario tooling pull a single pair of helpers instead of
each duplicating ~80 LOC of elevation loading and DEM path assembly.

Offline-first (P3): no Isaac Sim imports. Pure ``pathlib`` + ``numpy``
only (numpy is inherited through the underlying loader's type hints).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np

from marslab.terrain.elevation_loader import load_terrain_elevation

# Repository root resolved at import time so callers may omit ``repo_root``
# when they are content with the package-relative default.  Mirrors
# :data:`marslab.terrain.elevation_loader.REPO_ROOT` so there is one
# canonical definition per module.
REPO_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))).resolve()


def load_scenario_terrain(
    terrain_cfg: Dict[str, Any],
    repo_root: Optional[str] = None,
) -> Tuple[np.ndarray, Dict[str, Any], float]:
    """Load the scenario terrain elevation grid.

    Thin facade around :func:`elevation_loader.load_terrain_elevation` so
    scenario-level code imports one module instead of reaching into the
    loader implementation.  Keeps the exact return contract of the
    underlying loader (``(elevation, metadata, resolution_m)``).

    Args:
        terrain_cfg: ``terrain`` block from a scenario config.  See
            :func:`marslab.terrain.elevation_loader.load_terrain_elevation`
            for the supported source/preset keys.
        repo_root: Absolute repo root used to resolve relative
            ``converted_dem_dir`` for HiRISE.  Defaults to the MarsLab
            repository root derived from this module's location.

    Returns:
        Tuple of ``(elevation, metadata, resolution_m)``.

    Raises:
        ValueError: Propagated from the underlying loader when the
            terrain source is missing, unknown, or misconfigured.
        FileNotFoundError: Propagated when a referenced DEM directory
            does not exist.
    """
    return load_terrain_elevation(terrain_cfg, repo_root=repo_root)


def resolve_dem_paths(
    terrain_cfg: Dict[str, Any],
    repo_root: Optional[str] = None,
) -> Dict[str, Path]:
    """Return canonical DEM-related asset paths for a scenario.

    Absorbs the ``os.path.join(REPO_ROOT, ...)`` assembly so every
    Stage 2 / Stage 3 caller resolves the same set of paths the same way.

    Keys returned:
        * ``converted_dir`` — absolute path of ``terrain.converted_dem_dir``
          (only present when ``source == "hirise"`` and the key is set).
        * ``elevation_npy`` — ``<converted_dir>/elevation.npy`` (only
          present when ``converted_dir`` is present).
        * ``metadata_json`` — ``<converted_dir>/metadata.json`` (only
          present when ``converted_dir`` is present).
        * ``texture_dir`` — absolute ``terrain.texture_dir`` when set.
        * ``rock_mesh_dir`` — absolute ``terrain.rock_mesh_dir`` when set.
        * ``rock_texture_dir`` — absolute ``terrain.rock_texture_dir``
          when set.

    Missing optional paths yield an absent key (never ``None``).  The
    function does **not** stat the filesystem; it only normalises path
    strings to absolute :class:`pathlib.Path` objects so the caller can
    hand them to asset loaders.

    Args:
        terrain_cfg: ``terrain`` block from a scenario config.
        repo_root: Absolute repo root used to resolve relative entries.
            Defaults to the repository root derived from this module.

    Returns:
        Mapping of canonical key → absolute :class:`pathlib.Path`.
    """
    root = Path(os.path.abspath(repo_root)) if repo_root else REPO_ROOT
    paths: Dict[str, Path] = {}

    source = terrain_cfg.get("source", "procedural")
    converted_dir = terrain_cfg.get("converted_dem_dir")
    if source == "hirise" and converted_dir:
        abs_converted = _as_absolute(converted_dir, root)
        paths["converted_dir"] = abs_converted
        paths["elevation_npy"] = abs_converted / "elevation.npy"
        paths["metadata_json"] = abs_converted / "metadata.json"

    for key in ("texture_dir", "rock_mesh_dir", "rock_texture_dir"):
        raw = terrain_cfg.get(key)
        if raw:
            paths[key] = _as_absolute(raw, root)

    return paths


def _as_absolute(path_like: str, root: Path) -> Path:
    """Resolve ``path_like`` against ``root`` unless it is already absolute."""
    candidate = Path(path_like)
    if candidate.is_absolute():
        return candidate.resolve()
    return (root / candidate).resolve()
