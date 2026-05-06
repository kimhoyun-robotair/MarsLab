"""Procedural Mars terrain generation.

Generates synthetic elevation maps for five terrain presets (flat,
crater, hills, rocky_plain, canyon) without requiring real HiRISE DEM
data. Output format matches dem_loader.py for seamless integration with
the rest of the pipeline.
"""

import numpy as np
from scipy.ndimage import gaussian_filter

# Procedural-preset tuning constants
# ----------------------------------
# ``MARS_DATUM_BASE_Z`` is the offset applied to every preset's base
# plane so the generated elevation array sits near the Mars datum
# (-2500 m). Mesh building re-normalises to z_min=0 for physics, but
# preserving the absolute datum lets the metadata round-trip with
# real HiRISE DEMs whose elevations are reported relative to the same
# Mars equipotential surface.
MARS_DATUM_BASE_Z: float = -2500.0

# Crater preset -- impact-basin tuning. Radius is a fraction of the
# shortest grid side so the bowl always fits in the domain. Depth and
# rim height are picked to give a clearly traversable rim without
# clipping the floor against ``MARS_DATUM_BASE_Z``.
CRATER_RADIUS_FRACTION: float = 0.3
CRATER_DEPTH_M: float = 20.0
CRATER_RIM_HEIGHT_M: float = 5.0
CRATER_RIM_OUTER_FACTOR: float = 1.3

# Hills preset -- rolling-terrain bumps superimposed on a smooth
# noise field. Five gaussian bumps are enough to break visual
# repetition while staying cheap to compute.
HILLS_BUMP_COUNT: int = 5
HILLS_BUMP_AMP_RANGE_M: tuple[float, float] = (10.0, 25.0)
HILLS_BUMP_SIGMA_RANGE: tuple[float, float] = (20.0, 50.0)

# Rocky-plain preset -- exposed-bedrock mounds. Fifteen mounds give
# ~one-mound-per-300 m^2 on a typical 256x256x1m grid, matching the
# coarse boulder spacing of the InSight landing site.
ROCKY_PLAIN_MOUND_COUNT: int = 15
ROCKY_PLAIN_MOUND_AMP_RANGE_M: tuple[float, float] = (0.3, 1.5)
ROCKY_PLAIN_MOUND_SIGMA_RANGE: tuple[float, float] = (3.0, 8.0)


def generate_terrain(
    preset: str,
    size: tuple[int, int],
    resolution: float,
    seed: int,
    kwargs: dict | None = None,
) -> tuple[np.ndarray, dict]:
    """Generate a procedural Mars terrain elevation map.

    Args:
        preset: Terrain type. One of ``"flat"``, ``"crater"``, ``"hills"``,
            ``"rocky_plain"``, ``"canyon"``.
        size: (rows, cols) in pixels.
        resolution: Meters per pixel.
        seed: Random seed for reproducibility.
        kwargs: Per-preset overrides. Currently consumed only by the
            ``"canyon"`` preset (``canyon_depth``, ``canyon_floor_width``,
            ``canyon_total_width``, ``canyon_curvature``, ``canyon_craters``,
            ``canyon_crater_radius_range``, ``canyon_crater_depth_range``).
            Ignored by the other presets.

    Returns:
        A tuple of (elevation, metadata) matching dem_loader.py format:
        - elevation: 2D float32 array in meters.
        - metadata: dict with resolution_x/y, width, height, elevation_min/max, etc.

    Raises:
        ValueError: If preset is unknown or size/resolution is invalid.
    """
    if preset not in ("flat", "crater", "hills", "rocky_plain", "canyon"):
        raise ValueError(
            f"Unknown preset '{preset}', expected: flat, crater, hills, rocky_plain, canyon"
        )
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError(f"size must be positive, got {size}")
    if resolution <= 0:
        raise ValueError(f"resolution must be > 0, got {resolution}")

    if kwargs is None:
        kwargs = {}

    rng = np.random.default_rng(seed)
    rows, cols = size

    # Preset whitelist is enforced above; the dispatch below covers every
    # accepted value, so no terminal ``else`` branch is needed.
    if preset == "flat":
        elevation = _generate_flat(rng, rows, cols)
    elif preset == "crater":
        elevation = _generate_crater(rng, rows, cols)
    elif preset == "hills":
        elevation = _generate_hills(rng, rows, cols)
    elif preset == "canyon":
        elevation = _generate_canyon(rng, rows, cols, resolution, kwargs)
    else:  # preset == "rocky_plain"
        elevation = _generate_rocky_plain(rng, rows, cols)

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


