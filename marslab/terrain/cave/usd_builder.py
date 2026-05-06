"""Cave mesh USD builder (Layer 2).

Converts trimesh objects from :mod:`marslab.terrain.cave.orchestrator`
into USD prims for Isaac Sim rendering and PhysX collision. Requires
Isaac Sim runtime.

Pattern follows mesh_builder.build_terrain_mesh() and
rock_instancer.place_rocks_on_terrain().
"""

from __future__ import annotations

import numpy as np
import trimesh


def _trimesh_to_usd_prim(
    stage,
    mesh: trimesh.Trimesh,
    prim_path: str,
    semantic_label: str = "cave_wall",
    double_sided: bool = True,
) -> None:
    """Convert a trimesh.Trimesh to a USD Mesh prim with collision.

    Args:
        stage: USD stage.
        mesh: Source trimesh mesh.
        prim_path: USD prim path (e.g. "/World/Cave/Tube").
        semantic_label: Semantic label for annotation.
        double_sided: Whether the mesh renders/collides on both sides.
    """
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics, Vt

    verts = mesh.vertices
    faces = mesh.faces

    # Points
    points_vt = Vt.Vec3fArray([Gf.Vec3f(float(v[0]), float(v[1]), float(v[2])) for v in verts])

    # Face indices (triangles)
    face_indices = faces.ravel().tolist()
    face_counts = [3] * len(faces)

    # Vertex normals (computed by trimesh)
    normals = mesh.vertex_normals
    normals_vt = Vt.Vec3fArray([Gf.Vec3f(float(n[0]), float(n[1]), float(n[2])) for n in normals])

    # Define mesh prim
    usd_mesh = UsdGeom.Mesh.Define(stage, prim_path)
    usd_mesh.GetPointsAttr().Set(points_vt)
    usd_mesh.GetFaceVertexIndicesAttr().Set(face_indices)
    usd_mesh.GetFaceVertexCountsAttr().Set(face_counts)
    usd_mesh.GetSubdivisionSchemeAttr().Set("none")

    # Normals
    usd_mesh.GetNormalsAttr().Set(normals_vt)
    usd_mesh.SetNormalsInterpolation("vertex")

    # Double-sided rendering for cave interiors
    if double_sided:
        usd_mesh.GetDoubleSidedAttr().Set(True)

    # UV coordinates (simple planar projection for now)
    n_verts = len(verts)
    uvs = np.zeros((n_verts, 2), dtype=np.float32)
    if n_verts > 0:
        x_range = verts[:, 0].max() - verts[:, 0].min()
        y_range = verts[:, 1].max() - verts[:, 1].min()
        if x_range > 1e-6 and y_range > 1e-6:
            uvs[:, 0] = (verts[:, 0] - verts[:, 0].min()) / x_range
            uvs[:, 1] = (verts[:, 1] - verts[:, 1].min()) / y_range

    uv_primvar = UsdGeom.PrimvarsAPI(usd_mesh.GetPrim()).CreatePrimvar(
        "st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex
    )
    uvs_vt = Vt.Vec2fArray([Gf.Vec2f(float(u[0]), float(u[1])) for u in uvs])
    uv_primvar.Set(uvs_vt)

    # Physics collision (exact triangle mesh)
    prim = usd_mesh.GetPrim()
    UsdPhysics.CollisionAPI.Apply(prim)
    mesh_collision = UsdPhysics.MeshCollisionAPI.Apply(prim)
    mesh_collision.GetApproximationAttr().Set("none")

    # Semantic label
    prim.CreateAttribute("semanticLabel", Sdf.ValueTypeNames.String).Set(semantic_label)


def build_cave_scene(
    cave_data: dict,
    stage,
    prim_base_path: str = "/World/Cave",
    seed: int | None = None,
) -> np.ndarray:
    """Build USD prims for all cave mesh components.

    Creates sub-prims under prim_base_path for each cave component:
        {base}/Surface    — ground surface (skylight holes cut)
        {base}/Tube       — tube ceiling + walls
        {base}/Floor      — tube floor
        {base}/Skylight_N — skylight shaft walls
        {base}/DebrisCone_N — debris piles
        {base}/Breakdown  — PointInstancer for breakdown blocks
        {base}/Breakdown/Prototypes/block_0 — icosphere prototype mesh
        {base}/Materials/BreakdownMtl — OmniPBR material bound to the
            breakdown prototype (created only when there is at least one
            breakdown block to instance).

    Args:
        cave_data: Dict from
            :func:`marslab.terrain.cave.orchestrator.generate_cave_mesh`.
        stage: USD stage.
        prim_base_path: Base USD prim path.
        seed: Optional RNG seed for the breakdown block orientation /
            scale draws.  When ``None`` the seed is sourced from
            ``cave_data["metadata"]["seed"]`` (populated by
            :func:`marslab.terrain.cave.orchestrator.generate_cave_mesh`)
            so the USD builder stays deterministic with the upstream
            mesh generator.  A hardcoded fallback would silently
            override user-supplied seeds.

    Returns:
        surface_elevation: 2D float32 array for spawn z calculations.
    """
    from pxr import UsdGeom

    # Ensure parent Xform exists
    UsdGeom.Xform.Define(stage, prim_base_path)

    # Surface terrain
    _trimesh_to_usd_prim(
        stage,
        cave_data["surface_mesh"],
        f"{prim_base_path}/Surface",
        semantic_label="soil",
        double_sided=False,
    )

    # Tube shell (ceiling + walls)
    _trimesh_to_usd_prim(
        stage,
        cave_data["tube_mesh"],
        f"{prim_base_path}/Tube",
        semantic_label="cave_wall",
        double_sided=True,
    )

    # Tube floor
    _trimesh_to_usd_prim(
        stage,
        cave_data["floor_mesh"],
        f"{prim_base_path}/Floor",
        semantic_label="cave_floor",
        double_sided=True,
    )

    # Skylight shafts
    for i, shaft in enumerate(cave_data["skylight_meshes"]):
        _trimesh_to_usd_prim(
            stage,
            shaft,
            f"{prim_base_path}/Skylight_{i}",
            semantic_label="cave_wall",
            double_sided=True,
        )

    # Debris cones
    for i, cone in enumerate(cave_data["debris_cones"]):
        _trimesh_to_usd_prim(
            stage,
            cone,
            f"{prim_base_path}/DebrisCone_{i}",
            semantic_label="breakdown",
            double_sided=False,
        )

    # Breakdown blocks as PointInstancer
    breakdown_positions = cave_data["breakdown_positions"]
    if breakdown_positions:
        # Resolve the effective seed: explicit argument > metadata > 0.
        effective_seed: int
        if seed is not None:
            effective_seed = int(seed)
        else:
            metadata = cave_data.get("metadata", {}) or {}
            md_seed = metadata.get("seed")
            effective_seed = int(md_seed) if md_seed is not None else 0
        _build_breakdown_instancer(
            stage,
            breakdown_positions,
            prim_base_path,
            seed=effective_seed,
        )

    return cave_data["surface_elevation"]


