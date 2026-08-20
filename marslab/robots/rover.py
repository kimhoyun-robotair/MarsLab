"""Rover USD spawn and DriveAPI setup orchestration.

Every function here touches Isaac Sim / USD, so imports are deferred
inside each function. Public surface is declared via ``__all__``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from marslab.config.schema.rover import ChassisConfig, RoverConfig, SuspensionConfig, WheelsConfig
from marslab.quaternion import rpy_to_quat

# ``resolve_joint_indices`` re-exported here so ``main.py`` and tests can
# import it via ``from marslab.robots.rover import resolve_joint_indices``
# (the spawn helper sits naturally on the rover facade).
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


def load_rover_usd(usd_path: Path, prim_path: str) -> None:
    """Attach the rover USD under ``prim_path`` and wait for load.

    Args:
        usd_path: Rover USD path from the validated configuration.
        prim_path: Destination stage path (e.g. ``/World/Rover``).

    Raises:
        FileNotFoundError: If ``usd_path`` does not exist.
    """
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
    """Overwrite the rover root Xform with translate + orient.

    Args:
        stage: USD stage handle.
        prim_path: Rover root prim path.
        spawn_xyz: World-frame position (m).
        orientation_rpy: ``(roll, pitch, yaw)`` in radians (ZYX intrinsic).

    Note:
        For the NASA JPL m2020 URDF, callers pass ``[pi, 0, 0]`` to
        compensate for the URDF's non-standard link frame convention.
        See ``docs/frame_conventions.md`` for the full coordinate-frame
        story.
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
    com_offset: tuple[float, float, float],
    angular_damping: float,
    linear_damping: float,
) -> None:
    """Apply CoM override + angular/linear damping on the articulation body.

    See ``configs/rover_m2020.yaml`` comments for tuning rationale.
    """
    from pxr import Gf, PhysxSchema, UsdPhysics

    art_root_prim = stage.GetPrimAtPath(art_root_path)
    if not art_root_prim.IsValid():
        _LOG.warning("%s not found; skipping mass override.", art_root_path)
        return

    if not art_root_prim.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(art_root_prim)
    mass_api = UsdPhysics.MassAPI(art_root_prim)
    mass_api.GetCenterOfMassAttr().Set(
        Gf.Vec3f(float(com_offset[0]), float(com_offset[1]), float(com_offset[2]))
    )

    if angular_damping > 0.0 or linear_damping > 0.0:
        if not art_root_prim.HasAPI(PhysxSchema.PhysxRigidBodyAPI):
            PhysxSchema.PhysxRigidBodyAPI.Apply(art_root_prim)
        rb_api = PhysxSchema.PhysxRigidBodyAPI(art_root_prim)
        if angular_damping > 0.0:
            rb_api.CreateAngularDampingAttr().Set(float(angular_damping))
        if linear_damping > 0.0:
            rb_api.CreateLinearDampingAttr().Set(float(linear_damping))


# --- M2020 ballpark physics injection ---------------------------------------
# Three small helpers below replace the URDF auto-computed mass / inertia /
# friction placeholders with the values declared in
# ``configs/rover_m2020.yaml`` ``chassis:`` / ``wheels:`` /
# ``suspension:`` blocks.  They run pre-reset (right after USD spawn) so
# PhysX picks up the overrides during the first ``world.reset()`` tensor
# sync.  Each helper takes its config block as a plain ``dict`` (the same
# block ``SkidSteerDriveConfig`` validates) so the unit test can mock the
# stage without booting Isaac Sim.


def _set_mass_and_inertia(
    stage: Any,
    prim_path: str,
    mass_kg: float,
    diagonal_inertia: tuple[float, float, float],
) -> bool:
    """Apply ``UsdPhysics.MassAPI`` mass + diagonal inertia to a single prim.

    Returns ``True`` on success, ``False`` if the prim is missing.  All
    USD imports are deferred so unit tests can pass a mock ``stage`` whose
    ``GetPrimAtPath`` returns a mock prim with ``IsValid()`` = False (no
    USD import needed for the negative-path test).
    """
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return False

    from pxr import Gf, UsdPhysics  # noqa: WPS433  (deferred Isaac Sim import)

    if not prim.HasAPI(UsdPhysics.MassAPI):
        UsdPhysics.MassAPI.Apply(prim)
    mass_api = UsdPhysics.MassAPI(prim)
    mass_api.GetMassAttr().Set(float(mass_kg))
    mass_api.GetDiagonalInertiaAttr().Set(
        Gf.Vec3f(
            float(diagonal_inertia[0]),
            float(diagonal_inertia[1]),
            float(diagonal_inertia[2]),
        )
    )
    return True


