"""Aggregated pydantic schema for MarsLab configuration.

R2 (2026-04-22) split the original 670-LOC schema.py into seven domain
modules plus a root aggregator. Public imports remain unchanged:

    from marslab.config.schema import MarsLabConfig, MarsEnvConfig, ...

Domain files: mars_env.py, terrain.py, robot.py, rendering.py,
sensors.py, telemetry.py, benchmark.py, root.py. The original
schema.py is preserved under ``delete_later/schema.py`` for rollback
(see delete_later/README.md).
"""

from marslab.config.schema.benchmark import BenchmarkConfig
from marslab.config.schema.mars_env import (
    DynamicAtmosphereConfig,
    MarsEnvConfig,
    SunSweepConfig,
    TauConstantConfig,
    TauRampConfig,
    TauSineConfig,
)
from marslab.config.schema.rendering import (
    FogConfig,
    PathTracingConfig,
    RayTracingConfig,
    RenderingConfig,
    SkyDomeConfig,
)
from marslab.config.schema.robot import (
    OdometryCovarianceConfig,
    RobotConfig,
    SkidSteerDriveConfig,
)
from marslab.config.schema.root import MarsLabConfig
from marslab.config.schema.sensors import SensorImuConfig, SensorsConfig
from marslab.config.schema.telemetry import TelemetryConfig
from marslab.config.schema.terrain import CaveConfig, DemCropConfig, TerrainConfig

# R2-A1 (2026-04-22) exported FogConfig / RayTracingConfig /
# PathTracingConfig / SkyDomeConfig alongside the pre-existing public
# names.
# R2-A2 (2026-04-22) extended the list with DynamicAtmosphereConfig /
# SunSweepConfig / TauConstantConfig / TauRampConfig / TauSineConfig so
# ``from marslab.config.schema import DynamicAtmosphereConfig`` works
# without reaching into ``marslab.config.schema.mars_env``.
__all__ = [
    "BenchmarkConfig",
    "CaveConfig",
    "DemCropConfig",
    "DynamicAtmosphereConfig",
    "FogConfig",
    "MarsEnvConfig",
    "MarsLabConfig",
    "OdometryCovarianceConfig",
    "PathTracingConfig",
    "RayTracingConfig",
    "RenderingConfig",
    "RobotConfig",
    "SensorImuConfig",
    "SensorsConfig",
    "SkidSteerDriveConfig",
    "SkyDomeConfig",
    "SunSweepConfig",
    "TauConstantConfig",
    "TauRampConfig",
    "TauSineConfig",
    "TelemetryConfig",
    "TerrainConfig",
]
