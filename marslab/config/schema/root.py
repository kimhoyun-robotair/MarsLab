"""Root aggregator schema: MarsLabConfig composes all domain blocks.

Split from marslab.config.schema (R2, 2026-04-22). Imports every
domain module so the top-level ``MarsLabConfig`` has all field types
resolved without forward references.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from marslab.config.schema.mars_env import MarsEnvConfig
from marslab.config.schema.rendering import RenderingConfig
from marslab.config.schema.robot import RobotConfig
from marslab.config.schema.scene import SceneConfig
from marslab.config.schema.terrain import TerrainConfig

__all__ = ["MarsLabConfig"]


# Reviewer 2 #12 (2026-04-24): ``extra="forbid"`` turns on at the root
# too, but MarsLabConfig has to accommodate two pieces of legacy YAML
# surface that were previously silently dropped by pydantic v2's default
# ``extra="ignore"``:
#
# * ``rover:`` — scenario YAMLs declare per-scenario rover tuning under
#   this key.  ``load_and_validate`` merges the scenario with the robot
#   base_config and the result STILL sits under ``rover:``.  The runtime
#   (``marslab.runtime.*``) reads the raw dict alongside ``MarsLabConfig``
#   so keeping ``rover`` strictly-typed in schema would be premature.
#   It is therefore accepted as an opaque dict and preserved verbatim
#   on the model.
# * ``base_config:`` — ``marslab.config.loader.load_and_validate`` pops
#   this before calling the constructor.  A belt-and-suspenders pop here
#   covers direct ``MarsLabConfig(**yaml)`` call sites.
#
# Every other unknown key at the root now fails with ValidationError,
# which is exactly the failure mode Reviewer 2 asked for: typos like
# ``mars_envs:`` or ``rendering:`` misplaced as ``renderring:`` no
# longer disappear.


class MarsLabConfig(BaseModel):
    """Top-level MarsLab configuration aggregating all sub-configs.

    P1-1b (2026-04-23) added the ``scene`` block for the spacecraft /
    Mars base scenarios.  Default is an empty :class:`SceneConfig` so
    every pre-existing scenario YAML (jezero_flat, cerberus_canyon,
    cave_lava_tube, ...) continues to validate without change.
    """

    model_config = ConfigDict(extra="forbid")

    mars_env: MarsEnvConfig = Field(default_factory=MarsEnvConfig)
    terrain: TerrainConfig = Field(default_factory=TerrainConfig)
    robots: list[RobotConfig] = Field(default_factory=list)
    rendering: RenderingConfig = Field(default_factory=RenderingConfig)
    scene: SceneConfig = Field(default_factory=SceneConfig)
    # Reviewer 2 #12 (2026-04-24): ``rover`` is accepted as an opaque
    # dict — strictly typing it would cascade into a deep refactor of
    # the scenario loader / runtime that is out-of-scope for item #12.
    # ``dict`` keeps forbid happy while preserving the block verbatim.
    rover: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Per-scenario rover tuning deep-merged from "
            "``configs/robots/rover_m2020.yaml`` via the scenario loader. "
            "Consumed by the runtime as an untyped dict; promoting this "
            "to a strict schema is tracked separately in Reviewer 2 #17."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _strip_base_config_key(cls, data: Any) -> Any:
        """Drop the top-level ``base_config`` key if it slipped through.

        ``load_and_validate`` already pops ``base_config`` before
        calling this constructor, but direct ``MarsLabConfig(**yaml)``
        call sites (tests, visualizers) do not.  Popping here keeps
        those paths tolerant without weakening ``extra="forbid"`` for
        genuine typos elsewhere at the root.
        """
        if isinstance(data, dict) and "base_config" in data:
            data = dict(data)
            data.pop("base_config", None)
        return data
