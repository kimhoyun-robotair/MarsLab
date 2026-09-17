"""Define validated ROS topics, QoS, and frame settings.
Validators keep ground-truth and operational odometry distinct.
The schema stays independent of rclpy imports."""

import re
from typing import Literal

from pydantic import Field, field_validator, model_validator

from marslab.config.schema.common import (
    NonEmptyString,
    PositiveInt,
    StrictConfigModel,
)


def _normalize_ros_segments(value: str, *, allow_outer_slashes: bool) -> str:
    if not allow_outer_slashes and (value.startswith("/") or value.endswith("/")):
        raise ValueError("ROS topic names must be relative and must not start or end with '/'")
    normalized = value.strip("/") if allow_outer_slashes else value
    segments = normalized.split("/")
    if not normalized or "//" in value or any(
        re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", segment) is None or "__" in segment
        for segment in segments
    ):
        raise ValueError(f"invalid ROS name: {value!r}")
    return "/".join(segments)


def normalize_ros_namespace(value: str) -> str:
    return _normalize_ros_segments(value, allow_outer_slashes=True)


def normalize_relative_ros_topic(value: str) -> str:
    return _normalize_ros_segments(value, allow_outer_slashes=False)


def resolve_ros_topic(namespace: str, topic: str) -> str:
    return f"/{normalize_ros_namespace(namespace)}/{normalize_relative_ros_topic(topic)}"


class RosTopicsConfig(StrictConfigModel):
    cmd_vel: NonEmptyString
    imu: NonEmptyString
    imu_noisy: NonEmptyString
    odom: NonEmptyString
    gt_trajectory: NonEmptyString
    rgb: NonEmptyString
    depth: NonEmptyString
    points: NonEmptyString
    camera_info: NonEmptyString
    lidar: NonEmptyString
    scan: NonEmptyString = "scan"
    joint_states: NonEmptyString

    @field_validator("*", mode="after")
    @classmethod
    def normalize_topic(cls, value: str) -> str:
        return normalize_relative_ros_topic(value)


class OdomPublisherConfig(StrictConfigModel):
    frame_id: Literal["odom"]
    child_frame_id: Literal["base_link"]
    queue_size: PositiveInt = Field(le=1000)
    gt_frame_id: Literal["map"] = "map"
    gt_child_frame_id: Literal["base_link_gt"] = "base_link_gt"


class QoSProfileConfig(StrictConfigModel):
    reliability: Literal["reliable", "best_effort"]
    durability: Literal["volatile", "transient_local"]
    history: Literal["keep_last", "keep_all"] = "keep_last"
    depth: PositiveInt = Field(le=1000)


class Ros2BridgeConfig(StrictConfigModel):
    namespace: NonEmptyString
    topics: RosTopicsConfig
    odom_publisher: OdomPublisherConfig
    sensor_parent_frame_id: Literal["Body_Chassis"]
    graph_path: NonEmptyString = "/World/Stage3ROS2Graph"
    cmd_vel_queue_size: PositiveInt = Field(default=10, le=1000)
    cmd_vel_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="reliable", durability="volatile", depth=10
    )
    odom_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="reliable", durability="volatile", depth=10
    )
    sensor_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="best_effort", durability="volatile", depth=5
    )
    joint_state_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="reliable", durability="volatile", depth=100
    )
    tf_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="reliable", durability="transient_local", depth=100
    )

    @field_validator("namespace", mode="after")
    @classmethod
    def normalize_namespace(cls, value: str) -> str:
        return normalize_ros_namespace(value)

    @model_validator(mode="after")
    def check_distinct_odom_topics(self) -> "Ros2BridgeConfig":
        resolved_topics = tuple(
            resolve_ros_topic(self.namespace, topic)
            for topic in (self.topics.odom, self.topics.gt_trajectory)
        )
        if resolved_topics[0] == resolved_topics[1]:
            raise ValueError("resolved odom and gt_trajectory topics must be distinct")
        for name in ("sensor_qos", "joint_state_qos"):
            if getattr(self, name).durability != "volatile":
                raise ValueError(f"{name}.durability must be volatile for OmniGraph publishers")
        return self


__all__ = [
    "normalize_relative_ros_topic",
    "normalize_ros_namespace",
    "resolve_ros_topic",
    "OdomPublisherConfig",
    "QoSProfileConfig",
    "Ros2BridgeConfig",
]
