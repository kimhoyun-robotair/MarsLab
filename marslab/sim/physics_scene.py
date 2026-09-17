"""Keep referenced assets under the World-owned PhysicsScene at runtime."""

from __future__ import annotations

import logging
import math
from importlib import import_module
from typing import Any

_LOG = logging.getLogger(__name__)


def _owner_relationships(stage: Any) -> list[Any]:
    Usd = import_module("pxr.Usd")
    UsdPhysics = import_module("pxr.UsdPhysics")

    relationships = {}
    for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            owner = UsdPhysics.RigidBodyAPI(prim).GetSimulationOwnerRel()
        elif prim.HasAPI(UsdPhysics.CollisionAPI):
            parent = prim.GetParent()
            while parent and not parent.HasAPI(UsdPhysics.RigidBodyAPI):
                parent = parent.GetParent()
            # A collider follows its rigid body even inside an instance proxy.
            owner = (
                UsdPhysics.RigidBodyAPI(parent).GetSimulationOwnerRel()
                if parent
                else UsdPhysics.CollisionAPI(prim).GetSimulationOwnerRel()
            )
        else:
            continue
        if owner and owner.GetTargets():
            relationships[owner.GetPath()] = owner
    return list(relationships.values())


def _single_owner_target(relationship: Any) -> Any:
    targets = relationship.GetForwardedTargets()
    if len(targets) != 1 or not targets[0].IsPrimPath():
        raise RuntimeError(
            f"{relationship.GetPath()} must resolve to one PhysicsScene prim; "
            f"authored targets={relationship.GetTargets()}, resolved targets={targets}"
        )
    return targets[0]


def validate_world_physics(
    stage: Any,
    world_scene_path: str,
    gravity: float,
) -> None:
    """Reject ambiguous scene ownership and inconsistent configured gravity."""
    Sdf = import_module("pxr.Sdf")
    Usd = import_module("pxr.Usd")
    UsdPhysics = import_module("pxr.UsdPhysics")

    expected_path = Sdf.Path(world_scene_path)
    scene_paths = [
        prim.GetPath()
        for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies())
        if prim.IsA(UsdPhysics.Scene)
    ]
    if scene_paths != [expected_path]:
        raise RuntimeError(
            f"World must own the only active PhysicsScene at {expected_path}; "
            f"found {[str(path) for path in scene_paths]}"
        )

    scene = UsdPhysics.Scene(stage.GetPrimAtPath(expected_path))
    direction = scene.GetGravityDirectionAttr().Get()
    magnitude = scene.GetGravityMagnitudeAttr().Get()
    if (
        direction is None
        or any(
            not math.isclose(float(actual), expected, abs_tol=1e-6)
            for actual, expected in zip(direction, (0.0, 0.0, -1.0), strict=True)
        )
        or magnitude is None
        or not math.isclose(float(magnitude), abs(float(gravity)), rel_tol=1e-6, abs_tol=1e-6)
    ):
        raise RuntimeError(
            f"World PhysicsScene {expected_path} gravity mismatch: "
            f"direction={direction}, magnitude={magnitude}; "
            f"expected direction=(0, 0, -1), magnitude={abs(float(gravity))}"
        )

    relationships = _owner_relationships(stage)
    for relationship in relationships:
        target = _single_owner_target(relationship)
        if target != expected_path:
            raise RuntimeError(
                f"{relationship.GetPath()} resolves to {target}; "
                f"the only supported simulation owner is {expected_path}"
            )
    _LOG.info(
        "Verified World PhysicsScene=%s gravity_direction=%s gravity_magnitude=%.6f "
        "explicit_simulation_owners=%d",
        expected_path,
        direction,
        float(magnitude),
        len(relationships),
    )


def normalize_reference_physics(
    stage: Any,
    reference_root_path: str,
    world_scene_path: str,
    gravity: float,
) -> None:
    """Disable input-owned scenes and redirect their effective body/collider owners."""
    Sdf = import_module("pxr.Sdf")
    Usd = import_module("pxr.Usd")
    UsdPhysics = import_module("pxr.UsdPhysics")

    expected_path = Sdf.Path(world_scene_path)
    root = stage.GetPrimAtPath(reference_root_path)
    if not root or not root.IsActive():
        raise RuntimeError(f"Referenced scene root is missing or inactive: {reference_root_path}")
    world_scene = stage.GetPrimAtPath(expected_path)
    if not world_scene or not world_scene.IsActive() or not world_scene.IsA(UsdPhysics.Scene):
        raise RuntimeError(f"World PhysicsScene is missing or inactive: {expected_path}")
    if expected_path.HasPrefix(root.GetPath()):
        raise RuntimeError(
            f"World PhysicsScene {expected_path} cannot be owned by the referenced input"
        )

    scene_prims = [
        prim
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies())
        if prim.IsA(UsdPhysics.Scene)
    ]
    scene_paths = {prim.GetPath() for prim in scene_prims}
    for prim in scene_prims:
        if prim == root or prim.IsInstanceProxy():
            raise RuntimeError(
                f"Cannot deactivate input PhysicsScene {prim.GetPath()} without changing "
                "its referenced root or instance; provide an independently editable scene prim"
            )

    replacements = []
    for relationship in _owner_relationships(stage):
        if _single_owner_target(relationship) in scene_paths:
            if relationship.GetPrim().IsInstanceProxy():
                raise RuntimeError(
                    f"Cannot redirect instance-proxy simulation owner {relationship.GetPath()} "
                    f"to {expected_path}; author the owner on its editable rigid body "
                    "or input asset"
                )
            replacements.append(relationship)

    session_layer = stage.GetSessionLayer()
    if not session_layer.permissionToEdit:
        raise RuntimeError(
            "Cannot normalize PhysicsScene ownership: runtime session layer is read-only"
        )
    with Usd.EditContext(stage, session_layer):
        for relationship in replacements:
            original_target = _single_owner_target(relationship)
            if (
                not relationship.SetTargets([expected_path])
                or _single_owner_target(relationship) != expected_path
            ):
                raise RuntimeError(
                    f"Failed to redirect {relationship.GetPath()} to {expected_path}"
                )
            _LOG.info(
                "Redirected %s from %s to %s",
                relationship.GetPath(),
                original_target,
                expected_path,
            )
        # Children must be deactivated before parents invalidate their prim handles.
        for path in sorted(scene_paths, key=lambda value: value.pathElementCount, reverse=True):
            prim = stage.GetPrimAtPath(path)
            if not prim.SetActive(False) or prim.IsActive():
                raise RuntimeError(f"Failed to deactivate input PhysicsScene {path}")
            _LOG.info("Deactivated input PhysicsScene at %s in the runtime session layer", path)

    validate_world_physics(stage, world_scene_path, gravity)


__all__ = ["normalize_reference_physics", "validate_world_physics"]
