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


class TerrainConfig(BaseModel):
    """Terrain generation parameters."""

    source: Literal["hirise", "procedural"] = Field(default="hirise")
    dem_path: str | None = Field(default=None, description="Path to HiRISE DEM GeoTIFF")
    converted_dem_dir: str | None = Field(
        default=None,
        description="Directory containing pre-converted elevation.npy and metadata.json",
    )
    rock_sfd_k: float = Field(default=0.05, ge=0.001, le=0.15, description="Golombek CFA fraction")
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


class RobotConfig(BaseModel):
    """Single robot configuration."""

    type: str = Field(description="Robot type identifier (e.g., 'rover', 'quadruped')")
    urdf_path: str | None = Field(default=None, description="Path to custom URDF file")
    usd_asset_path: str | None = Field(default=None, description="Path to built-in USD asset")
    spawn_position: list[float] = Field(
        default=[0.0, 0.0, 0.5], min_length=3, max_length=3, description="[x, y, z] in meters"
    )
    sensor_config_paths: list[str] = Field(default_factory=list)

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
        default=5.0, ge=0.1, description="W/m^2 to Isaac Sim light units scale factor"
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
        default=1000.0, ge=1.0, description="Sky dome brightness multiplier"
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
    benchmark: BenchmarkConfig | None = Field(default=None)
