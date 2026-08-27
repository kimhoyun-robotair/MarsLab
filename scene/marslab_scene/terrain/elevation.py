"""Elevation normalization helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


class _ElevationSettings(Protocol):
    @property
    def normalization(self) -> str: ...

    @property
    def reference_percentile(self) -> float | None: ...

    @property
    def manual_reference_m(self) -> float | None: ...

    @property
    def vertical_scale(self) -> float: ...

    @property
    def z_offset_m(self) -> float: ...


class ElevationError(ValueError):
    """Base error for elevation normalization."""


class NoValidElevationError(ElevationError):
    """Raised when elevation statistics cannot be computed."""


@dataclass(frozen=True, slots=True)
class ElevationResult:
    """Normalized elevation and reference metadata."""

    local_z: np.ndarray
    raw_min_m: float
    raw_max_m: float
    z_reference_mode: str
    z_reference_m: float
    vertical_scale: float
    z_offset_m: float
    local_min_m: float
    local_max_m: float


def compute_z_reference(
    array: np.ndarray,
    valid_mask: np.ndarray,
    config: _ElevationSettings,
) -> float:
    """Compute the raw elevation reference from valid pixels only."""
    valid_values = _valid_values(array, valid_mask)
    mode = config.normalization

    if mode == "absolute":
        return 0.0
    if mode == "min_zero":
        return float(np.min(valid_values))
    if mode == "mean_zero":
        return float(np.mean(valid_values))
    if mode == "median_zero":
        return float(np.median(valid_values))
    if mode == "percentile_zero":
        if config.reference_percentile is None:
            msg = "reference_percentile is required for percentile_zero"
            raise ElevationError(msg)
        return float(np.percentile(valid_values, config.reference_percentile))
    if mode == "manual":
        if config.manual_reference_m is None:
            msg = "manual_reference_m is required for manual normalization"
            raise ElevationError(msg)
        return float(config.manual_reference_m)

    msg = f"Unsupported elevation normalization mode: {mode}"
    raise ElevationError(msg)


def normalize_elevation(
    array: np.ndarray,
    valid_mask: np.ndarray,
    config: _ElevationSettings,
) -> ElevationResult:
    """Normalize raw elevation into local simulation Z."""
    values = np.asarray(array, dtype=np.float64)
    mask = np.asarray(valid_mask, dtype=bool)
    if values.shape != mask.shape:
        msg = "array and valid_mask must have the same shape"
        raise ValueError(msg)
    if config.vertical_scale <= 0:
        msg = "vertical_scale must be > 0"
        raise ElevationError(msg)

    valid_values = _valid_values(values, mask)
    z_reference_m = compute_z_reference(values, mask, config)
    local_z = (values - z_reference_m) * config.vertical_scale + config.z_offset_m
    valid_local = local_z[mask]

    return ElevationResult(
        local_z=local_z,
        raw_min_m=float(np.min(valid_values)),
        raw_max_m=float(np.max(valid_values)),
        z_reference_mode=config.normalization,
        z_reference_m=z_reference_m,
        vertical_scale=float(config.vertical_scale),
        z_offset_m=float(config.z_offset_m),
        local_min_m=float(np.min(valid_local)),
        local_max_m=float(np.max(valid_local)),
    )


def denormalize_elevation(z_local: np.ndarray, result: ElevationResult) -> np.ndarray:
    """Convert local simulation Z values back to raw elevation."""
    return (np.asarray(z_local, dtype=np.float64) - result.z_offset_m) / result.vertical_scale + (
        result.z_reference_m
    )


def _valid_values(array: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    values = np.asarray(array, dtype=np.float64)
    mask = np.asarray(valid_mask, dtype=bool)
    if values.shape != mask.shape:
        msg = "array and valid_mask must have the same shape"
        raise ValueError(msg)

    valid_values = values[mask]
    valid_values = valid_values[np.isfinite(valid_values)]
    if valid_values.size == 0:
        msg = "No valid elevation pixels are available"
        raise NoValidElevationError(msg)
    return valid_values