def _normalize_noise(
    rng: np.random.Generator,
    rows: int,
    cols: int,
    sigma: float,
    amplitude: float,
) -> np.ndarray:
    """Draw Gaussian noise, smooth it, and rescale to the requested amplitude.

    Internally: ``rng.standard_normal((rows, cols))`` ->
    ``gaussian_filter(..., sigma)`` -> divide by std (``+1e-8`` guard) ->
    multiply by ``amplitude``. The seven call sites that share this
    numerically stable path are:

        1. ``_generate_flat``  -- one call (smooth_noise).
        2. ``_generate_hills`` -- one call (smooth_noise).
        3. ``_generate_canyon`` -- two calls (base_noise, wall_noise).
        4. ``_generate_rocky_plain`` -- three calls (low_freq,
           mid_freq, high_freq).

    Args:
        rng: Numpy random generator (consumes one draw).
        rows: Grid rows.
        cols: Grid cols.
        sigma: Gaussian blur sigma, in pixels.
        amplitude: Target standard deviation after normalisation.

    Returns:
        Shape ``(rows, cols)`` float64 array with empirical std close to
        ``amplitude``.
    """
    raw = rng.standard_normal((rows, cols))
    smooth = gaussian_filter(raw, sigma=sigma)
    return smooth / (np.std(smooth) + 1e-8) * amplitude


def _add_micro_detail(
    rng: np.random.Generator, elevation: np.ndarray, amplitude: float = 0.15
) -> np.ndarray:
    """Add high-frequency micro-terrain detail for close-up realism."""
    rows, cols = elevation.shape
    fine_noise = rng.standard_normal((rows, cols))
    fine = gaussian_filter(fine_noise, sigma=2.0) * amplitude
    return elevation + fine


def _generate_flat(rng: np.random.Generator, rows: int, cols: int) -> np.ndarray:
    """Flat desert with low-amplitude noise (~2m variation) + micro detail."""
    base = MARS_DATUM_BASE_Z
    smooth_noise = _normalize_noise(rng, rows, cols, sigma=10.0, amplitude=2.0)
    return _add_micro_detail(rng, base + smooth_noise)


def _generate_crater(rng: np.random.Generator, rows: int, cols: int) -> np.ndarray:
    """Impact crater with rim and ejecta blanket."""
    base = _generate_flat(rng, rows, cols)

    cy, cx = rows / 2.0, cols / 2.0
    radius = min(rows, cols) * CRATER_RADIUS_FRACTION
    depth = CRATER_DEPTH_M
    rim_height = CRATER_RIM_HEIGHT_M

    y_grid, x_grid = np.mgrid[0:rows, 0:cols]
    dist = np.sqrt((x_grid - cx) ** 2 + (y_grid - cy) ** 2)

    # Crater bowl (parabolic profile)
    inside = dist < radius
    crater = np.zeros_like(base)
    crater[inside] = -depth * (1.0 - (dist[inside] / radius) ** 2)

    # Rim (annular bump)
    rim_inner = radius
    rim_outer = radius * CRATER_RIM_OUTER_FACTOR
    rim_mask = (dist >= rim_inner) & (dist < rim_outer)
    rim_frac = (dist[rim_mask] - rim_inner) / (rim_outer - rim_inner)
    crater[rim_mask] = rim_height * np.sin(np.pi * rim_frac)

    return _add_micro_detail(rng, base + crater)


