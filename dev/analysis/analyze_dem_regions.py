"""Analyze HiRISE DEM to identify flat and crater candidate regions.

Scans the Jezero crater DEM with sliding windows to find:
  1. Flat regions: minimal elevation variation, low slope (Basic Mars scene)
  2. Crater regions: moderate elevation variation with concave center (Crater+Slopes scene)

Outputs a combined overview image showing both candidate types on the full DEM.

Usage:
    python3 dev/analysis/analyze_dem_regions.py
    python3 dev/analysis/analyze_dem_regions.py --dem-dir path/to/converted_dem/
"""

import argparse
import os
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from marslab.terrain.dem_loader import load_converted_dem  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_DEM_DIR = os.path.join(REPO_ROOT, "assets", "terrain", "dem", "jezero_crater_converted")
OUTPUT_DIR = os.path.join(REPO_ROOT, "work_log", "scene_generation")
OUTPUT_PNG = os.path.join(OUTPUT_DIR, "dem_regions_overview.png")

WINDOW_SIZE = 200  # pixels (= 200m at 1.0 m/px)
STRIDE = 20  # sliding window stride


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------


def compute_slope_deg(elevation: np.ndarray, resolution: float) -> np.ndarray:
    """Compute slope magnitude in degrees from elevation grid."""
    dy, dx = np.gradient(elevation, resolution)
    return np.degrees(np.arctan(np.sqrt(dx**2 + dy**2)))


