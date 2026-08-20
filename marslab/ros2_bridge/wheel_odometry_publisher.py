"""Integrate wheel encoders into operational odometry messages.
The optional publisher owns the dynamic odom-to-base transform.
ROS bindings are loaded only when the runtime bridge starts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np


@dataclass
class WheelOdometryContext:
    publisher: Any
    tf_broadcaster: Optional[Any]
    node: Any
    left_indices: np.ndarray
    right_indices: np.ndarray
    wheel_radius: float
    track_width: float
    slip_left: float
    slip_right: float
    sigma_omega: float
    rng: np.random.Generator
    frame_id: str = "odom"
    child_frame_id: str = "base_link"
    publish_tf: bool = False
    pose_diag: List[float] = field(default_factory=lambda: [1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2])
    twist_diag: List[float] = field(default_factory=lambda: [1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2])
    x: float = 0.0
    y: float = 0.0
    theta: float = 0.0
    last_stamp_ns: Optional[int] = None


def create_wheel_odometry_publisher(
    node: Any,
    topic: str,
    left_indices: List[int],
    right_indices: List[int],
    wheel_radius: float,
    track_width: float,
    *,
    slip_left: float = 0.0,
    slip_right: float = 0.0,
    sigma_omega: float = 0.0,
    seed: Optional[int] = None,
    queue_size: int = 10,
    odom_qos: Optional[Any] = None,
    tf_qos: Optional[Any] = None,
    frame_id: str = "odom",
    child_frame_id: str = "base_link",
    publish_tf: bool = False,
    pose_diag: Optional[List[float]] = None,
    twist_diag: Optional[List[float]] = None,
) -> WheelOdometryContext:
    """Create publisher + optional TF broadcaster for wheel-encoder odometry."""
    from nav_msgs.msg import Odometry

    if wheel_radius <= 0.0:
        raise ValueError(f"wheel_radius must be > 0, got {wheel_radius}")
    if track_width <= 0.0:
        raise ValueError(f"track_width must be > 0, got {track_width}")
    if not left_indices or not right_indices:
        raise ValueError("left_indices and right_indices must be non-empty")

    if odom_qos is not None:
        publisher = node.create_publisher(Odometry, topic, odom_qos)
    else:
        publisher = node.create_publisher(Odometry, topic, queue_size)

    tf_broadcaster: Optional[Any] = None
    if publish_tf:
        from tf2_ros import TransformBroadcaster  # noqa: PLC0415

        if tf_qos is not None:
            try:
                tf_broadcaster = TransformBroadcaster(node, qos=tf_qos)
            except TypeError:
                tf_broadcaster = TransformBroadcaster(node)
        else:
            tf_broadcaster = TransformBroadcaster(node)

    return WheelOdometryContext(
        publisher=publisher,
        tf_broadcaster=tf_broadcaster,
        node=node,
        left_indices=np.asarray(left_indices, dtype=np.int32),
        right_indices=np.asarray(right_indices, dtype=np.int32),
        wheel_radius=float(wheel_radius),
        track_width=float(track_width),
        slip_left=float(slip_left),
        slip_right=float(slip_right),
        sigma_omega=float(sigma_omega),
        rng=np.random.default_rng(seed),
        frame_id=frame_id,
        child_frame_id=child_frame_id,
        publish_tf=publish_tf,
        pose_diag=(list(pose_diag) if pose_diag is not None else [1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2]),
        twist_diag=(
            list(twist_diag) if twist_diag is not None else [1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2]
        ),
    )


def publish_wheel_odometry(ctx: WheelOdometryContext, joint_velocities: np.ndarray) -> None:
    """Integrate skid-steer FK and publish nav_msgs/Odometry on /rover/odom."""
    from geometry_msgs.msg import TransformStamped
    from nav_msgs.msg import Odometry

    jv = joint_velocities[0] if joint_velocities.ndim == 2 else joint_velocities
    omega_l = float(np.mean(jv[ctx.left_indices]))
    omega_r = float(np.mean(jv[ctx.right_indices]))

    omega_l_eff = omega_l * (1.0 - ctx.slip_left)
    omega_r_eff = omega_r * (1.0 - ctx.slip_right)
    if ctx.sigma_omega > 0.0:
        omega_l_eff += float(ctx.rng.normal(0.0, ctx.sigma_omega))
        omega_r_eff += float(ctx.rng.normal(0.0, ctx.sigma_omega))

    v = ctx.wheel_radius * 0.5 * (omega_l_eff + omega_r_eff)
    w = ctx.wheel_radius * (omega_r_eff - omega_l_eff) / ctx.track_width

    now_msg = ctx.node.get_clock().now().to_msg()
    now_ns = int(now_msg.sec) * 1_000_000_000 + int(now_msg.nanosec)
    dt = 0.0 if ctx.last_stamp_ns is None else max(0.0, (now_ns - ctx.last_stamp_ns) * 1e-9)
    ctx.last_stamp_ns = now_ns

    ctx.theta += w * dt
    ctx.x += v * float(np.cos(ctx.theta)) * dt
    ctx.y += v * float(np.sin(ctx.theta)) * dt

    qw = float(np.cos(ctx.theta * 0.5))
    qz = float(np.sin(ctx.theta * 0.5))

    if ctx.publish_tf and ctx.tf_broadcaster is not None:
        tf_msg = TransformStamped()
        tf_msg.header.stamp = now_msg
        tf_msg.header.frame_id = ctx.frame_id
        tf_msg.child_frame_id = ctx.child_frame_id
        tf_msg.transform.translation.x = ctx.x
        tf_msg.transform.translation.y = ctx.y
        tf_msg.transform.translation.z = 0.0
        tf_msg.transform.rotation.w = qw
        tf_msg.transform.rotation.x = 0.0
        tf_msg.transform.rotation.y = 0.0
        tf_msg.transform.rotation.z = qz
        ctx.tf_broadcaster.sendTransform(tf_msg)

    msg = Odometry()
    msg.header.stamp = now_msg
    msg.header.frame_id = ctx.frame_id
    msg.child_frame_id = ctx.child_frame_id
    msg.pose.pose.position.x = ctx.x
    msg.pose.pose.position.y = ctx.y
    msg.pose.pose.position.z = 0.0
    msg.pose.pose.orientation.w = qw
    msg.pose.pose.orientation.x = 0.0
    msg.pose.pose.orientation.y = 0.0
    msg.pose.pose.orientation.z = qz
    msg.twist.twist.linear.x = v
    msg.twist.twist.angular.z = w
    for i in range(6):
        msg.pose.covariance[i * 6 + i] = ctx.pose_diag[i]
        msg.twist.covariance[i * 6 + i] = ctx.twist_diag[i]
    ctx.publisher.publish(msg)


__all__ = [
    "WheelOdometryContext",
    "create_wheel_odometry_publisher",
    "publish_wheel_odometry",
]
