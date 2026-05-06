"""Aggregated pydantic schema for MarsLab configuration.

The schema is split into seven domain modules plus a root aggregator
to keep each module under ~300 LOC and surfaced area focused. Public
imports remain unchanged:

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
    ChassisConfig,
    DepthSensorConfig,
    IMUConfig,
    Lidar2DConfig,
    Lidar3DConfig,
    OdometryCovarianceConfig,
    OdomPublisherConfig,
    RobotConfig,
    SensorsConfig,
    SkidSteerDriveConfig,
    SuspensionConfig,
    WheelsConfig,
)
from marslab.config.schema.root import MarsLabConfig
from marslab.config.schema.ros2_bridge import QoSProfileConfig, Ros2BridgeConfig
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

__all__ = [
    "CameraConfig",
    "CaveConfig",
    "CaveGeometryConfig",
    "ChassisConfig",
    "DemCropConfig",
    "DepthSensorConfig",
    "DynamicAtmosphereConfig",
    "FogConfig",
    "IMUConfig",
    "Lidar2DConfig",
    "Lidar3DConfig",
    "MarsEnvConfig",
    "MarsLabConfig",
    "OdomPublisherConfig",
    "OdometryCovarianceConfig",
    "PathTracingConfig",
    "ProceduralCanyonConfig",
    "QoSProfileConfig",
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
    "SuspensionConfig",
    "TauConstantConfig",
    "TauRampConfig",
    "TauSineConfig",
    "TerrainConfig",
    "WheelsConfig",
]
