"""Build sensor TF frame records relative to each configured rigid mount.
The transformation data stays pure and offline-testable.
Broadcast conversion is kept separate from sensor creation."""

from __future__ import annotations

from marslab.config.schema.rover_sensors import CameraConfig, SensorsConfig

SensorFrame = tuple[str, list[float], list[float]] | tuple[str, list[float], list[float], str]
SensorFrames = list[SensorFrame]


def _camera_frame(child_frame: str, camera: CameraConfig) -> SensorFrame:
    frame = (
        child_frame,
        list(camera.local_translation),
        list(camera.local_orientation_rpy_deg),
    )
    return (*frame, camera.parent_link) if camera.parent_link is not None else frame


def build_sensor_frames(sensors_cfg: SensorsConfig) -> SensorFrames:
    """Construct the static-TF frame list from the rover sensor block."""
    frames: SensorFrames = [_camera_frame("camera_link", sensors_cfg.camera)]
    for name, lidar in (
        ("lidar_2d_link", sensors_cfg.lidar_2d),
        ("lidar_link", sensors_cfg.lidar_3d),
    ):
        if lidar is not None:
            frames.append(
                (name, list(lidar.local_translation), list(lidar.local_orientation_rpy_deg))
            )
    frames.append(
        (
            "imu_link",
            list(sensors_cfg.imu.local_translation),
            list(sensors_cfg.imu.local_orientation_rpy_deg),
        )
    )
    frames.extend(
        _camera_frame(f"{camera.name}_camera_link", camera) for camera in sensors_cfg.cameras
    )
    return frames


__all__ = ["SensorFrame", "SensorFrames", "build_sensor_frames"]
