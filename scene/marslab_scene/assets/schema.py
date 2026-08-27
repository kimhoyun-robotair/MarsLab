"""Shared strict asset-manifest fields."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from marslab_scene.config.paths import relative_posix_path
from marslab_scene.errors import ContractValueError

_SHA256_HEX_LENGTH = 64


class AssetManifestModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True, strict=True)


class AssetConventions(AssetManifestModel):
    up_axis: Literal["Z"]
    meters_per_unit: Annotated[float, Field(ge=1.0, le=1.0)]


class AssetProvenance(AssetManifestModel):
    producer: str = Field(min_length=1)
    marslab_revision: str | None
    marslab_utils_revision: str | None
    source_files: tuple[Path, ...]

    @field_validator("source_files", mode="before")
    @classmethod
    def validate_source_files(
        cls,
        value: list[Path | str] | tuple[Path | str, ...],
    ) -> tuple[Path, ...]:
        return tuple(relative_posix_path(item) for item in value)


class AssetLicense(AssetManifestModel):
    spdx_id: str = Field(min_length=1)
    attribution: str = Field(min_length=1)
    redistribution_allowed: Literal[True]


def validated_digests(value: dict[str, str]) -> dict[str, str]:
    """Validate root-relative digest keys and lowercase SHA-256 values."""
    validated: dict[str, str] = {}
    for path, digest in value.items():
        relative = relative_posix_path(path).as_posix()
        if len(digest) != _SHA256_HEX_LENGTH or digest.lower() != digest:
            raise ContractValueError("digest must be a lowercase SHA-256 hex value")
        try:
            _ = bytes.fromhex(digest)
        except ValueError as error:
            raise ContractValueError("digest must be a lowercase SHA-256 hex value") from error
        validated[relative] = digest
    return validated
