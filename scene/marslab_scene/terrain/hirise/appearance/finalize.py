"""Finalize Task 12 enhanced albedo textures with deterministic resizing and detail."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from pydantic import JsonValue
from rasterio.enums import Resampling
from rasterio.io import MemoryFile

from marslab_scene.terrain.hirise.config import DetailVariationConfig, UpscalingConfig


class TextureFinalizeError(ValueError):
    """Raised when an enhanced texture cannot be finalized."""


@dataclass(frozen=True, slots=True)
class EnhancedTexture:
    """Final enhanced texture artifact."""

    image: np.ndarray
    output_path: Path
    width: int
    height: int
    sha256: str
    parameters: dict[str, JsonValue]


def finalize_enhanced_texture(
    image: np.ndarray,
    *,
    crop_width_m: float,
    crop_height_m: float,
    upscaling: UpscalingConfig,
    detail_variation: DetailVariationConfig,
    output_path: Path,
) -> EnhancedTexture:
    """Resize, add deterministic detail variation, and write the enhanced PNG texture."""
    rgb = _as_rgb_uint8(image)
    width, height = _target_texture_size(
        source_width=rgb.shape[1],
        source_height=rgb.shape[0],
        crop_width_m=crop_width_m,
        crop_height_m=crop_height_m,
        config=upscaling,
    )
    resized = _resize_rgb(rgb, width=width, height=height, method=upscaling.method)
    varied = _apply_detail_variation(
        resized,
        crop_width_m=crop_width_m,
        crop_height_m=crop_height_m,
        config=detail_variation,
    )
    _write_png(output_path, varied)
    digest = hashlib.sha256(varied.tobytes()).hexdigest()
    return EnhancedTexture(
        image=varied,
        output_path=output_path,
        width=width,
        height=height,
        sha256=digest,
        parameters={
            "upscaling": {
                "enabled": upscaling.enabled,
                "method": upscaling.method,
                "target_m_per_px": upscaling.target_m_per_px,
                "max_texture_size_px": upscaling.max_texture_size_px,
                "allow_downsample": upscaling.allow_downsample,
            },
            "detail_variation": {
                "enabled": detail_variation.enabled,
                "seed": detail_variation.seed,
                "method": detail_variation.method,
                "strength": detail_variation.strength,
                "scales_m": list(detail_variation.scales_m),
            },
        },
    )


def _target_texture_size(
    *,
    source_width: int,
    source_height: int,
    crop_width_m: float,
    crop_height_m: float,
    config: UpscalingConfig,
) -> tuple[int, int]:
    if not config.enabled:
        return source_width, source_height
    if crop_width_m <= 0.0 or crop_height_m <= 0.0:
        msg = "crop dimensions must be > 0 for visual enhancement texture sizing"
        raise TextureFinalizeError(msg)
    target_width = int(np.ceil(crop_width_m / config.target_m_per_px))
    target_height = int(np.ceil(crop_height_m / config.target_m_per_px))
    if not config.allow_downsample:
        target_width = max(target_width, source_width)
        target_height = max(target_height, source_height)

    scale = min(
        1.0,
        config.max_texture_size_px / max(target_width, target_height),
    )
    return (
        max(1, int(round(target_width * scale))),
        max(1, int(round(target_height * scale))),
    )


def _resize_rgb(image: np.ndarray, *, width: int, height: int, method: str) -> np.ndarray:
    if image.shape[0] == height and image.shape[1] == width:
        return image.copy()

    with (
        MemoryFile() as memory_file,
        memory_file.open(
            driver="GTiff",
            width=image.shape[1],
            height=image.shape[0],
            count=3,
            dtype="uint8",
        ) as dataset,
    ):
        dataset.write(np.moveaxis(image, -1, 0))
        data = dataset.read(
            out_shape=(3, height, width),
            resampling=_resampling(method),
        )
    return np.moveaxis(data, 0, -1).astype(np.uint8)


def _apply_detail_variation(
    image: np.ndarray,
    *,
    crop_width_m: float,
    crop_height_m: float,
    config: DetailVariationConfig,
) -> np.ndarray:
    if not config.enabled or config.strength == 0.0:
        return image.copy()
    if config.method != "multi_scale_color_noise":
        msg = f"Unsupported detail variation method: {config.method}"
        raise TextureFinalizeError(msg)

    rng = np.random.default_rng(config.seed)
    height, width, _ = image.shape
    noise = np.zeros((height, width), dtype=np.float64)
    for scale_m in config.scales_m:
        low_width = max(2, int(np.ceil(crop_width_m / scale_m)))
        low_height = max(2, int(np.ceil(crop_height_m / scale_m)))
        low_noise = rng.normal(0.0, 1.0, size=(low_height, low_width))
        noise += _resize_plane_bilinear(low_noise, width=width, height=height)
    noise /= max(1, len(config.scales_m))
    std = float(np.std(noise))
    if std > 1.0e-12:
        noise = noise / std

    multiplier = 1.0 + np.clip(noise, -2.0, 2.0)[..., np.newaxis] * config.strength
    color_bias = rng.normal(0.0, config.strength * 0.30, size=(1, 1, 3))
    varied = image.astype(np.float64) * multiplier * (1.0 + color_bias)
    return np.clip(np.rint(varied), 0, 255).astype(np.uint8)


def _resize_plane_bilinear(array: np.ndarray, *, width: int, height: int) -> np.ndarray:
    source_y = np.linspace(0.0, array.shape[0] - 1, height)
    source_x = np.linspace(0.0, array.shape[1] - 1, width)
    rows = np.empty((height, array.shape[1]), dtype=np.float64)
    base_y = np.arange(array.shape[0], dtype=np.float64)
    for col in range(array.shape[1]):
        rows[:, col] = np.interp(source_y, base_y, array[:, col])
    result = np.empty((height, width), dtype=np.float64)
    base_x = np.arange(array.shape[1], dtype=np.float64)
    for row in range(height):
        result[row] = np.interp(source_x, base_x, rows[row])
    return result


def _as_rgb_uint8(image: np.ndarray) -> np.ndarray:
    data = np.asarray(image)
    if data.ndim != 3 or data.shape[2] != 3:
        msg = "enhanced texture image must be HxWx3 RGB"
        raise TextureFinalizeError(msg)
    if data.dtype == np.uint8:
        return data
    return np.clip(np.rint(data), 0, 255).astype(np.uint8)


def _write_png(path: Path, image: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.moveaxis(np.asarray(image, dtype=np.uint8), -1, 0)
    with rasterio.open(
        path,
        "w",
        driver="PNG",
        width=image.shape[1],
        height=image.shape[0],
        count=3,
        dtype="uint8",
    ) as dataset:
        dataset.write(data)


def _resampling(method: str) -> Resampling:
    if method == "lanczos":
        return Resampling.lanczos
    if method == "bicubic":
        return Resampling.cubic
    msg = f"Unsupported upscaling method: {method}"
    raise TextureFinalizeError(msg)
