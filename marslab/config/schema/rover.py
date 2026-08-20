"""Define validated rover spawn, physics, control, and odometry fields.
The model delegates sensor and ROS subtrees to domain schemas.
Strictness prevents runtime configuration drift after parsing."""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from marslab.config.schema.common import (
    FiniteFloat,
    NonEmptyString,
    NonNegativeFloat,
    PositiveFloat,
    StrictConfigModel,
    Vec2,
    Vec3,
)
from marslab.config.schema.rover_ros2 import Ros2BridgeConfig
from marslab.config.schema.rover_sensors import SensorsConfig


class SpawnConfig(StrictConfigModel):
    mode: Literal["dem_center", "dem_relative", "absolute"]
    xy: Vec2
    z_offset: NonNegativeFloat | None = None
    orientation_rpy: Vec3


class ChassisConfig(StrictConfigModel):
    mass: PositiveFloat = Field(le=5000.0)
    inertia_xx: PositiveFloat
    inertia_yy: PositiveFloat
    inertia_zz: PositiveFloat


class WheelsConfig(StrictConfigModel):
    mass: PositiveFloat = Field(le=100.0)
    inertia_spin: PositiveFloat
    inertia_transverse: PositiveFloat
    friction_static: FiniteFloat = Field(ge=0.0, le=2.0)
    friction_dynamic: FiniteFloat = Field(ge=0.0, le=2.0)
    restitution: FiniteFloat = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def check_friction_ordering(self) -> "WheelsConfig":
        if self.friction_static < self.friction_dynamic:
            raise ValueError("static friction must be at least dynamic friction")
        return self


class SuspensionConfig(StrictConfigModel):
    rocker_damping: NonNegativeFloat
    bogie_damping: NonNegativeFloat
    rocker_joint_names: tuple[NonEmptyString, ...] = Field(min_length=1)
    bogie_joint_names: tuple[NonEmptyString, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def check_joint_names(self) -> "SuspensionConfig":
        rocker_names = set(self.rocker_joint_names)
        bogie_names = set(self.bogie_joint_names)
        if len(rocker_names) != len(self.rocker_joint_names):
            raise ValueError("rocker_joint_names must not contain duplicates")
        if len(bogie_names) != len(self.bogie_joint_names):
            raise ValueError("bogie_joint_names must not contain duplicates")
        if rocker_names & bogie_names:
            raise ValueError("rocker_joint_names and bogie_joint_names must not overlap")
        return self


class ControlConfig(StrictConfigModel):
    wheel_radius: PositiveFloat
    wheelbase: PositiveFloat
    track_steer: PositiveFloat
    track_middle: PositiveFloat
    max_linear_velocity: PositiveFloat
    max_angular_velocity: PositiveFloat
    drive_joint_names: tuple[NonEmptyString, ...] = Field(min_length=1)
    steer_joint_names: tuple[NonEmptyString, ...] = Field(min_length=1)
    suspension_joint_names: tuple[NonEmptyString, ...] = Field(min_length=1)
    suspension_damping: NonNegativeFloat
    drive_damping: PositiveFloat
    drive_max_force: PositiveFloat
    steer_stiffness: PositiveFloat
    steer_damping: PositiveFloat
    steer_max_force: PositiveFloat
    drive_type: Literal["acceleration", "force"]
    negate_steer: bool
    max_wheel_accel_rate: PositiveFloat
    max_steer_angle: PositiveFloat
    steer_ramp_rate: PositiveFloat
    decel_multiplier: PositiveFloat
    debug_logging: bool

    @model_validator(mode="after")
    def check_joint_names(self) -> "ControlConfig":
        joint_groups = (
            ("drive_joint_names", self.drive_joint_names),
            ("steer_joint_names", self.steer_joint_names),
            ("suspension_joint_names", self.suspension_joint_names),
        )
        seen_names: set[str] = set()
        for group_name, joint_names in joint_groups:
            group_names = set(joint_names)
            if len(group_names) != len(joint_names):
                raise ValueError(f"{group_name} must not contain duplicates")
            if seen_names & group_names:
                raise ValueError("drive, steer, and suspension joint names must not overlap")
            seen_names.update(group_names)
        return self


class WheelOdometryConfig(StrictConfigModel):
    enabled: bool
    left_wheel_joints: tuple[NonEmptyString, ...] = Field(min_length=1)
    right_wheel_joints: tuple[NonEmptyString, ...] = Field(min_length=1)
    track_width: PositiveFloat
    slip_left: FiniteFloat
    slip_right: FiniteFloat
    sigma_omega: NonNegativeFloat
    pose_diag: (
        tuple[
            NonNegativeFloat,
            NonNegativeFloat,
            NonNegativeFloat,
            NonNegativeFloat,
            NonNegativeFloat,
            NonNegativeFloat,
        ]
        | None
    ) = None
    twist_diag: (
        tuple[
            NonNegativeFloat,
            NonNegativeFloat,
            NonNegativeFloat,
            NonNegativeFloat,
            NonNegativeFloat,
            NonNegativeFloat,
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def check_wheel_banks(self) -> "WheelOdometryConfig":
        if len(self.left_wheel_joints) != len(self.right_wheel_joints):
            raise ValueError("wheel odometry banks must have matching lengths")
        return self


class RoverConfig(StrictConfigModel):
    usd_path: Path
    urdf_source_path: Path
    prim_path: NonEmptyString
    spawn: SpawnConfig
    com_offset: Vec3
    angular_damping: NonNegativeFloat
    linear_damping: NonNegativeFloat
    chassis: ChassisConfig
    wheels: WheelsConfig
    suspension: SuspensionConfig
    ros2: Ros2BridgeConfig
    sensors: SensorsConfig
    control: ControlConfig
    wheel_odometry: WheelOdometryConfig


__all__ = [
    "ChassisConfig",
    "ControlConfig",
    "RoverConfig",
    "SpawnConfig",
    "SuspensionConfig",
    "WheelOdometryConfig",
    "WheelsConfig",
]
