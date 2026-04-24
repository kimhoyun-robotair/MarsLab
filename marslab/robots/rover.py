"""Rover USD spawn + DriveAPI setup for Stage 3.

Extracted from ``scripts/phase1/run_stage1.py`` so the Stage 3 runtime
can orchestrate rover + scene + ROS2 without inlining ~400 lines of
Isaac-Sim boilerplate.  Every function here touches Isaac Sim / USD, so
imports are deferred inside each function and unit tests are deferred
to integration smoke runs.  Public surface is declared via ``__all__``.
See ``work_log/rover_generation/`` for the step-by-step rationale.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# R3-A1: ``rpy_to_quat`` was relocated to ``marslab.math.quaternion`` as
# the single source of truth.  Re-exported here so every existing import
# site — ``from marslab.robots.rover import rpy_to_quat`` — keeps working
# without modification (tests/unit/test_rover_module.py, sensors/rover_rig.py).
from marslab.math.quaternion import rpy_to_quat  # noqa: F401

# R4-3 (2026-04-22): DriveAPI + PD-gain helpers relocated to
# ``marslab.robots.drive_api_setup``.  Re-exported here so existing
# imports (``from marslab.robots.rover import configure_drives``,
# ``reinforce_pd_gains``) keep working.  Original inline bodies are
from marslab.robots.drive_api_setup import (  # noqa: F401
    _apply_drive_api,
    configure_drives,
    reinforce_pd_gains,
)

__all__ = [
    "rpy_to_quat",
    "resolve_joint_indices",
    "SpawnedRover",
    "load_rover_usd",
    "apply_spawn_pose",
    "apply_mass_properties",
    "find_rigid_body_path",
    "_apply_drive_api",
    "configure_drives",
    "reinforce_pd_gains",
    "spawn_rover",
]


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
    com_offset = rover_cfg.get("com_offset")
    apply_mass_properties(
        stage,
        f"{chassis_path}/Body_Chassis",
        None if com_offset is None else tuple(float(v) for v in com_offset),
        float(rover_cfg.get("angular_damping", 0.0)),
        float(rover_cfg.get("linear_damping", 0.0)),
    )

    rigid_body_path = find_rigid_body_path(stage, chassis_path)
    return SpawnedRover(
        prim_path=prim_path,
        chassis_path=chassis_path,
        rigid_body_path=rigid_body_path,
    )
