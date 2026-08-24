"""Configure rover joint drives before and after physics reset.
DriveAPI writes precede reset while tensor gains follow reset.
Joint-index resolution remains pure for offline callers."""

from __future__ import annotations

import logging
from typing import Any, List

import numpy as np

from marslab.config.schema.rover import ControlConfig, SuspensionConfig

_LOG = logging.getLogger(__name__)


def resolve_joint_indices(dof_names: List[str], requested: List[str]) -> List[int]:
    """Resolve each requested joint name to its index in ``dof_names``."""
    name_to_index = {name: idx for idx, name in enumerate(dof_names)}
    missing = [name for name in requested if name not in name_to_index]
    if missing:
        raise ValueError(
            f"Joint(s) not present in articulation DOF list: {missing}. "
            f"Available DOFs: {list(dof_names)}"
        )
    return [name_to_index[name] for name in requested]


def _apply_drive_api(
    stage: Any,
    joint_path: str,
    stiffness: float,
    damping: float,
    max_force: float,
    drive_type: str,
) -> bool:
    """Create or update the angular DriveAPI on a single revolute joint."""
    from pxr import Sdf, UsdPhysics

    joint_prim = stage.GetPrimAtPath(joint_path)
    if not joint_prim.IsValid():
        return False
    if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
        UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
    drive_api = UsdPhysics.DriveAPI(joint_prim, "angular")
    stiffness_applied = joint_prim.CreateAttribute(
        "drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float
    ).Set(float(stiffness))
    damping_applied = joint_prim.CreateAttribute(
        "drive:angular:physics:damping", Sdf.ValueTypeNames.Float
    ).Set(float(damping))
    force_applied = joint_prim.CreateAttribute(
        "drive:angular:physics:maxForce", Sdf.ValueTypeNames.Float
    ).Set(float(max_force))
    type_attr = drive_api.GetTypeAttr() or drive_api.CreateTypeAttr()
    type_applied = type_attr.Set(drive_type)
    return all(
        bool(applied)
        for applied in (stiffness_applied, damping_applied, force_applied, type_applied)
    )


def configure_drives(
    stage: Any,
    chassis_path: str,
    control_cfg: ControlConfig,
) -> None:
    """Apply DriveAPI attributes to the actively controlled joints."""
    drive_joint_names = list(control_cfg.drive_joint_names)
    steer_joint_names = list(control_cfg.steer_joint_names)

    drive_damping = float(control_cfg.drive_damping)
    drive_max_force = float(control_cfg.drive_max_force)
    steer_stiffness = float(control_cfg.steer_stiffness)
    steer_damping = float(control_cfg.steer_damping)
    steer_max_force = float(control_cfg.steer_max_force)
    drive_type = str(control_cfg.drive_type)

    joints_scope = f"{chassis_path}/joints"
    missing: list[str] = []

    for jname in drive_joint_names:
        if not _apply_drive_api(
            stage,
            f"{joints_scope}/{jname}",
            stiffness=0.0,
            damping=drive_damping,
            max_force=drive_max_force,
            drive_type=drive_type,
        ):
            missing.append(jname)

    for jname in steer_joint_names:
        if not _apply_drive_api(
            stage,
            f"{joints_scope}/{jname}",
            stiffness=steer_stiffness,
            damping=steer_damping,
            max_force=steer_max_force,
            drive_type=drive_type,
        ):
            missing.append(jname)

    if missing:
        raise RuntimeError(f"drive override targets missing from rover USD: {missing}")


def reinforce_pd_gains(
    articulation: Any,
    control_cfg: ControlConfig,
    suspension_cfg: SuspensionConfig,
    dof_names: List[str],
) -> None:
    """Reinforce only MarsLab-owned PD gains after ``world.reset``."""
    drive_joint_names = list(control_cfg.drive_joint_names)
    steer_joint_names = list(control_cfg.steer_joint_names)

    drive_damping = float(control_cfg.drive_damping)
    steer_stiffness = float(control_cfg.steer_stiffness)
    steer_damping = float(control_cfg.steer_damping)

    drive_indices = resolve_joint_indices(dof_names, drive_joint_names)
    steer_indices = resolve_joint_indices(dof_names, steer_joint_names)
    rocker_indices = resolve_joint_indices(dof_names, list(suspension_cfg.rocker_joint_names))
    bogie_indices = resolve_joint_indices(dof_names, list(suspension_cfg.bogie_joint_names))

    owned_indices = drive_indices + steer_indices + rocker_indices + bogie_indices
    if len(set(owned_indices)) != len(owned_indices):
        raise ValueError("drive, steer, rocker, and bogie joint groups must not overlap")
    owned_index_array = np.asarray(owned_indices, dtype=np.int32)
    unowned_indices = sorted(set(range(len(dof_names))) - set(owned_indices))
    unowned_index_array = np.asarray(unowned_indices, dtype=np.int32)
    unowned_before = None
    if unowned_indices:
        prior_kps, prior_kds = articulation.get_gains(joint_indices=unowned_index_array)
        unowned_before = (np.asarray(prior_kps).copy(), np.asarray(prior_kds).copy())

    kps = np.zeros((1, len(owned_indices)), dtype=np.float32)
    kds = np.concatenate(
        (
            np.full(len(drive_indices), drive_damping, dtype=np.float32),
            np.full(len(steer_indices), steer_damping, dtype=np.float32),
            np.full(
                len(rocker_indices),
                float(suspension_cfg.rocker_damping),
                dtype=np.float32,
            ),
            np.full(
                len(bogie_indices),
                float(suspension_cfg.bogie_damping),
                dtype=np.float32,
            ),
        )
    ).reshape(1, -1)
    steer_start = len(drive_indices)
    steer_end = steer_start + len(steer_indices)
    kps[0, steer_start:steer_end] = steer_stiffness

    articulation.set_gains(
        kps=kps,
        kds=kds,
        joint_indices=owned_index_array,
    )
    applied_kps, applied_kds = articulation.get_gains(joint_indices=owned_index_array)
    if not np.allclose(applied_kps, kps) or not np.allclose(applied_kds, kds):
        raise RuntimeError("post-reset PD gain verification failed for MarsLab-owned joints")
    if unowned_before is not None:
        remaining_kps, remaining_kds = articulation.get_gains(joint_indices=unowned_index_array)
        if not np.array_equal(remaining_kps, unowned_before[0]) or not np.array_equal(
            remaining_kds, unowned_before[1]
        ):
            raise RuntimeError("post-reset PD gain update modified an unowned articulation DOF")
    _LOG.info(
        "Post-reset PD gain ownership:\n  owned DOFs updated: %d\n  unowned DOFs preserved: %d",
        len(owned_indices),
        len(unowned_indices),
    )
