"""ROS2 topic naming configuration.

Follows CLAUDE.md convention: /{robot_name}/{sensor_type}
All parameters from YAML config (G5).
"""

# Default sub-topic names per sensor type
SENSOR_TOPICS = {
    "camera": {
        "stereo_rgb": {"sub_topic": "image_raw", "type": "rgb"},
        "depth_camera": {"sub_topic": "image_raw", "type": "depth"},
    },
    "imu": {
        "imu_sensor": {"sub_topic": "data"},
    },
    "lidar": {
        "lidar_3d": {"sub_topic": "points"},
    },
}


def build_topic_name(robot_name: str, sensor_name: str, sub_topic: str) -> str:
    """Build a ROS2 topic name following CLAUDE.md convention.

    Args:
        robot_name: Robot identifier (e.g., "rover_0").
        sensor_name: Sensor name from config (e.g., "stereo_rgb").
        sub_topic: Sub-topic (e.g., "image_raw", "data", "points").

    Returns:
        Full topic path, e.g., "/rover_0/stereo_rgb/image_raw".
    """
    return f"/{robot_name}/{sensor_name}/{sub_topic}"


def get_default_sub_topic(sensor_type: str, sensor_name: str) -> str:
    """Get default sub-topic for a sensor type/name pair.

    Args:
        sensor_type: Sensor type ("camera", "imu", "lidar").
        sensor_name: Sensor name from config.

    Returns:
        Default sub-topic string.
    """
    type_map = SENSOR_TOPICS.get(sensor_type, {})
    info = type_map.get(sensor_name, {})
    return info.get("sub_topic", "data")
