"""Unit tests for marslab.environment.diffuse_fraction."""

import pytest

from marslab.environment.diffuse_fraction import compute_diffuse_fraction


def test_tau_0_3_range():
    """PLAN.md criterion: tau=0.3 -> [0.29, 0.38]."""
    df = compute_diffuse_fraction(0.3)
    assert 0.29 <= df <= 0.38, f"tau=0.3: got {df}"


def test_tau_1_0_range():
    """PLAN.md criterion: tau=1.0 -> [0.50, 0.53]."""
    df = compute_diffuse_fraction(1.0)
    assert 0.50 <= df <= 0.53, f"tau=1.0: got {df}"


def test_tau_zero():
    """No dust means no diffuse scattering."""
    df = compute_diffuse_fraction(0.0)
    assert df == pytest.approx(0.0, abs=0.01)


def test_monotonic_increase():
    """Diffuse fraction increases with tau."""
    taus = [0.1, 0.3, 0.5, 1.0, 2.0, 3.0, 5.0]
    fractions = [compute_diffuse_fraction(t) for t in taus]
    for i in range(len(fractions) - 1):
        assert fractions[i] < fractions[i + 1]


def test_high_tau_approaches_one():
    """At very high tau, nearly all light is diffuse."""
    df = compute_diffuse_fraction(6.0)
    assert df > 0.90


def test_negative_tau_raises():
    with pytest.raises(ValueError, match="tau"):
        compute_diffuse_fraction(-0.1)


def test_bounded_output():
    """Output is always in [0, 1]."""
    for tau in [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 6.0]:
        df = compute_diffuse_fraction(tau)
        assert 0.0 <= df <= 1.0
