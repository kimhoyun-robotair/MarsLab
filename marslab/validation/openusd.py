from __future__ import annotations

import importlib
from pathlib import Path

from marslab.validation.models import RoverFacts, SceneFacts, StageOpenError


def _dependencies(identifier: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    usd_utils = importlib.import_module("pxr.UsdUtils")
    layers, assets, unresolved = usd_utils.ComputeAllDependencies(identifier)
    return (
        tuple(sorted(layer.identifier for layer in layers)),
        tuple(sorted(str(asset) for asset in assets)),
        tuple(sorted(str(item) for item in unresolved)),
    )


def inspect_scene(path: Path) -> SceneFacts:
    usd = importlib.import_module("pxr.Usd")
    usd_geom = importlib.import_module("pxr.UsdGeom")
    usd_physics = importlib.import_module("pxr.UsdPhysics")
    stage = usd.Stage.Open(str(path))
    if stage is None:
        raise StageOpenError(path)
    default = stage.GetDefaultPrim()
    meshes: list[str] = []
    collisions: list[str] = []
    physics_scenes: list[str] = []
    prim_count = 0
    for prim in stage.Traverse():
        prim_count += 1
        prim_path = str(prim.GetPath())
        if prim.IsA(usd_geom.Mesh):
            meshes.append(prim_path)
        if (
            prim.HasAPI(usd_physics.CollisionAPI)
            or prim.GetAttribute("physics:collisionEnabled").IsValid()
        ):
            collisions.append(prim_path)
        if prim.IsA(usd_physics.Scene):
            physics_scenes.append(prim_path)
    layers, assets, unresolved = _dependencies(stage.GetRootLayer().identifier)
    return SceneFacts(
        default_prim=str(default.GetPath()) if default else None,
        up_axis=str(usd_geom.GetStageUpAxis(stage)),
        meters_per_unit=float(usd_geom.GetStageMetersPerUnit(stage)),
        prim_count=prim_count,
        mesh_paths=tuple(sorted(meshes)),
        collision_paths=tuple(sorted(collisions)),
        physics_scene_paths=tuple(sorted(physics_scenes)),
        layer_ids=layers,
        asset_ids=assets,
        unresolved_ids=unresolved,
    )


def inspect_rover(path: Path) -> RoverFacts:
    usd = importlib.import_module("pxr.Usd")
    usd_geom = importlib.import_module("pxr.UsdGeom")
    usd_physics = importlib.import_module("pxr.UsdPhysics")
    stage = usd.Stage.Open(str(path))
    if stage is None:
        raise StageOpenError(path)
    default = stage.GetDefaultPrim()
    names: set[str] = set()
    articulations: list[str] = []
    for prim in stage.Traverse():
        names.add(prim.GetName())
        if prim.HasAPI(usd_physics.ArticulationRootAPI):
            articulations.append(str(prim.GetPath()))
    layers, assets, unresolved = _dependencies(stage.GetRootLayer().identifier)
    return RoverFacts(
        default_prim=str(default.GetPath()) if default else None,
        up_axis=str(usd_geom.GetStageUpAxis(stage)),
        meters_per_unit=float(usd_geom.GetStageMetersPerUnit(stage)),
        prim_names=frozenset(names),
        articulation_paths=tuple(sorted(articulations)),
        layer_ids=layers,
        asset_ids=assets,
        unresolved_ids=unresolved,
    )


__all__ = ["inspect_rover", "inspect_scene"]
