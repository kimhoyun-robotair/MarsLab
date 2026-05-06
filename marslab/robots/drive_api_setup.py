"""Rover DriveAPI and PD-gain facade.

The four functions below — ``resolve_joint_indices``,
``_apply_drive_api``, ``configure_drives``, ``reinforce_pd_gains`` —
provide the runtime scripts with a focused module for rover drive
configuration.  ``marslab/robots/rover.py`` re-exports each name to
preserve existing imports (``from marslab.robots.rover import
configure_drives``).

Ordering contract (critical — PhysX tensor-cache semantics):

1. :func:`configure_drives` MUST run **pre-reset**.  PhysX synchronises
   USD DriveAPI attributes into its tensor cache only at the
   ``world.reset()`` boundary; any attribute writes after reset are
   silently dropped.
2. :func:`reinforce_pd_gains` MUST run **post-reset**.  Only the
   ``articulation.set_gains`` tensor path propagates to the running
   PhysX simulation; USD-level writes at that point are ignored.

The two stages are intentionally two separate callables so the caller
can interleave them around ``world.reset()`` and the physics warm-up
step loop.
"""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np


def resolve_joint_indices(dof_names: List[str], requested: List[str]) -> List[int]:
    """Resolve each requested joint name to its index in ``dof_names``.

    Raises:
        ValueError: If any requested joint is not present.
    """
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
    """Create or update the angular DriveAPI on a single revolute joint.

    Ordering note: called exclusively from :func:`configure_drives`, which
    MUST run **pre-reset** — PhysX syncs USD DriveAPI attributes to its
    tensor cache only at the ``world.reset()`` boundary.  Post-reset
    writes through this helper are silently ignored by PhysX.
    """
    from pxr import Sdf, UsdPhysics

    joint_prim = stage.GetPrimAtPath(joint_path)
    if not joint_prim.IsValid():
        return False
    if not joint_prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
        UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
    drive_api = UsdPhysics.DriveAPI(joint_prim, "angular")
    joint_prim.CreateAttribute("drive:angular:physics:stiffness", Sdf.ValueTypeNames.Float).Set(
        float(stiffness)
    )
    joint_prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
        float(damping)
    )
    joint_prim.CreateAttribute("drive:angular:physics:maxForce", Sdf.ValueTypeNames.Float).Set(
        float(max_force)
    )
    type_attr = drive_api.GetTypeAttr() or drive_api.CreateTypeAttr()
    type_attr.Set(drive_type)
    return True


def configure_drives(
    stage: Any,
    chassis_path: str,
    control_cfg: Dict[str, Any],
) -> None:
    """Apply DriveAPI attributes to drive / steer / suspension joints.

    Ordering note: MUST be called **BEFORE** ``world.reset()`` because
    PhysX syncs USD drive attributes to tensors only at the reset
    boundary; later writes are ignored by the tensor cache.  Post-reset
    gain reinforcement still runs through ``articulation.set_gains`` --
    see :func:`reinforce_pd_gains` for the post-reset counterpart.
    """
    drive_joint_names = list(control_cfg["drive_joint_names"])
    steer_joint_names = list(control_cfg["steer_joint_names"])
    suspension_names = list(control_cfg.get("suspension_joint_names", []))

    # All keys below are required in the ``control:`` block.
    # ``SkidSteerDriveConfig`` validates at load time so a missing YAML
    # key raises ``KeyError`` rather than silently substituting a literal.
    drive_damping = float(control_cfg["drive_damping"])
    drive_max_force = float(control_cfg["drive_max_force"])
    steer_stiffness = float(control_cfg["steer_stiffness"])
    steer_damping = float(control_cfg["steer_damping"])
    steer_max_force = float(control_cfg["steer_max_force"])
    suspension_damping = float(control_cfg["suspension_damping"])
    drive_type = str(control_cfg["drive_type"])

    joints_scope = f"{chassis_path}/joints"

    for jname in drive_joint_names:
        # Velocity mode: stiffness=0, damping=high.
        _apply_drive_api(
            stage,
            f"{joints_scope}/{jname}",
            stiffness=0.0,
            damping=drive_damping,
            max_force=drive_max_force,
            drive_type=drive_type,
        )

    for jname in steer_joint_names:
        # Position mode: stiffness=high, damping=moderate.
        _apply_drive_api(
            stage,
            f"{joints_scope}/{jname}",
            stiffness=steer_stiffness,
            damping=steer_damping,
            max_force=steer_max_force,
            drive_type=drive_type,
        )

    if suspension_damping > 0.0:
        for jname in suspension_names:
            # Damped passive joint: stiffness=0, damping>0.
            _apply_drive_api(
                stage,
                f"{joints_scope}/{jname}",
                stiffness=0.0,
                damping=suspension_damping,
                max_force=steer_max_force,
                drive_type=drive_type,
            )


def reinforce_pd_gains(
    articulation: Any,
    control_cfg: Dict[str, Any],
    dof_names: List[str],
) -> None:
    """Reinforce PD gains into the PhysX tensors after ``world.reset``.

    Ordering note: MUST be called **AFTER** ``world.reset()`` -- only
    the tensor-cache path (``articulation.set_gains``) propagates to
    the running PhysX simulation.  ``articulation.set_effort_modes``
    only touches USD, so post-reset ``set_gains`` is the only path
    that propagates to the tensor cache.  The caller is expected to
    run the warm-up sequence (10-step physics warmup + play timeline,
    see ``marslab/main.py``) immediately before calling this helper.
    """
    drive_joint_names = list(control_cfg["drive_joint_names"])
    steer_joint_names = list(control_cfg["steer_joint_names"])
    suspension_names = list(control_cfg.get("suspension_joint_names", []))

    # See ``configure_drives``; all required keys validated by
    # ``SkidSteerDriveConfig`` at load time.
    drive_damping = float(control_cfg["drive_damping"])
    steer_stiffness = float(control_cfg["steer_stiffness"])
    steer_damping = float(control_cfg["steer_damping"])
    suspension_damping = float(control_cfg["suspension_damping"])

    drive_indices = resolve_joint_indices(dof_names, drive_joint_names)
    steer_indices = resolve_joint_indices(dof_names, steer_joint_names)
    susp_indices: List[int] = []
    if suspension_names and suspension_damping > 0.0:
        susp_indices = resolve_joint_indices(dof_names, suspension_names)

    num_dof = len(dof_names)
    kps = np.zeros((1, num_dof), dtype=np.float32)
    kds = np.zeros((1, num_dof), dtype=np.float32)
    for idx in drive_indices:
        kds[0, idx] = drive_damping
    for idx in steer_indices:
        kps[0, idx] = steer_stiffness
        kds[0, idx] = steer_damping
    for idx in susp_indices:
        kds[0, idx] = suspension_damping

    articulation.set_gains(kps=kps, kds=kds)
