"""HiRISE Digital Elevation Model loader.

Reads GeoTIFF DEMs produced by the HiRISE camera on Mars Reconnaissance
Orbiter and returns a numpy elevation array with metadata.
"""

import json
import os

import numpy as np


def load_hirise_dem(dem_path: str) -> tuple[np.ndarray, dict]:
    """Load a HiRISE DEM GeoTIFF and return elevation data with metadata.

    Reads a single-band GeoTIFF using GDAL, extracts the elevation array
    as float32, and collects spatial metadata (resolution, bounds, CRS,
    no-data value).

    Args:
        dem_path: Absolute or relative path to the GeoTIFF file.

    Returns:
        A tuple of (elevation, metadata) where:
        - elevation: 2D numpy float32 array of shape (rows, cols)
          with values in meters. Nodata pixels are replaced with NaN.
        - metadata: dict with keys:
          - resolution_x: pixel width in meters (positive)
          - resolution_y: pixel height in meters (positive)
          - origin_x: top-left X coordinate in CRS units
          - origin_y: top-left Y coordinate in CRS units
          - width: number of columns
          - height: number of rows
          - crs_wkt: coordinate reference system as WKT string
          - nodata: no-data sentinel value (float or None)
          - elevation_min: minimum non-NaN elevation in meters
          - elevation_max: maximum non-NaN elevation in meters

    Raises:
        FileNotFoundError: If dem_path does not exist.
        ValueError: If the file cannot be opened by GDAL or has no raster bands.
    """
    from osgeo import gdal  # Lazy import: GDAL unavailable in Isaac Sim Python

    gdal.UseExceptions()

    abs_path = os.path.abspath(dem_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"DEM file not found: {abs_path}")

    try:
        ds = gdal.Open(abs_path, gdal.GA_ReadOnly)
    except RuntimeError as e:
        raise ValueError(f"GDAL cannot open file: {abs_path}") from e
    if ds is None:
        raise ValueError(f"GDAL cannot open file: {abs_path}")

    if ds.RasterCount < 1:
        ds = None
        raise ValueError(f"No raster bands in file: {abs_path}")

    band = ds.GetRasterBand(1)
    elevation = band.ReadAsArray().astype(np.float32)

    gt = ds.GetGeoTransform()
    nodata = band.GetNoDataValue()

    if nodata is not None:
        elevation[elevation == np.float32(nodata)] = np.nan

    metadata = {
        "resolution_x": abs(gt[1]),
        "resolution_y": abs(gt[5]),
        "origin_x": gt[0],
        "origin_y": gt[3],
        "width": ds.RasterXSize,
        "height": ds.RasterYSize,
        "crs_wkt": ds.GetProjection(),
        "nodata": nodata,
        "elevation_min": float(np.nanmin(elevation)),
        "elevation_max": float(np.nanmax(elevation)),
    }

    ds = None
    return elevation, metadata


