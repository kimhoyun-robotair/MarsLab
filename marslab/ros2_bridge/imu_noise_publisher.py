"""Python-side IMU noise injection with a seeded RNG.

The OmniGraph ``ReadIMU`` → ``PubIMU`` path publishes raw PhysX IMU
readings with no Gaussian noise on ``/<ns>/imu``.  This module provides
an optional rclpy-side publisher that reads the same IMU frame, injects
zero-mean Gaussian noise on all six axes (3 linear-acceleration +
3 angular-velocity), and publishes ``sensor_msgs/Imu`` on
``/<ns>/imu_noisy`` — a *separate* topic from the OmniGraph ``PubIMU``
output — so SLAM stacks that need repeatable noise sequences can subscribe
to ``imu_noisy`` instead.  The two topics are distinct by design: running
both publishers simultaneously does NOT produce duplicate messages on any
single topic.

The seeded :func:`numpy.random.default_rng` call guarantees that the same
``seed`` value produces an identical noise sequence across multiple runs.
Omitting ``seed`` (``None``) falls back to nondeterministic behaviour,
preserving the original behaviour of the OmniGraph path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np


@dataclass
class ImuNoiseContext:
    publisher: Any
    node: Any
    rng: np.random.Generator
    sigma_lin_acc: float
    sigma_ang_vel: float
    imu_prim_path: str
    frame_id: str = "imu_link"


def create_imu_noise_publisher(
    node: Any,
    topic: str,
    imu_prim_path: str,
    *,
    sigma_lin_acc: float = 0.0,
    sigma_ang_vel: float = 0.0,
    seed: Optional[int] = None,
    queue_size: int = 10,
    sensor_qos: Optional[Any] = None,
    frame_id: str = "imu_link",
) -> ImuNoiseContext:
    """Create a publisher that injects seeded Gaussian noise onto IMU readings."""
    from sensor_msgs.msg import Imu  # noqa: PLC0415

    if sensor_qos is not None:
        publisher = node.create_publisher(Imu, topic, sensor_qos)
    else:
        publisher = node.create_publisher(Imu, topic, queue_size)

    rng = np.random.default_rng(seed)
    return ImuNoiseContext(
        publisher=publisher,
        node=node,
        rng=rng,
        sigma_lin_acc=float(sigma_lin_acc),
        sigma_ang_vel=float(sigma_ang_vel),
        imu_prim_path=imu_prim_path,
        frame_id=frame_id,
    )


def publish_imu_with_noise(
    ctx: ImuNoiseContext,
    lin_acc: np.ndarray,
    ang_vel: np.ndarray,
    orientation_wxyz: Optional[np.ndarray] = None,
) -> None:
    """Inject Gaussian noise and publish sensor_msgs/Imu."""
    from sensor_msgs.msg import Imu  # noqa: PLC0415

    la = np.asarray(lin_acc, dtype=np.float64).copy()
    av = np.asarray(ang_vel, dtype=np.float64).copy()

    if ctx.sigma_lin_acc > 0.0:
        la += ctx.rng.normal(0.0, ctx.sigma_lin_acc, 3)
    if ctx.sigma_ang_vel > 0.0:
        av += ctx.rng.normal(0.0, ctx.sigma_ang_vel, 3)

    msg = Imu()
    msg.header.stamp = ctx.node.get_clock().now().to_msg()
    msg.header.frame_id = ctx.frame_id

    msg.linear_acceleration.x = float(la[0])
    msg.linear_acceleration.y = float(la[1])
    msg.linear_acceleration.z = float(la[2])

    msg.angular_velocity.x = float(av[0])
    msg.angular_velocity.y = float(av[1])
    msg.angular_velocity.z = float(av[2])

    if orientation_wxyz is not None:
        q = np.asarray(orientation_wxyz, dtype=np.float64)
        msg.orientation.w = float(q[0])
        msg.orientation.x = float(q[1])
        msg.orientation.y = float(q[2])
        msg.orientation.z = float(q[3])
    else:
        msg.orientation_covariance[0] = -1.0

    # Diagonal covariance: sigma^2 on each axis, -1 if sensor unavailable
    la_var = ctx.sigma_lin_acc ** 2 if ctx.sigma_lin_acc > 0.0 else 0.0
    av_var = ctx.sigma_ang_vel ** 2 if ctx.sigma_ang_vel > 0.0 else 0.0
    for i in range(3):
        msg.linear_acceleration_covariance[i * 3 + i] = la_var
        msg.angular_velocity_covariance[i * 3 + i] = av_var

    ctx.publisher.publish(msg)


__all__ = [
    "ImuNoiseContext",
    "create_imu_noise_publisher",
    "publish_imu_with_noise",
]
