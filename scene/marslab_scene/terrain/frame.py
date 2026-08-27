"""Terrain projected-to-local coordinate frame."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TypedDict, assert_never

import numpy as np

from marslab_scene.compat.profiles import (
    CompatibilityProfileName,
    HabitatElevationMode,
    RockElevationMode,
    resolve_compatibility_policy,
)
from marslab_scene.errors import ContractValueError


class Rep103GridError(ValueError):
    """Raised when a local terrain grid violates REP-103 orientation."""


class FrameMetadata(TypedDict):
    standard: str
    frame_id: str
    type: str
    x_axis: str
    y_axis: str
    z_axis: str
    meters_per_unit: float
    yaw_zero: str
    yaw_positive: str


def build_local_xy_grid(
    width: int,
    height: int,
    size_x_m: float,
    size_y_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Build the legacy crop-centered REP-103 local XY grid."""
    if width < 2 or height < 2:
        raise ContractValueError("width and height must be at least two")
    if size_x_m <= 0.0 or size_y_m <= 0.0:
        raise ContractValueError("terrain grid dimensions must be positive")
    columns = np.arange(width, dtype=np.float64)
    rows = np.arange(height, dtype=np.float64)
    x_row = (columns - (width - 1) / 2) * (size_x_m / (width - 1))
    y_column = ((height - 1) / 2 - rows) * (size_y_m / (height - 1))
    return (
        np.broadcast_to(x_row, (height, width)).copy(),
        np.broadcast_to(y_column[:, np.newaxis], (height, width)).copy(),
    )


def validate_rep103_grid(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> None:
    """Reject terrain arrays that do not follow REP-103 grid orientation."""
    x_values = np.asarray(x)
    y_values = np.asarray(y)
    z_values = np.asarray(z)
    if x_values.shape != y_values.shape or x_values.shape != z_values.shape:
        raise Rep103GridError("x, y, and z grids must have matching shapes")
    if x_values.ndim != 2:
        raise Rep103GridError("x, y, and z grids must be two-dimensional")
    if not np.isfinite(x_values).all() or not np.isfinite(y_values).all():
        raise Rep103GridError("x and y grids must contain finite values")
    if not np.isfinite(z_values).all():
        raise Rep103GridError("z grid must contain finite values")
    if not np.all(np.diff(x_values, axis=1) > 0):
        raise Rep103GridError("x grid must increase eastward with column index")
    if not np.all(np.diff(y_values, axis=0) < 0):
        raise Rep103GridError("row zero must remain north of increasing row indices")


def build_frame_metadata(frame_id: str = "map") -> FrameMetadata:
    """Return the retained REP-103 local ENU frame metadata."""
    return {
        "standard": "ROS REP-103",
        "frame_id": frame_id,
        "type": "local_enu",
        "x_axis": "east",
        "y_axis": "north",
        "z_axis": "up",
        "meters_per_unit": 1.0,
        "yaw_zero": "east",
        "yaw_positive": "counter_clockwise",
    }


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
