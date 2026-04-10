"""Terrain mesh builder for Isaac Sim.

Converts a numpy elevation array into a USD mesh prim with collision,
UV coordinates for texture mapping, and computed normals.
Requires Isaac Sim runtime — do NOT import from offline code.
"""

import numpy as np
from pxr import Gf, Sdf, UsdGeom, UsdPhysics


def build_terrain_mesh(
    elevation: np.ndarray,
    resolution: float,
    stage,
    prim_path: str,
    uv_scale: float = 4.0,
) -> None:
    """Build a USD terrain mesh from a 2D elevation array.

    Creates a triangulated mesh prim on the given USD stage with
    physics collision, UV coordinates, and vertex normals.

    Args:
        elevation: 2D float array of shape (rows, cols) with height values in meters.
        resolution: Spatial resolution in meters per pixel.
        stage: USD stage (from omni.usd.get_context().get_stage()).
        prim_path: USD prim path for the mesh (e.g., "/World/terrain").
        uv_scale: UV tiling factor. Higher = more texture repetitions.

    Raises:
        ValueError: If elevation is not 2D or resolution is not positive.
    """
    if elevation.ndim != 2:
        raise ValueError(f"elevation must be 2D, got shape {elevation.shape}")
    if resolution <= 0:
        raise ValueError(f"resolution must be > 0, got {resolution}")

    rows, cols = elevation.shape

    # Generate vertices and UV coordinates
    points = []
    uvs = []
    for r in range(rows):
        for c in range(cols):
            x = c * resolution
            y = r * resolution
            z = float(elevation[r, c])
            if np.isnan(z):
                z = 0.0
            points.append(Gf.Vec3f(x, y, z))

            # UV: normalized [0,1] * uv_scale for tiling
            u = (c / max(cols - 1, 1)) * uv_scale
            v = (r / max(rows - 1, 1)) * uv_scale
            uvs.append(Gf.Vec2f(u, v))

    # Compute vertex normals from elevation gradients
    normals = _compute_normals(elevation, resolution)

    # Generate triangle indices (2 triangles per grid cell)
    face_indices = []
    face_counts = []
    for r in range(rows - 1):
        for c in range(cols - 1):
            i00 = r * cols + c
            i10 = (r + 1) * cols + c
            i01 = r * cols + (c + 1)
            i11 = (r + 1) * cols + (c + 1)

            face_indices.extend([i00, i10, i01])
            face_counts.append(3)

            face_indices.extend([i01, i10, i11])
            face_counts.append(3)

    # Create USD mesh prim
    mesh = UsdGeom.Mesh.Define(stage, prim_path)
    mesh.GetPointsAttr().Set(points)
    mesh.GetFaceVertexIndicesAttr().Set(face_indices)
    mesh.GetFaceVertexCountsAttr().Set(face_counts)
    mesh.GetSubdivisionSchemeAttr().Set("none")

    # Set normals (vertex interpolation)
    mesh.GetNormalsAttr().Set(normals)
    mesh.SetNormalsInterpolation("vertex")

    # Set UV coordinates as primvar "st"
    primvar_api = UsdGeom.PrimvarsAPI(mesh.GetPrim())
    uv_primvar = primvar_api.CreatePrimvar("st", Sdf.ValueTypeNames.Float2Array)
    uv_primvar.Set(uvs)
    uv_primvar.SetInterpolation("vertex")

    # Enable collision
    mesh_prim = stage.GetPrimAtPath(prim_path)
    UsdPhysics.CollisionAPI.Apply(mesh_prim)
    UsdPhysics.MeshCollisionAPI.Apply(mesh_prim)


def _compute_normals(elevation: np.ndarray, resolution: float) -> list:
    """Compute vertex normals from elevation gradients.

    Args:
        elevation: 2D elevation array (rows, cols).
        resolution: Meters per pixel.

    Returns:
        List of Gf.Vec3f normals, one per vertex.
    """
    rows, cols = elevation.shape
    elev = np.nan_to_num(elevation, nan=0.0)

    # Compute gradients (dz/dx, dz/dy)
    dy, dx = np.gradient(elev, resolution)

    normals = []
    for r in range(rows):
        for c in range(cols):
            n = Gf.Vec3f(-float(dx[r, c]), -float(dy[r, c]), 1.0)
            n = n.GetNormalized()
            normals.append(n)

    return normals
