"""Unit tests for marslab.ros2_bridge.odometry_math pure helpers."""

import numpy as np
import pytest

from marslab.quaternion import quat_inverse, quat_multiply, quat_rotate_vec
from marslab.ros2_bridge.odometry_math import compute_odom_delta, world_twist_to_body

IDENTITY = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)


def _quat_yaw(yaw_rad: float) -> np.ndarray:
    """Build a [w,x,y,z] quaternion from a yaw-only rotation."""
    half = 0.5 * yaw_rad
    return np.array([np.cos(half), 0.0, 0.0, np.sin(half)], dtype=np.float32)


class TestQuatInverse:
    def test_identity_self_inverse(self) -> None:
        np.testing.assert_array_almost_equal(quat_inverse(IDENTITY), IDENTITY)

    def test_negates_vector_part(self) -> None:
        q = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
        inv = quat_inverse(q)
        np.testing.assert_array_almost_equal(inv, [0.5, -0.5, -0.5, -0.5])

    def test_composition_gives_identity(self) -> None:
        q = _quat_yaw(np.pi / 3)
        prod = quat_multiply(q, quat_inverse(q))
        np.testing.assert_array_almost_equal(prod, IDENTITY, decimal=6)

    def test_bad_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="shape"):
            quat_inverse(np.array([1.0, 0.0, 0.0]))


class TestQuatMultiply:
    def test_identity_left(self) -> None:
        q = _quat_yaw(0.7)
        np.testing.assert_array_almost_equal(quat_multiply(IDENTITY, q), q)

    def test_identity_right(self) -> None:
        q = _quat_yaw(-1.2)
        np.testing.assert_array_almost_equal(quat_multiply(q, IDENTITY), q)

    def test_yaw_addition(self) -> None:
        q1 = _quat_yaw(np.pi / 6)
        q2 = _quat_yaw(np.pi / 4)
        expected = _quat_yaw(np.pi / 6 + np.pi / 4)
        np.testing.assert_array_almost_equal(quat_multiply(q1, q2), expected, decimal=6)

    def test_non_commutative(self) -> None:
        """Quaternion multiplication is not commutative in general."""
        q1 = np.array([0.7071, 0.7071, 0.0, 0.0], dtype=np.float32)  # 90° about X
        q2 = np.array([0.7071, 0.0, 0.7071, 0.0], dtype=np.float32)  # 90° about Y
        a = quat_multiply(q1, q2)
        b = quat_multiply(q2, q1)
        assert not np.allclose(a, b, atol=1e-4)


class TestQuatRotateVec:
    def test_identity_passthrough(self) -> None:
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        np.testing.assert_array_almost_equal(quat_rotate_vec(IDENTITY, v), v)

    def test_90deg_yaw_rotates_x_to_y(self) -> None:
        q = _quat_yaw(np.pi / 2)
        out = quat_rotate_vec(q, np.array([1.0, 0.0, 0.0]))
        np.testing.assert_array_almost_equal(out, [0.0, 1.0, 0.0], decimal=5)

    def test_z_axis_invariant_under_yaw(self) -> None:
        q = _quat_yaw(1.2)
        v = np.array([0.0, 0.0, 2.5], dtype=np.float32)
        np.testing.assert_array_almost_equal(quat_rotate_vec(q, v), v, decimal=5)

    def test_bad_vector_shape_raises(self) -> None:
        with pytest.raises(ValueError, match="vector"):
            quat_rotate_vec(IDENTITY, np.array([1.0, 2.0]))


