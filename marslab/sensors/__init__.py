"""Sensor spawn facade for MarsLab.

The unified spawn API lives in ``sensor_spawner.py``.  Earlier
per-sensor modules (``camera.py``, ``imu.py``, ``lidar.py``) have been
removed; use :func:`marslab.sensors.sensor_spawner.spawn_sensors` for
all sensor types.

:func:`spawn_sensors` returns a :class:`SensorHandles` object bundling
the live Isaac Sim sensor handles, their USD prim paths, and the
read-side helpers (``read_imu`` / ``read_camera_rgb`` /
``read_camera_depth`` / ``read_lidar_3d_point_cloud``).  The IMU
Mars-gravity assertion and the ``local_orientation_rpy_deg`` YAML
plumbing live alongside the spawn implementation.
"""

from marslab.sensors.sensor_spawner import SensorHandles, spawn_sensors

__all__ = [
    "SensorHandles",
    "spawn_sensors",
]
