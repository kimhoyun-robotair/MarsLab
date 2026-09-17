"""Define validated camera, IMU sampling, and 2-D/3-D LiDAR settings.
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
    min_distance_m: NonNegativeFloat
    max_distance_m: PositiveFloat
    noise_mean: FiniteFloat
    noise_sigma: NonNegativeFloat

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
    horizontal_fov_deg: PositiveFloat | None = Field(default=None, lt=180.0)
    clipping_range: tuple[PositiveFloat, PositiveFloat]
    depth_sensor: DepthSensorConfig

    @model_validator(mode="after")
    def check_clipping_range(self) -> "CameraConfig":
        if self.clipping_range[1] <= self.clipping_range[0]:
            raise ValueError("camera clipping far plane must exceed near plane")
        return self


class Lidar2DConfig(StrictConfigModel):
    local_translation: Vec3
    local_orientation_rpy_deg: Vec3
    range_min: PositiveFloat
    range_max: PositiveFloat
    horizontal_fov_deg: PositiveFloat = Field(le=360.0)
    rotation_rate_hz: PositiveFloat

    @model_validator(mode="after")
    def check_range(self) -> "Lidar2DConfig":
        if self.range_max <= self.range_min:
            raise ValueError("lidar_2d range_max must exceed range_min")
        if not self.rotation_rate_hz.is_integer():
            raise ValueError("OmniLidar rotation_rate_hz must be an integer number of Hz")
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
        if not self.rotation_rate_hz.is_integer():
            raise ValueError("OmniLidar rotation_rate_hz must be an integer number of Hz")
        if (self.profile_name is None) == (self.profile_json_path is None):
            raise ValueError("lidar requires exactly one profile source")
        if self.profile_json_path is not None:
            raise ValueError(
                "lidar_3d.profile_json_path is unsupported by Isaac 5.1 OmniLidar; "
                "select an installed USD sensor model with profile_name and variant"
            )
        if self.usd_profile is not None:
            raise ValueError(
                "lidar_3d.usd_profile is unsupported; profile_name selects the USD sensor model"
            )
        return self


class IMUConfig(StrictConfigModel):
    sampling_frequency_hz: PositiveInt
    local_translation: Vec3
    local_orientation_rpy_deg: Vec3
    sigma_lin_acc: NonNegativeFloat
    sigma_ang_vel: NonNegativeFloat


class SensorsConfig(StrictConfigModel):
    seed: int | None = Field(ge=0)
    camera: CameraConfig
    lidar_2d: Lidar2DConfig
    lidar_3d: Lidar3DConfig
    imu: IMUConfig


__all__ = [
    "CameraConfig",
    "DepthSensorConfig",
    "IMUConfig",
    "Lidar2DConfig",
    "Lidar3DConfig",
    "SensorsConfig",
]
