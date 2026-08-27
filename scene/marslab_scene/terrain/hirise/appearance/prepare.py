"""End-to-end preparation for Task 12 visual enhancement textures."""

from __future__ import annotations

from dataclasses import dataclass

from marslab_scene.terrain.hirise.appearance.colorize import (
    ColorizedAlbedo,
    colorize_luminance_with_palette,
)
from marslab_scene.terrain.hirise.appearance.finalize import (
    EnhancedTexture,
    finalize_enhanced_texture,
)
from marslab_scene.terrain.hirise.appearance.material import prepared_texture_from_enhanced
from marslab_scene.terrain.hirise.appearance.orthomosaic import (
    OrthomosaicLuminance,
    read_orthomosaic_luminance,
)
from marslab_scene.terrain.hirise.appearance.palette import MarsPalette, extract_mastcam_palette
from marslab_scene.terrain.hirise.config import PipelineConfig
from marslab_scene.terrain.hirise.ingest.geotiff import RasterCrop
from marslab_scene.terrain.hirise.texture.prepare import PreparedTexture


@dataclass(frozen=True, slots=True)
class PreparedVisualEnhancement:
    """Prepared Task 12 texture plus material adapter and processing intermediates."""

    enhanced_texture: EnhancedTexture
    prepared_texture: PreparedTexture
    luminance: OrthomosaicLuminance
    palette: MarsPalette
    colorized: ColorizedAlbedo


def prepare_visual_enhancement(
    config: PipelineConfig,
    crop: RasterCrop,
    *,
    source_width: int,
    source_height: int,
) -> PreparedVisualEnhancement | None:
    """Prepare the Task 12 enhanced texture when enabled."""
    visual = config.visual_enhancement
    if not visual.enabled or visual.mode == "none":
        return None

    luminance = read_orthomosaic_luminance(
        visual.orthomosaic,
        crop,
        output_width=source_width,
        output_height=source_height,
    )
    palette = (
        extract_mastcam_palette(visual.mastcam_reference)
        if visual.mode == "orthomosaic_mastcam_palette"
        else _builtin_jezero_palette()
    )
    colorized = colorize_luminance_with_palette(luminance.array, palette, visual.colorization)
    enhanced = finalize_enhanced_texture(
        colorized.image,
        crop_width_m=config.crop.width_m,
        crop_height_m=config.crop.height_m,
        upscaling=visual.upscaling,
        detail_variation=visual.detail_variation,
        output_path=config.usd.output_dir / visual.packaging.texture_relative_path,
    )
    return PreparedVisualEnhancement(
        enhanced_texture=enhanced,
        prepared_texture=prepared_texture_from_enhanced(enhanced, config.texture),
        luminance=luminance,
        palette=palette,
        colorized=colorized,
    )


def _builtin_jezero_palette() -> MarsPalette:
    return MarsPalette(
        shadow_rgb=(64, 34, 24),
        midtone_rgb=(151, 86, 48),
        highlight_rgb=(224, 181, 124),
        source_pixel_count=0,
        used_pixel_count=0,
        sky_rejection_applied=False,
    )
