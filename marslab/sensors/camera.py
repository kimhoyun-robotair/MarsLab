"""DEPRECATED — replaced by sensor_spawner.py.

This module is retained only until sensors/__init__.py export is removed
and the file is git-rm'd by the user.  Do not import from here.  See the
Reviewer 2 audit C-17 / item #16 (2026-04-24) consolidation, which moved
camera spawn + the ``read_camera_rgb`` / ``read_camera_depth`` helpers
onto :class:`marslab.sensors.sensor_spawner.SensorHandles`.

Original docstring (preserved for reference):
Camera sensor attachment for Isaac Sim.  Attaches RGB and/or depth
cameras to robots. All parameters from YAML config (G5). Requires Isaac
Sim runtime with World stepping. Camera data is only available after
``world.step(render=True)``.
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
        robot_prim_path: Robot root prim path (e.g., "/World/Rover").
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

    name, mount_link = config["name"], config["mount_link"]
    prim_path = f"{robot_prim_path}/{mount_link}/{name}"

    # Fallback if mount_link doesn't exist
    if not stage.GetPrimAtPath(f"{robot_prim_path}/{mount_link}").IsValid():
        prim_path = f"{robot_prim_path}/{name}"

    clip_range = config.get("clipping_range", [0.1, 100.0])

    camera = Camera(
        prim_path=prim_path,
        resolution=tuple(config.get("resolution", [1280, 720])),
        translation=np.array(config.get("offset_position", [0.0, 0.0, 0.0]), dtype=np.float64),
        frequency=config.get("update_rate", 30),
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


def _read_frame(data, dtype) -> np.ndarray:
    """Coerce camera frame data to ``np.ndarray`` of ``dtype`` (empty if None)."""
    return np.array([] if data is None else data, dtype=dtype)


def read_camera_rgb(camera) -> np.ndarray:
    """Read RGBA image from camera. Returns (H, W, 4) uint8 array or empty."""
    return _read_frame(camera.get_rgba(), np.uint8)


def read_camera_depth(camera) -> np.ndarray:
    """Read depth image from camera. Returns (H, W) float32 meters or empty."""
    return _read_frame(camera.get_depth(), np.float32)
