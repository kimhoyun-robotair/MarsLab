"""Scene composition helpers (structures, static dressing).

Hosts logic that composes auxiliary static geometry on top of the terrain +
rover pipeline -- landers, habitat modules, solar arrays, antennas, etc.
Everything loads from pre-authored USD assets (no runtime URDF/OBJ/FBX
import — see ``reference_rover_usd_source``).
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
