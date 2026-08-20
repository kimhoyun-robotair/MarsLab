"""Define validated ROS topics, rates, QoS, and frame settings.
Validators keep ground-truth and operational odometry distinct.
The schema stays independent of rclpy imports."""

from typing import Literal

from pydantic import Field, model_validator

from marslab.config.schema.common import (
    NonEmptyString,
    PositiveFloat,
    PositiveInt,
    StrictConfigModel,
)


class RosTopicsConfig(StrictConfigModel):
    cmd_vel: NonEmptyString
    robot_description: NonEmptyString
    imu: NonEmptyString
    imu_noisy: NonEmptyString
    odom: NonEmptyString
    gt_trajectory: NonEmptyString
    rgb: NonEmptyString
    depth: NonEmptyString
    points: NonEmptyString
    camera_info: NonEmptyString
    lidar: NonEmptyString
    joint_states: NonEmptyString


class RosRatesConfig(StrictConfigModel):
    imu: PositiveFloat
    odom: PositiveFloat
    rgb: PositiveFloat
    depth: PositiveFloat
    points: PositiveFloat
    camera_info: PositiveFloat
    lidar: PositiveFloat
    joint_states: PositiveFloat


class OdomPublisherConfig(StrictConfigModel):
    frame_id: NonEmptyString
    child_frame_id: NonEmptyString
    queue_size: PositiveInt = Field(le=1000)
    gt_frame_id: NonEmptyString = "map"
    gt_child_frame_id: NonEmptyString = "base_link_gt"


class QoSProfileConfig(StrictConfigModel):
    reliability: Literal["reliable", "best_effort"]
    durability: Literal["volatile", "transient_local"]
    history: Literal["keep_last", "keep_all"] = "keep_last"
    depth: PositiveInt = Field(le=1000)


class Ros2BridgeConfig(StrictConfigModel):
    namespace: NonEmptyString
    topics: RosTopicsConfig
    rates: RosRatesConfig
    odom_publisher: OdomPublisherConfig
    sensor_parent_frame_id: NonEmptyString
    graph_path: NonEmptyString = "/World/Stage3ROS2Graph"
    cmd_vel_queue_size: PositiveInt = Field(default=10, le=1000)
    publish_pointcloud2: bool = True
    publish_camera_info: bool = True
    publish_robot_description: bool = True
    cmd_vel_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="reliable", durability="volatile", depth=10
    )
    odom_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="reliable", durability="volatile", depth=10
    )
    sensor_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="best_effort", durability="volatile", depth=5
    )
    tf_qos: QoSProfileConfig = QoSProfileConfig(
        reliability="reliable", durability="transient_local", depth=100
    )

    @model_validator(mode="after")
    def check_distinct_odom_topics(self) -> "Ros2BridgeConfig":
        namespace = self.namespace.strip("/")
        resolved_topics = tuple(
            "/".join(part for part in (namespace, topic.strip("/")) if part)
            for topic in (self.topics.odom, self.topics.gt_trajectory)
        )
        if resolved_topics[0] == resolved_topics[1]:
            raise ValueError("resolved odom and gt_trajectory topics must be distinct")
        return self


__all__ = ["OdomPublisherConfig", "QoSProfileConfig", "Ros2BridgeConfig"]
