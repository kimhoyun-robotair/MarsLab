"""Procedural Mars terrain generation.

Generates synthetic elevation maps for three terrain presets (flat, crater,
hills) without requiring real HiRISE DEM data. Output format matches
dem_loader.py for seamless integration with the rest of the pipeline.
"""

import numpy as np
from scipy.ndimage import gaussian_filter


def generate_terrain(
    preset: str,
    size: tuple[int, int],
    resolution: float,
    seed: int,
) -> tuple[np.ndarray, dict]:
    """Generate a procedural Mars terrain elevation map.

    Args:
        preset: Terrain type — "flat", "crater", or "hills".
        size: (rows, cols) in pixels.
        resolution: Meters per pixel.
        seed: Random seed for reproducibility.

    Returns:
        A tuple of (elevation, metadata) matching dem_loader.py format:
        - elevation: 2D float32 array in meters.
        - metadata: dict with resolution_x/y, width, height, elevation_min/max, etc.

    Raises:
        ValueError: If preset is unknown or size/resolution is invalid.
    """
    if preset not in ("flat", "crater", "hills"):
        raise ValueError(f"Unknown preset '{preset}', expected: flat, crater, hills")
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError(f"size must be positive, got {size}")
    if resolution <= 0:
        raise ValueError(f"resolution must be > 0, got {resolution}")

    rng = np.random.default_rng(seed)
    rows, cols = size

    if preset == "flat":
        elevation = _generate_flat(rng, rows, cols)
    elif preset == "crater":
        elevation = _generate_crater(rng, rows, cols)
    else:
        elevation = _generate_hills(rng, rows, cols)

    elevation = elevation.astype(np.float32)

    metadata = {
        "resolution_x": resolution,
        "resolution_y": resolution,
        "origin_x": 0.0,
        "origin_y": 0.0,
        "width": cols,
        "height": rows,
        "crs_wkt": "",
        "nodata": None,
        "elevation_min": float(np.min(elevation)),
        "elevation_max": float(np.max(elevation)),
    }

    return elevation, metadata


def _generate_flat(rng: np.random.Generator, rows: int, cols: int) -> np.ndarray:
    """Flat desert with low-amplitude noise (~2m variation)."""
    base = -2500.0
    noise = rng.standard_normal((rows, cols))
    smooth_noise = gaussian_filter(noise, sigma=10.0)
    smooth_noise = smooth_noise / np.std(smooth_noise) * 2.0
    return base + smooth_noise


def _generate_crater(rng: np.random.Generator, rows: int, cols: int) -> np.ndarray:
    """Impact crater with rim and ejecta blanket."""
    base = _generate_flat(rng, rows, cols)

    cy, cx = rows / 2.0, cols / 2.0
    radius = min(rows, cols) * 0.3
    depth = 20.0
    rim_height = 5.0

    y_grid, x_grid = np.mgrid[0:rows, 0:cols]
    dist = np.sqrt((x_grid - cx) ** 2 + (y_grid - cy) ** 2)

    # Crater bowl (parabolic profile)
    inside = dist < radius
    crater = np.zeros_like(base)
    crater[inside] = -depth * (1.0 - (dist[inside] / radius) ** 2)

    # Rim (annular bump)
    rim_inner = radius
    rim_outer = radius * 1.3
    rim_mask = (dist >= rim_inner) & (dist < rim_outer)
    rim_frac = (dist[rim_mask] - rim_inner) / (rim_outer - rim_inner)
    crater[rim_mask] = rim_height * np.sin(np.pi * rim_frac)

    return base + crater


def _generate_hills(rng: np.random.Generator, rows: int, cols: int) -> np.ndarray:
    """Gently rolling hills with large-scale variation (~30m amplitude)."""
    base = -2500.0
    noise = rng.standard_normal((rows, cols))
    smooth_noise = gaussian_filter(noise, sigma=30.0)
    smooth_noise = smooth_noise / np.std(smooth_noise) * 30.0

    # Add a few gaussian bumps for distinct hills
    y_grid, x_grid = np.mgrid[0:rows, 0:cols]
    bumps = np.zeros((rows, cols))
    for _ in range(5):
        cx = rng.uniform(0, cols)
        cy = rng.uniform(0, rows)
        amp = rng.uniform(10.0, 25.0)
        sigma = rng.uniform(20.0, 50.0)
        bumps += amp * np.exp(-((x_grid - cx) ** 2 + (y_grid - cy) ** 2) / (2 * sigma**2))

    return base + smooth_noise + bumps
