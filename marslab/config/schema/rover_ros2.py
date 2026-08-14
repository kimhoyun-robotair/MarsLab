from typing import Literal

from pydantic import Field

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
    scan: NonEmptyString
    joint_states: NonEmptyString


class RosRatesConfig(StrictConfigModel):
    imu: PositiveFloat
    odom: PositiveFloat
    rgb: PositiveFloat
    depth: PositiveFloat
    points: PositiveFloat
    camera_info: PositiveFloat
    lidar: PositiveFloat
    scan: PositiveFloat
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
    publish_odom_tf: bool
    graph_path: NonEmptyString = "/World/Stage3ROS2Graph"
    cmd_vel_queue_size: PositiveInt = Field(default=10, le=1000)
    publish_pointcloud2: bool = True
    publish_camera_info: bool = True
    publish_robot_description: bool = True
    publish_joint_states: bool = True
    enable_isaac_nameoverride: bool = False
    rename_root_to_base_link: bool = False
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


__all__ = ["OdomPublisherConfig", "QoSProfileConfig", "Ros2BridgeConfig"]
