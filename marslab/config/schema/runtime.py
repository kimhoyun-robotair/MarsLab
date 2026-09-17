"""Define process switches and the odometry TF authority flag.
Models are strict and immutable after startup parsing.
No simulator or ROS dependency crosses this boundary."""

from marslab.config.schema.common import StrictConfigModel


class RuntimeConfig(StrictConfigModel):
    headless: bool
    ros2_enabled: bool
    atmosphere_enabled: bool
    enable_motion_bvh: bool = True


class WheelOdomConfig(StrictConfigModel):
    publish_tf: bool


__all__ = ["RuntimeConfig", "WheelOdomConfig"]
