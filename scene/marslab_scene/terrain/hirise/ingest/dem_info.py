"""DEM metadata inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import rasterio
from pydantic import JsonValue
from rasterio.transform import Affine


@dataclass(frozen=True, slots=True)
class DemInfo:
    """Metadata summary for a DEM raster band."""

    path: str
    width: int
    height: int
    count: int
    dtype: str
    crs_wkt: str | None
    transform: tuple[float, float, float, float, float, float]
    bounds: tuple[float, float, float, float]
    nodata: float | None
    pixel_size_x_m: float
    pixel_size_y_m: float
    is_north_up: bool
    estimated_full_raster_size_mb: float

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a JSON-serializable representation."""
        return {
            "path": self.path,
            "width": self.width,
            "height": self.height,
            "count": self.count,
            "band_count": self.count,
            "dtype": self.dtype,
            "crs_wkt": self.crs_wkt,
            "transform": list(self.transform),
            "bounds": list(self.bounds),
            "nodata": self.nodata,
            "pixel_size_x_m": self.pixel_size_x_m,
            "pixel_size_y_m": self.pixel_size_y_m,
            "is_north_up": self.is_north_up,
            "estimated_full_raster_size_mb": self.estimated_full_raster_size_mb,
        }


class DemInfoError(ValueError):
    """Base error for DEM metadata validation."""


class UnsupportedRasterTransformError(DemInfoError):
    """Raised when a raster transform is rotated or sheared."""


class UnsupportedCrsError(DemInfoError):
    """Raised when the CRS is missing or not projected in meters."""


def inspect_dem(path: Path | str, band: int = 1) -> DemInfo:
    """Inspect raster metadata without reading pixel data."""
    raster_path = Path(path)
    with rasterio.open(raster_path) as dataset:
        if band < 1 or band > dataset.count:
            msg = f"Band {band} is outside available band range 1..{dataset.count}"
            raise ValueError(msg)

        transform = dataset.transform
        dtype = dataset.dtypes[band - 1]
        bytes_per_sample = _dtype_size(dtype)
        estimated_size_mb = (
            dataset.width * dataset.height * dataset.count * bytes_per_sample / 1_000_000
        )

        return DemInfo(
            path=str(raster_path),
            width=dataset.width,
            height=dataset.height,
            count=dataset.count,
            dtype=dtype,
            crs_wkt=dataset.crs.to_wkt() if dataset.crs else None,
            transform=_affine_to_tuple(transform),
            bounds=(
                float(dataset.bounds.left),
                float(dataset.bounds.bottom),
                float(dataset.bounds.right),
                float(dataset.bounds.top),
            ),
            nodata=_band_nodata(dataset.nodatavals, band),
            pixel_size_x_m=abs(float(transform.a)),
            pixel_size_y_m=abs(float(transform.e)),
            is_north_up=_is_north_up(transform),
            estimated_full_raster_size_mb=float(estimated_size_mb),
        )


def validate_dem_for_mvp(info: DemInfo, *, require_projected_units_meters: bool = True) -> None:
    """Validate metadata assumptions required by the MVP."""
    transform = Affine(*info.transform)
    if not _is_north_up(transform):
        msg = "Rotated or sheared rasters are not supported by the MVP"
        raise UnsupportedRasterTransformError(msg)

    if require_projected_units_meters:
        if info.crs_wkt is None:
            msg = "DEM CRS is missing; projected meter units are required"
            raise UnsupportedCrsError(msg)

        crs = rasterio.crs.CRS.from_wkt(info.crs_wkt)
        if not crs.is_projected or not _crs_uses_meter_units(crs):
            msg = "DEM CRS must be projected and use meter units for the MVP"
            raise UnsupportedCrsError(msg)


def _affine_to_tuple(transform: Affine) -> tuple[float, float, float, float, float, float]:
    return (
        float(transform.a),
        float(transform.b),
        float(transform.c),
        float(transform.d),
        float(transform.e),
        float(transform.f),
    )


def _is_north_up(transform: Affine) -> bool:
    return transform.b == 0 and transform.d == 0 and transform.a > 0 and transform.e < 0


def _band_nodata(nodatavals: tuple[float | None, ...], band: int) -> float | None:
    nodata = nodatavals[band - 1]
    return float(nodata) if nodata is not None else None


def _dtype_size(dtype: str) -> int:
    return int(__import__("numpy").dtype(dtype).itemsize)


def _crs_uses_meter_units(crs: rasterio.crs.CRS) -> bool:
    units_factor = crs.linear_units_factor
    if units_factor is None:
        return False

    unit_name, factor = units_factor
    return unit_name.lower() in {"metre", "meter", "metres", "meters"} and float(factor) == 1.0
