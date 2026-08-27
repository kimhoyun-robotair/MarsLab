"""Strict schema-v1 scene recipe models."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Final, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from marslab_scene.config.paths import relative_local_path, relative_posix_path
from marslab_scene.errors import ContractValueError

_SCALE_CLAMP_LENGTH: Final = 2


class StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, strict=True)


class SceneIdentity(StrictModel):
    id: str = Field(min_length=1)
    compatibility_profile: str = Field(min_length=1)


class HiriseSource(StrictModel):
    type: Literal["hirise"]
    dem: Path

    @field_validator("dem", mode="before")
    @classmethod
    def validate_dem(cls, value: Path | str) -> Path:
        return relative_local_path(value)


class ArtifactSource(StrictModel):
    type: Literal["artifact"]
    manifest: Path

    @field_validator("manifest", mode="before")
    @classmethod
    def validate_manifest(cls, value: Path | str) -> Path:
        return relative_local_path(value)


class LegacyExternalDependency(StrictModel):
    owner_layer: Path
    authored_path_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source: Path
    destination: Path
    sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    redistribution_allowed: Literal[True]

    @field_validator("owner_layer", "destination", mode="before")
    @classmethod
    def validate_artifact_path(cls, value: Path | str) -> Path:
        return relative_posix_path(value)

    @field_validator("source", mode="before")
    @classmethod
    def validate_source_path(cls, value: Path | str) -> Path:
        return relative_local_path(value)


class LegacyArtifactSource(StrictModel):
    type: Literal["legacy_artifact"]
    root: Path
    stage: Path
    dem: Path
    metadata: Path
    external_dependencies: tuple[LegacyExternalDependency, ...]

    @field_validator("root", mode="before")
    @classmethod
    def validate_root(cls, value: Path | str) -> Path:
        return relative_local_path(value)

    @field_validator("stage", "dem", "metadata", mode="before")
    @classmethod
    def validate_entrypoint(cls, value: Path | str) -> Path:
        return relative_posix_path(value)

    @field_validator("external_dependencies", mode="before")
    @classmethod
    def validate_dependencies(
        cls,
        value: list[LegacyExternalDependency] | tuple[LegacyExternalDependency, ...],
    ) -> tuple[LegacyExternalDependency, ...]:
        return tuple(value)


TerrainSource: TypeAlias = Annotated[
    HiriseSource | ArtifactSource | LegacyArtifactSource,
    Field(discriminator="type"),
]


class EmptySettings(StrictModel):
    pass


class TerrainSettings(StrictModel):
    source: TerrainSource
    crop: EmptySettings = Field(default_factory=EmptySettings)
    mesh: EmptySettings = Field(default_factory=EmptySettings)
    texture: EmptySettings = Field(default_factory=EmptySettings)
    appearance: EmptySettings = Field(default_factory=EmptySettings)
    modifiers: tuple[()] = ()

    @field_validator("modifiers", mode="before")
    @classmethod
    def validate_modifiers(cls, value: list[None] | tuple[()]) -> tuple[()]:
        if value:
            raise ContractValueError("terrain modifiers are unavailable in schema v1")
        return ()


class RocksDisabled(StrictModel):
    enabled: Literal[False]


class RocksEnabled(StrictModel):
    enabled: Literal[True]
    asset: Path
    placements: Path
    seed: int
    top_k: int = Field(ge=1)
    scale_clamp: tuple[float, float]

    @field_validator("asset", "placements", mode="before")
    @classmethod
    def validate_input_path(cls, value: Path | str) -> Path:
        return relative_local_path(value)

    @field_validator("scale_clamp", mode="before")
    @classmethod
    def validate_scale_values(cls, value: list[float] | tuple[float, float]) -> tuple[float, float]:
        if len(value) != _SCALE_CLAMP_LENGTH:
            raise ContractValueError("scale_clamp must contain exactly two values")
        return (value[0], value[1])

    @model_validator(mode="after")
    def validate_scale_clamp(self) -> RocksEnabled:
        if self.scale_clamp[0] >= self.scale_clamp[1]:
            raise ContractValueError("scale_clamp lower bound must be less than upper bound")
        return self


RocksSettings: TypeAlias = Annotated[
    RocksDisabled | RocksEnabled,
    Field(discriminator="enabled"),
]


class HabitatPlacement(StrictModel):
    mode: Literal["crop_center", "absolute", "flattest"]
    x: float | None = None
    y: float | None = None
    z_align: Literal["body_floor_to_surface", "aabb_min_to_surface", "center", "none"]
    z_offset_m: float = 0.0


class HabitatDisabled(StrictModel):
    enabled: Literal[False]


class HabitatEnabled(StrictModel):
    enabled: Literal[True]
    asset: Path
    placement: HabitatPlacement

    @field_validator("asset", mode="before")
    @classmethod
    def validate_asset_path(cls, value: Path | str) -> Path:
        return relative_local_path(value)


HabitatSettings: TypeAlias = Annotated[
    HabitatDisabled | HabitatEnabled,
    Field(discriminator="enabled"),
]


class LayerSettings(StrictModel):
    rocks: RocksSettings
    habitat: HabitatSettings


class OutputSettings(StrictModel):
    directory: Path
    stage: Path
    runtime_package: Path
    manifest: Path

    @field_validator("directory", "stage", "runtime_package", "manifest", mode="before")
    @classmethod
    def validate_output_path(cls, value: Path | str) -> Path:
        return relative_local_path(value)

    @field_validator("stage", "runtime_package", "manifest")
    @classmethod
    def validate_output_filename(cls, value: Path) -> Path:
        if len(value.parts) != 1:
            raise ContractValueError("output file must be a bare filename")
        return value


class SceneRecipe(StrictModel):
    schema_version: Literal[1]
    scene: SceneIdentity
    terrain: TerrainSettings
    layers: LayerSettings
    output: OutputSettings
