"""Deterministic Mastcam-Z reference palette extraction for Task 12."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

from marslab_scene.terrain.hirise.config import MastcamReferenceConfig


class PaletteExtractionError(ValueError):
    """Raised when a Mastcam reference palette cannot be extracted."""


@dataclass(frozen=True, slots=True)
class MarsPalette:
    """Shadow/midtone/highlight Mars-like color palette."""

    shadow_rgb: tuple[int, int, int]
    midtone_rgb: tuple[int, int, int]
    highlight_rgb: tuple[int, int, int]
    source_pixel_count: int
    used_pixel_count: int
    sky_rejection_applied: bool


def extract_mastcam_palette(config: MastcamReferenceConfig) -> MarsPalette:
    """Extract a deterministic terrain-biased RGB palette from a reference image."""
    if config.path is None:
        msg = "mastcam_reference.path is required"
        raise PaletteExtractionError(msg)

    image = _read_rgb_image(config.path)
    if config.roi is not None:
        image = _crop_roi(image, config.roi)

    pixels = image.reshape(-1, 3)
    source_count = len(pixels)
    if source_count == 0:
        msg = "Mastcam reference image contains no pixels"
        raise PaletteExtractionError(msg)

    used_pixels = _reject_likely_sky(pixels) if config.sky_rejection else pixels
    sky_applied = config.sky_rejection and len(used_pixels) != len(pixels)
    if len(used_pixels) == 0:
        used_pixels = pixels
        sky_applied = False

    shadow, midtone, highlight = _palette_by_luminance(
        used_pixels,
        percentiles=config.robust_percentiles,
    )
    return MarsPalette(
        shadow_rgb=shadow,
        midtone_rgb=midtone,
        highlight_rgb=highlight,
        source_pixel_count=source_count,
        used_pixel_count=len(used_pixels),
        sky_rejection_applied=sky_applied,
    )


def _read_rgb_image(path: Path) -> np.ndarray:
    try:
        with rasterio.open(path) as dataset:
            if dataset.count == 1:
                band = dataset.read(1)
                data = np.repeat(band[np.newaxis, :, :], 3, axis=0)
            else:
                indexes = [1, 2, 3] if dataset.count >= 3 else list(range(1, dataset.count + 1))
                data = dataset.read(indexes)
                if data.shape[0] < 3:
                    data = np.repeat(data[:1], 3, axis=0)
    except Exception as exc:
        raise PaletteExtractionError(f"Could not open Mastcam reference image: {path}") from exc

    rgb = np.moveaxis(_to_uint8(data[:3]), 0, -1)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        msg = "Mastcam reference image must resolve to RGB data"
        raise PaletteExtractionError(msg)
    return rgb


def _to_uint8(data: np.ndarray) -> np.ndarray:
    values = np.asarray(data)
    if values.dtype == np.uint8:
        return values
    values = values.astype(np.float64)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return np.zeros(values.shape, dtype=np.uint8)
    min_value = float(np.min(finite))
    max_value = float(np.max(finite))
    if max_value <= min_value:
        return np.zeros(values.shape, dtype=np.uint8)
    return np.clip(np.rint((values - min_value) / (max_value - min_value) * 255), 0, 255).astype(
        np.uint8
    )


def _crop_roi(image: np.ndarray, roi: tuple[int, int, int, int]) -> np.ndarray:
    x_min, y_min, x_max, y_max = roi
    if x_min < 0 or y_min < 0 or x_max <= x_min or y_max <= y_min:
        msg = "mastcam_reference.roi must be [x_min, y_min, x_max, y_max]"
        raise PaletteExtractionError(msg)
    clipped = image[y_min : min(y_max, image.shape[0]), x_min : min(x_max, image.shape[1])]
    if clipped.size == 0:
        msg = "mastcam_reference.roi selects no pixels"
        raise PaletteExtractionError(msg)
    return clipped


def _reject_likely_sky(pixels: np.ndarray) -> np.ndarray:
    values = pixels.astype(np.float64)
    red = values[:, 0]
    green = values[:, 1]
    blue = values[:, 2]
    sky_like = (blue > red * 1.08) & (blue > green * 1.02) & (blue > 80)
    return pixels[~sky_like]


def _palette_by_luminance(
    pixels: np.ndarray,
    *,
    percentiles: tuple[float, float, float],
) -> tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]:
    if any(percentile < 0 or percentile > 100 for percentile in percentiles):
        msg = "robust_percentiles values must be between 0 and 100"
        raise PaletteExtractionError(msg)

    values = pixels.astype(np.float64)
    luminance = 0.2126 * values[:, 0] + 0.7152 * values[:, 1] + 0.0722 * values[:, 2]
    order = np.argsort(luminance)
    sorted_pixels = values[order]
    colors = []
    for percentile in percentiles:
        index = int(round((percentile / 100.0) * (len(sorted_pixels) - 1)))
        colors.append(tuple(int(channel) for channel in np.rint(sorted_pixels[index]).clip(0, 255)))
    return colors[0], colors[1], colors[2]
