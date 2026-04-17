"""Scenario YAML loader with base-config include + deep-merge + spawn resolve.

A Stage-3 scenario YAML carries terrain/rendering/atmosphere blocks *and*
an optional ``rover:`` block whose ``base_config`` key points to a common
rover definition (e.g. ``configs/robots/rover_m2020.yaml``).  Scenario
values override base values via recursive dict merge (the scenario wins
for leaf conflicts; lists are replaced, not concatenated).

Spawn resolution converts a declarative spawn spec into a concrete
``(x, y, z)`` world-frame point by sampling the terrain elevation grid:

* ``mode: "absolute"`` — use ``xy`` as-is, set ``z = xy[2]`` (or
  explicit ``z``).
* ``mode: "dem_center"`` — spawn at DEM centre, ``z = dem_z_at_center +
  z_offset``.
* ``mode: "dem_relative"`` — ``xy`` is a local offset from DEM centre
  (metres), ``z = bilinear_sample(elevation, xy) + z_offset``.

The module has zero Isaac Sim / ROS2 dependencies (P3 offline-testable).
"""

from __future__ import annotations

import copy
import os
from typing import Any, Dict, Optional, Tuple

import numpy as np
import yaml

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _read_yaml(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(_format_missing_file_message(path))
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def _format_missing_file_message(path: str) -> str:
    """Build a FileNotFoundError message that lists sibling YAMLs.

    When a user mistypes a scenario path (trailing ``2``, stray ``.yml``
    vs ``.yaml``, etc.), showing up to 8 real YAML files in the same
    directory lets them fix the typo without a separate ``ls`` step.
    """
    parent = os.path.dirname(path) or "."
    nearby: list[str] = []
    if os.path.isdir(parent):
        for name in sorted(os.listdir(parent)):
            if name.endswith((".yaml", ".yml")):
                nearby.append(name)
            if len(nearby) >= 8:
                break
    if nearby:
        listing = ", ".join(nearby)
        return f"Config not found: {path!r} (nearby YAMLs in {parent}: {listing})"
    return f"Config not found: {path!r}"


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dicts; override wins, lists are replaced.

    Args:
        base: The lower-priority dictionary.  Not mutated.
        override: The higher-priority dictionary.  Not mutated.

    Returns:
        A new dict containing the merge.  Nested dicts are merged
        recursively; non-dict values in ``override`` replace the
        corresponding value in ``base``.  Keys only in ``base`` are
        preserved verbatim.
    """
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _resolve_path(path: str, anchor_dir: Optional[str]) -> str:
    """Expand a path against ``anchor_dir`` or the repo root."""
    if os.path.isabs(path):
        return path
    if anchor_dir is not None:
        candidate = os.path.abspath(os.path.join(anchor_dir, path))
        if os.path.isfile(candidate):
            return candidate
    return os.path.abspath(os.path.join(REPO_ROOT, path))


def load_scenario_config(scenario_path: str) -> Dict[str, Any]:
    """Load a scenario YAML, merging a rover ``base_config`` if present.

    The scenario YAML is the higher-priority input; the base config
    (pointed at by ``rover.base_config``) only contributes the common
    rover/sensors/control/ros2 blocks.  The merge is done under the
    ``rover:`` subtree so terrain/rendering/mars_env live only in the
    scenario file.

    Args:
        scenario_path: Path to the scenario YAML.  Relative paths are
            resolved against the current working directory first, then
            against repo root.

    Returns:
        Fully merged config dict.  The ``rover.base_config`` key is
        removed from the result.

    Raises:
        ValueError: If ``scenario_path`` contains internal whitespace
            that does not correspond to a real file on disk.  This
            usually means the CLI value got pasted with a trailing
            token (``2>&1`` is a shell redirection, not an argparse
            argument).
    """
    scenario_path = str(scenario_path).strip()
    resolved = scenario_path
    if not os.path.isabs(resolved):
        resolved = os.path.abspath(resolved)
        if not os.path.isfile(resolved):
            resolved = os.path.abspath(os.path.join(REPO_ROOT, scenario_path))
    if any(ch.isspace() for ch in scenario_path) and not os.path.isfile(resolved):
        raise ValueError(
            f"Scenario path contains embedded whitespace: {scenario_path!r}. "
            "Did you paste a shell redirection like `2>&1` into --config? "
            "Redirections belong after the command, outside argparse."
        )
    scenario_cfg = _read_yaml(resolved)
    scenario_dir = os.path.dirname(resolved)

    rover_override = scenario_cfg.get("rover")
    if not isinstance(rover_override, dict):
        # No rover block — scenario-only (run_stage2 style).
        return scenario_cfg

    base_path = rover_override.get("base_config")
    if base_path is None:
        # Scenario declares rover inline without referencing a base.
        merged = copy.deepcopy(scenario_cfg)
        merged["rover"] = copy.deepcopy(rover_override)
        return merged

    base_full = _resolve_path(str(base_path), scenario_dir)
    base_cfg = _read_yaml(base_full)

    merged_rover_inputs = copy.deepcopy(rover_override)
    merged_rover_inputs.pop("base_config", None)

    merged_rover = deep_merge(base_cfg, merged_rover_inputs)

    merged_cfg = copy.deepcopy(scenario_cfg)
    merged_cfg["rover"] = merged_rover
    # Legacy alias normalisation: sensors.lidar (single entry) → lidar_3d.
    sensors = merged_rover.get("sensors")
    if isinstance(sensors, dict) and "lidar" in sensors and "lidar_3d" not in sensors:
        sensors["lidar_3d"] = sensors.pop("lidar")
    return merged_cfg


def _bilinear_sample(grid: np.ndarray, row_f: float, col_f: float) -> float:
    """Bilinear interpolation on ``grid`` at fractional indices.

    Out-of-range indices clamp to the nearest valid cell.  Designed for
    dense 2-D elevation grids (shape ``(H, W)``).
    """
    if grid.ndim != 2:
        raise ValueError(f"Elevation grid must be 2-D, got shape {grid.shape}")
    h, w = grid.shape
    if h == 0 or w == 0:
        raise ValueError("Elevation grid is empty")
    row_f = float(np.clip(row_f, 0.0, h - 1))
    col_f = float(np.clip(col_f, 0.0, w - 1))
    r0 = int(np.floor(row_f))
    c0 = int(np.floor(col_f))
    r1 = min(r0 + 1, h - 1)
    c1 = min(c0 + 1, w - 1)
    dr = row_f - r0
    dc = col_f - c0
    v00 = float(grid[r0, c0])
    v01 = float(grid[r0, c1])
    v10 = float(grid[r1, c0])
    v11 = float(grid[r1, c1])
    v0 = v00 * (1.0 - dc) + v01 * dc
    v1 = v10 * (1.0 - dc) + v11 * dc
    return v0 * (1.0 - dr) + v1 * dr


def resolve_spawn_pose(
    rover_cfg: Dict[str, Any],
    elevation: Optional[np.ndarray],
    metadata: Optional[Dict[str, Any]],
    resolution: float,
) -> Tuple[float, float, float]:
    """Resolve rover spawn (x, y, z) from a declarative spawn spec.

    The returned pose lives in the same world frame as the terrain mesh
    built by ``marslab.terrain.mesh_builder.compute_mesh_arrays``:

    - Mesh vertices span ``X ∈ [0, (cols-1)·res]`` and
      ``Y ∈ [0, (rows-1)·res]`` (its corner at world origin).  Its
      centre is at ``((cols-1)·res/2, (rows-1)·res/2)``.
    - Mesh Z is normalised by subtracting ``np.nanmin(elevation)`` so
      the lowest point sits at ``z=0``.

    Both conventions must be mirrored here; otherwise the rover spawns
    in a void below the mesh (raw Mars-datum Z ≈ -2573 m) or at the
    mesh corner instead of its centre.

    Args:
        rover_cfg: The merged ``rover:`` block from the scenario config.
        elevation: Terrain elevation grid (shape ``(H, W)``, metres).
            May be ``None`` when ``mode == "absolute"``.
        metadata: Terrain metadata dict.  Reserved for future geo-anchor
            support; currently unused for mesh-frame placement.
        resolution: Grid cell size in metres.  Must match the elevation
            grid spacing.

    Returns:
        ``(x, y, z)`` tuple in world coordinates (metres, Z-up), in the
        same frame as the terrain mesh.

    Raises:
        ValueError: If the spawn spec is invalid or required data is
            missing.
    """
    spawn = rover_cfg.get("spawn", {}) if isinstance(rover_cfg, dict) else {}
    mode = str(spawn.get("mode", "absolute"))
    xy = spawn.get("xy", [0.0, 0.0])
    if not (isinstance(xy, (list, tuple)) and len(xy) >= 2):
        raise ValueError(f"spawn.xy must be [x, y], got {xy!r}")
    x = float(xy[0])
    y = float(xy[1])
    z_offset = float(spawn.get("z_offset", 0.0))

    if mode == "absolute":
        z = float(spawn.get("z", z_offset))
        return x, y, z

    if elevation is None:
        raise ValueError(f"spawn.mode={mode!r} requires a terrain elevation grid")
    if resolution <= 0.0:
        raise ValueError(f"resolution must be > 0, got {resolution}")

    h, w = elevation.shape
    center_row = (h - 1) / 2.0
    center_col = (w - 1) / 2.0
    mesh_center_x = center_col * resolution
    mesh_center_y = center_row * resolution

    if mode == "dem_center":
        row_f, col_f = center_row, center_col
        world_x = mesh_center_x
        world_y = mesh_center_y
    elif mode == "dem_relative":
        # xy is metres offset from mesh centre (x → +X, y → +Y).
        world_x = mesh_center_x + x
        world_y = mesh_center_y + y
        col_f = world_x / resolution
        row_f = world_y / resolution
    else:
        raise ValueError(f"Unknown spawn.mode: {mode!r}")

    dem_z_raw = _bilinear_sample(elevation, row_f, col_f)

    # Match mesh_builder normalization: mesh Z = raw - nanmin(elevation).
    z_shift = float(np.nanmin(elevation))
    if not np.isfinite(z_shift):
        z_shift = 0.0
    dem_z = dem_z_raw - z_shift
    return world_x, world_y, dem_z + z_offset
