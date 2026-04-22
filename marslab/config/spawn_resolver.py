"""Spawn pose resolution from declarative spawn specs + DEM elevation grid.

Split from marslab.config.scenario_loader (R2, 2026-04-22). Sibling
marslab.config.yaml_loader holds the YAML I/O + deep_merge logic.
Zero Isaac Sim imports; offline-testable (P3).

The three spawn modes:

* ``mode: "absolute"`` — use ``xy`` as-is, set ``z = xy[2]`` (or
  explicit ``z``).
* ``mode: "dem_center"`` — spawn at DEM centre, ``z = dem_z_at_center +
  z_offset``.
* ``mode: "dem_relative"`` — ``xy`` is a local offset from DEM centre
  (metres), ``z = bilinear_sample(elevation, xy) + z_offset``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import numpy as np

__all__ = ["resolve_spawn_pose"]


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
