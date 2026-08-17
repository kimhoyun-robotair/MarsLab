from marslab.config.schema.common import StrictConfigModel


class RuntimeConfig(StrictConfigModel):
    headless: bool
    ros2_enabled: bool
    atmosphere_enabled: bool


class WheelOdomConfig(StrictConfigModel):
    publish_tf: bool


__all__ = ["RuntimeConfig", "WheelOdomConfig"]