def apply_chassis_physics(
    stage: Any,
    rigid_body_path: str,
    chassis_cfg: ChassisConfig,
) -> bool:
    """Inject chassis mass + diagonal inertia from the YAML ``chassis:`` block.

    Args:
        stage: USD stage (or a duck-typed mock with ``GetPrimAtPath``).
        rigid_body_path: Articulation root path returned by
            :func:`find_rigid_body_path` (the prim that actually carries
            ``RigidBodyAPI``).
        chassis_cfg: Validated dict matching
            :class:`marslab.config.schema.robot.ChassisConfig`.

    Returns:
        True if the override was applied, False if the prim was missing
        (the caller logs a warning and continues — sensors / drive joints
        may still be configurable from the rover root).

    The inertia tensor is M2020-ballpark (NOT a CAD-derived calibration).
    See ``configs/rover_m2020.yaml`` ``chassis:`` block for the
    bounding-box derivation; the unit test asserts the YAML values match
    the bbox formula to 1 % so a future edit cannot silently desync the
    documented formula from the numbers PhysX sees.
    """
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
    """Inject per-wheel mass / inertia / friction.

    Walks each ``wheel_link_names`` entry under ``chassis_path/{name}``
    and applies:

      * ``UsdPhysics.MassAPI`` mass + diagonal inertia (spin axis = X).
        The two transverse axes share ``inertia_transverse``; the spin
        axis uses ``inertia_spin``.
      * ``UsdPhysics.MaterialAPI`` static + dynamic friction +
        restitution on a freshly-bound material.  Friction lives on a
        ``PhysicsMaterial`` so the same coefficients apply to every
        contact pair this collider participates in (ground plane, rocks,
        DEM mesh).

    Args:
        stage: USD stage handle.
        chassis_path: Path to the chassis Xform whose direct children are
            the wheel links (``LF_DRIVE``, ``LM_DRIVE``, …).  The current
            M2020 USD nests wheels at ``{chassis_path}/{link_name}``.
        wheel_link_names: List of wheel link names to override.  Typically
            the six ``*_DRIVE`` link names taken from the URDF.
        wheels_cfg: Validated dict matching
            :class:`marslab.config.schema.robot.WheelsConfig`.

    Returns:
        Mapping ``{link_name -> bool}`` recording whether the override
        landed on each wheel.  False values indicate a missing prim — the
        caller logs and continues so a typo in the YAML wheel-name list
        does not abort the entire spawn.
    """
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
        results[name] = _set_mass_and_inertia(stage, wheel_prim_path, mass, inertia)
        # Friction lands on the wheel collider via a dedicated PhysX
        # material.  Failure to find the prim has already been recorded
        # in ``results[name]``; the friction binding is still attempted
        # so a follow-up fix to the wheel-link name list takes effect
        # on the next spawn without revisiting this helper.
        _bind_wheel_friction_material(
            stage,
            wheel_prim_path,
            friction_static=friction_static,
            friction_dynamic=friction_dynamic,
            restitution=restitution,
        )
    return results


def _bind_wheel_friction_material(
    stage: Any,
    wheel_prim_path: str,
    *,
    friction_static: float,
    friction_dynamic: float,
    restitution: float,
) -> bool:
    """Bind a per-wheel ``PhysicsMaterial`` carrying the friction coefficients.

    Material lives at ``{wheel_prim_path}/PhysicsMaterial`` so each wheel
    owns its own material prim (cheaper than rebinding a shared material
    six times and easier to inspect in usdview).  Returns False if the
    wheel prim is missing — caller already logged.
    """
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
    physics_material.GetStaticFrictionAttr().Set(float(friction_static))
    physics_material.GetDynamicFrictionAttr().Set(float(friction_dynamic))
    physics_material.GetRestitutionAttr().Set(float(restitution))

    # Bind the material to the wheel collider so PhysX picks it up for
    # every contact this wheel participates in.
    binding_api = UsdShade.MaterialBindingAPI.Apply(prim)
    binding_api.Bind(material, materialPurpose="physics")
    return True


def apply_suspension_damping_split(
    stage: Any,
    chassis_path: str,
    suspension_cfg: SuspensionConfig,
) -> dict[str, bool]:
    """Apply rocker / bogie damping separately to the suspension joints.

    The legacy ``control.suspension_damping`` covered every rocker / bogie
    joint with one number; this helper writes ``rocker_damping`` to the
    rocker joints and ``bogie_damping`` to the bogie joints via the same
    ``drive:angular:physics:damping`` USD attribute used by
    :func:`marslab.robots.drive_api_setup._apply_drive_api`.

    Returns:
        Mapping ``{joint_name -> bool}`` recording whether the damping
        attribute was written.  False = joint prim missing.
    """
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
    """Write ``drive:angular:physics:damping`` on a single joint prim.

    Mirrors the USD attribute path used by ``_apply_drive_api`` so PhysX
    treats the suspension damping channel identically to the wheel /
    steering damping channels.  Returns False if the joint prim is
    missing.

    Note:
        The raw USD attribute path is kept here (not the typed
        ``UsdPhysics.DriveAPI`` accessors) for symmetry with
        ``_apply_drive_api`` and so the unit-test fakes can verify the
        attribute by string key.
    """
    prim = stage.GetPrimAtPath(joint_path)
    if not prim.IsValid():
        return False

    from pxr import Sdf, UsdPhysics  # noqa: WPS433  (deferred)

    if not prim.HasAPI(UsdPhysics.DriveAPI, "angular"):
        UsdPhysics.DriveAPI.Apply(prim, "angular")
    prim.CreateAttribute("drive:angular:physics:damping", Sdf.ValueTypeNames.Float).Set(
        float(damping)
    )
    return True


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

    _LOG.warning("no RigidBodyAPI child under %s; sensors will be static!", chassis_path)
    return chassis_path


