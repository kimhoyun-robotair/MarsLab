"""Shared handle dataclass for the Stage-3 ROS2 bridge.

Separated from :mod:`marslab.ros2_bridge.__init__` during R4-6 so that
:mod:`marslab.ros2_bridge.rclpy_integration` and the sensor-graph
builders can share a common value type without re-triggering the
package top-level import (which keeps the public surface lazy with
respect to rclpy).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from marslab.ros2_bridge.odometry_publisher import OdometryPublisherContext


@dataclass
class BridgeContext:
    """Aggregate handles used by the Stage-3 main loop.

    Attributes:
        node: The rclpy ``Node`` handle.
        cmd_vel_subscription: The rclpy subscription created for
            ``cmd_vel`` (kept alive for the lifetime of the node).
        static_tf_broadcaster: StaticTransformBroadcaster publishing
            sensor TFs at startup.
        odom_ctx: :class:`OdometryPublisherContext` bundle.
        twist_state: Mutable dict written by the cmd_vel callback and
            read by the rover controller each tick.
    """

    node: Any
    cmd_vel_subscription: Any
    static_tf_broadcaster: Any
    odom_ctx: OdometryPublisherContext
    twist_state: Dict[str, float]


__all__ = ["BridgeContext"]
