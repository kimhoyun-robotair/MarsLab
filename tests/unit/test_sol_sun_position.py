"""Unit tests for ``compute_sol_sun_position()``.

Coverage splits into three groups:

* ``TestSolSunPositionLinear``: pre-refactor first-order approximation,
  invoked explicitly with ``mode="linear"``. Retained as regression
  tests for the legacy envelope so future edits to the helper do not
  silently change linear behaviour that downstream tooling may still
  compare against.
* ``TestSolSunPositionSpherical``: new Reviewer-2 fix. Exercises the
  standard spherical-astronomy identities (Allison & McEwen 2000) and
  validates Jezero-crater sun paths against textbook values.
* ``TestSolSunPositionValidation``: shared input-validation contract.
"""

import math

import pytest

from marslab.environment.sun_position import (
    DEFAULT_LATITUDE_DEG,
    MARS_OBLIQUITY_DEG,
    compute_sol_sun_position,
    solar_declination_deg,
)


class TestSolSunPositionLinear:
    """Legacy linear-mode envelope (``mode='linear'``)."""

    def test_sunrise_elevation_zero(self) -> None:
        """At t=0 (sunrise), linear-mode elevation is 0."""
        pos = compute_sol_sun_position(0.0, mode="linear")
        assert pos.elevation_deg == pytest.approx(0.0, abs=1e-9)

    def test_sunset_elevation_zero(self) -> None:
        """At t=1 (sunset), linear-mode elevation is 0."""
        pos = compute_sol_sun_position(1.0, mode="linear")
        assert pos.elevation_deg == pytest.approx(0.0, abs=1e-9)

    def test_noon_elevation_max(self) -> None:
        """At t=0.5 (noon), elevation equals max_elevation_deg."""
        pos = compute_sol_sun_position(0.5, max_elevation_deg=60.0, mode="linear")
        assert pos.elevation_deg == pytest.approx(60.0, abs=1e-9)

    def test_sunrise_azimuth_is_start(self) -> None:
        """At t=0, azimuth is start_azimuth_deg (linear envelope)."""
        pos = compute_sol_sun_position(0.0, start_azimuth_deg=90.0, mode="linear")
        assert pos.azimuth_deg == pytest.approx(90.0, abs=1e-9)

    def test_sunset_azimuth_is_end(self) -> None:
        """At t=1, azimuth is end_azimuth_deg (linear envelope)."""
        pos = compute_sol_sun_position(1.0, end_azimuth_deg=270.0, mode="linear")
        assert pos.azimuth_deg == pytest.approx(270.0, abs=1e-9)

    def test_noon_azimuth_is_midpoint(self) -> None:
        """At t=0.5, azimuth is the midpoint of start and end (linear)."""
        pos = compute_sol_sun_position(
            0.5, start_azimuth_deg=90.0, end_azimuth_deg=270.0, mode="linear"
        )
        assert pos.azimuth_deg == pytest.approx(180.0, abs=1e-9)

    def test_zenith_at_linear_noon(self) -> None:
        """Linear zenith at noon matches pi/2 - radians(max_elevation)."""
        pos = compute_sol_sun_position(0.5, max_elevation_deg=60.0, mode="linear")
        expected_zenith = math.pi / 2.0 - math.radians(60.0)
        assert pos.zenith_angle_rad == pytest.approx(expected_zenith, abs=1e-9)

    def test_zenith_at_linear_sunrise(self) -> None:
        """Linear zenith at sunrise matches pi/2 (sun on horizon)."""
        pos = compute_sol_sun_position(0.0, mode="linear")
        assert pos.zenith_angle_rad == pytest.approx(math.pi / 2.0, abs=1e-9)


