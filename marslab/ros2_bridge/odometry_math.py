"""Pure-Python quaternion + odometry helpers (no ROS2, no Isaac Sim).

The rover runtime publishes ``odom→base_link`` TF and a ``nav_msgs/Odometry``
message from Isaac Sim's world-frame articulation pose.  The odometry
frame is defined as the *initial* world pose of the rover, so the math
reduces to:

    delta_pos_odom = R(q_init_inv) * (pos_world - pos_init_world)
    delta_quat      = q_init_inv ⊗ q_current_world
    body_twist      = R(q_current_inv) * world_twist

All quaternions use the ``[w, x, y, z]`` (scalar-first) convention
matching Isaac Sim's articulation API and ROS2 ``geometry_msgs/Quaternion``
field order.

Every helper is deterministic, side-effect free, and built on NumPy
only so that ``tests/unit/`` can validate it headlessly (P3).
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

# R3-A1: quat_inverse / quat_multiply / quat_rotate_vec were relocated to
# ``marslab.math.quaternion`` as the single source of truth.  The imports
# below preserve backward compatibility for every existing call site
# (``marslab.ros2_bridge.odometry_publisher``, ``tests/unit/test_odometry_math``)
# that still does ``from marslab.ros2_bridge.odometry_math import quat_*``.
from marslab.math.quaternion import (  # noqa: F401
    quat_inverse,
    quat_multiply,
    quat_rotate_vec,
)

# DISABLED (moved_to_marslab_math_R3-A1): original quat_inverse definition.
# def quat_inverse(q: np.ndarray) -> np.ndarray:
#     """Return the inverse of a unit quaternion ``[w, x, y, z]``.
#
#     For a unit quaternion the inverse equals the conjugate: negate the
#     vector part, keep the scalar.  The caller is responsible for keeping
#     ``q`` unit-norm; this function does not renormalise.
#
#     Args:
#         q: Shape ``(4,)`` quaternion with scalar-first ordering.
#
#     Returns:
#         Shape ``(4,)`` inverse quaternion, dtype float32.
#     """
#     q = np.asarray(q, dtype=np.float32)
#     if q.shape != (4,):
#         raise ValueError(f"quaternion must have shape (4,), got {q.shape}")
#     return np.array([q[0], -q[1], -q[2], -q[3]], dtype=np.float32)
#
#
# DISABLED (moved_to_marslab_math_R3-A1): original quat_multiply definition.
# def quat_multiply(q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
#     """Hamilton product ``q1 ⊗ q2`` of two ``[w, x, y, z]`` quaternions.
#
#     Args:
#         q1: Left operand, shape ``(4,)``.
#         q2: Right operand, shape ``(4,)``.
#
#     Returns:
#         Shape ``(4,)`` product, dtype float32.
#     """
#     q1 = np.asarray(q1, dtype=np.float32)
#     q2 = np.asarray(q2, dtype=np.float32)
#     if q1.shape != (4,) or q2.shape != (4,):
#         raise ValueError(f"quaternions must have shape (4,), got {q1.shape} and {q2.shape}")
#     w1, x1, y1, z1 = q1
#     w2, x2, y2, z2 = q2
#     return np.array(
#         [
#             w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
#             w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
#             w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
#             w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
#         ],
#         dtype=np.float32,
#     )
#
#
# DISABLED (moved_to_marslab_math_R3-A1): original quat_rotate_vec definition.
# def quat_rotate_vec(q: np.ndarray, v: np.ndarray) -> np.ndarray:
#     """Rotate a 3-vector by a ``[w, x, y, z]`` quaternion.
#
#     Computes ``q ⊗ [0, v] ⊗ q^-1`` and returns the vector part.
#
#     Args:
#         q: Rotation quaternion, shape ``(4,)``.
#         v: Vector to rotate, shape ``(3,)``.
#
#     Returns:
#         Rotated vector, shape ``(3,)``, dtype float32.
#     """
#     v = np.asarray(v, dtype=np.float32)
#     if v.shape != (3,):
#         raise ValueError(f"vector must have shape (3,), got {v.shape}")
#     v_quat = np.array([0.0, v[0], v[1], v[2]], dtype=np.float32)
#     q_inv = quat_inverse(q)
#     result = quat_multiply(quat_multiply(q, v_quat), q_inv)
#     return result[1:4].astype(np.float32)


def compute_odom_delta(
    cur_pos_world: np.ndarray,
    cur_quat_world: np.ndarray,
    init_pos_world: np.ndarray,
    init_quat_world: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Convert a world-frame rover pose into odom-frame pose.

    The odom frame is defined as the initial world pose.  Given current
    and initial poses, returns the pose expressed relative to that
    initial frame — exactly what ``nav_msgs/Odometry`` expects in its
    ``pose.pose`` field.

    Args:
        cur_pos_world: Current rover position in world frame, shape ``(3,)``.
        cur_quat_world: Current rover orientation in world frame,
            shape ``(4,)`` scalar-first.
        init_pos_world: Initial rover position in world frame, shape ``(3,)``.
        init_quat_world: Initial rover orientation in world frame,
            shape ``(4,)`` scalar-first.

    Returns:
        Tuple of ``(delta_pos_odom, delta_quat_odom)``:
            * ``delta_pos_odom`` shape ``(3,)`` — position in odom frame.
            * ``delta_quat_odom`` shape ``(4,)`` — orientation in odom frame.
    """
    cur_pos_world = np.asarray(cur_pos_world, dtype=np.float32)
    init_pos_world = np.asarray(init_pos_world, dtype=np.float32)
    if cur_pos_world.shape != (3,) or init_pos_world.shape != (3,):
        raise ValueError("position must have shape (3,)")
    init_quat_inv = quat_inverse(init_quat_world)
    delta_pos_world = cur_pos_world - init_pos_world
    delta_pos_odom = quat_rotate_vec(init_quat_inv, delta_pos_world)
    delta_quat_odom = quat_multiply(init_quat_inv, np.asarray(cur_quat_world, dtype=np.float32))
    return delta_pos_odom, delta_quat_odom


def world_twist_to_body(
    linear_world: np.ndarray,
    angular_world: np.ndarray,
    cur_quat_world: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Rotate world-frame linear/angular velocity into body frame.

    ``nav_msgs/Odometry`` expresses the twist in the child frame
    (``base_link``), so the world-frame velocities coming from Isaac
    Sim's articulation must be rotated by the inverse of the current
    body-in-world orientation.

    Args:
        linear_world: Linear velocity in world frame, shape ``(3,)``.
        angular_world: Angular velocity in world frame, shape ``(3,)``.
        cur_quat_world: Current body orientation in world frame,
            shape ``(4,)`` scalar-first.

    Returns:
        Tuple of ``(linear_body, angular_body)`` each shape ``(3,)``.
    """
    q_inv = quat_inverse(cur_quat_world)
    linear_body = quat_rotate_vec(q_inv, linear_world)
    angular_body = quat_rotate_vec(q_inv, angular_world)
    return linear_body, angular_body
