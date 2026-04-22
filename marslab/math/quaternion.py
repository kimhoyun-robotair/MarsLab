"""Pure-NumPy quaternion algebra and ZYX RPY conversion.

All quaternions in this module use the **scalar-first** ``[w, x, y, z]``
convention, matching:

* Isaac Sim's articulation pose API,
* ROS2 ``geometry_msgs/Quaternion`` field order (w, x, y, z),
* URDF / ROS ZYX intrinsic RPY convention for
  :func:`rpy_to_quat` and :func:`quat_to_rpy`.

Every function is deterministic, side-effect free, and NumPy-only so
``tests/unit/`` can validate the module headlessly (see project
principle P3: offline-first testing).

This module is the single source of truth for quaternion helpers
previously duplicated across:

* ``marslab.ros2_bridge.odometry_math`` (quat_inverse / quat_multiply /
  quat_rotate_vec) — now re-exported from here.
* ``marslab.robots.rover`` (rpy_to_quat) — now re-exported from here.
* ``scripts/phase1/run_stage3_monolithic_new.py`` (rpy_to_quat) — now
  imported from here.

The Oracle twin ``scripts/phase1/run_stage3_monolithic.py`` keeps its
local ``rpy_to_quat`` copy (diff=0 policy).
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def quat_inverse(q: np.ndarray) -> np.ndarray:
    """Return the inverse of a unit quaternion ``[w, x, y, z]``.

    For a unit quaternion the inverse equals the conjugate: negate the
    vector part, keep the scalar.  The caller is responsible for keeping
    ``q`` unit-norm; this function does not renormalise.

    Args:
        q: Shape ``(4,)`` quaternion with scalar-first ordering.

    Returns:
        Shape ``(4,)`` inverse quaternion, dtype float32.

    Raises:
        ValueError: If ``q`` does not have shape ``(4,)``.
    """
    q = np.asarray(q, dtype=np.float32)
    if q.shape != (4,):
        raise ValueError(f"quaternion must have shape (4,), got {q.shape}")
    return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float32)


def quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Hamilton product ``q1 ⊗ q2`` of two ``[w, x, y, z]`` quaternions.

    Args:
        q1: Left operand, shape ``(4,)``.
        q2: Right operand, shape ``(4,)``.

    Returns:
        Shape ``(4,)`` product quaternion, dtype float32.

    Raises:
        ValueError: If either input does not have shape ``(4,)``.
    """
    q1 = np.asarray(q1, dtype=np.float32)
    q2 = np.asarray(q2, dtype=np.float32)
    if q1.shape != (4,) or q2.shape != (4,):
        raise ValueError(f"quaternions must have shape (4,), got {q1.shape} and {q2.shape}")
    w1, x1, y1, z1 = q1
    w2, x2, y2, z2 = q2
    return np.array(
        [
            w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
        ],
        dtype=np.float32,
    )


def quat_rotate_vec(q: np.ndarray, v: np.ndarray) -> np.ndarray:
    """Rotate a 3-vector by a ``[w, x, y, z]`` quaternion.

    Computes ``q ⊗ [0, v] ⊗ q⁻¹`` and returns the vector part.  ``q``
    is assumed to be unit-norm (not re-normalised here).

    Args:
        q: Rotation quaternion, shape ``(4,)``.
        v: Vector to rotate, shape ``(3,)``.

    Returns:
        Rotated vector, shape ``(3,)``, dtype float32.

    Raises:
        ValueError: If ``v`` does not have shape ``(3,)`` (shape check on
            ``q`` is delegated to :func:`quat_inverse`).
    """
    v = np.asarray(v, dtype=np.float32)
    if v.shape != (3,):
        raise ValueError(f"vector must have shape (3,), got {v.shape}")
    v_quat = np.array([0.0, v[0], v[1], v[2]], dtype=np.float32)
    q_inv = quat_inverse(q)
    result = quat_multiply(quat_multiply(q, v_quat), q_inv)
    return result[1:4].astype(np.float32)


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
    sin_pitch = float(np.clip(sin_pitch, -1.0, 1.0))
    pitch = float(np.arcsin(sin_pitch))

    # Gimbal-lock threshold: |sin(pitch)| > 1 - 1e-6 ⇒ roll indeterminate.
    if abs(sin_pitch) > 1.0 - 1e-6:
        roll = 0.0
        yaw = float(np.arctan2(-2.0 * (x * y - w * z), 1.0 - 2.0 * (y * y + z * z)))
    else:
        roll = float(np.arctan2(2.0 * (w * x + y * z), 1.0 - 2.0 * (x * x + y * y)))
        yaw = float(np.arctan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z)))

    return roll, pitch, yaw
