"""rclpy wrapper that publishes ``odom→base_link`` TF + ``nav_msgs/Odometry``.

Pure quaternion math lives in :mod:`marslab.ros2_bridge.odometry_math`;
this module owns the ROS2 side (publisher + TransformBroadcaster + the
``publish_odometry`` step-loop callback).  Keeping the ROS2-dependent
surface small lets us unit-test every non-trivial formula offline (P3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from marslab.ros2_bridge.odometry_math import (
    compute_odom_delta,
    world_twist_to_body,
)


def _set_xyz(target: Any, vec: np.ndarray) -> None:
    """Copy a shape-(3,) vector into a ROS2 message's ``.x/.y/.z`` fields."""
    target.x = float(vec[0])
    target.y = float(vec[1])
    target.z = float(vec[2])


def _set_wxyz(target: Any, quat: np.ndarray) -> None:
    """Copy a scalar-first shape-(4,) quaternion into ``.w/.x/.y/.z`` fields."""
    target.w = float(quat[0])
    target.x = float(quat[1])
    target.y = float(quat[2])
    target.z = float(quat[3])


@dataclass
class OdometryPublisherContext:
    """Handles + state carried across step-loop calls.

    The odom frame is anchored at the rover's initial world pose, so
    the initial position / orientation travel alongside the publisher
    instead of being recomputed every tick.
    """

    publisher: Any
    tf_broadcaster: Any
    node: Any
    init_pos_world: np.ndarray
    init_quat_world: np.ndarray
    frame_id: str = "odom"
    child_frame_id: str = "base_link"


def create_odometry_publisher(
    node: Any,
    topic: str,
    init_pos_world: np.ndarray,
    init_quat_world: np.ndarray,
    queue_size: int = 10,
    frame_id: str = "odom",
    child_frame_id: str = "base_link",
    *,
    odom_qos: Optional[Any] = None,
    tf_qos: Optional[Any] = None,
) -> OdometryPublisherContext:
    """Create the odometry publisher + TF broadcaster bundle.

    Args:
        node: ``rclpy`` node.
        topic: Fully-qualified odometry topic (e.g. ``/rover/odom``).
        init_pos_world: Rover position at ``t=0`` in world frame, shape ``(3,)``.
        init_quat_world: Rover orientation at ``t=0`` in world frame,
            shape ``(4,)`` scalar-first.
        queue_size: rclpy QoS depth.  Ignored when ``odom_qos`` is
            provided (the QoSProfile carries its own depth).
        frame_id: Odometry parent frame.  Must match the slam_toolbox
            ``odom_frame`` param.
        child_frame_id: Odometry child frame.  Must match
            ``base_frame``.
        odom_qos: Optional ``rclpy.qos.QoSProfile`` for the
            ``nav_msgs/Odometry`` publisher.  When ``None`` the
            publisher is created with the integer ``queue_size``
            overload (rclpy default profile).  Reviewer 2 #04 (2026-04-24).
        tf_qos: Optional ``rclpy.qos.QoSProfile`` forwarded to the
            ``tf2_ros.TransformBroadcaster``.  ``TransformBroadcaster``
            takes a ``qos`` keyword argument in tf2_ros >= 0.25.  When
            ``None`` the default ``/tf`` QoS (RELIABLE + KEEP_LAST 100)
            is used.

    Returns:
        :class:`OdometryPublisherContext` to be reused by
        :func:`publish_odometry` on every sim step.
    """
    from nav_msgs.msg import Odometry
    from tf2_ros import TransformBroadcaster

    if odom_qos is not None:
        publisher = node.create_publisher(Odometry, topic, odom_qos)
    else:
        publisher = node.create_publisher(Odometry, topic, queue_size)

    if tf_qos is not None:
        # TransformBroadcaster added the ``qos`` keyword in
        # tf2_ros >= 0.25 (ROS 2 Humble+).  Older installs fall back
        # to the no-argument constructor via the TypeError branch so
        # MarsLab still boots on a mismatched tf2_ros.
        try:
            tf_broadcaster = TransformBroadcaster(node, qos=tf_qos)
        except TypeError:
            tf_broadcaster = TransformBroadcaster(node)
    else:
        tf_broadcaster = TransformBroadcaster(node)

    return OdometryPublisherContext(
        publisher=publisher,
        tf_broadcaster=tf_broadcaster,
        node=node,
        init_pos_world=np.asarray(init_pos_world, dtype=np.float32).copy(),
        init_quat_world=np.asarray(init_quat_world, dtype=np.float32).copy(),
        frame_id=frame_id,
        child_frame_id=child_frame_id,
    )


def publish_odometry(
    ctx: OdometryPublisherContext,
    cur_pos_world: np.ndarray,
    cur_quat_world: np.ndarray,
    linear_vel_world: np.ndarray,
    angular_vel_world: np.ndarray,
) -> None:
    """Publish a single ``odom→base_link`` TF + ``Odometry`` message.

    Args:
        ctx: Context returned by :func:`create_odometry_publisher`.
        cur_pos_world: Current chassis position in world frame, shape ``(3,)``.
        cur_quat_world: Current chassis orientation in world frame,
            shape ``(4,)`` scalar-first.
        linear_vel_world: World-frame linear velocity of the root body,
            shape ``(3,)``.
        angular_vel_world: World-frame angular velocity of the root body,
            shape ``(3,)``.
    """
    from geometry_msgs.msg import TransformStamped
    from nav_msgs.msg import Odometry

    cur_pos_world = np.asarray(cur_pos_world, dtype=np.float32)
    cur_quat_world = np.asarray(cur_quat_world, dtype=np.float32)
    delta_pos_odom, delta_quat_odom = compute_odom_delta(
        cur_pos_world, cur_quat_world, ctx.init_pos_world, ctx.init_quat_world
    )
    linear_body, angular_body = world_twist_to_body(
        linear_vel_world, angular_vel_world, cur_quat_world
    )

    now = ctx.node.get_clock().now().to_msg()

    tf_msg = TransformStamped()
    tf_msg.header.stamp = now
    tf_msg.header.frame_id = ctx.frame_id
    tf_msg.child_frame_id = ctx.child_frame_id
    _set_xyz(tf_msg.transform.translation, delta_pos_odom)
    _set_wxyz(tf_msg.transform.rotation, delta_quat_odom)
    ctx.tf_broadcaster.sendTransform(tf_msg)

    odom = Odometry()
    odom.header.stamp = now
    odom.header.frame_id = ctx.frame_id
    odom.child_frame_id = ctx.child_frame_id
    _set_xyz(odom.pose.pose.position, delta_pos_odom)
    _set_wxyz(odom.pose.pose.orientation, delta_quat_odom)
    _set_xyz(odom.twist.twist.linear, linear_body)
    _set_xyz(odom.twist.twist.angular, angular_body)
    ctx.publisher.publish(odom)
