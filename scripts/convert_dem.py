"""GeoTIFF to numpy pre-conversion for GDAL-free Isaac Sim loading.

Run with system Python (which has GDAL installed):
    python scripts/convert_dem.py --config configs/terrain/jezero_crater.yaml

This converts the HiRISE DEM GeoTIFF into elevation.npy + metadata.json,
which Isaac Sim Python can load without GDAL via load_converted_dem().
"""

import argparse
import os
import sys

import numpy as np

# Ensure marslab package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from marslab.config.loader import load_config
from marslab.terrain.dem_loader import load_converted_dem, load_hirise_dem, save_converted_dem


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert HiRISE GeoTIFF to numpy format")
    parser.add_argument(
        "--config",
        default="configs/terrain/jezero_crater.yaml",
        help="Path to terrain config YAML",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: derived from config or DEM path)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    if config.terrain.source != "hirise":
        print(
            f"[convert_dem] terrain.source is '{config.terrain.source}',"
            f" not 'hirise'. Nothing to convert."
        )
        return

    if config.terrain.dem_path is None:
        print("[convert_dem] ERROR: terrain.dem_path is not set in config.")
        sys.exit(1)

    # Determine output directory
    if args.output_dir:
        output_dir = args.output_dir
    elif config.terrain.converted_dem_dir:
        output_dir = config.terrain.converted_dem_dir
    else:
        # Derive from DEM path: foo/bar.tif -> foo/bar_converted/
        base = os.path.splitext(config.terrain.dem_path)[0]
        output_dir = base + "_converted"

    # Stage 1: Load GeoTIFF with GDAL
    print(f"[convert_dem] Loading GeoTIFF: {config.terrain.dem_path}")
    elevation, metadata = load_hirise_dem(config.terrain.dem_path)
    print(f"  Shape: {elevation.shape}")
    print(f"  Resolution: {metadata['resolution_x']:.4f} m/px")
    print(f"  Elevation: {metadata['elevation_min']:.1f} ~ {metadata['elevation_max']:.1f} m")

    # Stage 2: Save as numpy + JSON
    print(f"[convert_dem] Saving to: {output_dir}/")
    save_converted_dem(elevation, metadata, output_dir)

    # Stage 3: Verify round-trip
    print("[convert_dem] Verifying round-trip...")
    loaded_elev, loaded_meta = load_converted_dem(output_dir)

    assert loaded_elev.shape == elevation.shape, "Shape mismatch after round-trip"
    assert loaded_elev.dtype == np.float32, "Dtype mismatch after round-trip"
    assert np.allclose(loaded_elev, elevation, equal_nan=True), "Elevation data mismatch"
    assert loaded_meta["resolution_x"] == metadata["resolution_x"], "Resolution mismatch"

    npy_size = os.path.getsize(os.path.join(output_dir, "elevation.npy"))
    print("  Round-trip verification: PASSED")
    print(f"  Output size: {npy_size / 1024:.1f} KB")
    print("\n[convert_dem] Done. Isaac Sim can now load this with:")
    print(f'  converted_dem_dir: "{output_dir}"')


if __name__ == "__main__":
    main()
