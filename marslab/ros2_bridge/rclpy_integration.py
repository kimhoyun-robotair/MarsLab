"""Assemble the optional rclpy side of the runtime bridge.
Factories return one context containing subscribers and publishers.
Imports remain deferred for CPU-only configuration checks."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from marslab.config.schema.rover_ros2 import Ros2BridgeConfig
from marslab.ros2_bridge.context import BridgeContext
from marslab.ros2_bridge.rclpy_publishers import (
    create_cmd_vel_setup,
    create_ground_truth_setup,
    create_noisy_imu_setup,
    create_rclpy_node,
    create_static_tf_setup,
    create_wheel_odometry_setup,
    resolve_qos_bundle,
)


def init_rclpy_side(
    ros2_cfg: dict[str, Any],
    sensor_frames: Iterable[tuple[str, Any]],
    node_name: str = "marslab_stage3_runtime",
    *,
    wheel_odom_params: dict[str, Any] | None = None,
    imu_noise_params: dict[str, Any] | None = None,
    wheel_odom_publish_tf: bool,
) -> BridgeContext:
    import rclpy  # noqa: PLC0415 -- Isaac Sim runtime dependency
    from rclpy import parameter  # noqa: PLC0415 -- Isaac Sim runtime dependency

    config = Ros2BridgeConfig.model_validate(ros2_cfg)
    qos = resolve_qos_bundle(config)
    owns_rclpy = not rclpy.ok()
    node = None
    try:
        if owns_rclpy:
            rclpy.init(args=None)
        node = create_rclpy_node(rclpy, parameter, config, node_name)
        cmd_vel_subscription, twist_state = create_cmd_vel_setup(node, config, qos)
        static_tf_broadcaster = create_static_tf_setup(node, config, sensor_frames, qos)
        odom_ctx = create_ground_truth_setup(node, config, qos)
        wheel_odom_ctx = create_wheel_odometry_setup(
            node,
            config,
            wheel_odom_params,
            wheel_odom_publish_tf,
            qos,
        )
        imu_noise_ctx = create_noisy_imu_setup(node, config, imu_noise_params, qos)

        return BridgeContext(
            node=node,
            cmd_vel_subscription=cmd_vel_subscription,
            static_tf_broadcaster=static_tf_broadcaster,
            odom_ctx=odom_ctx,
            twist_state=twist_state,
            shutdown=rclpy.try_shutdown if owns_rclpy else None,
            wheel_odom_ctx=wheel_odom_ctx,
            imu_noise_ctx=imu_noise_ctx,
        )
    except BaseException:
        if node is not None:
            try:
                node.destroy_node()
                logging.getLogger(__name__).info("Partial ROS node destroyed after setup failure.")
            except Exception:
                logging.getLogger(__name__).exception("Partial ROS node cleanup failed.")
        if owns_rclpy:
            try:
                rclpy.try_shutdown()
                logging.getLogger(__name__).info("rclpy context closed after setup failure.")
            except Exception:
                logging.getLogger(__name__).exception("Partial rclpy context cleanup failed.")
        raise


__all__ = ["init_rclpy_side"]