def _build_breakdown_instancer(
    stage,
    blocks: list[dict],
    prim_base_path: str,
    seed: int = 0,
) -> None:
    """Create a PointInstancer for breakdown blocks.

    Uses icosphere prototypes with random deformation, following
    the pattern from rock_instancer.py.

    Args:
        stage: USD stage.
        blocks: List of {x, y, z, diameter} dicts.
        prim_base_path: Base prim path.
        seed: RNG seed for block orientation / scale draws. The caller
            (:func:`build_cave_scene`) is responsible for threading
            the scenario seed through. A local hardcoded default would
            let user-supplied seeds drift silently.
    """
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics, UsdShade

    instancer_path = f"{prim_base_path}/Breakdown"
    instancer = UsdGeom.PointInstancer.Define(stage, instancer_path)

    # Create a single icosphere prototype
    UsdGeom.Scope.Define(stage, f"{instancer_path}/Prototypes")
    proto_path = f"{instancer_path}/Prototypes/block_0"

    # Simple icosphere-like mesh
    ico = trimesh.creation.icosphere(subdivisions=1, radius=0.5)
    _trimesh_to_usd_prim(
        stage,
        ico,
        proto_path,
        semantic_label="breakdown",
        double_sided=False,
    )

    # Apply dark material to prototype
    mtl_path = f"{prim_base_path}/Materials/BreakdownMtl"
    mtl = UsdShade.Material.Define(stage, mtl_path)
    shader = UsdShade.Shader.Define(stage, f"{mtl_path}/Shader")
    shader.CreateIdAttr("OmniPBR")
    # Dark basalt color
    shader.CreateInput("diffuse_color_constant", Sdf.ValueTypeNames.Color3f).Set(
        Gf.Vec3f(0.12, 0.08, 0.06)
    )
    shader.CreateInput("reflection_roughness_constant", Sdf.ValueTypeNames.Float).Set(0.88)
    shader.CreateInput("metallic_constant", Sdf.ValueTypeNames.Float).Set(0.0)
    mtl.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    prim = stage.GetPrimAtPath(proto_path)
    UsdShade.MaterialBindingAPI.Apply(prim).Bind(mtl)

    # Set instance data -- RNG seeded from caller so each scenario seed
    # produces deterministic block orientations / scales.
    rng = np.random.default_rng(seed)
    positions = []
    orientations = []
    scales = []
    proto_indices = []

    for block in blocks:
        positions.append(Gf.Vec3f(block["x"], block["y"], block["z"]))

        # Random rotation
        yaw = float(rng.uniform(0, 360))
        pitch = float(rng.uniform(-20, 20))
        roll = float(rng.uniform(-20, 20))
        q = Gf.Rotation(Gf.Vec3d(0, 0, 1), yaw).GetQuat()
        q = q * Gf.Rotation(Gf.Vec3d(0, 1, 0), pitch).GetQuat()
        q = q * Gf.Rotation(Gf.Vec3d(1, 0, 0), roll).GetQuat()
        orientations.append(Gf.Quath(q))

        d = block["diameter"]
        scales.append(Gf.Vec3f(d, d, d * float(rng.uniform(0.5, 1.0))))
        proto_indices.append(0)

    instancer.GetProtoIndicesAttr().Set(proto_indices)
    instancer.GetPositionsAttr().Set(positions)
    instancer.GetOrientationsAttr().Set(orientations)
    instancer.GetScalesAttr().Set(scales)

    rel = instancer.GetPrototypesRel()
    rel.AddTarget(proto_path)

    # Collision for instancer
    UsdPhysics.CollisionAPI.Apply(instancer.GetPrim())
