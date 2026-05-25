"""Shared handle dataclass for the rover ROS2 bridge.

Separated from :mod:`marslab.ros2_bridge.__init__` so that
:mod:`marslab.ros2_bridge.rclpy_integration` and the sensor-graph
builders can share a common value type without re-triggering the
package top-level import (every public function defers its rclpy
imports until runtime).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from marslab.ros2_bridge.imu_noise_publisher import ImuNoiseContext
from marslab.ros2_bridge.odometry_publisher import OdometryPublisherContext
from marslab.ros2_bridge.wheel_odometry_publisher import WheelOdometryContext


@dataclass
class BridgeContext:
    """Aggregate handles used by the runtime main loop.

    ``odom_ctx`` publishes the PhysX articulation pose verbatim on
    ``/rover/GT_Trajectory`` for ATE ground-truth comparison.
    ``wheel_odom_ctx`` integrates wheel-joint angular velocities into a
    skid-steer dead-reckoning estimate on ``/rover/odom`` so a downstream
    SLAM stack has a noisy odometry source to fuse / correct.
    ``imu_noise_ctx`` publishes Python-side noisy IMU on ``/rover/imu``
    when IMU noise fields are non-zero; ``None`` when noise is disabled.
    """

    node: Any
    cmd_vel_subscription: Any
    static_tf_broadcaster: Any
    odom_ctx: OdometryPublisherContext
    twist_state: Dict[str, float]
    robot_description_ctx: Optional[Any] = None
    wheel_odom_ctx: Optional[WheelOdometryContext] = None
    imu_noise_ctx: Optional[ImuNoiseContext] = None


__all__ = ["BridgeContext"]
