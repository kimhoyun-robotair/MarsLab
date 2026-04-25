"""Unit tests for ``sun_position_from_utc()`` and the JD/MSD/Ls helpers.

The wrapper layered on top of ``compute_sol_sun_position`` implements
the Allison & McEwen (2000) UTC -> Mars Sol Date -> Local Mean Solar
Time -> spherical-trig sun position pipeline. Reference values come
from:

* Allison & McEwen (2000), Planet. Space Sci. 48 (2-3), 215-235,
  Table 6 (J2000 reference epoch + 2000-01-06 reference sample).
* The NASA GISS Mars24 Sunclock algorithm document
  (https://www.giss.nasa.gov/tools/mars24/help/algorithm.html), which
  lists the canonical numerical constants used here.
* Published Mars surface mission landing Ls values (Spirit, Opportunity,
  Curiosity, Perseverance) cross-referenced against
  https://mars.nasa.gov/ mission landing reports.

Tolerances:

* MSD: ``abs=1e-2`` (~ 1.5 minute LMST drift). Comfortable inside the
  Mars24 0.001 sol claimed precision; loose enough that leap-second
  drift outside the modelled epoch does not break the test.
* Ls : ``abs=1.0 deg``. Matches the truncated harmonic series we keep
  (the missing higher-order PBS terms contribute < 0.01 deg, but the
  rounded landing-time references above are themselves only quoted
  to ~0.5 deg).
* Sun elevation: ``abs=2.0 deg``. Reflects the spherical-mode
  declination approximation (``delta = 25.19 sin(Ls)``) which is
  good to ~1 deg over the orbit.
"""

import math
from datetime import datetime, timedelta, timezone

import pytest

from marslab.environment.sun_position import (
    SunPosition,
    julian_date_to_mars_sol_date,
    mars_areocentric_longitude_deg,
    mars_sol_date_to_local_solar_time_fraction,
    sun_position_from_utc,
    utc_to_julian_date,
)

# ---------------------------------------------------------------------------
# Step-by-step pipeline checks
# ---------------------------------------------------------------------------


