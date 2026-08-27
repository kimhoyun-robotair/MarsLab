"""Rock asset bundle schema and public loader."""

from __future__ import annotations

import math
from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import ConfigDict, Field, ValidationError, field_validator, model_validator

from marslab_scene.assets.io import (
    load_asset_yaml,
    require_digest_coverage,
    validate_bundle_digests,
)
from marslab_scene.assets.schema import (
    AssetConventions,
    AssetLicense,
    AssetManifestModel,
    AssetProvenance,
    validated_digests,
)
from marslab_scene.config.paths import relative_posix_path, resolve_manifest_file
from marslab_scene.contracts.assets import RockAssetDescriptor
from marslab_scene.errors import ArtifactManifestError, ContractValueError, PathContractError
from marslab_scene.usd.validation import (
    AssetPrimContract,
    AssetStageContract,
    geometry_bounds,
    validate_asset_stage,
    validate_mesh_vertex_indices,
    validate_prototype_texture,
)

_STABLE_FACE_SIZE: Final = 3


class RockFiles(AssetManifestModel):
    stage: Path
    prototypes: tuple[Path, ...]
    textures: tuple[Path, ...]
    license: Path

    @field_validator("stage", "license", mode="before")
    @classmethod
    def validate_single_path(cls, value: Path | str) -> Path:
        return relative_posix_path(value)

    @field_validator("prototypes", "textures", mode="before")
    @classmethod
    def validate_paths(cls, value: list[Path | str] | tuple[Path | str, ...]) -> tuple[Path, ...]:
        return tuple(relative_posix_path(item) for item in value)


class RockPrototype(AssetManifestModel):
    id: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    stage: Path
    prim_path: str = Field(pattern=r"^/[A-Za-z0-9_/]+$")
    geometry_prim: str = Field(pattern=r"^/[A-Za-z0-9_/]+$")
    material_prim: str = Field(pattern=r"^/[A-Za-z0-9_/]+$")
    texture: Path
    collision_prim: str = Field(pattern=r"^/[A-Za-z0-9_/]+$")
    native_diameter_m: float = Field(gt=0.0)
    stable_poses_wxyz: tuple[tuple[float, float, float, float], ...]
    stable_faces_vertex_indices: tuple[tuple[int, int, int], ...]

    @field_validator("stage", "texture", mode="before")
    @classmethod
    def validate_file_path(cls, value: Path | str) -> Path:
        return relative_posix_path(value)

    @field_validator("stable_poses_wxyz", "stable_faces_vertex_indices", mode="before")
    @classmethod
    def validate_nested_tuple(
        cls,
        value: list[list[float] | list[int]] | tuple[tuple[float, ...] | tuple[int, ...], ...],
    ) -> tuple[tuple[float | int, ...], ...]:
        return tuple(tuple(item) for item in value)

    @model_validator(mode="after")
    def validate_stable_metadata(self) -> RockPrototype:
        if not self.stable_poses_wxyz or len(self.stable_poses_wxyz) != len(
            self.stable_faces_vertex_indices
        ):
            raise ContractValueError("stable pose and face candidate counts must match")
        for pose in self.stable_poses_wxyz:
            squared_norm = sum(value * value for value in pose)
            if not math.isclose(squared_norm, 1.0, abs_tol=1e-6):
                raise ContractValueError("stable_poses_wxyz must contain unit quaternions")
        for face in self.stable_faces_vertex_indices:
            if len(set(face)) != _STABLE_FACE_SIZE or min(face) < 0:
                detail = "stable_faces_vertex_indices must contain unique triangle indices"
                raise ContractValueError(detail)
        return self


