"""Terrain projected-to-local coordinate frame."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import assert_never

from marslab_scene.compat.profiles import (
    CompatibilityProfileName,
    HabitatElevationMode,
    RockElevationMode,
    resolve_compatibility_policy,
)
from marslab_scene.errors import ContractValueError


@dataclass(frozen=True, slots=True)
class TerrainFrame:
    projected_crs: str
    raster_affine: tuple[float, float, float, float, float, float]
    origin_projected_m: tuple[float, float]
    z_reference_m: float
    vertical_scale: float
    z_offset_m: float
    compatibility_profile: CompatibilityProfileName

    def __post_init__(self) -> None:
        values = (*self.raster_affine, *self.origin_projected_m, self.z_reference_m)
        if not self.projected_crs or not all(math.isfinite(value) for value in values):
            raise ContractValueError(
                "terrain frame values must be finite and CRS must be non-empty"
            )
        if not math.isfinite(self.vertical_scale) or self.vertical_scale <= 0.0:
            raise ContractValueError("vertical_scale must be finite and positive")
        if not math.isfinite(self.z_offset_m):
            raise ContractValueError("z_offset_m must be finite")

    def projected_to_local_xy(self, x_projected: float, y_projected: float) -> tuple[float, float]:
        """Convert projected XY meters to local ENU XY meters."""
        return (
            x_projected - self.origin_projected_m[0],
            y_projected - self.origin_projected_m[1],
        )

    def rock_z_local(self, z_raw: float) -> float:
        """Apply the selected rock elevation contract."""
        policy = resolve_compatibility_policy(self.compatibility_profile)
        match policy.rock_elevation:
            case RockElevationMode.CANONICAL:
                return (z_raw - self.z_reference_m) * self.vertical_scale + self.z_offset_m
            case RockElevationMode.LEGACY_OFFSET_BEFORE_SCALE:
                return ((z_raw - self.z_reference_m) + self.z_offset_m) * self.vertical_scale
            case unreachable:
                assert_never(unreachable)

    def habitat_z_local(self, z_raw: float) -> float:
        """Apply the selected habitat elevation contract."""
        policy = resolve_compatibility_policy(self.compatibility_profile)
        match policy.habitat_elevation:
            case HabitatElevationMode.CANONICAL:
                return (z_raw - self.z_reference_m) * self.vertical_scale + self.z_offset_m
            case HabitatElevationMode.LEGACY_REFERENCE_ONLY:
                return z_raw - self.z_reference_m
            case unreachable:
                assert_never(unreachable)
