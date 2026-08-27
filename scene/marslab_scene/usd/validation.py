"""Standalone USD asset-bundle semantic validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pxr import Sdf, Usd, UsdGeom, UsdShade, UsdUtils

from marslab_scene.errors import ContractValueError
from marslab_scene.usd._manifest import SceneArtifactManifest, validate_scene_manifest
from marslab_scene.usd._scene_validation import (
    SceneSemanticReport,
    SceneValidationContract,
    validate_scene_stage,
)

__all__ = [
    "SceneArtifactManifest",
    "SceneSemanticReport",
    "SceneValidationContract",
    "validate_scene_manifest",
    "validate_scene_stage",
]


@dataclass(frozen=True, slots=True)
class AssetPrimContract:
    geometry_prim: str
    material_prim: str
    collision_prim: str
    label: str


@dataclass(frozen=True, slots=True)
class AssetStageContract:
    default_prim: str
    prims: tuple[AssetPrimContract, ...]
    textures: tuple[Path, ...]
    layers: tuple[Path, ...]


def validate_asset_stage(
    stage_path: Path,
    contract: AssetStageContract,
) -> None:
    """Open a stage with usd-core and validate composition, paths, and prim contracts."""
    _validate_authored_layer_references(stage_path.parent.resolve(), contract.layers)
    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        detail = f"USD stage cannot be opened: {stage_path.name}"
        raise ContractValueError(detail)
    _validate_stage_identity(stage, contract.default_prim)

    root = stage_path.parent.resolve()
    _validate_dependencies(stage, root)
    dependency_textures = _resolved_asset_dependencies(stage_path)
    if dependency_textures != {path.resolve() for path in contract.textures}:
        raise ContractValueError("texture dependency inventory does not match manifest")

    for prim_contract in contract.prims:
        _validate_prim_contract(stage, prim_contract)


def _validate_stage_identity(stage: Usd.Stage, default_prim: str) -> None:
    if stage.GetDefaultPrim().GetPath().pathString != default_prim:
        detail = f"default_prim does not match USD stage: {default_prim}"
        raise ContractValueError(detail)
    if UsdGeom.GetStageUpAxis(stage) != "Z":
        raise ContractValueError("up_axis does not match USD stage")
    if UsdGeom.GetStageMetersPerUnit(stage) != 1.0:
        raise ContractValueError("meters_per_unit does not match USD stage")


def _validate_authored_layer_references(root: Path, layer_paths: tuple[Path, ...]) -> None:
    for layer_path in layer_paths:
        layer = Sdf.Layer.FindOrOpen(str(layer_path))
        if not layer:
            detail = f"USD layer cannot be opened: {layer_path.name}"
            raise ContractValueError(detail)
        for token in layer.GetExternalReferences():
            _validate_asset_token(root, layer_path.parent, token)


def _validate_prim_contract(stage: Usd.Stage, contract: AssetPrimContract) -> None:
    geometry = stage.GetPrimAtPath(contract.geometry_prim)
    material = stage.GetPrimAtPath(contract.material_prim)
    collision = stage.GetPrimAtPath(contract.collision_prim)
    if not geometry or not geometry.IsA(UsdGeom.Mesh):
        detail = f"geometry_prim is missing or not a mesh: {contract.label}"
        raise ContractValueError(detail)
    if not material or not material.IsA(UsdShade.Material):
        detail = f"material_prim is missing or not a material: {contract.label}"
        raise ContractValueError(detail)
    if not collision or not collision.IsA(UsdGeom.Mesh):
        detail = f"collision_prim is missing or not a mesh: {contract.label}"
        raise ContractValueError(detail)
    bound_material, _ = UsdShade.MaterialBindingAPI(geometry).ComputeBoundMaterial()
    if not bound_material or bound_material.GetPrim().GetPath() != material.GetPath():
        detail = f"material binding does not match manifest: {contract.label}"
        raise ContractValueError(detail)
    collision_enabled = collision.GetAttribute("physics:collisionEnabled")
    collision_api_applied = "PhysicsCollisionAPI" in collision.GetAppliedSchemas()
    if not collision_api_applied or not collision_enabled.Get():
        detail = f"collision contract is not enabled: {contract.label}"
        raise ContractValueError(detail)


def geometry_bounds(
    stage_path: Path,
    prim_path: str,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return the aligned world-space bounds for a declared geometry prim."""
    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        detail = f"USD stage cannot be opened: {stage_path.name}"
        raise ContractValueError(detail)
    prim = stage.GetPrimAtPath(prim_path)
    if not prim:
        detail = f"geometry prim does not exist: {prim_path}"
        raise ContractValueError(detail)
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"])
    aligned = bounds.ComputeWorldBound(prim).ComputeAlignedBox()
    minimum = aligned.GetMin()
    maximum = aligned.GetMax()
    return (
        (float(minimum[0]), float(minimum[1]), float(minimum[2])),
        (float(maximum[0]), float(maximum[1]), float(maximum[2])),
    )


