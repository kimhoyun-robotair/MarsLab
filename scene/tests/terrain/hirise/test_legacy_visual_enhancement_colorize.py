from __future__ import annotations

import numpy as np
import pytest
from marslab_scene.terrain.hirise.appearance.colorize import colorize_luminance_with_palette
from marslab_scene.terrain.hirise.appearance.palette import MarsPalette
from marslab_scene.terrain.hirise.config import ColorizationConfig

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]


def _palette() -> MarsPalette:
    return MarsPalette(
        shadow_rgb=(70, 32, 20),
        midtone_rgb=(150, 82, 44),
        highlight_rgb=(230, 178, 118),
        source_pixel_count=12,
        used_pixel_count=12,
        sky_rejection_applied=False,
    )


def test_colorized_albedo_is_rgb_and_not_grayscale() -> None:
    luminance = np.tile(np.linspace(0.0, 1.0, 16, dtype=np.float32), (8, 1))

    result = colorize_luminance_with_palette(
        luminance,
        _palette(),
        ColorizationConfig(),
    )

    assert result.image.shape == (8, 16, 3)
    assert result.image.dtype == np.uint8
    assert not np.array_equal(result.image[:, :, 0], result.image[:, :, 1])
    assert not np.array_equal(result.image[:, :, 1], result.image[:, :, 2])
    assert result.parameters["palette_mode"] == "reference_image"


def test_colorized_luminance_detail_is_preserved() -> None:
    luminance = np.tile(np.linspace(0.0, 1.0, 64, dtype=np.float32), (32, 1))

    result = colorize_luminance_with_palette(
        luminance,
        _palette(),
        ColorizationConfig(preserve_luminance=True, contrast=1.0, gamma=1.0),
    )

    output = result.luminance
    correlation = np.corrcoef(luminance.reshape(-1), output.reshape(-1))[0, 1]
    assert correlation > 0.97
    assert output[:, -1].mean() > output[:, 0].mean()


def test_colorized_hue_follows_palette_channels() -> None:
    luminance = np.full((12, 12), 0.5, dtype=np.float32)

    result = colorize_luminance_with_palette(
        luminance,
        _palette(),
        ColorizationConfig(saturation_scale=1.0, contrast=1.0, gamma=1.0),
    )

    mean_rgb = result.image.reshape(-1, 3).mean(axis=0)
    assert mean_rgb[0] > mean_rgb[1] > mean_rgb[2]
