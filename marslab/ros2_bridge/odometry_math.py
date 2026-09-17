"""Pure encoder kinematics and world-to-body twist conversion.

Wheel odometry uses only joint encoders and configured geometry.
World twist conversion belongs to the separate ground-truth stream.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np

from marslab.quaternion import quat_inverse, quat_rotate_vec


def wheel_contact_positions(
    wheelbase: float,
    track_steer: float,
    track_middle: float,
    steering_axle_offset: float = 0.0,
) -> np.ndarray:
    """Return planar LF, LM, LR, RF, RM, RR contact geometry in meters."""
    if min(wheelbase, track_steer, track_middle) <= 0.0:
        raise ValueError("wheelbase and wheel tracks must be positive")
    if not np.isfinite(steering_axle_offset) or abs(steering_axle_offset) >= wheelbase / 2.0:
        raise ValueError("steering_axle_offset must be finite and within half the wheelbase")
    front_x = wheelbase / 2.0 + steering_axle_offset
    rear_x = -wheelbase / 2.0 + steering_axle_offset
    return np.asarray(
        [
            (front_x, track_steer / 2.0),
            (0.0, track_middle / 2.0),
            (rear_x, track_steer / 2.0),
            (front_x, -track_steer / 2.0),
            (0.0, -track_middle / 2.0),
            (rear_x, -track_steer / 2.0),
        ],
        dtype=np.float64,
    )


def encoder_planar_twist(
    wheel_speeds: np.ndarray,
    steering_angles: np.ndarray,
    wheel_positions: np.ndarray,
) -> tuple[float, float]:
    """Fit forward speed and yaw rate to six measured rolling velocities.

    Steering is LF, LR, RF, RR in the controller's positive-left convention.
    The fixed middle wheels impose zero lateral velocity at the rover origin.
    Each row satisfies speed = cos(steer)*v + (x*sin(steer)-y*cos(steer))*yaw_rate.
    """
    if wheel_speeds.shape != (6,) or steering_angles.shape != (4,):
        raise ValueError("encoder odometry requires six drive and four steering measurements")
    if wheel_positions.shape != (6, 2):
        raise ValueError("wheel_positions must have shape (6, 2)")
    if not all(
        np.all(np.isfinite(values))
        for values in (wheel_speeds, steering_angles, wheel_positions)
    ):
        raise ValueError("wheel encoder measurements and geometry must be finite")
    angles = np.zeros(6, dtype=np.float64)
    angles[[0, 2, 3, 5]] = steering_angles
    cos_angles = np.cos(angles)
    yaw_lever = wheel_positions[:, 0] * np.sin(angles) - wheel_positions[:, 1] * cos_angles
    rolling = np.column_stack((cos_angles, yaw_lever))
    twist, _, rank, _ = np.linalg.lstsq(rolling, wheel_speeds, rcond=None)
    if rank != 2:
        raise ValueError("wheel encoder geometry cannot resolve forward speed and yaw rate")
    return float(twist[0]), float(twist[1])


def world_twist_to_body(
    linear_world: np.ndarray,
    angular_world: np.ndarray,
    cur_quat_world: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """Rotate world-frame linear/angular velocity into body frame.

    ``nav_msgs/Odometry`` expresses the twist in the child frame
    (``base_link_gt`` for ground truth), so the world-frame velocities coming from Isaac
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
