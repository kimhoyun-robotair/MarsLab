"""Mars-like colorization from orthomosaic luminance and a reference palette."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import JsonValue

from marslab_scene.terrain.hirise.appearance.palette import MarsPalette
from marslab_scene.terrain.hirise.config import ColorizationConfig


class ColorizationError(ValueError):
    """Raised when visual enhancement colorization cannot be completed."""


@dataclass(frozen=True, slots=True)
class ColorizedAlbedo:
    """RGB albedo image and the parameters used to generate it."""

    image: np.ndarray
    luminance: np.ndarray
    parameters: dict[str, JsonValue]


def colorize_luminance_with_palette(
    luminance: np.ndarray,
    palette: MarsPalette,
    config: ColorizationConfig,
) -> ColorizedAlbedo:
    """Generate an RGB Mars-like albedo image from normalized luminance."""
    normalized = _prepare_luminance(luminance)
    adjusted = _adjust_luminance(
        normalized,
        contrast=config.contrast,
        gamma=config.gamma,
    )
    rgb = _palette_map(
        adjusted,
        shadow=np.asarray(palette.shadow_rgb, dtype=np.float64) / 255.0,
        midtone=np.asarray(palette.midtone_rgb, dtype=np.float64) / 255.0,
        highlight=np.asarray(palette.highlight_rgb, dtype=np.float64) / 255.0,
        shadow_strength=config.shadow_strength,
        midtone_strength=config.midtone_strength,
        highlight_strength=config.highlight_strength,
    )
    rgb = _scale_saturation(rgb, config.saturation_scale)
    if config.preserve_luminance:
        rgb = _preserve_luminance(rgb, adjusted)

    image = np.clip(np.rint(rgb * 255.0), 0, 255).astype(np.uint8)
    return ColorizedAlbedo(
        image=image,
        luminance=_rgb_luminance(image).astype(np.float32),
        parameters={
            "palette_mode": config.palette_mode,
            "preserve_luminance": config.preserve_luminance,
            "shadow_strength": config.shadow_strength,
            "midtone_strength": config.midtone_strength,
            "highlight_strength": config.highlight_strength,
            "saturation_scale": config.saturation_scale,
            "contrast": config.contrast,
            "gamma": config.gamma,
            "palette": {
                "shadow_rgb": list(palette.shadow_rgb),
                "midtone_rgb": list(palette.midtone_rgb),
                "highlight_rgb": list(palette.highlight_rgb),
            },
        },
    )


def _prepare_luminance(luminance: np.ndarray) -> np.ndarray:
    values = np.asarray(luminance, dtype=np.float64)
    if values.ndim != 2:
        msg = "luminance must be a 2D array"
        raise ColorizationError(msg)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        msg = "luminance contains no finite values"
        raise ColorizationError(msg)
    values = np.where(np.isfinite(values), values, float(np.nanmedian(finite)))
    min_value = float(np.min(values))
    max_value = float(np.max(values))
    if min_value < 0.0 or max_value > 1.0:
        if max_value <= min_value:
            return np.zeros(values.shape, dtype=np.float64)
        values = (values - min_value) / (max_value - min_value)
    return np.clip(values, 0.0, 1.0)


def _adjust_luminance(luminance: np.ndarray, *, contrast: float, gamma: float) -> np.ndarray:
    if contrast <= 0.0:
        msg = "colorization.contrast must be > 0"
        raise ColorizationError(msg)
    if gamma <= 0.0:
        msg = "colorization.gamma must be > 0"
        raise ColorizationError(msg)
    contrasted = np.clip((luminance - 0.5) * contrast + 0.5, 0.0, 1.0)
    return np.power(contrasted, 1.0 / gamma)


def _palette_map(
    luminance: np.ndarray,
    *,
    shadow: np.ndarray,
    midtone: np.ndarray,
    highlight: np.ndarray,
    shadow_strength: float,
    midtone_strength: float,
    highlight_strength: float,
) -> np.ndarray:
    color = np.empty((*luminance.shape, 3), dtype=np.float64)

    low = luminance <= 0.30
    low_t = np.divide(luminance, 0.30, out=np.zeros_like(luminance), where=low)
    color[low] = _mix(shadow * shadow_strength, midtone * midtone_strength, low_t[low])

    mid = (luminance > 0.30) & (luminance <= 0.75)
    mid_t = (luminance - 0.30) / 0.45
    color[mid] = _mix(midtone * midtone_strength, highlight * highlight_strength, mid_t[mid])

    high = luminance > 0.75
    high_t = (luminance - 0.75) / 0.25
    color[high] = _mix(highlight * highlight_strength, highlight, high_t[high])

    return np.clip(color, 0.0, 1.0)


def _mix(left: np.ndarray, right: np.ndarray, t: np.ndarray) -> np.ndarray:
    weights = np.asarray(t, dtype=np.float64)[..., np.newaxis]
    return left * (1.0 - weights) + right * weights


def _scale_saturation(rgb: np.ndarray, saturation_scale: float) -> np.ndarray:
    if saturation_scale < 0.0:
        msg = "colorization.saturation_scale must be >= 0"
        raise ColorizationError(msg)
    luminance = _rgb_luminance_float(rgb)[..., np.newaxis]
    return np.clip(luminance + (rgb - luminance) * saturation_scale, 0.0, 1.0)


def _preserve_luminance(rgb: np.ndarray, target_luminance: np.ndarray) -> np.ndarray:
    current = _rgb_luminance_float(rgb)
    scale = np.divide(
        target_luminance,
        current,
        out=np.ones_like(target_luminance),
        where=current > 1.0e-6,
    )
    return np.clip(rgb * scale[..., np.newaxis], 0.0, 1.0)


def _rgb_luminance(image: np.ndarray) -> np.ndarray:
    values = image.astype(np.float64) / 255.0
    return _rgb_luminance_float(values)


def _rgb_luminance_float(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
