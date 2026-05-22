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


