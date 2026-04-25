"""Aggregated pydantic schema for MarsLab configuration.

R2 (2026-04-22) split the original 670-LOC schema.py into seven domain
modules plus a root aggregator. Public imports remain unchanged:

    from marslab.config.schema import MarsLabConfig, MarsEnvConfig, ...
"""

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
    CameraConfig,
    IMUConfig,
    Lidar2DConfig,
    Lidar3DConfig,
    OdometryCovarianceConfig,
    RobotConfig,
    SensorsConfig,
    SkidSteerDriveConfig,
)
from marslab.config.schema.root import MarsLabConfig
from marslab.config.schema.ros2_bridge import Ros2BridgeConfig
from marslab.config.schema.scene import (
    SceneConfig,
    StructureAssetConfig,
    StructureConfigSchema,
)
from marslab.config.schema.terrain import (
    CaveConfig,
    CaveGeometryConfig,
    DemCropConfig,
    ProceduralCanyonConfig,
    TerrainConfig,
)

# R2-A1 (2026-04-22) exported FogConfig / RayTracingConfig /
# PathTracingConfig / SkyDomeConfig alongside the pre-existing public
# names.
# R2-A2 (2026-04-22) extended the list with DynamicAtmosphereConfig /
# SunSweepConfig / TauConstantConfig / TauRampConfig / TauSineConfig so
# ``from marslab.config.schema import DynamicAtmosphereConfig`` works
# without reaching into ``marslab.config.schema.mars_env``.
__all__ = [
    "CameraConfig",
    "CaveConfig",
    "CaveGeometryConfig",
    "DemCropConfig",
    "DynamicAtmosphereConfig",
    "FogConfig",
    "IMUConfig",
    "Lidar2DConfig",
    "Lidar3DConfig",
    "MarsEnvConfig",
    "MarsLabConfig",
    "OdometryCovarianceConfig",
    "PathTracingConfig",
    "ProceduralCanyonConfig",
    "RayTracingConfig",
    "RenderingConfig",
    "RobotConfig",
    "Ros2BridgeConfig",
    "SceneConfig",
    "SensorsConfig",
    "SkidSteerDriveConfig",
    "SkyDomeConfig",
    "StructureAssetConfig",
    "StructureConfigSchema",
    "SunSweepConfig",
    "TauConstantConfig",
    "TauRampConfig",
    "TauSineConfig",
    "TerrainConfig",
]
