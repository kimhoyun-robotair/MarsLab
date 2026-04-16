"""Unit tests for compute_sol_sun_position() — diurnal sun sweep."""

import math

import pytest

from marslab.environment.sun_position import compute_sol_sun_position


class TestSolSunPositionBoundary:
    """Boundary values at sunrise, noon, and sunset."""

    def test_sunrise_elevation_zero(self) -> None:
        """At t=0 (sunrise), elevation should be 0."""
        pos = compute_sol_sun_position(0.0)
        assert pos.elevation_deg == pytest.approx(0.0, abs=1e-9)

    def test_sunset_elevation_zero(self) -> None:
        """At t=1 (sunset), elevation should be 0."""
        pos = compute_sol_sun_position(1.0)
        assert pos.elevation_deg == pytest.approx(0.0, abs=1e-9)

    def test_noon_elevation_max(self) -> None:
        """At t=0.5 (noon), elevation should equal max_elevation_deg."""
        pos = compute_sol_sun_position(0.5, max_elevation_deg=60.0)
        assert pos.elevation_deg == pytest.approx(60.0, abs=1e-9)

    def test_sunrise_azimuth_is_start(self) -> None:
        """At t=0, azimuth should be start_azimuth_deg."""
        pos = compute_sol_sun_position(0.0, start_azimuth_deg=90.0)
        assert pos.azimuth_deg == pytest.approx(90.0, abs=1e-9)

    def test_sunset_azimuth_is_end(self) -> None:
        """At t=1, azimuth should be end_azimuth_deg."""
        pos = compute_sol_sun_position(1.0, end_azimuth_deg=270.0)
        assert pos.azimuth_deg == pytest.approx(270.0, abs=1e-9)

    def test_noon_azimuth_is_midpoint(self) -> None:
        """At t=0.5, azimuth should be midpoint of start and end."""
        pos = compute_sol_sun_position(0.5, start_azimuth_deg=90.0, end_azimuth_deg=270.0)
        assert pos.azimuth_deg == pytest.approx(180.0, abs=1e-9)


class TestSolSunPositionZenith:
    """Zenith angle consistency with elevation."""

    def test_zenith_at_noon(self) -> None:
        """Zenith angle at noon = pi/2 - max_elevation (in radians)."""
        pos = compute_sol_sun_position(0.5, max_elevation_deg=60.0)
        expected_zenith = math.pi / 2.0 - math.radians(60.0)
        assert pos.zenith_angle_rad == pytest.approx(expected_zenith, abs=1e-9)

    def test_zenith_at_sunrise(self) -> None:
        """Zenith angle at sunrise = pi/2 (sun on horizon)."""
        pos = compute_sol_sun_position(0.0)
        assert pos.zenith_angle_rad == pytest.approx(math.pi / 2.0, abs=1e-9)


class TestSolSunPositionValidation:
    """Input validation and error handling."""

    def test_t_negative_raises(self) -> None:
        with pytest.raises(ValueError, match="time_of_sol_fraction"):
            compute_sol_sun_position(-0.1)

    def test_t_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="time_of_sol_fraction"):
            compute_sol_sun_position(1.1)

    def test_max_elevation_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="max_elevation_deg"):
            compute_sol_sun_position(0.5, max_elevation_deg=0.0)

    def test_max_elevation_above_90_raises(self) -> None:
        with pytest.raises(ValueError, match="max_elevation_deg"):
            compute_sol_sun_position(0.5, max_elevation_deg=91.0)
