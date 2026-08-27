"""NoData mask and fill helpers."""

from __future__ import annotations

import numpy as np


class NoDataError(ValueError):
    """Base error for NoData handling."""


class NoValidDataError(NoDataError):
    """Raised when an operation needs at least one valid pixel."""


def build_valid_mask(array: np.ndarray, nodata: float | None) -> np.ndarray:
    """Return a boolean mask where finite, non-NoData pixels are valid."""
    values = np.asarray(array)
    valid = np.isfinite(values)
    if nodata is not None:
        valid &= values != nodata
    return valid


def fill_nodata(array: np.ndarray, valid_mask: np.ndarray, method: str) -> np.ndarray:
    """Fill invalid cells for downstream mesh generation."""
    values = np.asarray(array, dtype=np.float64)
    mask = np.asarray(valid_mask, dtype=bool)
    if values.shape != mask.shape:
        msg = "array and valid_mask must have the same shape"
        raise ValueError(msg)
    if not mask.any():
        msg = "Cannot fill NoData without at least one valid pixel"
        raise NoValidDataError(msg)

    filled = values.copy()
    invalid = ~mask
    if not invalid.any():
        return filled

    if method == "mean":
        filled[invalid] = float(np.mean(values[mask]))
        return filled

    if method == "zero":
        filled[invalid] = 0.0
        return filled

    if method == "nearest":
        return _fill_nearest(filled, mask)

    msg = f"Unsupported NoData fill method: {method}"
    raise ValueError(msg)


def _fill_nearest(array: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    filled = array.copy()
    valid_rows, valid_cols = np.nonzero(valid_mask)
    invalid_rows, invalid_cols = np.nonzero(~valid_mask)

    valid_values = filled[valid_rows, valid_cols]
    for row, col in zip(invalid_rows, invalid_cols, strict=True):
        distances = (valid_rows - row) ** 2 + (valid_cols - col) ** 2
        nearest_index = int(np.argmin(distances))
        filled[row, col] = valid_values[nearest_index]

    return filled
