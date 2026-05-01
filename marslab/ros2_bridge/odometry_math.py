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
only so that ``tests/unit/`` can validate it headlessly (offline-first
testing requirement).
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

# ``quat_inverse`` / ``quat_multiply`` / ``quat_rotate_vec`` live in
# ``marslab.quaternion`` as the single source of truth.  The imports
# below preserve backward compatibility for every existing call site
# (``marslab.ros2_bridge.odometry_publisher``, ``tests/unit/test_odometry_math``)
# that still does ``from marslab.ros2_bridge.odometry_math import quat_*``.
from marslab.quaternion import (  # noqa: F401
    quat_inverse,
    quat_multiply,
    quat_rotate_vec,
)


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
