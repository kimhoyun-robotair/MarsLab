"""Pure-Python rover control primitives (Ackermann + ramp helpers).

Everything here is pure NumPy -- no Isaac Sim, no ROS2, no IO -- so it
can be unit-tested without booting any simulation.

Contents:
    * ``ackermann_command`` -- ICR-based steer angles + Euclidean
      per-wheel angular velocities for a 6-wheel rocker-bogie rover.
    * ``ramp_wheel_velocities`` -- per-step drive velocity target limiter
      with asymmetric acceleration/deceleration rates.
    * ``ramp_steer_angles`` -- per-step steer angle target limiter.
    * ``clamp_steer_angles`` -- saturate steer angles at mechanical
      limits (rocker-bogie collision avoidance).

Coordinate convention (internal):
    X+ = rover forward, Y+ = rover left, Z+ = up.
    Steer angle positive = wheel turns left (CCW from above).
"""

from typing import Tuple

import numpy as np

# Minimum angular velocity magnitude to distinguish straight from curved.
_EPS_W = 1e-6

# Minimum lateral distance from ICR to a wheel before using atan limit.
_EPS_DY = 1e-9


def ackermann_command(
    v: float,
    w: float,
    wheelbase: float,
    track_steer: float,
    track_middle: float,
    wheel_radius: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute Ackermann steer angles and per-wheel angular velocities.

    Args:
        v: Commanded linear velocity (m/s, positive = forward).
        w: Commanded angular velocity (rad/s, positive = CCW / left turn).
        wheelbase: Front-to-rear axle distance (m).
        track_steer: Lateral distance between front/rear steerable wheels (m).
        track_middle: Lateral distance between middle non-steerable wheels (m).
        wheel_radius: Wheel rolling radius (m).

    Returns:
        Tuple of two arrays:
            steer_angles: shape ``(4,)`` float32 — ``[LF, LR, RF, RR]`` in rad.
            wheel_velocities: shape ``(6,)`` float32 —
                ``[LF, LM, LR, RF, RM, RR]`` in rad/s.

    Raises:
        ValueError: If any geometric parameter is non-positive.
    """
    if wheelbase <= 0.0:
        raise ValueError(f"wheelbase must be > 0, got {wheelbase}")
    if track_steer <= 0.0:
        raise ValueError(f"track_steer must be > 0, got {track_steer}")
    if track_middle <= 0.0:
        raise ValueError(f"track_middle must be > 0, got {track_middle}")
    if wheel_radius <= 0.0:
        raise ValueError(f"wheel_radius must be > 0, got {wheel_radius}")

    half_wb = wheelbase / 2.0
    half_ts = track_steer / 2.0
    half_tm = track_middle / 2.0

    # Straight: no angular velocity → all steer zero, uniform drive.
    if abs(w) < _EPS_W:
        steer = np.zeros(4, dtype=np.float32)
        omega = float(v) / wheel_radius
        vel = np.full(6, omega, dtype=np.float32)
        return steer, vel

    # Turning (includes point-turn when v ≈ 0).
    # ICR sits at (0, R) in the rover frame where R = v/w.
    R = float(v) / float(w)

    # Steerable wheel positions — order: [LF, LR, RF, RR].
    steer_xy = [
        (+half_wb, +half_ts),  # LF: front-left
        (-half_wb, +half_ts),  # LR: rear-left
        (+half_wb, -half_ts),  # RF: front-right
        (-half_wb, -half_ts),  # RR: rear-right
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
            # arctan2(x_w, dy) instead of arctan(x_w/dy): the division
            # form silently drops the sign of dy so tight turns
            # (R < half_ts, dy < 0 on the inside wheel) land in the
            # wrong quadrant and the "dy == 0" branch above is never
            # reached for small-but-nonzero dy.  The result is wrapped
            # into the principal wheel-axis range (-pi/2, pi/2] -- a
            # real steer joint has +/-40 deg limits, so values outside
            # (-pi/2, pi/2) must flip the wheel by pi and let the drive
            # velocity compensate (see below).
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
        (+half_wb, +half_ts),  # LF
        (0.0, +half_tm),  # LM
        (-half_wb, +half_ts),  # LR
        (+half_wb, -half_ts),  # RF
        (0.0, -half_tm),  # RM
        (-half_wb, -half_ts),  # RR
    ]

    wheel_velocities = np.zeros(6, dtype=np.float32)
    for i, (x_w, y_w) in enumerate(drive_xy):
        dy = R - y_w
        dist = np.sqrt(x_w**2 + dy**2)
        wheel_velocities[i] = float(np.copysign(1.0, w * dy)) * abs(w) * dist / wheel_radius

    return steer_angles, wheel_velocities


def clamp_steer_angles(angles: np.ndarray, max_angle: float) -> np.ndarray:
    """Saturate steer angles at mechanical stops.

    The Ackermann controller can request 87°+ angles for tight turns
    (R < wheelbase/2), which folds the rocker-bogie suspension.  Real
    rovers have mechanical stops typically around 40°.

    Args:
        angles: Steer angle array (rad), any shape.
        max_angle: Maximum absolute steer angle (rad).  Must be > 0.

    Returns:
        ``np.clip(angles, -max_angle, +max_angle)`` as float32.

    Raises:
        ValueError: If ``max_angle <= 0``.
    """
    if max_angle <= 0.0:
        raise ValueError(f"max_angle must be > 0, got {max_angle}")
    return np.clip(angles, -max_angle, max_angle).astype(np.float32)


def ramp_steer_angles(
    current: np.ndarray,
    target: np.ndarray,
    per_step_limit: float,
) -> np.ndarray:
    """Limit per-step change in steer angle targets.

    Prevents snap transitions (e.g. cmd_vel going to zero while wheels
    are still spinning -> sudden lateral impulse).  If ``per_step_limit``
    is 0 or negative, the function returns ``target`` unchanged (ramp
    disabled).

    Args:
        current: Last commanded steer targets (rad), shape ``(n,)``.
        target: Desired new steer targets (rad), shape ``(n,)``.
        per_step_limit: Maximum absolute delta per step (rad).

    Returns:
        New ramped targets, same shape/dtype as ``current``.

    Note:
        As of v1.0 the steer ramp is also implemented inline at the
        runtime level (``marslab.runtime.main_loop``).  Prefer this
        helper for new code paths so the ramp logic stays single-sourced.
    """
    if per_step_limit <= 0.0:
        return target.astype(current.dtype, copy=True)
    delta = target.astype(current.dtype) - current
    delta = np.clip(delta, -per_step_limit, per_step_limit)
    return current + delta


def ramp_wheel_velocities(
    current: np.ndarray,
    target: np.ndarray,
    per_step_limit: float,
    decel_multiplier: float = 1.0,
) -> np.ndarray:
    """Limit per-step change in drive velocity targets.

    Prevents the impulse that occurs when ``set_joint_velocity_targets``
    jumps from 0 to a large value while ``drive_damping`` is high in
    acceleration mode.  Braking (target magnitude lower than current)
    is allowed to happen ``decel_multiplier`` times faster than
    acceleration, which matches the human intuition that a rover should
    stop quickly but accelerate gently.

    If ``per_step_limit`` is 0 or negative, the function returns
    ``target`` unchanged (ramp disabled).

    Args:
        current: Last commanded wheel velocity targets (rad/s), shape ``(n,)``.
        target: Desired new velocity targets (rad/s), shape ``(n,)``.
        per_step_limit: Baseline (acceleration) per-step delta limit (rad/s).
        decel_multiplier: Multiplier applied per-element when the new
            target magnitude is lower than the current target magnitude.
            ``1.0`` = symmetric, ``3.0`` = brake 3× faster than accel.

    Returns:
        New ramped targets, same shape/dtype as ``current``.
    """
    if per_step_limit <= 0.0:
        return target.astype(current.dtype, copy=True)
    tgt = target.astype(current.dtype)
    delta = tgt - current
    is_decel = np.abs(tgt) < np.abs(current)
    step_lim = np.where(
        is_decel,
        np.asarray(per_step_limit * decel_multiplier, dtype=current.dtype),
        np.asarray(per_step_limit, dtype=current.dtype),
    ).astype(current.dtype)
    delta = np.clip(delta, -step_lim, step_lim)
    return (current + delta).astype(current.dtype)
