"""GeoTIFF DEM reading helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from rasterio.crs import CRS
from rasterio.windows import Window, bounds, transform


@dataclass(frozen=True, slots=True)
class RasterCrop:
    """Windowed raster data and metadata."""

    array: np.ndarray
    mask: np.ndarray
    transform: Affine
    bounds: tuple[float, float, float, float]


def read_dem_window(path: Path | str, window: Window, band: int = 1) -> RasterCrop:
    """Read only a DEM crop window."""
    with rasterio.open(path) as dataset:
        if band < 1 or band > dataset.count:
            msg = f"Band {band} is outside available band range 1..{dataset.count}"
            raise ValueError(msg)

        masked = dataset.read(band, window=window, masked=True)
        crop_transform = transform(window, dataset.transform)
        crop_bounds = bounds(window, dataset.transform)
        fill_value = dataset.nodata if dataset.nodata is not None else 0

    return RasterCrop(
        array=np.asarray(masked.filled(fill_value)),
        mask=np.ma.getmaskarray(masked),
        transform=crop_transform,
        bounds=(
            float(crop_bounds[0]),
            float(crop_bounds[1]),
            float(crop_bounds[2]),
            float(crop_bounds[3]),
        ),
    )


def write_cropped_geotiff(
    path: Path | str,
    crop: RasterCrop,
    *,
    crs_wkt: str | None,
    nodata: float | None,
) -> Path:
    """Write a debug cropped GeoTIFF."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    crs = CRS.from_wkt(crs_wkt) if crs_wkt else None
    with rasterio.open(
        output_path,
        "w",
        driver="GTiff",
        width=crop.array.shape[1],
        height=crop.array.shape[0],
        count=1,
        dtype=crop.array.dtype,
        crs=crs,
        transform=crop.transform,
        nodata=nodata,
    ) as dataset:
        dataset.write(crop.array, 1)
        dataset.write_mask((~crop.mask).astype("uint8") * 255)
    return output_path