def _spawn_rover_usd(
    stage: Any,
    rover: RoverConfig,
    spawn_xyz: tuple[float, float, float],
) -> str:
    """Attach the USD reference, set the spawn pose, and locate the rigid body.

    Loads the rover USD under ``prim_path``, writes the world-frame
    translation + configured orientation onto the root Xform, then walks the
    chassis to find the prim that actually carries ``RigidBodyAPI``.

    Args:
        stage: USD stage (post-``SimulationApp`` init).
        rover: Typed rover configuration validated before Kit starts.
        spawn_xyz: World-frame spawn position (m).

    Returns:
        Path of the moving ``RigidBodyAPI`` prim under
        ``{prim_path}/Body_Chassis``.  Falls back to the chassis path
        itself with a warning when no rigid-body child is found.
    """
    load_rover_usd(rover.usd_path, rover.prim_path)
    apply_spawn_pose(stage, rover.prim_path, spawn_xyz, rover.spawn.orientation_rpy)
    chassis_path = f"{rover.prim_path}/Body_Chassis"
    # Discover the moving rigid-body prim BEFORE applying mass /
    # damping so both ``apply_mass_properties`` and
    # ``apply_chassis_physics`` operate on the same articulation body.
    return find_rigid_body_path(stage, chassis_path)


def _apply_rover_mass(
    stage: Any,
    rigid_body_path: str,
    com_offset: tuple[float, float, float],
    angular_damping: float,
    linear_damping: float,
) -> None:
    """Forward CoM offset + damping overrides to :func:`apply_mass_properties`.

    Thin pass-through that exists so :func:`spawn_rover` can stay a flat
    orchestrator: every override here is optional and any of the three
    inputs may be ``None`` / ``0.0`` to skip.
    """
    apply_mass_properties(
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
    """Validate and apply chassis / wheel / suspension overrides.

    Args:
        stage: USD stage handle.
        rigid_body_path: Articulation root path returned by
            :func:`find_rigid_body_path`.  Wheel and suspension joints
            are addressed relative to its parent (the chassis Xform).
        rover: Typed rover configuration validated before Kit starts.
    """
    chassis_path = f"{rover.prim_path}/Body_Chassis"
    if not apply_chassis_physics(stage, rigid_body_path, rover.chassis):
        _LOG.warning(
            "chassis prim missing at %s; chassis mass/inertia override skipped.",
            rigid_body_path,
        )
    apply_wheel_physics(stage, chassis_path, rover.control.drive_joint_names, rover.wheels)
    apply_suspension_damping_split(stage, chassis_path, rover.suspension)


def spawn_rover(
    stage: Any,
    rover: RoverConfig,
    spawn_xyz: tuple[float, float, float],
) -> SpawnedRover:
    """Attach the rover USD, position it, and set physics overrides.

    Thin orchestrator that delegates to three helpers in order:

    1. :func:`_spawn_rover_usd` -- USD reference + spawn pose + rigid
       body discovery.
    2. :func:`_apply_rover_mass` -- CoM offset + angular / linear
       damping on the articulation body.
    3. :func:`_apply_rover_articulation_physics` -- chassis / wheel /
       suspension overrides validated through pydantic.

    Drive configuration (pre-reset) and PD gain reinforcement
    (post-reset) are left for the caller so it can interleave them
    around ``world.reset()``.

    Args:
        stage: USD stage (post-``SimulationApp`` init).
        rover: Typed rover configuration validated before Kit starts.
        spawn_xyz: World-frame spawn position computed by the caller
            (e.g. via DEM bbox sampling in ``marslab/main.py``).

    Returns:
        :class:`SpawnedRover` with discovered prim paths.

    """
    prim_path = rover.prim_path
    rigid_body_path = _spawn_rover_usd(stage, rover, spawn_xyz)
    _apply_rover_mass(
        stage,
        rigid_body_path,
        rover.com_offset,
        rover.angular_damping,
        rover.linear_damping,
    )

    _apply_rover_articulation_physics(stage, rigid_body_path, rover)

    return SpawnedRover(
        prim_path=prim_path,
        chassis_path=f"{prim_path}/Body_Chassis",
        rigid_body_path=rigid_body_path,
    )
