"""Build chassis-relative sensor TF frame records.
The transformation data stays pure and offline-testable.
Broadcast conversion is kept separate from sensor creation."""

from __future__ import annotations

from marslab.config.schema.rover_sensors import SensorsConfig

SensorFrame = tuple[str, list[float], list[float]]
SensorFrames = list[SensorFrame]


def build_sensor_frames(sensors_cfg: SensorsConfig) -> SensorFrames:
    """Construct the static-TF frame list from the rover sensor block."""
    return [
        (
            "camera_link",
            list(sensors_cfg.camera.local_translation),
            list(sensors_cfg.camera.local_orientation_rpy_deg),
        ),
        (
            "lidar_link",
            list(sensors_cfg.lidar_3d.local_translation),
            list(sensors_cfg.lidar_3d.local_orientation_rpy_deg),
        ),
        (
            "imu_link",
            list(sensors_cfg.imu.local_translation),
            list(sensors_cfg.imu.local_orientation_rpy_deg),
        ),
    ]


__all__ = ["SensorFrame", "SensorFrames", "build_sensor_frames"]
