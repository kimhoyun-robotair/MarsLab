"""Cross-stage artifact and layer contracts."""

from marslab_scene.contracts.assets import HabitatAssetDescriptor, RockAssetDescriptor
from marslab_scene.contracts.layers import (
    FlatnessReport,
    HabitatLayer,
    RockLayer,
    RockPlacementStats,
    TerrainAnchor,
)
from marslab_scene.contracts.scene import LayerSummary, SceneArtifact
from marslab_scene.contracts.terrain import TerrainArtifact, load_terrain_artifact

__all__ = [
    "FlatnessReport",
    "HabitatAssetDescriptor",
    "HabitatLayer",
    "LayerSummary",
    "RockAssetDescriptor",
    "RockLayer",
    "RockPlacementStats",
    "SceneArtifact",
    "TerrainAnchor",
    "TerrainArtifact",
    "load_terrain_artifact",
]
