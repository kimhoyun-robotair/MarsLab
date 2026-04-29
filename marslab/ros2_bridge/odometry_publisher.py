"""rclpy wrapper that publishes ``odom→base_link`` TF + ``nav_msgs/Odometry``.

Pure quaternion math lives in :mod:`marslab.ros2_bridge.odometry_math`;
this module owns the ROS2 side (publisher + TransformBroadcaster + the
``publish_odometry`` step-loop callback).  Keeping the ROS2-dependent
surface small lets every non-trivial formula be unit-tested offline.
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

    ``tf_broadcaster`` may be ``None`` when the caller opts out of
    rclpy-side TF publishing -- the OmniGraph
    ``ROS2PublishTransformTree`` becomes the sole TF authority for
    ``odom -> base_link``.  ``publish_tf`` records the choice so
    :func:`publish_odometry` does not need to inspect the broadcaster
    handle to decide whether to skip ``sendTransform``.
    """

    publisher: Any
    tf_broadcaster: Optional[Any]
    node: Any
    init_pos_world: np.ndarray
    init_quat_world: np.ndarray
    frame_id: str = "odom"
    child_frame_id: str = "base_link"
    publish_tf: bool = True


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
    publish_tf: bool = True,
) -> OdometryPublisherContext:
    """Create the odometry publisher + (optional) TF broadcaster bundle.

    Args:
        node: ``rclpy`` node.
        topic: Fully-qualified odometry topic (e.g. ``/rover/odom``).
        init_pos_world: Rover position at ``t=0`` in world frame, shape ``(3,)``.
        init_quat_world: Rover orientation at ``t=0`` in world frame,
            shape ``(4,)`` scalar-first.
        queue_size: rclpy QoS depth.  Ignored when ``odom_qos`` is
            provided (the QoSProfile carries its own depth).
        frame_id: Odometry parent frame.  Must match the SLAM stack's
            ``odom_frame`` param.
        child_frame_id: Odometry child frame.  Must match
            ``base_frame``.
        odom_qos: Optional ``rclpy.qos.QoSProfile`` for the
            ``nav_msgs/Odometry`` publisher.  When ``None`` the
            publisher is created with the integer ``queue_size``
            overload (rclpy default profile).
        tf_qos: Optional ``rclpy.qos.QoSProfile`` forwarded to the
            ``tf2_ros.TransformBroadcaster``.  Ignored when
            ``publish_tf=False``.
        publish_tf: When ``True`` (default, backward compatible) the
            function constructs a ``tf2_ros.TransformBroadcaster`` and
            :func:`publish_odometry` broadcasts ``odom -> base_link``
            on ``/tf``.  When ``False`` the broadcaster is **not**
            constructed, ``ctx.tf_broadcaster`` stays ``None``, and
            :func:`publish_odometry` skips ``sendTransform`` -- this is
            the mode where the OmniGraph
            ``ROS2PublishTransformTree`` becomes the sole TF authority
            for ``odom -> base_link``.  Never run this ``True`` while a
            ``ros2 run topic_tools relay /tf_raw /tf`` external relay is
            active: that yields two parents for ``base_link`` in the TF
            tree.  ``tf2_ros`` is imported lazily inside the ``True``
            branch so a node without ``tf2_ros`` on PYTHONPATH still
            works in the ``False`` mode.

    Returns:
        :class:`OdometryPublisherContext` to be reused by
        :func:`publish_odometry` on every sim step.
    """
    from nav_msgs.msg import Odometry

    if odom_qos is not None:
        publisher = node.create_publisher(Odometry, topic, odom_qos)
    else:
        publisher = node.create_publisher(Odometry, topic, queue_size)

    tf_broadcaster: Optional[Any] = None
    if publish_tf:
        # Local import keeps callers that opt out (the default mode)
        # on systems without tf2_ros installed working.
        from tf2_ros import (
            TransformBroadcaster,
        )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

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
        publish_tf=publish_tf,
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

    if ctx.publish_tf and ctx.tf_broadcaster is not None:
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