def validate_mesh_vertex_indices(
    stage_path: Path,
    prim_path: str,
    indices: tuple[int, ...],
) -> None:
    """Require declared stable-face indices to address geometry vertices."""
    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        detail = f"USD stage cannot be opened: {stage_path.name}"
        raise ContractValueError(detail)
    mesh = UsdGeom.Mesh(stage.GetPrimAtPath(prim_path))
    points = mesh.GetPointsAttr().Get()
    if not points or any(index >= len(points) for index in indices):
        detail = f"stable_face_vertex_indices are invalid: {prim_path}"
        raise ContractValueError(detail)


def validate_prototype_texture(
    stage_path: Path,
    prim_path: str,
    expected_texture: Path,
) -> None:
    """Require prototype texture metadata to match its composed asset dependency."""
    stage = Usd.Stage.Open(str(stage_path))
    if not stage:
        detail = f"USD stage cannot be opened: {stage_path.name}"
        raise ContractValueError(detail)
    prototype = stage.GetPrimAtPath(prim_path)
    if not prototype:
        detail = f"prim_path does not exist: {prim_path}"
        raise ContractValueError(detail)
    dependencies: set[Path] = set()
    prefix = f"{prim_path}/"
    for prim in stage.Traverse():
        path = prim.GetPath().pathString
        if path != prim_path and not path.startswith(prefix):
            continue
        for attribute in prim.GetAttributes():
            if attribute.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue
            asset_path = attribute.Get()
            if not asset_path or not asset_path.path:
                continue
            property_stack = attribute.GetPropertyStack()
            if not property_stack or not property_stack[0].layer.realPath:
                detail = f"texture asset has no owning layer: {attribute.GetPath().pathString}"
                raise ContractValueError(detail)
            owner = Path(property_stack[0].layer.realPath).resolve().parent
            dependencies.add((owner / asset_path.path).resolve())
    if dependencies != {expected_texture.resolve()}:
        raise ContractValueError("prototype texture metadata does not match USD dependency")


def _validate_dependencies(stage: Usd.Stage, root: Path) -> None:
    for layer in stage.GetUsedLayers():
        if not layer.realPath:
            continue
        layer_path = Path(layer.realPath).resolve()
        _require_contained(root, layer_path)
        for token in layer.GetExternalReferences():
            _validate_asset_token(root, layer_path.parent, token)
    for prim in stage.Traverse():
        for attribute in prim.GetAttributes():
            if attribute.GetTypeName() != Sdf.ValueTypeNames.Asset:
                continue
            asset_path = attribute.Get()
            if not asset_path or not asset_path.path:
                continue
            property_stack = attribute.GetPropertyStack()
            if not property_stack or not property_stack[0].layer.realPath:
                detail = f"asset path has no owning layer: {attribute.GetPath().pathString}"
                raise ContractValueError(detail)
            owner = Path(property_stack[0].layer.realPath).resolve().parent
            _validate_asset_token(root, owner, asset_path.path)
    _, _, unresolved = UsdUtils.ComputeAllDependencies(str(stage.GetRootLayer().realPath))
    if unresolved:
        detail = f"USD stage has unresolved dependencies: {sorted(unresolved)}"
        raise ContractValueError(detail)


def _resolved_asset_dependencies(stage_path: Path) -> set[Path]:
    _, assets, _ = UsdUtils.ComputeAllDependencies(str(stage_path))
    return {Path(asset).resolve() for asset in assets}


def _validate_asset_token(root: Path, owner: Path, token: str) -> None:
    raw = Path(token)
    if raw.is_absolute() or "://" in token or token.startswith("file:"):
        detail = f"expected a relative USD asset path: {token}"
        raise ContractValueError(detail)
    _require_contained(root, (owner / raw).resolve())


def _require_contained(root: Path, path: Path) -> None:
    try:
        _ = path.relative_to(root)
    except ValueError:
        detail = f"USD dependency escapes bundle root: {path.name}"
        raise ContractValueError(detail) from None
    if not path.is_file():
        detail = f"USD dependency does not exist: {path.name}"
        raise ContractValueError(detail)
