"""Unit tests for marslab.robots.rover_control — Ackermann steering controller."""

import numpy as np
import pytest

from marslab.robots.rover_control import ackermann_command

# Perseverance rover geometry (URDF measured).
WB = 2.26  # wheelbase (m)
TS = 2.125  # track_steer (m)
TM = 2.369  # track_middle (m)
R = 0.2667  # wheel_radius (m)


class TestAckermannStraight:
    """Straight-line motion (w ≈ 0)."""

    def test_forward(self) -> None:
        steer, vel = ackermann_command(1.0, 0.0, WB, TS, TM, R)
        np.testing.assert_array_almost_equal(steer, [0, 0, 0, 0])
        expected_omega = 1.0 / R
        np.testing.assert_array_almost_equal(vel, [expected_omega] * 6, decimal=4)

    def test_reverse(self) -> None:
        steer, vel = ackermann_command(-0.5, 0.0, WB, TS, TM, R)
        np.testing.assert_array_almost_equal(steer, [0, 0, 0, 0])
        expected_omega = -0.5 / R
        np.testing.assert_array_almost_equal(vel, [expected_omega] * 6, decimal=4)

    def test_zero(self) -> None:
        steer, vel = ackermann_command(0.0, 0.0, WB, TS, TM, R)
        np.testing.assert_array_almost_equal(steer, [0, 0, 0, 0])
        np.testing.assert_array_almost_equal(vel, [0, 0, 0, 0, 0, 0])


class TestAckermannPointTurn:
    """Point turn (v ≈ 0, w ≠ 0): ICR at rover center."""

    def test_ccw_steer_nonzero(self) -> None:
        """CCW (w > 0): all steer angles must be nonzero."""
        steer, vel = ackermann_command(0.0, 1.0, WB, TS, TM, R)
        assert all(abs(s) > 0.01 for s in steer), f"Expected nonzero steer, got {steer}"

    def test_ccw_left_backward_right_forward(self) -> None:
        """CCW (w > 0): left wheels backward, right wheels forward."""
        _, vel = ackermann_command(0.0, 1.0, WB, TS, TM, R)
        # vel order: [LF, LM, LR, RF, RM, RR]
        assert vel[0] < 0, f"LF should be negative, got {vel[0]}"
        assert vel[1] < 0, f"LM should be negative, got {vel[1]}"
        assert vel[2] < 0, f"LR should be negative, got {vel[2]}"
        assert vel[3] > 0, f"RF should be positive, got {vel[3]}"
        assert vel[4] > 0, f"RM should be positive, got {vel[4]}"
        assert vel[5] > 0, f"RR should be positive, got {vel[5]}"

    def test_cw_opposite_of_ccw(self) -> None:
        """CW (w < 0): velocities should be negated vs CCW."""
        _, vel_ccw = ackermann_command(0.0, 1.0, WB, TS, TM, R)
        _, vel_cw = ackermann_command(0.0, -1.0, WB, TS, TM, R)
        np.testing.assert_array_almost_equal(vel_cw, -vel_ccw, decimal=4)


class TestAckermannCurve:
    """Curved motion (v ≠ 0, w ≠ 0)."""

    def test_left_turn_inner_slower(self) -> None:
        """Left turn (w > 0): inner (left) wheels slower than outer (right)."""
        _, vel = ackermann_command(2.0, 0.5, WB, TS, TM, R)
        # vel: [LF, LM, LR, RF, RM, RR]
        # Left = inner, Right = outer for left turn
        assert abs(vel[0]) < abs(vel[3]), "LF should be slower than RF"
        assert abs(vel[1]) < abs(vel[4]), "LM should be slower than RM"

    def test_left_turn_all_forward(self) -> None:
        """Left turn with v > 0: all wheels should roll forward."""
        _, vel = ackermann_command(2.0, 0.5, WB, TS, TM, R)
        assert all(v > 0 for v in vel), f"All vels should be positive, got {vel}"

    def test_right_turn_symmetry(self) -> None:
        """Right turn should be mirror of left turn."""
        steer_l, vel_l = ackermann_command(2.0, 0.5, WB, TS, TM, R)
        steer_r, vel_r = ackermann_command(2.0, -0.5, WB, TS, TM, R)
        # Steer: LF↔RF, LR↔RR should swap and negate.
        # steer order: [LF, LR, RF, RR]
        np.testing.assert_almost_equal(steer_r[0], -steer_l[2], decimal=4)
        np.testing.assert_almost_equal(steer_r[2], -steer_l[0], decimal=4)
        np.testing.assert_almost_equal(steer_r[1], -steer_l[3], decimal=4)
        np.testing.assert_almost_equal(steer_r[3], -steer_l[1], decimal=4)
        # Vel: LF↔RF, LM↔RM, LR↔RR should swap.
        np.testing.assert_almost_equal(vel_r[0], vel_l[3], decimal=4)
        np.testing.assert_almost_equal(vel_r[3], vel_l[0], decimal=4)
        np.testing.assert_almost_equal(vel_r[1], vel_l[4], decimal=4)
        np.testing.assert_almost_equal(vel_r[4], vel_l[1], decimal=4)

    def test_front_rear_steer_opposite_sign(self) -> None:
        """Front and rear steer angles should have opposite signs."""
        steer, _ = ackermann_command(2.0, 0.5, WB, TS, TM, R)
        # steer: [LF, LR, RF, RR]
        # LF (front) and LR (rear) should be opposite sign
        assert (
            steer[0] * steer[1] < 0
        ), f"LF ({steer[0]}) and LR ({steer[1]}) should have opposite signs"
        assert (
            steer[2] * steer[3] < 0
        ), f"RF ({steer[2]}) and RR ({steer[3]}) should have opposite signs"


