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
:mod:`marslab.ros2_bridge.rclpy_integration` respectively. The original
definitions are preserved as DISABLED comments below per
``feedback_no_delete_comment``.
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
from marslab.ros2_bridge.sensor_graph import (
    GRAPH_PATH,
    SensorGraphHandle,
    build_sensor_graph,
)
from marslab.ros2_bridge.tf_broadcaster import (
    build_static_sensor_transforms,
    publish_static_sensor_tfs,
)

# DISABLED R4-6 (2026-04-22): original BridgeContext dataclass + init_rclpy_side
# body moved to marslab.ros2_bridge.context and .rclpy_integration. Retained
# here as comments per feedback_no_delete_comment to preserve rollback.
#
# from dataclasses import dataclass
# from typing import Any, Dict, Iterable, Tuple
# import numpy as np
#
# @dataclass
# class BridgeContext:
#     """Aggregate handles used by the Stage-3 main loop."""
#
#     node: Any
#     cmd_vel_subscription: Any
#     static_tf_broadcaster: Any
#     odom_ctx: OdometryPublisherContext
#     twist_state: Dict[str, float]
#
#
# def _ns_topic(ns: str, name: str) -> str:
#     return f"/{ns}/{name}"
#
#
# def init_rclpy_side(
#     ros2_cfg: Dict[str, Any],
#     sensor_frames: Iterable[Tuple[str, Any]],
#     init_pos_world: np.ndarray,
#     init_quat_world: np.ndarray,
#     node_name: str = "marslab_stage3_runtime",
# ) -> BridgeContext:
#     import rclpy
#     import rclpy.parameter
#
#     if not rclpy.ok():
#         rclpy.init(args=None)
#
#     ns = str(ros2_cfg["namespace"])
#     topics = dict(ros2_cfg["topics"])
#
#     node = rclpy.create_node(
#         f"{ns}_{node_name}",
#         parameter_overrides=[
#             rclpy.parameter.Parameter(
#                 "use_sim_time",
#                 rclpy.parameter.Parameter.Type.BOOL,
#                 True,
#             )
#         ],
#     )
#
#     twist_state: Dict[str, float] = {"v": 0.0, "w": 0.0}
#     cmd_vel_topic = _ns_topic(ns, topics["cmd_vel"])
#     cmd_vel_sub = create_cmd_vel_subscriber(node, cmd_vel_topic, twist_state)
#
#     static_broadcaster = publish_static_sensor_tfs(node, sensor_frames)
#
#     odom_topic = _ns_topic(ns, topics["odom"])
#     odom_pub_cfg = ros2_cfg.get("odom_publisher", {}) if isinstance(ros2_cfg, dict) else {}
#     odom_ctx = create_odometry_publisher(
#         node=node,
#         topic=odom_topic,
#         init_pos_world=init_pos_world,
#         init_quat_world=init_quat_world,
#         queue_size=int(odom_pub_cfg.get("queue_size", 10)),
#         frame_id=str(odom_pub_cfg.get("frame_id", "odom")),
#         child_frame_id=str(odom_pub_cfg.get("child_frame_id", "base_link")),
#     )
#
#     return BridgeContext(
#         node=node,
#         cmd_vel_subscription=cmd_vel_sub,
#         static_tf_broadcaster=static_broadcaster,
#         odom_ctx=odom_ctx,
#         twist_state=twist_state,
#     )


__all__ = [
    "BridgeContext",
    "GRAPH_PATH",
    "OdometryPublisherContext",
    "SensorGraphHandle",
    "build_sensor_graph",
    "build_static_sensor_transforms",
    "create_cmd_vel_subscriber",
    "create_odometry_publisher",
    "init_rclpy_side",
    "publish_odometry",
    "publish_static_sensor_tfs",
]
