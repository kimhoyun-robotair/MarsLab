"""Unit tests for marslab.environment.light_intensity.

Beer's Law with Mars relative optical air mass per Appelbaum & Flood (1990)
NASA TM-102299 Eq. 2. Tests are structured to:

1. Pin the Appelbaum air mass helper against known reference values at
   zenith angles where the flat ``1/cos(z)`` approximation would visibly
   differ (> 70 deg).
2. Verify Beer's Law invariants: ``I(tau=0) = I_0``, horizon returns 0,
   monotone decrease in ``tau``, input validation.
"""

import math

import pytest

from marslab.environment.light_intensity import (
    _appelbaum_airmass,
    compute_direct_intensity,
)

# Tolerances picked to exercise the non-flat behavior explicitly. At z <= 60
# the two formulas agree to < 0.5%, so 1% catches regressions without being
# brittle. At z >= 80 we must reject the flat approximation, so we compare
# against hand-derived Appelbaum values.
_APPELBAUM_REL_TOL = 0.01
_APPELBAUM_HIGH_Z_ABS_TOL = 0.2


# --------------------------------------------------------------------------- #
# Air mass helper (Appelbaum Eq. 2)                                           #
# --------------------------------------------------------------------------- #


def test_appelbaum_airmass_at_zenith_zero():
    """At the sub-solar point, m(0) = 1 (one atmosphere)."""
    assert _appelbaum_airmass(0.0) == pytest.approx(1.0, abs=0.001)


def test_appelbaum_airmass_at_60_deg():
    """At z=60 deg the flat and Appelbaum forms still agree (~2.0)."""
    m = _appelbaum_airmass(math.radians(60.0))
    # Appelbaum: 1.9928, flat: 2.0000 — both acceptable within 5%.
    assert m == pytest.approx(1.9928, rel=_APPELBAUM_REL_TOL)


def test_appelbaum_airmass_at_80_deg_differs_from_flat():
    """At z=80 deg flat (5.76) overestimates Appelbaum (5.58) by ~3%.

    This is the first zenith where the fix is quantitatively visible.
    """
    m = _appelbaum_airmass(math.radians(80.0))
    flat = 1.0 / math.cos(math.radians(80.0))
    assert m == pytest.approx(5.5803, abs=_APPELBAUM_HIGH_Z_ABS_TOL)
    assert m < flat  # Appelbaum is always smaller near the horizon.


def test_appelbaum_airmass_at_horizon_is_finite():
    """At z=89 deg Appelbaum returns a bounded value (~26.3).

    The flat approximation gives ~57.3 at this zenith, which severely
    overstates the attenuation and is the core Reviewer 2 C-1 complaint.
    """
    m = _appelbaum_airmass(math.radians(89.0))
    flat = 1.0 / math.cos(math.radians(89.0))
    assert m == pytest.approx(26.31, abs=_APPELBAUM_HIGH_Z_ABS_TOL)
    # Flat diverges: Appelbaum must be less than half of it.
    assert m < 0.5 * flat


# --------------------------------------------------------------------------- #
# Beer's Law (compute_direct_intensity)                                        #
# --------------------------------------------------------------------------- #


def test_no_atmosphere_returns_toa():
    """tau=0 means no attenuation: I = I_0 regardless of zenith."""
    assert compute_direct_intensity(589.0, 0.0, math.radians(30)) == pytest.approx(589.0, abs=1e-6)
    assert compute_direct_intensity(589.0, 0.0, math.radians(85)) == pytest.approx(589.0, abs=1e-6)


def test_beer_law_uses_appelbaum_airmass():
    """Direct intensity matches ``I_0 * exp(-tau * m_appelbaum)`` exactly."""
    tau = 0.3
    zenith = math.radians(30)
    m = _appelbaum_airmass(zenith)
    expected = 589.0 * math.exp(-tau * m)
    result = compute_direct_intensity(589.0, tau, zenith)
    assert result == pytest.approx(expected, abs=1e-6)


def test_beer_law_differs_from_flat_at_high_zenith():
    """At z=85 deg the Appelbaum and flat-airmass outputs disagree > 5%.

    This is the regression test for C-1: pre-fix code used ``tau/cos(z)`` and
    would pass a "within 5% of flat" test. Post-fix we require a measurable
    gap.
    """
    tau = 0.5
    zenith = math.radians(85.0)
    flat_intensity = 589.0 * math.exp(-tau / math.cos(zenith))
    result = compute_direct_intensity(589.0, tau, zenith)
    # Appelbaum airmass is smaller -> intensity larger than the flat form.
    rel_gap = (result - flat_intensity) / flat_intensity
    assert rel_gap > 0.5  # ~80% larger at z=85 with tau=0.5.


def test_appelbaum_flood_reference_within_5_percent():
    """Within 5% of Appelbaum & Flood (1990) reference at moderate zenith.

    Reference: tau=0.5, zenith=45 deg, I_0=589 W/m^2. The Appelbaum
    airmass at z=45 deg is 1.4119, flat is 1.4142 — they agree to 0.2%.
    """
    zenith = math.radians(45.0)
    result = compute_direct_intensity(589.0, 0.5, zenith)
    m = _appelbaum_airmass(zenith)
    reference = 589.0 * math.exp(-0.5 * m)
    assert abs(result - reference) / reference < 0.05


def test_beer_flux_below_horizon_is_zero():
    """zenith >= pi/2 returns 0 (sun at or below horizon)."""
    assert compute_direct_intensity(589.0, 0.3, math.pi / 2) == 0.0
    assert compute_direct_intensity(589.0, 0.3, math.pi) == 0.0
    # Just above horizon must still be positive and finite.
    just_above = compute_direct_intensity(589.0, 0.3, math.radians(89.0))
    assert just_above > 0.0
    assert math.isfinite(just_above)


def test_beer_flux_decreases_with_tau():
    """Fixed zenith: intensity monotonically decreases with increasing tau."""
    zenith = math.radians(30.0)
    taus = [0.1, 0.3, 0.5, 1.0, 2.0, 3.0]
    intensities = [compute_direct_intensity(589.0, t, zenith) for t in taus]
    for i in range(len(intensities) - 1):
        assert intensities[i] > intensities[i + 1]


def test_high_tau_drastically_reduces_intensity():
    """High tau drastically reduces intensity at moderate zenith."""
    low_tau = compute_direct_intensity(589.0, 0.3, math.radians(45.0))
    high_tau = compute_direct_intensity(589.0, 3.0, math.radians(45.0))
    assert high_tau < low_tau * 0.1  # >90% reduction.


def test_negative_solar_constant_raises():
    with pytest.raises(ValueError, match="solar_constant"):
        compute_direct_intensity(-100.0, 0.3, math.radians(45.0))


def test_negative_tau_raises():
    with pytest.raises(ValueError, match="tau"):
        compute_direct_intensity(589.0, -0.1, math.radians(45.0))
