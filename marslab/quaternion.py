"""Pure-NumPy quaternion algebra and ZYX RPY conversion.

All quaternions in this module use the **scalar-first** ``[w, x, y, z]``
convention, matching:

* Isaac Sim's articulation pose API,
* ROS2 ``geometry_msgs/Quaternion`` field order (w, x, y, z),
* URDF / ROS ZYX intrinsic RPY convention for
  :func:`rpy_to_quat` and :func:`quat_to_rpy`.

Every function is deterministic, side-effect free, and NumPy-only so
``tests/unit/`` can validate the module headlessly (offline-first
testing principle).

This module is the single source of truth for quaternion helpers:

* ``marslab.ros2_bridge.odometry_math`` (quat_inverse / quat_multiply /
  quat_rotate_vec) re-exports from here.
* ``marslab.robots.rover`` (rpy_to_quat) re-exports from here.
* Stage 3 runtime scripts import ``rpy_to_quat`` from here directly.

Dtype policy
------------
The helpers do not force-cast inputs to ``float32``. Isaac Sim's
articulation APIs return ``float64`` arrays; an ``astype(float32)``
on every call would create one fresh allocation per quaternion
operation (>=400 allocations/sec at 200 Hz on the main runtime loop)
and would silently downgrade runtime precision for odometry math.
Inputs are converted with ``np.asarray`` only (no copy when the dtype
already matches) and the resulting dtype is inherited from the input —
so ``float64 in -> float64 out`` and ``float32 in -> float32 out``.
"""

from __future__ import annotations

import logging
from typing import Tuple

import numpy as np

_logger = logging.getLogger(__name__)

#: Tolerance above which :func:`quat_inverse` warns that its input is not a
#: unit quaternion. ``norm^2`` is compared against ``1`` so the threshold is
#: dimensionless; ``1e-3`` flags ~0.05% drift, safely above float32 noise
#: (~6e-8) but well below values that would silently break odometry math.
_UNIT_QUAT_NORM_SQ_TOL = 1e-3


def quat_inverse(q: np.ndarray) -> np.ndarray:
    """Return the inverse of a unit quaternion ``[w, x, y, z]``.

    For a unit quaternion the inverse equals the conjugate: negate the
    vector part, keep the scalar. The caller is responsible for keeping
    ``q`` unit-norm; this function does **not** renormalise, but it does
    emit a ``WARNING`` via :mod:`logging` when ``|q|^2`` deviates from
    ``1`` by more than :data:`_UNIT_QUAT_NORM_SQ_TOL`. The returned
    value is still the conjugate — callers that observe the warning
    should renormalise their upstream state rather than rely on this
    helper to paper over drift.

    Args:
        q: Shape ``(4,)`` quaternion with scalar-first ordering.

    Returns:
        Shape ``(4,)`` inverse quaternion. Dtype is inherited from ``q``
        (``np.asarray`` never copies when the dtype already matches).

    Raises:
        ValueError: If ``q`` does not have shape ``(4,)``.
    """
    q = np.asarray(q)
    if q.shape != (4,):
        raise ValueError(f"quaternion must have shape (4,), got {q.shape}")
    norm_sq = float(np.sum(q * q))
    if abs(norm_sq - 1.0) > _UNIT_QUAT_NORM_SQ_TOL:
        _logger.warning(
            "quat_inverse: non-unit quaternion norm^2=%.6f; "
            "returning conjugate (not true inverse). Renormalise upstream.",
            norm_sq,
        )
    return np.array([q[0], -q[1], -q[2], -q[3]], dtype=q.dtype)


def quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Hamilton product ``q1 ⊗ q2`` of two ``[w, x, y, z]`` quaternions.

    Args:
        q1: Left operand, shape ``(4,)``.
        q2: Right operand, shape ``(4,)``.

    Returns:
        Shape ``(4,)`` product quaternion. Dtype is the NumPy promotion
        of ``q1.dtype`` and ``q2.dtype`` (``float64`` when either input
        is ``float64``).

    Raises:
        ValueError: If either input does not have shape ``(4,)``.
    """
    q1 = np.asarray(q1)
    q2 = np.asarray(q2)
    if q1.shape != (4,) or q2.shape != (4,):
        raise ValueError(f"quaternions must have shape (4,), got {q1.shape} and {q2.shape}")
    out_dtype = np.result_type(q1.dtype, q2.dtype)
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ],
        dtype=out_dtype,
    )


def quat_rotate_vec(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate a 3-vector by a ``[w, x, y, z]`` quaternion.

    Computes ``q ⊗ [0, v] ⊗ q⁻¹`` and returns the vector part.  ``q``
    is assumed to be unit-norm (not re-normalised here).

    Args:
        q: Rotation quaternion, shape ``(4,)``.
        v: Vector to rotate, shape ``(3,)``.

    Returns:
        Rotated vector, shape ``(3,)``. Dtype is the NumPy promotion of
        ``q.dtype`` and ``v.dtype``.

    Raises:
        ValueError: If ``v`` does not have shape ``(3,)`` (shape check on
            ``q`` is delegated to :func:`quat_inverse`).
    """
    v = np.asarray(v)
    if v.shape != (3,):
        raise ValueError(f"vector must have shape (3,), got {v.shape}")
    q_arr = np.asarray(q)
    out_dtype = np.result_type(q_arr.dtype, v.dtype)
    v_quat = np.array([0.0, v[0], v[1], v[2]], dtype=out_dtype)
    q_inv = quat_inverse(q_arr)
    result = quat_multiply(quat_multiply(q_arr, v_quat), q_inv)
    return result[1:4]


