"""Unit tests for terrain material albedo validation."""

import pytest


def test_mars_albedo_range_valid():
    """Mars surface albedo is in [0.10, 0.40]."""
    albedo_min, albedo_max = 0.10, 0.40
    assert 0.0 <= albedo_min < albedo_max <= 1.0


def test_mars_albedo_from_config():
    """Schema default albedo range matches Mars values."""
    from marslab.config.schema import MarsEnvConfig

    config = MarsEnvConfig()
    a_min, a_max = config.surface_albedo_range
    assert 0.10 <= a_min <= 0.20
    assert 0.30 <= a_max <= 0.50
    assert a_min < a_max


def test_albedo_inverted_range_raises():
    """Inverted albedo range raises ValidationError."""
    from pydantic import ValidationError

    from marslab.config.schema import MarsEnvConfig

    with pytest.raises(ValidationError):
        MarsEnvConfig(surface_albedo_range=(0.5, 0.1))


def test_mars_regolith_color_derivation():
    """Albedo-derived color is reddish-brown (R > G > B)."""
    import numpy as np

    albedo = 0.25  # mid-range
    color = np.array([albedo * 2.5, albedo * 1.8, albedo * 1.2])
    color = np.clip(color, 0.0, 1.0)
    assert color[0] > color[1] > color[2]  # R > G > B
    assert all(0.0 <= c <= 1.0 for c in color)


def test_albedo_boundary_colors():
    """Colors at boundary albedo values are still valid."""
    import numpy as np

    for albedo in [0.10, 0.40]:
        color = np.array([albedo * 2.5, albedo * 1.8, albedo * 1.2])
        color = np.clip(color, 0.0, 1.0)
        assert all(0.0 <= c <= 1.0 for c in color)
