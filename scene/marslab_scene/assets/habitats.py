"""Habitat asset bundle schema and public loader."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError, field_validator

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
from marslab_scene.contracts.assets import HabitatAssetDescriptor
from marslab_scene.errors import ArtifactManifestError, ContractValueError, PathContractError
from marslab_scene.usd.validation import (
    AssetPrimContract,
    AssetStageContract,
    geometry_bounds,
    validate_asset_stage,
)


class HabitatFiles(AssetManifestModel):
    stage: Path
    textures: tuple[Path, ...]
    license: Path

    @field_validator("stage", "license", mode="before")
    @classmethod
    def validate_single_path(cls, value: Path | str) -> Path:
        return relative_posix_path(value)

    @field_validator("textures", mode="before")
    @classmethod
    def validate_paths(cls, value: list[Path | str] | tuple[Path | str, ...]) -> tuple[Path, ...]:
        return tuple(relative_posix_path(item) for item in value)


class HabitatAssetManifest(AssetManifestModel):
    schema_version: Literal[1]
    kind: Literal["habitat_asset_bundle"]
    files: HabitatFiles
    conventions: AssetConventions
    provenance: AssetProvenance
    license: AssetLicense
    digests: dict[str, str]
    default_prim: Literal["/Habitat"]
    geometry_prim: str = Field(pattern=r"^/[A-Za-z0-9_/]+$")
    material_prim: str = Field(pattern=r"^/[A-Za-z0-9_/]+$")
    collision_prim: str = Field(pattern=r"^/[A-Za-z0-9_/]+$")
    relocatable: Literal[True]
    centroid_zup_m: tuple[float, float, float]
    aabb_min_zup_m: tuple[float, float, float]
    aabb_max_zup_m: tuple[float, float, float]
    body_floor_z_m: float
    footprint_size_m: tuple[float, float]

    @field_validator("digests", mode="before")
    @classmethod
    def validate_digests(cls, value: dict[str, str]) -> dict[str, str]:
        return validated_digests(value)

    @field_validator(
        "centroid_zup_m",
        "aabb_min_zup_m",
        "aabb_max_zup_m",
        "footprint_size_m",
        mode="before",
    )
    @classmethod
    def validate_vector(
        cls,
        value: list[float] | tuple[float, ...],
    ) -> tuple[float, ...]:
        return tuple(value)


def load_habitat_asset(path: Path | str) -> HabitatAssetDescriptor:
    """Load and semantically validate a relocatable habitat asset bundle."""
    manifest_path = Path(path).expanduser().resolve()
    try:
        return _load_habitat_asset(manifest_path)
    except (ValidationError, PathContractError, ContractValueError) as error:
        raise ArtifactManifestError(path=manifest_path, detail=str(error)) from error


def _load_habitat_asset(manifest_path: Path) -> HabitatAssetDescriptor:
    manifest = HabitatAssetManifest.model_validate(load_asset_yaml(manifest_path))
    root = manifest_path.parent.resolve()
    files = (manifest.files.stage, *manifest.files.textures, manifest.files.license)
    require_digest_coverage(manifest.digests, files)
    bundle_digest = validate_bundle_digests(root, manifest.digests)
    stage_path = resolve_manifest_file(root, manifest.files.stage)
    textures = tuple(resolve_manifest_file(root, item) for item in manifest.files.textures)
    validate_asset_stage(
        stage_path,
        AssetStageContract(
            default_prim=manifest.default_prim,
            prims=(
                AssetPrimContract(
                    geometry_prim=manifest.geometry_prim,
                    material_prim=manifest.material_prim,
                    collision_prim=manifest.collision_prim,
                    label="habitat",
                ),
            ),
            textures=textures,
            layers=(stage_path,),
        ),
    )
    actual_minimum, actual_maximum = geometry_bounds(stage_path, manifest.geometry_prim)
    _require_vector_close("aabb_min_zup_m", actual_minimum, manifest.aabb_min_zup_m)
    _require_vector_close("aabb_max_zup_m", actual_maximum, manifest.aabb_max_zup_m)
    actual_centroid = tuple(
        (low + high) / 2.0 for low, high in zip(actual_minimum, actual_maximum, strict=True)
    )
    _require_vector_close("centroid_zup_m", actual_centroid, manifest.centroid_zup_m)
    if not math.isclose(manifest.body_floor_z_m, actual_minimum[2], abs_tol=1e-6):
        raise ContractValueError("body_floor_z_m does not match geometry")
    actual_footprint = (
        actual_maximum[0] - actual_minimum[0],
        actual_maximum[1] - actual_minimum[1],
    )
    _require_vector_close("footprint_size_m", actual_footprint, manifest.footprint_size_m)
    license_path = resolve_manifest_file(root, manifest.files.license)
    if not license_path.read_text(encoding="utf-8").strip():
        raise ContractValueError("license file must not be empty")
    return HabitatAssetDescriptor(
        manifest_path=manifest_path,
        stage_path=stage_path,
        centroid_zup_m=manifest.centroid_zup_m,
        aabb_min_zup_m=manifest.aabb_min_zup_m,
        aabb_max_zup_m=manifest.aabb_max_zup_m,
        body_floor_z_m=manifest.body_floor_z_m,
        license_path=license_path,
        attribution=manifest.license.attribution,
        bundle_digest=bundle_digest,
    )


def _require_vector_close(
    label: str,
    actual: tuple[float, ...],
    expected: tuple[float, ...],
) -> None:
    if len(actual) != len(expected) or any(
        not math.isclose(left, right, abs_tol=1e-6)
        for left, right in zip(actual, expected, strict=True)
    ):
        detail = f"{label} does not match geometry"
        raise ContractValueError(detail)
