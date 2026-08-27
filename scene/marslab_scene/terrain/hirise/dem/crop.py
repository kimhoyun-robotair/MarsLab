"""Crop window calculation."""

from __future__ import annotations

import math

from affine import Affine
from rasterio.windows import Window

from marslab_scene.terrain.hirise.config import CropConfig
from marslab_scene.terrain.hirise.ingest.dem_info import DemInfo


class CropError(ValueError):
    """Base error for crop calculation failures."""


class CropOutOfBoundsError(CropError):
    """Raised when the requested crop extends outside the raster."""


class UnsupportedRasterTransformError(CropError):
    """Raised when crop math would be invalid for the raster transform."""


def compute_crop_window(info: DemInfo, config: CropConfig) -> Window:
    """Compute a rasterio window for a meter-sized crop."""
    transform = Affine(*info.transform)
    _validate_north_up(transform)

    width_px = _meters_to_pixels(config.width_m, info.pixel_size_x_m)
    height_px = _meters_to_pixels(config.height_m, info.pixel_size_y_m)
    center_x, center_y = _crop_center_projected(info, config)
    center_col, center_row = (~transform) * (center_x, center_y)

    col_off = _round_half_up(center_col - width_px / 2)
    row_off = _round_half_up(center_row - height_px / 2)
    window = Window(col_off=col_off, row_off=row_off, width=width_px, height=height_px)

    if not _window_inside_raster(window, info.width, info.height):
        if not config.allow_partial:
            msg = (
                "Requested crop window is outside raster bounds: "
                f"window={window}, raster_width={info.width}, raster_height={info.height}"
            )
            raise CropOutOfBoundsError(msg)
        window = _clip_window(window, info.width, info.height)

    return window


def compute_crop_origin_projected(
    crop_transform: Affine,
    width: int,
    height: int,
) -> tuple[float, float]:
    """Return the projected center of a crop."""
    left = crop_transform.c
    top = crop_transform.f
    right = left + crop_transform.a * width
    bottom = top + crop_transform.e * height
    return ((left + right) / 2, (top + bottom) / 2)


def _crop_center_projected(info: DemInfo, config: CropConfig) -> tuple[float, float]:
    if config.center_mode == "dataset_center":
        left, bottom, right, top = info.bounds
        return ((left + right) / 2, (bottom + top) / 2)

    if config.center_mode == "projected":
        if config.center_x is None or config.center_y is None:
            msg = "center_x and center_y are required when center_mode=projected"
            raise CropError(msg)
        return (config.center_x, config.center_y)

    msg = f"Unsupported crop center_mode: {config.center_mode}"
    raise CropError(msg)


def _meters_to_pixels(size_m: float, pixel_size_m: float) -> int:
    pixels = _round_half_up(size_m / pixel_size_m)
    return max(1, pixels)


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _window_inside_raster(window: Window, width: int, height: int) -> bool:
    return (
        window.col_off >= 0
        and window.row_off >= 0
        and window.col_off + window.width <= width
        and window.row_off + window.height <= height
    )


def _clip_window(window: Window, width: int, height: int) -> Window:
    col_off = max(0, int(window.col_off))
    row_off = max(0, int(window.row_off))
    col_end = min(width, int(window.col_off + window.width))
    row_end = min(height, int(window.row_off + window.height))
    return Window(
        col_off=col_off,
        row_off=row_off,
        width=max(0, col_end - col_off),
        height=max(0, row_end - row_off),
    )


def _validate_north_up(transform: Affine) -> None:
    if transform.b != 0 or transform.d != 0 or transform.a <= 0 or transform.e >= 0:
        msg = "Rotated or sheared rasters are not supported by the MVP"
        raise UnsupportedRasterTransformError(msg)
