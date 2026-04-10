"""Camera sensor attachment for Isaac Sim.

Attaches RGB and/or depth cameras to robots. All parameters from
YAML config (G5). Requires Isaac Sim runtime with World stepping.

Camera data is only available after world.step(render=True).
"""

import numpy as np
from pxr import Gf, UsdGeom


def attach_camera(stage, robot_prim_path: str, config: dict) -> object:
    """Attach an RGB or depth camera to a robot.

    Creates a Camera prim as a child of the robot's mount link.
    If enable_depth is true, adds depth annotator.

    Note: Camera data requires world.step(render=True) to populate.

    Args:
        stage: USD stage.
        robot_prim_path: Robot root prim path (e.g., "/simple_rover").
        config: Sensor config dict with keys: name, mount_link,
            offset_position, resolution, focal_length,
            horizontal_aperture, clipping_range, enable_depth.

    Returns:
        The initialized Camera object.
    """
    try:
        from isaacsim.sensors.camera import Camera
    except ImportError:
        from omni.isaac.sensor import Camera

    name = config["name"]
    mount_link = config["mount_link"]
    prim_path = f"{robot_prim_path}/{mount_link}/{name}"

    # Fallback if mount_link doesn't exist
    parent_prim = stage.GetPrimAtPath(f"{robot_prim_path}/{mount_link}")
    if not parent_prim.IsValid():
        prim_path = f"{robot_prim_path}/{name}"

    offset_pos = config.get("offset_position", [0.0, 0.0, 0.0])
    resolution = tuple(config.get("resolution", [1280, 720]))
    clip_range = config.get("clipping_range", [0.1, 100.0])
    update_rate = config.get("update_rate", 30)

    camera = Camera(
        prim_path=prim_path,
        resolution=resolution,
        translation=np.array(offset_pos, dtype=np.float64),
        frequency=update_rate,
    )
    camera.initialize()

    # Set clipping range via USD
    cam_prim = stage.GetPrimAtPath(prim_path)
    if cam_prim.IsValid():
        cam_geom = UsdGeom.Camera(cam_prim)
        cam_geom.CreateClippingRangeAttr().Set(Gf.Vec2f(float(clip_range[0]), float(clip_range[1])))

    if config.get("enable_depth", False):
        camera.add_distance_to_image_plane_to_frame()

    return camera


def read_camera_rgb(camera) -> np.ndarray:
    """Read RGBA image from camera.

    Returns:
        (H, W, 4) uint8 array, or empty array if no data.
    """
    data = camera.get_rgba()
    if data is None:
        return np.array([], dtype=np.uint8)
    return np.array(data, dtype=np.uint8)


def read_camera_depth(camera) -> np.ndarray:
    """Read depth image from camera (requires enable_depth=true).

    Returns:
        (H, W) float32 array of distances in meters, or empty array.
    """
    data = camera.get_depth()
    if data is None:
        return np.array([], dtype=np.float32)
    return np.array(data, dtype=np.float32)
