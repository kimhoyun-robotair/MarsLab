"""Computed rock and habitat layer contracts."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from marslab_scene.errors import ContractValueError


@dataclass(frozen=True, slots=True)
class TerrainAnchor:
    projected_xy_m: tuple[float, float]
    local_xyz_m: tuple[float, float, float]
    dem_row_column: tuple[int, int]
    mode: Literal["crop_center", "absolute", "flattest"]


@dataclass(frozen=True, slots=True)
class FlatnessReport:
    elevation_range_m: float
    valid_sample_count: int


@dataclass(frozen=True, slots=True)
class RockPlacementStats:
    csv_count: int
    placed_count: int
    skipped_out_of_bounds: int
    skipped_nodata: int
    clamped_count: int


@dataclass(frozen=True, slots=True)
class RockLayer:
    asset_manifest: Path
    positions_local_m: NDArray[np.float64]
    prototype_indices: NDArray[np.int32]
    scales: NDArray[np.float64]
    orientations_wxyz: NDArray[np.float64]
    placement_source: Path | None
    seed: int | None
    stats: RockPlacementStats

    def __post_init__(self) -> None:
        count = len(self.positions_local_m)
        if self.positions_local_m.shape != (count, 3):
            raise ContractValueError("positions_local_m must have shape (N, 3)")
        if self.prototype_indices.shape != (count,):
            raise ContractValueError("prototype_indices must have shape (N,)")
        if self.scales.shape != (count,):
            raise ContractValueError("scales must have shape (N,)")
        if self.orientations_wxyz.shape != (count, 4):
            raise ContractValueError("orientations_wxyz must have shape (N, 4)")
        if self.positions_local_m.dtype != np.float64 or self.scales.dtype != np.float64:
            raise ContractValueError("positions and scales must use float64")
        if self.orientations_wxyz.dtype != np.float64:
            raise ContractValueError("orientations_wxyz must use float64")
        if self.prototype_indices.dtype != np.int32:
            raise ContractValueError("prototype_indices must use int32")
        if not all(
            np.isfinite(array).all()
            for array in (self.positions_local_m, self.scales, self.orientations_wxyz)
        ):
            raise ContractValueError("rock layer arrays must be finite")


@dataclass(frozen=True, slots=True)
class HabitatLayer:
    asset_manifest: Path
    translation_local_m: tuple[float, float, float]
    rotation_wxyz: tuple[float, float, float, float]
    anchor: TerrainAnchor
    flatness: FlatnessReport

    def __post_init__(self) -> None:
        values = (*self.translation_local_m, *self.rotation_wxyz)
        if not all(math.isfinite(value) for value in values):
            raise ContractValueError("habitat transform must be finite")
