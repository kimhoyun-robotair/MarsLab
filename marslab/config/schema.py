"""Pydantic v2 configuration schema for MarsLab.

All Mars environment, terrain, robot, rendering, and benchmark parameters
are defined here. Every value has a physically meaningful range constraint.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class MarsEnvConfig(BaseModel):
    """Mars environmental parameters."""

    gravity: float = Field(default=3.72, ge=3.0, le=4.0, description="Surface gravity in m/s^2")
    atmo_pressure: float = Field(
        default=610, ge=400, le=1200, description="Atmospheric pressure in Pa"
    )
    atmo_density: float = Field(
        default=0.020, ge=0.005, le=0.05, description="Atmospheric density in kg/m^3"
    )
    dust_optical_depth: float = Field(
        default=0.3, ge=0.05, le=6.0, description="Dust optical depth (tau)"
    )
    solar_constant_mean: float = Field(
        default=589, ge=480, le=730, description="Solar constant in W/m^2 at 1.52 AU"
    )
    surface_albedo_range: tuple[float, float] = Field(
        default=(0.10, 0.40), description="Surface albedo min/max"
    )
    surface_temp_mean: float = Field(
        default=-60, ge=-140, le=30, description="Mean surface temperature in Celsius"
    )
    sol_duration_seconds: int = Field(
        default=88642, ge=80000, le=95000, description="Sol duration in seconds"
    )
    dust_opacity_range: tuple[float, float] = Field(
        default=(0.5, 2.0), description="Tau range for domain randomization"
    )
    sun_azimuth_deg: float = Field(
        default=180.0, ge=0.0, le=360.0, description="Sun azimuth in degrees (0=N, 90=E, 180=S)"
    )
    sun_elevation_deg: float = Field(
        default=45.0, ge=0.0, le=90.0, description="Sun elevation above horizon in degrees"
    )
    seed: int = Field(default=42, ge=0)

    @model_validator(mode="after")
    def check_ranges(self) -> "MarsEnvConfig":
        """Validate that range tuples are ordered (min < max)."""
        if self.surface_albedo_range[0] >= self.surface_albedo_range[1]:
            raise ValueError(
                f"surface_albedo_range must be (min, max) with min < max, "
                f"got {self.surface_albedo_range}"
            )
        if self.dust_opacity_range[0] >= self.dust_opacity_range[1]:
            raise ValueError(
                f"dust_opacity_range must be (min, max) with min < max, "
                f"got {self.dust_opacity_range}"
            )
        return self


class DemCropConfig(BaseModel):
    """Row/column crop window into a pre-loaded HiRISE DEM.

    Added for Wk2 #1-#3 (2026-04-14) so scenario YAMLs can carve
    distinct regions (plain, rim, delta) out of the shared Jezero DEM
    without committing multiple GeoTIFFs to the repo. All values are
    pixel indices into the source elevation array.
    """

    row: int = Field(ge=0, description="Top-left row index of the crop window")
    col: int = Field(ge=0, description="Top-left column index of the crop window")
    height: int = Field(ge=1, description="Crop window height in pixels")
    width: int = Field(ge=1, description="Crop window width in pixels")


class TerrainConfig(BaseModel):
    """Terrain generation parameters."""

    source: Literal["hirise", "procedural"] = Field(default="hirise")
    scenario_name: str | None = Field(
        default=None,
        description="Human-readable scenario identifier (e.g. 'basic_mars'). "
        "Propagated to visualizations and LOG entries; purely informational.",
    )
    dem_path: str | None = Field(default=None, description="Path to HiRISE DEM GeoTIFF")
    converted_dem_dir: str | None = Field(
        default=None,
        description="Directory containing pre-converted elevation.npy and metadata.json",
    )
    dem_crop: DemCropConfig | None = Field(
        default=None,
        description="Optional sub-window crop into the loaded DEM. When set, "
        "scenario builders use only this region instead of the full DEM.",
    )
    rock_sfd_k: float = Field(
        default=0.05, ge=0, le=0.15, description="Golombek CFA fraction (0=no rocks)"
    )
    rock_diameter_range: tuple[float, float] = Field(
        default=(0.20, 3.0), description="Rock diameter range in meters (< 20cm as texture)"
    )
    semantic_classes: list[str] = Field(
        default=["soil", "bedrock", "sand", "big_rock"],
        description="AI4Mars-compatible terrain classes",
    )
    terrain_size: tuple[int, int] = Field(
        default=(256, 256), description="Procedural terrain size (rows, cols) in pixels"
    )
    terrain_resolution: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Meters per pixel for procedural terrain"
    )
    procedural_preset: str | None = Field(
        default=None, description="Procedural preset: flat, crater, hills"
    )
    texture_dir: str | None = Field(
        default=None, description="Path to PBR texture directory (albedo.png, normal.png, etc.)"
    )
    rock_color: tuple[float, float, float] = Field(
        default=(0.42, 0.28, 0.20), description="Mars rock base color RGB (reddish-brown)"
    )
    rock_roughness: float = Field(
        default=0.92, ge=0.0, le=1.0, description="Rock surface roughness"
    )
    rock_mesh_dir: str | None = Field(
        default=None, description="Rock OBJ mesh directory (null = Sphere fallback)"
    )
    rock_texture_dir: str | None = Field(
        default=None, description="Rock PBR texture directory (null = color only)"
    )
    uv_scale: float = Field(default=16.0, ge=1.0, description="Texture UV tiling factor")
    seed: int = Field(default=42, ge=0)

    @model_validator(mode="after")
    def check_terrain(self) -> "TerrainConfig":
        """Validate conditional requirements and range ordering."""
        if self.source == "hirise" and self.dem_path is None and self.converted_dem_dir is None:
            raise ValueError("dem_path or converted_dem_dir is required when source is 'hirise'")
        if self.source == "procedural" and self.procedural_preset is None:
            raise ValueError("procedural_preset is required when source is 'procedural'")
        if self.rock_diameter_range[0] >= self.rock_diameter_range[1]:
            raise ValueError(
                f"rock_diameter_range must be (min, max) with min < max, "
                f"got {self.rock_diameter_range}"
            )
        return self


class OdometryCovarianceConfig(BaseModel):
    """Diagonal covariance values for the nav_msgs/Odometry publisher.

    ROS2 Odometry carries two 6x6 covariance matrices (pose + twist,
    each laid out in xyz + rpy order). For v1.0 we only populate the
    diagonal — off-diagonal correlations are set to zero by the
    publisher. These variances are placeholders sized from typical
    wheel-encoder / IMU-fusion reference setups; real numbers come
    from the SLAM/Nav2 experiments in Wk3+.

    Wk2 #6 (2026-04-14, task #17) introduced this block so G5 is
    honored — no numeric covariance lives in Python.
    """

    pose_diag: list[float] = Field(
        default=[1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2],
        min_length=6,
        max_length=6,
        description=(
            "Diagonal of the 6x6 pose covariance matrix in (x, y, z, "
            "roll, pitch, yaw) order. z / roll / pitch entries are "
            "large (1e6) because a planar skid-steer rover has no "
            "direct estimate of them — SLAM/Nav2 should ignore those "
            "axes entirely via the inflated variance."
        ),
    )
    twist_diag: list[float] = Field(
        default=[1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2],
        min_length=6,
        max_length=6,
        description=(
            "Diagonal of the 6x6 twist covariance matrix in (vx, vy, "
            "vz, wx, wy, wz) order. Same rationale as pose_diag: the "
            "non-planar components are masked with 1e6."
        ),
    )

    @model_validator(mode="after")
    def check_non_negative(self) -> "OdometryCovarianceConfig":
        """Variance must be non-negative for every diagonal entry."""
        for name, values in (
            ("pose_diag", self.pose_diag),
            ("twist_diag", self.twist_diag),
        ):
            for i, v in enumerate(values):
                if v < 0.0:
                    raise ValueError(f"{name}[{i}] must be >= 0, got {v}")
        return self


class SkidSteerDriveConfig(BaseModel):
    """Skid-steer drive geometry and actuation limits.

    Used by ``marslab.ros2_bridge.cmd_vel_subscriber`` to convert
    ``geometry_msgs/Twist`` into per-wheel angular velocities. Wk2 #4
    (2026-04-14) added these fields so G5 (no hardcoded constants) is
    honored: wheel radius, track width, and speed clamps all flow from
    YAML rather than being embedded in Python.

    Wk2 #6 (2026-04-14, task #17) added the ``odom_covariance`` field
    so the ``nav_msgs/Odometry`` publisher can pull its placeholder
    covariance matrices from the same block. The odometry publisher
    itself reads the same wheel-joint names declared here, so the FK
    pipeline and the IK pipeline always agree on the active wheel set.
    """

    wheel_radius: float = Field(default=0.15, gt=0.0, description="Wheel radius in meters")
    track_width: float = Field(
        default=0.70,
        gt=0.0,
        description="Distance between left and right wheel centers in meters",
    )
    max_linear_vel: float = Field(
        default=1.0,
        gt=0.0,
        description="Upper bound on commanded linear velocity in m/s",
    )
    max_angular_vel: float = Field(
        default=1.5,
        gt=0.0,
        description="Upper bound on commanded yaw rate in rad/s",
    )
    cmd_vel_timeout_s: float = Field(
        default=0.5,
        gt=0.0,
        description=(
            "Safety watchdog timeout in seconds. If no /cmd_vel message has "
            "arrived within this window, the subscriber zeros every wheel "
            "velocity so the rover does not keep cruising at the last "
            "commanded velocity when the Nav2 controller_server drops. "
            "Wk2 #7b / task #18."
        ),
    )
    left_wheel_joints: list[str] = Field(
        default=["joint_fl", "joint_ml", "joint_rl"],
        description="Articulation joint names for the left wheel bank",
    )
    right_wheel_joints: list[str] = Field(
        default=["joint_fr", "joint_mr", "joint_rr"],
        description="Articulation joint names for the right wheel bank",
    )
    odom_covariance: OdometryCovarianceConfig = Field(
        default_factory=OdometryCovarianceConfig,
        description=(
            "Diagonal placeholder covariance for the nav_msgs/Odometry "
            "publisher (Wk2 #6 / task #17)."
        ),
    )

    @model_validator(mode="after")
    def check_wheel_joints(self) -> "SkidSteerDriveConfig":
        """Left and right banks must have the same non-zero joint count."""
        if not self.left_wheel_joints or not self.right_wheel_joints:
            # Keep this error message split across two source lines for
            # readability. black would otherwise collapse it into a single
            # 104-char physical line via implicit string concatenation,
            # which is parser-valid but visually confusing.
            # fmt: off
            raise ValueError(
                "left_wheel_joints and right_wheel_joints must each list "
                "at least one joint name"
            )
            # fmt: on
        if len(self.left_wheel_joints) != len(self.right_wheel_joints):
            raise ValueError(
                f"left_wheel_joints ({len(self.left_wheel_joints)}) and "
                f"right_wheel_joints ({len(self.right_wheel_joints)}) must "
                f"have matching lengths for a symmetric skid-steer rover"
            )
        return self


class RobotConfig(BaseModel):
    """Single robot configuration."""

    type: str = Field(description="Robot type identifier (e.g., 'rover', 'quadruped')")
    urdf_path: str | None = Field(default=None, description="Path to custom URDF file")
    usd_asset_path: str | None = Field(default=None, description="Path to built-in USD asset")
    spawn_position: list[float] = Field(
        default=[0.0, 0.0, 0.5], min_length=3, max_length=3, description="[x, y, z] in meters"
    )
    sensor_config_paths: list[str] = Field(default_factory=list)
    drive: SkidSteerDriveConfig | None = Field(
        default=None,
        description=(
            "Skid-steer drive parameters for cmd_vel → wheel control. Required "
            "for rovers that are teleoperable via /cmd_vel (Wk2 #4)."
        ),
    )

    @model_validator(mode="after")
    def check_robot_path(self) -> "RobotConfig":
        """At least one of urdf_path or usd_asset_path must be provided."""
        if self.urdf_path is None and self.usd_asset_path is None:
            raise ValueError("At least one of urdf_path or usd_asset_path must be provided")
        return self


class RenderingConfig(BaseModel):
    """Rendering configuration."""

    mode: Literal["path_tracing", "ray_tracing"] = Field(default="path_tracing")
    sky_dome_hdri_dir: str = Field(default="assets/sky/hdri/")
    resolution: list[int] = Field(
        default=[1280, 720], min_length=2, max_length=2, description="[width, height] in pixels"
    )
    spp: int = Field(default=32, ge=1, le=256, description="Samples per pixel per frame")
    total_spp: int = Field(default=256, ge=1, description="Total accumulated samples")
    max_bounces: int = Field(default=8, ge=1, le=64, description="Max ray bounces")
    sun_intensity_scale: float = Field(
        default=30.0, ge=0.1, description="W/m^2 to Isaac Sim light units scale factor"
    )
    sun_color: list[float] = Field(
        default=[1.0, 0.95, 0.85],
        min_length=3,
        max_length=3,
        description="Sun light RGB color [0-1]",
    )
    sun_angular_diameter_deg: float = Field(
        default=0.35, ge=0.1, le=5.0, description="Sun angular diameter from Mars"
    )
    dome_brightness_scale: float = Field(
        default=5000.0, ge=1.0, description="Sky dome brightness multiplier"
    )
    fog_density_scale: float = Field(
        default=0.002, ge=0.0, description="Tau to fog density conversion factor"
    )
    fog_color: list[float] = Field(
        default=[0.78, 0.62, 0.42],
        min_length=3,
        max_length=3,
        description="Mars dust haze fog color RGB [0-1]",
    )

    @model_validator(mode="after")
    def check_resolution(self) -> "RenderingConfig":
        """Resolution values must be positive."""
        if any(v <= 0 for v in self.resolution):
            raise ValueError(f"Resolution values must be positive, got {self.resolution}")
        return self


class SensorImuConfig(BaseModel):
    """Wk1 IMU live-gravity probe parameters (Phase B #23 / B4).

    Read by ``marslab.sensors.imu_probe.run_live_gravity_probe`` to
    drive the THE critical test (PLAN.md §6.2): spawn the rover under
    Mars gravity, settle, sample the attached IMU, and assert that the
    measured z-axis acceleration matches ``target_gz`` within
    ``tolerance``. No numeric Mars physics value lives in Python -- all
    four fields flow from ``configs/mars_env.yaml`` via this block.
    """

    sample_count: int = Field(
        default=20,
        ge=1,
        description="Number of IMU samples averaged for the gravity verdict.",
    )
    settle_steps: int = Field(
        default=50,
        ge=0,
        description=(
            "Physics steps to advance before sampling begins, so wheel "
            "contact oscillations damp out before the accelerometer is "
            "read."
        ),
    )
    target_gz: float = Field(
        default=3.72,
        ge=0.0,
        le=15.0,
        description=(
            "Expected downward accelerometer magnitude in m/s^2. Defaults "
            "to Mars surface gravity -- keep synchronised with "
            "mars_env.gravity unless the probe is deliberately tuned for "
            "a different body."
        ),
    )
    tolerance: float = Field(
        default=0.05,
        gt=0.0,
        description=(
            "Absolute tolerance on |mean_z - target_gz| AND on |mean_x| "
            "and |mean_y| for the probe to report pass=True."
        ),
    )
    stddev_z_max: float = Field(
        default=0.10,
        gt=0.0,
        description=(
            "Upper bound on per-sample stddev of the z acceleration "
            "before the reading is rejected as 'rover still bouncing'. "
            "Catches the settle_steps-too-low failure mode where "
            "mean_z is on target but the probe averaged a noisy "
            "contact oscillation."
        ),
    )
    mount_link: str = Field(
        default="imu_link",
        min_length=1,
        description=(
            "URDF link name to mount the probe IMU on. Override when a "
            "different rover URDF uses a non-REP-145 link identifier. "
            "Not a physical constant -- the value is a string label "
            "that identifies a prim path under the rover root, so G5 is "
            "honored via this YAML-overridable field."
        ),
    )
    fallback_link: str = Field(
        default="base_link",
        min_length=1,
        description=(
            "Backup link name used when ``mount_link`` is absent on the "
            "imported USD stage. The URDF importer occasionally drops "
            "empty links, and the probe falls back here instead of "
            "raising so the gate can still run on legacy URDFs."
        ),
    )
    # Phase C2 (#34, 2026-04-15): IMU ROS2 publisher fields.
    # Wired into marslab.ros2_bridge.imu_node.IMUPublisher so the
    # interactive GUI scene exposes /<robot_name>/imu/data and the
    # SLAM/Nav stack can consume it. Phase B's run_live_gravity_probe
    # is now disabled (the probe was a one-shot offline gate); the
    # gate now runs against the live ROS2 topic during a manual
    # `ros2 topic echo` after the user launches scripts/run_scene_interactive.py.
    publish_rate_hz: float = Field(
        default=100.0,
        gt=0.0,
        le=1000.0,
        description=(
            "ROS2 publish rate in Hz for the IMU sensor_msgs/Imu topic. "
            "Defaults to 100 Hz which matches the cmd_vel/odometry "
            "watchdog budget at physics_dt=1/200 s. The publisher timer "
            "fires at 1/publish_rate_hz seconds."
        ),
    )
    frame_id: str = Field(
        default="imu_link",
        min_length=1,
        description=(
            "REP-105 ``header.frame_id`` for the published Imu msg. "
            "Must match a TF frame broadcast by tf_broadcaster.py so "
            "downstream consumers can resolve the IMU pose against "
            "base_link."
        ),
    )
    topic_name: str = Field(
        default="/{robot_name}/imu/data",
        min_length=1,
        description=(
            "ROS2 topic template. ``{robot_name}`` is substituted with "
            "the rover instance name (e.g. ``rover_0``) at publisher "
            "construction time. Override to escape the templating by "
            "passing a literal path that does not contain ``{robot_name}``."
        ),
    )


class SensorsConfig(BaseModel):
    """Sensor-subsystem configuration container (Phase B #23 / B4).

    Thin wrapper that nests the per-sensor-kind config blocks under a
    single top-level ``sensors`` YAML key. Today only the Wk1 IMU probe
    lives here; additional subsystems (stereo calibration, LiDAR noise
    models) can join without re-flattening the schema.
    """

    imu: SensorImuConfig = Field(default_factory=SensorImuConfig)


class TelemetryConfig(BaseModel):
    """Runtime telemetry output paths (Phase B #23 / B4).

    Consumed by ``marslab.telemetry.json_sink.write_sink`` and the Phase
    B hooks inside ``scripts/run_scene.py``. Keeps workspace file
    locations out of Python source so a user can redirect the Wk1 IMU
    gate output without editing code.
    """

    json_sink_path: str = Field(
        default="_workspace/wk1_imu_gate.json",
        min_length=1,
        description=(
            "Destination path for the Wk1 IMU gate JSON payload. Parent "
            "directories are created on demand by the sink."
        ),
    )


class BenchmarkConfig(BaseModel):
    """Benchmark data generation and evaluation parameters."""

    annotation_format: str = Field(default="ai4mars")
    dr_axes: list[str] = Field(default_factory=list, description="Domain randomization axes")
    num_samples: int = Field(default=10000, ge=1)
    seed: int = Field(default=42, ge=0)


class MarsLabConfig(BaseModel):
    """Top-level MarsLab configuration aggregating all sub-configs."""

    mars_env: MarsEnvConfig = Field(default_factory=MarsEnvConfig)
    terrain: TerrainConfig = Field(default_factory=TerrainConfig)
    robots: list[RobotConfig] = Field(default_factory=list)
    rendering: RenderingConfig = Field(default_factory=RenderingConfig)
    sensors: SensorsConfig = Field(
        default_factory=SensorsConfig,
        description=(
            "Sensor-subsystem config container. Currently holds the Wk1 "
            "IMU live-gravity probe block under 'sensors.imu'."
        ),
    )
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    benchmark: BenchmarkConfig | None = Field(default=None)
