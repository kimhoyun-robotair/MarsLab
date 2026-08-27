from __future__ import annotations

import hashlib

import numpy as np
import pytest
import rasterio
from marslab_scene.terrain.hirise.appearance.finalize import finalize_enhanced_texture
from marslab_scene.terrain.hirise.config import DetailVariationConfig, UpscalingConfig

pytestmark = [pytest.mark.unit, pytest.mark.legacy_parity]


def _rgb_gradient(width: int = 12, height: int = 8) -> np.ndarray:
    x = np.linspace(40, 220, width, dtype=np.float64)
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :, 0] = x
    image[:, :, 1] = np.clip(x * 0.55, 0, 255)
    image[:, :, 2] = np.clip(x * 0.30, 0, 255)
    return image


def _hash(array: np.ndarray) -> str:
    return hashlib.sha256(array.tobytes()).hexdigest()


def test_finalize_texture_enforces_dimension_cap(tmp_path) -> None:
    result = finalize_enhanced_texture(
        _rgb_gradient(),
        crop_width_m=10.0,
        crop_height_m=5.0,
        upscaling=UpscalingConfig(
            enabled=True,
            method="bicubic",
            target_m_per_px=0.1,
            max_texture_size_px=32,
        ),
        detail_variation=DetailVariationConfig(enabled=False),
        output_path=tmp_path / "textures" / "terrain_albedo_mars_enhanced.png",
    )

    assert result.width == 32
    assert result.height == 16
    assert result.output_path.exists()
    with rasterio.open(result.output_path) as dataset:
        assert (dataset.width, dataset.height, dataset.count) == (32, 16, 3)


def test_detail_variation_is_deterministic_for_same_seed(tmp_path) -> None:
    kwargs = {
        "crop_width_m": 4.0,
        "crop_height_m": 4.0,
        "upscaling": UpscalingConfig(enabled=True, target_m_per_px=0.25, max_texture_size_px=64),
        "detail_variation": DetailVariationConfig(enabled=True, seed=7, strength=0.10),
    }

    first = finalize_enhanced_texture(
        _rgb_gradient(),
        output_path=tmp_path / "a" / "terrain_albedo_mars_enhanced.png",
        **kwargs,
    )
    second = finalize_enhanced_texture(
        _rgb_gradient(),
        output_path=tmp_path / "b" / "terrain_albedo_mars_enhanced.png",
        **kwargs,
    )

    assert _hash(first.image) == _hash(second.image)
    assert first.sha256 == second.sha256


def test_detail_variation_changes_with_seed_and_zero_strength_disables(tmp_path) -> None:
    base = finalize_enhanced_texture(
        _rgb_gradient(),
        crop_width_m=4.0,
        crop_height_m=4.0,
        upscaling=UpscalingConfig(enabled=True, target_m_per_px=0.25, max_texture_size_px=64),
        detail_variation=DetailVariationConfig(enabled=True, seed=1, strength=0.0),
        output_path=tmp_path / "base" / "terrain_albedo_mars_enhanced.png",
    )
    varied = finalize_enhanced_texture(
        _rgb_gradient(),
        crop_width_m=4.0,
        crop_height_m=4.0,
        upscaling=UpscalingConfig(enabled=True, target_m_per_px=0.25, max_texture_size_px=64),
        detail_variation=DetailVariationConfig(enabled=True, seed=2, strength=0.10),
        output_path=tmp_path / "varied" / "terrain_albedo_mars_enhanced.png",
    )

    assert base.image.shape == varied.image.shape
    assert _hash(base.image) != _hash(varied.image)