class TestSolSunPositionSpherical:
    """Spherical-trig mode (default). Reviewer-2 Item #8 fix."""

    def test_transit_elevation_at_equator_equinox_is_90(self) -> None:
        """Equator (phi=0), Ls=0 (delta=0): transit puts sun at zenith.

        This is the textbook ``90 - |phi - delta|`` identity, degenerating
        to 90 deg when both latitude and declination are zero.
        """
        pos = compute_sol_sun_position(0.5, latitude_deg=0.0, ls_deg=0.0)
        assert pos.elevation_deg == pytest.approx(90.0, abs=1e-6)

    def test_transit_azimuth_north_hemisphere_equinox_is_south(self) -> None:
        """Jezero at equinox transit: sun due south (az=180 deg).

        Verifies the spherical formula reduces to the intuitive result
        when ``delta=0`` and the observer sits in the northern hemisphere.
        """
        pos = compute_sol_sun_position(0.5)  # defaults: Jezero, Ls=0
        assert pos.azimuth_deg == pytest.approx(180.0, abs=1e-6)

    def test_nighttime_elevation_is_zero_clamped(self) -> None:
        """Sub-horizon samples clamp to elevation_deg=0 for lighting code."""
        # Jezero midnight: sin(el) = -cos(phi), well below horizon.
        pos = compute_sol_sun_position(0.0)
        assert pos.elevation_deg == 0.0

    def test_sunrise_sunset_symmetric_around_transit(self) -> None:
        """Elevation symmetric, azimuth sums to 360 deg, at t=0.5 +/- dx.

        At equinox the sun path is a great circle mirror-symmetric about
        local solar noon, so el(0.5 - x) = el(0.5 + x) and azimuths sum
        to 360 deg (one east of south, one west of south).
        """
        for dx in (0.05, 0.1, 0.2):
            p_minus = compute_sol_sun_position(0.5 - dx)
            p_plus = compute_sol_sun_position(0.5 + dx)
            assert p_minus.elevation_deg == pytest.approx(p_plus.elevation_deg, abs=1e-6)
            assert (p_minus.azimuth_deg + p_plus.azimuth_deg) == pytest.approx(360.0, abs=1e-6)

    def test_ls_90_summer_solstice_matches_obliquity_identity(self) -> None:
        """Jezero Ls=90 (N summer solstice) transit elevation.

        delta(Ls=90) = obliquity = 25.19 deg. phi = 18.44 deg. Since
        delta > phi the sun passes north of zenith at transit and
        elevation = 90 - (delta - phi) = 90 - 6.75 = 83.25 deg.
        Azimuth should snap to 0 (due north) with numerical rounding.
        """
        pos = compute_sol_sun_position(0.5, ls_deg=90.0)
        expected_el = 90.0 - (MARS_OBLIQUITY_DEG - DEFAULT_LATITUDE_DEG)
        assert pos.elevation_deg == pytest.approx(expected_el, abs=1e-4)
        # az=0 and az=360 are both acceptable here (modulo 360).
        assert pos.azimuth_deg == pytest.approx(0.0, abs=1e-4) or pos.azimuth_deg == pytest.approx(
            360.0, abs=1e-4
        )

    def test_pole_latitude_summer_elevation_equals_declination(self) -> None:
        """North pole at Ls=90: sun stays at elevation = declination.

        At phi=90 the formula collapses to sin(el) = sin(delta) so the
        sun is at a constant elevation equal to the declination, for
        every hour angle. This is the Martian polar-summer sanity check.
        """
        expected_el = solar_declination_deg(90.0)
        for t in (0.1, 0.3, 0.5, 0.7, 0.9):
            pos = compute_sol_sun_position(t, latitude_deg=90.0, ls_deg=90.0)
            assert pos.elevation_deg == pytest.approx(expected_el, abs=1e-4)

    def test_linear_and_spherical_disagree_on_azimuth_at_jezero(self) -> None:
        """Regression guard: the fix actually changes the default output.

        If someone reverts ``compute_sol_sun_position`` to the linear
        default, this test fails. Picks t=0.25 where the linear
        envelope gives az=135 deg while spherical astronomy gives a
        value closer to ~100 deg (east-of-south, sigmoid toward transit).
        """
        p_sph = compute_sol_sun_position(0.25)
        p_lin = compute_sol_sun_position(0.25, mode="linear")
        assert abs(p_sph.azimuth_deg - p_lin.azimuth_deg) > 15.0

    def test_solar_declination_helper_bounds(self) -> None:
        """``solar_declination_deg`` is a sine wave of amplitude obliquity."""
        assert solar_declination_deg(0.0) == pytest.approx(0.0, abs=1e-12)
        assert solar_declination_deg(90.0) == pytest.approx(MARS_OBLIQUITY_DEG, abs=1e-12)
        assert solar_declination_deg(180.0) == pytest.approx(0.0, abs=1e-10)
        assert solar_declination_deg(270.0) == pytest.approx(-MARS_OBLIQUITY_DEG, abs=1e-12)


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

    def test_unknown_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            compute_sol_sun_position(0.5, mode="bogus")  # type: ignore[arg-type]

    def test_latitude_out_of_range_raises(self) -> None:
        with pytest.raises(ValueError, match="latitude_deg"):
            compute_sol_sun_position(0.5, latitude_deg=100.0)
