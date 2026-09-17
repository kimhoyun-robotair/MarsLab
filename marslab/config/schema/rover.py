"""Define validated rover spawn, physics, control, and odometry fields.
The model delegates sensor and ROS subtrees to domain schemas.
Strictness prevents runtime configuration drift after parsing."""

from math import atan, pi
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
    z_offset: NonNegativeFloat
    orientation_rpy: Vec3


class ChassisConfig(StrictConfigModel):
    rigid_body_prim_name: NonEmptyString


class WheelsConfig(StrictConfigModel):
    link_names: tuple[NonEmptyString, ...] = Field(min_length=1)
    friction_static: FiniteFloat = Field(ge=0.0, le=2.0)
    friction_dynamic: FiniteFloat = Field(ge=0.0, le=2.0)
    restitution: FiniteFloat = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def check_friction_ordering(self) -> "WheelsConfig":
        if len(set(self.link_names)) != len(self.link_names):
            raise ValueError("wheel link_names must not contain duplicates")
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
    steering_axle_offset: FiniteFloat = 0.0
    track_steer: PositiveFloat
    track_middle: PositiveFloat
    max_linear_velocity: PositiveFloat
    max_angular_velocity: PositiveFloat
    command_timeout: PositiveFloat = 0.5
    drive_joint_names: tuple[NonEmptyString, ...] = Field(min_length=6, max_length=6)
    steer_joint_names: tuple[NonEmptyString, ...] = Field(min_length=4, max_length=4)
    drive_damping: PositiveFloat
    drive_max_force: PositiveFloat
    brake_stiffness: NonNegativeFloat = 50000.0
    steer_stiffness: PositiveFloat
    steer_damping: PositiveFloat
    steer_max_force: PositiveFloat
    drive_type: Literal["acceleration", "force"]
    negate_steer: bool
    max_wheel_accel_rate: PositiveFloat
    max_steer_angle: PositiveFloat = Field(lt=pi / 2.0)
    steering_alignment_tolerance: PositiveFloat = 0.02
    steering_stop_speed: PositiveFloat = 0.05
    steer_ramp_rate: PositiveFloat
    decel_multiplier: PositiveFloat
    debug_logging: bool

    @model_validator(mode="after")
    def check_steering_geometry(self) -> "ControlConfig":
        half_wheelbase = self.wheelbase / 2.0
        if abs(self.steering_axle_offset) >= half_wheelbase:
            raise ValueError("steering_axle_offset must lie within half the wheelbase")
        pivot_angle = atan(
            (half_wheelbase + abs(self.steering_axle_offset)) / (self.track_steer / 2.0)
        )
        if self.max_steer_angle < pivot_angle:
            raise ValueError(
                "max_steer_angle cannot support pivot turns with the configured geometry: "
                f"requires at least {pivot_angle:.6f} rad, got {self.max_steer_angle:.6f} rad"
            )
        if self.steering_alignment_tolerance >= self.max_steer_angle:
            raise ValueError("steering_alignment_tolerance must be below max_steer_angle")
        return self

    @model_validator(mode="after")
    def check_joint_names(self) -> "ControlConfig":
        joint_groups = (
            ("drive_joint_names", self.drive_joint_names),
            ("steer_joint_names", self.steer_joint_names),
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
    left_wheel_joints: tuple[NonEmptyString, ...] = Field(min_length=3, max_length=3)
    right_wheel_joints: tuple[NonEmptyString, ...] = Field(min_length=3, max_length=3)
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
        joints = (*self.left_wheel_joints, *self.right_wheel_joints)
        if len(set(joints)) != len(joints):
            raise ValueError("wheel odometry banks must contain six distinct drive joints")
        return self


class RoverConfig(StrictConfigModel):
    usd_path: Path
    urdf_source_path: Path
    prim_path: NonEmptyString
    spawn: SpawnConfig
    angular_damping: NonNegativeFloat
    linear_damping: NonNegativeFloat
    chassis: ChassisConfig
    wheels: WheelsConfig
    suspension: SuspensionConfig
    ros2: Ros2BridgeConfig
    sensors: SensorsConfig
    control: ControlConfig
    wheel_odometry: WheelOdometryConfig

    @model_validator(mode="after")
    def check_joint_ownership(self) -> "RoverConfig":
        control_names = set((*self.control.drive_joint_names, *self.control.steer_joint_names))
        suspension_names = set(
            (*self.suspension.rocker_joint_names, *self.suspension.bogie_joint_names)
        )
        if control_names & suspension_names:
            raise ValueError("drive, steer, and suspension joint names must not overlap")
        encoder_order = (
            *self.wheel_odometry.left_wheel_joints,
            *self.wheel_odometry.right_wheel_joints,
        )
        if encoder_order != self.control.drive_joint_names:
            raise ValueError(
                "wheel odometry banks must match control.drive_joint_names in "
                "LF, LM, LR, RF, RM, RR order"
            )
        return self


__all__ = [
    "ChassisConfig",
    "ControlConfig",
    "RoverConfig",
    "SpawnConfig",
    "SuspensionConfig",
    "WheelOdometryConfig",
    "WheelsConfig",
]
