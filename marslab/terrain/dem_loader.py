"""HiRISE Digital Elevation Model loader.

Reads GeoTIFF DEMs produced by the HiRISE camera on Mars Reconnaissance
Orbiter and returns a numpy elevation array with metadata.
"""

import os

import numpy as np
from osgeo import gdal

gdal.UseExceptions()


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
