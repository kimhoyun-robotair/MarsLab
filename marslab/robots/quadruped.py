"""Quadruped robot spawning for Isaac Sim.

Loads the Unitree Go2 from Isaac Sim's built-in USD assets.
Perception-ready only — no locomotion policy or dynamics validation.
Requires Isaac Sim runtime.
"""

import logging

from pxr import Gf, Sdf, UsdGeom, UsdPhysics

from marslab.config.schema import RobotConfig

logger = logging.getLogger(__name__)


def spawn_quadruped(stage, config: RobotConfig, gravity: float) -> str:
    """Spawn a quadruped robot from a built-in USD asset.

    Loads the Unitree Go2 (or similar) from Isaac Sim's asset library
    and places it at the configured spawn position. Perception-ready
    only — no locomotion policy is applied.

    Args:
        stage: USD stage.
        config: Robot configuration with usd_asset_path and spawn_position.
        gravity: Surface gravity in m/s^2 (applied to physics scene).

    Returns:
        The USD prim path of the spawned quadruped.

    Raises:
        RuntimeError: If the USD asset cannot be loaded.
    """
    # Ensure physics scene with Mars gravity
    physics_scene_path = "/physicsScene"
    scene_prim = stage.GetPrimAtPath(physics_scene_path)
    if not scene_prim.IsValid():
        scene = UsdPhysics.Scene.Define(stage, Sdf.Path(physics_scene_path))
        scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
        scene.CreateGravityMagnitudeAttr().Set(gravity)

    # Resolve asset path
    usd_path = _resolve_asset_path(config.usd_asset_path)

    # Create prim and add USD reference
    prim_path = "/World/quadruped"
    prim = stage.DefinePrim(Sdf.Path(prim_path), "Xform")
    prim.GetReferences().AddReference(usd_path)

    if not prim.IsValid():
        raise RuntimeError(f"Failed to load USD asset: {usd_path}")

    # Set spawn position
    xform = UsdGeom.Xformable(prim)
    xform.ClearXformOpOrder()
    translate_op = xform.AddTranslateOp()
    x, y, z = config.spawn_position
    translate_op.Set(Gf.Vec3d(x, y, z))

    return prim_path


def _resolve_asset_path(asset_path: str) -> str:
    """Resolve a USD asset path, checking Isaac Sim's built-in assets.

    Args:
        asset_path: Relative path like "Isaac/Robots/Unitree/Go2/go2.usd"
            or an absolute path.

    Returns:
        Full resolved asset path.
    """
    # Try Isaac Sim built-in assets first
    try:
        from isaacsim.storage.native import get_assets_root_path

        assets_root = get_assets_root_path()
        if assets_root:
            full_path = f"{assets_root}/{asset_path}"
            logger.info("Resolved asset: %s", full_path)
            return full_path
    except ImportError:
        logger.warning("isaacsim.storage.native not available, using path as-is")

    return asset_path
