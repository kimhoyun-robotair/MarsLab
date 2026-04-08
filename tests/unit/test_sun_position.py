"""Unit tests for marslab.environment.sun_position."""

import math

import pytest

from marslab.environment.sun_position import SunPosition, compute_sun_position


def test_zenith_angle_formula():
    """zenith_angle_rad = pi/2 - radians(elevation)."""
    sp = compute_sun_position(180, 45)
    expected = math.pi / 2.0 - math.radians(45)
    assert sp.zenith_angle_rad == pytest.approx(expected, abs=1e-10)


def test_elevation_90_zenith_zero():
    """Sun at zenith: elevation=90 -> zenith_angle=0."""
    sp = compute_sun_position(0, 90)
    assert sp.zenith_angle_rad == pytest.approx(0.0, abs=1e-10)


def test_elevation_0_zenith_half_pi():
    """Sun on horizon: elevation=0 -> zenith_angle=pi/2."""
    sp = compute_sun_position(0, 0)
    assert sp.zenith_angle_rad == pytest.approx(math.pi / 2.0, abs=1e-10)


def test_returns_sun_position():
    sp = compute_sun_position(270, 30)
    assert isinstance(sp, SunPosition)
    assert sp.azimuth_deg == 270
    assert sp.elevation_deg == 30


def test_azimuth_out_of_range():
    with pytest.raises(ValueError, match="azimuth_deg"):
        compute_sun_position(-10, 45)


def test_elevation_out_of_range():
    with pytest.raises(ValueError, match="elevation_deg"):
        compute_sun_position(180, 100)


def test_boundary_values():
    """Boundary values are valid."""
    sp0 = compute_sun_position(0, 0)
    sp360 = compute_sun_position(360, 90)
    assert sp0.azimuth_deg == 0
    assert sp360.azimuth_deg == 360
