"""Compute feasible Ackermann commands without Isaac or ROS dependencies.

Axes are X forward, Y left, Z up; positive steering turns left.
The runtime owns acceleration and steering ramp state.
"""

import math
from typing import Tuple

import numpy as np

# Minimum angular velocity magnitude to distinguish straight from curved.
_EPS_W = 1e-6

# Minimum lateral distance from ICR to a wheel before using atan limit.
_EPS_DY = 1e-9


def constrain_ackermann_twist(
    v: float,
    w: float,
    wheelbase: float,
    track_steer: float,
    max_steer_angle: float,
    steering_axle_offset: float = 0.0,
) -> tuple[float, float]:
    """Preserve a feasible point turn or limit yaw to an exterior rolling arc."""
    if not all(math.isfinite(value) for value in (
        v, w, wheelbase, track_steer, max_steer_angle, steering_axle_offset
    )):
        raise ValueError("Ackermann command and geometry must be finite")
    if wheelbase <= 0.0 or track_steer <= 0.0 or not 0.0 < max_steer_angle < math.pi / 2.0:
        raise ValueError("Ackermann geometry must be positive and steering limit below pi/2")
    if abs(steering_axle_offset) >= wheelbase / 2.0:
        raise ValueError("steering axle offset must lie between front and rear axles")
    longest_arm = wheelbase / 2.0 + abs(steering_axle_offset)
    if abs(v) < 1e-6:
        if abs(w) >= _EPS_W and math.atan2(longest_arm, track_steer / 2.0) > max_steer_angle:
            raise ValueError("steering limit is insufficient for a point turn")
        return 0.0, w
    min_radius = track_steer / 2.0 + longest_arm / math.tan(max_steer_angle)
    yaw_limit = abs(v) / min_radius
    return v, max(-yaw_limit, min(w, yaw_limit))


def ackermann_command(
    v: float,
    w: float,
    wheelbase: float,
    track_steer: float,
    track_middle: float,
    wheel_radius: float,
    steering_axle_offset: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute Ackermann steer angles and per-wheel angular velocities.

    Args:
        v: Commanded linear velocity (m/s, positive = forward).
        w: Commanded angular velocity (rad/s, positive = CCW / left turn).
        wheelbase: Front-to-rear axle distance (m).
        track_steer: Lateral distance between front/rear steerable wheels (m).
        track_middle: Lateral distance between middle non-steerable wheels (m).
        wheel_radius: Wheel rolling radius (m).
        steering_axle_offset: Steering axle midpoint ahead of the middle axle (m).

    Returns:
        Tuple of two arrays:
            steer_angles: shape ``(4,)`` float32 -- ``[LF, LR, RF, RR]`` in rad.
            wheel_velocities: shape ``(6,)`` float32 --
                ``[LF, LM, LR, RF, RM, RR]`` in rad/s.

    Raises:
        ValueError: If commands or geometry are non-finite, or geometry is non-positive.
    """
    if not all(
        math.isfinite(value) for value in (
            v, w, wheelbase, track_steer, track_middle, wheel_radius, steering_axle_offset
        )
    ):
        raise ValueError("Ackermann command and geometry must be finite")
    if wheelbase <= 0.0:
        raise ValueError(f"wheelbase must be > 0, got {wheelbase}")
    if track_steer <= 0.0:
        raise ValueError(f"track_steer must be > 0, got {track_steer}")
    if track_middle <= 0.0:
        raise ValueError(f"track_middle must be > 0, got {track_middle}")
    if wheel_radius <= 0.0:
        raise ValueError(f"wheel_radius must be > 0, got {wheel_radius}")
    if abs(steering_axle_offset) >= wheelbase / 2.0:
        raise ValueError("steering axle offset must lie between front and rear axles")

    half_wb = wheelbase / 2.0
    half_ts = track_steer / 2.0
    half_tm = track_middle / 2.0
    front_x = half_wb + steering_axle_offset
    rear_x = -half_wb + steering_axle_offset

    # Straight: no angular velocity -> all steer zero, uniform drive.
    if abs(w) < _EPS_W:
        steer = np.zeros(4, dtype=np.float32)
        omega = float(v) / wheel_radius
        vel = np.full(6, omega, dtype=np.float32)
        return steer, vel

    # Turning (includes point-turn when v ~ 0).
    # ICR sits at (0, R) in the rover frame where R = v/w.
    R = float(v) / float(w)

    # Steerable wheel positions -- order: [LF, LR, RF, RR].
    steer_xy = [
        (front_x, +half_ts),  # LF: front-left
        (rear_x, +half_ts),  # LR: rear-left
        (front_x, -half_ts),  # RF: front-right
        (rear_x, -half_ts),  # RR: rear-right
    ]

    steer_angles = np.zeros(4, dtype=np.float32)
    for i, (x_w, y_w) in enumerate(steer_xy):
        dy = R - y_w
        if abs(dy) < _EPS_DY:
            # ICR exactly at wheel lateral position -> +/-90 deg steer.
            # ``np.arctan2(x_w, 0)`` already returns ``sign(x_w)*pi/2``,
            # but the branch is explicit so ``x_w == 0`` (degenerate,
            # pick +) does not propagate float subnormals into downstream
            # clamps.
            steer_angles[i] = float(np.copysign(np.pi / 2.0, x_w if x_w != 0.0 else 1.0))
        else:
            # Keep the wheel axis within +/-90 degrees; drive signs account
            # for the pi reversal on the inner side of the rotation center.
            theta = float(np.arctan2(x_w, dy))
            if theta > np.pi / 2.0:
                theta -= np.pi
            elif theta < -np.pi / 2.0:
                theta += np.pi
            steer_angles[i] = theta

    # Euclidean distance to ICR -- matches the NVIDIA
    # AckermannController approach.  Each wheel at (x_w, y_w) has
    # distance sqrt(x_w^2 + (R-y_w)^2).
    #
    # Sign: steer stays in the (-pi/2, pi/2] principal range above, so
    # positive wheel rotation moves along the direction
    # (cos theta, sin theta).  The tangential velocity at the contact
    # is w x (r_icr_to_wheel) = (w*dy, w*x_w).  Projected onto
    # (cos theta, sin theta) this gives
    # omega_wheel * r = w * dy / cos theta.  Because cos theta > 0 in
    # the principal range, omega_wheel has the sign of (w * dy) --
    # exactly the original copysign(w, w*dy) convention.
    drive_xy = [
        (front_x, +half_ts),  # LF
        (0.0, +half_tm),  # LM
        (rear_x, +half_ts),  # LR
        (front_x, -half_ts),  # RF
        (0.0, -half_tm),  # RM
        (rear_x, -half_ts),  # RR
    ]

    wheel_velocities = np.zeros(6, dtype=np.float32)
    for i, (x_w, y_w) in enumerate(drive_xy):
        dy = R - y_w
        dist = np.sqrt(x_w**2 + dy**2)
        wheel_velocities[i] = float(np.copysign(1.0, w * dy)) * abs(w) * dist / wheel_radius

    return steer_angles, wheel_velocities
