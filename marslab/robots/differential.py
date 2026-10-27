"""Author the same passive rocker differential for every rover profile.

Joint names and USD scopes come from the selected rover. The sign of the
coupling follows the authored joint frames, including mirrored rocker axes.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

_LOG = logging.getLogger(__name__)
_DEFAULT_ROCKER_NAMES = ("LEFT_DIFFERENTIAL", "RIGHT_DIFFERENTIAL")
# PhysX requires limited revolutes; these are numerical bounds, not mechanical stops.
_UNBOUNDED_LIMIT_DEGREES = 1.0e10


@dataclass(frozen=True)
class _RockerPair:
    left: Any
    right: Any
    left_axis: str
    right_axis: str
    gearing: float


def _rocker_joints(
    stage: Any,
    chassis_path: str,
    joint_names: tuple[str, str],
    rigid_body_prim_name: str,
    joints_prim_name: str,
) -> _RockerPair:
    from pxr import Gf, Sdf, UsdPhysics

    if len(joint_names) != 2 or len(set(joint_names)) != 2:
        raise ValueError("Rocker differential requires two distinct joint names")
    joints = []
    axes = []
    parent_path = Sdf.Path(f"{chassis_path}/{rigid_body_prim_name}")
    parent = stage.GetPrimAtPath(parent_path)
    if not parent or not parent.HasAPI(UsdPhysics.ArticulationRootAPI):
        raise RuntimeError(f"Rocker differential requires the chassis articulation: {parent_path}")
    local_axes = {
        "X": Gf.Vec3d(1.0, 0.0, 0.0),
        "Y": Gf.Vec3d(0.0, 1.0, 0.0),
        "Z": Gf.Vec3d(0.0, 0.0, 1.0),
    }
    for name in joint_names:
        path = f"{chassis_path}/{joints_prim_name}/{name}"
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
        axis_name = joint.GetAxisAttr().Get()
        if axis_name not in local_axes:
            raise RuntimeError(f"Unsupported revolute axis {axis_name!r}: {path}")
        axis = Gf.Rotation(Gf.Quatd(joint.GetLocalRot0Attr().Get())).TransformDir(
            local_axes[axis_name]
        )
        if abs(axis[0]) > 1e-6 or abs(axis[2]) > 1e-6 or abs(abs(axis[1]) - 1.0) > 1e-6:
            raise RuntimeError(f"Rocker differential requires a lateral chassis +/-Y axis: {path}")
        axes.append(axis)
        joints.append(joint)
    if (
        joints[0].GetBody1Rel().GetForwardedTargets()
        == joints[1].GetBody1Rel().GetForwardedTargets()
    ):
        raise RuntimeError("Rocker differential must connect two distinct rocker bodies")
    # PhysX solves q_right + gearing*q_left = 0. Mirrored joint coordinates
    # require gearing=-1 to retain equal-and-opposite physical rocker rotation.
    gearing = 1.0 if Gf.Dot(axes[0], axes[1]) > 0.0 else -1.0
    return _RockerPair(
        left=joints[0],
        right=joints[1],
        left_axis=f"rot{joints[0].GetAxisAttr().Get()}",
        right_axis=f"rot{joints[1].GetAxisAttr().Get()}",
        gearing=gearing,
    )


def validate_rocker_differential(
    stage: Any,
    chassis_path: str,
    *,
    joint_names: tuple[str, str] = _DEFAULT_ROCKER_NAMES,
    rigid_body_prim_name: str = "Body_Chassis",
    joints_prim_name: str = "joints",
) -> None:
    """Require equal-and-opposite physical rocker rotation before physics starts."""
    from pxr import PhysxSchema, UsdPhysics

    pair = _rocker_joints(stage, chassis_path, joint_names, rigid_body_prim_name, joints_prim_name)
    for joint in (pair.left, pair.right):
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

    left_mimics = _mimic_schemas(pair.left)
    right_mimics = _mimic_schemas(pair.right)
    if left_mimics or right_mimics != [f"PhysxMimicJointAPI:{pair.right_axis}"]:
        raise RuntimeError(
            "Rocker differential requires exactly one right-to-left mimic constraint"
        )
    mimic = PhysxSchema.PhysxMimicJointAPI(pair.right.GetPrim(), pair.right_axis)
    if (
        mimic.GetReferenceJointRel().GetForwardedTargets() != [pair.left.GetPath()]
        or mimic.GetReferenceJointAxisAttr().Get() != pair.left_axis
        or mimic.GetGearingAttr().Get() != pair.gearing
        or mimic.GetOffsetAttr().Get() != 0.0
    ):
        raise RuntimeError(
            f"Rocker differential must enforce {joint_names[1]} + "
            f"{pair.gearing:g} * {joint_names[0]} = 0"
        )
    _LOG.info(
        "marslab.physics.rocker_differential_verified left=%s right=%s "
        "gearing=%s offset=0 stiffness=0",
        pair.left.GetPath(),
        pair.right.GetPath(),
        pair.gearing,
    )


def _mimic_schemas(joint: Any) -> list[str]:
    return [
        schema
        for schema in joint.GetPrim().GetAppliedSchemas()
        if schema.startswith("PhysxMimicJointAPI:")
    ]


def configure_rocker_differential(
    stage: Any,
    chassis_path: str,
    *,
    joint_names: tuple[str, str] = _DEFAULT_ROCKER_NAMES,
    rigid_body_prim_name: str = "Body_Chassis",
    joints_prim_name: str = "joints",
    persist: bool = False,
) -> None:
    """Author in the runtime session, or the current edit target during an asset rebuild."""
    from pxr import PhysxSchema, Usd, UsdPhysics

    pair = _rocker_joints(stage, chassis_path, joint_names, rigid_body_prim_name, joints_prim_name)
    for joint in (pair.left, pair.right):
        existing = _mimic_schemas(joint)
        permitted = [f"PhysxMimicJointAPI:{pair.right_axis}"] if joint == pair.right else []
        if existing and existing != permitted:
            raise RuntimeError(
                f"Unexpected existing rocker coupling at {joint.GetPath()}: {existing}"
            )

    edit_target = stage.GetEditTarget() if persist else Usd.EditTarget(stage.GetSessionLayer())
    if not edit_target.GetLayer().permissionToEdit:
        raise RuntimeError("Cannot author rocker differential into a read-only layer")
    with Usd.EditContext(stage, edit_target):
        for joint in (pair.left, pair.right):
            for attribute, bound in (
                (joint.GetLowerLimitAttr(), -_UNBOUNDED_LIMIT_DEGREES),
                (joint.GetUpperLimitAttr(), _UNBOUNDED_LIMIT_DEGREES),
            ):
                if math.isinf(float(attribute.Get())):
                    attribute.Set(bound)
            drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), "angular")
            drive.CreateStiffnessAttr(0.0)
            drive.CreateTargetVelocityAttr(0.0)

        mimic = PhysxSchema.PhysxMimicJointAPI.Apply(pair.right.GetPrim(), pair.right_axis)
        mimic.CreateReferenceJointRel().SetTargets([pair.left.GetPath()])
        mimic.CreateReferenceJointAxisAttr(pair.left_axis)
        mimic.CreateGearingAttr(pair.gearing)
        mimic.CreateOffsetAttr(0.0)
    validate_rocker_differential(
        stage,
        chassis_path,
        joint_names=joint_names,
        rigid_body_prim_name=rigid_body_prim_name,
        joints_prim_name=joints_prim_name,
    )


__all__ = ["configure_rocker_differential", "validate_rocker_differential"]
