"""Define validated camera, IMU sampling, and 3-D LiDAR settings.
Acquisition is mandatory and separate from ROS transport.
Isaac handles are created only by runtime spawners."""

from pathlib import Path

from pydantic import Field, model_validator

from marslab.config.schema.common import (
    FiniteFloat,
    NonEmptyString,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    StrictConfigModel,
    Vec3,
)


class DepthSensorConfig(StrictConfigModel):
    enabled: bool
    baseline_mm: PositiveFloat
    min_distance_m: NonNegativeFloat
    max_distance_m: PositiveFloat
    noise_mean: FiniteFloat
    noise_sigma: NonNegativeFloat
    confidence_threshold: FiniteFloat = Field(ge=0.0, le=1.0)
    max_disparity_pixel: PositiveFloat

    @model_validator(mode="after")
    def check_distance_range(self) -> "DepthSensorConfig":
        if self.max_distance_m <= self.min_distance_m:
            raise ValueError("depth max_distance_m must exceed min_distance_m")
        return self


class CameraConfig(StrictConfigModel):
    local_translation: Vec3
    local_orientation_rpy_deg: Vec3
    resolution: tuple[PositiveInt, PositiveInt]
    focal_length_mm: PositiveFloat
    clipping_range: tuple[PositiveFloat, PositiveFloat]
    depth_sensor: DepthSensorConfig

    @model_validator(mode="after")
    def check_clipping_range(self) -> "CameraConfig":
        if self.clipping_range[1] <= self.clipping_range[0]:
            raise ValueError("camera clipping far plane must exceed near plane")
        return self


class Lidar3DConfig(StrictConfigModel):
    local_translation: Vec3
    local_orientation_rpy_deg: Vec3
    range_min: PositiveFloat
    range_max: PositiveFloat
    horizontal_fov_deg: PositiveFloat = Field(le=360.0)
    rotation_rate_hz: PositiveFloat
    profile_name: NonEmptyString | None
    profile_json_path: Path | None
    usd_profile: NonEmptyString | None
    variant: NonEmptyString | None = None
    vertical_fov_deg: PositiveFloat = Field(le=180.0)

    @model_validator(mode="after")
    def check_range_and_profile(self) -> "Lidar3DConfig":
        if self.range_max <= self.range_min:
            raise ValueError("lidar range_max must exceed range_min")
        if (self.profile_name is None) == (self.profile_json_path is None):
            raise ValueError("lidar requires exactly one profile source")
        return self


class IMUConfig(StrictConfigModel):
    sampling_frequency_hz: PositiveInt
    local_translation: Vec3
    local_orientation_rpy_deg: Vec3
    sigma_lin_acc: NonNegativeFloat
    sigma_ang_vel: NonNegativeFloat


class SensorsConfig(StrictConfigModel):
    seed: int | None
    camera: CameraConfig
    lidar_3d: Lidar3DConfig
    imu: IMUConfig


__all__ = [
    "CameraConfig",
    "DepthSensorConfig",
    "IMUConfig",
    "Lidar3DConfig",
    "SensorsConfig",
]
