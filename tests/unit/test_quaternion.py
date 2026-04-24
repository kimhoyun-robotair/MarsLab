"""Unit tests for marslab.math.quaternion helpers ([w,x,y,z] convention)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from marslab.math import quaternion as qm
from marslab.math.quaternion import (
    quat_inverse,
    quat_multiply,
    quat_rotate_vec,
    quat_to_rpy,
    rpy_to_quat,
)

# Tolerances — float32 storage means we cannot demand 1e-12.
ATOL = 1e-6
RPY_ATOL = 1e-5


# ---------------------------------------------------------------------------
# quat_inverse
# ---------------------------------------------------------------------------


def test_quat_inverse_identity_is_identity() -> None:
    """Inverse of identity quaternion is the identity itself."""
    identity = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    inv = quat_inverse(identity)
    np.testing.assert_allclose(inv, identity, atol=ATOL)


def test_quat_inverse_compose_is_identity() -> None:
    """``q ⊗ q⁻¹`` yields identity for a unit quaternion (90° Z-axis)."""
    # 90° rotation about Z: [cos(45°), 0, 0, sin(45°)].
    half = math.pi / 4.0
    q = np.array([math.cos(half), 0.0, 0.0, math.sin(half)], dtype=np.float32)
    q_inv = quat_inverse(q)
    composed = quat_multiply(q, q_inv)
    identity = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    np.testing.assert_allclose(composed, identity, atol=ATOL)


def test_quat_inverse_shape_validation() -> None:
    """Wrong-shape inputs raise ``ValueError`` (scalar-first enforced)."""
    with pytest.raises(ValueError, match="shape"):
        quat_inverse(np.array([1.0, 0.0, 0.0], dtype=np.float32))
    with pytest.raises(ValueError, match="shape"):
        quat_inverse(np.array([[1.0, 0.0, 0.0, 0.0]], dtype=np.float32))


def test_quat_inverse_scalar_first_negates_vector_part() -> None:
    """Scalar-first convention: inverse keeps ``w`` and negates ``[x,y,z]``."""
    q = np.array([0.5, 0.1, 0.2, 0.3], dtype=np.float32)
    inv = quat_inverse(q)
    assert inv[0] == pytest.approx(0.5, abs=ATOL)
    assert inv[1] == pytest.approx(-0.1, abs=ATOL)
    assert inv[2] == pytest.approx(-0.2, abs=ATOL)
    assert inv[3] == pytest.approx(-0.3, abs=ATOL)


# ---------------------------------------------------------------------------
# quat_multiply
# ---------------------------------------------------------------------------


def test_quat_multiply_identity_right() -> None:
    """Right-multiplying by identity leaves ``q`` unchanged."""
    q = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    identity = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    result = quat_multiply(q, identity)
    np.testing.assert_allclose(result, q, atol=ATOL)


def test_quat_multiply_two_90_z_is_180_z() -> None:
    """Two 90° Z-axis rotations compose into a 180° Z-axis rotation."""
    half = math.pi / 4.0
    q_90 = np.array([math.cos(half), 0.0, 0.0, math.sin(half)], dtype=np.float32)
    q_180_expected = np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    q_180_actual = quat_multiply(q_90, q_90)
    np.testing.assert_allclose(q_180_actual, q_180_expected, atol=ATOL)


def test_quat_multiply_non_commutative() -> None:
    """Hamilton product is non-commutative for generic quaternions."""
    # 90° about X, 90° about Y — distinct rotations.
    half = math.pi / 4.0
    q_x = np.array([math.cos(half), math.sin(half), 0.0, 0.0], dtype=np.float32)
    q_y = np.array([math.cos(half), 0.0, math.sin(half), 0.0], dtype=np.float32)
    xy = quat_multiply(q_x, q_y)
    yx = quat_multiply(q_y, q_x)
    # They must differ by more than the floating-point tolerance.
    assert not np.allclose(xy, yx, atol=1e-3)


# ---------------------------------------------------------------------------
# quat_rotate_vec
# ---------------------------------------------------------------------------


def test_quat_rotate_vec_identity_preserves_vector() -> None:
    """Identity quaternion leaves any vector unchanged."""
    identity = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    rotated = quat_rotate_vec(identity, v)
    np.testing.assert_allclose(rotated, v, atol=ATOL)


def test_quat_rotate_vec_90_z_maps_x_to_y() -> None:
    """A 90° Z-axis rotation maps ``[1,0,0]`` to ``[0,1,0]``."""
    half = math.pi / 4.0
    q = np.array([math.cos(half), 0.0, 0.0, math.sin(half)], dtype=np.float32)
    v = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    rotated = quat_rotate_vec(q, v)
    np.testing.assert_allclose(rotated, np.array([0.0, 1.0, 0.0]), atol=1e-5)


def test_quat_rotate_vec_180_x_flips_y() -> None:
    """A 180° X-axis rotation maps ``[0,1,0]`` to ``[0,-1,0]``."""
    q = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # 180° about X
    v = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    rotated = quat_rotate_vec(q, v)
    np.testing.assert_allclose(rotated, np.array([0.0, -1.0, 0.0]), atol=1e-5)


def test_quat_rotate_vec_rejects_wrong_shape() -> None:
    """Non-3-vector inputs raise ``ValueError``."""
    identity = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    with pytest.raises(ValueError, match="shape"):
        quat_rotate_vec(identity, np.array([1.0, 2.0], dtype=np.float32))


# ---------------------------------------------------------------------------
# rpy_to_quat
# ---------------------------------------------------------------------------


def test_rpy_to_quat_zero_is_identity() -> None:
    """(0, 0, 0) RPY maps to the identity quaternion."""
    w, x, y, z = rpy_to_quat(0.0, 0.0, 0.0)
    assert (w, x, y, z) == pytest.approx((1.0, 0.0, 0.0, 0.0), abs=ATOL)


def test_rpy_to_quat_roll_half_pi() -> None:
    """(π/2, 0, 0) maps to ``[cos(π/4), sin(π/4), 0, 0]``."""
    w, x, y, z = rpy_to_quat(math.pi / 2.0, 0.0, 0.0)
    expected = (math.cos(math.pi / 4.0), math.sin(math.pi / 4.0), 0.0, 0.0)
    assert (w, x, y, z) == pytest.approx(expected, abs=ATOL)


def test_rpy_to_quat_returns_unit_norm() -> None:
    """Any RPY input produces a unit-norm quaternion."""
    samples = [
        (0.1, 0.2, 0.3),
        (-0.7, 1.1, -0.4),
        (math.pi / 3.0, -math.pi / 5.0, math.pi / 6.0),
    ]
    for roll, pitch, yaw in samples:
        w, x, y, z = rpy_to_quat(roll, pitch, yaw)
        norm = math.sqrt(w * w + x * x + y * y + z * z)
        assert norm == pytest.approx(1.0, abs=ATOL)


# ---------------------------------------------------------------------------
# quat_to_rpy
# ---------------------------------------------------------------------------


def test_quat_to_rpy_identity_is_zero() -> None:
    """Identity quaternion decodes to RPY (0, 0, 0)."""
    roll, pitch, yaw = quat_to_rpy(np.array([1.0, 0.0, 0.0, 0.0]))
    assert (roll, pitch, yaw) == pytest.approx((0.0, 0.0, 0.0), abs=ATOL)


def test_quat_to_rpy_roundtrip_three_axis() -> None:
    """``quat_to_rpy(rpy_to_quat(r,p,y))`` recovers the original RPY.

    Sampled away from the gimbal-lock boundary (``|pitch| < π/2``).
    Uses dot-product > 0.9999 to sidestep the ``q``/``-q`` double cover.
    """
    samples = [
        (0.0, 0.0, 0.0),
        (0.1, -0.2, 0.3),
        (-0.5, 0.4, -0.6),
        (math.pi / 4.0, math.pi / 6.0, -math.pi / 3.0),
    ]
    for roll, pitch, yaw in samples:
        w, x, y, z = rpy_to_quat(roll, pitch, yaw)
        q = np.array([w, x, y, z], dtype=np.float64)
        r_rt, p_rt, y_rt = quat_to_rpy(q)
        # Compare recovered quaternion to input (handles double cover).
        w2, x2, y2, z2 = rpy_to_quat(r_rt, p_rt, y_rt)
        q_rt = np.array([w2, x2, y2, z2], dtype=np.float64)
        dot = abs(float(np.dot(q, q_rt)))
        assert dot > 0.9999, (
            f"roundtrip mismatch: input=({roll},{pitch},{yaw}) "
            f"out=({r_rt},{p_rt},{y_rt}) dot={dot}"
        )


def test_quat_to_rpy_shape_validation() -> None:
    """Non-(4,) quaternion input raises ``ValueError``."""
    with pytest.raises(ValueError, match="shape"):
        quat_to_rpy(np.array([1.0, 0.0, 0.0]))


# ---------------------------------------------------------------------------
# Convention / documentation invariants
# ---------------------------------------------------------------------------


def test_module_docstring_declares_scalar_first() -> None:
    """Module docstring must explicitly declare the scalar-first convention.

    This is a cross-surface contract: Isaac Sim articulation pose API and
    ``geometry_msgs/Quaternion`` both expect ``[w, x, y, z]``; consumers
    reading the docstring must see this guarantee.
    """
    doc = qm.__doc__ or ""
    assert "scalar-first" in doc.lower()
    assert "[w, x, y, z]" in doc
