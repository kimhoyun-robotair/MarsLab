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
