"""Terrain artifact schema and runtime contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, ClassVar, Final, Literal

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    ValidationError,
    field_validator,
)

from marslab_scene.compat.profiles import (
    resolve_compatibility_policy,
)
from marslab_scene.config.paths import relative_posix_path, resolve_manifest_file
from marslab_scene.contracts.files import require_artifact_file
from marslab_scene.contracts.provenance import Provenance
from marslab_scene.errors import (
    ArtifactManifestError,
    CompatibilityProfileMismatch,
    ContractValueError,
    PathContractError,
    SamplingSurfaceUnavailable,
)
from marslab_scene.terrain.frame import TerrainFrame

_JSON_ADAPTER: Final[TypeAdapter[JsonValue]] = TypeAdapter(JsonValue)
_AFFINE_LENGTH: Final = 6
_XY_LENGTH: Final = 2


class _ManifestModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, strict=True)


class TerrainFiles(_ManifestModel):
    stage: Path
    dem: Path | None

    @field_validator("stage", "dem", mode="before")
    @classmethod
    def validate_path(cls, value: Path | str | None) -> Path | None:
        return None if value is None else relative_posix_path(value)


class WorldConventions(_ManifestModel):
    up_axis: Literal["Z"]
    meters_per_unit: Annotated[float, Field(ge=1.0, le=1.0)]


class ManifestProvenance(_ManifestModel):
    producer: str = Field(min_length=1)
    marslab_revision: str | None
    marslab_utils_revision: str | None
    source_files: tuple[Path, ...]

    @field_validator("source_files", mode="before")
    @classmethod
    def validate_source_files(cls, value: tuple[Path | str, ...]) -> tuple[Path, ...]:
        return tuple(relative_posix_path(item) for item in value)


class TerrainFrameManifest(_ManifestModel):
    projected_crs: str = Field(min_length=1)
    raster_affine: tuple[float, float, float, float, float, float]
    origin_projected_m: tuple[float, float]
    z_reference_m: float
    vertical_scale: float = Field(gt=0.0)
    z_offset_m: float

    @field_validator("raster_affine", mode="before")
    @classmethod
    def validate_affine(
        cls,
        value: list[float] | tuple[float, float, float, float, float, float],
    ) -> tuple[float, float, float, float, float, float]:
        if len(value) != _AFFINE_LENGTH:
            raise ContractValueError("raster_affine must contain exactly six values")
        return (value[0], value[1], value[2], value[3], value[4], value[5])

    @field_validator("origin_projected_m", mode="before")
    @classmethod
    def validate_origin(cls, value: list[float] | tuple[float, float]) -> tuple[float, float]:
        if len(value) != _XY_LENGTH:
            raise ContractValueError("origin_projected_m must contain exactly two values")
        return (value[0], value[1])


class TerrainArtifactManifest(_ManifestModel):
    schema_version: Literal[1]
    kind: Literal["terrain_artifact"]
    files: TerrainFiles
    conventions: WorldConventions
    provenance: ManifestProvenance
    digests: dict[str, str]
    compatibility_profile: str = Field(min_length=1)
    coordinate_frame: TerrainFrameManifest | None
    semantic_comparison_report: Path | None = None
    seed: int | None = None

    @field_validator("semantic_comparison_report", mode="before")
    @classmethod
    def validate_semantic_report(cls, value: Path | str | None) -> Path | None:
        return None if value is None else relative_posix_path(value)


@dataclass(frozen=True, slots=True)
class TerrainArtifact:
    root_dir: Path
    stage_path: Path
    dem_path: Path | None
    manifest_path: Path
    coordinate_frame: TerrainFrame | None
    provenance: Provenance

    def __post_init__(self) -> None:
        require_artifact_file(self.root_dir, self.stage_path)
        require_artifact_file(self.root_dir, self.manifest_path)
        if self.dem_path is not None:
            require_artifact_file(self.root_dir, self.dem_path)

    def require_sampling_surface(self) -> tuple[Path, TerrainFrame]:
        if self.dem_path is None or self.coordinate_frame is None:
            raise SamplingSurfaceUnavailable(artifact=self.manifest_path)
        return self.dem_path, self.coordinate_frame


def _load_yaml(path: Path) -> JsonValue:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise ArtifactManifestError(path=path, detail=str(error)) from error
    return _JSON_ADAPTER.validate_python(raw)


def load_terrain_artifact(
    path: Path | str,
    *,
    profile: str,
) -> TerrainArtifact:
    """Load a terrain artifact and enforce compatibility identity."""
    manifest_path = Path(path).expanduser().resolve()
    policy = resolve_compatibility_policy(profile)
    try:
        manifest = TerrainArtifactManifest.model_validate(_load_yaml(manifest_path))
        if manifest.compatibility_profile != policy.name:
            raise CompatibilityProfileMismatch(
                expected=policy.name,
                actual=manifest.compatibility_profile,
                artifact=manifest_path,
            )
        root = manifest_path.parent.resolve()
        if manifest.semantic_comparison_report is not None:
            _ = resolve_manifest_file(root, manifest.semantic_comparison_report)
        stage_path = resolve_manifest_file(root, manifest.files.stage)
        dem_path = (
            None if manifest.files.dem is None else resolve_manifest_file(root, manifest.files.dem)
        )
        frame_data = manifest.coordinate_frame
        frame = (
            None
            if frame_data is None
            else TerrainFrame(
                projected_crs=frame_data.projected_crs,
                raster_affine=frame_data.raster_affine,
                origin_projected_m=frame_data.origin_projected_m,
                z_reference_m=frame_data.z_reference_m,
                vertical_scale=frame_data.vertical_scale,
                z_offset_m=frame_data.z_offset_m,
                compatibility_profile=policy.name,
            )
        )
        return TerrainArtifact(
            root_dir=root,
            stage_path=stage_path,
            dem_path=dem_path,
            manifest_path=manifest_path,
            coordinate_frame=frame,
            provenance=Provenance(
                producer=manifest.provenance.producer,
                marslab_revision=manifest.provenance.marslab_revision,
                marslab_utils_revision=manifest.provenance.marslab_utils_revision,
                source_files=tuple(root / item for item in manifest.provenance.source_files),
            ),
        )
    except (ValidationError, PathContractError) as error:
        raise ArtifactManifestError(path=manifest_path, detail=str(error)) from error
