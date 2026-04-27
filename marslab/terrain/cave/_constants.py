"""Literal defaults for cave geometry tuning knobs.

These constants are consumed as fallbacks when a ``CaveConfig`` does
not carry a ``geometry`` block. The top nine knobs that materially
affect centerline / surface tuning are also mirrored in
:class:`CaveGeometryConfig` so scenarios can override them from YAML.

Kept private (``_constants``) because the submodules call the wrapper
functions with explicit kwargs; external callers should pass values
through ``CaveGeometryConfig`` instead of importing these directly.
"""

from __future__ import annotations

from typing import Final

# Centerline shape
CENTERLINE_PATH_LENGTH_FACTOR: Final[float] = 1.1
CENTERLINE_FREQ_RATIO_SECONDARY: Final[float] = 2.3
CENTERLINE_SECONDARY_AMP_RATIO: Final[float] = 0.3
CENTERLINE_AMP_DOMAIN_RATIO: Final[float] = 0.15

# Cross-section Gaussian smoothing (sigma along stations, sigma along ring)
CROSS_SECTION_SMOOTH_SIGMA: Final[tuple[float, float]] = (3.0, 2.0)

# Tube floor debris
FLOOR_DEBRIS_HEIGHT_SCALE: Final[float] = 0.3
FLOOR_DEBRIS_SMOOTH_SIGMA: Final[float] = 1.5
FLOOR_WIDTH_RATIO: Final[float] = 0.5  # floor_pts = ring_pts * ratio
FLOOR_WIDTH_MIN_PTS: Final[int] = 8

# Surface cap noise
SURFACE_NOISE_SIGMA: Final[float] = 10.0
SURFACE_NOISE_AMPLITUDE_M: Final[float] = 2.0

# Debris cone geometry
DEBRIS_CONE_DIAMETER_RATIO: Final[float] = 0.15  # base diameter vs tube width
DEBRIS_CONE_EXCLUSION_RATIO: Final[float] = 0.1  # half-exclusion vs tube width
DEBRIS_CONE_MAX_OFFSET_RATIO: Final[float] = 0.35
DEBRIS_CONE_RADIUS_SHRINK: Final[float] = 0.8  # base vs skylight diameter/2
DEBRIS_CONE_NOISE_SIGMA: Final[float] = 0.05
DEBRIS_CONE_RINGS: Final[int] = 12
DEBRIS_CONE_SEGMENTS: Final[int] = 24

# Skylight shaft
SKYLIGHT_SEPARATION_RATIO: Final[float] = 1.5
SKYLIGHT_MARGIN_EXTRA_M: Final[float] = 10.0
SKYLIGHT_SHAFT_RING_SPACING_M: Final[float] = 5.0
SKYLIGHT_SHAFT_RING_MIN: Final[int] = 10
SKYLIGHT_SHAFT_SEG_MIN: Final[int] = 16

# Breakdown blocks
BREAKDOWN_DIAMETER_CAP_M: Final[float] = 5.0
BREAKDOWN_FLOOR_SPAN_RATIO: Final[float] = 0.8  # shrink left/right by this
BREAKDOWN_CENTERLINE_EXCLUSION_RATIO: Final[float] = 0.1  # vs station width
BREAKDOWN_MAX_ATTEMPTS: Final[int] = 5000
