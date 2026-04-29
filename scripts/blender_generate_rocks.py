"""Blender headless rock mesh generation for Mars simulation.

Generates angular rock meshes using Blender's Displace modifier
with cloud noise, then decimates to target poly count.
Much higher quality than trimesh icosphere deformation.

Run: blender --background --python scripts/blender_generate_rocks.py

Output: assets/mars_assets/mars_rocks/meshes/rock_blender_{0-7}.obj
"""

import os
import random

import bpy


def clear_scene() -> None:
    """Remove all objects from the scene."""
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def generate_rock(seed: int, output_path: str, target_faces: int = 2000) -> None:
    """Generate a single angular rock mesh and export as OBJ.

    Args:
        seed: Random seed for reproducibility.
        output_path: Path to save the OBJ file.
        target_faces: Target face count after decimation.
    """
    random.seed(seed)
    clear_scene()

    # 1. Create icosphere (subdivisions=4 = ~5120 faces, decimated to target)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.5)
    obj = bpy.context.active_object
    obj.name = f"rock_{seed}"

    # 2. Non-uniform scale for variety
    sx = random.uniform(0.5, 1.5)
    sy = random.uniform(0.5, 1.5)
    sz = random.uniform(0.25, 0.85)
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)

    # 3. Two displacement passes (cloud noise for angular shape, musgrave for detail)
    def _apply_displace(mod_name: str, tex_name: str, tex_type: str, strength: float) -> None:
        tex = bpy.data.textures.new(tex_name, type=tex_type)
        tex.noise_scale = (
            random.uniform(0.3, 0.9) if tex_type == "CLOUDS" else random.uniform(0.5, 1.5)
        )
        if tex_type == "CLOUDS":
            tex.noise_depth = random.randint(2, 6)
        mod = obj.modifiers.new(mod_name, "DISPLACE")
        mod.texture = tex
        mod.strength = strength
        mod.mid_level = 0.5
        bpy.ops.object.modifier_apply(modifier=mod_name)

    _apply_displace("Displace1", f"RockNoise_{seed}", "CLOUDS", random.uniform(0.12, 0.35))
    _apply_displace("Displace2", f"RockDetail_{seed}", "MUSGRAVE", random.uniform(0.03, 0.10))

    # 5. Decimate to target poly count
    current_faces = len(obj.data.polygons)
    if current_faces > target_faces:
        mod_dec = obj.modifiers.new("Decimate", "DECIMATE")
        mod_dec.ratio = target_faces / current_faces
        bpy.ops.object.modifier_apply(modifier="Decimate")

    # 6. Normalize to unit bounding box (radius ~0.5)
    max_dim = max(obj.dimensions)
    if max_dim > 0:
        scale_factor = 1.0 / max_dim
        obj.scale = (scale_factor, scale_factor, scale_factor)
        bpy.ops.object.transform_apply(scale=True)

    # 7. Export OBJ
    bpy.ops.wm.obj_export(
        filepath=output_path,
        export_selected_objects=True,
        export_uv=False,
        export_normals=True,
        export_materials=False,
    )

    final_faces = len(obj.data.polygons)
    print(f"  {os.path.basename(output_path)}: {final_faces} faces")


def main() -> None:
    # Resolve output directory relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    output_dir = os.path.join(project_dir, "assets", "rocks")
    os.makedirs(output_dir, exist_ok=True)

    # Remove old trimesh rocks
    for f in os.listdir(output_dir):
        if f.startswith("rock_proto_") and f.endswith(".obj"):
            os.remove(os.path.join(output_dir, f))
            print(f"  Removed old: {f}")

    num_prototypes = 8
    base_seed = 42

    print(f"[blender_rocks] Generating {num_prototypes} rock prototypes...")

    for i in range(num_prototypes):
        output_path = os.path.join(output_dir, f"rock_blender_{i}.obj")
        generate_rock(seed=base_seed + i, output_path=output_path)

    print(f"\n[blender_rocks] Done. Output: {output_dir}/")


if __name__ == "__main__":
    main()