def _generate_hills(rng: np.random.Generator, rows: int, cols: int) -> np.ndarray:
    """Gently rolling hills with large-scale variation (~30m amplitude)."""
    base = MARS_DATUM_BASE_Z
    smooth_noise = _normalize_noise(rng, rows, cols, sigma=30.0, amplitude=30.0)

    # Add a few gaussian bumps for distinct hills
    y_grid, x_grid = np.mgrid[0:rows, 0:cols]
    bumps = np.zeros((rows, cols))
    amp_lo, amp_hi = HILLS_BUMP_AMP_RANGE_M
    sig_lo, sig_hi = HILLS_BUMP_SIGMA_RANGE
    for _ in range(HILLS_BUMP_COUNT):
        cx = rng.uniform(0, cols)
        cy = rng.uniform(0, rows)
        amp = rng.uniform(amp_lo, amp_hi)
        sigma = rng.uniform(sig_lo, sig_hi)
        bumps += amp * np.exp(-((x_grid - cx) ** 2 + (y_grid - cy) ** 2) / (2 * sigma**2))

    return _add_micro_detail(rng, base + smooth_noise + bumps)


def _generate_canyon(
    rng: np.random.Generator,
    rows: int,
    cols: int,
    resolution: float,
    params: dict,
) -> np.ndarray:
    """Procedural canyon with walls, traversable floor, and small craters.

    Generates a winding canyon carved into a flat plain. The canyon has
    steep walls (50-70 deg) flanking a traversable floor (<5 deg), with
    optional small craters on the floor for obstacle avoidance testing.

    Args:
        rng: Numpy random generator.
        rows: Number of rows (pixels).
        cols: Number of columns (pixels).
        resolution: Meters per pixel.
        params: Canyon configuration dict with keys:
            canyon_depth, canyon_floor_width, canyon_total_width,
            canyon_curvature, canyon_craters, canyon_crater_radius_range,
            canyon_crater_depth_range.
    """
    depth = float(params.get("canyon_depth", 40.0))
    floor_width = float(params.get("canyon_floor_width", 30.0))
    total_width = float(params.get("canyon_total_width", 80.0))
    curvature = float(params.get("canyon_curvature", 0.3))
    n_craters = int(params.get("canyon_craters", 2))
    crater_r_range = params.get("canyon_crater_radius_range", [5.0, 15.0])
    crater_d_range = params.get("canyon_crater_depth_range", [2.0, 6.0])

    base = MARS_DATUM_BASE_Z

    # Low-frequency base terrain noise (subtle, ~1m)
    base_noise = _normalize_noise(rng, rows, cols, sigma=15.0, amplitude=1.0)

    elevation = np.full((rows, cols), base, dtype=np.float64) + base_noise

    # Canyon centerline: sinusoidal curve along the row axis (N-S)
    # Centerline column position as function of row
    row_coords = np.arange(rows) * resolution
    center_col_m = (cols / 2.0) * resolution  # center of map in meters

    # Generate smooth curvature using low-frequency sinusoids
    freq1 = 2.0 * np.pi / (rows * resolution)
    freq2 = 2.0 * np.pi / (rows * resolution) * 2.3
    phase_primary = rng.uniform(0, 2 * np.pi)
    phase_secondary = rng.uniform(0, 2 * np.pi)
    amplitude = curvature * (cols * resolution) * 0.15

    centerline_m = (
        center_col_m
        + amplitude * np.sin(freq1 * row_coords + phase_primary)
        + amplitude * 0.3 * np.sin(freq2 * row_coords + phase_secondary)
    )

    # Build distance-to-centerline map
    y_grid, x_grid = np.mgrid[0:rows, 0:cols]
    x_m = x_grid.astype(np.float64) * resolution
    centerline_2d = centerline_m[y_grid]
    dist = np.abs(x_m - centerline_2d)

    # Canyon profile parameters (in meters)
    floor_half = floor_width / 2.0
    rim_half = total_width / 2.0
    wall_width = rim_half - floor_half

    # Smoothstep function: 3t^2 - 2t^3
    def smoothstep(t: np.ndarray) -> np.ndarray:
        t_clamped = np.clip(t, 0.0, 1.0)
        return t_clamped * t_clamped * (3.0 - 2.0 * t_clamped)

    # Apply canyon profile
    # Inside floor: full depth
    floor_mask = dist < floor_half
    elevation[floor_mask] = base - depth + base_noise[floor_mask] * 0.3

    # Wall transition: smoothstep from floor to rim
    wall_mask = (dist >= floor_half) & (dist < rim_half)
    if wall_width > 0:
        t = (dist[wall_mask] - floor_half) / wall_width
        wall_height = depth * smoothstep(t)
        elevation[wall_mask] = base - depth + wall_height + base_noise[wall_mask] * 0.2

    # Add wall roughness (medium frequency noise on walls only)
    wall_noise = _normalize_noise(rng, rows, cols, sigma=3.0, amplitude=1.5)
    elevation[wall_mask] += wall_noise[wall_mask]

    # Small craters on canyon floor
    floor_rows = np.where(floor_mask.any(axis=1))[0]
    if len(floor_rows) > 0 and n_craters > 0:
        for _ in range(n_craters):
            cr_row = rng.choice(floor_rows)
            floor_cols_at_row = np.where(floor_mask[cr_row])[0]
            if len(floor_cols_at_row) == 0:
                continue
            cr_col = rng.choice(floor_cols_at_row)
            cr_radius = rng.uniform(crater_r_range[0], crater_r_range[1])
            cr_depth = rng.uniform(crater_d_range[0], crater_d_range[1])
            cr_rim_h = cr_depth * 0.2

            cr_dist = np.sqrt(
                ((x_grid - cr_col) * resolution) ** 2 + ((y_grid - cr_row) * resolution) ** 2
            )
            cr_inside = cr_dist < cr_radius
            crater_profile = np.zeros_like(elevation)
            crater_profile[cr_inside] = -cr_depth * (1.0 - (cr_dist[cr_inside] / cr_radius) ** 2)
            # Rim
            cr_rim_mask = (cr_dist >= cr_radius) & (cr_dist < cr_radius * 1.3)
            rim_frac = (cr_dist[cr_rim_mask] - cr_radius) / (cr_radius * 0.3)
            crater_profile[cr_rim_mask] = cr_rim_h * np.sin(np.pi * rim_frac)
            elevation += crater_profile

    return _add_micro_detail(rng, elevation).astype(np.float32)


