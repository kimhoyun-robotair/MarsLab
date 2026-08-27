"""Resolution-aware and legacy-compatible terrain flatness search."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.contracts.layers import FlatnessReport, TerrainAnchor
from marslab_scene.terrain.frame import TerrainFrame


class FlatnessSearchError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class FlattestAnchor:
    anchor: TerrainAnchor
    report: FlatnessReport
    raw_z_m: float


def find_flattest_anchor(
    dem_path: Path,
    frame: TerrainFrame,
    *,
    footprint_half_x_m: float,
    footprint_half_y_m: float,
    policy: CompatibilityPolicy,
) -> FlattestAnchor:
    """Return the first row-major minimum-range fully valid footprint."""
    with rasterio.open(dem_path) as dataset:
        transform = dataset.transform
        if transform.b != 0.0 or transform.d != 0.0:
            raise FlatnessSearchError("rotated or sheared DEM transforms are unsupported")
        raw = dataset.read(1).astype(np.float64)
        invalid = ~np.isfinite(raw)
        if dataset.nodata is not None:
            invalid |= raw == dataset.nodata
        raw[invalid] = np.nan

    if policy.flatness_uses_raster_resolution:
        radius_x = math.ceil(abs(footprint_half_x_m) / abs(transform.a))
        radius_y = math.ceil(abs(footprint_half_y_m) / abs(transform.e))
    else:
        radius_x = math.ceil(abs(footprint_half_x_m))
        radius_y = math.ceil(abs(footprint_half_y_m))

    height, width = raw.shape
    if 2 * radius_x + 1 > width or 2 * radius_y + 1 > height:
        raise FlatnessSearchError("no fully-defined footprint window fits within the DEM")
    best: tuple[float, float, float, int, int, float] | None = None
    for row in range(radius_y, height - radius_y):
        for column in range(radius_x, width - radius_x):
            window = raw[
                row - radius_y : row + radius_y + 1,
                column - radius_x : column + radius_x + 1,
            ]
            if not np.isfinite(window).all():
                continue
            elevation_range = float(np.max(window) - np.min(window))
            if best is None or elevation_range < best[0]:
                best = (
                    elevation_range,
                    float(np.std(window)),
                    float(np.mean(window)),
                    row,
                    column,
                    float(window.size),
                )
    if best is None:
        raise FlatnessSearchError("no fully-defined footprint window exists in the DEM")
    elevation_range, standard_deviation, mean_raw, row, column, sample_count = best
    projected_x, projected_y = transform * (column + 0.5, row + 0.5)
    local_x, local_y = frame.projected_to_local_xy(projected_x, projected_y)
    surface_z = frame.habitat_z_local(mean_raw)
    return FlattestAnchor(
        anchor=TerrainAnchor(
            projected_xy_m=(float(projected_x), float(projected_y)),
            local_xyz_m=(local_x, local_y, surface_z),
            dem_row_column=(row, column),
            mode="flattest",
        ),
        report=FlatnessReport(
            elevation_range_m=elevation_range,
            valid_sample_count=int(sample_count),
            standard_deviation_m=standard_deviation,
            mean_surface_z_m=surface_z,
            window_radius_px=(radius_y, radius_x),
        ),
        raw_z_m=mean_raw,
    )
