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
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Tuple

import numpy as np

from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber
from marslab.ros2_bridge.odometry_publisher import (
    OdometryPublisherContext,
    create_odometry_publisher,
    publish_odometry,
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


@dataclass
class BridgeContext:
    """Aggregate handles used by the Stage-3 main loop."""

    node: Any
    cmd_vel_subscription: Any
    static_tf_broadcaster: Any
    odom_ctx: OdometryPublisherContext
    twist_state: Dict[str, float]


def _ns_topic(ns: str, name: str) -> str:
    return f"/{ns}/{name}"


def init_rclpy_side(
    ros2_cfg: Dict[str, Any],
    sensor_frames: Iterable[Tuple[str, Any]],
    init_pos_world: np.ndarray,
    init_quat_world: np.ndarray,
    node_name: str = "marslab_stage3_runtime",
) -> BridgeContext:
    """Boot rclpy and wire cmd_vel / static TF / odom publishers.

    Args:
        ros2_cfg: Merged ``rover.ros2`` block (namespace + topic map).
        sensor_frames: Iterable of ``(child_frame_id, local_xyz)``
            pairs for static sensor TFs.
        init_pos_world: Rover initial world position, shape ``(3,)``.
        init_quat_world: Rover initial world orientation (scalar-first).
        node_name: rclpy node name; namespaced by ``ros2_cfg["namespace"]``.

    Returns:
        :class:`BridgeContext` holding every handle the main loop
        needs plus the shared ``twist_state`` dict written by the
        cmd_vel subscriber callback.
    """
    import rclpy
    import rclpy.parameter

    if not rclpy.ok():
        rclpy.init(args=None)

    ns = str(ros2_cfg["namespace"])
    topics = dict(ros2_cfg["topics"])

    node = rclpy.create_node(
        f"{ns}_{node_name}",
        parameter_overrides=[
            rclpy.parameter.Parameter(
                "use_sim_time",
                rclpy.parameter.Parameter.Type.BOOL,
                True,
            )
        ],
    )

    twist_state: Dict[str, float] = {"v": 0.0, "w": 0.0}
    cmd_vel_topic = _ns_topic(ns, topics["cmd_vel"])
    cmd_vel_sub = create_cmd_vel_subscriber(node, cmd_vel_topic, twist_state)

    static_broadcaster = publish_static_sensor_tfs(node, sensor_frames)

    odom_topic = _ns_topic(ns, topics["odom"])
    # R3 (2026-04-22) G5: pull frame_id / child_frame_id / queue_size from
    # YAML when the rover block declares an ``odom_publisher`` sub-map. The
    # sub-map mirrors ``OdomPublisherConfig`` (marslab/config/schema/robot.py)
    # so slam_toolbox and Nav2 frame names stay aligned with a single YAML
    # source. Falls back to the historical function defaults when the key
    # is absent so existing scenario YAMLs keep loading unchanged.
    odom_pub_cfg = ros2_cfg.get("odom_publisher", {}) if isinstance(ros2_cfg, dict) else {}
    odom_ctx = create_odometry_publisher(
        node=node,
        topic=odom_topic,
        init_pos_world=init_pos_world,
        init_quat_world=init_quat_world,
        queue_size=int(odom_pub_cfg.get("queue_size", 10)),
        frame_id=str(odom_pub_cfg.get("frame_id", "odom")),
        child_frame_id=str(odom_pub_cfg.get("child_frame_id", "base_link")),
    )

    return BridgeContext(
        node=node,
        cmd_vel_subscription=cmd_vel_sub,
        static_tf_broadcaster=static_broadcaster,
        odom_ctx=odom_ctx,
        twist_state=twist_state,
    )


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
