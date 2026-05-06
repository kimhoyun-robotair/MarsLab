"""Sensor spawn helpers -- see :func:`spawn_sensors`.

:func:`spawn_sensors` returns a :class:`SensorHandles` object bundling
the live Isaac Sim sensor handles, their USD prim paths, and the
read-side helpers (``read_imu`` / ``read_camera_rgb`` /
``read_camera_depth`` / ``read_lidar_3d_point_cloud``).  The IMU
Mars-gravity assertion and the ``local_orientation_rpy_deg`` YAML
plumbing live alongside the spawn implementation in
:mod:`marslab.sensors.sensor_spawner`.
"""

from marslab.sensors.sensor_spawner import SensorHandles, spawn_sensors

__all__ = [
    "SensorHandles",
    "spawn_sensors",
]
