"""Reusable HiRISE terrain sub-stage authoring."""

from __future__ import annotations

import posixpath
from pathlib import Path

import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdShade, Vt

from marslab_scene.terrain.hirise.config import PipelineConfig, TextureConfig
from marslab_scene.terrain.hirise.mesh.heightfield import MeshData
from marslab_scene.terrain.hirise.texture.prepare import PreparedTexture
from marslab_scene.terrain.hirise.texture.uv import build_face_varying_uvs


class TerrainStageError(RuntimeError):
    """Raised when the reusable terrain sub-stage cannot be authored."""


def _write_mesh(
    stage: Usd.Stage,
    prim_path: str,
    mesh: MeshData,
    *,
    visible: bool,
) -> UsdGeom.Mesh:
    usd_mesh = UsdGeom.Mesh.Define(stage, prim_path)
    points = [tuple(float(value) for value in vertex) for vertex in mesh.vertices]
    indices = [int(index) for face in mesh.faces for index in face]
    usd_mesh.CreatePointsAttr(Vt.Vec3fArray(points))
    usd_mesh.CreateFaceVertexIndicesAttr(indices)
    usd_mesh.CreateFaceVertexCountsAttr([3] * len(mesh.faces))
    usd_mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    usd_mesh.CreateDoubleSidedAttr(defaultValue=False)
    usd_mesh.CreateVisibilityAttr(UsdGeom.Tokens.inherited if visible else UsdGeom.Tokens.invisible)
    return usd_mesh


def _write_uvs(usd_mesh: UsdGeom.Mesh, mesh: MeshData) -> None:
    values = [
        tuple(float(value) for value in uv) for uv in np.asarray(build_face_varying_uvs(mesh))
    ]
    primvar = UsdGeom.PrimvarsAPI(usd_mesh.GetPrim()).CreatePrimvar(
        "st",
        Sdf.ValueTypeNames.TexCoord2fArray,
        UsdGeom.Tokens.faceVarying,
    )
    primvar.Set(Vt.Vec2fArray(values))


def _bind_texture(
    stage: Usd.Stage,
    visual_prim: Usd.Prim,
    texture: PreparedTexture,
    config: TextureConfig,
    scene_path: Path,
) -> None:
    if not texture.enabled or texture.output_path is None:
        return
    material_path = f"/World/Looks/{config.material.name}"
    material = UsdShade.Material.Define(stage, material_path)
    preview = UsdShade.Shader.Define(stage, f"{material_path}/PreviewSurface")
    preview.CreateIdAttr("UsdPreviewSurface")
    preview.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(config.material.roughness)
    preview.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(config.material.metallic)
    preview.CreateInput("opacity", Sdf.ValueTypeNames.Float).Set(config.material.opacity)
    reader = UsdShade.Shader.Define(stage, f"{material_path}/STReader")
    reader.CreateIdAttr("UsdPrimvarReader_float2")
    reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
    reader_output = reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)
    albedo = UsdShade.Shader.Define(stage, f"{material_path}/AlbedoTexture")
    albedo.CreateIdAttr("UsdUVTexture")
    relative = texture.output_path.relative_to(scene_path.parent)
    albedo.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(
        Sdf.AssetPath(posixpath.join(*relative.parts))
    )
    albedo.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set(config.color_space)
    albedo.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(reader_output)
    rgb_output = albedo.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
    preview.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(rgb_output)
    material.CreateSurfaceOutput().ConnectToSource(preview.ConnectableAPI(), "surface")
    UsdShade.MaterialBindingAPI.Apply(visual_prim).Bind(material)


def _apply_physics(stage: Usd.Stage, collision_prim: Usd.Prim, config: PipelineConfig) -> None:
    physics_scene = UsdPhysics.Scene.Define(stage, f"{config.usd.root_prim}/PhysicsScene")
    physics_scene.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
    physics_scene.CreateGravityMagnitudeAttr(config.physics.gravity_mps2)
    UsdPhysics.CollisionAPI.Apply(collision_prim).CreateCollisionEnabledAttr(defaultValue=True)
    UsdPhysics.MeshCollisionAPI.Apply(collision_prim).CreateApproximationAttr(
        config.physics.collision_approximation
    )
    material = UsdShade.Material.Define(stage, f"{config.usd.terrain_prim}/PhysicsMaterial")
    material_api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    material_api.CreateStaticFrictionAttr(config.physics.static_friction)
    material_api.CreateDynamicFrictionAttr(config.physics.dynamic_friction)
    material_api.CreateRestitutionAttr(config.physics.restitution)
    UsdShade.MaterialBindingAPI.Apply(collision_prim).Bind(material)


def write_terrain_stage(
    visual: MeshData,
    collision: MeshData,
    config: PipelineConfig,
    texture: PreparedTexture | None = None,
) -> Path:
    """Author the one reusable terrain stage allowed outside SceneBuilder."""
    scene_path = config.usd.output_dir / config.usd.terrain_scene_name
    scene_path.parent.mkdir(parents=True, exist_ok=True)
    stage = Usd.Stage.CreateNew(str(scene_path))
    if stage is None:
        message = f"could not create terrain stage: {scene_path}"
        raise TerrainStageError(message)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, config.usd.meters_per_unit)
    world = UsdGeom.Xform.Define(stage, config.usd.root_prim)
    stage.SetDefaultPrim(world.GetPrim())
    UsdGeom.Xform.Define(stage, config.usd.terrain_prim)
    visual_mesh = _write_mesh(stage, config.usd.visual_prim, visual, visible=True)
    _write_uvs(visual_mesh, visual)
    collision_mesh = _write_mesh(stage, config.usd.collision_prim, collision, visible=False)
    _apply_physics(stage, collision_mesh.GetPrim(), config)
    if texture is not None:
        _bind_texture(stage, visual_mesh.GetPrim(), texture, config.texture, scene_path)
    stage.GetRootLayer().Save()
    return scene_path
