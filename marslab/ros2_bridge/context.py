"""Group live ROS 2 publisher handles for the simulation loop.
The dataclass carries GT, wheel odometry, and noisy IMU channels.
It can be imported without starting a ROS node."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Optional

from marslab.ros2_bridge.imu_noise_publisher import ImuNoiseContext
from marslab.ros2_bridge.odometry_publisher import GroundTruthPosePublisherContext
from marslab.ros2_bridge.wheel_odometry_publisher import WheelOdometryContext

if TYPE_CHECKING:
    from marslab.ros2_bridge.depth_publisher import DepthPublisher
    from marslab.ros2_bridge.lidar_scan_publisher import LidarScanPublisher


@dataclass
class BridgeContext:
    """Aggregate publisher handles consumed by the runtime main loop."""

    node: Any
    cmd_vel_subscription: Any
    static_tf_broadcaster: Any
    odom_ctx: GroundTruthPosePublisherContext
    twist_state: Dict[str, float]
    shutdown: Callable[[], None] | None = None
    wheel_odom_ctx: Optional[WheelOdometryContext] = None
    imu_noise_ctx: Optional[ImuNoiseContext] = None
    depth_publisher: DepthPublisher | None = None
    lidar_scan_publisher: LidarScanPublisher | None = None


__all__ = ["BridgeContext"]
