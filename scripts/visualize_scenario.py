"""Offline visualizer for MarsLab scenario YAMLs (Wk2 #1-#3).

Loads a scenario YAML through the pydantic schema, applies the optional
DEM crop, runs the Golombek rock sampler, and produces a 2x2 matplotlib
figure with:

    1. Cropped DEM elevation heatmap with rover spawn marker
    2. Local slope magnitude heatmap (deg)
    3. Rock placement scatter (size = diameter)
    4. CFA curve: Golombek theoretical vs sampled

This script is pure offline: no Isaac Sim, no pxr, no GDAL at import
time (GDAL is only touched if the scenario omits a pre-converted DEM
directory).

Usage:
    python3 scripts/visualize_scenario.py <scenario_yaml> [<output_png>]

Example:
    python3 scripts/visualize_scenario.py configs/scenarios/basic_mars.yaml
    -> writes _workspace/wk2_terrain_basic_mars.png
"""

from __future__ import annotations

import math
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

from marslab.config.loader import load_and_validate
from marslab.config.schema import MarsLabConfig, TerrainConfig
from marslab.terrain.dem_loader import crop_dem, load_converted_dem, load_hirise_dem
from marslab.terrain.rock_placer import compute_cfa, sample_rocks_golombek


def _resolve_dem(terrain: TerrainConfig) -> tuple[np.ndarray, dict]:
    """Load the source DEM declared in the terrain config."""
    if terrain.converted_dem_dir and os.path.isdir(terrain.converted_dem_dir):
        return load_converted_dem(terrain.converted_dem_dir)
    if terrain.dem_path and os.path.isfile(terrain.dem_path):
        return load_hirise_dem(terrain.dem_path)
    raise FileNotFoundError(
        "Neither converted_dem_dir nor dem_path resolve to an existing "
        f"file for scenario '{terrain.scenario_name}'"
    )


def _apply_crop(
    terrain: TerrainConfig, elevation: np.ndarray, metadata: dict
) -> tuple[np.ndarray, dict]:
    """Apply the optional dem_crop window from the scenario YAML."""
    if terrain.dem_crop is None:
        return elevation, metadata
    return crop_dem(
        elevation,
        metadata,
        row=terrain.dem_crop.row,
        col=terrain.dem_crop.col,
        height=terrain.dem_crop.height,
        width=terrain.dem_crop.width,
    )


def _slope_map(elevation: np.ndarray, resolution: float) -> np.ndarray:
    """Return per-pixel slope magnitude in degrees."""
    gy, gx = np.gradient(elevation.astype(np.float32), resolution, resolution)
    return np.degrees(np.arctan(np.sqrt(gx * gx + gy * gy)))


