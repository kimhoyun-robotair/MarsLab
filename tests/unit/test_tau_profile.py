"""Unit tests for tau temporal profile functions."""

import pytest

from marslab.environment.tau_profile import (
    compute_tau,
    compute_tau_constant,
    compute_tau_ramp,
    compute_tau_sine,
)


class TestTauConstant:
    """Tests for the constant tau profile."""

    def test_returns_base_tau(self) -> None:
        assert compute_tau_constant(0.3, 0.0) == pytest.approx(0.3)
        assert compute_tau_constant(0.3, 0.5) == pytest.approx(0.3)
        assert compute_tau_constant(0.3, 1.0) == pytest.approx(0.3)

    def test_negative_tau_raises(self) -> None:
        with pytest.raises(ValueError, match="base_tau"):
            compute_tau_constant(-0.1, 0.5)


class TestTauRamp:
    """Tests for the linear ramp tau profile."""

    def test_start_value(self) -> None:
        assert compute_tau_ramp(0.3, 2.0, 0.0) == pytest.approx(0.3)

    def test_end_value(self) -> None:
        assert compute_tau_ramp(0.3, 2.0, 1.0) == pytest.approx(2.0)

    def test_midpoint(self) -> None:
        assert compute_tau_ramp(0.3, 2.0, 0.5) == pytest.approx(1.15)

    def test_decreasing_ramp(self) -> None:
        """Dissipation: start > end."""
        assert compute_tau_ramp(2.0, 0.3, 0.5) == pytest.approx(1.15)

    def test_negative_start_raises(self) -> None:
        with pytest.raises(ValueError, match="start_tau"):
            compute_tau_ramp(-0.1, 2.0, 0.5)

    def test_negative_end_raises(self) -> None:
        with pytest.raises(ValueError, match="end_tau"):
            compute_tau_ramp(0.3, -0.1, 0.5)


class TestTauSine:
    """Tests for the sinusoidal tau profile."""

    def test_at_t_zero(self) -> None:
        """sin(0) = 0, so tau = base."""
        assert compute_tau_sine(0.5, 0.3, 1.0, 0.0) == pytest.approx(0.5)

    def test_quarter_period_peak(self) -> None:
        """At t=0.25 with period=1, sin(pi/2)=1, tau = base + amplitude."""
        assert compute_tau_sine(0.5, 0.3, 1.0, 0.25) == pytest.approx(0.8)

    def test_half_period_returns_base(self) -> None:
        """At t=0.5 with period=1, sin(pi)=0, tau = base."""
        assert compute_tau_sine(0.5, 0.3, 1.0, 0.5) == pytest.approx(0.5, abs=1e-9)

    def test_non_negative_clamp(self) -> None:
        """Large amplitude can push below 0; should be clamped."""
        tau = compute_tau_sine(0.1, 0.5, 1.0, 0.75)
        assert tau >= 0.0

    def test_negative_amplitude_raises(self) -> None:
        with pytest.raises(ValueError, match="amplitude"):
            compute_tau_sine(0.5, -0.1, 1.0, 0.5)

    def test_zero_period_raises(self) -> None:
        with pytest.raises(ValueError, match="period_fraction"):
            compute_tau_sine(0.5, 0.3, 0.0, 0.5)


class TestTauDispatcher:
    """Tests for the compute_tau() dispatcher."""

    def test_constant_dispatch(self) -> None:
        assert compute_tau("constant", 0.5, base_tau=0.3) == pytest.approx(0.3)

    def test_ramp_dispatch(self) -> None:
        assert compute_tau("ramp", 1.0, start_tau=0.3, end_tau=2.0) == pytest.approx(2.0)

    def test_sine_dispatch(self) -> None:
        assert compute_tau("sine", 0.25, base_tau=0.5, amplitude=0.3, period_fraction=1.0) == (
            pytest.approx(0.8)
        )

    def test_unknown_profile_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown tau profile"):
            compute_tau("unknown", 0.5)


class TestTValidation:
    """Shared t-range validation across all profiles."""

    def test_constant_t_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="t must be"):
            compute_tau_constant(0.3, -0.1)

    def test_ramp_t_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="t must be"):
            compute_tau_ramp(0.3, 2.0, 1.1)

    def test_sine_t_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="t must be"):
            compute_tau_sine(0.5, 0.3, 1.0, -0.01)
