"""Unit tests for marslab.environment.sky_dome."""

import pytest

from marslab.environment.sky_dome import SkyDomeParams, compute_sky_dome_params


def test_butterscotch_at_low_tau():
    """Low tau sky must be butterscotch: R > G > B, R > 0.6."""
    sky = compute_sky_dome_params(0.3, "assets/mars_assets/mars_sky/")
    r, g, b = sky.base_color_rgb
    assert r > 0.6, f"R={r} not > 0.6"
    assert g > 0.4, f"G={g} not > 0.4"
    assert b < 0.5, f"B={b} not < 0.5"
    assert r > g > b, f"Expected R > G > B, got ({r}, {g}, {b})"


@pytest.mark.parametrize("tau", [0.1, 0.5, 1.0, 2.0, 3.0])
def test_brightness_positive(tau: float) -> None:
    """Brightness is always positive."""
    sky = compute_sky_dome_params(tau, "assets/mars_assets/mars_sky/")
    assert sky.brightness > 0


def test_brightness_decreases_with_tau():
    """Brightness decreases as dust increases."""
    b_low = compute_sky_dome_params(0.1, "assets/mars_assets/mars_sky/").brightness
    b_high = compute_sky_dome_params(3.0, "assets/mars_assets/mars_sky/").brightness
    assert b_low > b_high


def test_hdri_path_not_empty():
    sky = compute_sky_dome_params(0.3, "assets/mars_assets/mars_sky/")
    assert len(sky.hdri_texture_path) > 0
    assert sky.hdri_texture_path.endswith(".png")


def test_returns_sky_dome_params():
    sky = compute_sky_dome_params(0.5, "assets/mars_assets/mars_sky/")
    assert isinstance(sky, SkyDomeParams)


def test_negative_tau_raises():
    with pytest.raises(ValueError, match="tau"):
        compute_sky_dome_params(-0.1, "assets/mars_assets/mars_sky/")


@pytest.mark.parametrize("tau", [0.0, 0.3, 1.0, 3.0, 5.0])
def test_color_rgb_range(tau: float) -> None:
    """All color channels are in [0, 1]."""
    sky = compute_sky_dome_params(tau, "assets/mars_assets/mars_sky/")
    for c in sky.base_color_rgb:
        assert 0.0 <= c <= 1.0


def test_hdri_selection_by_tau():
    """Different tau ranges select different HDRI files."""
    sky_clear = compute_sky_dome_params(0.1, "hdri/")
    sky_mod = compute_sky_dome_params(1.0, "hdri/")
    sky_dusty = compute_sky_dome_params(2.0, "hdri/")
    assert "clear" in sky_clear.hdri_texture_path
    assert "moderate" in sky_mod.hdri_texture_path
    assert "dusty" in sky_dusty.hdri_texture_path
