"""Sensor attachment for MarsLab.

Dispatches sensor config YAMLs to the correct attach function
based on the 'type' field. No base class, no registry (P1).
"""

import os

import yaml

from marslab.sensors.camera import attach_camera
from marslab.sensors.imu import attach_imu
from marslab.sensors.lidar import attach_lidar
from marslab.sensors.sensor_spawner import SensorHandles, spawn_sensors

__all__ = [
    "attach_camera",
    "attach_imu",
    "attach_lidar",
    "load_and_attach_sensor",
    "SensorHandles",
    "spawn_sensors",
]

_SENSOR_DISPATCH = {
    "camera": attach_camera,
    "imu": attach_imu,
    "lidar": attach_lidar,
}


def load_and_attach_sensor(stage, robot_prim_path: str, config_path: str) -> str | object:
    """Load sensor config from YAML and attach to robot.

    Dispatches to the correct attach_* function based on the
    'type' field in the sensor config.

    Args:
        stage: USD stage.
        robot_prim_path: Robot root prim path.
        config_path: Path to sensor YAML config file.

    Returns:
        Sensor object or prim path from the attach function.

    Raises:
        FileNotFoundError: If config_path does not exist.
        ValueError: If sensor type is unknown.
    """
    abs_path = os.path.abspath(config_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Sensor config not found: {abs_path}")

    with open(abs_path, "r") as f:
        data = yaml.safe_load(f)

    sensor_cfg = data.get("sensor", data)
    sensor_type = sensor_cfg.get("type")

    if sensor_type not in _SENSOR_DISPATCH:
        raise ValueError(
            f"Unknown sensor type '{sensor_type}'. " f"Supported: {list(_SENSOR_DISPATCH.keys())}"
        )

    attach_fn = _SENSOR_DISPATCH[sensor_type]
    return attach_fn(stage, robot_prim_path, sensor_cfg)
