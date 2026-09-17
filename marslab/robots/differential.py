"""Author and validate the passive rocker differential in USD physics."""

from __future__ import annotations

import logging
import math
from typing import Any

_LOG = logging.getLogger(__name__)
_ROCKER_NAMES = ("LEFT_DIFFERENTIAL", "RIGHT_DIFFERENTIAL")
# PhysX requires limited revolutes; these are numerical bounds, not mechanical stops.
_UNBOUNDED_LIMIT_DEGREES = 1.0e10


def _rocker_joints(stage: Any, chassis_path: str) -> tuple[Any, Any]:
    from pxr import Gf, Sdf, UsdPhysics

    joints = []
    parent_path = Sdf.Path(f"{chassis_path}/Body_Chassis")
    parent = stage.GetPrimAtPath(parent_path)
    if not parent or not parent.HasAPI(UsdPhysics.ArticulationRootAPI):
        raise RuntimeError(f"Rocker differential requires the chassis articulation: {parent_path}")
    for name in _ROCKER_NAMES:
        path = f"{chassis_path}/joints/{name}"
        joint = UsdPhysics.RevoluteJoint(stage.GetPrimAtPath(path))
        if not joint or not joint.GetPrim().IsActive():
            raise RuntimeError(f"Rocker differential requires an active revolute joint: {path}")
        if (
            not joint.GetJointEnabledAttr().Get()
            or joint.GetExcludeFromArticulationAttr().Get()
            or joint.GetBody0Rel().GetForwardedTargets() != [parent_path]
        ):
            raise RuntimeError(f"Rocker joint must belong to the chassis articulation: {path}")
        child_paths = joint.GetBody1Rel().GetForwardedTargets()
        if len(child_paths) != 1:
            raise RuntimeError(f"Rocker joint must connect one child rigid body: {path}")
        child = stage.GetPrimAtPath(child_paths[0])
        if not child or not child.HasAPI(UsdPhysics.RigidBodyAPI):
            raise RuntimeError(f"Rocker child rigid body is missing: {path}")
        axis = Gf.Rotation(Gf.Quatd(joint.GetLocalRot0Attr().Get())).TransformDir(
            Gf.Vec3d(0.0, 1.0, 0.0)
        )
        if joint.GetAxisAttr().Get() != "Y" or (axis - Gf.Vec3d(0.0, -1.0, 0.0)).GetLength() > 1e-6:
            raise RuntimeError(
                f"Rocker differential expects both joint axes along chassis -Y: {path}"
            )
        joints.append(joint)
    if (
        joints[0].GetBody1Rel().GetForwardedTargets()
        == joints[1].GetBody1Rel().GetForwardedTargets()
    ):
        raise RuntimeError("Rocker differential must connect two distinct rocker bodies")
    return joints[0], joints[1]


def validate_rocker_differential(stage: Any, chassis_path: str) -> None:
    """Require an equal-and-opposite passive coupling before physics initializes."""
    from pxr import PhysxSchema, UsdPhysics

    left, right = _rocker_joints(stage, chassis_path)
    for joint in (left, right):
        low = float(joint.GetLowerLimitAttr().Get())
        high = float(joint.GetUpperLimitAttr().Get())
        if not (math.isfinite(low) and math.isfinite(high) and low < 0.0 < high):
            raise RuntimeError(
                f"Rocker mimic requires finite revolute limits around zero: {joint.GetPath()}"
            )
        drive = UsdPhysics.DriveAPI(joint.GetPrim(), "angular")
        if (
            not drive
            or drive.GetStiffnessAttr().Get() != 0.0
            or drive.GetTargetVelocityAttr().Get() != 0.0
        ):
            raise RuntimeError(f"Rocker joint must remain passive: {joint.GetPath()}")

    left_mimics = [
        schema
        for schema in left.GetPrim().GetAppliedSchemas()
        if schema.startswith("PhysxMimicJointAPI:")
    ]
    right_mimics = [
        schema
        for schema in right.GetPrim().GetAppliedSchemas()
        if schema.startswith("PhysxMimicJointAPI:")
    ]
    if left_mimics or right_mimics != ["PhysxMimicJointAPI:rotY"]:
        raise RuntimeError(
            "Rocker differential requires exactly one RIGHT-to-LEFT mimic constraint"
        )
    mimic = PhysxSchema.PhysxMimicJointAPI(right.GetPrim(), UsdPhysics.Tokens.rotY)
    if (
        mimic.GetReferenceJointRel().GetForwardedTargets() != [left.GetPath()]
        or mimic.GetReferenceJointAxisAttr().Get() != UsdPhysics.Tokens.rotY
        or mimic.GetGearingAttr().Get() != 1.0
        or mimic.GetOffsetAttr().Get() != 0.0
    ):
        raise RuntimeError(
            "Rocker differential must enforce LEFT_DIFFERENTIAL + RIGHT_DIFFERENTIAL = 0"
        )
    _LOG.info(
        "marslab.physics.rocker_differential_verified left=%s right=%s "
        "gearing=1 offset=0 stiffness=0",
        left.GetPath(),
        right.GetPath(),
    )


def configure_rocker_differential(stage: Any, chassis_path: str, *, persist: bool = False) -> None:
    """Author in the runtime session, or the current edit target during an asset rebuild."""
    from pxr import PhysxSchema, Usd, UsdPhysics

    left, right = _rocker_joints(stage, chassis_path)
    for joint in (left, right):
        existing = [
            schema
            for schema in joint.GetPrim().GetAppliedSchemas()
            if schema.startswith("PhysxMimicJointAPI:")
        ]
        permitted = ["PhysxMimicJointAPI:rotY"] if joint == right else []
        if existing and existing != permitted:
            raise RuntimeError(
                f"Unexpected existing rocker coupling at {joint.GetPath()}: {existing}"
            )

    edit_target = stage.GetEditTarget() if persist else Usd.EditTarget(stage.GetSessionLayer())
    if not edit_target.GetLayer().permissionToEdit:
        raise RuntimeError("Cannot author rocker differential into a read-only layer")
    with Usd.EditContext(stage, edit_target):
        for joint in (left, right):
            for attribute, bound in (
                (joint.GetLowerLimitAttr(), -_UNBOUNDED_LIMIT_DEGREES),
                (joint.GetUpperLimitAttr(), _UNBOUNDED_LIMIT_DEGREES),
            ):
                if math.isinf(float(attribute.Get())):
                    attribute.Set(bound)
            drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular")
            drive.CreateStiffnessAttr(0.0)
            drive.CreateTargetVelocityAttr(0.0)

        # PhysX solves q_right + gearing*q_left + offset = 0 with two-way impulses.
        mimic = PhysxSchema.PhysxMimicJointAPI.Apply(right.GetPrim(), UsdPhysics.Tokens.rotY)
        mimic.CreateReferenceJointRel().SetTargets([left.GetPath()])
        mimic.CreateReferenceJointAxisAttr(UsdPhysics.Tokens.rotY)
        mimic.CreateGearingAttr(1.0)
        mimic.CreateOffsetAttr(0.0)
    validate_rocker_differential(stage, chassis_path)


__all__ = ["configure_rocker_differential", "validate_rocker_differential"]
