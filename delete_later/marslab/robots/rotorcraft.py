"""Rotorcraft spawning for Isaac Sim.

Spawns an Ingenuity-class rotorcraft from URDF. Phase 1 is kinematic only —
no flight dynamics or Mars aerodynamics. The atmo_density parameter is
accepted for interface compatibility with Phase 2.
Requires Isaac Sim runtime.
"""

import os

import omni.kit.commands
from pxr import Gf, Sdf, UsdGeom, UsdPhysics

from marslab.config.schema import RobotConfig


def spawn_rotorcraft(stage, config: RobotConfig, gravity: float, atmo_density: float) -> str:
    """Spawn a rotorcraft from URDF into the Isaac Sim stage.

    Phase 1: kinematic only. The rotorcraft is placed at a fixed position.
    No flight dynamics or Mars aerodynamics are simulated.

    Args:
        stage: USD stage.
        config: Robot configuration with urdf_path and spawn_position.
        gravity: Surface gravity in m/s^2 (applied to physics scene).
        atmo_density: Atmospheric density in kg/m^3 (unused in Phase 1,
            reserved for Phase 2 aerodynamics).

    Returns:
        The USD prim path of the spawned rotorcraft.

    Raises:
        FileNotFoundError: If the URDF file does not exist.
    """
    urdf_path = os.path.abspath(config.urdf_path)
    if not os.path.isfile(urdf_path):
        raise FileNotFoundError(f"URDF file not found: {urdf_path}")

    # Ensure physics scene with Mars gravity
    physics_scene_path = "/physicsScene"
    scene_prim = stage.GetPrimAtPath(physics_scene_path)
    if not scene_prim.IsValid():
        scene = UsdPhysics.Scene.Define(stage, Sdf.Path(physics_scene_path))
        scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
        scene.CreateGravityMagnitudeAttr().Set(gravity)

    _, import_config = omni.kit.commands.execute("URDFCreateImportConfig")
    import_config.merge_fixed_joints = True
    import_config.fix_base = True  # Fixed in air for Phase 1 kinematic
    import_config.make_default_prim = False
    import_config.create_physics_scene = False

    result = omni.kit.commands.execute(
        "URDFParseAndImportFile",
        urdf_path=urdf_path,
        import_config=import_config,
    )
    robot_prim_path = result if isinstance(result, str) else result[1]

    # Set spawn position
    robot_prim = stage.GetPrimAtPath(robot_prim_path)
    if robot_prim.IsValid():
        xform = UsdGeom.Xformable(robot_prim)
        xform.ClearXformOpOrder()
        translate_op = xform.AddTranslateOp()
        x, y, z = config.spawn_position
        translate_op.Set(Gf.Vec3d(x, y, z))

    return robot_prim_path
