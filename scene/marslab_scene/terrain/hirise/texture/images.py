"""Behavior-neutral HiRISE texture image processing."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

from marslab_scene.terrain.hirise.config import TextureConfig, TextureOutputSize
from marslab_scene.terrain.hirise.ingest.dem_info import DemInfo
from marslab_scene.terrain.hirise.ingest.geotiff import RasterCrop

_RGBA_CHANNELS: Final = 4


class TextureError(ValueError):
    """Base error for texture preparation failures."""


class TextureAlignmentError(TextureError):
    """Raised when georeferenced texture alignment is unsupported."""


def solid_image(texture: TextureConfig) -> np.ndarray:
    """Create the retained one-pixel solid texture."""
    channels = np.asarray(texture.solid_color, dtype=np.float64)
    rgb = np.clip(np.rint(channels[:3] * 255), 0, 255).astype(np.uint8)
    return rgb.reshape(3, 1, 1)


def elevation_colormap(z: np.ndarray, *, width: int, height: int) -> np.ndarray:
    """Create the retained diagnostic elevation colormap."""
    resized = _resize_array_nearest(np.asarray(z, dtype=np.float64), width=width, height=height)
    min_z = float(np.min(resized))
    max_z = float(np.max(resized))
    span = max(max_z - min_z, 1e-12)
    t = np.clip((resized - min_z) / span, 0.0, 1.0)
    low = np.array([70, 34, 24], dtype=np.float64)
    mid = np.array([160, 86, 42], dtype=np.float64)
    high = np.array([222, 184, 126], dtype=np.float64)
    first = low[:, None, None] * (1.0 - np.minimum(t, 0.5) * 2.0) + mid[:, None, None] * (
        np.minimum(t, 0.5) * 2.0
    )
    second_weight = np.clip((t - 0.5) * 2.0, 0.0, 1.0)
    rgb = first * (1.0 - second_weight) + high[:, None, None] * second_weight
    return np.clip(np.rint(rgb), 0, 255).astype(np.uint8)


def read_albedo_raster(
    texture: TextureConfig,
    info: DemInfo,
    crop: RasterCrop,
) -> tuple[np.ndarray, str | None]:
    """Read a crop-aligned georeferenced albedo raster."""
    dem_crs = CRS.from_wkt(info.crs_wkt) if info.crs_wkt else None
    with rasterio.open(texture.path) as dataset:
        if dataset.crs is None:
            raise TextureAlignmentError("albedo_raster source is not georeferenced")
        if dem_crs is None or dataset.crs != dem_crs:
            raise TextureAlignmentError(
                "CRS/projection mismatch for albedo_raster; Task 11 does not reproject"
            )
        window = from_bounds(*crop.bounds, transform=dataset.transform)
        width, height = resolve_output_size(
            texture,
            default_width=max(1, round(window.width)),
            default_height=max(1, round(window.height)),
        )
        indexes = _color_indexes(dataset.count)
        data = dataset.read(
            indexes,
            window=window,
            out_shape=(len(indexes), height, width),
            resampling=_rasterio_resampling(texture.resampling),
            boundless=True,
            fill_value=0,
        )
        return _to_rgb_uint8(data), dataset.crs.to_wkt()


def read_image_stretch(texture: TextureConfig) -> np.ndarray:
    """Read a non-georeferenced image with stretch semantics."""
    with rasterio.open(texture.path) as dataset:
        width, height = resolve_output_size(
            texture,
            default_width=dataset.width,
            default_height=dataset.height,
        )
        indexes = _color_indexes(dataset.count)
        data = dataset.read(
            indexes,
            out_shape=(len(indexes), height, width),
            resampling=_rasterio_resampling(texture.resampling),
        )
    return _to_rgb_uint8(data)


def resolve_output_size(
    texture: TextureConfig,
    *,
    default_width: int,
    default_height: int,
) -> tuple[int, int]:
    """Resolve the bounded output texture dimensions."""
    if isinstance(texture.output_size, TextureOutputSize):
        return (texture.output_size.width, texture.output_size.height)
    width = max(1, default_width)
    height = max(1, default_height)
    scale = min(1.0, texture.max_texture_size_px / max(width, height))
    return (max(1, round(width * scale)), max(1, round(height * scale)))


def _resize_array_nearest(array: np.ndarray, *, width: int, height: int) -> np.ndarray:
    row_indices = np.rint(np.linspace(0, array.shape[0] - 1, height)).astype(np.int64)
    col_indices = np.rint(np.linspace(0, array.shape[1] - 1, width)).astype(np.int64)
    return array[row_indices][:, col_indices]


def _color_indexes(count: int) -> list[int]:
    if count == 1:
        return [1]
    if count in {3, 4}:
        return list(range(1, count + 1))
    if count > _RGBA_CHANNELS:
        return [1, 2, 3]
    raise TextureError("Texture source must have at least one band")


def _to_rgb_uint8(data: np.ndarray) -> np.ndarray:
    array = np.asarray(data)
    if array.shape[0] == 1:
        array = np.repeat(array, 3, axis=0)
    if array.shape[0] >= _RGBA_CHANNELS:
        array = array[:_RGBA_CHANNELS]
    if array.dtype == np.uint8:
        return array
    values = array.astype(np.float64)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros_like(values, dtype=np.uint8)
    min_value = float(np.min(finite))
    max_value = float(np.max(finite))
    if max_value <= min_value:
        return np.zeros_like(values, dtype=np.uint8)
    return np.clip(
        np.rint((values - min_value) / (max_value - min_value) * 255),
        0,
        255,
    ).astype(np.uint8)


def write_png(path: Path, array: np.ndarray) -> None:
    """Write a band-first uint8 PNG texture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(array, dtype=np.uint8)
    with rasterio.open(
        path,
        "w",
        driver="PNG",
        width=data.shape[2],
        height=data.shape[1],
        count=data.shape[0],
        dtype="uint8",
    ) as dataset:
        dataset.write(data)


def _rasterio_resampling(method: str) -> Resampling:
    if method == "nearest":
        return Resampling.nearest
    if method == "bilinear":
        return Resampling.bilinear
    if method == "cubic":
        return Resampling.cubic
    message = f"Unsupported texture resampling method: {method}"
    raise TextureError(message)
