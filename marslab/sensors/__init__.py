"""Sensor spawn facade for MarsLab (Stage-3 unified).

Reviewer-2 item #16 (2026-04-24): Path A (``attach_camera`` / ``attach_imu``
/ ``attach_lidar`` / ``load_and_attach_sensor``) was retired.  The single
supported entry point is :func:`marslab.sensors.sensor_spawner.spawn_sensors`,
which returns a :class:`SensorHandles` object bundling the live Isaac
Sim sensor handles, their USD prim paths, and the read-side helpers
(``read_imu`` / ``read_camera_rgb`` / ``read_camera_depth`` /
``read_lidar_3d_point_cloud``).  The IMU Mars-gravity assertion (THE
critical test, Batch 1 item #6) and the ``offset_orientation`` / rpy
YAML plumbing moved into ``sensor_spawner.py`` as part of this
consolidation.

The legacy Path A modules (``camera.py``, ``imu.py``, ``lidar.py``) are
kept on disk but carry a deprecation notice and are no longer exported
here.  They will be removed by the user via ``git rm`` once the audit
branch lands; importing them directly now raises nothing — the files
continue to compile so any straggler import breaks loudly rather than
silently, but no in-tree caller depends on them.
"""

from marslab.sensors.sensor_spawner import SensorHandles, spawn_sensors

__all__ = [
    "SensorHandles",
    "spawn_sensors",
]
