"""DEM elevation grid to 3D terrain mesh converter.

Two layers (offline-first testing):
  Layer 1: ``compute_mesh_arrays()`` -- pure numpy, offline-testable.
  Layer 2: ``build_terrain_mesh()`` -- USD writer requiring Isaac Sim.

Triangle winding is CCW from +Z so PhysX normals point upward:
  Triangle 1: [i00, i01, i10]   Triangle 2: [i01, i11, i10]
"""

import numpy as np

# Each quad in the elevation grid splits into two triangles, three
# vertex indices each, so face index storage is 6 ints per quad.
_VERTS_PER_QUAD = 6  # 2 tris * 3 verts


def compute_mesh_arrays(
    elevation: np.ndarray,
    resolution: float,
    uv_scale: float = 1.0,
) -> dict:
    """Compute mesh geometry arrays from an elevation grid.

    Pure numpy — no Isaac Sim dependency. Offline-testable.

    The elevation array is normalized so that its minimum value becomes
    zero. This prevents absolute Mars datum coordinates (~-2518 m) from
    reaching the physics engine, which caused spawn-z coupling bugs in
    previous implementations.

    Args:
        elevation: 2D float32 array of shape (rows, cols) in meters.
            NaN values are replaced with 0.0 after normalization.
        resolution: Meters per pixel (grid spacing).
        uv_scale: UV tiling factor for texture mapping.

    Returns:
        Dict with keys:
            ``points``: np.ndarray shape (N, 3) float32
            ``normals``: np.ndarray shape (N, 3) float32
            ``face_indices``: list[int] (3 ints per triangle)
            ``face_counts``: list[int] (all 3s)
            ``uvs``: np.ndarray shape (N, 2) float32
            ``normalized_elevation``: np.ndarray shape (rows, cols) float32

    Raises:
        ValueError: If the elevation grid is too small to form triangles
            (needs at least 2x2) or resolution is non-positive.
    """
    if elevation.ndim != 2:
        raise ValueError(f"elevation must be 2D, got shape {elevation.shape}")
    rows, cols = elevation.shape
    if rows < 2 or cols < 2:
        raise ValueError(f"elevation must be at least 2x2 to form triangles, got ({rows}, {cols})")
    if resolution <= 0:
        raise ValueError(f"resolution must be > 0, got {resolution}")

    # Normalize: shift minimum to zero, replace NaN with 0.
    elev = elevation.astype(np.float32, copy=True)
    valid_min = np.nanmin(elev)
    elev -= valid_min
    elev = np.nan_to_num(elev, nan=0.0)

    # --- Vertices ---
    n_verts = rows * cols
    points = np.empty((n_verts, 3), dtype=np.float32)

    col_indices = np.arange(cols, dtype=np.float32)
    row_indices = np.arange(rows, dtype=np.float32)
    col_grid, row_grid = np.meshgrid(col_indices, row_indices)

    points[:, 0] = (col_grid * resolution).ravel()
    points[:, 1] = (row_grid * resolution).ravel()
    points[:, 2] = elev.ravel()

    # --- Face indices (CCW winding for +Z normals; see module docstring) ---
    n_quads = (rows - 1) * (cols - 1)
    face_indices = np.empty(n_quads * _VERTS_PER_QUAD, dtype=np.int32)

    r_idx = np.arange(rows - 1)
    c_idx = np.arange(cols - 1)
    rc, cc = np.meshgrid(r_idx, c_idx, indexing="ij")
    rc = rc.ravel()
    cc = cc.ravel()

    i00 = rc * cols + cc
    i01 = rc * cols + (cc + 1)
    i10 = (rc + 1) * cols + cc
    i11 = (rc + 1) * cols + (cc + 1)

    # Triangle 1: i00, i01, i10
    face_indices[0::_VERTS_PER_QUAD] = i00
    face_indices[1::_VERTS_PER_QUAD] = i01
    face_indices[2::_VERTS_PER_QUAD] = i10
    # Triangle 2: i01, i11, i10
    face_indices[3::_VERTS_PER_QUAD] = i01
    face_indices[4::_VERTS_PER_QUAD] = i11
    face_indices[5::_VERTS_PER_QUAD] = i10

    n_faces = n_quads * 2
    face_counts = [3] * n_faces

    # --- UV coordinates ---
    uvs = np.empty((n_verts, 2), dtype=np.float32)
    u_vals = col_indices / max(cols - 1, 1) * uv_scale
    v_vals = row_indices / max(rows - 1, 1) * uv_scale
    u_grid, v_grid = np.meshgrid(u_vals, v_vals)
    uvs[:, 0] = u_grid.ravel()
    uvs[:, 1] = v_grid.ravel()

    # --- Vertex normals (from gradient) ---
    normals = _compute_vertex_normals(elev, resolution)

    return {
        "points": points,
        "normals": normals,
        "face_indices": face_indices.tolist(),
        "face_counts": face_counts,
        "uvs": uvs,
        "normalized_elevation": elev,
    }


def _compute_vertex_normals(elevation: np.ndarray, resolution: float) -> np.ndarray:
    """Compute per-vertex normals from elevation gradients.

    Uses numpy.gradient for central differences. The resulting normals
    point generally upward (+Z) on typical terrain.

    Args:
        elevation: 2D float32 normalized elevation array.
        resolution: Grid spacing in meters.

    Returns:
        np.ndarray of shape (rows*cols, 3) float32, unit normals.
    """
    dy, dx = np.gradient(elevation, resolution)
    rows, cols = elevation.shape
    n_verts = rows * cols

    normals = np.empty((n_verts, 3), dtype=np.float32)
    normals[:, 0] = (-dx).ravel()
    normals[:, 1] = (-dy).ravel()
    normals[:, 2] = 1.0

    # Normalize to unit length
    lengths = np.sqrt(np.sum(normals**2, axis=1, keepdims=True))
    lengths = np.maximum(lengths, 1e-8)
    normals /= lengths

    return normals


