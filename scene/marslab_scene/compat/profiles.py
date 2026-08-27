"""Immutable numerical compatibility policies."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from types import MappingProxyType
from typing import Final, Literal, TypeAlias

from marslab_scene.errors import UnknownCompatibilityProfileError

CompatibilityProfileName: TypeAlias = Literal["canonical", "marslab_utils_6f30d67"]


@unique
class RockElevationMode(StrEnum):
    CANONICAL = "canonical"
    LEGACY_OFFSET_BEFORE_SCALE = "legacy_offset_before_scale"


@unique
class HabitatElevationMode(StrEnum):
    CANONICAL = "canonical"
    LEGACY_REFERENCE_ONLY = "legacy_reference_only"


@dataclass(frozen=True, slots=True)
class CompatibilityPolicy:
    name: CompatibilityProfileName
    rock_elevation: RockElevationMode
    habitat_elevation: HabitatElevationMode
    flatness_uses_raster_resolution: bool
    clamp_single_anchor_to_edge: bool
    legacy_centroid_transform: bool


_PROFILES: Final = MappingProxyType(
    {
        "canonical": CompatibilityPolicy(
            name="canonical",
            rock_elevation=RockElevationMode.CANONICAL,
            habitat_elevation=HabitatElevationMode.CANONICAL,
            flatness_uses_raster_resolution=True,
            clamp_single_anchor_to_edge=False,
            legacy_centroid_transform=False,
        ),
        "marslab_utils_6f30d67": CompatibilityPolicy(
            name="marslab_utils_6f30d67",
            rock_elevation=RockElevationMode.LEGACY_OFFSET_BEFORE_SCALE,
            habitat_elevation=HabitatElevationMode.LEGACY_REFERENCE_ONLY,
            flatness_uses_raster_resolution=False,
            clamp_single_anchor_to_edge=True,
            legacy_centroid_transform=True,
        ),
    }
)


def resolve_compatibility_policy(name: str) -> CompatibilityPolicy:
    """Resolve a required schema-v1 profile name."""
    try:
        return _PROFILES[name]
    except KeyError:
        raise UnknownCompatibilityProfileError(name=name) from None
