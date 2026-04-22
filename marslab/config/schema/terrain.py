"""Terrain schemas: DEM crop, cave (lava tube), terrain generation.

Split from marslab.config.schema (R2, 2026-04-22). Intra-file order:
``DemCropConfig`` -> ``CaveConfig`` -> ``TerrainConfig`` so the later
models reference the earlier ones without forward-ref strings.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

__all__ = ["CaveConfig", "DemCropConfig", "TerrainConfig"]


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


class CaveConfig(BaseModel):
    """Mars lava tube cave parameters for procedural generation.

    Science basis: Sauro et al. 2020, Cushing 2007/2012, Theinat 2020,
    Blair 2017, Blank 2024 (BRAILLE). See work_log/scene_generation/mars_cave.md.
    """

    tube_width_m: float = Field(
        default=200.0,
        ge=80.0,
        le=300.0,
        description="Lava tube width in meters (Sauro 2020: 80-300m, mode 200m)",
    )
    tube_height_ratio: float = Field(
        default=0.5,
        ge=0.25,
        le=0.6,
        description="Height/width ratio for half-ellipse cross-section (W:H 2:1 to 3:1)",
    )
    cross_section_noise: float = Field(
        default=0.20,
        ge=0.0,
        le=0.4,
        description="±fraction of Gaussian noise on cross-section radius (Chwala 2024)",
    )
    tube_direction_deg: float = Field(
        default=0.0,
        ge=0.0,
        le=360.0,
        description="Tube axis direction in degrees (0=along Y axis, 90=along X axis)",
    )
    tube_curvature: float = Field(
        default=0.15,
        ge=0.0,
        le=0.5,
        description="Sinusoidal curvature amplitude factor for centerline",
    )
    ceiling_thickness_m: float = Field(
        default=50.0,
        ge=20.0,
        le=100.0,
        description="Rock ceiling thickness above tube crown (Sauro 2018: 30-80m)",
    )
    skylight_count: int = Field(
        default=10,
        ge=0,
        le=20,
        description="Number of skylights (ceiling collapse openings) along the tube",
    )
    skylight_diameter_m: float = Field(
        default=20.0,
        ge=5.0,
        le=250.0,
        description="Skylight opening diameter in meters (5-250m)",
    )
    skylight_depth_m: float = Field(
        default=90.0,
        ge=20.0,
        le=200.0,
        description="Skylight depth from surface to tube ceiling (Cushing 2007: 68-178m)",
    )
    skylight_overhang_deg: float = Field(
        default=5.0,
        ge=0.0,
        le=15.0,
        description="Inward overhang angle of skylight walls (Cushing 2012)",
    )
    debris_cone_present: bool = Field(
        default=True,
        description="Whether debris cones are placed inside the tube",
    )
    debris_cone_count: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Number of debris cones randomly placed inside the tube",
    )
    debris_cone_angle_deg: float = Field(
        default=30.0,
        ge=20.0,
        le=40.0,
        description="Angle of repose for debris cone (Cushing 2012: ~30 deg)",
    )
    breakdown_coverage_pct: float = Field(
        default=25.0,
        ge=0.0,
        le=80.0,
        description="Floor area covered by breakdown blocks (Blank 2024: 10-80%)",
    )
    breakdown_block_mean_m: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="LogNormal mean block diameter (Blank 2024: mean 0.5m)",
    )
    breakdown_block_sigma: float = Field(
        default=0.3,
        ge=0.05,
        le=1.0,
        description="LogNormal sigma for block size distribution",
    )
    floor_flat_pct: float = Field(
        default=70.0,
        ge=20.0,
        le=100.0,
        description="Percentage of floor that is flat vs debris-covered",
    )
    wall_albedo_range: tuple[float, float] = Field(
        default=(0.05, 0.15),
        description="Cave wall/ceiling albedo range (dark basalt, Rodriguez 2021)",
    )
    ring_resolution: int = Field(
        default=40,
        ge=12,
        le=120,
        description="Number of vertices per cross-section ring",
    )
    path_resolution: int = Field(
        default=100,
        ge=20,
        le=400,
        description="Number of cross-sections along the tube centerline",
    )

    @model_validator(mode="after")
    def check_cave_ranges(self) -> "CaveConfig":
        """Validate cave parameter consistency."""
        if self.wall_albedo_range[0] >= self.wall_albedo_range[1]:
            raise ValueError(
                f"wall_albedo_range must be (min, max) with min < max, "
                f"got {self.wall_albedo_range}"
            )
        tube_height = self.tube_width_m * self.tube_height_ratio
        if self.skylight_count > 0 and self.skylight_depth_m < tube_height:
            raise ValueError(
                f"skylight_depth_m ({self.skylight_depth_m}) must be >= tube height "
                f"({tube_height:.1f}m = width * ratio) for the shaft to reach the tube"
            )
        return self


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
        default=None,
        description="Procedural preset: flat, crater, hills, rocky_plain, canyon, cave",
    )
    cave: CaveConfig | None = Field(
        default=None,
        description="Cave (lava tube) generation parameters. Required when "
        "procedural_preset is 'cave'.",
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
