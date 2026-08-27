"""Raw DEM sampling shared by placement layers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from numpy.typing import NDArray
from scipy.ndimage import map_coordinates

_XY_DIMENSIONS = 2
_SENTINEL_THRESHOLD = 1.0e30


class DemSamplingError(ValueError):
    """Raised when a DEM cannot satisfy the sampling contract."""


@dataclass(frozen=True, slots=True)
class DemSamples:
    raw_z_m: NDArray[np.float64]
    valid_mask: NDArray[np.bool_]
    out_of_bounds_mask: NDArray[np.bool_]
    nodata_mask: NDArray[np.bool_]


def sample_raw_dem_batch(dem_path: Path, projected_xy_m: np.ndarray) -> DemSamples:
    """Sample raw DEM elevation and explicit validity masks at projected XY."""
    xy = np.asarray(projected_xy_m, dtype=np.float64)
    if xy.ndim != _XY_DIMENSIONS or xy.shape[1] != _XY_DIMENSIONS:
        detail = f"projected_xy_m must have shape (N, 2); got {xy.shape}"
        raise DemSamplingError(detail)
    if not np.isfinite(xy).all():
        raise DemSamplingError("projected_xy_m values must be finite")

    path = Path(dem_path).expanduser().resolve()
    if not path.is_file():
        detail = f"DEM not found: {path}"
        raise DemSamplingError(detail)
    with rasterio.open(path) as dataset:
        transform = dataset.transform
        if transform.b != 0.0 or transform.d != 0.0:
            raise DemSamplingError("rotated or sheared DEM transforms are unsupported")
        elevation = dataset.read(1).astype(np.float64)
        invalid_pixels = ~np.isfinite(elevation)
        if dataset.nodata is not None:
            invalid_pixels |= elevation == dataset.nodata
        invalid_pixels |= np.abs(elevation) > _SENTINEL_THRESHOLD
        elevation[invalid_pixels] = np.nan
        bounds = dataset.bounds
        in_bounds = (
            (xy[:, 0] >= bounds.left)
            & (xy[:, 0] <= bounds.right)
            & (xy[:, 1] >= bounds.bottom)
            & (xy[:, 1] <= bounds.top)
        )
        raw_z = np.full(xy.shape[0], np.nan, dtype=np.float64)
        if in_bounds.any():
            columns, rows = (~transform) * (xy[in_bounds, 0], xy[in_bounds, 1])
            row_indices = np.clip(np.asarray(rows), 0.0, float(dataset.height - 1))
            column_indices = np.clip(np.asarray(columns), 0.0, float(dataset.width - 1))
            raw_z[in_bounds] = map_coordinates(
                elevation,
                np.vstack([row_indices, column_indices]),
                order=1,
                mode="constant",
                cval=np.nan,
            )
    out_of_bounds = ~in_bounds
    nodata = in_bounds & ~np.isfinite(raw_z)
    return DemSamples(
        raw_z_m=raw_z,
        valid_mask=in_bounds & np.isfinite(raw_z),
        out_of_bounds_mask=out_of_bounds,
        nodata_mask=nodata,
    )
