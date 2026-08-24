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

Every helper is deterministic, side-effect free, and built on NumPy.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from marslab.quaternion import quat_inverse, quat_rotate_vec


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