def terrain_z_at(
    elevation: np.ndarray,
    resolution: float,
    x: float,
    y: float,
    strict: bool = False,
) -> float:
    """Bilinear interpolation of terrain elevation at world (x, y).

    Pure numpy -- no Isaac Sim dependency. Used to compute rover spawn z
    and rock placement heights.

    Args:
        elevation: 2D normalized elevation array (z_min=0).
        resolution: Meters per pixel.
        x: World x coordinate in meters.
        y: World y coordinate in meters.
        strict: When ``True``, raise ``ValueError`` if ``(x, y)`` falls
            outside the elevation grid bounds. When ``False`` (default),
            the query is clamped to the nearest valid cell so callers
            that sweep slightly outside the heightmap (rover BBox at
            domain edges) still receive a finite value.

    Returns:
        Interpolated elevation in meters.

    Raises:
        ValueError: If ``strict=True`` and ``(x, y)`` is outside the
            ``[0, (cols-1)*resolution] x [0, (rows-1)*resolution]`` box.
    """
    rows, cols = elevation.shape
    if strict:
        x_max = (cols - 1) * resolution
        y_max = (rows - 1) * resolution
        if x < 0.0 or x > x_max or y < 0.0 or y > y_max:
            raise ValueError(
                f"terrain_z_at({x}, {y}) is outside elevation bounds "
                f"[0, {x_max}] x [0, {y_max}] (strict=True)"
            )
    col_f = float(np.clip(x / resolution, 0.0, cols - 1.0))
    row_f = float(np.clip(y / resolution, 0.0, rows - 1.0))

    c0 = int(col_f)
    r0 = int(row_f)
    c1 = min(c0 + 1, cols - 1)
    r1 = min(r0 + 1, rows - 1)

    dc = col_f - c0
    dr = row_f - r0

    z00 = float(elevation[r0, c0])
    z01 = float(elevation[r0, c1])
    z10 = float(elevation[r1, c0])
    z11 = float(elevation[r1, c1])

    z = z00 * (1 - dc) * (1 - dr) + z01 * dc * (1 - dr) + z10 * (1 - dc) * dr + z11 * dc * dr
    return z


def build_terrain_mesh(
    elevation: np.ndarray,
    resolution: float,
    stage,
    prim_path: str,
    uv_scale: float = 1.0,
) -> np.ndarray:
    """Build a USD terrain mesh with collision from an elevation grid.

    Calls ``compute_mesh_arrays()`` internally, then creates a
    ``UsdGeom.Mesh`` prim with ``UsdPhysics.CollisionAPI`` and
    ``UsdPhysics.MeshCollisionAPI`` (approximation="none" for exact
    triangle collision).

    Args:
        elevation: 2D float32 elevation array (rows, cols) in meters.
        resolution: Meters per pixel.
        stage: USD stage (from omni.usd.get_context().get_stage()).
        prim_path: USD prim path for the terrain mesh.
        uv_scale: UV tiling factor.

    Returns:
        The normalized elevation array (z_min=0) for use by
        ``terrain_z_at()`` and rock height sampling.
    """
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics, Vt

    mesh_data = compute_mesh_arrays(elevation, resolution, uv_scale)

    points_np = mesh_data["points"]
    normals_np = mesh_data["normals"]
    uvs_np = mesh_data["uvs"]
    face_indices = mesh_data["face_indices"]
    face_counts = mesh_data["face_counts"]

    # Convert numpy arrays to USD types
    points_vt = Vt.Vec3fArray([Gf.Vec3f(float(p[0]), float(p[1]), float(p[2])) for p in points_np])
    normals_vt = Vt.Vec3fArray(
        [Gf.Vec3f(float(n[0]), float(n[1]), float(n[2])) for n in normals_np]
    )

    # Define the mesh prim
    mesh = UsdGeom.Mesh.Define(stage, prim_path)
    mesh.GetPointsAttr().Set(points_vt)
    mesh.GetFaceVertexIndicesAttr().Set(face_indices)
    mesh.GetFaceVertexCountsAttr().Set(face_counts)
    mesh.GetSubdivisionSchemeAttr().Set("none")

    # Vertex normals
    mesh.GetNormalsAttr().Set(normals_vt)
    mesh.SetNormalsInterpolation("vertex")

    # UV coordinates (texture mapping)
    uv_primvar = UsdGeom.PrimvarsAPI(mesh.GetPrim()).CreatePrimvar(
        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex
    )
    uvs_vt = Vt.Vec2fArray([Gf.Vec2f(float(u[0]), float(u[1])) for u in uvs_np])
    uv_primvar.Set(uvs_vt)

    # Physics collision (exact triangle mesh, no convex hull)
    prim = mesh.GetPrim()
    UsdPhysics.CollisionAPI.Apply(prim)
    mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
    mesh_collision.GetApproximationAttr().Set("none")

    # Semantic label for annotation
    prim.CreateAttribute("semanticLabel", Sdf.ValueTypeNames.String).Set("soil")

    return mesh_data["normalized_elevation"]