def visualize(config: MarsLabConfig, output_png: str) -> None:
    """Render a 2x2 offline scenario figure and write it to disk."""

    def _setup_panel(ax, title: str, xlabel: str = "X (m)", ylabel: str = "Y (m)") -> None:
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

    terrain = config.terrain
    elevation, metadata = _resolve_dem(terrain)
    elev, meta = _apply_crop(terrain, elevation, metadata)

    res_x = float(meta.get("resolution_x", terrain.terrain_resolution))
    res_y = float(meta.get("resolution_y", terrain.terrain_resolution))
    side_x = meta["width"] * res_x
    side_y = meta["height"] * res_y
    area_m2 = side_x * side_y

    rocks = sample_rocks_golombek(
        area_m2=area_m2,
        k=terrain.rock_sfd_k,
        diameter_range=terrain.rock_diameter_range,
        seed=terrain.seed,
    )

    slope = _slope_map(elev, res_x)
    slope_stats = {
        "mean": float(np.mean(slope)),
        "p50": float(np.percentile(slope, 50)),
        "p90": float(np.percentile(slope, 90)),
        "p99": float(np.percentile(slope, 99)),
        "max": float(np.max(slope)),
    }

    measured_cfa = sum(math.pi / 4.0 * r.diameter**2 for r in rocks) / area_m2

    fig, axes = plt.subplots(2, 2, figsize=(14, 11))

    ax1 = axes[0][0]
    im1 = ax1.imshow(elev, cmap="terrain", origin="lower", extent=[0, side_x, 0, side_y])
    fig.colorbar(im1, ax=ax1, label="Elevation (m)")
    _setup_panel(
        ax1,
        f"{terrain.scenario_name or 'scenario'} — DEM crop "
        f"({meta['width']}x{meta['height']} @ {res_x:.1f} m/px)",
    )
    if config.robots:
        rx, ry, _ = config.robots[0].spawn_position
        ax1.plot(rx, ry, marker="*", color="red", markersize=16, label="rover spawn")
        ax1.legend(loc="upper right")

    ax2 = axes[0][1]
    im2 = ax2.imshow(slope, cmap="magma", origin="lower", extent=[0, side_x, 0, side_y], vmin=0.0)
    fig.colorbar(im2, ax=ax2, label="Slope (deg)")
    _setup_panel(
        ax2,
        "Slope magnitude — "
        f"mean={slope_stats['mean']:.1f} p90={slope_stats['p90']:.1f} "
        f"max={slope_stats['max']:.1f} deg",
    )

    ax3 = axes[1][0]
    if rocks:
        sizes = [max(4.0, r.diameter * 20) for r in rocks]
        ax3.scatter(
            [r.x for r in rocks],
            [r.y for r in rocks],
            s=sizes,
            alpha=0.35,
            c="sienna",
            edgecolors="none",
        )
    ax3.set_xlim(0, side_x)
    ax3.set_ylim(0, side_y)
    ax3.set_aspect("equal")
    _setup_panel(
        ax3,
        f"Rock placement — k={terrain.rock_sfd_k} "
        f"(n={len(rocks)}, measured CFA={measured_cfa:.3f})",
    )

    ax4 = axes[1][1]
    d_theory = np.linspace(0.01, terrain.rock_diameter_range[1], 200)
    cfa_theory = [compute_cfa(terrain.rock_sfd_k, float(d)) for d in d_theory]
    ax4.semilogy(d_theory, cfa_theory, "b-", label="Golombek model", linewidth=2)
    d_thresh = np.linspace(
        terrain.rock_diameter_range[0],
        0.95 * terrain.rock_diameter_range[1],
        30,
    )
    cfa_sampled = [
        max(sum(math.pi / 4.0 * r.diameter**2 for r in rocks if r.diameter >= d) / area_m2, 1e-6)
        for d in d_thresh
    ]
    ax4.semilogy(d_thresh, cfa_sampled, "ro", label="Sampled", markersize=4)
    ax4.set_title("Size-Frequency Distribution")
    ax4.set_xlabel("Diameter threshold (m)")
    ax4.set_ylabel("CFA (fraction)")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    fig.suptitle(
        f"MarsLab scenario: {terrain.scenario_name or os.path.basename(output_png)}",
        fontsize=14,
    )
    fig.tight_layout()

    os.makedirs(os.path.dirname(output_png) or ".", exist_ok=True)
    fig.savefig(output_png, dpi=140)
    plt.close(fig)

    print(f"Saved: {output_png}")
    print(
        f"  elev range: [{float(elev.min()):.2f}, {float(elev.max()):.2f}] m | "
        f"slope p90={slope_stats['p90']:.2f} deg | "
        f"rocks n={len(rocks)} | measured CFA={measured_cfa:.4f} "
        f"(target k={terrain.rock_sfd_k})"
    )


def main(argv: list[str]) -> int:
    """Command-line entry point.

    Returns a non-zero exit code on failure so CI scripts can chain this
    visualizer into their acceptance pipeline.
    """
    if len(argv) < 2:
        print(__doc__)
        return 2
    yaml_path = argv[1]
    config = load_and_validate(yaml_path)
    scenario_name = config.terrain.scenario_name or os.path.splitext(os.path.basename(yaml_path))[0]

    if len(argv) >= 3:
        out_path = argv[2]
    else:
        out_path = os.path.join("_workspace", f"wk2_terrain_{scenario_name}.png")

    visualize(config, out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
