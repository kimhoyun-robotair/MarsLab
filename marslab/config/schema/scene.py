"""Scene composition schema: static structures declared per-scenario.

Pydantic mirror of :class:`marslab.scene.structure_loader.StructureConfig`
(dataclass).  Kept as a separate model so YAML validation happens
without importing the Isaac-Sim-bound loader module.

The pydantic model's field set is deliberately a **superset** of the
dataclass fields it mirrors -- YAML keys are validated here first, then
a caller converts each entry into a :class:`StructureConfig` dataclass
via :meth:`StructureConfigSchema.to_dataclass` before invoking
:func:`marslab.scene.structure_loader.load_structures`.

This module supports the spacecraft landing and Mars base scenarios.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field, model_validator

if TYPE_CHECKING:  # pragma: no cover - type-checker only
    from marslab.scene.structure_loader import StructureConfig

__all__ = [
    "SceneConfig",
    "StructureAssetConfig",
    "StructureConfigSchema",
]


# Both models below pin ``extra="forbid"`` so a misspelled structure
# field (``spawn_xyz`` vs ``spawn_position``, ``collisions`` vs
# ``collision``) fails YAML validation instead of being silently
# dropped into a default.


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

    model_config = ConfigDict(extra="forbid")

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


class StructureAssetConfig(BaseModel):
    """User-provided ``.obj`` / ``.stl`` mesh for drop-in scene dressing.

    The ``structure_assets:`` block lets every scenario drop a
    third-party mesh into the world via YAML without going through the
    offline USD conversion that :class:`StructureConfigSchema`
    requires.  The runtime loader reads the mesh with ``trimesh``
    (offline-safe, P3) and converts to USD on the fly via
    ``omni.kit.asset_converter`` -- the canonical Isaac Sim extension
    for OBJ/STL/FBX -> USD conversion (kit-105+, see
    ``docs.omniverse.nvidia.com/extensions/latest/ext_asset-converter.html``).

    Differences vs :class:`StructureConfigSchema`:

    * ``path`` accepts ``.obj`` / ``.stl`` (not USD).  The
      authoritative list of supported extensions lives in
      :data:`marslab.scene.structure_loader.STRUCTURE_ASSET_EXTENSIONS`.
    * ``scale`` is a single float (uniform), not a 3-tuple -- artists
      drop a mesh, position it, scale it; per-axis scale would invite
      the kind of mistakes that break collision normals.
    * No ``static`` / ``collision`` toggles; the scope is "drop in
      geometry", physics tagging stays on the existing USD pipeline.
    * ``name`` is optional; the loader auto-derives a USD-safe name
      from the file stem when absent.

    Attributes:
        path: Path to the source mesh file.  Resolved relative to repo
            root or absolute.
        position: World-frame translation ``[x, y, z]`` in metres.
        rotation_rpy_deg: ZYX intrinsic ``[roll, pitch, yaw]`` in degrees.
            Defaults to identity.
        scale: Uniform scale factor.  Defaults to 1.0.  Negative values
            are allowed but are user-error in 99% of cases.
        name: Optional USD child name.  ``None`` triggers
            ``stem`` of ``path`` with non-USD characters replaced
            (handled by the loader).
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        ...,
        min_length=1,
        description=(
            "Path to the source ``.obj`` or ``.stl`` mesh.  Absolute or "
            "relative to the repo root."
        ),
    )
    position: list[float] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="World-frame translation [x, y, z] in metres.",
    )
    rotation_rpy_deg: list[float] = Field(
        default=[0.0, 0.0, 0.0],
        min_length=3,
        max_length=3,
        description="ZYX intrinsic [roll, pitch, yaw] in degrees.",
    )
    scale: float = Field(
        default=1.0,
        description="Uniform scale factor applied after orient.",
    )
    name: str | None = Field(
        default=None,
        description=(
            "Optional USD child name.  When None the loader derives one "
            "from the file stem (sanitised to [A-Za-z_][A-Za-z0-9_]*)."
        ),
    )

    @model_validator(mode="after")
    def _validate_extension_and_name(self) -> "StructureAssetConfig":
        """Reject unsupported extensions + invalid USD names early.

        Mirrors :class:`StructureConfigSchema`'s name guard so the YAML
        diagnoses the typo at config-load time rather than after Isaac
        Sim spins up.
        """
        lowered = self.path.lower()
        if not (lowered.endswith(".obj") or lowered.endswith(".stl")):
            raise ValueError(f"structure_assets path must end in .obj or .stl, got {self.path!r}")
        if self.name is not None:
            if any(c.isspace() for c in self.name):
                raise ValueError(
                    f"structure_assets name must not contain whitespace, got {self.name!r}"
                )
            if "/" in self.name or "\\" in self.name:
                raise ValueError(
                    f"structure_assets name must not contain path separators, " f"got {self.name!r}"
                )
            if self.name and self.name[0].isdigit():
                raise ValueError(
                    f"structure_assets name must not start with a digit, got {self.name!r}"
                )
        return self


class SceneConfig(BaseModel):
    """Scene-level config: static structures dressed on top of terrain.

    Fields:
        structures: Ordered list of :class:`StructureConfigSchema`
            declarations.  Order is preserved end-to-end so log output
            and prim creation sequence stay stable.
        structure_assets: Ordered list of :class:`StructureAssetConfig`
            drop-in OBJ/STL meshes.  Converts at runtime via
            ``omni.kit.asset_converter``.  Empty list = no drop-ins
            (default for every scenario).
    """

    model_config = ConfigDict(extra="forbid")

    structures: list[StructureConfigSchema] = Field(
        default_factory=list,
        description=(
            "Static USD structures (lander, backshell, habitat, solar "
            "arrays, ...) to attach after terrain + rover spawn.  Empty "
            "list is the default and adds no structures."
        ),
    )
    structure_assets: list[StructureAssetConfig] = Field(
        default_factory=list,
        description=(
            "Drop-in OBJ/STL meshes converted to USD at runtime.  Use "
            "this block for user-provided art (rocks, props, tools) "
            "that has not been pre-baked into a USD asset.  Empty list "
            "= no drop-ins (default)."
        ),
    )
