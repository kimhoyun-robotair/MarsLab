"""Define validated mission cameras, IMU, and optional LiDAR settings.
Acquisition is separate from ROS transport.
Isaac handles are created only by runtime spawners."""

from pathlib import Path
from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

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
    # A sibling rigid link's USD/URDF name; None selects the chassis link.
    parent_link: Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")] | None = (
        None
    )
    # An existing USD Camera, relative to parent_link or absolute below it.
    # Authored pose is preserved and checked against local_* before acquisition.
    prim_path: NonEmptyString | None = None
    # Relative to the selected parent link. Orientation describes a camera mount
    # with +X forward/+Y left/+Z up, not USD's +X right/+Y up/-Z forward axes.
    local_translation: Vec3
    local_orientation_rpy_deg: Vec3
    resolution: tuple[PositiveInt, PositiveInt]
    focal_length_mm: PositiveFloat
    horizontal_fov_deg: PositiveFloat | None = Field(default=None, lt=180.0)
    clipping_range: tuple[PositiveFloat, PositiveFloat]
    depth_sensor: DepthSensorConfig
    # Synthetic renderer depth is a simulation aid, not a flight camera output.
    depth_output: bool = True

    @model_validator(mode="after")
    def check_clipping_range(self) -> "CameraConfig":
        if self.clipping_range[1] <= self.clipping_range[0]:
            raise ValueError("camera clipping far plane must exceed near plane")
        if not self.depth_output and self.depth_sensor.enabled:
            raise ValueError("depth_sensor noise requires depth_output=true")
        if self.prim_path is not None:
            path = self.prim_path.removeprefix("/")
            if not path or any(
                not part.isidentifier() or not part.isascii() for part in path.split("/")
            ):
                raise ValueError("camera prim_path must contain valid USD prim names")
        return self


class NamedCameraConfig(CameraConfig):
    name: Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]


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
    cameras: list[NamedCameraConfig] = Field(default_factory=list)
    lidar_2d: Lidar2DConfig | None = None
    lidar_3d: Lidar3DConfig | None = None
    imu: IMUConfig

    @model_validator(mode="after")
    def check_camera_identities(self) -> "SensorsConfig":
        names = [camera.name for camera in self.cameras]
        if "primary" in names or len(names) != len(set(names)):
            raise ValueError("additional camera names must be unique and cannot be 'primary'")
        authored_paths = [
            (None if camera.prim_path.startswith("/") else camera.parent_link, camera.prim_path)
            for camera in [self.camera, *self.cameras]
            if camera.prim_path is not None
        ]
        if len(authored_paths) != len(set(authored_paths)):
            raise ValueError("camera prim_path values must be unique")
        return self


__all__ = [
    "CameraConfig",
    "DepthSensorConfig",
    "IMUConfig",
    "Lidar2DConfig",
    "Lidar3DConfig",
    "NamedCameraConfig",
    "SensorsConfig",
]
