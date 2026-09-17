"""Keep hidden rock-library prototypes from becoming standalone PhysX colliders."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from importlib import import_module
from typing import Any

_LOG = logging.getLogger(__name__)


@dataclass
class _InstancerPlan:
    instancer: Any
    targets: list[Any]
    clones: dict[Any, Any]
    transforms: Any


def _unused_child_path(stage: Any, parent_path: Any, name: str, reserved: set[Any]) -> Any:
    candidate = parent_path.AppendChild(name)
    suffix = 1
    while stage.GetPrimAtPath(candidate) or candidate in reserved:
        candidate = parent_path.AppendChild(f"{name}_{suffix}")
        suffix += 1
    reserved.add(candidate)
    return candidate


def _instance_transforms(instancer: Any) -> Any:
    Usd = import_module("pxr.Usd")
    UsdGeom = import_module("pxr.UsdGeom")

    time = Usd.TimeCode.Default()
    indices = instancer.GetProtoIndicesAttr().Get(time)
    positions = instancer.GetPositionsAttr().Get(time)
    if indices is None or positions is None:
        raise RuntimeError(
            f"Cannot normalize {instancer.GetPath()}: default instance arrays are required"
        )
    transforms = instancer.ComputeInstanceTransformsAtTime(
        time, time, UsdGeom.PointInstancer.IncludeProtoXform, UsdGeom.PointInstancer.IgnoreMask
    )
    if len(transforms) != len(indices):
        raise RuntimeError(f"Cannot evaluate all instance transforms at {instancer.GetPath()}")
    return transforms


def normalize_external_prototypes(stage: Any, scene_root_path: str) -> None:
    """Move hidden external prototypes into their instancers using session-layer references."""
    Usd = import_module("pxr.Usd")
    UsdGeom = import_module("pxr.UsdGeom")
    UsdShade = import_module("pxr.UsdShade")

    root = stage.GetPrimAtPath(scene_root_path)
    if not root or not root.IsActive():
        raise RuntimeError(f"Referenced scene root is missing or inactive: {scene_root_path}")
    instancers = [
        UsdGeom.PointInstancer(prim)
        for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies())
        if prim.IsA(UsdGeom.PointInstancer)
    ]
    plans = []
    originals = set()
    reserved = set()
    for instancer in instancers:
        targets = instancer.GetPrototypesRel().GetTargets()
        hidden_external = []
        for target in targets:
            prototype = stage.GetPrimAtPath(target)
            if not target.IsPrimPath() or not prototype or not prototype.IsActive():
                raise RuntimeError(
                    f"{instancer.GetPath()} has an invalid prototype target: {target}"
                )
            if target.HasPrefix(instancer.GetPath()):
                continue
            imageable = UsdGeom.Imageable(prototype)
            if not imageable or imageable.ComputeVisibility() != UsdGeom.Tokens.invisible:
                continue
            if not target.HasPrefix(root.GetPath()) or any(
                other.GetPath().HasPrefix(target) for other in instancers
            ):
                raise RuntimeError(
                    f"Cannot deactivate hidden prototype {target}: it is outside {scene_root_path} "
                    "or contains a PointInstancer"
                )
            if prototype.IsInstanceProxy():
                raise RuntimeError(f"Cannot deactivate instance-proxy prototype {target}")
            hidden_external.append(target)
        if not hidden_external:
            continue
        prim = instancer.GetPrim()
        if prim.IsInstanceProxy() or prim.IsInstance():
            raise RuntimeError(f"Cannot create runtime prototypes under instance {prim.GetPath()}")
        container = _unused_child_path(stage, prim.GetPath(), "Prototypes", reserved)
        clones = {}
        for target in hidden_external:
            if target not in clones:
                clones[target] = _unused_child_path(stage, container, target.name, reserved)
        plans.append(_InstancerPlan(instancer, targets, clones, _instance_transforms(instancer)))
        originals.update(clones)
    if not plans:
        return

    # An input-owned prototype may also be referenced by an unrelated instancer.
    for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if prim.IsA(UsdGeom.PointInstancer) and not prim.GetPath().HasPrefix(root.GetPath()):
            shared = originals.intersection(
                UsdGeom.PointInstancer(prim).GetPrototypesRel().GetTargets()
            )
            if shared:
                raise RuntimeError(
                    f"Cannot deactivate prototypes {sorted(map(str, shared))}: "
                    f"they are also used by PointInstancer {prim.GetPath()} "
                    f"outside {scene_root_path}"
                )

    relationships = {}
    materials = {}
    for original in originals:
        prototype = stage.GetPrimAtPath(original)
        for prim in Usd.PrimRange(prototype, Usd.TraverseInstanceProxies()):
            for relationship in prim.GetRelationships():
                targets = relationship.GetTargets()
                if targets:
                    relationships[relationship.GetPath()] = targets
            if UsdGeom.Imageable(prim):
                binding = UsdShade.MaterialBindingAPI(prim)
                for purpose in (UsdShade.Tokens.allPurpose, "physics"):
                    material, _ = binding.ComputeBoundMaterial(materialPurpose=purpose)
                    if material:
                        materials[(prim.GetPath(), purpose)] = material.GetPath()

    session_layer = stage.GetSessionLayer()
    if not session_layer.permissionToEdit:
        raise RuntimeError("Cannot normalize point prototypes: runtime session layer is read-only")
    with Usd.EditContext(stage, session_layer):
        for plan in plans:
            for original, destination in plan.clones.items():
                UsdGeom.Scope.Define(stage, destination.GetParentPath())
                clone = stage.DefinePrim(destination)
                if not clone.GetReferences().AddInternalReference(original) or not clone.SetActive(
                    True
                ):
                    raise RuntimeError(f"Cannot reference prototype {original} at {destination}")
            targets = [plan.clones.get(target, target) for target in plan.targets]
            if (
                not plan.instancer.GetPrototypesRel().SetTargets(targets)
                or plan.instancer.GetPrototypesRel().GetTargets() != targets
            ):
                raise RuntimeError(f"Cannot retarget prototypes for {plan.instancer.GetPath()}")

        # Shared prototypes remain active until every instancer has its own reference.
        for original in sorted(originals, key=lambda path: path.pathElementCount, reverse=True):
            prototype = stage.GetPrimAtPath(original)
            if not prototype.SetActive(False) or prototype.IsActive():
                raise RuntimeError(f"Cannot deactivate external prototype {original}")

    for plan in plans:
        if _instance_transforms(plan.instancer) != plan.transforms:
            raise RuntimeError(
                f"Prototype relocation changed instance transforms at {plan.instancer.GetPath()}"
            )
        for original, destination in plan.clones.items():
            clone = stage.GetPrimAtPath(destination)
            if not clone or not clone.IsActive():
                raise RuntimeError(f"Relocated prototype is missing or inactive: {destination}")
            for path, targets in relationships.items():
                if path.HasPrefix(original):
                    relocated_path = path.ReplacePrefix(original, destination)
                    expected = [target.ReplacePrefix(original, destination) for target in targets]
                    if stage.GetRelationshipAtPath(relocated_path).GetTargets() != expected:
                        raise RuntimeError(
                            f"Prototype relocation changed relationship {path} at {relocated_path}"
                        )
            for (path, purpose), material_path in materials.items():
                if path.HasPrefix(original):
                    relocated_path = path.ReplacePrefix(original, destination)
                    material, _ = UsdShade.MaterialBindingAPI(
                        stage.GetPrimAtPath(relocated_path)
                    ).ComputeBoundMaterial(materialPurpose=purpose)
                    expected = material_path.ReplacePrefix(original, destination)
                    if not material or material.GetPath() != expected:
                        raise RuntimeError(
                            f"Prototype relocation changed {purpose or 'visual'} material "
                            f"binding at {relocated_path}; expected {expected}"
                        )
        _LOG.info(
            "Normalized %d hidden external prototypes for %s; preserved %d instance transforms",
            len(plan.clones),
            plan.instancer.GetPath(),
            len(plan.transforms),
        )


__all__ = ["normalize_external_prototypes"]
