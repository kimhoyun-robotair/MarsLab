"""Cave subpackage: geometry, mesh, features, breakdown, orchestrator, USD builder.

R5 (2026-04-23) split the previously 884-LOC ``cave_generator.py`` into
four focused submodules. The 2026-04-26 follow-up moved the thin
orchestrator and the USD builder into this same subpackage so all
cave-related code lives under one folder:

* ``orchestrator`` (was top-level ``cave_generator.py``) -- thin numpy +
  trimesh assembly entry point :func:`generate_cave_mesh`.
* ``usd_builder`` (was top-level ``cave_mesh_builder.py``) -- Isaac Sim
  USD prim creation :func:`build_cave_scene`.

Submodules:
    geometry     -- centerline, cross-section, tangent frames (pure math)
    mesh         -- trimesh ring-stitching for tube/floor/shaft/surface
    features     -- skylight placement, debris cone construction
    breakdown    -- lognormal rejection-sampled breakdown blocks
    orchestrator -- thin generate_cave_mesh entry point (Layer 1)
    usd_builder  -- USD prim creation for Isaac Sim (Layer 2)
    _constants   -- private literal defaults consumed when YAML omits
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
from marslab.terrain.cave.orchestrator import generate_cave_mesh

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
    "generate_cave_mesh",
    "tangent_frames",
]
