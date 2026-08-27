"""Prepare albedo texture images for Task 11 visual materials."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from pydantic import JsonValue

from marslab_scene.terrain.elevation import ElevationResult
from marslab_scene.terrain.hirise.config import PipelineConfig, TextureConfig
from marslab_scene.terrain.hirise.ingest.dem_info import DemInfo
from marslab_scene.terrain.hirise.ingest.geotiff import RasterCrop
from marslab_scene.terrain.hirise.texture.images import (
    TextureError,
    elevation_colormap,
    read_albedo_raster,
    read_image_stretch,
    resolve_output_size,
    solid_image,
    write_png,
)
from marslab_scene.terrain.hirise.texture.uv import uv_metadata


@dataclass(frozen=True, slots=True)
class PreparedTexture:
    """Texture artifact and metadata for USD material authoring."""

    enabled: bool
    mode: str
    output_path: Path | None
    width: int | None
    height: int | None
    source_path: Path | None
    source_is_georeferenced: bool
    georeference_ignored: bool
    source_crs: str | None
    crs_match_required: bool
    reprojection_performed: bool
    color_space: str
    channel_semantics: str
    resampling: str
    roughness: float
    metallic: float

    def to_metadata(self, output_dir: Path) -> dict[str, JsonValue]:
        """Return JSON-serializable texture metadata."""
        output_path = (
            str(self.output_path.relative_to(output_dir))
            if self.output_path is not None and self.output_path.is_relative_to(output_dir)
            else (str(self.output_path) if self.output_path is not None else None)
        )
        return {
            "enabled": self.enabled,
            "mode": self.mode,
            "source_path": str(self.source_path) if self.source_path is not None else None,
            "source_is_georeferenced": self.source_is_georeferenced,
            "georeference_ignored": self.georeference_ignored,
            "source_crs": self.source_crs,
            "crs_match_required": self.crs_match_required,
            "reprojection_performed": self.reprojection_performed,
            "output_path": output_path,
            "output_size_px": [self.width, self.height]
            if self.width is not None and self.height is not None
            else None,
            "resampling": self.resampling,
            "color_space": self.color_space,
            "channel_semantics": self.channel_semantics,
            "uv_convention": uv_metadata(),
            "material": {
                "bound_to": "VisualMesh" if self.enabled else None,
                "roughness": self.roughness,
                "metallic": self.metallic,
            },
            "collision_mesh_modified": False,
        }


def prepare_texture(
    config: PipelineConfig,
    info: DemInfo,
    crop: RasterCrop,
    elevation: ElevationResult,
    visual_z: np.ndarray,
) -> PreparedTexture | None:
    """Prepare a texture image according to the pipeline texture config."""
    _ = elevation
    texture = config.texture
    if not texture.enabled or texture.mode == "none":
        return _disabled_texture(texture)

    output_path = config.usd.output_dir / texture.output_dir / texture.output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if texture.mode == "solid":
        array = solid_image(texture)
        write_png(output_path, array)
        return _prepared(texture, output_path, array, source_path=None)

    if texture.mode == "elevation_colormap":
        size = resolve_output_size(
            texture,
            default_width=visual_z.shape[1],
            default_height=visual_z.shape[0],
        )
        array = elevation_colormap(visual_z, width=size[0], height=size[1])
        write_png(output_path, array)
        return _prepared(
            texture,
            output_path,
            array,
            source_path=None,
            channel_semantics=(
                texture.channel_semantics
                if texture.channel_semantics != "unknown"
                else "debug_elevation_colormap"
            ),
        )

    if texture.mode == "albedo_raster":
        if texture.path is None:
            raise TextureError("texture.path is required for albedo_raster")
        array, source_crs = read_albedo_raster(texture, info, crop)
        write_png(output_path, array)
        return _prepared(
            texture,
            output_path,
            array,
            source_path=texture.path,
            source_is_georeferenced=True,
            source_crs=source_crs,
        )

    if texture.mode == "image_stretch":
        if texture.path is None:
            raise TextureError("texture.path is required for image_stretch")
        array = read_image_stretch(texture)
        write_png(output_path, array)
        return _prepared(
            texture,
            output_path,
            array,
            source_path=texture.path,
            source_is_georeferenced=False,
            georeference_ignored=True,
        )

    raise TextureError(f"Unsupported texture mode: {texture.mode}")


def _disabled_texture(texture: TextureConfig) -> PreparedTexture:
    return PreparedTexture(
        enabled=False,
        mode="none",
        output_path=None,
        width=None,
        height=None,
        source_path=None,
        source_is_georeferenced=False,
        georeference_ignored=False,
        source_crs=None,
        crs_match_required=texture.require_same_crs,
        reprojection_performed=False,
        color_space=texture.color_space,
        channel_semantics=texture.channel_semantics,
        resampling=texture.resampling,
        roughness=texture.material.roughness,
        metallic=texture.material.metallic,
    )


def _prepared(
    texture: TextureConfig,
    output_path: Path,
    array: np.ndarray,
    *,
    source_path: Path | None,
    source_is_georeferenced: bool = False,
    georeference_ignored: bool = False,
    source_crs: str | None = None,
    channel_semantics: str | None = None,
) -> PreparedTexture:
    return PreparedTexture(
        enabled=True,
        mode=texture.mode,
        output_path=output_path,
        width=int(array.shape[2]),
        height=int(array.shape[1]),
        source_path=source_path,
        source_is_georeferenced=source_is_georeferenced,
        georeference_ignored=georeference_ignored,
        source_crs=source_crs,
        crs_match_required=texture.require_same_crs,
        reprojection_performed=False,
        color_space=texture.color_space,
        channel_semantics=channel_semantics or texture.channel_semantics,
        resampling=texture.resampling,
        roughness=texture.material.roughness,
        metallic=texture.material.metallic,
    )