class TestAckermannEuclidean:
    """Euclidean distance-based wheel velocity properties."""

    def test_front_rear_faster_than_middle_on_curve(self) -> None:
        """Front/rear wheels are farther from ICR than middle → faster."""
        _, vel = ackermann_command(2.0, 0.5, WB, TS, TM, R)
        # LF (front, x_w != 0) should be faster than LM (middle, x_w = 0)
        # on the same (left) side, because LF has longitudinal offset.
        assert abs(vel[0]) > abs(
            vel[1]
        ), f"LF ({abs(vel[0]):.4f}) should be faster than LM ({abs(vel[1]):.4f})"

    def test_middle_wheels_same_as_linear_approx(self) -> None:
        """Middle wheels (x_w=0): Euclidean reduces to |w*(R-y_w)/r|."""
        _, vel = ackermann_command(2.0, 0.5, WB, TS, TM, R)
        v, w = 2.0, 0.5
        r_turn = v / w
        # LM: y_w = +TM/2
        expected_lm = w * (r_turn - TM / 2.0) / R
        np.testing.assert_almost_equal(vel[1], expected_lm, decimal=4)

    def test_point_turn_front_faster_than_middle(self) -> None:
        """Point turn: front/rear wheels farther from center → faster."""
        _, vel = ackermann_command(0.0, 1.0, WB, TS, TM, R)
        # LF (has x-offset from ICR) should be faster than LM (no x-offset)
        assert abs(vel[0]) > abs(
            vel[1]
        ), f"LF ({abs(vel[0]):.4f}) should be faster than LM ({abs(vel[1]):.4f})"


class TestAckermannShapes:
    """Output shape and dtype."""

    def test_steer_shape(self) -> None:
        steer, _ = ackermann_command(1.0, 0.5, WB, TS, TM, R)
        assert steer.shape == (4,)
        assert steer.dtype == np.float32

    def test_vel_shape(self) -> None:
        _, vel = ackermann_command(1.0, 0.5, WB, TS, TM, R)
        assert vel.shape == (6,)
        assert vel.dtype == np.float32


