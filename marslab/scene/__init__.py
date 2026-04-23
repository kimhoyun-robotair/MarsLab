"""Scene composition helpers (structures, static dressing).

The ``marslab.scene`` package hosts logic that composes auxiliary
static geometry on top of the terrain + rover pipeline -- spacecraft
landers, habitat modules, solar arrays, antennas, etc.  Everything is
loaded from pre-authored USD assets (no runtime URDF/OBJ/FBX import --
see ``reference_rover_usd_source``).

P1-1 (2026-04-23) introduced :mod:`marslab.scene.structure_loader`.
"""

from marslab.scene.structure_loader import (
    StructureConfig,
    load_structure,
    load_structures,
)

__all__ = [
    "StructureConfig",
    "load_structure",
    "load_structures",
]
