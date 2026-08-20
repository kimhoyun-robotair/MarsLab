"""Group live ROS 2 publisher handles for the simulation loop.
The dataclass carries GT, wheel odometry, and noisy IMU channels.
It can be imported without starting a ROS node."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from marslab.ros2_bridge.imu_noise_publisher import ImuNoiseContext
from marslab.ros2_bridge.odometry_publisher import GroundTruthPosePublisherContext
from marslab.ros2_bridge.wheel_odometry_publisher import WheelOdometryContext


@dataclass
class BridgeContext:
    """Aggregate publisher handles consumed by the runtime main loop."""

    node: Any
    cmd_vel_subscription: Any
    static_tf_broadcaster: Any
    odom_ctx: GroundTruthPosePublisherContext
    twist_state: Dict[str, float]
    robot_description_ctx: Optional[Any] = None
    wheel_odom_ctx: Optional[WheelOdometryContext] = None
    imu_noise_ctx: Optional[ImuNoiseContext] = None


__all__ = ["BridgeContext"]
