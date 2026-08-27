"""Material adapter for Task 12 enhanced visual textures."""

from __future__ import annotations

from marslab_scene.terrain.hirise.appearance.finalize import EnhancedTexture
from marslab_scene.terrain.hirise.config import TextureConfig
from marslab_scene.terrain.hirise.texture.prepare import PreparedTexture


def prepared_texture_from_enhanced(
    texture: EnhancedTexture,
    config: TextureConfig,
) -> PreparedTexture:
    """Adapt a Task 12 enhanced texture for the existing USD material writer."""
    return PreparedTexture(
        enabled=True,
        mode="visual_enhancement",
        output_path=texture.output_path,
        width=texture.width,
        height=texture.height,
        source_path=None,
        source_is_georeferenced=True,
        georeference_ignored=False,
        source_crs=None,
        crs_match_required=True,
        reprojection_performed=False,
        color_space=config.color_space,
        channel_semantics="mars_enhanced_albedo",
        resampling="lanczos",
        roughness=config.material.roughness,
        metallic=config.material.metallic,
    )
