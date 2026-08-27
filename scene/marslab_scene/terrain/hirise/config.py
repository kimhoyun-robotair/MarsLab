"""Behavior-neutral HiRISE terrain configuration values."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class InputConfig:
    path: Path
    source_type: str = "geotiff"
    band: int = 1
    nodata_override: float | None = None


@dataclass(frozen=True, slots=True)
class CropConfig:
    mode: str = "center_size"
    center_mode: str = "dataset_center"
    center_x: float | None = None
    center_y: float | None = None
    width_m: float = 500.0
    height_m: float = 500.0
    allow_partial: bool = False


@dataclass(frozen=True, slots=True)
class ResampleConfig:
    method: str = "bilinear"


@dataclass(frozen=True, slots=True)
class CoordinatesConfig:
    convention: str = "ros_rep_103_enu"
    frame_id: str = "map"
    local_origin: str = "crop_center"
    x_axis: str = "east_or_projected_easting"
    y_axis: str = "north_or_projected_northing"
    z_axis: str = "up"
    yaw_zero: str = "east"
    yaw_positive: str = "counter_clockwise"
    require_projected_units_meters: bool = True
    reject_rotated_rasters: bool = True


@dataclass(frozen=True, slots=True)
class ProcessingConfig:
    fill_nodata: str = "nearest"
    smoothing_sigma_m: float = 0.0


@dataclass(frozen=True, slots=True)
class ElevationConfig:
    normalization: str = "min_zero"
    reference_percentile: float | None = None
    manual_reference_m: float | None = None
    vertical_scale: float = 1.0
    z_offset_m: float = 0.0
    clip_min_m: float | None = None
    clip_max_m: float | None = None
    nodata_policy: str = "mask_before_statistics"


@dataclass(frozen=True, slots=True)
class MeshConfig:
    visual_grid_size: int = 513
    collision_grid_size: int = 257
    triangulation: str = "regular"
    add_edge_skirt: bool = False
    edge_skirt_depth_m: float = 20.0
    write_visual_obj: bool = True
    write_collision_obj: bool = True


@dataclass(frozen=True, slots=True)
class UsdConfig:
    output_dir: Path = Path("./out/jezero_001")
    terrain_scene_name: str = "terrain.usda"
    root_prim: str = "/World"
    terrain_prim: str = "/World/MarsTerrain"
    visual_prim: str = "/World/MarsTerrain/VisualMesh"
    collision_prim: str = "/World/MarsTerrain/CollisionMesh"
    default_prim: str = "World"
    up_axis: str = "Z"
    meters_per_unit: float = 1.0
    file_format: str = "usda"


@dataclass(frozen=True, slots=True)
class PhysicsConfig:
    gravity_mps2: float = 3.711
    terrain_static: bool = True
    collision_approximation: str = "none"
    static_friction: float = 1.0
    dynamic_friction: float = 0.8
    restitution: float = 0.0
    contact_offset_m: float = 0.02
    rest_offset_m: float = 0.0


@dataclass(frozen=True, slots=True)
class ExportConfig:
    write_cropped_geotiff: bool = True
    write_metadata_json: bool = True
    write_resolved_config: bool = True


@dataclass(frozen=True, slots=True)
class TextureOutputSize:
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class TextureColormapConfig:
    name: str = "mars_debug"
    min_mode: str = "local_min"
    max_mode: str = "local_max"
    explicit_min_m: float | None = None
    explicit_max_m: float | None = None


@dataclass(frozen=True, slots=True)
class TextureMaterialConfig:
    name: str = "MarsTerrain_Material"
    roughness: float = 0.85
    metallic: float = 0.0
    opacity: float = 1.0


@dataclass(frozen=True, slots=True)
class TextureUvConfig:
    convention: str = "rep103_local_enu"
    u_axis: str = "+X_east"
    v_axis: str = "+Y_north"
    u_west: float = 0.0
    u_east: float = 1.0
    v_south: float = 0.0
    v_north: float = 1.0
    image_row_0: str = "north_top"
    verify_with_quadrant_test: bool = True


@dataclass(frozen=True, slots=True)
class TextureConfig:
    enabled: bool = True
    mode: str = "solid"
    path: Path | None = None
    require_same_crs: bool = True
    allow_reprojection: bool = False
    allow_non_georeferenced: bool = True
    non_georeferenced_policy: str = "stretch_to_crop"
    output_size: str | TextureOutputSize = "auto"
    max_texture_size_px: int = 4096
    resampling: str = "bilinear"
    output_dir: str = "textures"
    output_name: str = "terrain_albedo.png"
    color_space: str = "sRGB"
    channel_semantics: str = "unknown"
    solid_color: tuple[float, ...] = (0.58, 0.32, 0.20)
    colormap: TextureColormapConfig = field(default_factory=TextureColormapConfig)
    material: TextureMaterialConfig = field(default_factory=TextureMaterialConfig)
    uv: TextureUvConfig = field(default_factory=TextureUvConfig)


@dataclass(frozen=True, slots=True)
class OrthomosaicConfig:
    path: Path | None = None
    require_same_crs: bool = True
    resampling: str = "bilinear"
    band_mode: str = "auto"
    band_index: int | None = None


@dataclass(frozen=True, slots=True)
class MastcamReferenceConfig:
    path: Path | None = None
    roi: tuple[int, int, int, int] | None = None
    sky_rejection: bool = True
    robust_percentiles: tuple[float, float, float] = (5.0, 50.0, 95.0)


@dataclass(frozen=True, slots=True)
class ColorizationConfig:
    palette_mode: str = "reference_image"
    preserve_luminance: bool = True
    shadow_strength: float = 0.55
    midtone_strength: float = 1.0
    highlight_strength: float = 0.85
    saturation_scale: float = 0.95
    contrast: float = 1.15
    gamma: float = 1.0


@dataclass(frozen=True, slots=True)
class UpscalingConfig:
    enabled: bool = True
    method: str = "lanczos"
    target_m_per_px: float = 0.05
    max_texture_size_px: int = 8192
    allow_downsample: bool = True


@dataclass(frozen=True, slots=True)
class DetailVariationConfig:
    enabled: bool = True
    seed: int = 42
    method: str = "multi_scale_color_noise"
    strength: float = 0.08
    scales_m: tuple[float, ...] = (0.05, 0.20, 1.0)


@dataclass(frozen=True, slots=True)
class VisualPackagingConfig:
    texture_relative_path: str = "textures/terrain_albedo_mars_enhanced.png"
    forbid_absolute_asset_paths: bool = True
    record_absolute_input_paths: bool = False


@dataclass(frozen=True, slots=True)
class VisualEnhancementConfig:
    enabled: bool = False
    mode: str = "none"
    orthomosaic: OrthomosaicConfig = field(default_factory=OrthomosaicConfig)
    mastcam_reference: MastcamReferenceConfig = field(default_factory=MastcamReferenceConfig)
    colorization: ColorizationConfig = field(default_factory=ColorizationConfig)
    upscaling: UpscalingConfig = field(default_factory=UpscalingConfig)
    detail_variation: DetailVariationConfig = field(default_factory=DetailVariationConfig)
    packaging: VisualPackagingConfig = field(default_factory=VisualPackagingConfig)


@dataclass(frozen=True, slots=True)
class PipelineConfig:
    input: InputConfig
    crop: CropConfig = field(default_factory=CropConfig)
    resample: ResampleConfig = field(default_factory=ResampleConfig)
    coordinates: CoordinatesConfig = field(default_factory=CoordinatesConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    elevation: ElevationConfig = field(default_factory=ElevationConfig)
    mesh: MeshConfig = field(default_factory=MeshConfig)
    usd: UsdConfig = field(default_factory=UsdConfig)
    physics: PhysicsConfig = field(default_factory=PhysicsConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    texture: TextureConfig = field(default_factory=TextureConfig)
    visual_enhancement: VisualEnhancementConfig = field(default_factory=VisualEnhancementConfig)
