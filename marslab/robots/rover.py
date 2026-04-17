"""Rover USD spawn + DriveAPI setup for Stage 3.

Extracted from ``scripts/phase1/run_stage1.py`` so the Stage 3 runtime
can orchestrate rover + scene + ROS2 without inlining ~400 lines of
Isaac-Sim boilerplate.  Every function here touches Isaac Sim / USD, so
imports are deferred inside each function and unit tests are deferred
to integration smoke runs.

Public surface:

* :func:`rpy_to_quat` — pure ZYX intrinsic RPY → scalar-first quat.
* :func:`resolve_joint_indices` — name-based DOF index lookup.
* :func:`load_rover_usd` — add USD reference under a prim path.
* :func:`apply_spawn_pose` — set Xform translate/orient on the root.
* :func:`apply_mass_properties` — CoM override + angular/linear damping.
* :func:`find_rigid_body_path` — locate the RigidBodyAPI child prim.
* :func:`configure_drives` — pre-reset DriveAPI attribute writes.
* :func:`reinforce_pd_gains` — post-reset ``set_gains`` to the PhysX tensors.
* :func:`spawn_rover` — orchestrates the above in the expected order.

The split mirrors the sequence the Stage 1 runtime follows so the
refactor is mechanically equivalent.  See ``work_log/rover_generation/``
for the rationale behind each step.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def rpy_to_quat(roll: float, pitch: float, yaw: float) -> Tuple[float, float, float, float]:
    """Convert roll-pitch-yaw (radians) to quaternion ``(w, x, y, z)``.

    ZYX intrinsic convention (URDF / ROS standard).  Pure NumPy; no
    Isaac Sim dependency.
    """
    cr, sr = np.cos(roll / 2.0), np.sin(roll / 2.0)
    cp, sp = np.cos(pitch / 2.0), np.sin(pitch / 2.0)
    cy, sy = np.cos(yaw / 2.0), np.sin(yaw / 2.0)
    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return float(w), float(x), float(y), float(z)


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


@dataclass
class SpawnedRover:
    """Handles returned by :func:`spawn_rover`.

    Fields:
        prim_path: USD path to the rover root Xform (``/World/Rover``).
        chassis_path: USD path to the articulation-root chassis.
        rigid_body_path: USD path to the moving RigidBodyAPI child (or
            ``chassis_path`` if no child was found).
    """

    prim_path: str
    chassis_path: str
    rigid_body_path: str


def load_rover_usd(usd_abs: str, prim_path: str) -> None:
    """Attach the rover USD under ``prim_path`` and wait for load.

    Args:
        usd_abs: Absolute filesystem path to the rover USD.
        prim_path: Destination stage path (e.g. ``/World/Rover``).

    Raises:
        FileNotFoundError: If ``usd_abs`` does not exist.
    """
    if not os.path.isfile(usd_abs):
        raise FileNotFoundError(f"Rover USD not found: {usd_abs}")

    import omni.kit.app
    from isaacsim.core.utils.stage import add_reference_to_stage, is_stage_loading

    add_reference_to_stage(usd_path=usd_abs, prim_path=prim_path)
    app = omni.kit.app.get_app()
    while is_stage_loading():
        app.update()


def apply_spawn_pose(
    stage: Any,
    prim_path: str,
    spawn_xyz: Tuple[float, float, float],
    orientation_rpy: Tuple[float, float, float],
) -> None:
    """Overwrite the rover root Xform with translate + orient.

    Args:
        stage: USD stage handle.
        prim_path: Rover root prim path.
        spawn_xyz: World-frame position (m).
        orientation_rpy: ``(roll, pitch, yaw)`` in radians (ZYX intrinsic).
    """
    from pxr import Gf, UsdGeom

    rover_prim = stage.GetPrimAtPath(prim_path)
    if not rover_prim.IsValid():
        raise RuntimeError(f"Rover prim missing at {prim_path}; USD not loaded?")

    xform = UsdGeom.Xformable(rover_prim)
    xform.ClearXformOpOrder()
    translate_op = xform.AddTranslateOp()
    translate_op.Set(Gf.Vec3d(float(spawn_xyz[0]), float(spawn_xyz[1]), float(spawn_xyz[2])))

    qw, qx, qy, qz = rpy_to_quat(
        float(orientation_rpy[0]),
        float(orientation_rpy[1]),
        float(orientation_rpy[2]),
    )
    orient_op = xform.AddOrientOp()
    orient_op.Set(Gf.Quatf(float(qw), float(qx), float(qy), float(qz)))


def apply_mass_properties(
    stage: Any,
    art_root_path: str,
    com_offset: Optional[Tuple[float, float, float]],
    angular_damping: float,
    linear_damping: float,
) -> None:
    """Apply CoM override + angular/linear damping on the articulation body.

    All three overrides are optional (pass ``None`` / ``0.0`` to skip).
    See ``configs/robots/rover_m2020.yaml`` comments for tuning rationale.
    """
    from pxr import Gf, Sdf, UsdPhysics

    art_root_prim = stage.GetPrimAtPath(art_root_path)
    if not art_root_prim.IsValid():
        print(
            f"[marslab.robots.rover] WARNING: {art_root_path} not found; "
            "skipping mass override.",
            file=sys.stderr,
        )
        return

    if com_offset is not None:
        if not art_root_prim.HasAPI(UsdPhysics.MassAPI):
            UsdPhysics.MassAPI.Apply(art_root_prim)
        mass_api = UsdPhysics.MassAPI(art_root_prim)
        mass_api.GetCenterOfMassAttr().Set(
            Gf.Vec3f(float(com_offset[0]), float(com_offset[1]), float(com_offset[2]))
        )

    if angular_damping > 0.0:
        attr = art_root_prim.CreateAttribute(
            "physxRigidBody:angularDamping", Sdf.ValueTypeNames.Float
        )
        attr.Set(float(angular_damping))

    if linear_damping > 0.0:
        attr = art_root_prim.CreateAttribute(
            "physxRigidBody:linearDamping", Sdf.ValueTypeNames.Float
        )
        attr.Set(float(linear_damping))


def find_rigid_body_path(stage: Any, chassis_path: str) -> str:
    """Return the path of the first RigidBodyAPI child of the chassis.

    After ``URDF→USD`` with ``merge_fixed_joints=False`` the chassis is
    a static Xform and its first child carries ``RigidBodyAPI``.  That
    child is the prim that actually moves with physics — all sensors
    must attach there.  If no such child is found, the caller gets
    ``chassis_path`` back with a warning on stderr (sensors would then
    be static in world space).
    """
    from pxr import UsdPhysics

    chassis_prim = stage.GetPrimAtPath(chassis_path)
    if not chassis_prim.IsValid():
        raise RuntimeError(f"Chassis prim missing at {chassis_path}")

    for child in chassis_prim.GetChildren():
        if child.HasAPI(UsdPhysics.RigidBodyAPI):
            return str(child.GetPath())

    print(
        f"[marslab.robots.rover] WARNING: no RigidBodyAPI child under {chassis_path}; "
        "sensors will be static!",
        file=sys.stderr,
    )
    return chassis_path


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

    Must be called BEFORE ``world.reset()`` because PhysX syncs USD
    drive attributes to tensors only at the reset boundary; later
    writes are ignored by the tensor cache.  Post-reset gain reinforce
    still runs through ``articulation.set_gains`` — see
    :func:`reinforce_pd_gains`.
    """
    drive_joint_names = list(control_cfg["drive_joint_names"])
    steer_joint_names = list(control_cfg["steer_joint_names"])
    suspension_names = list(control_cfg.get("suspension_joint_names", []))

    drive_damping = float(control_cfg.get("drive_damping", 100000.0))
    drive_max_force = float(control_cfg.get("drive_max_force", 1000000.0))
    steer_stiffness = float(control_cfg.get("steer_stiffness", 50000.0))
    steer_damping = float(control_cfg.get("steer_damping", 5000.0))
    steer_max_force = float(control_cfg.get("steer_max_force", 100000.0))
    suspension_damping = float(control_cfg.get("suspension_damping", 0.0))
    drive_type = str(control_cfg.get("drive_type", "acceleration"))

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

    ``articulation.set_effort_modes`` only touches USD, so post-reset
    ``set_gains`` is the only path that propagates to the tensor cache.
    Matches the Stage 1 warm-up sequence (10-step physics warmup + play
    timeline) that the caller is expected to run immediately before
    calling this helper.
    """
    drive_joint_names = list(control_cfg["drive_joint_names"])
    steer_joint_names = list(control_cfg["steer_joint_names"])
    suspension_names = list(control_cfg.get("suspension_joint_names", []))

    drive_damping = float(control_cfg.get("drive_damping", 100000.0))
    steer_stiffness = float(control_cfg.get("steer_stiffness", 50000.0))
    steer_damping = float(control_cfg.get("steer_damping", 5000.0))
    suspension_damping = float(control_cfg.get("suspension_damping", 0.0))

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


def spawn_rover(
    stage: Any,
    rover_cfg: Dict[str, Any],
    usd_abs: str,
    spawn_xyz: Tuple[float, float, float],
) -> SpawnedRover:
    """Attach the rover USD, position it, and set physics overrides.

    This is a convenience wrapper that calls
    :func:`load_rover_usd` → :func:`apply_spawn_pose` →
    :func:`apply_mass_properties` → :func:`find_rigid_body_path` in
    order.  Drive configuration (pre-reset) and PD gain reinforcement
    (post-reset) are left for the caller so it can interleave them
    around ``world.reset()``.

    Args:
        stage: USD stage (post-``SimulationApp`` init).
        rover_cfg: Merged ``rover:`` block from the scenario config.
        usd_abs: Absolute path to the rover USD file.
        spawn_xyz: World-frame spawn position from
            :func:`marslab.config.scenario_loader.resolve_spawn_pose`.

    Returns:
        :class:`SpawnedRover` with discovered prim paths.
    """
    prim_path = str(rover_cfg.get("prim_path", "/World/Rover"))
    load_rover_usd(usd_abs, prim_path)

    spawn_block = rover_cfg.get("spawn", {}) if isinstance(rover_cfg, dict) else {}
    rpy = tuple(
        spawn_block.get("orientation_rpy")
        or rover_cfg.get("spawn_orientation_rpy", [0.0, 0.0, 0.0])
    )
    apply_spawn_pose(stage, prim_path, spawn_xyz, rpy)

    chassis_path = f"{prim_path}/Body_Chassis"
    # The articulation body lives one level deeper; that's also where
    # damping + CoM overrides belong.
    art_body_path = f"{chassis_path}/Body_Chassis"

    com_offset = rover_cfg.get("com_offset")
    if com_offset is not None:
        com_offset = (float(com_offset[0]), float(com_offset[1]), float(com_offset[2]))
    apply_mass_properties(
        stage,
        art_body_path,
        com_offset,
        float(rover_cfg.get("angular_damping", 0.0)),
        float(rover_cfg.get("linear_damping", 0.0)),
    )

    rigid_body_path = find_rigid_body_path(stage, chassis_path)
    return SpawnedRover(
        prim_path=prim_path,
        chassis_path=chassis_path,
        rigid_body_path=rigid_body_path,
    )
