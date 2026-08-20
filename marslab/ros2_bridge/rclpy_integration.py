from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from marslab.config.schema.rover_ros2 import Ros2BridgeConfig
from marslab.ros2_bridge.context import BridgeContext
from marslab.ros2_bridge.rclpy_publishers import (
    create_cmd_vel_setup,
    create_ground_truth_setup,
    create_noisy_imu_setup,
    create_rclpy_node,
    create_robot_description_setup,
    create_static_tf_setup,
    create_wheel_odometry_setup,
    resolve_qos_bundle,
)


def init_rclpy_side(
    ros2_cfg: dict[str, Any],
    sensor_frames: Iterable[tuple[str, Any]],
    node_name: str = "marslab_stage3_runtime",
    *,
    urdf_path: str | None = None,
    wheel_odom_params: dict[str, Any] | None = None,
    imu_noise_params: dict[str, Any] | None = None,
    wheel_odom_publish_tf: bool,
) -> BridgeContext:
    import rclpy  # noqa: PLC0415 -- Isaac Sim runtime dependency
    from rclpy import parameter  # noqa: PLC0415 -- Isaac Sim runtime dependency

    if not rclpy.ok():
        rclpy.init(args=None)

    config = Ros2BridgeConfig.model_validate(ros2_cfg)
    qos = resolve_qos_bundle(config)
    node = create_rclpy_node(rclpy, parameter, config, node_name)
    cmd_vel_subscription, twist_state = create_cmd_vel_setup(node, config, qos)
    static_tf_broadcaster = create_static_tf_setup(node, config, sensor_frames, qos)
    robot_description_ctx = create_robot_description_setup(node, config, urdf_path)
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
        robot_description_ctx=robot_description_ctx,
        wheel_odom_ctx=wheel_odom_ctx,
        imu_noise_ctx=imu_noise_ctx,
    )


__all__ = ["init_rclpy_side"]
