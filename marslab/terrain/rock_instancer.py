"""Rock 3D instancing on terrain for Isaac Sim.

Places rocks as 3D USD primitives on the terrain surface using
PointInstancer for efficient rendering. Supports OBJ mesh prototypes
(from generate_rock_meshes.py) or Sphere fallback. PBR material applied.
Requires Isaac Sim runtime — do NOT import from offline code.
"""

import os

import numpy as np
from pxr import Gf, Sdf, UsdGeom, UsdShade

from marslab.terrain.rock_placer import RockPlacement


def place_rocks_on_terrain(
    stage,
    rocks: list[RockPlacement],
    elevation: np.ndarray,
    resolution: float,
    prim_path: str = "/World/Rocks",
    seed: int = 42,
    rock_color: tuple[float, float, float] = (0.42, 0.28, 0.20),
    rock_roughness: float = 0.92,
    rock_mesh_dir: str | None = None,
) -> None:
    """Place rocks as 3D instanced primitives on the terrain.

    If rock_mesh_dir is provided and contains OBJ files, uses those
    as prototypes. Otherwise falls back to Sphere prototypes.
    PBR material applied from config (G5).

    Args:
        stage: USD stage.
        rocks: List of RockPlacement from sample_rocks_golombek().
        elevation: 2D terrain elevation array (rows, cols).
        resolution: Terrain meters per pixel.
        prim_path: USD path for the instancer.
        seed: Random seed for rotation randomization.
        rock_color: Mars rock base color RGB from config.
        rock_roughness: Rock surface roughness (0-1) from config.
        rock_mesh_dir: Path to OBJ mesh files (None = Sphere fallback).
    """
    if not rocks:
        return

    rng = np.random.default_rng(seed)
    rows, cols = elevation.shape
    elev = np.nan_to_num(elevation, nan=0.0)

    # Create prototypes
    proto_container_path = prim_path + "/Prototypes"
    stage.DefinePrim(Sdf.Path(proto_container_path), "Scope")

    proto_paths = _create_prototypes(stage, proto_container_path, rock_mesh_dir, rng)

    # Apply PBR material to all prototypes
    _apply_rock_material(stage, proto_container_path, proto_paths, rock_color, rock_roughness)

    # Build instancer data
    positions = []
    orientations = []
    scales = []
    proto_indices = []

    for rock in rocks:
        col_i = int(np.clip(rock.x / resolution, 0, cols - 1))
        row_i = int(np.clip(rock.y / resolution, 0, rows - 1))
        z = float(elev[row_i, col_i])

        positions.append(Gf.Vec3f(rock.x, rock.y, z))

        # Random rotation: yaw + pitch + roll for angular appearance
        yaw = rng.uniform(0, 360)
        pitch = rng.uniform(-20, 20)
        roll = rng.uniform(-20, 20)
        orientations.append(_euler_to_quath(roll, pitch, yaw))

        # Scale from diameter
        s = rock.diameter / 1.0
        scales.append(Gf.Vec3f(s, s, s * (rock.height / rock.diameter)))

        proto_indices.append(int(rng.integers(0, len(proto_paths))))

    # Create PointInstancer
    instancer = UsdGeom.PointInstancer.Define(stage, prim_path)
    rel = instancer.GetPrototypesRel()
    for p in proto_paths:
        rel.AddTarget(Sdf.Path(p))

    instancer.GetProtoIndicesAttr().Set(proto_indices)
    instancer.GetPositionsAttr().Set(positions)
    instancer.GetOrientationsAttr().Set(orientations)
    instancer.GetScalesAttr().Set(scales)

    # Apply semantic label for annotation
    prim = stage.GetPrimAtPath(prim_path)
    if prim.IsValid():
        prim.CreateAttribute("semanticLabel", Sdf.ValueTypeNames.String).Set("big_rock")


def _create_prototypes(stage, container_path: str, mesh_dir: str | None, rng) -> list[str]:
    """Create rock prototypes from OBJ files or Sphere fallback."""
    proto_paths = []

    if mesh_dir and os.path.isdir(mesh_dir):
        obj_files = sorted(f for f in os.listdir(mesh_dir) if f.endswith(".obj"))
        if obj_files:
            import trimesh

            for i, obj_file in enumerate(obj_files):
                proto_path = f"{container_path}/rock_{i}"
                mesh = trimesh.load(os.path.join(mesh_dir, obj_file), force="mesh")
                _create_usd_mesh_from_trimesh(stage, proto_path, mesh)
                proto_paths.append(proto_path)
            return proto_paths

    # Fallback: Sphere prototypes (6 variants)
    sphere_scales = [
        (1.0, 1.0, 0.4),
        (1.4, 0.7, 0.6),
        (0.8, 1.2, 0.35),
        (1.1, 0.9, 0.8),
        (0.7, 1.3, 0.5),
        (1.3, 0.6, 0.45),
    ]
    for i, (sx, sy, sz) in enumerate(sphere_scales):
        proto_path = f"{container_path}/rock_{i}"
        sphere = UsdGeom.Sphere.Define(stage, proto_path)
        sphere.GetRadiusAttr().Set(0.5)
        xform = UsdGeom.Xformable(sphere.GetPrim())
        xform.AddScaleOp().Set(Gf.Vec3f(sx, sy, sz))
        proto_paths.append(proto_path)

    return proto_paths


def _create_usd_mesh_from_trimesh(stage, prim_path: str, mesh) -> None:
    """Convert a trimesh.Trimesh to a USD Mesh prim."""
    usd_mesh = UsdGeom.Mesh.Define(stage, prim_path)
    usd_mesh.GetPointsAttr().Set(
        [Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])) for v in mesh.vertices]
    )
    usd_mesh.GetFaceVertexIndicesAttr().Set(mesh.faces.flatten().tolist())
    usd_mesh.GetFaceVertexCountsAttr().Set([3] * len(mesh.faces))
    usd_mesh.GetSubdivisionSchemeAttr().Set("none")


def _apply_rock_material(
    stage,
    container_path: str,
    proto_paths: list[str],
    color: tuple[float, float, float],
    roughness: float,
) -> None:
    """Apply Mars rock PBR material to all prototypes."""
    from isaacsim.core.api.materials.omni_pbr import OmniPBR

    mat_path = f"{container_path}/rock_material"
    material = OmniPBR(prim_path=mat_path)
    material.set_color(np.array(color))
    material.set_reflection_roughness(roughness)
    material.set_metallic_constant(0.0)

    mat_prim = stage.GetPrimAtPath(mat_path)
    if mat_prim.IsValid():
        mat_shade = UsdShade.Material(mat_prim)
        for proto_path in proto_paths:
            proto_prim = stage.GetPrimAtPath(proto_path)
            if proto_prim.IsValid():
                UsdShade.MaterialBindingAPI.Apply(proto_prim)
                UsdShade.MaterialBindingAPI(proto_prim).Bind(mat_shade)


def _euler_to_quath(roll_deg: float, pitch_deg: float, yaw_deg: float) -> Gf.Quath:
    """Convert euler angles (degrees) to Gf.Quath quaternion."""
    roll = np.radians(roll_deg)
    pitch = np.radians(pitch_deg)
    yaw = np.radians(yaw_deg)

    cr, sr = np.cos(roll / 2), np.sin(roll / 2)
    cp, sp = np.cos(pitch / 2), np.sin(pitch / 2)
    cy, sy = np.cos(yaw / 2), np.sin(yaw / 2)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy

    return Gf.Quath(float(w), float(x), float(y), float(z))