class RockAssetManifest(AssetManifestModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal[1]
    kind: Literal["rock_asset_bundle"]
    files: RockFiles
    conventions: AssetConventions
    provenance: AssetProvenance
    license: AssetLicense
    digests: dict[str, str]
    default_prim: Literal["/World"]
    prototype_root: Literal["/World/RockPrototypes"]
    relocatable: Literal[True]
    prototypes: tuple[RockPrototype, ...]

    @field_validator("digests", mode="before")
    @classmethod
    def validate_digests(cls, value: dict[str, str]) -> dict[str, str]:
        return validated_digests(value)

    @field_validator("prototypes", mode="before")
    @classmethod
    def validate_prototypes(
        cls,
        value: list[RockPrototype] | tuple[RockPrototype, ...],
    ) -> tuple[RockPrototype, ...]:
        return tuple(value)

    @model_validator(mode="after")
    def validate_prototype_inventory(self) -> RockAssetManifest:
        ids = tuple(prototype.id for prototype in self.prototypes)
        if not ids or len(set(ids)) != len(ids):
            raise ContractValueError("prototype IDs must be non-empty and unique")
        if tuple(prototype.stage for prototype in self.prototypes) != self.files.prototypes:
            raise ContractValueError("prototype stage order must match files.prototypes")
        for prototype in self.prototypes:
            expected_path = f"{self.prototype_root}/{prototype.id}"
            if prototype.prim_path != expected_path:
                raise ContractValueError("prim_path must match prototype_root and stable ID")
        return self


def load_rock_asset(path: Path | str) -> RockAssetDescriptor:
    """Load and semantically validate a relocatable rock asset bundle."""
    manifest_path = Path(path).expanduser().resolve()
    try:
        return _load_rock_asset(manifest_path)
    except (ValidationError, PathContractError, ContractValueError) as error:
        raise ArtifactManifestError(path=manifest_path, detail=str(error)) from error


def _load_rock_asset(manifest_path: Path) -> RockAssetDescriptor:
    manifest = RockAssetManifest.model_validate(load_asset_yaml(manifest_path))
    root = manifest_path.parent.resolve()
    files = (
        manifest.files.stage,
        *manifest.files.prototypes,
        *manifest.files.textures,
        manifest.files.license,
    )
    require_digest_coverage(manifest.digests, files)
    bundle_digest = validate_bundle_digests(root, manifest.digests)
    stage_path = resolve_manifest_file(root, manifest.files.stage)
    prototype_layers = tuple(
        resolve_manifest_file(root, item) for item in manifest.files.prototypes
    )
    textures = tuple(resolve_manifest_file(root, item) for item in manifest.files.textures)
    validate_asset_stage(
        stage_path,
        AssetStageContract(
            default_prim=manifest.default_prim,
            prims=tuple(
                AssetPrimContract(
                    geometry_prim=item.geometry_prim,
                    material_prim=item.material_prim,
                    collision_prim=item.collision_prim,
                    label=item.id,
                )
                for item in manifest.prototypes
            ),
            textures=textures,
            layers=(stage_path, *prototype_layers),
        ),
    )
    for prototype in manifest.prototypes:
        validate_prototype_texture(
            stage_path,
            prototype.prim_path,
            resolve_manifest_file(root, prototype.texture),
        )
        for face in prototype.stable_faces_vertex_indices:
            validate_mesh_vertex_indices(stage_path, prototype.geometry_prim, face)
        minimum, maximum = geometry_bounds(stage_path, prototype.geometry_prim)
        diameter = max(maximum[0] - minimum[0], maximum[1] - minimum[1])
        if not math.isclose(diameter, prototype.native_diameter_m, abs_tol=1e-6):
            detail = f"native_diameter_m does not match geometry: {prototype.id}"
            raise ContractValueError(detail)
    license_path = resolve_manifest_file(root, manifest.files.license)
    if not license_path.read_text(encoding="utf-8").strip():
        raise ContractValueError("license file must not be empty")
    return RockAssetDescriptor(
        manifest_path=manifest_path,
        stage_path=stage_path,
        prototype_ids=tuple(item.id for item in manifest.prototypes),
        native_diameters_m=tuple(item.native_diameter_m for item in manifest.prototypes),
        stable_pose_candidates_wxyz=tuple(item.stable_poses_wxyz for item in manifest.prototypes),
        license_path=license_path,
        attribution=manifest.license.attribution,
        bundle_digest=bundle_digest,
    )