def rpy_to_quat(roll: float, pitch: float, yaw: float) -> Tuple[float, float, float, float]:
    """Convert roll-pitch-yaw (radians) to quaternion ``(w, x, y, z)``.

    Uses the ZYX intrinsic convention (yaw around Z, then pitch around
    Y, then roll around X) which is the URDF / ROS standard.  Pure
    Python floats out so the result is JSON-serialisable and Isaac-Sim
    ``Xformable`` orient APIs accept it directly.

    Args:
        roll: Rotation about X (radians).
        pitch: Rotation about Y (radians).
        yaw: Rotation about Z (radians).

    Returns:
        ``(w, x, y, z)`` tuple, scalar-first, each a Python ``float``.
    """
    cr, sr = np.cos(roll / 2.0), np.sin(roll / 2.0)
    cp, sp = np.cos(pitch / 2.0), np.sin(pitch / 2.0)
    cy, sy = np.cos(yaw / 2.0), np.sin(yaw / 2.0)

    w = cr * cp * cy + sr * sp * sy
    x = sr * cp * cy - cr * sp * sy
    y = cr * sp * cy + sr * cp * sy
    z = cr * cp * sy - sr * sp * cy
    return float(w), float(x), float(y), float(z)


def quat_to_rpy(q: np.ndarray) -> Tuple[float, float, float]:
    """Convert a scalar-first quaternion ``[w, x, y, z]`` to ZYX RPY.

    Inverse of :func:`rpy_to_quat`.  Uses the standard ZYX intrinsic
    extraction; pitch is clamped to ``[-π/2, π/2]`` and, when the
    asin argument saturates (gimbal lock), roll is set to 0 and yaw
    absorbs the combined rotation — matching the convention used by
    ``tf_transformations.euler_from_quaternion(..., 'sxyz')``.

    Gimbal-lock branch
    ------------------
    At ``|sin(pitch)| > 1 - 1e-6`` the ``arcsin`` is saturated, so the
    pitch is set explicitly to ``copysign(pi/2, sin_pitch)`` rather
    than taking ``arcsin`` of a clamped value. This guarantees the
    reported pitch has the correct sign even when float round-off
    pushes the argument to exactly ±1. The yaw residual is derived
    from the ``R[0, 1] / R[1, 1]`` entries of the rotation matrix so
    the returned triple still reconstructs the correct quaternion via
    :func:`rpy_to_quat` (up to the roll/yaw degeneracy inherent to
    gimbal lock).

    Args:
        q: Shape ``(4,)`` unit quaternion, scalar-first.

    Returns:
        ``(roll, pitch, yaw)`` tuple in radians, each a Python ``float``.

    Raises:
        ValueError: If ``q`` does not have shape ``(4,)``.
    """
    q = np.asarray(q, dtype=np.float64)
    if q.shape != (4,):
        raise ValueError(f"quaternion must have shape (4,), got {q.shape}")
    w, x, y, z = q

    # Pitch — asin argument clamped to avoid NaN from float round-off.
    sin_pitch = 2.0 * (w * y - z * x)
    sin_pitch_clipped = float(np.clip(sin_pitch, -1.0, 1.0))

    # Gimbal-lock threshold: |sin(pitch)| > 1 - 1e-6 ⇒ roll indeterminate.
    if abs(sin_pitch_clipped) > 1.0 - 1e-6:
        # Explicit copysign — the arcsin output at ±1 is ±π/2 but using
        # copysign on the pre-clip value keeps the sign stable across
        # float round-off.
        pitch = float(np.copysign(np.pi / 2.0, sin_pitch))
        roll = 0.0
        # Yaw absorbs the residual rotation. Use R[0, 1] / R[1, 1] entries:
        #   R[0, 1] = 2*(x*y - w*z)
        #   R[1, 1] = 1 - 2*(x*x + z*z)  (standard ZYX rotation matrix)
        yaw = float(np.arctan2(-2.0 * (x * y - w * z), 1.0 - 2.0 * (x * x + z * z)))
    else:
        pitch = float(np.arcsin(sin_pitch_clipped))
        roll = float(np.arctan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y)))
        yaw = float(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))

    return roll, pitch, yaw
