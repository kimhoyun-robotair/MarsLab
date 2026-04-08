"""Rover spawning for Isaac Sim.

Loads a rover URDF, converts to USD, and spawns in the simulation.
Requires Isaac Sim runtime — do NOT import from offline code.
"""

import os

import omni.kit.commands
from pxr import Gf, Sdf, UsdGeom, UsdPhysics

from marslab.config.schema import RobotConfig


def spawn_rover(stage, config: RobotConfig, gravity: float) -> str:
    """Spawn a rover from URDF into the Isaac Sim stage.

    Converts the URDF to USD and places the robot at the configured
    spawn position. Configures the physics scene with the specified gravity.

    Args:
        stage: USD stage.
        config: Robot configuration with urdf_path and spawn_position.
        gravity: Surface gravity magnitude in m/s^2 (e.g., 3.72 for Mars).

    Returns:
        The USD prim path of the spawned robot.

    Raises:
        FileNotFoundError: If the URDF file does not exist.
        RuntimeError: If URDF import fails.
    """
    urdf_path = os.path.abspath(config.urdf_path)
    if not os.path.isfile(urdf_path):
        raise FileNotFoundError(f"URDF file not found: {urdf_path}")

    # Configure physics scene gravity
    physics_scene_path = "/physicsScene"
    scene_prim = stage.GetPrimAtPath(physics_scene_path)
    if not scene_prim.IsValid():
        scene = UsdPhysics.Scene.Define(stage, Sdf.Path(physics_scene_path))
        scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
        scene.CreateGravityMagnitudeAttr().Set(gravity)
    else:
        scene = UsdPhysics.Scene(scene_prim)
        scene.GetGravityMagnitudeAttr().Set(gravity)

    # Create URDF import config
    _, import_config = omni.kit.commands.execute("URDFCreateImportConfig")
    import_config.merge_fixed_joints = False
    import_config.fix_base = False
    import_config.make_default_prim = False
    import_config.create_physics_scene = False

    # Import URDF
    result = omni.kit.commands.execute(
        "URDFParseAndImportFile",
        urdf_path=urdf_path,
        import_config=import_config,
    )
    if result is None or (isinstance(result, tuple) and result[0] is None):
        raise RuntimeError(f"URDF import failed for: {urdf_path}")

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
