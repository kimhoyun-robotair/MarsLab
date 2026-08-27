"""Deterministic final scene manifest serialization."""

from __future__ import annotations

import hashlib
import json
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

from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.config.paths import relative_posix_path, resolve_manifest_file
from marslab_scene.contracts.layers import HabitatLayer, RockLayer
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.errors import ArtifactManifestError, ContractValueError, PathContractError

_JSON_ADAPTER = TypeAdapter(JsonValue)
_SHA256_LENGTH: Final = 64


class _ManifestModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, strict=True)


class SceneFiles(_ManifestModel):
    stage: Path
    runtime_package: Path
    semantic_comparison_report: Path

    @field_validator("stage", "runtime_package", "semantic_comparison_report", mode="before")
    @classmethod
    def validate_path(cls, value: Path | str) -> Path:
        return relative_posix_path(value)


class SceneConventions(_ManifestModel):
    up_axis: Literal["Z"]
    meters_per_unit: Annotated[float, Field(ge=1.0, le=1.0)]


class SceneProvenance(_ManifestModel):
    producer: Literal["marslab_scene"]
    marslab_revision: str | None
    marslab_utils_revision: str | None
    source_files: tuple[Path, ...]

    @field_validator("source_files", mode="before")
    @classmethod
    def validate_source_files(
        cls, value: list[Path | str] | tuple[Path | str, ...]
    ) -> tuple[Path, ...]:
        return tuple(relative_posix_path(item) for item in value)


class SceneLayerManifest(_ManifestModel):
    kind: Literal["rocks", "habitat"]
    count: int = Field(ge=0)


class SceneArtifactManifest(_ManifestModel):
    schema_version: Literal[1]
    kind: Literal["scene_artifact"]
    files: SceneFiles
    conventions: SceneConventions
    provenance: SceneProvenance
    compatibility_profile: str = Field(min_length=1)
    resolved_config_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    seed: int | None
    layers: tuple[SceneLayerManifest, ...]
    digests: dict[str, str]
    semantic_comparison_report_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("layers", mode="before")
    @classmethod
    def validate_layers(
        cls,
        value: list[SceneLayerManifest] | tuple[SceneLayerManifest, ...],
    ) -> tuple[SceneLayerManifest, ...]:
        return tuple(value)

    @field_validator("digests", mode="before")
    @classmethod
    def validate_digests(cls, value: dict[str, str]) -> dict[str, str]:
        validated: dict[str, str] = {}
        for path, digest in value.items():
            relative = relative_posix_path(path).as_posix()
            if len(digest) != _SHA256_LENGTH or digest.lower() != digest:
                raise ContractValueError("digest must be a lowercase SHA-256 hex value")
            try:
                _ = bytes.fromhex(digest)
            except ValueError as error:
                raise ContractValueError("digest must be a lowercase SHA-256 hex value") from error
            validated[relative] = digest
        return validated


@dataclass(frozen=True, slots=True)
class SceneManifestInputs:
    stage_path: Path
    package_path: Path
    report_path: Path
    terrain: TerrainArtifact
    rocks: RockLayer | None
    habitat: HabitatLayer | None
    policy: CompatibilityPolicy


def write_scene_manifest(manifest_path: Path, inputs: SceneManifestInputs) -> None:
    """Write root-relative provenance, checksums, and semantic report identity."""
    root = manifest_path.parent
    digest_paths = tuple(
        sorted(path for path in root.rglob("*") if path.is_file() and path != manifest_path)
    )
    digests = {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in digest_paths
    }
    config_input = {
        "compatibility_profile": inputs.policy.name,
        "terrain_manifest_sha256": _digest(inputs.terrain.manifest_path),
        "rock_seed": None if inputs.rocks is None else inputs.rocks.seed,
        "rock_asset_manifest_sha256": _optional_digest(
            None if inputs.rocks is None else inputs.rocks.asset_manifest
        ),
        "habitat_asset_manifest_sha256": _optional_digest(
            None if inputs.habitat is None else inputs.habitat.asset_manifest
        ),
    }
    config_digest = hashlib.sha256(
        json.dumps(config_input, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    layers = []
    if inputs.rocks is not None:
        layers.append({"kind": "rocks", "count": len(inputs.rocks.positions_local_m)})
    if inputs.habitat is not None:
        layers.append({"kind": "habitat", "count": 1})
    report_key = inputs.report_path.relative_to(root).as_posix()
    manifest = {
        "schema_version": 1,
        "kind": "scene_artifact",
        "files": {
            "stage": inputs.stage_path.relative_to(root).as_posix(),
            "runtime_package": inputs.package_path.relative_to(root).as_posix(),
            "semantic_comparison_report": report_key,
        },
        "conventions": {"up_axis": "Z", "meters_per_unit": 1.0},
        "provenance": {
            "producer": "marslab_scene",
            "marslab_revision": inputs.terrain.provenance.marslab_revision,
            "marslab_utils_revision": inputs.terrain.provenance.marslab_utils_revision,
            "source_files": [],
        },
        "compatibility_profile": inputs.policy.name,
        "resolved_config_digest": config_digest,
        "seed": None if inputs.rocks is None else inputs.rocks.seed,
        "layers": layers,
        "digests": digests,
        "semantic_comparison_report_digest": digests[report_key],
    }
    _ = manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=True), encoding="utf-8")


def validate_scene_manifest(manifest_path: Path) -> SceneArtifactManifest:
    """Validate final manifest schema, contained paths, and every declared checksum."""
    path = manifest_path.expanduser().resolve()
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        manifest = SceneArtifactManifest.model_validate(_JSON_ADAPTER.validate_python(raw))
    except (
        OSError,
        yaml.YAMLError,
        ValidationError,
        PathContractError,
        ContractValueError,
    ) as error:
        raise ArtifactManifestError(path=path, detail=str(error)) from error
    try:
        _validate_manifest_files(path.parent, manifest)
    except (PathContractError, ContractValueError) as error:
        raise ArtifactManifestError(path=path, detail=str(error)) from error
    return manifest


def _validate_manifest_files(root: Path, manifest: SceneArtifactManifest) -> None:
    required = {
        manifest.files.stage.as_posix(),
        manifest.files.runtime_package.as_posix(),
        manifest.files.semantic_comparison_report.as_posix(),
    }
    if not required.issubset(manifest.digests):
        raise ContractValueError("final manifest digest inventory is incomplete")
    for relative, expected in manifest.digests.items():
        dependency = resolve_manifest_file(root, relative)
        if _digest(dependency) != expected:
            detail = f"checksum mismatch: {relative}"
            raise ContractValueError(detail)
    report_key = manifest.files.semantic_comparison_report.as_posix()
    if manifest.semantic_comparison_report_digest != manifest.digests[report_key]:
        raise ContractValueError("semantic report digest does not match digest inventory")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _optional_digest(path: Path | None) -> str | None:
    return None if path is None else _digest(path)
