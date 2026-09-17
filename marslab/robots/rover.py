"""Spawn and configure the rover USD at the Isaac boundary.
Physics overrides are applied before reset from typed settings.
USD and Isaac imports remain local to runtime helpers."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from marslab.config.schema.rover import RoverConfig, SuspensionConfig, WheelsConfig
from marslab.quaternion import rpy_to_quat

# Re-exported so callers use the rover facade for joint-index resolution.
from marslab.robots.drive_api_setup import resolve_joint_indices

_LOG = logging.getLogger(__name__)

__all__ = [
    "resolve_joint_indices",
    "SpawnedRover",
    "load_rover_usd",
    "apply_spawn_pose",
    "apply_body_damping",
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


def apply_body_damping(
    stage: Any,
    rigid_body_path: str,
    angular_damping: float,
    linear_damping: float,
) -> None:
    """Set chassis damping while retaining source USD mass properties."""
    from pxr import PhysxSchema

    prim = _require_rigid_body(stage, rigid_body_path)
    rb_api = PhysxSchema.PhysxRigidBodyAPI.Apply(prim)
    angular = _set_verified_float(rb_api.CreateAngularDampingAttr(), angular_damping)
    linear = _set_verified_float(rb_api.CreateLinearDampingAttr(), linear_damping)
    _LOG.info(
        "marslab.physics.damping_verified body=%s angular=%s linear=%s",
        rigid_body_path,
        angular,
        linear,
    )
    _log_usd_mass_properties(prim)


def _require_rigid_body(stage: Any, prim_path: str) -> Any:
    from pxr import UsdPhysics

    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid() or not prim.IsActive():
        raise RuntimeError(f"Configured rigid body missing or inactive: {prim_path}")
    if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
        raise RuntimeError(f"Configured target lacks RigidBodyAPI: {prim_path}")
    if not UsdPhysics.RigidBodyAPI(prim).GetRigidBodyEnabledAttr().Get():
        raise RuntimeError(f"Configured rigid body is disabled: {prim_path}")
    if prim.IsInstanceProxy():
        raise RuntimeError(f"Configured rigid body is not editable: {prim_path}")
    return prim


def _set_verified_float(attribute: Any, requested: float) -> float:
    if not attribute.Set(float(requested)):
        raise RuntimeError(f"Could not set physics attribute: {attribute.GetPath()}")
    actual = attribute.Get()
    if actual is None or not math.isclose(float(actual), requested, rel_tol=1e-6, abs_tol=1e-8):
        raise RuntimeError(
            f"Physics attribute mismatch at {attribute.GetPath()}: "
            f"requested={requested}, actual={actual}"
        )
    return float(actual)


def _log_usd_mass_properties(prim: Any) -> None:
    from pxr import UsdPhysics

    mass = UsdPhysics.MassAPI(prim)
    _LOG.info(
        "marslab.physics.usd_mass_properties body=%s mass=%s inertia=%s center_of_mass=%s",
        prim.GetPath(),
        mass.GetMassAttr().Get(),
        mass.GetDiagonalInertiaAttr().Get(),
        mass.GetCenterOfMassAttr().Get(),
    )


def apply_wheel_physics(
    stage: Any,
    chassis_path: str,
    wheel_link_names: tuple[str, ...],
    wheels_cfg: WheelsConfig,
) -> None:
    """Set wheel contact and verify each owned collider's effective material."""
    for name in wheel_link_names:
        wheel_prim_path = f"{chassis_path}/{name}"
        wheel = _require_rigid_body(stage, wheel_prim_path)
        colliders = _wheel_colliders(wheel)
        _bind_wheel_friction_material(
            stage,
            wheel,
            colliders,
            f"{chassis_path}/PhysicsMaterials/{name}",
            wheels_cfg,
        )
        _log_usd_mass_properties(wheel)


def _wheel_colliders(wheel: Any) -> list[Any]:
    """Include collision instance proxies, without crossing rigid-body ownership."""
    from pxr import Usd, UsdPhysics

    colliders = []
    for prim in Usd.PrimRange(wheel, Usd.TraverseInstanceProxies()):
        if prim != wheel and prim.HasAPI(UsdPhysics.RigidBodyAPI):
            raise RuntimeError(
                f"Wheel material scope contains another rigid body: {prim.GetPath()}"
            )
        if (
            prim.HasAPI(UsdPhysics.CollisionAPI)
            and UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()
        ):
            colliders.append(prim)
    if not colliders:
        raise RuntimeError(f"Configured wheel has no enabled colliders: {wheel.GetPath()}")
    return colliders


def _bind_wheel_friction_material(
    stage: Any,
    wheel: Any,
    colliders: list[Any],
    material_path: str,
    wheels_cfg: WheelsConfig,
) -> None:
    """Author at the editable body; physics bindings leave visual materials intact."""
    from pxr import UsdPhysics, UsdShade

    material = UsdShade.Material.Define(stage, material_path)
    physics_material = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    static = _set_verified_float(
        physics_material.CreateStaticFrictionAttr(), wheels_cfg.friction_static
    )
    dynamic = _set_verified_float(
        physics_material.CreateDynamicFrictionAttr(), wheels_cfg.friction_dynamic
    )
    restitution = _set_verified_float(
        physics_material.CreateRestitutionAttr(), wheels_cfg.restitution
    )

    binding_api = UsdShade.MaterialBindingAPI.Apply(wheel)
    if not binding_api.Bind(
        material,
        bindingStrength=UsdShade.Tokens.strongerThanDescendants,
        materialPurpose="physics",
    ):
        raise RuntimeError(f"Could not bind wheel physics material: {wheel.GetPath()}")
    for collider in colliders:
        effective, relationship = UsdShade.MaterialBindingAPI(collider).ComputeBoundMaterial(
            materialPurpose="physics"
        )
        if not effective or effective.GetPath() != material.GetPath():
            raise RuntimeError(
                f"Wheel physics material mismatch at {collider.GetPath()}: "
                f"expected={material.GetPath()}, actual={effective.GetPath()}, "
                f"binding={relationship.GetPath()}"
            )
        _LOG.info(
            "marslab.physics.wheel_contact_verified body=%s collider=%s material=%s "
            "static=%s dynamic=%s restitution=%s instance_proxy=%s",
            wheel.GetPath(),
            collider.GetPath(),
            effective.GetPath(),
            static,
            dynamic,
            restitution,
            collider.IsInstanceProxy(),
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


def _apply_rover_articulation_physics(
    stage: Any,
    rover: RoverConfig,
) -> None:
    """Validate and apply wheel contact and suspension overrides."""
    chassis_path = f"{rover.prim_path}/Body_Chassis"
    apply_wheel_physics(
        stage,
        chassis_path,
        rover.wheels.link_names,
        rover.wheels,
    )
    suspension_results = apply_suspension_damping_split(stage, chassis_path, rover.suspension)
    missing = [name for name, applied in suspension_results.items() if not applied]
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
    apply_body_damping(
        stage,
        rigid_body_path,
        rover.angular_damping,
        rover.linear_damping,
    )

    _apply_rover_articulation_physics(stage, rover)

    return SpawnedRover(
        prim_path=prim_path,
        chassis_path=f"{prim_path}/Body_Chassis",
        rigid_body_path=rigid_body_path,
    )
