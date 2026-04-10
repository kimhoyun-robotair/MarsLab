"""LiDAR sensor attachment for Isaac Sim.

Attaches a rotating LiDAR sensor to robots. All parameters from
YAML config (G5). Requires Isaac Sim runtime.
"""

import numpy as np
from pxr import Gf, Sdf, UsdGeom


def attach_lidar(stage, robot_prim_path: str, config: dict) -> str:
    """Attach an RTX or PhysX LiDAR sensor to a robot.

    Creates a LiDAR prim under the robot's mount link.

    Args:
        stage: USD stage.
        robot_prim_path: Robot root prim path.
        config: Sensor config dict with keys: name, mount_link,
            offset_position, rotation_rate, horizontal_fov,
            vertical_fov, max_range, min_range.

    Returns:
        The LiDAR sensor prim path.
    """
    import omni.kit.commands

    name = config["name"]
    mount_link = config["mount_link"]
    parent_path = f"{robot_prim_path}/{mount_link}"
    sensor_path = f"{parent_path}/{name}"
    offset_pos = config.get("offset_position", [0.0, 0.0, 0.0])
    rotation_rate = config.get("rotation_rate", 10.0)
    h_fov = config.get("horizontal_fov", [0.0, 360.0])
    v_fov = config.get("vertical_fov", [-15.0, 15.0])
    h_res = config.get("horizontal_resolution", 0.4)
    v_res = config.get("vertical_resolution", 2.0)
    max_range = config.get("max_range", 100.0)
    min_range = config.get("min_range", 0.4)

    # Ensure parent prim exists
    parent_prim = stage.GetPrimAtPath(parent_path)
    if not parent_prim.IsValid():
        parent_path = robot_prim_path
        sensor_path = f"{parent_path}/{name}"

    # Try RTX LiDAR creation command
    try:
        omni.kit.commands.execute(
            "RangeSensorCreateLidar",
            path=sensor_path,
            parent=None,
            min_range=min_range,
            max_range=max_range,
            draw_points=False,
            draw_lines=False,
            horizontal_fov=h_fov[1] - h_fov[0],
            vertical_fov=(v_fov[1] - v_fov[0]),
            horizontal_resolution=h_res,
            vertical_resolution=v_res,
            rotation_rate=rotation_rate,
            high_lod=True,
            yaw_offset=0.0,
        )
    except Exception:
        # Fallback: create a basic Xform prim as placeholder
        prim = stage.DefinePrim(Sdf.Path(sensor_path), "Xform")
        xform = UsdGeom.Xformable(prim)
        xform.AddTranslateOp().Set(Gf.Vec3d(*offset_pos))

    # Set position offset
    lidar_prim = stage.GetPrimAtPath(sensor_path)
    if lidar_prim.IsValid():
        xformable = UsdGeom.Xformable(lidar_prim)
        existing_ops = xformable.GetOrderedXformOps()
        if not existing_ops:
            xformable.AddTranslateOp().Set(Gf.Vec3d(*offset_pos))

    return sensor_path


def read_lidar_point_cloud(lidar_prim_path: str) -> np.ndarray:
    """Read current LiDAR point cloud.

    Args:
        lidar_prim_path: The prim path of the LiDAR sensor.

    Returns:
        (N, 3) float32 array of XYZ points, or empty (0, 3) array.
    """
    try:
        from isaacsim.sensors.rtx import LidarRtx

        lidar = LidarRtx(lidar_prim_path)
        pc = lidar.get_point_cloud()
        if pc is not None and len(pc) > 0:
            return np.array(pc, dtype=np.float32).reshape(-1, 3)
    except (ImportError, Exception):
        pass

    try:
        from omni.isaac.range_sensor import _range_sensor

        lidar_interface = _range_sensor.acquire_lidar_sensor_interface()
        pc = lidar_interface.get_point_cloud_data(lidar_prim_path)
        if pc is not None and len(pc) > 0:
            return np.array(pc, dtype=np.float32).reshape(-1, 3)
    except (ImportError, Exception):
        pass

    return np.empty((0, 3), dtype=np.float32)
