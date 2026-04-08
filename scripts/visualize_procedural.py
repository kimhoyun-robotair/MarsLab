"""Offline procedural terrain visualization for developer review.

Generates a comparison of three terrain presets (flat, crater, hills)
with rock placement overlay.

Run: python3 scripts/visualize_procedural.py

Output: work_log/procedural_terrain_visualization.png
"""

import os

import matplotlib.pyplot as plt

from marslab.terrain.procedural_generator import generate_terrain
from marslab.terrain.rock_placer import sample_rocks_golombek

PRESETS = [
    ("flat", 0.03),
    ("crater", 0.06),
    ("hills", 0.04),
]


def main() -> None:
    """Generate procedural terrain comparison plots."""
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))

    for col, (preset, k) in enumerate(PRESETS):
        elev, meta = generate_terrain(preset, (256, 256), 1.0, seed=42)
        side_x = meta["width"] * meta["resolution_x"]
        side_y = meta["height"] * meta["resolution_y"]
        area = side_x * side_y

        rocks = sample_rocks_golombek(area, k, (0.20, 3.0), seed=42)

        # Top row: elevation heatmap
        ax_top = axes[0, col]
        im = ax_top.imshow(elev, cmap="terrain", origin="lower", extent=[0, side_x, 0, side_y])
        fig.colorbar(im, ax=ax_top, label="Elevation (m)", shrink=0.8)
        ax_top.set_title(f"{preset.capitalize()} (k={k})")
        ax_top.set_xlabel("X (m)")
        ax_top.set_ylabel("Y (m)")

        # Bottom row: rock placement
        ax_bot = axes[1, col]
        ax_bot.imshow(
            elev, cmap="terrain", origin="lower", extent=[0, side_x, 0, side_y], alpha=0.4
        )
        if rocks:
            xs = [r.x for r in rocks]
            ys = [r.y for r in rocks]
            sizes = [r.diameter * 30 for r in rocks]
            ax_bot.scatter(xs, ys, s=sizes, alpha=0.4, c="sienna", edgecolors="none")
        ax_bot.set_xlim(0, side_x)
        ax_bot.set_ylim(0, side_y)
        ax_bot.set_title(f"Rocks: {len(rocks):,}")
        ax_bot.set_xlabel("X (m)")
        ax_bot.set_ylabel("Y (m)")

    os.makedirs("work_log", exist_ok=True)
    fig.tight_layout()
    fig.savefig("work_log/procedural_terrain_visualization.png", dpi=150)
    plt.close(fig)
    print("Saved: work_log/procedural_terrain_visualization.png")


if __name__ == "__main__":
    main()
