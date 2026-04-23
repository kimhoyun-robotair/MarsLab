"""Root aggregator schema: MarsLabConfig composes all domain blocks.

Split from marslab.config.schema (R2, 2026-04-22). Imports every
domain module so the top-level ``MarsLabConfig`` has all field types
resolved without forward references.
"""

from pydantic import BaseModel, Field

from marslab.config.schema.mars_env import MarsEnvConfig
from marslab.config.schema.rendering import RenderingConfig
from marslab.config.schema.robot import RobotConfig
from marslab.config.schema.scene import SceneConfig
from marslab.config.schema.terrain import TerrainConfig

__all__ = ["MarsLabConfig"]


class MarsLabConfig(BaseModel):
    """Top-level MarsLab configuration aggregating all sub-configs.

    P1-1b (2026-04-23) added the ``scene`` block for the spacecraft /
    Mars base scenarios.  Default is an empty :class:`SceneConfig` so
    every pre-existing scenario YAML (jezero_flat, cerberus_canyon,
    cave_lava_tube, ...) continues to validate without change.
    """

    mars_env: MarsEnvConfig = Field(default_factory=MarsEnvConfig)
    terrain: TerrainConfig = Field(default_factory=TerrainConfig)
    robots: list[RobotConfig] = Field(default_factory=list)
    rendering: RenderingConfig = Field(default_factory=RenderingConfig)
    scene: SceneConfig = Field(default_factory=SceneConfig)