def save_converted_dem(elevation: np.ndarray, metadata: dict, output_dir: str) -> None:
    """Save DEM data as GDAL-free format (.npy + metadata.json).

    Pre-converts GeoTIFF-loaded DEM data into a format loadable without
    GDAL. Intended to be called from system Python (which has GDAL) so
    that Isaac Sim Python (which lacks GDAL) can load the result.

    Args:
        elevation: 2D float32 elevation array from load_hirise_dem().
        metadata: Metadata dict from load_hirise_dem().
        output_dir: Directory to write elevation.npy and metadata.json.

    Raises:
        ValueError: If elevation is not a 2D array.
    """
    if elevation.ndim != 2:
        raise ValueError(f"elevation must be 2D, got {elevation.ndim}D")

    os.makedirs(output_dir, exist_ok=True)
    np.save(os.path.join(output_dir, "elevation.npy"), elevation.astype(np.float32))

    with open(os.path.join(output_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)


def load_converted_dem(converted_dir: str) -> tuple[np.ndarray, dict]:
    """Load pre-converted DEM data (no GDAL required).

    Reads elevation.npy and metadata.json produced by save_converted_dem().
    Uses only numpy and json (stdlib), so this works in any Python
    environment including Isaac Sim's bundled Python.

    Args:
        converted_dir: Directory containing elevation.npy and metadata.json.

    Returns:
        Same (elevation, metadata) tuple as load_hirise_dem().

    Raises:
        FileNotFoundError: If elevation.npy or metadata.json is missing.
    """
    elev_path = os.path.join(converted_dir, "elevation.npy")
    meta_path = os.path.join(converted_dir, "metadata.json")

    if not os.path.isfile(elev_path):
        raise FileNotFoundError(
            f"Pre-converted elevation not found: {elev_path}. "
            f"Run 'python scripts/convert_dem.py' first."
        )
    if not os.path.isfile(meta_path):
        raise FileNotFoundError(
            f"Pre-converted metadata not found: {meta_path}. "
            f"Run 'python scripts/convert_dem.py' first."
        )

    elevation = np.load(elev_path).astype(np.float32)

    with open(meta_path, "r") as f:
        metadata = json.load(f)

    return elevation, metadata


def crop_dem(
    elevation: np.ndarray,
    metadata: dict,
    row: int,
    col: int,
    height: int,
    width: int,
) -> tuple[np.ndarray, dict]:
    """Crop a rectangular window from a loaded DEM.

    Pure-numpy helper used by scenario YAMLs (Wk2 #1-#3, 2026-04-14) to
    extract specific regions (Jezero plain, rim, delta) from the full
    HiRISE DEM without reloading the source GeoTIFF. The returned
    metadata preserves the original ``resolution_x/y`` and ``crs_wkt``
    but updates ``width``, ``height``, ``origin_x/y`` (shifted by the
    crop offset in CRS units), and recomputes ``elevation_min/max``
    for the cropped region.

    Args:
        elevation: 2D float32 array from ``load_hirise_dem`` or
            ``load_converted_dem``.
        metadata: Metadata dict from the same loader.
        row: Top-left row index of the crop (0-based, inclusive).
        col: Top-left column index of the crop (0-based, inclusive).
        height: Number of rows in the crop window.
        width: Number of columns in the crop window.

    Returns:
        Tuple ``(cropped_elevation, cropped_metadata)``. The cropped
        elevation is a *copy* (not a view) so callers may mutate it.

    Raises:
        ValueError: If the crop window falls outside the source DEM,
            if height/width are non-positive, or if the resulting
            crop contains any NaN pixels (since downstream mesh
            building does not tolerate holes).
    """
    if elevation.ndim != 2:
        raise ValueError(f"elevation must be 2D, got shape {elevation.shape}")
    if height <= 0 or width <= 0:
        raise ValueError(f"crop height/width must be > 0, got ({height}, {width})")
    if row < 0 or col < 0:
        raise ValueError(f"crop row/col must be >= 0, got ({row}, {col})")

    src_rows, src_cols = elevation.shape
    if row + height > src_rows or col + width > src_cols:
        raise ValueError(
            f"crop window ({row}:{row + height}, {col}:{col + width}) "
            f"exceeds DEM bounds ({src_rows}, {src_cols})"
        )

    cropped = np.array(elevation[row : row + height, col : col + width], dtype=np.float32)
    if np.isnan(cropped).any():
        raise ValueError(
            f"cropped region contains {int(np.isnan(cropped).sum())} NaN pixel(s); "
            f"choose a crop window fully inside valid data"
        )

    res_x = float(metadata.get("resolution_x", 1.0))
    res_y = float(metadata.get("resolution_y", 1.0))
    origin_x = float(metadata.get("origin_x", 0.0))
    origin_y = float(metadata.get("origin_y", 0.0))

    cropped_meta = dict(metadata)
    cropped_meta["width"] = int(width)
    cropped_meta["height"] = int(height)
    cropped_meta["origin_x"] = origin_x + col * res_x
    cropped_meta["origin_y"] = origin_y - row * res_y
    cropped_meta["elevation_min"] = float(cropped.min())
    cropped_meta["elevation_max"] = float(cropped.max())
    cropped_meta["crop_source_shape"] = [int(src_rows), int(src_cols)]
    cropped_meta["crop_offset"] = [int(row), int(col)]
    return cropped, cropped_meta
