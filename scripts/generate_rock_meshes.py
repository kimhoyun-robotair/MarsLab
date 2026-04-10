"""Generate procedural angular rock meshes for Mars simulation.

Creates 8 rock prototypes by deforming icospheres with noise.
No Isaac Sim required — runs with system Python + trimesh (P3).
Seed-based reproducibility (G5).

Run: python3 scripts/generate_rock_meshes.py
Output: assets/rocks/rock_proto_{0-7}.obj
"""

import os

import numpy as np
import trimesh


def generate_rock_mesh(seed: int, subdivisions: int = 2) -> trimesh.Trimesh:
    """Generate a single angular rock mesh from a deformed icosphere.

    Args:
        seed: Random seed for reproducibility.
        subdivisions: Icosphere subdivision level (2 = ~160 faces).

    Returns:
        A trimesh.Trimesh object representing the rock.
    """
    rng = np.random.default_rng(seed)

    # Start with icosphere
    mesh = trimesh.creation.icosphere(subdivisions=subdivisions)
    verts = np.array(mesh.vertices, dtype=np.float64)

    # Non-uniform scale for variety (flat slabs, elongated, blocky)
    scale = rng.uniform([0.5, 0.5, 0.25], [1.5, 1.5, 0.9])
    verts *= scale

    # Radial vertex displacement (creates angular irregularity)
    for i in range(len(verts)):
        r = np.linalg.norm(verts[i])
        if r > 0:
            # Multi-frequency noise for natural look
            noise_low = rng.uniform(-0.20, 0.20)
            noise_high = rng.uniform(-0.08, 0.08)
            verts[i] = verts[i] * (1.0 + noise_low + noise_high)

    # Optional: slight random shear for more angular appearance
    shear = rng.uniform(-0.15, 0.15, size=(3,))
    verts[:, 0] += verts[:, 2] * shear[0]
    verts[:, 1] += verts[:, 2] * shear[1]
    verts[:, 2] += verts[:, 0] * shear[2]

    mesh.vertices = verts

    # Normalize to unit radius (will be scaled by rock diameter in instancer)
    max_extent = np.max(np.abs(verts))
    if max_extent > 0:
        mesh.vertices /= max_extent * 2.0  # radius ~0.5

    return mesh


def main() -> None:
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "assets",
        "rocks",
    )
    os.makedirs(output_dir, exist_ok=True)

    num_prototypes = 8
    base_seed = 42

    print(f"[generate_rock_meshes] Generating {num_prototypes} rock prototypes...")

    for i in range(num_prototypes):
        mesh = generate_rock_mesh(seed=base_seed + i)
        filepath = os.path.join(output_dir, f"rock_proto_{i}.obj")
        mesh.export(filepath)
        print(f"  rock_proto_{i}.obj: {len(mesh.vertices)} verts, {len(mesh.faces)} faces")

    print(f"\n[generate_rock_meshes] Done. Output: {output_dir}/")


if __name__ == "__main__":
    main()
