"""Module-focused tests for ``marslab.config.schema.rendering``.

R8-5 (2026-04-23). Focuses on lighting spec, sky-dome parameters, and
sun azimuth range at the module level — orthogonal to the aggregated
``test_config_schema.py`` coverage. The sun azimuth / elevation range
guards live on ``MarsEnvConfig`` (not ``RenderingConfig``) but the
``RenderingConfig.sun_*`` colour / intensity fields own their own
invariants and are covered here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from marslab.config.schema import (
    MarsEnvConfig,
    RenderingConfig,
    SkyDomeConfig,
)


class TestLightingSpec:
    """Sun light colour + intensity + angular diameter defaults."""

    def test_default_sun_color_is_mars_warm_white(self) -> None:
        """Default sun colour is slightly warm white ``[1.0, 0.95, 0.85]``."""
        cfg = RenderingConfig()
        assert cfg.sun_color == [1.0, 0.95, 0.85]

    def test_sun_color_must_have_three_channels(self) -> None:
        with pytest.raises(ValidationError):
            RenderingConfig(sun_color=[1.0, 0.5])
        with pytest.raises(ValidationError):
            RenderingConfig(sun_color=[1.0, 0.5, 0.2, 0.1])

    def test_sun_intensity_scale_must_be_positive(self) -> None:
        """``sun_intensity_scale`` is the W/m^2 to Isaac-Sim light scale.

        Negative / zero values would invert the lighting and are rejected."""
        with pytest.raises(ValidationError):
            RenderingConfig(sun_intensity_scale=0.0)
        with pytest.raises(ValidationError):
            RenderingConfig(sun_intensity_scale=-5.0)

    def test_sun_angular_diameter_range(self) -> None:
        """Mars sun apparent diameter is ~0.35 deg; schema bounds it to [0.1, 5.0]."""
        assert RenderingConfig(sun_angular_diameter_deg=0.1).sun_angular_diameter_deg == 0.1
        assert RenderingConfig(sun_angular_diameter_deg=5.0).sun_angular_diameter_deg == 5.0
        with pytest.raises(ValidationError):
            RenderingConfig(sun_angular_diameter_deg=0.05)
        with pytest.raises(ValidationError):
            RenderingConfig(sun_angular_diameter_deg=10.0)

    def test_sun_prim_path_default(self) -> None:
        """R3 migrated ``/World/SunLight`` literal into YAML."""
        assert RenderingConfig().sun_prim_path == "/World/SunLight"


class TestSkyDomeParams:
    """``SkyDomeConfig`` butterscotch clear-sky and dusty endpoints."""

    def test_butterscotch_clear_sky_ordering(self) -> None:
        """Bell et al. 2006: R > G > B at low tau (butterscotch)."""
        c = SkyDomeConfig()
        r, g, b = c.clear_rgb
        assert r > g > b, f"clear_rgb must be butterscotch ordered, got {c.clear_rgb}"

    def test_dusty_sky_brighter_than_clear(self) -> None:
        """Global dust storm endpoint must be lighter than clear."""
        c = SkyDomeConfig()
        assert sum(c.dusty_rgb) > sum(c.clear_rgb)

    def test_brightness_min_clamped_to_unit_interval(self) -> None:
        """``brightness_min`` > 1 is rejected."""
        with pytest.raises(ValidationError):
            SkyDomeConfig(brightness_min=1.01)

    def test_brightness_decay_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            SkyDomeConfig(brightness_decay=-0.01)

    def test_dome_prim_path_default(self) -> None:
        """R3 migrated ``/World/DomeLight`` literal into YAML."""
        assert RenderingConfig().dome_prim_path == "/World/DomeLight"


class TestSunAzimuthRange:
    """Sun azimuth / elevation live on ``MarsEnvConfig`` — validate
    the cross-schema boundary so a rendering test catches regression."""

    def test_default_sun_azimuth_south_at_noon(self) -> None:
        """Default 180 deg = sun due south (northern-hemisphere noon)."""
        assert MarsEnvConfig().sun_azimuth_deg == 180.0

    @pytest.mark.parametrize("az", [0.0, 90.0, 180.0, 270.0, 360.0])
    def test_sun_azimuth_accepts_full_circle(self, az: float) -> None:
        MarsEnvConfig(sun_azimuth_deg=az)

    @pytest.mark.parametrize("bad", [-1.0, 361.0, 720.0])
    def test_sun_azimuth_rejects_out_of_range(self, bad: float) -> None:
        with pytest.raises(ValidationError):
            MarsEnvConfig(sun_azimuth_deg=bad)

    def test_sun_elevation_accepts_horizon_to_zenith(self) -> None:
        assert MarsEnvConfig(sun_elevation_deg=0.0).sun_elevation_deg == 0.0
        assert MarsEnvConfig(sun_elevation_deg=90.0).sun_elevation_deg == 90.0

    def test_sun_elevation_rejects_below_horizon(self) -> None:
        with pytest.raises(ValidationError):
            MarsEnvConfig(sun_elevation_deg=-5.0)

    def test_sun_elevation_rejects_above_zenith(self) -> None:
        with pytest.raises(ValidationError):
            MarsEnvConfig(sun_elevation_deg=100.0)
