"""Ingenuity-like vehicle settings; unpublished constants are simulation choices."""

from typing import Literal

from pydantic import Field, model_validator

from marslab.config.schema.common import (
    NonEmptyString, NonNegativeFloat, PositiveFloat, PositiveInt, StrictConfigModel, Vec3,
)
from marslab.config.schema.rover import SpawnConfig

PositiveVec3 = tuple[PositiveFloat, PositiveFloat, PositiveFloat]


class DroneSimulationConfig(StrictConfigModel):
    physics_hz: PositiveInt = 500
    render_hz: PositiveInt = 60
    real_time: bool = True
    duration_seconds: NonNegativeFloat = 0.0


class ArduPilotConfig(StrictConfigModel):
    json_bind: str = "127.0.0.1"
    json_port: PositiveInt = 9002
    mavlink_port: PositiveInt = 14560
    instance: int = 0
    navigation: Literal["sim_truth", "ekf3"] = "sim_truth"
    rate_bandwidth_radps: PositiveVec3 = (10.0, 10.0, 8.0)
    attitude_p: PositiveVec3 = (4.0, 4.0, 3.0)
    rsc_setpoint: PositiveFloat = 0.7
    # A geodetic bookkeeping origin for SITL; it is not simulated Mars GNSS.
    home_latitude_deg: float = -35.363261
    home_longitude_deg: float = 149.165230
    home_altitude_m: float = 584.0
    parameter_overrides: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def transport_settings(self) -> "ArduPilotConfig":
        if self.json_port > 65535 or self.mavlink_port > 65535:
            raise ValueError("ArduPilot UDP ports must fit in 16 bits")
        if self.instance < 0 or self.rsc_setpoint > 1.0:
            raise ValueError("ArduPilot instance must be nonnegative and RSC setpoint <= 1")
        return self


class DroneActuatorConfig(StrictConfigModel):
    rotor_rpm: PositiveFloat = 2400.0
    spool_up_seconds: PositiveFloat = 1.0
    spool_down_seconds: PositiveFloat = 1.5
    max_thrust_ratio: PositiveFloat = 1.6
    max_torque_nm: PositiveVec3 = (0.35, 0.35, 0.12)
    # Grip 2018, IX: demonstration servo model, not flight servo identification.
    servo_frequency_hz: PositiveFloat = 12.0
    servo_damping_ratio: PositiveFloat = 0.85
    collective_min_deg: float = -4.5
    collective_hover_deg: float = 8.0
    collective_max_deg: float = 17.5
    cyclic_limit_deg: PositiveFloat = 10.0
    # Reduced direct-drive rotor/motor model. These are selected simulation values.
    rotor_inertia_kgm2: PositiveFloat = 0.00015
    rotor_drag_hover_nm: PositiveFloat = 0.20
    rotor_drag_per_collective_deg: PositiveFloat = 0.012
    motor_speed_kp: PositiveFloat = 0.015
    motor_speed_ki: NonNegativeFloat = 0.025
    motor_max_torque_nm: PositiveFloat = 0.7
    collective_feedforward: bool = True

    @model_validator(mode="after")
    def ordered_collective(self) -> "DroneActuatorConfig":
        if not self.collective_min_deg < self.collective_hover_deg < self.collective_max_deg:
            raise ValueError("drone collective limits must bracket collective_hover_deg")
        return self


class DroneSensorConfig(StrictConfigModel):
    seed: int = 42
    imu_hz: PositiveInt = 500
    imu_acceleration_filter_size: PositiveInt = 7
    imu_angular_velocity_filter_size: PositiveInt = 4
    imu_accel_sigma: NonNegativeFloat = 0.03
    imu_gyro_sigma: NonNegativeFloat = 0.002
    imu_accel_bias: Vec3 = (0.004, -0.003, 0.006)
    imu_gyro_bias: Vec3 = (0.0002, -0.0001, 0.00015)
    nav_hz: PositiveInt = 30
    nav_position: Vec3 = (0.0, 0.0, -0.20)
    nav_resolution: tuple[PositiveInt, PositiveInt] = (640, 480)
    nav_central_pixel_scale_rad: PositiveFloat = 0.00357
    rte_hz: PositiveInt = 1
    rte_position: Vec3 = (0.05, 0.0, -0.20)
    rte_resolution: tuple[PositiveInt, PositiveInt] = (4208, 3120)
    rte_angle_below_horizon_deg: PositiveFloat = Field(default=45.0, lt=90.0)
    rte_horizontal_fov_deg: PositiveFloat = Field(default=102.0, lt=180.0)
    rte_vertical_fov_deg: PositiveFloat = Field(default=82.0, lt=180.0)
    range_hz: PositiveInt = 50
    range_position: Vec3 = (0.0, 0.0, -0.21)
    range_min_m: PositiveFloat = 0.05
    range_max_m: PositiveFloat = 40.0
    range_sigma_m: NonNegativeFloat = 0.02
    range_beam_divergence_rad: PositiveFloat = 0.004

    @model_validator(mode="after")
    def range_limits(self) -> "DroneSensorConfig":
        if self.range_max_m <= self.range_min_m:
            raise ValueError("drone range_max_m must exceed range_min_m")
        return self


class DroneFlightConfig(StrictConfigModel):
    takeoff_height_m: PositiveFloat = 3.0
    takeoff_speed_mps: PositiveFloat = 1.0
    landing_speed_mps: PositiveFloat = 0.3


class DroneConfig(StrictConfigModel):
    # Empty selects NVIDIA's installed asset root; URLs remain URLs in the loader.
    asset_url: str = ""
    asset_scale: NonNegativeFloat = 0.0
    prim_path: NonEmptyString = "/World/Ingenuity"
    spawn: SpawnConfig = Field(default_factory=lambda: SpawnConfig(
        mode="dem_center", xy=(0.0, 0.0), z_offset=0.328,
        orientation_rpy=(0.0, 0.0, 0.0),
    ))
    mass_kg: PositiveFloat = 1.8
    inertia_kgm2: PositiveVec3 = (0.025, 0.025, 0.045)
    foot_z_m: float = -0.30
    foot_radius_m: PositiveFloat = 0.025
    foot_xy_m: PositiveFloat = 0.17
    publish_ground_truth: bool = False
    flight_backend: Literal["ardupilot", "external_wrench"] = "ardupilot"
    ardupilot: ArduPilotConfig = Field(default_factory=ArduPilotConfig)
    simulation: DroneSimulationConfig = Field(default_factory=DroneSimulationConfig)
    actuators: DroneActuatorConfig = Field(default_factory=DroneActuatorConfig)
    sensors: DroneSensorConfig = Field(default_factory=DroneSensorConfig)
    flight: DroneFlightConfig = Field(default_factory=DroneFlightConfig)

    @model_validator(mode="after")
    def compatible_rates(self) -> "DroneConfig":
        sim, sensors = self.simulation, self.sensors
        if any(hz > sim.physics_hz for hz in (sensors.imu_hz, sensors.range_hz, sim.render_hz)):
            raise ValueError("drone physics_hz must cover IMU, range, and rendering rates")
        if any(sim.render_hz % hz for hz in (sensors.nav_hz, sensors.rte_hz)):
            raise ValueError("drone render_hz must be a multiple of both camera rates")
        if any(sim.physics_hz % hz for hz in (sensors.imu_hz, sensors.range_hz)):
            raise ValueError("drone physics_hz must be a multiple of IMU and range rates")
        return self