def scan_windows(
    elevation: np.ndarray,
    resolution: float,
    window_size: int,
    stride: int,
) -> list[dict]:
    """Scan DEM with sliding windows and compute statistics for each."""
    rows, cols = elevation.shape
    slope = compute_slope_deg(elevation, resolution)
    results = []

    for r in range(0, rows - window_size + 1, stride):
        for c in range(0, cols - window_size + 1, stride):
            patch = elevation[r : r + window_size, c : c + window_size]
            slope_patch = slope[r : r + window_size, c : c + window_size]

            # Skip patches with NaN
            if np.any(np.isnan(patch)):
                continue

            dz = float(np.ptp(patch))  # max - min
            std = float(np.std(patch))
            mean_slope = float(np.mean(slope_patch))

            # Concavity: center elevation vs border mean
            center = patch[
                window_size // 4 : 3 * window_size // 4,
                window_size // 4 : 3 * window_size // 4,
            ]
            border_top = patch[: window_size // 4, :]
            border_bot = patch[3 * window_size // 4 :, :]
            border_left = patch[:, : window_size // 4]
            border_right = patch[:, 3 * window_size // 4 :]
            border_mean = np.mean(
                np.concatenate(
                    [
                        border_top.ravel(),
                        border_bot.ravel(),
                        border_left.ravel(),
                        border_right.ravel(),
                    ]
                )
            )
            center_mean = np.mean(center)
            concavity = float(border_mean - center_mean)  # positive = bowl shape

            results.append(
                {
                    "row": r,
                    "col": c,
                    "size": window_size,
                    "dz": dz,
                    "std": std,
                    "mean_slope": mean_slope,
                    "concavity": concavity,
                }
            )

    return results


def select_flat_candidates(windows: list[dict], n: int = 3) -> list[dict]:
    """Select top-N flattest windows by combined dz + slope score."""
    for w in windows:
        w["flat_score"] = w["dz"] + w["mean_slope"] * 2.0
    ranked = sorted(windows, key=lambda w: w["flat_score"])
    return ranked[:n]


def select_steep_candidates(windows: list[dict], n: int = 3) -> list[dict]:
    """Select top-N steepest windows by mean slope.

    Prioritizes regions where a rover will feel the incline: high mean
    slope with significant fraction of pixels above 5 degrees.
    """
    ranked = sorted(windows, key=lambda w: w["mean_slope"], reverse=True)
    return ranked[:n]


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------


def plot_overview(
    elevation: np.ndarray,
    resolution: float,
    flat_candidates: list[dict],
    crater_candidates: list[dict],
    output_path: str,
) -> None:
    """Plot full DEM with candidate regions marked."""
    rows, cols = elevation.shape
    extent = [0, cols * resolution, rows * resolution, 0]  # left, right, bottom, top

    fig, ax = plt.subplots(1, 1, figsize=(10, 10))
    im = ax.imshow(elevation, cmap="terrain", extent=extent, aspect="equal")
    fig.colorbar(im, ax=ax, shrink=0.7, label="Elevation (m)")
    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_title(
        f"Jezero HiRISE DEM ({rows}x{cols}, {resolution} m/px)\n"
        f"Elevation range: [{elevation.min():.1f}, {elevation.max():.1f}] m"
    )

    def _draw_candidates(cands: list[dict], color: str, tag: str, text_dy_top: bool) -> None:
        for i, w in enumerate(cands):
            x0 = w["col"] * resolution
            y0 = w["row"] * resolution
            sz = w["size"] * resolution
            is_primary = i == 0
            rect = mpatches.Rectangle(
                (x0, y0),
                sz,
                sz,
                linewidth=2.5 if is_primary else 1.5,
                edgecolor=color,
                facecolor="none",
                linestyle="-" if is_primary else "--",
            )
            ax.add_patch(rect)
            ax.text(
                x0 + 3,
                y0 + 12 if text_dy_top else y0 + sz - 5,
                f"{tag} #{i + 1}: dz={w['dz']:.1f}m, slope={w['mean_slope']:.1f}deg",
                color=color,
                fontsize=7,
                fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", facecolor="black", alpha=0.7),
            )

    _draw_candidates(flat_candidates, "lime", "Flat", text_dy_top=True)
    _draw_candidates(crater_candidates, "red", "Steep", text_dy_top=False)

    # Legend
    flat_patch = mpatches.Patch(edgecolor="lime", facecolor="none", label="Flat candidates")
    steep_patch = mpatches.Patch(edgecolor="red", facecolor="none", label="Steep candidates")
    ax.legend(handles=[flat_patch, steep_patch], loc="upper right", fontsize=9)

    fig.tight_layout()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[analyze_dem] Saved: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze HiRISE DEM regions")
    parser.add_argument(
        "--dem-dir",
        default=DEFAULT_DEM_DIR,
        help="Directory containing the converted DEM (elevation.npy + metadata.json)",
    )
    args = parser.parse_args()

    print(f"[analyze_dem] Loading DEM: {args.dem_dir}", flush=True)
    elevation, metadata = load_converted_dem(args.dem_dir)
    resolution = float(metadata.get("resolution_x", 1.0))
    print(
        f"[analyze_dem] DEM: {elevation.shape}, {resolution} m/px, "
        f"z=[{elevation.min():.1f}, {elevation.max():.1f}] m",
        flush=True,
    )

    print(
        f"[analyze_dem] Scanning with {WINDOW_SIZE}x{WINDOW_SIZE} windows, stride={STRIDE}...",
        flush=True,
    )
    windows = scan_windows(elevation, resolution, WINDOW_SIZE, STRIDE)
    print(f"[analyze_dem] {len(windows)} valid windows scanned.", flush=True)

    flat_candidates = select_flat_candidates(windows, n=3)
    steep_candidates = select_steep_candidates(windows, n=3)

    print("\n--- Flat Candidates ---")
    for i, w in enumerate(flat_candidates):
        print(
            f"  #{i + 1}: row={w['row']}, col={w['col']}, size={w['size']}, "
            f"dz={w['dz']:.2f}m, std={w['std']:.2f}m, slope={w['mean_slope']:.2f} deg"
        )

    print("\n--- Steep / Crater+Slopes Candidates ---")
    for i, w in enumerate(steep_candidates):
        print(
            f"  #{i + 1}: row={w['row']}, col={w['col']}, size={w['size']}, "
            f"dz={w['dz']:.2f}m, std={w['std']:.2f}m, slope={w['mean_slope']:.2f} deg, "
            f"concavity={w['concavity']:.2f}m"
        )

    print("\n[analyze_dem] Generating overview plot...", flush=True)
    plot_overview(elevation, resolution, flat_candidates, steep_candidates, OUTPUT_PNG)

    # Print crop commands for convenience
    if flat_candidates:
        f = flat_candidates[0]
        print("\n[analyze_dem] Recommended flat crop:")
        print(f"  row: {f['row']}, col: {f['col']}, height: {f['size']}, width: {f['size']}")
    if steep_candidates:
        c = steep_candidates[0]
        print("\n[analyze_dem] Recommended steep crop:")
        print(f"  row: {c['row']}, col: {c['col']}, height: {c['size']}, width: {c['size']}")


if __name__ == "__main__":
    main()
