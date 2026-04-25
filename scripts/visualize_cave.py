"""Offline cave mesh visualization.

Generates a 4-panel matplotlib figure showing the procedurally generated
cave from multiple views, plus an OBJ export for external viewing.

Usage:
    python3 scripts/visualize_cave.py [--seed 42] [--width 200]
                                      [--output work_log/scene_generation/cave_preview.png]
"""

import argparse
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from marslab.terrain.cave.orchestrator import generate_cave_mesh  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--width", type=float, default=200.0, help="Tube width (m)")
    parser.add_argument("--skylight-count", type=int, default=10, help="Skylights")
    parser.add_argument(
        "--skylight-diameter", type=float, default=20.0, help="Skylight diameter (m)"
    )
    parser.add_argument("--debris-cone-count", type=int, default=5, help="Debris cones")
    parser.add_argument("--domain", type=int, default=400, help="Domain size (px)")
    parser.add_argument(
        "--output",
        default=os.path.join(REPO_ROOT, "work_log", "scene_generation", "cave_preview.png"),
        help="Output image path",
    )
    parser.add_argument("--export-obj", action="store_true", help="Also export OBJ")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    print(
        f"Generating cave mesh (seed={args.seed}, width={args.width}m, "
        f"domain={args.domain}x{args.domain}) ...",
        flush=True,
    )

    result = generate_cave_mesh(
        tube_width_m=args.width,
        skylight_count=args.skylight_count,
        skylight_diameter_m=args.skylight_diameter,
        debris_cone_count=args.debris_cone_count,
        domain_size=(args.domain, args.domain),
        resolution=1.0,
        seed=args.seed,
    )

    tube = result["tube_mesh"]
    floor = result["floor_mesh"]
    surface = result["surface_mesh"]
    meta = result["metadata"]
    skylights = result["skylight_positions"]
    breakdowns = result["breakdown_positions"]

    print(f"  Tube: {len(tube.vertices)} verts, {len(tube.faces)} faces")
    print(f"  Floor: {len(floor.vertices)} verts, {len(floor.faces)} faces")
    print(f"  Surface: {len(surface.vertices)} verts, {len(surface.faces)} faces")
    print(f"  Skylights: {len(skylights)}")
    print(f"  Debris cones: {len(result['debris_cones'])}")
    print(f"  Breakdown blocks: {len(breakdowns)}")

    # --- Figure ---
    fig = plt.figure(figsize=(16, 12))
    fig.suptitle(
        f"Mars Cave (Lava Tube) Preview — width={args.width}m, seed={args.seed}",
        fontsize=14,
        fontweight="bold",
    )

    def _setup_panel(
        ax, title: str, xlabel: str, ylabel: str, equal: bool = False, zlabel: str | None = None
    ):
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        if zlabel is not None:
            ax.set_zlabel(zlabel)
        if equal:
            ax.set_aspect("equal")

    # Panel 1: Plan view (XY) — tube footprint + skylight + breakdowns
    ax1 = fig.add_subplot(2, 2, 1)
    _setup_panel(ax1, "Plan View (Top-Down)", "X (m)", "Y (m)", equal=True)

    # Tube floor outline (scatter floor vertices)
    fv = floor.vertices
    ax1.scatter(fv[:, 0], fv[:, 1], s=0.3, c="saddlebrown", alpha=0.4, label="Floor")

    # Skylight circles
    for i, (sx, sy) in enumerate(skylights):
        circle = plt.Circle(
            (sx, sy),
            args.skylight_diameter / 2.0,
            fill=False,
            edgecolor="gold",
            linewidth=2,
            linestyle="--",
            label="Skylight" if i == 0 else None,
        )
        ax1.add_patch(circle)

    # Debris cones
    debris_cones = result["debris_cones"]
    for i, cone in enumerate(debris_cones):
        cx = cone.vertices[:, 0].mean()
        cy = cone.vertices[:, 1].mean()
        ax1.plot(
            cx,
            cy,
            "^",
            color="darkorange",
            markersize=8,
            label="Debris cone" if i == 0 else None,
        )

    # Breakdown blocks (sample for performance)
    if breakdowns:
        bx = [b["x"] for b in breakdowns[:500]]
        by = [b["y"] for b in breakdowns[:500]]
        bd = [b["diameter"] for b in breakdowns[:500]]
        ax1.scatter(bx, by, s=[d * 3 for d in bd], c="gray", alpha=0.3, label="Breakdown")

    ax1.set_xlim(0, meta["domain_m"][1])
    ax1.set_ylim(0, meta["domain_m"][0])
    ax1.legend(fontsize=8, loc="upper right")

    # Panel 2: Cross-section at mid-point
    ax2 = fig.add_subplot(2, 2, 2)
    _setup_panel(ax2, "Cross-Section (Mid-Tube)", "Horizontal offset (m)", "Z (m)", equal=True)

    # Extract a cross-section slice through the middle
    tv = tube.vertices
    mid_y = np.median(tv[:, 1])
    slice_mask = np.abs(tv[:, 1] - mid_y) < 5.0
    if slice_mask.sum() > 0:
        slice_pts = tv[slice_mask]
        ax2.scatter(slice_pts[:, 0], slice_pts[:, 2], s=1, c="darkslategray")

    # Floor slice
    floor_mid_mask = np.abs(fv[:, 1] - mid_y) < 5.0
    if floor_mid_mask.sum() > 0:
        floor_slice = fv[floor_mid_mask]
        ax2.scatter(floor_slice[:, 0], floor_slice[:, 2], s=2, c="sienna")

    # Surface line
    ax2.axhline(y=meta["surface_z"], color="olive", linestyle="--", alpha=0.5, label="Surface")
    ax2.legend(fontsize=8)

    # Panel 3: Longitudinal section (along tube axis)
    ax3 = fig.add_subplot(2, 2, 3)
    _setup_panel(ax3, "Longitudinal Section (Along Tube)", "Along-tube distance (m)", "Z (m)")

    # Project onto tube direction
    mid_x = np.median(tv[:, 0])
    long_mask = np.abs(tv[:, 0] - mid_x) < args.width * 0.3
    if long_mask.sum() > 0:
        long_pts = tv[long_mask]
        ax3.scatter(
            long_pts[:, 1], long_pts[:, 2], s=0.5, c="darkslategray", alpha=0.3, label="Tube shell"
        )

    floor_long_mask = np.abs(fv[:, 0] - mid_x) < args.width * 0.3
    if floor_long_mask.sum() > 0:
        floor_long = fv[floor_long_mask]
        ax3.scatter(floor_long[:, 1], floor_long[:, 2], s=0.5, c="sienna", alpha=0.3, label="Floor")

    ax3.axhline(y=meta["surface_z"], color="olive", linestyle="--", alpha=0.5, label="Surface")
    ax3.legend(fontsize=8)

    # Panel 4: 3D wireframe
    ax4 = fig.add_subplot(2, 2, 4, projection="3d")
    _setup_panel(ax4, "3D View", "X", "Y", zlabel="Z")

    # Subsample for performance
    step = max(1, len(tube.vertices) // 2000)
    tv_sub = tube.vertices[::step]
    ax4.scatter(
        tv_sub[:, 0], tv_sub[:, 1], tv_sub[:, 2], s=0.3, c="darkslategray", alpha=0.3, label="Tube"
    )

    fv_sub = floor.vertices[:: max(1, len(floor.vertices) // 1000)]
    ax4.scatter(
        fv_sub[:, 0], fv_sub[:, 1], fv_sub[:, 2], s=0.3, c="sienna", alpha=0.3, label="Floor"
    )

    # Skylight shafts
    for shaft in result["skylight_meshes"]:
        sv = shaft.vertices[:: max(1, len(shaft.vertices) // 200)]
        ax4.scatter(sv[:, 0], sv[:, 1], sv[:, 2], s=0.5, c="gold", alpha=0.5)

    ax4.view_init(elev=30, azim=-60)

    plt.tight_layout()
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    fig.savefig(args.output, dpi=150, bbox_inches="tight")
    print(f"Saved: {args.output}")
    plt.close(fig)

    # Optional OBJ export
    if args.export_obj:
        import trimesh as tm

        combined = tm.util.concatenate(
            [tube, floor, surface] + result["skylight_meshes"] + result["debris_cones"]
        )
        obj_path = args.output.replace(".png", ".obj")
        combined.export(obj_path)
        print(f"Exported OBJ: {obj_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
