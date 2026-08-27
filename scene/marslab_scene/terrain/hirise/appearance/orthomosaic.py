"""Orthomosaic crop, resample, and luminance extraction for Task 12."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds

from marslab_scene.terrain.hirise.config import OrthomosaicConfig
from marslab_scene.terrain.hirise.ingest.geotiff import RasterCrop


class OrthomosaicProcessingError(ValueError):
    """Raised when orthomosaic luminance extraction fails."""


@dataclass(frozen=True, slots=True)
class OrthomosaicLuminance:
    """Normalized luminance crop from a georeferenced orthomosaic."""

    array: np.ndarray
    source_width: int
    source_height: int
    output_width: int
    output_height: int
    band_mode: str
    resampling: str


def read_orthomosaic_luminance(
    config: OrthomosaicConfig,
    crop: RasterCrop,
    *,
    output_width: int,
    output_height: int,
) -> OrthomosaicLuminance:
    """Read the orthomosaic over DEM crop bounds and return normalized luminance."""
    if config.path is None:
        msg = "orthomosaic.path is required"
        raise OrthomosaicProcessingError(msg)
    if output_width < 1 or output_height < 1:
        msg = "output_width and output_height must be >= 1"
        raise OrthomosaicProcessingError(msg)

    with rasterio.open(config.path) as dataset:
        window = from_bounds(*crop.bounds, transform=dataset.transform)
        indexes, band_mode = _select_indexes(
            count=dataset.count,
            band_mode=config.band_mode,
            band_index=config.band_index,
        )
        data = dataset.read(
            indexes,
            window=window,
            out_shape=(len(indexes), output_height, output_width),
            resampling=_resampling(config.resampling),
            boundless=True,
            fill_value=0,
        )

    luminance = _extract_luminance(data)
    return OrthomosaicLuminance(
        array=_normalize_luminance(luminance),
        source_width=max(1, int(round(window.width))),
        source_height=max(1, int(round(window.height))),
        output_width=output_width,
        output_height=output_height,
        band_mode=band_mode,
        resampling=config.resampling,
    )


def _select_indexes(
    *,
    count: int,
    band_mode: str,
    band_index: int | None,
) -> tuple[list[int], str]:
    if count < 1:
        msg = "Orthomosaic must have at least one band"
        raise OrthomosaicProcessingError(msg)
    if band_mode == "auto":
        return (list(range(1, 4)), "rgb") if count >= 3 else ([1], "grayscale")
    if band_mode == "grayscale":
        return [1], "grayscale"
    if band_mode == "rgb":
        if count < 3:
            msg = "Orthomosaic band_mode=rgb requires at least 3 bands"
            raise OrthomosaicProcessingError(msg)
        return [1, 2, 3], "rgb"
    if band_mode == "band":
        if band_index is None or band_index < 1 or band_index > count:
            msg = "Orthomosaic band_index is outside the available band range"
            raise OrthomosaicProcessingError(msg)
        return [band_index], "band"
    msg = f"Unsupported orthomosaic band_mode: {band_mode}"
    raise OrthomosaicProcessingError(msg)


def _extract_luminance(data: np.ndarray) -> np.ndarray:
    values = np.asarray(data, dtype=np.float64)
    if values.ndim != 3:
        msg = "Orthomosaic data must be band-first"
        raise OrthomosaicProcessingError(msg)
    if values.shape[0] == 1:
        return values[0]
    rgb = values[:3]
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _normalize_luminance(array: np.ndarray) -> np.ndarray:
    values = np.asarray(array, dtype=np.float64)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        msg = "Orthomosaic luminance contains no finite values"
        raise OrthomosaicProcessingError(msg)
    min_value = float(np.min(finite))
    max_value = float(np.max(finite))
    if max_value <= min_value:
        return np.zeros(values.shape, dtype=np.float32)
    normalized = (values - min_value) / (max_value - min_value)
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)


def _resampling(method: str) -> Resampling:
    if method == "nearest":
        return Resampling.nearest
    if method == "bilinear":
        return Resampling.bilinear
    if method == "cubic":
        return Resampling.cubic
    msg = f"Unsupported orthomosaic resampling method: {method}"
    raise OrthomosaicProcessingError(msg)
