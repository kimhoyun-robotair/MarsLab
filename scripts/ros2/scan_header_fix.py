#!/usr/bin/env python3
"""LaserScan header off-by-one normalization for Isaac Sim -> slam_toolbox.

Isaac Sim's ``isaacsim.ros2.bridge.ROS2RtxLidarHelper(type='laser_scan')``
publishes full-rotary scans with ``angle_max = angle_min + N * angle_increment``
(exclusive end), while Open Karto (slam_toolbox) expects the inclusive
convention ``angle_max = angle_min + (N - 1) * angle_increment``. The
1-ray discrepancy triggers ``LaserRangeScan contains N range readings,
expected N+1`` and slam_toolbox drops every scan.

This node subscribes to the raw Isaac Sim topic, rewrites ``angle_max``
on each message, and republishes on a ``*_corrected`` topic. slam_toolbox,
Nav2 obstacle_layer, and collision_monitor all point at the corrected
topic via YAML.

Topics (ROS2 Jazzy):
    in  : /rover/scan           (sensor_msgs/LaserScan)
    out : /rover/scan_corrected (sensor_msgs/LaserScan)
"""

from __future__ import annotations

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan


class ScanHeaderFix(Node):
    """Rewrite exclusive-end ``angle_max`` to inclusive-end semantics."""

    def __init__(self) -> None:
        super().__init__("scan_header_fix")
        self.declare_parameter("input_topic", "/rover/scan")
        self.declare_parameter("output_topic", "/rover/scan_corrected")
        in_topic = self.get_parameter("input_topic").value
        out_topic = self.get_parameter("output_topic").value

        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )
        self._pub = self.create_publisher(LaserScan, out_topic, qos)
        self._sub = self.create_subscription(LaserScan, in_topic, self._cb, qos)
        self.get_logger().info(
            f"scan_header_fix: {in_topic} -> {out_topic} " "(angle_max -= angle_increment)"
        )

    def _cb(self, msg: LaserScan) -> None:
        msg.angle_max = msg.angle_max - msg.angle_increment
        self._pub.publish(msg)


def main() -> None:
    rclpy.init()
    node = ScanHeaderFix()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
