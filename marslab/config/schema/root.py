"""Define the integrated scene and runtime configuration root.
Strict immutable models compose the validated YAML tree.
Nested domain schemas supply scene, rover, and scenario fields."""

from pathlib import Path

from marslab.config.schema.common import StrictConfigModel
from marslab.config.schema.rover import RoverConfig
from marslab.config.schema.runtime import RuntimeConfig, WheelOdomConfig
from marslab.config.schema.scenario import MarsEnvConfig, RenderingConfig


class SceneConfig(StrictConfigModel):
    usdz_path: Path


class MarsLabConfig(StrictConfigModel):
    scene: SceneConfig
    runtime: RuntimeConfig
    mars_env: MarsEnvConfig
    rendering: RenderingConfig
    rover: RoverConfig
    wheel_odom: WheelOdomConfig


__all__ = ["MarsLabConfig", "SceneConfig"]
