"""Root aggregator schema: MarsLabConfig composes all domain blocks.

Split from marslab.config.schema (R2, 2026-04-22). Imports every
domain module so the top-level ``MarsLabConfig`` has all field types
resolved without forward references.
"""

from pydantic import BaseModel, Field

from marslab.config.schema.benchmark import BenchmarkConfig
from marslab.config.schema.mars_env import MarsEnvConfig
from marslab.config.schema.rendering import RenderingConfig
from marslab.config.schema.robot import RobotConfig
from marslab.config.schema.sensors import SensorsConfig
from marslab.config.schema.telemetry import TelemetryConfig
from marslab.config.schema.terrain import TerrainConfig

__all__ = ["MarsLabConfig"]


class MarsLabConfig(BaseModel):
    """Top-level MarsLab configuration aggregating all sub-configs."""

    mars_env: MarsEnvConfig = Field(default_factory=MarsEnvConfig)
    terrain: TerrainConfig = Field(default_factory=TerrainConfig)
    robots: list[RobotConfig] = Field(default_factory=list)
    rendering: RenderingConfig = Field(default_factory=RenderingConfig)
    sensors: SensorsConfig = Field(
        default_factory=SensorsConfig,
        description=(
            "Sensor-subsystem config container. Currently holds the Wk1 "
            "IMU live-gravity probe block under 'sensors.imu'."
        ),
    )
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    benchmark: BenchmarkConfig | None = Field(default=None)
