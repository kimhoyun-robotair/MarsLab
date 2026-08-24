"""Spawn and configure the rover USD at the Isaac boundary.
Physics overrides are applied before reset from typed settings.
USD and Isaac imports remain local to runtime helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from marslab.config.schema.rover import ChassisConfig, RoverConfig, SuspensionConfig, WheelsConfig
from marslab.quaternion import rpy_to_quat

# Re-exported so callers use the rover facade for joint-index resolution.
from marslab.robots.drive_api_setup import resolve_joint_indices

_LOG = logging.getLogger(__name__)

__all__ = [
    "resolve_joint_indices",
    "SpawnedRover",
    "load_rover_usd",
    "apply_spawn_pose",
    "apply_mass_properties",
    "apply_chassis_physics",
    "apply_wheel_physics",
    "apply_suspension_damping_split",
    "find_rigid_body_path",
    "spawn_rover",
]


@dataclass
class SpawnedRover:
    """Handles returned by :func:`spawn_rover`."""

    prim_path: str
    chassis_path: str
    rigid_body_path: str


def load_rover_usd(usd_path: Path, prim_path: str) -> None:
    """Attach the rover USD under ``prim_path`` and wait for load."""
    if not usd_path.is_file():
        raise FileNotFoundError(f"Rover USD not found: {usd_path}")

    import omni.kit.app
    from isaacsim.core.utils.stage import add_reference_to_stage, is_stage_loading

    add_reference_to_stage(usd_path=str(usd_path), prim_path=prim_path)
    app = omni.kit.app.get_app()
    while is_stage_loading():
        app.update()


def apply_spawn_pose(
    stage: Any,
    prim_path: str,
    spawn_xyz: tuple[float, float, float],
    orientation_rpy: tuple[float, float, float],
) -> None:
    """Overwrite the rover root Xform with translate + orient."""
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
    com_offset: tuple[float, float, float],
    angular_damping: float,
    linear_damping: float,
) -> bool:
    """Apply CoM override + angular/linear damping on the articulation body."""
    from pxr import Gf, PhysxSchema, UsdPhysics

    art_root_prim = stage.GetPrimAtPath(art_root_path)
    if not art_root_prim.IsValid():
        _LOG.warning("%s not found; skipping mass override.", art_root_path)
        return False

    if not art_root_prim.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(art_root_prim)
    mass_api = UsdPhysics.MassAPI(art_root_prim)
    applied = [
        mass_api.GetCenterOfMassAttr().Set(
            Gf.Vec3f(float(com_offset[0]), float(com_offset[1]), float(com_offset[2]))
        )
    ]

    if not art_root_prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
        PhysxSchema.PhysxRigidBodyAPI.Apply(art_root_prim)
    rb_api = PhysxSchema.PhysxRigidBodyAPI(art_root_prim)
    applied.extend(
        (
            rb_api.CreateAngularDampingAttr().Set(float(angular_damping)),
            rb_api.CreateLinearDampingAttr().Set(float(linear_damping)),
        )
    )
    return all(bool(result) for result in applied)


def _set_mass_and_inertia(
    stage: Any,
    prim_path: str,
    mass_kg: float,
    diagonal_inertia: tuple[float, float, float],
) -> bool:
    """Apply ``UsdPhysics.MassAPI`` mass + diagonal inertia to a single prim."""
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return False

    from pxr import Gf, UsdPhysics  # noqa: WPS433  (deferred Isaac Sim import)

    if not prim.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(prim)
    mass_api = UsdPhysics.MassAPI(prim)
    mass_applied = mass_api.GetMassAttr().Set(float(mass_kg))
    inertia_applied = mass_api.GetDiagonalInertiaAttr().Set(
        Gf.Vec3f(
            float(diagonal_inertia[0]),
            float(diagonal_inertia[1]),
            float(diagonal_inertia[2]),
        )
    )
    return bool(mass_applied) and bool(inertia_applied)


def apply_chassis_physics(
    stage: Any,
    rigid_body_path: str,
    chassis_cfg: ChassisConfig,
) -> bool:
    """Inject chassis mass + diagonal inertia from the YAML ``chassis:`` block."""
    return _set_mass_and_inertia(
        stage,
        rigid_body_path,
        chassis_cfg.mass,
        (
            chassis_cfg.inertia_xx,
            chassis_cfg.inertia_yy,
            chassis_cfg.inertia_zz,
        ),
    )


def apply_wheel_physics(
    stage: Any,
    chassis_path: str,
    wheel_link_names: tuple[str, ...],
    wheels_cfg: WheelsConfig,
) -> dict[str, bool]:
    """Inject per-wheel mass / inertia / friction."""
    mass = wheels_cfg.mass
    inertia = (
        wheels_cfg.inertia_spin,
        wheels_cfg.inertia_transverse,
        wheels_cfg.inertia_transverse,
    )
    friction_static = wheels_cfg.friction_static
    friction_dynamic = wheels_cfg.friction_dynamic
    restitution = wheels_cfg.restitution

    results: dict[str, bool] = {}
    for name in wheel_link_names:
        wheel_prim_path = f"{chassis_path}/{name}"
        mass_applied = _set_mass_and_inertia(stage, wheel_prim_path, mass, inertia)
        material_applied = _bind_wheel_friction_material(
            stage,
            wheel_prim_path,
            friction_static=friction_static,
            friction_dynamic=friction_dynamic,
            restitution=restitution,
        )
        results[name] = mass_applied and material_applied
    return results


def _bind_wheel_friction_material(
    stage: Any,
    wheel_prim_path: str,
    *,
    friction_static: float,
    friction_dynamic: float,
    restitution: float,
) -> bool:
    """Bind a per-wheel ``PhysicsMaterial`` carrying the friction coefficients."""
    prim = stage.GetPrimAtPath(wheel_prim_path)
    if not prim.IsValid():
        return False

    from pxr import Sdf, UsdPhysics, UsdShade  # noqa: WPS433  (deferred)

    material_path = f"{wheel_prim_path}/PhysicsMaterial"
    material = UsdShade.Material.Define(stage, Sdf.Path(material_path))
    material_prim = material.GetPrim()
    if not material_prim.HasAPI(UsdPhysics.MaterialAPI):
        UsdPhysics.MaterialAPI.Apply(material_prim)
    physics_material = UsdPhysics.MaterialAPI(material_prim)
    static_applied = physics_material.GetStaticFrictionAttr().Set(float(friction_static))
    dynamic_applied = physics_material.GetDynamicFrictionAttr().Set(float(friction_dynamic))
    restitution_applied = physics_material.GetRestitutionAttr().Set(float(restitution))

    binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
    binding_applied = binding_api.Bind(material, materialPurpose="physics")
    return all(
        bool(applied)
        for applied in (
            static_applied,
            dynamic_applied,
            restitution_applied,
            binding_applied,
        )
    )


def apply_suspension_damping_split(
    stage: Any,
    chassis_path: str,
    suspension_cfg: SuspensionConfig,
) -> dict[str, bool]:
    """Apply rocker / bogie damping separately to the suspension joints."""
    rocker_names = suspension_cfg.rocker_joint_names
    bogie_names = suspension_cfg.bogie_joint_names
    rocker_damping = suspension_cfg.rocker_damping
    bogie_damping = suspension_cfg.bogie_damping
    joints_scope = f"{chassis_path}/joints"

    results: dict[str, bool] = {}
    for jname in rocker_names:
        results[jname] = _write_joint_damping(stage, f"{joints_scope}/{jname}", rocker_damping)
    for jname in bogie_names:
        results[jname] = _write_joint_damping(stage, f"{joints_scope}/{jname}", bogie_damping)
    return results


def _write_joint_damping(stage: Any, joint_path: str, damping: float) -> bool:
    """Write ``drive:angular:physics:damping`` on a single joint prim."""
    prim = stage.GetPrimAtPath(joint_path)
    if not prim.IsValid():
        return False

    from pxr import Sdf, UsdPhysics  # noqa: WPS433  (deferred)

    if not prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
        UsdPhysics.DriveAPI.Apply(prim, "angular")
    applied = prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
        float(damping)
    )
    return bool(applied)


def find_rigid_body_path(stage: Any, chassis_path: str, rigid_body_prim_name: str) -> str:
    """Resolve the configured direct child and require a rigid-body contract."""
    from pxr import UsdPhysics

    chassis_prim = stage.GetPrimAtPath(chassis_path)
    if not chassis_prim.IsValid():
        raise RuntimeError(f"Chassis prim missing at {chassis_path}")

    rigid_body_path = f"{chassis_path}/{rigid_body_prim_name}"
    rigid_body_prim = stage.GetPrimAtPath(rigid_body_path)
    if not rigid_body_prim.IsValid():
        raise RuntimeError(f"Configured chassis rigid body missing at {rigid_body_path}")
    if rigid_body_prim.GetParent() != chassis_prim:
        raise RuntimeError(
            f"Configured chassis rigid body must be a direct child: {rigid_body_path}"
        )
    if not rigid_body_prim.HasAPI(UsdPhysics.RigidBodyAPI):
        raise RuntimeError(f"Configured chassis target lacks RigidBodyAPI: {rigid_body_path}")
    return rigid_body_path


def _spawn_rover_usd(
    stage: Any,
    rover: RoverConfig,
    spawn_xyz: tuple[float, float, float],
) -> str:
    """Attach the USD reference, set the spawn pose, and locate the rigid body."""
    load_rover_usd(rover.usd_path, rover.prim_path)
    apply_spawn_pose(stage, rover.prim_path, spawn_xyz, rover.spawn.orientation_rpy)
    chassis_path = f"{rover.prim_path}/Body_Chassis"
    return find_rigid_body_path(stage, chassis_path, rover.chassis.rigid_body_prim_name)


def _apply_rover_mass(
    stage: Any,
    rigid_body_path: str,
    com_offset: tuple[float, float, float],
    angular_damping: float,
    linear_damping: float,
) -> bool:
    """Forward CoM offset + damping overrides to :func:`apply_mass_properties`."""
    return apply_mass_properties(
        stage,
        rigid_body_path,
        com_offset,
        angular_damping,
        linear_damping,
    )


def _apply_rover_articulation_physics(
    stage: Any,
    rigid_body_path: str,
    rover: RoverConfig,
) -> None:
    """Validate and apply chassis / wheel / suspension overrides."""
    chassis_path = f"{rover.prim_path}/Body_Chassis"
    missing: list[str] = []
    if not apply_chassis_physics(stage, rigid_body_path, rover.chassis):
        missing.append(rigid_body_path)
    wheel_results = apply_wheel_physics(
        stage,
        chassis_path,
        rover.wheels.link_names,
        rover.wheels,
    )
    missing.extend(name for name, applied in wheel_results.items() if not applied)
    suspension_results = apply_suspension_damping_split(stage, chassis_path, rover.suspension)
    missing.extend(name for name, applied in suspension_results.items() if not applied)
    if missing:
        raise RuntimeError(f"physics override targets missing from rover USD: {missing}")


def spawn_rover(
    stage: Any,
    rover: RoverConfig,
    spawn_xyz: tuple[float, float, float],
) -> SpawnedRover:
    """Attach the rover USD, position it, and set physics overrides."""
    prim_path = rover.prim_path
    rigid_body_path = _spawn_rover_usd(stage, rover, spawn_xyz)
    if not _apply_rover_mass(
        stage,
        rigid_body_path,
        rover.com_offset,
        rover.angular_damping,
        rover.linear_damping,
    ):
        raise RuntimeError(f"rigid-body override target missing from rover USD: {rigid_body_path}")

    _apply_rover_articulation_physics(stage, rigid_body_path, rover)

    return SpawnedRover(
        prim_path=prim_path,
        chassis_path=f"{prim_path}/Body_Chassis",
        rigid_body_path=rigid_body_path,
    )