def _generate_rocky_plain(rng: np.random.Generator, rows: int, cols: int) -> np.ndarray:
    """Rocky plain with medium-scale undulations (0.3-2m) for close-up realism."""
    base = MARS_DATUM_BASE_Z

    # Low-frequency base terrain (~5m variation)
    low_freq = _normalize_noise(rng, rows, cols, sigma=15.0, amplitude=5.0)

    # Medium-frequency rocky undulations (~1.5m)
    mid_freq = _normalize_noise(rng, rows, cols, sigma=5.0, amplitude=1.5)

    # High-frequency micro-roughness (~0.3m)
    high_freq = _normalize_noise(rng, rows, cols, sigma=1.5, amplitude=0.3)

    # Scattered small mounds (like exposed bedrock)
    y_grid, x_grid = np.mgrid[0:rows, 0:cols]
    mounds = np.zeros((rows, cols))
    amp_lo, amp_hi = ROCKY_PLAIN_MOUND_AMP_RANGE_M
    sig_lo, sig_hi = ROCKY_PLAIN_MOUND_SIGMA_RANGE
    for _ in range(ROCKY_PLAIN_MOUND_COUNT):
        cx = rng.uniform(0, cols)
        cy = rng.uniform(0, rows)
        amp = rng.uniform(amp_lo, amp_hi)
        sigma = rng.uniform(sig_lo, sig_hi)
        mounds += amp * np.exp(-((x_grid - cx) ** 2 + (y_grid - cy) ** 2) / (2 * sigma**2))

    return _add_micro_detail(rng, base + low_freq + mid_freq + high_freq + mounds)
