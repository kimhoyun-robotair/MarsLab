"""Scene composition schema: static structures declared per-scenario.

Pydantic mirror of :class:`marslab.scene.structure_loader.StructureConfig`
(dataclass).  Kept as a separate model so YAML validation happens
without importing the Isaac-Sim-bound loader module.

The pydantic model's field set is deliberately a **superset** of the
dataclass fields it mirrors -- YAML keys are validated here first, then
a caller converts each entry into a :class:`StructureConfig` dataclass
via :meth:`StructureConfigSchema.to_dataclass` before invoking
:func:`marslab.scene.structure_loader.load_structures`.

P1-1b (2026-04-23) introduced this module for the spacecraft landing
and Mars base scenarios.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, model_validator

if TYPE_CHECKING:  # pragma: no cover - type-checker only
    from marslab.scene.structure_loader import StructureConfig

__all__ = [
    "SceneConfig",
    "StructureConfigSchema",
]


class StructureConfigSchema(BaseModel):
    """Pydantic mirror of
    :class:`marslab.scene.structure_loader.StructureConfig`.

    Field parity notes:

    * ``spawn_xyz`` and ``spawn_rpy_deg`` are 3-element float lists in
      YAML (pydantic) and 3-tuples in the dataclass.  The conversion
      happens in :meth:`to_dataclass`.
    * ``prim_path`` defaults to empty string -- the loader substitutes
      ``/World/Structures/{name}`` when empty.  Kept as ``str`` rather
      than ``str | None`` so the dataclass default matches the pydantic
      default byte-for-byte.
    """

    name: str = Field(
        ...,
        min_length=1,
        description=(
            "Short identifier used as the USD child prim name. "
            "Must be alphanumeric / underscore; no leading digit."
        ),
    )
    asset_path: str = Field(
        ...,
        min_length=1,
        description=(
            "Path to the .usd / .usda / .usdc asset.  Absolute or "
            "relative to the project root -- the loader resolves before "
            "the existence check."
        ),
    )
    spawn_xyz: list[float] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="World-frame translation [x, y, z] in metres.",
    )
    spawn_rpy_deg: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description=(
            "ZYX intrinsic [roll, pitch, yaw] in degrees. Degrees "
            "(not radians) chosen so YAML values stay readable."
        ),
    )
    scale: list[float] = Field(
        default=[1.0, 1.0, 1.0],
        min_length=3,
        max_length=3,
        description="Per-axis scale factor applied after orient.",
    )
    static: bool = Field(
        default=True,
        description=(
            "True = CollisionAPI only (immovable).  False = additionally "
            "apply RigidBodyAPI so the prop can be pushed by dynamics."
        ),
    )
    collision: bool = Field(
        default=True,
        description=(
            "Gate for CollisionAPI.  False leaves the structure purely "
            "visual (no physics response; rays + sensors still see it)."
        ),
    )
    prim_path: str = Field(
        default="",
        description=(
            "Override destination prim path.  Empty string triggers the "
            "default /World/Structures/{name} layout."
        ),
    )

    @model_validator(mode="after")
    def _validate_name(self) -> "StructureConfigSchema":
        """Reject names that would produce an invalid USD child token.

        USD tokens must match ``[A-Za-z_][A-Za-z0-9_]*``.  We do not
        enforce the full grammar (the stage API will reject otherwise),
        but we catch the common mistakes: whitespace, slashes, leading
        digits.
        """
        if any(c.isspace() for c in self.name):
            raise ValueError(f"structure name must not contain whitespace, got {self.name!r}")
        if "/" in self.name or "\\" in self.name:
            raise ValueError(f"structure name must not contain path separators, got {self.name!r}")
        if self.name[0].isdigit():
            raise ValueError(f"structure name must not start with a digit, got {self.name!r}")
        return self

    def to_dataclass(self) -> "StructureConfig":
        """Convert the pydantic model into the loader dataclass.

        Performs the list → tuple coercion required by the dataclass
        (dataclass fields are typed ``Tuple[float, float, float]``).
        """
        # Import inside the method so the schema module stays free of
        # Isaac-Sim-triggering imports even though the loader module
        # itself is offline-safe -- keeps the dependency graph crisp.
        from marslab.scene.structure_loader import StructureConfig

        return StructureConfig(
            name=self.name,
            asset_path=self.asset_path,
            spawn_xyz=(self.spawn_xyz[0], self.spawn_xyz[1], self.spawn_xyz[2]),
            spawn_rpy_deg=(
                self.spawn_rpy_deg[0],
                self.spawn_rpy_deg[1],
                self.spawn_rpy_deg[2],
            ),
            scale=(self.scale[0], self.scale[1], self.scale[2]),
            static=self.static,
            collision=self.collision,
            prim_path=self.prim_path,
        )


class SceneConfig(BaseModel):
    """Scene-level config: static structures dressed on top of terrain.

    Fields:
        structures: Ordered list of :class:`StructureConfigSchema`
            declarations.  Order is preserved end-to-end so log output
            and prim creation sequence stay stable.
    """

    structures: list[StructureConfigSchema] = Field(
        default_factory=list,
        description=(
            "Static USD structures (lander, backshell, habitat, solar "
            "arrays, ...) to attach after terrain + rover spawn.  Empty "
            "list is the default and adds no structures."
        ),
    )
