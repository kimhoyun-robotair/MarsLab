"""Unit tests for marslab.environment.light_intensity."""

import math

import pytest

from marslab.environment.light_intensity import compute_direct_intensity


def test_no_atmosphere():
    """tau=0 means no attenuation: I = I_0."""
    result = compute_direct_intensity(589, 0.0, math.radians(30))
    assert result == pytest.approx(589.0, abs=1e-6)


def test_beer_law_formula():
    """Verify Beer's Law: I = I_0 * exp(-tau / cos(theta_z))."""
    tau = 0.3
    zenith = math.radians(30)
    expected = 589 * math.exp(-tau / math.cos(zenith))
    result = compute_direct_intensity(589, tau, zenith)
    assert result == pytest.approx(expected, abs=1e-6)


def test_appelbaum_flood_reference():
    """Within 5% of Appelbaum & Flood (1990) reference values.

    Reference: tau=0.5, zenith=45deg, I_0=589 W/m^2
    Expected: 589 * exp(-0.5/cos(45deg)) = 589 * exp(-0.707) ≈ 290 W/m^2
    """
    zenith = math.radians(45)
    result = compute_direct_intensity(589, 0.5, zenith)
    reference = 589 * math.exp(-0.5 / math.cos(zenith))
    assert abs(result - reference) / reference < 0.05


def test_sun_below_horizon():
    """zenith >= pi/2 returns 0 (sun at or below horizon)."""
    assert compute_direct_intensity(589, 0.3, math.pi / 2) == 0.0
    assert compute_direct_intensity(589, 0.3, math.pi) == 0.0


def test_high_tau():
    """High tau drastically reduces intensity."""
    low_tau = compute_direct_intensity(589, 0.3, math.radians(45))
    high_tau = compute_direct_intensity(589, 3.0, math.radians(45))
    assert high_tau < low_tau * 0.1  # >90% reduction


def test_negative_solar_constant_raises():
    with pytest.raises(ValueError, match="solar_constant"):
        compute_direct_intensity(-100, 0.3, math.radians(45))


def test_negative_tau_raises():
    with pytest.raises(ValueError, match="tau"):
        compute_direct_intensity(589, -0.1, math.radians(45))


def test_multiple_tau_values():
    """Intensity monotonically decreases with increasing tau."""
    zenith = math.radians(30)
    taus = [0.1, 0.3, 0.5, 1.0, 2.0, 3.0]
    intensities = [compute_direct_intensity(589, t, zenith) for t in taus]
    for i in range(len(intensities) - 1):
        assert intensities[i] > intensities[i + 1]
