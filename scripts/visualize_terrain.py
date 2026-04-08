"""Offline terrain visualization for developer review.

Generates three plots without Isaac Sim:
    1. Real HiRISE DEM elevation heatmap (falls back to synthetic if unavailable)
    2. Rock placement scatter plot
    3. SFD curve: theoretical CFA vs sampled CFA

Run: python3 scripts/visualize_terrain.py

Output: work_log/terrain_visualization.png
"""

import math
import os

import matplotlib.pyplot as plt
import numpy as np

from marslab.terrain.rock_placer import compute_cfa, sample_rocks_golombek

REAL_DEM_PATH = "assets/terrain/dem/jezero_crater.tif"


def main() -> None:
    """Generate terrain visualization plots."""
    # --- Load DEM ---
    if os.path.isfile(REAL_DEM_PATH):
        from marslab.terrain.dem_loader import load_hirise_dem

        dem, meta = load_hirise_dem(REAL_DEM_PATH)
        side_x = meta["width"] * meta["resolution_x"]
        side_y = meta["height"] * meta["resolution_y"]
        area = side_x * side_y
        side = math.sqrt(area)
        dem_title = f"Jezero Crater DEM ({meta['width']}x{meta['height']}, 1m/px)"
        print(f"Using real DEM: {REAL_DEM_PATH}")
    else:
        rng = np.random.default_rng(42)
        dem = rng.uniform(-2500, -2400, (100, 100)).astype(np.float32)
        side_x, side_y = 100.0, 100.0
        area = 10000.0
        side = 100.0
        dem_title = "Synthetic DEM Elevation"
        print("Real DEM not found, using synthetic data")

    # --- Parameters ---
    k = 0.05
    d_range = (0.05, 3.0)
    seed = 42

    # --- Generate rocks ---
    rocks = sample_rocks_golombek(area, k, d_range, seed=seed)

    # --- Create figure ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Plot 1: DEM elevation heatmap
    ax1 = axes[0]
    im = ax1.imshow(dem, cmap="terrain", origin="lower", extent=[0, side_x, 0, side_y])
    fig.colorbar(im, ax=ax1, label="Elevation (m)")
    ax1.set_title(dem_title)
    ax1.set_xlabel("X (m)")
    ax1.set_ylabel("Y (m)")

    # Plot 2: Rock placement scatter
    ax2 = axes[1]
    if rocks:
        xs = [r.x for r in rocks]
        ys = [r.y for r in rocks]
        sizes = [r.diameter * 20 for r in rocks]  # scale for visibility
        ax2.scatter(xs, ys, s=sizes, alpha=0.3, c="sienna", edgecolors="none")
    ax2.set_xlim(0, side)
    ax2.set_ylim(0, side)
    ax2.set_aspect("equal")
    ax2.set_title(f"Rock Placement (k={k}, n={len(rocks)})")
    ax2.set_xlabel("X (m)")
    ax2.set_ylabel("Y (m)")

    # Plot 3: SFD curve — theoretical vs sampled
    ax3 = axes[2]
    diameters_theory = np.linspace(0.01, 3.0, 200)
    cfa_theory = [compute_cfa(k, d) for d in diameters_theory]
    ax3.semilogy(diameters_theory, cfa_theory, "b-", label="Golombek model", linewidth=2)

    # Sampled CFA: for each diameter threshold, fraction of area covered by larger rocks
    d_thresholds = np.linspace(0.05, 2.5, 30)
    cfa_sampled = []
    for d_thresh in d_thresholds:
        rock_area = sum(math.pi / 4 * r.diameter**2 for r in rocks if r.diameter >= d_thresh)
        cfa_sampled.append(rock_area / area)
    ax3.semilogy(d_thresholds, cfa_sampled, "ro", label="Sampled", markersize=4)

    ax3.set_title("Size-Frequency Distribution")
    ax3.set_xlabel("Diameter (m)")
    ax3.set_ylabel("CFA (fraction)")
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # --- Save ---
    os.makedirs("work_log", exist_ok=True)
    output_path = "work_log/terrain_visualization.png"
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {output_path}")


if __name__ == "__main__":
    main()
