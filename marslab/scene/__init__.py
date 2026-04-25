"""Scene composition helpers (structures, static dressing).

Hosts logic that composes auxiliary static geometry on top of the terrain +
rover pipeline -- landers, habitat modules, solar arrays, antennas, etc.
Everything loads from pre-authored USD assets (no runtime URDF/OBJ/FBX
import — see ``reference_rover_usd_source``).
"""

from marslab.scene.structure_loader import (
    STRUCTURE_ASSET_EXTENSIONS,
    StructureAsset,
    StructureConfig,
    build_structure_asset,
    convert_mesh_to_usd,
    load_structure,
    load_structure_assets,
    load_structures,
    resolve_asset_name,
)

__all__ = [
    "STRUCTURE_ASSET_EXTENSIONS",
    "StructureAsset",
    "StructureConfig",
    "build_structure_asset",
    "convert_mesh_to_usd",
    "load_structure",
    "load_structure_assets",
    "load_structures",
    "resolve_asset_name",
]
