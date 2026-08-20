"""Expose the public MarsLab ROS 2 bridge surface.
Graph builders and publisher factories stay behind runtime boundaries.
Importing the package does not initialize rclpy."""

from __future__ import annotations

from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber
from marslab.ros2_bridge.context import BridgeContext
from marslab.ros2_bridge.odometry_publisher import (
    GroundTruthPosePublisherContext,
    create_ground_truth_pose_publisher,
    publish_ground_truth_pose,
)
from marslab.ros2_bridge.rclpy_integration import init_rclpy_side
from marslab.ros2_bridge.robot_description_publisher import (
    RobotDescriptionContext,
    publish_robot_description,
    rewrite_mesh_paths_to_file_uri,
)
from marslab.ros2_bridge.sensor_graph import (
    GRAPH_PATH,
    SensorGraphHandle,
    build_sensor_graph,
)
from marslab.ros2_bridge.tf_broadcaster import (
    build_static_sensor_transforms,
    publish_static_sensor_tfs,
)

__all__ = [
    "BridgeContext",
    "GRAPH_PATH",
    "GroundTruthPosePublisherContext",
    "RobotDescriptionContext",
    "SensorGraphHandle",
    "build_sensor_graph",
    "build_static_sensor_transforms",
    "create_cmd_vel_subscriber",
    "create_ground_truth_pose_publisher",
    "init_rclpy_side",
    "publish_ground_truth_pose",
    "publish_robot_description",
    "publish_static_sensor_tfs",
    "rewrite_mesh_paths_to_file_uri",
]
