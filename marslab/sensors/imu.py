"""IMU sensor attachment for Isaac Sim.

Attaches an IMU sensor to robots. At rest on Mars, z-axis must
read 3.72 +/- 0.05 m/s^2 (THE critical test). All parameters
from YAML config (G5). Requires Isaac Sim runtime with World stepping.
"""

from pxr import Gf


def attach_imu(stage, robot_prim_path: str, config: dict) -> str:
    """Attach an IMU sensor to a robot.

    Creates an IMU sensor prim under the robot's mount link.
    The IMU automatically reads from the physics scene gravity
    (set to Mars 3.72 m/s^2). Data requires world.step() to populate.

    Args:
        stage: USD stage.
        robot_prim_path: Robot root prim path.
        config: Sensor config dict with keys: name, mount_link,
            offset_position, offset_orientation, update_rate.

    Returns:
        The IMU sensor prim path.
    """
    import omni.kit.commands

    name = config["name"]
    mount_link = config["mount_link"]
    parent_path = f"{robot_prim_path}/{mount_link}"
    sensor_path = f"{parent_path}/{name}"
    offset_pos = config.get("offset_position", [0.0, 0.0, 0.0])
    update_rate = config.get("update_rate", 200)

    # Ensure parent prim exists
    parent_prim = stage.GetPrimAtPath(parent_path)
    if not parent_prim.IsValid():
        parent_path = robot_prim_path
        sensor_path = f"{parent_path}/{name}"

    # Create IMU sensor via Isaac Sim command
    omni.kit.commands.execute(
        "IsaacSensorCreateImuSensor",
        path=sensor_path,
        parent=None,
        sensor_period=1.0 / update_rate,
        translation=Gf.Vec3d(*offset_pos),
        orientation=Gf.Quatd(1.0, 0.0, 0.0, 0.0),
    )

    return sensor_path


def read_imu(imu_prim_path: str) -> dict:
    """Read current IMU sensor data.

    Must be called after world.step() for data to be populated.

    Args:
        imu_prim_path: The prim path of the IMU sensor.

    Returns:
        Dict with keys:
        - lin_acc: [ax, ay, az] in m/s^2 (z should be ~3.72 at rest)
        - ang_vel: [gx, gy, gz] in rad/s
    """
    try:
        from isaacsim.sensors.physics import _sensor
    except ImportError:
        from omni.isaac.sensor import _sensor

    imu_interface = _sensor.acquire_imu_sensor_interface()
    reading = imu_interface.get_sensor_reading(
        imu_prim_path, use_latest_data=True, read_gravity=True
    )

    return {
        "lin_acc": [reading.lin_acc_x, reading.lin_acc_y, reading.lin_acc_z],
        "ang_vel": [reading.ang_vel_x, reading.ang_vel_y, reading.ang_vel_z],
    }
