"""Strict schema-v1 HiRISE recipe settings."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from marslab_scene.config.paths import relative_local_path, relative_posix_path
from marslab_scene.errors import ContractValueError


class _StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, strict=True)


class CropSettings(_StrictModel):
    mode: Literal["center_size"] = "center_size"
    center_mode: Literal["dataset_center", "projected"] = "dataset_center"
    center_x: float | None = None
    center_y: float | None = None
    width_m: float = Field(default=500.0, gt=0.0)
    height_m: float = Field(default=500.0, gt=0.0)
    allow_partial: bool = False

    @model_validator(mode="after")
    def validate_projected_center(self) -> CropSettings:
        if self.center_mode == "projected" and (self.center_x is None or self.center_y is None):
            raise ContractValueError("center_x and center_y are required for projected crop")
        return self


class ElevationSettings(_StrictModel):
    normalization: Literal[
        "absolute", "min_zero", "mean_zero", "median_zero", "percentile_zero", "manual"
    ] = "min_zero"
    reference_percentile: float | None = Field(default=None, ge=0.0, le=100.0)
    manual_reference_m: float | None = None
    vertical_scale: float = Field(default=1.0, gt=0.0)
    z_offset_m: float = 0.0
    nodata_policy: Literal["mask_before_statistics"] = "mask_before_statistics"

    @model_validator(mode="after")
    def validate_reference(self) -> ElevationSettings:
        if self.normalization == "manual" and self.manual_reference_m is None:
            raise ContractValueError("manual_reference_m is required for manual normalization")
        if self.normalization == "percentile_zero" and self.reference_percentile is None:
            raise ContractValueError(
                "reference_percentile is required for percentile_zero normalization"
            )
        return self


class MeshSettings(_StrictModel):
    visual_grid_size: int = Field(default=513, ge=2)
    collision_grid_size: int = Field(default=257, ge=2)

    @field_validator("visual_grid_size", "collision_grid_size")
    @classmethod
    def validate_odd_grid(cls, value: int) -> int:
        if value % 2 == 0:
            raise ContractValueError("HiRISE mesh grid size must be odd")
        return value


class TextureOutputSizeSettings(_StrictModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class TextureMaterialSettings(_StrictModel):
    name: str = "MarsTerrain_Material"
    roughness: float = Field(default=0.85, ge=0.0, le=1.0)
    metallic: float = Field(default=0.0, ge=0.0, le=1.0)
    opacity: float = Field(default=1.0, ge=0.0, le=1.0)


class TextureUvSettings(_StrictModel):
    convention: Literal["rep103_local_enu"] = "rep103_local_enu"
    u_axis: Literal["+X_east"] = "+X_east"
    v_axis: Literal["+Y_north"] = "+Y_north"
    u_west: float = 0.0
    u_east: float = 1.0
    v_south: float = 0.0
    v_north: float = 1.0
    image_row_0: Literal["north_top"] = "north_top"
    verify_with_quadrant_test: bool = True


class TextureSettings(_StrictModel):
    enabled: bool = True
    mode: Literal["none", "solid", "elevation_colormap", "albedo_raster", "image_stretch"] = "solid"
    path: Path | None = None
    require_same_crs: bool = True
    allow_reprojection: Literal[False] = False
    allow_non_georeferenced: bool = True
    non_georeferenced_policy: Literal["stretch_to_crop"] = "stretch_to_crop"
    output_size: Literal["auto"] | TextureOutputSizeSettings = "auto"
    max_texture_size_px: int = Field(default=4096, gt=0)
    resampling: Literal["nearest", "bilinear", "cubic", "lanczos"] = "bilinear"
    output_dir: str = "textures"
    output_name: str = "terrain_albedo.png"
    color_space: Literal["sRGB"] = "sRGB"
    channel_semantics: str = "unknown"
    solid_color: tuple[float, ...] = (0.58, 0.32, 0.20)
    material: TextureMaterialSettings = Field(default_factory=TextureMaterialSettings)
    uv: TextureUvSettings = Field(default_factory=TextureUvSettings)

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, value: Path | str | None) -> Path | None:
        return None if value is None else relative_local_path(value)

    @field_validator("solid_color", mode="before")
    @classmethod
    def validate_solid_color(cls, value: list[float] | tuple[float, ...]) -> tuple[float, ...]:
        channels = tuple(value)
        outside_range = any(channel < 0.0 or channel > 1.0 for channel in channels)
        if len(channels) not in {3, 4} or outside_range:
            raise ContractValueError("solid_color must have 3 or 4 channels in the 0..1 range")
        return channels

    @field_validator("output_dir", "output_name")
    @classmethod
    def validate_output_path(cls, value: str) -> str:
        return relative_posix_path(value).as_posix()

    @model_validator(mode="after")
    def validate_texture_source(self) -> TextureSettings:
        if self.mode in {"albedo_raster", "image_stretch"} and self.path is None:
            raise ContractValueError("texture path is required for the selected mode")
        if isinstance(self.output_size, TextureOutputSizeSettings) and (
            self.output_size.width > self.max_texture_size_px
            or self.output_size.height > self.max_texture_size_px
        ):
            raise ContractValueError("texture output_size exceeds max_texture_size_px")
        return self


class OrthomosaicSettings(_StrictModel):
    path: Path | None = None
    require_same_crs: bool = True
    resampling: Literal["nearest", "bilinear", "cubic", "lanczos"] = "bilinear"
    band_mode: Literal["auto", "grayscale", "rgb", "band"] = "auto"
    band_index: int | None = Field(default=None, ge=1)

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, value: Path | str | None) -> Path | None:
        return None if value is None else relative_local_path(value)


class MastcamReferenceSettings(_StrictModel):
    path: Path | None = None
    roi: tuple[int, int, int, int] | None = None
    sky_rejection: bool = True
    robust_percentiles: tuple[float, float, float] = (5.0, 50.0, 95.0)

    @field_validator("path", mode="before")
    @classmethod
    def validate_path(cls, value: Path | str | None) -> Path | None:
        return None if value is None else relative_local_path(value)

    @field_validator("roi", "robust_percentiles", mode="before")
    @classmethod
    def validate_tuples(
        cls,
        value: list[int] | list[float] | tuple[int, ...] | tuple[float, ...] | None,
    ) -> tuple[int, ...] | tuple[float, ...] | None:
        return None if value is None else tuple(value)


class ColorizationSettings(_StrictModel):
    palette_mode: Literal["reference_image"] = "reference_image"
    preserve_luminance: bool = True
    shadow_strength: float = 0.55
    midtone_strength: float = 1.0
    highlight_strength: float = 0.85
    saturation_scale: float = 0.95
    contrast: float = 1.15
    gamma: float = Field(default=1.0, gt=0.0)


class UpscalingSettings(_StrictModel):
    enabled: bool = True
    method: Literal["nearest", "bilinear", "cubic", "lanczos"] = "lanczos"
    target_m_per_px: float = Field(default=0.05, gt=0.0)
    max_texture_size_px: int = Field(default=8192, gt=0)
    allow_downsample: bool = True


class DetailVariationSettings(_StrictModel):
    enabled: bool = True
    seed: int = 42
    method: Literal["multi_scale_color_noise"] = "multi_scale_color_noise"
    strength: float = Field(default=0.08, ge=0.0)
    scales_m: tuple[float, ...] = (0.05, 0.20, 1.0)

    @field_validator("scales_m", mode="before")
    @classmethod
    def validate_scales(cls, value: list[float] | tuple[float, ...]) -> tuple[float, ...]:
        return tuple(value)


class VisualPackagingSettings(_StrictModel):
    texture_relative_path: str = "textures/terrain_albedo_mars_enhanced.png"
    forbid_absolute_asset_paths: Literal[True] = True
    record_absolute_input_paths: Literal[False] = False

    @field_validator("texture_relative_path")
    @classmethod
    def validate_texture_path(cls, value: str) -> str:
        return relative_posix_path(value).as_posix()


class AppearanceSettings(_StrictModel):
    enabled: bool = False
    mode: Literal["none", "orthomosaic_mastcam_palette"] = "none"
    orthomosaic: OrthomosaicSettings = Field(default_factory=OrthomosaicSettings)
    mastcam_reference: MastcamReferenceSettings = Field(default_factory=MastcamReferenceSettings)
    colorization: ColorizationSettings = Field(default_factory=ColorizationSettings)
    upscaling: UpscalingSettings = Field(default_factory=UpscalingSettings)
    detail_variation: DetailVariationSettings = Field(default_factory=DetailVariationSettings)
    packaging: VisualPackagingSettings = Field(default_factory=VisualPackagingSettings)

    @model_validator(mode="after")
    def validate_enabled_mode(self) -> AppearanceSettings:
        if self.enabled == (self.mode == "none"):
            raise ContractValueError("appearance enabled flag and mode are inconsistent")
        if self.mode == "orthomosaic_mastcam_palette" and (
            self.orthomosaic.path is None or self.mastcam_reference.path is None
        ):
            raise ContractValueError("appearance source paths are required for palette mode")
        return self
