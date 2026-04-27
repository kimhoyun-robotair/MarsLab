"""Unit tests for marslab.environment.diffuse_fraction.

The module ships a **1-D cartoon approximation** of COMIMART
(Vicente-Retortillo et al. 2015). These tests encode both the
acceptance bands and the Rayleigh-floor regression bounds.
"""

import pytest

from marslab.environment.diffuse_fraction import (
    compute_diffuse_fraction,
    compute_diffuse_fraction_1d_approx,
)


def test_tau_0_3_range():
    """tau=0.3 -> [0.29, 0.38]."""
    df = compute_diffuse_fraction_1d_approx(0.3)
    assert 0.29 <= df <= 0.38, f"tau=0.3: got {df}"


def test_tau_1_0_range():
    """tau=1.0 -> [0.50, 0.53]."""
    df = compute_diffuse_fraction_1d_approx(1.0)
    assert 0.50 <= df <= 0.53, f"tau=1.0: got {df}"


def test_tau_zero_has_rayleigh_floor():
    """tau=0 is NOT zero: Mars CO2 atmosphere has a Rayleigh floor ~0.10.

    Post-audit regression (§C-2): the pre-audit table used [0.0, 0.0]
    which is unphysical for a molecular atmosphere. We now require a
    non-zero diffuse fraction at tau=0 and pin it close to 0.10.
    """
    df = compute_diffuse_fraction_1d_approx(0.0)
    assert df == pytest.approx(0.10, abs=0.02)


def test_monotonic_increase():
    """Diffuse fraction increases with tau."""
    taus = [0.1, 0.3, 0.5, 1.0, 2.0, 3.0, 5.0]
    fractions = [compute_diffuse_fraction_1d_approx(t) for t in taus]
    for i in range(len(fractions) - 1):
        assert fractions[i] < fractions[i + 1]


def test_high_tau_approaches_one():
    """At very high tau, nearly all light is diffuse."""
    df = compute_diffuse_fraction_1d_approx(6.0)
    assert df > 0.90


def test_negative_tau_raises():
    with pytest.raises(ValueError, match="tau"):
        compute_diffuse_fraction_1d_approx(-0.1)


def test_bounded_output():
    """Output is always in [0, 1]."""
    for tau in [0.0, 0.1, 0.5, 1.0, 2.0, 5.0, 6.0]:
        df = compute_diffuse_fraction_1d_approx(tau)
        assert 0.0 <= df <= 1.0


# ---------------------------------------------------------------------------
# Diffuse-fraction regression tests
# ---------------------------------------------------------------------------


def test_diffuse_fraction_monotonic_in_tau():
    """Regression: dense tau sweep must be strictly non-decreasing.

    Guards against any future table edit that introduces a local dip.
    """
    taus = [i * 0.1 for i in range(61)]  # 0.0, 0.1, ..., 6.0
    fractions = [compute_diffuse_fraction_1d_approx(t) for t in taus]
    for prev, nxt in zip(fractions, fractions[1:], strict=False):
        assert prev <= nxt + 1e-12, f"non-monotonic step: {prev} -> {nxt} in tau sweep"


def test_diffuse_fraction_nonzero_at_tau_zero():
    """Regression: tau=0 must stay above a Rayleigh floor of 0.05.

    The pre-audit implementation returned exactly 0.0 at tau=0, which
    broke both the physics (CO2 Rayleigh scattering always produces a
    small diffuse component) and downstream sky-dome intensity scaling
    (``dome_intensity *= diffuse_fraction`` went to zero at low opacity).
    """
    df = compute_diffuse_fraction_1d_approx(0.0)
    assert df >= 0.05, f"tau=0 below Rayleigh floor: got {df}"


def test_diffuse_fraction_saturates_at_high_tau():
    """Regression: tau >= 3 must yield diffuse_fraction >= 0.80.

    High-opacity scenarios (paper tau-sweep endpoints at tau=4) should
    be dominated by diffuse light; guards against accidental truncation
    of the upper table end.
    """
    for tau in [3.0, 4.0, 5.0, 6.0]:
        df = compute_diffuse_fraction_1d_approx(tau)
        assert df >= 0.80, f"tau={tau}: expected >= 0.80, got {df}"


# ---------------------------------------------------------------------------
# Backward-compat alias
# ---------------------------------------------------------------------------


def test_deprecated_alias_matches_new_function():
    """``compute_diffuse_fraction`` must delegate to the 1-D approx fn."""
    for tau in [0.0, 0.3, 1.0, 2.0, 4.0]:
        assert compute_diffuse_fraction(tau) == compute_diffuse_fraction_1d_approx(tau)


def test_zenith_hook_is_accepted_but_ignored():
    """v1.0: zenith_rad is accepted but must not change the result.

    Documents the forward-compatibility contract; when the v2.0 2-D
    model lands this test will be replaced with zenith-dependent
    assertions.
    """
    base = compute_diffuse_fraction_1d_approx(1.0)
    for z in [0.0, 0.5, 1.0, 1.3]:
        assert compute_diffuse_fraction_1d_approx(1.0, zenith_rad=z) == base
