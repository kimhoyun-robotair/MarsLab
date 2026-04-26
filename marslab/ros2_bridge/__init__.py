"""ROS2 bridge package for MarsLab Stage-3 integration.

Public surface
--------------

* :func:`init_rclpy_side` -- Create the rclpy node + cmd_vel
  subscriber + static sensor TF + odometry publisher in one call.
  The only function needed by ``scripts/phase1/run_stage3.py``.
* :func:`build_sensor_graph` -- OmniGraph construction (re-exported
  from :mod:`marslab.ros2_bridge.sensor_graph`).
* Pure math helpers in :mod:`marslab.ros2_bridge.odometry_math`.

The individual submodules (``cmd_vel_subscriber``, ``odometry_publisher``,
``tf_broadcaster``) stay importable on their own for unit tests.

R4-6 (2026-04-22): ``BridgeContext`` dataclass and ``init_rclpy_side``
moved to :mod:`marslab.ros2_bridge.context` and
:mod:`marslab.ros2_bridge.rclpy_integration` respectively.
"""

from __future__ import annotations

from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber
from marslab.ros2_bridge.context import BridgeContext
from marslab.ros2_bridge.odometry_publisher import (
    OdometryPublisherContext,
    create_odometry_publisher,
    publish_odometry,
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
    "OdometryPublisherContext",
    "RobotDescriptionContext",
    "SensorGraphHandle",
    "build_sensor_graph",
    "build_static_sensor_transforms",
    "create_cmd_vel_subscriber",
    "create_odometry_publisher",
    "init_rclpy_side",
    "publish_odometry",
    "publish_robot_description",
    "publish_static_sensor_tfs",
    "rewrite_mesh_paths_to_file_uri",
]
