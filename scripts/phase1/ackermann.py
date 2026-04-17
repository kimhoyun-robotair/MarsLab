"""DEPRECATED — use :mod:`marslab.robots.rover_control` instead.

This script-local module is kept as a thin re-export shim so existing
unit tests (``tests/unit/test_ackermann.py``) and any ``run_stage1.py``
imports continue to work unchanged.  All new code must import from
``marslab.robots.rover_control``.

The original module body is preserved below as comments per project
rule "do not delete, comment out" (see ``work_log/`` feedback memory).
"""

# Re-export the canonical implementation.
from marslab.robots.rover_control import (  # noqa: F401
    ackermann_command,
    clamp_steer_angles,
    ramp_steer_angles,
    ramp_wheel_velocities,
)

__all__ = [
    "ackermann_command",
    "clamp_steer_angles",
    "ramp_steer_angles",
    "ramp_wheel_velocities",
]


# ---------------------------------------------------------------------------
# ORIGINAL MODULE BODY (kept for history; do not uncomment — see
# marslab/robots/rover_control.py for the canonical implementation).
# ---------------------------------------------------------------------------
# """Ackermann steering controller for 6-wheel rocker-bogie rover.
#
# Computes 4 corner steering angles and 6 individual wheel angular
# velocities from a (v, w) twist command.  Designed for the NASA JPL
# Perseverance-class rover with front/rear corner steering and
# non-steerable middle wheels.
#
# Three operating modes handled automatically:
#
# 1. **Straight** (``|w| < eps``): all steer angles zero, uniform wheel speed.
# 2. **Point turn** (``v ~ 0, w != 0``): steer at ±arctan(wb/track),
#    left wheels reverse, right wheels forward (or vice versa).
# 3. **Ackermann curve**: ICR-based per-wheel steer angles and
#    speed-proportional velocities.
#
# The module is pure Python + NumPy with no Isaac Sim dependency,
# so it can be unit-tested offline (P3).
#
# Coordinate convention (internal):
#     X+ = rover forward, Y+ = rover left, Z+ = up.
#     Steer angle positive = wheel turns left (CCW from above).
# """
#
# from typing import Tuple
#
# import numpy as np
#
# # Minimum angular velocity magnitude to distinguish straight from curved.
# _EPS_W = 1e-6
#
# # Minimum lateral distance from ICR to a wheel before using atan limit.
# _EPS_DY = 1e-9
#
#
# def ackermann_command(
#     v: float,
#     w: float,
#     wheelbase: float,
#     track_steer: float,
#     track_middle: float,
#     wheel_radius: float,
# ) -> Tuple[np.ndarray, np.ndarray]:
#     """Compute Ackermann steer angles and per-wheel angular velocities.
#
#     Args:
#         v: Commanded linear velocity (m/s, positive = forward).
#         w: Commanded angular velocity (rad/s, positive = CCW / left turn).
#         wheelbase: Front-to-rear axle distance (m).
#         track_steer: Lateral distance between front/rear steerable wheels (m).
#         track_middle: Lateral distance between middle non-steerable wheels (m).
#         wheel_radius: Wheel rolling radius (m).
#
#     Returns:
#         Tuple of two arrays:
#             steer_angles: shape ``(4,)`` float32 — ``[LF, LR, RF, RR]`` in rad.
#             wheel_velocities: shape ``(6,)`` float32 —
#                 ``[LF, LM, LR, RF, RM, RR]`` in rad/s.
#
#     Raises:
#         ValueError: If any geometric parameter is non-positive.
#     """
#     if wheelbase <= 0.0:
#         raise ValueError(f"wheelbase must be > 0, got {wheelbase}")
#     if track_steer <= 0.0:
#         raise ValueError(f"track_steer must be > 0, got {track_steer}")
#     if track_middle <= 0.0:
#         raise ValueError(f"track_middle must be > 0, got {track_middle}")
#     if wheel_radius <= 0.0:
#         raise ValueError(f"wheel_radius must be > 0, got {wheel_radius}")
#
#     half_wb = wheelbase / 2.0
#     half_ts = track_steer / 2.0
#     half_tm = track_middle / 2.0
#
#     # Straight: no angular velocity → all steer zero, uniform drive.
#     if abs(w) < _EPS_W:
#         steer = np.zeros(4, dtype=np.float32)
#         omega = float(v) / wheel_radius
#         vel = np.full(6, omega, dtype=np.float32)
#         return steer, vel
#
#     # Turning (includes point-turn when v ≈ 0).
#     R = float(v) / float(w)
#
#     # Steerable wheel positions — order: [LF, LR, RF, RR].
#     steer_xy = [
#         (+half_wb, +half_ts),  # LF: front-left
#         (-half_wb, +half_ts),  # LR: rear-left
#         (+half_wb, -half_ts),  # RF: front-right
#         (-half_wb, -half_ts),  # RR: rear-right
#     ]
#
#     steer_angles = np.zeros(4, dtype=np.float32)
#     for i, (x_w, y_w) in enumerate(steer_xy):
#         dy = R - y_w
#         if abs(dy) < _EPS_DY:
#             steer_angles[i] = float(np.copysign(np.pi / 2.0, x_w))
#         else:
#             steer_angles[i] = float(np.arctan(x_w / dy))
#
#     # Euclidean distance to ICR — matches NVIDIA AckermannController approach.
#     drive_xy = [
#         (+half_wb, +half_ts),  # LF
#         (0.0, +half_tm),       # LM
#         (-half_wb, +half_ts),  # LR
#         (+half_wb, -half_ts),  # RF
#         (0.0, -half_tm),       # RM
#         (-half_wb, -half_ts),  # RR
#     ]
#
#     wheel_velocities = np.zeros(6, dtype=np.float32)
#     for i, (x_w, y_w) in enumerate(drive_xy):
#         dy = R - y_w
#         dist = np.sqrt(x_w**2 + dy**2)
#         wheel_velocities[i] = (
#             float(np.copysign(1.0, w * dy)) * abs(w) * dist / wheel_radius
#         )
#
#     return steer_angles, wheel_velocities
