"""Evaluation-only ground-truth pose publisher.

This module publishes the articulation's absolute Isaac-world pose as a
timestamped ``nav_msgs/Odometry`` message.  It is deliberately topic-only:
the operational ``odom``/``base_link`` stream and its optional transform
authority live in :mod:`marslab.ros2_bridge.wheel_odometry_publisher`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from marslab.ros2_bridge.odometry_math import world_twist_to_body


def _set_xyz(target: Any, vec: NDArray[np.float32]) -> None:
    """Copy a shape-(3,) vector into a ROS2 message's ``.x/.y/.z`` fields."""
    target.x = float(vec[0])
    target.y = float(vec[1])
    target.z = float(vec[2])


def _set_wxyz(target: Any, quat: NDArray[np.float32]) -> None:
    """Copy a scalar-first shape-(4,) quaternion into ``.w/.x/.y/.z`` fields."""
    target.w = float(quat[0])
    target.x = float(quat[1])
    target.y = float(quat[2])
    target.z = float(quat[3])


@dataclass
class GroundTruthPosePublisherContext:
    """Handles and labels carried across ground-truth publish calls."""

    publisher: Any
    node: Any
    frame_id: str = "map"
    child_frame_id: str = "base_link_gt"


def create_ground_truth_pose_publisher(
    node: Any,
    topic: str,
    queue_size: int = 10,
    frame_id: str = "map",
    child_frame_id: str = "base_link_gt",
    *,
    odom_qos: Any = None,
) -> GroundTruthPosePublisherContext:
    """Create the topic-only ground-truth pose publisher.

    Args:
        node: ``rclpy`` node.
        topic: Fully-qualified GT trajectory topic (e.g.
            ``/rover/GT_Trajectory``).
        queue_size: rclpy QoS depth.  Ignored when ``odom_qos`` is
            provided (the QoSProfile carries its own depth).
        frame_id: Ground-truth parent frame, normally ``map``.
        child_frame_id: Ground-truth child frame, normally ``base_link_gt``.
        odom_qos: Optional ``rclpy.qos.QoSProfile`` for the
            ``nav_msgs/Odometry`` publisher.  When ``None`` the
            publisher is created with the integer ``queue_size``
            overload (rclpy default profile).

    Returns:
        :class:`GroundTruthPosePublisherContext` to be reused by
        :func:`publish_ground_truth_pose` on every sim step.
    """
    from nav_msgs.msg import Odometry

    if odom_qos is not None:
        publisher = node.create_publisher(Odometry, topic, odom_qos)
    else:
        publisher = node.create_publisher(Odometry, topic, queue_size)

    return GroundTruthPosePublisherContext(
        publisher=publisher,
        node=node,
        frame_id=frame_id,
        child_frame_id=child_frame_id,
    )


def publish_ground_truth_pose(
    ctx: GroundTruthPosePublisherContext,
    cur_pos_world: NDArray[np.float32],
    cur_quat_world: NDArray[np.float32],
    linear_vel_world: NDArray[np.float32],
    angular_vel_world: NDArray[np.float32],
) -> None:
    """Publish one absolute Isaac-world pose as ``nav_msgs/Odometry``.

    Args:
        ctx: Context returned by :func:`create_ground_truth_pose_publisher`.
        cur_pos_world: Current chassis position in world frame, shape ``(3,)``.
        cur_quat_world: Current chassis orientation in world frame,
            shape ``(4,)`` scalar-first.
        linear_vel_world: World-frame linear velocity of the root body,
            shape ``(3,)``.
        angular_vel_world: World-frame angular velocity of the root body,
            shape ``(3,)``.
    """
    from nav_msgs.msg import Odometry

    cur_pos_world = np.asarray(cur_pos_world, dtype=np.float32)
    cur_quat_world = np.asarray(cur_quat_world, dtype=np.float32)
    linear_body, angular_body = world_twist_to_body(
        linear_vel_world, angular_vel_world, cur_quat_world
    )

    now = ctx.node.get_clock().now().to_msg()

    odom = Odometry()
    odom.header.stamp = now
    odom.header.frame_id = ctx.frame_id
    odom.child_frame_id = ctx.child_frame_id
    _set_xyz(odom.pose.pose.position, cur_pos_world)
    _set_wxyz(odom.pose.pose.orientation, cur_quat_world)
    _set_xyz(odom.twist.twist.linear, linear_body)
    _set_xyz(odom.twist.twist.angular, angular_body)
    ctx.publisher.publish(odom)


__all__ = [
    "GroundTruthPosePublisherContext",
    "create_ground_truth_pose_publisher",
    "publish_ground_truth_pose",
]
