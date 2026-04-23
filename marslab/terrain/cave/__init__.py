"""Cave submodule package: geometry, mesh, features, breakdown.

Introduced in R5 (2026-04-23) to split the previously 884-LOC
``marslab/terrain/cave_generator.py`` into focused submodules while
preserving the public ``generate_cave_mesh`` entry point at the
original import path. Consumers that already import from
``marslab.terrain.cave_generator`` keep working unchanged; new code
may reach directly into the submodules below.

Submodules:
    geometry  -- centerline, cross-section, tangent frames (pure math)
    mesh      -- trimesh ring-stitching for tube/floor/shaft/surface
    features  -- skylight placement, debris cone construction
    breakdown -- lognormal rejection-sampled breakdown blocks
    _constants -- private literal defaults consumed when YAML omits
                  the optional ``geometry`` block
"""

from marslab.terrain.cave.breakdown import generate_breakdown_positions
from marslab.terrain.cave.features import (
    build_debris_cone,
    compute_skylight_positions,
)
from marslab.terrain.cave.geometry import (
    build_centerline,
    build_cross_sections,
    tangent_frames,
)
from marslab.terrain.cave.mesh import (
    build_skylight_shaft,
    build_surface_cap,
    build_tube_floor,
    build_tube_shell,
)

__all__ = [
    "build_centerline",
    "build_cross_sections",
    "build_debris_cone",
    "build_skylight_shaft",
    "build_surface_cap",
    "build_tube_floor",
    "build_tube_shell",
    "compute_skylight_positions",
    "generate_breakdown_positions",
    "tangent_frames",
]
