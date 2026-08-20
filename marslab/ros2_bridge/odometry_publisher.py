"""Publish absolute evaluation ground-truth pose messages.
The stream is topic-only and does not own operational odometry TF.
ROS message bindings load only when a publisher is created."""

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
    """Create the topic-only ground-truth pose publisher."""
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
    """Publish one absolute Isaac-world pose as ``nav_msgs/Odometry``."""
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
