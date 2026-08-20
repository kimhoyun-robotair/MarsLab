"""Construct publisher setups and their validated QoS bundle.
Each factory exposes the narrow handle used by runtime orchestration.
ROS bindings remain local to the runtime call path."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from marslab.config.schema.rover_ros2 import Ros2BridgeConfig
from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber
from marslab.ros2_bridge.imu_noise_publisher import create_imu_noise_publisher
from marslab.ros2_bridge.odometry_publisher import create_ground_truth_pose_publisher
from marslab.ros2_bridge.robot_description_publisher import publish_robot_description
from marslab.ros2_bridge.sensor_graph_builder import _ns_topic
from marslab.ros2_bridge.tf_broadcaster import publish_static_sensor_tfs
from marslab.ros2_bridge.wheel_odometry_publisher import create_wheel_odometry_publisher


@dataclass(frozen=True, slots=True)
class QosBundle:
    cmd_vel: Any
    odom: Any
    sensor: Any
    tf: Any


def resolve_qos_bundle(config: Ros2BridgeConfig) -> QosBundle:
    from marslab.ros2_bridge.qos import to_rclpy_qos  # noqa: PLC0415

    return QosBundle(
        cmd_vel=to_rclpy_qos(config.cmd_vel_qos),
        odom=to_rclpy_qos(config.odom_qos),
        sensor=to_rclpy_qos(config.sensor_qos),
        tf=to_rclpy_qos(config.tf_qos),
    )


def create_rclpy_node(
    rclpy: Any,
    parameter: Any,
    config: Ros2BridgeConfig,
    node_name: str,
) -> Any:
    return rclpy.create_node(
        f"{config.namespace}_{node_name}",
        parameter_overrides=[
            parameter.Parameter(
                "use_sim_time",
                parameter.Parameter.Type.BOOL,
                True,
            )
        ],
    )


def create_cmd_vel_setup(
    node: Any,
    config: Ros2BridgeConfig,
    qos: QosBundle,
) -> tuple[Any, dict[str, float]]:
    twist_state = {"v": 0.0, "w": 0.0}
    subscription = create_cmd_vel_subscriber(
        node,
        _ns_topic(config.namespace, config.topics.cmd_vel),
        twist_state,
        queue_size=config.cmd_vel_queue_size,
        qos=qos.cmd_vel,
    )
    return subscription, twist_state


def create_static_tf_setup(
    node: Any,
    config: Ros2BridgeConfig,
    sensor_frames: Iterable[tuple[str, Any]],
    qos: QosBundle,
) -> Any:
    return publish_static_sensor_tfs(
        node,
        sensor_frames,
        parent_frame_id=config.sensor_parent_frame_id,
        qos=qos.tf,
    )


def create_robot_description_setup(
    node: Any,
    config: Ros2BridgeConfig,
    urdf_path: str | None,
) -> Any | None:
    if config.publish_robot_description and urdf_path:
        return publish_robot_description(
            node,
            urdf_path,
            topic=_ns_topic(config.namespace, config.topics.robot_description),
        )
    return None


def create_ground_truth_setup(node: Any, config: Ros2BridgeConfig, qos: QosBundle) -> Any:
    odom = config.odom_publisher
    return create_ground_truth_pose_publisher(
        node=node,
        topic=_ns_topic(config.namespace, config.topics.gt_trajectory),
        queue_size=odom.queue_size,
        frame_id=odom.gt_frame_id,
        child_frame_id=odom.gt_child_frame_id,
        odom_qos=qos.odom,
    )


def create_wheel_odometry_setup(
    node: Any,
    config: Ros2BridgeConfig,
    params: dict[str, Any] | None,
    publish_tf: bool,
    qos: QosBundle,
) -> Any | None:
    if params is None:
        return None
    odom = config.odom_publisher
    return create_wheel_odometry_publisher(
        node=node,
        topic=_ns_topic(config.namespace, config.topics.odom),
        left_indices=params["left_indices"],
        right_indices=params["right_indices"],
        wheel_radius=float(params["wheel_radius"]),
        track_width=float(params["track_width"]),
        slip_left=float(params.get("slip_left", 0.0)),
        slip_right=float(params.get("slip_right", 0.0)),
        sigma_omega=float(params.get("sigma_omega", 0.0)),
        seed=int(params["seed"]) if params.get("seed") is not None else None,
        queue_size=odom.queue_size,
        odom_qos=qos.odom,
        tf_qos=qos.tf,
        frame_id=odom.frame_id,
        child_frame_id=odom.child_frame_id,
        publish_tf=publish_tf,
        pose_diag=params.get("pose_diag"),
        twist_diag=params.get("twist_diag"),
    )


def create_noisy_imu_setup(
    node: Any,
    config: Ros2BridgeConfig,
    params: dict[str, Any] | None,
    qos: QosBundle,
) -> Any | None:
    if params is None:
        return None
    sigma_lin_acc = float(params.get("sigma_lin_acc", 0.0))
    sigma_ang_vel = float(params.get("sigma_ang_vel", 0.0))
    if sigma_lin_acc <= 0.0 and sigma_ang_vel <= 0.0:
        return None
    return create_imu_noise_publisher(
        node=node,
        topic=_ns_topic(config.namespace, config.topics.imu_noisy),
        imu_prim_path=str(params["imu_prim_path"]),
        sigma_lin_acc=sigma_lin_acc,
        sigma_ang_vel=sigma_ang_vel,
        seed=params.get("seed"),
        queue_size=10,
        sensor_qos=qos.sensor,
    )


__all__ = [
    "QosBundle",
    "create_cmd_vel_setup",
    "create_ground_truth_setup",
    "create_noisy_imu_setup",
    "create_rclpy_node",
    "create_robot_description_setup",
    "create_static_tf_setup",
    "create_wheel_odometry_setup",
    "resolve_qos_bundle",
]
