"""Default values for cave geometry tuning knobs.

The constants here serve two roles:

1. **Defaults for low-level helpers.** ``geometry.py``, ``mesh.py``,
   ``features.py``, and ``breakdown.py`` accept these knobs as
   default-valued kwargs so that direct callers (tests, debugging
   scripts) can invoke the helpers without first constructing a
   :class:`CaveConfig`. The orchestrator overrides the YAML-surfaced
   subset on every call.
2. **Source of truth for the YAML-surfaced subset.** Nine knobs are
   mirrored in :class:`CaveGeometryConfig` (centerline shape, cross-
   section smoothing, floor debris height, surface cap noise, debris
   cone diameter ratio). The orchestrator passes
   ``cfg.geometry.*`` through to the helpers, so YAML overrides take
   effect without touching these constants.

The remaining knobs in this module are **mesh-tessellation floors**
(ring counts, segment minimums), **deterministic geometry ratios**
(skylight separation, debris cone exclusion), or **algorithm tuning**
(``BREAKDOWN_MAX_ATTEMPTS``). They are not surfaced to YAML because
they shape the discretisation rather than the physical cave dimensions
that scenarios care about.

Kept private (``_constants``) because the submodules call the wrapper
functions with explicit kwargs; external callers should pass values
through :class:`CaveGeometryConfig` instead of importing these
directly.
"""

from __future__ import annotations

from typing import Final

# Centerline shape -- mirrored in CaveGeometryConfig (YAML-surfaced).
CENTERLINE_PATH_LENGTH_FACTOR: Final[float] = 1.1
CENTERLINE_FREQ_RATIO_SECONDARY: Final[float] = 2.3
CENTERLINE_SECONDARY_AMP_RATIO: Final[float] = 0.3
CENTERLINE_AMP_DOMAIN_RATIO: Final[float] = 0.15

# Cross-section Gaussian smoothing (sigma along stations, sigma along
# ring) -- mirrored in CaveGeometryConfig (YAML-surfaced).
CROSS_SECTION_SMOOTH_SIGMA: Final[tuple[float, float]] = (3.0, 2.0)

# Tube floor debris -- height_scale is YAML-surfaced via
# CaveGeometryConfig.floor_debris_height_scale.  smooth_sigma /
# width_ratio / width_min_pts are mesh tessellation knobs (smoothing
# kernel and floor strip resolution); kept as constants.
FLOOR_DEBRIS_HEIGHT_SCALE: Final[float] = 0.3
FLOOR_DEBRIS_SMOOTH_SIGMA: Final[float] = 1.5
FLOOR_WIDTH_RATIO: Final[float] = 0.5  # floor_pts = ring_pts * ratio
FLOOR_WIDTH_MIN_PTS: Final[int] = 8

# Surface cap noise -- both knobs YAML-surfaced via
# CaveGeometryConfig.surface_noise_*.
SURFACE_NOISE_SIGMA: Final[float] = 10.0
SURFACE_NOISE_AMPLITUDE_M: Final[float] = 2.0

# Debris cone geometry -- diameter_ratio is YAML-surfaced; the rest
# (exclusion ratios, mesh tessellation, jitter sigma) shape the
# placement footprint and discretisation rather than physical cave
# dimensions, so they stay as constants.
DEBRIS_CONE_DIAMETER_RATIO: Final[float] = 0.15  # base diameter vs tube width
DEBRIS_CONE_EXCLUSION_RATIO: Final[float] = 0.1  # half-exclusion vs tube width
DEBRIS_CONE_MAX_OFFSET_RATIO: Final[float] = 0.35
DEBRIS_CONE_RADIUS_SHRINK: Final[float] = 0.8  # base vs skylight diameter/2
DEBRIS_CONE_NOISE_SIGMA: Final[float] = 0.05
DEBRIS_CONE_RINGS: Final[int] = 12
DEBRIS_CONE_SEGMENTS: Final[int] = 24

# Skylight shaft -- separation/margin and shaft tessellation. These
# guard mesh validity (ring/segment minimums) and inter-skylight
# spacing; not surfaced to YAML because tweaking them risks producing
# degenerate meshes.
SKYLIGHT_SEPARATION_RATIO: Final[float] = 1.5
SKYLIGHT_MARGIN_EXTRA_M: Final[float] = 10.0
SKYLIGHT_SHAFT_RING_SPACING_M: Final[float] = 5.0
SKYLIGHT_SHAFT_RING_MIN: Final[int] = 10
SKYLIGHT_SHAFT_SEG_MIN: Final[int] = 16

# Breakdown blocks -- diameter cap is a physical-realism cap (Blank
# 2024 reports breakdown block sizes up to ~5 m); span/exclusion
# ratios shape the placement window inside the tube; max_attempts is
# the rejection-sampling budget for non-overlap. None are surfaced to
# YAML in v1.0 because no scenario has needed to override them.
BREAKDOWN_DIAMETER_CAP_M: Final[float] = 5.0
BREAKDOWN_FLOOR_SPAN_RATIO: Final[float] = 0.8  # shrink left/right by this
BREAKDOWN_CENTERLINE_EXCLUSION_RATIO: Final[float] = 0.1  # vs station width
BREAKDOWN_MAX_ATTEMPTS: Final[int] = 5000
