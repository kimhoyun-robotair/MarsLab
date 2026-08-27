"""DEM resampling helpers."""

from __future__ import annotations

import numpy as np


def resample_elevation(array: np.ndarray, target_size: int, method: str) -> np.ndarray:
    """Resample a 2D elevation array to a square target grid."""
    values = np.asarray(array, dtype=np.float64)
    if values.ndim != 2:
        msg = "array must be 2D"
        raise ValueError(msg)
    if target_size < 2:
        msg = "target_size must be >= 2"
        raise ValueError(msg)
    if method == "nearest":
        return _resample_nearest(values, target_size)
    if method == "bilinear":
        return _resample_bilinear(values, target_size)

    msg = f"Unsupported resampling method: {method}"
    raise ValueError(msg)


def _resample_nearest(array: np.ndarray, target_size: int) -> np.ndarray:
    src_height, src_width = array.shape
    row_positions = np.linspace(0, src_height - 1, target_size)
    col_positions = np.linspace(0, src_width - 1, target_size)
    rows = np.clip(np.floor(row_positions + 0.5).astype(int), 0, src_height - 1)
    cols = np.clip(np.floor(col_positions + 0.5).astype(int), 0, src_width - 1)
    return array[np.ix_(rows, cols)]


def _resample_bilinear(array: np.ndarray, target_size: int) -> np.ndarray:
    src_height, src_width = array.shape
    row_positions = np.linspace(0, src_height - 1, target_size)
    col_positions = np.linspace(0, src_width - 1, target_size)

    out = np.empty((target_size, target_size), dtype=np.float64)
    for out_row, row_position in enumerate(row_positions):
        row0 = int(np.floor(row_position))
        row1 = min(row0 + 1, src_height - 1)
        row_t = row_position - row0
        for out_col, col_position in enumerate(col_positions):
            col0 = int(np.floor(col_position))
            col1 = min(col0 + 1, src_width - 1)
            col_t = col_position - col0

            top = (1 - col_t) * array[row0, col0] + col_t * array[row0, col1]
            bottom = (1 - col_t) * array[row1, col0] + col_t * array[row1, col1]
            out[out_row, out_col] = (1 - row_t) * top + row_t * bottom

    return out