class TestAckermannTightTurn:
    """Regression for reviewer 2 audit 05§C1 — tight turn where R < half_ts.

    Under the old ``np.arctan(x_w / dy)`` form, ``dy = R - y_w`` silently
    dropped its sign when crossing zero, landing inside-wheel steer angles
    in the wrong quadrant.  Switching to ``np.arctan2(x_w, dy)`` plus a
    ±π wrap keeps steer in the mechanically-reachable (-π/2, π/2]
    principal range while preserving the original ``copysign(w * dy)``
    drive-velocity sign.
    """

    def test_r_below_half_track_no_pi_flip(self) -> None:
        """R = half_ts / 2 → inside LF wheel: continuous, no ±π jump."""
        half_ts = TS / 2.0
        # Pick v, w so that R = half_ts / 2 = 0.53125 < half_ts = 1.0625.
        w = 1.0
        v = (half_ts / 2.0) * w
        steer, vel = ackermann_command(v, w, WB, TS, TM, R)
        # steer order: [LF, LR, RF, RR]
        # Inside wheels (LF, LR) are past the ICR laterally → dy < 0.
        # Post-wrap, every steer angle must remain in (-π/2, π/2].
        assert np.all(np.abs(steer) <= np.pi / 2.0 + 1e-6), (
            f"Tight turn produced out-of-range steer {steer} (must stay in "
            f"±π/2 after principal-range wrap)."
        )
        # LF and LR share x-sign only as front/rear mirror, so their
        # magnitudes should be approximately equal and nonzero.
        assert abs(steer[0]) > 0.1, f"LF steer should be nontrivial, got {steer[0]}"
        assert abs(steer[1]) > 0.1, f"LR steer should be nontrivial, got {steer[1]}"
        # Drive velocities must still be finite and nonzero.
        assert np.all(np.isfinite(vel)) and np.any(np.abs(vel) > 1e-3)

    def test_r_below_half_track_diagonal_consistency(self) -> None:
        """Diagonal wheels (LF vs RR) must keep consistent signs at tight R."""
        w = 1.0
        v = (TS / 4.0) * w  # R = half_ts / 2
        steer, _ = ackermann_command(v, w, WB, TS, TM, R)
        # steer order: [LF, LR, RF, RR]
        # LF (inside-front) and RR (outside-rear) are diagonal — in the
        # principal range they share sign (both positive for CCW).
        assert (
            steer[0] * steer[3] > 0
        ), f"Diagonal LF ({steer[0]}) and RR ({steer[3]}) must share sign for CCW tight turn."

    def test_r_below_half_track_matches_arctan2_wrapped(self) -> None:
        """Numerical check: inside wheel equals arctan2(x, dy) wrapped by π."""
        w = 1.0
        v = (TS / 4.0) * w  # R = 0.53125
        r_icr = v / w
        steer, _ = ackermann_command(v, w, WB, TS, TM, R)
        half_wb, half_ts = WB / 2.0, TS / 2.0
        # Manual principal-range arctan2 for LF:
        raw = np.arctan2(+half_wb, r_icr - (+half_ts))  # dy < 0 here
        if raw > np.pi / 2.0:
            raw -= np.pi
        elif raw < -np.pi / 2.0:
            raw += np.pi
        np.testing.assert_almost_equal(steer[0], raw, decimal=5)


class TestAckermannZeroLateralOffset:
    """dy == 0 branch: arctan(x/0) → NaN; arctan2(x, 0) → ±π/2."""

    def test_dy_zero_gives_half_pi(self) -> None:
        """When R coincides with a wheel's y coordinate, steer = +π/2."""
        # Choose v, w such that R = v/w = +half_ts (LF/LR lateral coord).
        half_ts = TS / 2.0
        w = 0.5
        v = half_ts * w
        steer, vel = ackermann_command(v, w, WB, TS, TM, R)
        # LF sits at (+half_wb, +half_ts), dy = R - y_w = 0.
        # x_w > 0 → steer = +π/2.
        np.testing.assert_almost_equal(steer[0], np.pi / 2.0, decimal=5)
        # LR sits at (-half_wb, +half_ts), dy = 0, x_w < 0 → steer = -π/2.
        np.testing.assert_almost_equal(steer[1], -np.pi / 2.0, decimal=5)
        assert np.all(np.isfinite(steer)), f"Steer must be finite, got {steer}"
        assert np.all(np.isfinite(vel)), f"Vel must be finite, got {vel}"


class TestAckermannSymmetricTurnDirection:
    """Left/right turn steer magnitudes must be symmetric at every radius,
    including the tight-turn regime that exposed the arctan bug."""

    @pytest.mark.parametrize("v, w", [(0.5, 1.0), (0.1, 1.0), (0.0, 1.0)])
    def test_left_right_magnitudes_match(self, v: float, w: float) -> None:
        steer_l, _ = ackermann_command(v, +w, WB, TS, TM, R)
        steer_r, _ = ackermann_command(v, -w, WB, TS, TM, R)
        # Pairwise mirrored: LF↔RF, LR↔RR should have equal magnitude.
        np.testing.assert_almost_equal(abs(steer_l[0]), abs(steer_r[2]), decimal=5)
        np.testing.assert_almost_equal(abs(steer_l[1]), abs(steer_r[3]), decimal=5)
        np.testing.assert_almost_equal(abs(steer_l[2]), abs(steer_r[0]), decimal=5)
        np.testing.assert_almost_equal(abs(steer_l[3]), abs(steer_r[1]), decimal=5)


class TestAckermannValidation:
    """Parameter validation."""

    @pytest.mark.parametrize(
        "wb,ts,tm,r,match",
        [
            (0.0, TS, TM, R, "wheelbase"),
            (WB, -1.0, TM, R, "track_steer"),
            (WB, TS, TM, 0.0, "wheel_radius"),
        ],
        ids=["zero_wheelbase", "negative_track_steer", "zero_wheel_radius"],
    )
    def test_invalid_geometry_raises(
        self, wb: float, ts: float, tm: float, r: float, match: str
    ) -> None:
        with pytest.raises(ValueError, match=match):
            ackermann_command(1.0, 0.0, wb, ts, tm, r)