class TestComputeOdomDelta:
    def test_zero_delta_when_still(self) -> None:
        pos = np.array([5.0, -2.0, 1.0], dtype=np.float32)
        q = _quat_yaw(0.3)
        dp, dq = compute_odom_delta(pos, q, pos, q)
        np.testing.assert_array_almost_equal(dp, [0.0, 0.0, 0.0], decimal=5)
        np.testing.assert_array_almost_equal(dq, IDENTITY, decimal=5)

    def test_pure_translation_in_world_frame_with_identity_init(self) -> None:
        init_pos = np.zeros(3, dtype=np.float32)
        init_q = IDENTITY
        cur_pos = np.array([3.0, -1.0, 0.5], dtype=np.float32)
        dp, dq = compute_odom_delta(cur_pos, IDENTITY, init_pos, init_q)
        np.testing.assert_array_almost_equal(dp, cur_pos, decimal=5)
        np.testing.assert_array_almost_equal(dq, IDENTITY, decimal=5)

    def test_rotated_init_frame(self) -> None:
        """When odom frame is rotated, world delta must be de-rotated."""
        init_pos = np.zeros(3, dtype=np.float32)
        init_q = _quat_yaw(np.pi / 2)  # odom frame rotated 90° CCW from world.
        # Rover moved +1 m along world X.
        cur_pos = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        dp, _ = compute_odom_delta(cur_pos, init_q, init_pos, init_q)
        # Odom X points along world Y, odom Y points along -world X.
        # World displacement (+1,0,0) → odom (0, -1, 0).
        np.testing.assert_array_almost_equal(dp, [0.0, -1.0, 0.0], decimal=5)

    def test_identity_init_quat_with_x_rolled_current(self) -> None:
        """Phase 2 entry-point contract: identity init_quat + X-rolled current.

        The Stage-3 entry point (``marslab/main.py``) pins
        ``init_quat_world`` to identity even when the PhysX-reported
        spawn quaternion is X-rolled (``spawn_orientation_rpy =
        [pi, 0, 0]``).  This test pins the resulting odom-frame
        quaternion equality so a future regression in the entry
        point cannot silently drop the X-roll cancellation chain
        (``odom -> Body_Chassis`` carries the X-roll, the static
        ``base_link -> Body_Chassis`` wrapper cancels it, leaving
        ``odom -> base_link`` REP-103 yaw-only).
        """
        # pi about world X-axis, scalar-first quat = (cos(pi/2), sin(pi/2), 0, 0)
        # = (0, 1, 0, 0)
        x_rolled = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
        init_pos = np.zeros(3, dtype=np.float32)
        cur_pos = np.array([2.0, 0.0, 0.0], dtype=np.float32)

        dp, dq = compute_odom_delta(cur_pos, x_rolled, init_pos, IDENTITY)

        # Identity init means the world delta passes through unchanged.
        np.testing.assert_array_almost_equal(dp, cur_pos, decimal=5)
        # Identity ⊗ X-roll = X-roll.  The X-roll surfaces on
        # odom -> Body_Chassis exactly as expected.
        np.testing.assert_array_almost_equal(dq, x_rolled, decimal=5)

    def test_identity_init_quat_passes_yaw_through_unchanged(self) -> None:
        """Identity init_quat: current yaw appears verbatim in odom delta.

        With ``init_quat_world = identity``, ``compute_odom_delta``
        reduces to ``delta_quat = identity^-1 ⊗ current = current``.
        Pinning this equality so the entry-point change in
        ``marslab/main.py`` (force identity init_quat) keeps
        delivering ROS-conventional yaw-bearing odom messages.
        """
        init_pos = np.zeros(3, dtype=np.float32)
        cur_pos = np.array([0.5, 0.5, 0.0], dtype=np.float32)
        cur_q = _quat_yaw(0.7)

        dp, dq = compute_odom_delta(cur_pos, cur_q, init_pos, IDENTITY)

        # World-frame translation passes through unchanged because
        # the rotation by identity^-1 is a no-op.
        np.testing.assert_array_almost_equal(dp, cur_pos, decimal=5)
        np.testing.assert_array_almost_equal(dq, cur_q, decimal=5)


class TestWorldTwistToBody:
    def test_identity_orientation_passthrough(self) -> None:
        lin = np.array([0.5, 0.0, 0.0], dtype=np.float32)
        ang = np.array([0.0, 0.0, 0.2], dtype=np.float32)
        lb, ab = world_twist_to_body(lin, ang, IDENTITY)
        np.testing.assert_array_almost_equal(lb, lin, decimal=6)
        np.testing.assert_array_almost_equal(ab, ang, decimal=6)

    def test_yaw_rotates_linear(self) -> None:
        """Body yaw 90° → world +X velocity appears as body +Y inversely rotated."""
        q = _quat_yaw(np.pi / 2)
        lin_world = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        lb, _ = world_twist_to_body(lin_world, np.zeros(3), q)
        # Body frame sees world +X as body -Y.
        np.testing.assert_array_almost_equal(lb, [0.0, -1.0, 0.0], decimal=5)
