"""Root aggregator schema: MarsLabConfig composes all domain blocks.

Imports every domain module so the top-level ``MarsLabConfig`` has all
field types resolved without forward references.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from marslab.config.schema.mars_env import MarsEnvConfig
from marslab.config.schema.rendering import RenderingConfig
from marslab.config.schema.robot import RobotConfig

__all__ = ["MarsLabConfig"]


# ``extra="forbid"`` is set at the root too, but MarsLabConfig has to
# accommodate two pieces of legacy YAML surface that pydantic v2's
# default ``extra="ignore"`` would otherwise silently drop:
#
# * ``rover:`` -- scenario YAMLs declare per-scenario rover tuning under
#   this key. The runtime (``marslab.runtime.*``) reads the raw dict
#   alongside ``MarsLabConfig`` so keeping ``rover`` strictly-typed in
#   schema would be premature. It is therefore accepted as an opaque
#   dict and preserved verbatim on the model.
# * ``base_config:`` -- legacy YAML include key; popped by
#   ``_strip_base_config_key`` below so direct ``MarsLabConfig(**yaml)``
#   call sites are tolerant.
#
# Every other unknown key at the root now fails with ValidationError,
# so typos like ``mars_envs:`` or ``rendering:`` misspelled as
# ``renderring:`` no longer disappear.


class MarsLabConfig(BaseModel):
    """Top-level MarsLab configuration aggregating runtime sub-configs.

    The passthrough pipeline consumes supplied Scene USDZ packages and does
    not author terrain or scene structures internally, so the
    root model now composes only ``mars_env`` + ``robots``
    + ``rendering`` + an opaque ``rover`` block. Legacy ``terrain`` and
    ``scene`` blocks in scenario YAMLs were retired with the rest of the
    in-repo authoring stack.
    """

    model_config = ConfigDict(extra="forbid")

    mars_env: MarsEnvConfig = Field(default_factory=MarsEnvConfig)
    robots: list[RobotConfig] = Field(default_factory=list)
    rendering: RenderingConfig = Field(default_factory=RenderingConfig)
    # ``rover`` is accepted as an opaque dict because strictly typing it
    # would cascade into a deep refactor of the scenario loader and the
    # runtime.  ``dict`` keeps forbid happy while preserving the block
    # verbatim.
    rover: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Per-scenario rover tuning deep-merged from "
            "``configs/rover_m2020.yaml`` via the scenario loader. "
            "Consumed by the runtime as an untyped dict; promoting this "
            "to a strict schema is a follow-up because the rover subtree "
            "is the most complex YAML block.  Partial schema validation "
            "through ``WheelsConfig`` / ``ChassisConfig`` / etc. is "
            "applied reactively at the runtime layer."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _strip_base_config_key(cls, data: Any) -> Any:
        """Drop the top-level ``base_config`` key if it slipped through.

        Direct ``MarsLabConfig(**yaml)`` call sites (tests, visualizers)
        may carry a stray ``base_config:`` key. Popping here keeps
        those paths tolerant without weakening ``extra="forbid"`` for
        typos elsewhere at the root.
        """
        if isinstance(data, dict) and "base_config" in data:
            data = dict(data)
            data.pop("base_config", None)
        return data
