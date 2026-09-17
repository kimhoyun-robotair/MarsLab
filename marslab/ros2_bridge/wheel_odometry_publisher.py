"""Integrate wheel encoders into operational odometry messages.
The optional publisher owns the dynamic odom-to-base transform.
ROS bindings are loaded only when the runtime bridge starts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

import numpy as np

from marslab.ros2_bridge.odometry_math import encoder_planar_twist, wheel_contact_positions
from marslab.ros2_bridge.timestamp import ros_stamp_from_ns, split_stamp_ns


@dataclass
class WheelOdometryContext:
    publisher: Any
    tf_broadcaster: Optional[Any]
    node: Any
    left_indices: np.ndarray
    right_indices: np.ndarray
    steering_indices: np.ndarray
    wheel_radius: float
    wheel_positions: np.ndarray
    negate_steer: bool
    slip_left: float
    slip_right: float
    sigma_omega: float
    rng: np.random.Generator
    seed: Optional[int] = None
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
    *,
    steering_indices: List[int],
    wheelbase: float,
    track_steer: float,
    track_middle: float,
    negate_steer: bool,
    steering_axle_offset: float = 0.0,
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
    if len(left_indices) != 3 or len(right_indices) != 3 or len(steering_indices) != 4:
        raise ValueError("wheel odometry requires three wheels per bank and four steering joints")
    wheel_positions = wheel_contact_positions(
        wheelbase, track_steer, track_middle, steering_axle_offset
    )

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
        steering_indices=np.asarray(steering_indices, dtype=np.int32),
        wheel_radius=float(wheel_radius),
        wheel_positions=wheel_positions,
        negate_steer=negate_steer,
        slip_left=float(slip_left),
        slip_right=float(slip_right),
        sigma_omega=float(sigma_omega),
        rng=np.random.default_rng(seed),
        seed=seed,
        frame_id=frame_id,
        child_frame_id=child_frame_id,
        publish_tf=publish_tf,
        pose_diag=(list(pose_diag) if pose_diag is not None else [1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2]),
        twist_diag=(
            list(twist_diag) if twist_diag is not None else [1e-3, 1e-3, 1e6, 1e6, 1e6, 1e-2]
        ),
    )


def reset_wheel_odometry(ctx: WheelOdometryContext) -> None:
    """Reset the pose, sample baseline, and noise sequence for a new run."""
    ctx.x = 0.0
    ctx.y = 0.0
    ctx.theta = 0.0
    ctx.last_stamp_ns = None
    ctx.rng = np.random.default_rng(ctx.seed)


def publish_wheel_odometry(
    ctx: WheelOdometryContext,
    joint_velocities: np.ndarray,
    joint_positions: np.ndarray,
    *,
    stamp_ns: int,
) -> None:
    """Integrate measured Ackermann encoders and publish operational odometry."""
    split_stamp_ns(stamp_ns)
    if ctx.last_stamp_ns is not None:
        if stamp_ns < ctx.last_stamp_ns:
            raise ValueError("Wheel odometry time moved backwards; reset before a new run")
        if stamp_ns == ctx.last_stamp_ns:
            return

    from geometry_msgs.msg import TransformStamped
    from nav_msgs.msg import Odometry

    stamp = ros_stamp_from_ns(stamp_ns)
    dt = 0.0 if ctx.last_stamp_ns is None else (stamp_ns - ctx.last_stamp_ns) * 1e-9
    jv = joint_velocities[0] if joint_velocities.ndim == 2 else joint_velocities
    jp = joint_positions[0] if joint_positions.ndim == 2 else joint_positions
    omega_l_eff = jv[ctx.left_indices] * (1.0 - ctx.slip_left)
    omega_r_eff = jv[ctx.right_indices] * (1.0 - ctx.slip_right)
    if ctx.sigma_omega > 0.0:
        omega_l_eff += float(ctx.rng.normal(0.0, ctx.sigma_omega))
        omega_r_eff += float(ctx.rng.normal(0.0, ctx.sigma_omega))

    steer = jp[ctx.steering_indices] * (-1.0 if ctx.negate_steer else 1.0)
    wheel_speeds = ctx.wheel_radius * np.concatenate((omega_l_eff, omega_r_eff))
    v, w = encoder_planar_twist(wheel_speeds, steer, ctx.wheel_positions)

    ctx.last_stamp_ns = stamp_ns

    delta_yaw = w * dt
    distance = v * dt * float(np.sinc(delta_yaw / (2.0 * np.pi)))
    midpoint_yaw = ctx.theta + delta_yaw * 0.5
    ctx.x += distance * float(np.cos(midpoint_yaw))
    ctx.y += distance * float(np.sin(midpoint_yaw))
    ctx.theta += delta_yaw

    qw = float(np.cos(ctx.theta * 0.5))
    qz = float(np.sin(ctx.theta * 0.5))

    if ctx.publish_tf and ctx.tf_broadcaster is not None:
        tf_msg = TransformStamped()
        tf_msg.header.stamp = stamp
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
    msg.header.stamp = stamp
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
    "reset_wheel_odometry",
]