class TestUtcToJulianDate:
    """JD computation for a few well-known UTC instants."""

    def test_unix_epoch(self) -> None:
        """1970-01-01 00:00:00 UTC has JD = 2440587.5 by definition."""
        dt = datetime(1970, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert utc_to_julian_date(dt) == pytest.approx(2440587.5, abs=1e-9)

    def test_j2000_civil(self) -> None:
        """2000-01-01 12:00:00 UTC is JD_UT = 2451545.0 (within the dUT1 ~ 0 s)."""
        dt = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert utc_to_julian_date(dt) == pytest.approx(2451545.0, abs=1e-9)

    def test_naive_datetime_rejected(self) -> None:
        """Naive datetimes must be rejected -- silent UTC assumption is a footgun."""
        with pytest.raises(TypeError):
            utc_to_julian_date(datetime(2024, 1, 1, 0, 0, 0))

    def test_non_utc_tz_rejected(self) -> None:
        """Non-UTC timezones must be rejected to keep the contract explicit."""
        kst = timezone(timedelta(hours=9))
        with pytest.raises(ValueError):
            utc_to_julian_date(datetime(2024, 1, 1, 9, 0, 0, tzinfo=kst))


class TestJulianDateToMsd:
    """MSD reference values from Allison & McEwen (2000)."""

    def test_allison_mcewen_2000_01_06(self) -> None:
        """2000-01-06 00:00 UTC -> MSD ~ 44796.0 (Allison & McEwen 2000 Table 6)."""
        dt = datetime(2000, 1, 6, 0, 0, 0, tzinfo=timezone.utc)
        jd = utc_to_julian_date(dt)
        msd = julian_date_to_mars_sol_date(jd)
        # Allison & McEwen Table 6: MSD at this reference epoch is 44795.99955.
        # Our 37 s leap-second offset (vs the 32 s used in the original
        # 2000-era table) shifts MSD by +5/86400 ~ +5.8e-5 sol, which is
        # well inside the 1e-2 tolerance.
        assert msd == pytest.approx(44796.0, abs=1e-2)

    def test_msd_increases_one_per_sol(self) -> None:
        """Two UTC samples 88775.245 s apart (one Mars sol) differ by ~1 MSD."""
        dt0 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        # Mars sidereal sol = 88775.245 s? Mars solar day = 88775.244 s on
        # average per Allison & McEwen (sidereal sol = 88642.66 s).
        # Use the synodic value because MSD counts solar days.
        dt1 = dt0 + timedelta(seconds=88775.244)
        jd0 = utc_to_julian_date(dt0)
        jd1 = utc_to_julian_date(dt1)
        msd0 = julian_date_to_mars_sol_date(jd0)
        msd1 = julian_date_to_mars_sol_date(jd1)
        assert (msd1 - msd0) == pytest.approx(1.0, abs=1e-3)


class TestLocalSolarTimeFraction:
    """LMST = (MTC + lambda_E * 24/360) mod 24, normalised to [0, 1)."""

    def test_airy_zero_longitude_matches_mtc(self) -> None:
        """At longitude 0 (Airy-0) the local frac equals MTC / 24."""
        msd = 44797.25  # MTC = 6.0 hours
        frac = mars_sol_date_to_local_solar_time_fraction(msd, 0.0)
        assert frac == pytest.approx(0.25, abs=1e-12)

    def test_eastern_observer_sees_earlier_clock_relative_to_airy(self) -> None:
        """+90 east of Airy-0 is +6 hours ahead of MTC."""
        msd = 44797.0  # MTC = 0.0
        frac_east = mars_sol_date_to_local_solar_time_fraction(msd, 90.0)
        # MTC=0 + 6 h offset -> LMST = 6 h -> frac = 0.25
        assert frac_east == pytest.approx(0.25, abs=1e-12)

    def test_western_observer_sees_later_clock(self) -> None:
        """-90 east (i.e. 90 west) of Airy-0 is -6 hours -> LMST = 18 h."""
        msd = 44797.0  # MTC = 0.0
        frac_west = mars_sol_date_to_local_solar_time_fraction(msd, -90.0)
        assert frac_west == pytest.approx(0.75, abs=1e-12)

    def test_longitude_wraparound(self) -> None:
        """Longitudes outside [0, 360) are reduced modulo 360."""
        msd = 44797.0
        frac_a = mars_sol_date_to_local_solar_time_fraction(msd, 90.0)
        frac_b = mars_sol_date_to_local_solar_time_fraction(msd, 90.0 + 360.0)
        assert frac_a == pytest.approx(frac_b, abs=1e-12)


class TestAreocentricLongitude:
    """Ls reference values from published Mars surface mission landings.

    All five values are taken from the Mars24 algorithm sample output /
    NASA mission press kits and verified against the Mars24 web tool
    snapshots. Tolerances are loose (1 deg) because (a) the rounded
    references above only specify Ls to ~0.5 deg and (b) the truncated
    perturber series keeps us within ~0.5 deg of full Mars24.
    """

    LANDING_EVENTS = [
        # (label, year, month, day, hour, minute, expected_ls_deg)
        ("Spirit", 2004, 1, 4, 4, 35, 327.5),
        ("Opportunity", 2004, 1, 25, 4, 54, 339.1),
        ("Curiosity", 2012, 8, 6, 5, 17, 150.74),
        ("Perseverance", 2021, 2, 18, 20, 55, 5.49),
    ]

    @pytest.mark.parametrize("label,y,mo,d,h,mi,ls_expected", LANDING_EVENTS)
    def test_landing_ls(
        self,
        label: str,
        y: int,
        mo: int,
        d: int,
        h: int,
        mi: int,
        ls_expected: float,
    ) -> None:
        """Landing-time Ls must match the published mission value within 1 deg."""
        dt = datetime(y, mo, d, h, mi, 0, tzinfo=timezone.utc)
        jd_ut = utc_to_julian_date(dt)
        jd_tt = jd_ut + (37.0 + 32.184) / 86400.0
        ls = mars_areocentric_longitude_deg(jd_tt)
        # Wrap-around safe distance on the 360-deg circle.
        gap = min(abs(ls - ls_expected), 360.0 - abs(ls - ls_expected))
        assert gap < 1.0, f"{label}: got Ls={ls:.3f}, expected ~{ls_expected}"


# ---------------------------------------------------------------------------
# End-to-end wrapper checks
# ---------------------------------------------------------------------------


class TestSunPositionFromUtc:
    """End-to-end ``sun_position_from_utc`` behaviour."""

    def test_returns_sunposition(self) -> None:
        """Returns a ``SunPosition`` with sane field types."""
        dt = datetime(2024, 7, 20, 12, 0, 0, tzinfo=timezone.utc)
        pos = sun_position_from_utc(dt, latitude_deg=18.44, longitude_deg=77.45)
        assert isinstance(pos, SunPosition)
        assert 0.0 <= pos.azimuth_deg < 360.0
        assert 0.0 <= pos.elevation_deg <= 90.0
        assert pos.zenith_angle_rad == pytest.approx(
            math.pi / 2.0 - math.radians(pos.elevation_deg), abs=1e-12
        )

    def test_sun_below_horizon_clamped_to_zero(self) -> None:
        """Local midnight should produce elevation == 0 (sub-horizon clamp).

        Pick a UTC moment such that LMST at Jezero (77.45 deg E) is ~ 0 h,
        i.e. local midnight. We do that by reading the MSD-derived
        fraction directly and shifting -- this is the same pipeline the
        wrapper uses, so the test stays independent of leap-second
        drift while still exercising the clamp.
        """
        # Pick *any* UTC moment; we step in 1-hour increments looking for
        # a Jezero LMST near midnight.
        for hour in range(24):
            dt = datetime(2024, 5, 15, hour, 0, 0, tzinfo=timezone.utc)
            jd = utc_to_julian_date(dt)
            msd = julian_date_to_mars_sol_date(jd)
            frac = mars_sol_date_to_local_solar_time_fraction(msd, 77.45)
            if frac < 0.02 or frac > 0.98:
                pos = sun_position_from_utc(dt, 18.44, 77.45)
                assert pos.elevation_deg == pytest.approx(0.0, abs=1e-9)
                return
        pytest.fail("no UTC sample landed near Jezero local midnight")

    def test_high_elevation_at_local_noon_jezero_summer(self) -> None:
        """At Jezero local noon during northern summer, sun is high.

        Jezero phi ~ 18.44, obliquity 25.19, so peak elevation at
        Ls=90 (northern summer solstice) is 90 - (phi - obliquity) ~
        96.75 -> clamped at 90 minus a few deg of declination jitter.
        """
        # Find a UTC moment where Jezero LMST is ~ noon AND Ls is
        # near 90. Walk one Mars year (668 sols ~ 687 Earth days) in
        # daily steps -- this is cheap.
        target_dt = None
        for day in range(0, 800):
            dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(days=day)
            jd = utc_to_julian_date(dt)
            msd = julian_date_to_mars_sol_date(jd)
            frac = mars_sol_date_to_local_solar_time_fraction(msd, 77.45)
            jd_tt = jd + (37.0 + 32.184) / 86400.0
            ls = mars_areocentric_longitude_deg(jd_tt)
            if abs(frac - 0.5) < 0.02 and abs(ls - 90.0) < 5.0:
                target_dt = dt
                break
        assert target_dt is not None, "no Jezero noon-at-Ls=90 match found"
        pos = sun_position_from_utc(target_dt, 18.44, 77.45)
        # Northern summer solstice peak elevation ~ 90 - |phi - obliq| ~
        # 90 - 6.75 ~ 83.25. Allow 5 deg slack for hour-angle rounding.
        assert pos.elevation_deg > 78.0
        # Sun is roughly overhead -- azimuth is poorly conditioned at
        # high elevation; just assert it stays inside [0, 360).
        assert 0.0 <= pos.azimuth_deg < 360.0

    def test_invalid_latitude_rejected(self) -> None:
        """Latitude outside [-90, 90] raises ValueError."""
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            sun_position_from_utc(dt, latitude_deg=120.0, longitude_deg=0.0)

    def test_invalid_ls_override_rejected(self) -> None:
        """ls_override_deg outside [0, 360) raises ValueError."""
        dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError):
            sun_position_from_utc(dt, latitude_deg=0.0, longitude_deg=0.0, ls_override_deg=400.0)

    def test_ls_override_fixes_season(self) -> None:
        """Supplying ls_override_deg pins the solar declination.

        Two UTC moments six Earth months apart should give different
        elevations naturally, but identical declinations when both are
        called with ``ls_override_deg=0`` (vernal equinox).
        """
        # Both at Jezero LMST ~ noon (frac ~ 0.5). Use ls_override=0 -> delta=0.
        # At local noon, equinox elevation = 90 - |phi| = 90 - 18.44 = 71.56.
        # Find two UTC moments at Jezero local noon:
        noons = []
        for day in range(0, 200):
            dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(days=day)
            jd = utc_to_julian_date(dt)
            msd = julian_date_to_mars_sol_date(jd)
            frac = mars_sol_date_to_local_solar_time_fraction(msd, 77.45)
            if abs(frac - 0.5) < 0.005:
                noons.append(dt)
                if len(noons) == 2 and (noons[1] - noons[0]).days > 60:
                    break
        assert len(noons) >= 2, "did not find two Jezero local-noon UTC samples"
        pos_a = sun_position_from_utc(
            noons[0], latitude_deg=18.44, longitude_deg=77.45, ls_override_deg=0.0
        )
        pos_b = sun_position_from_utc(
            noons[-1], latitude_deg=18.44, longitude_deg=77.45, ls_override_deg=0.0
        )
        # With Ls forced to 0 (delta = 0) and both samples at LMST ~ noon,
        # elevation should match within the LMST snap tolerance (~ 1 deg).
        assert abs(pos_a.elevation_deg - pos_b.elevation_deg) < 2.0
        # And both should be near the equinox-noon prediction 90 - 18.44.
        assert pos_a.elevation_deg == pytest.approx(71.56, abs=2.0)
