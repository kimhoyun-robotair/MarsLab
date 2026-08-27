"""MarsLab offline scene construction contracts."""

from marslab_scene.compat import CompatibilityPolicy, resolve_compatibility_policy
from marslab_scene.config import SceneRecipe, load_scene_config
from marslab_scene.contracts import (
    FlatnessReport,
    HabitatAssetDescriptor,
    HabitatLayer,
    LayerSummary,
    RockAssetDescriptor,
    RockLayer,
    RockPlacementStats,
    SceneArtifact,
    TerrainAnchor,
    TerrainArtifact,
    load_terrain_artifact,
)
from marslab_scene.errors import (
    ArtifactManifestError,
    CompatibilityProfileMismatch,
    SceneConfigError,
    UnknownCompatibilityProfileError,
)
from marslab_scene.terrain import TerrainFrame
from marslab_scene.usd.builder import SceneBuilder

__all__ = [
    "ArtifactManifestError",
    "CompatibilityPolicy",
    "CompatibilityProfileMismatch",
    "FlatnessReport",
    "HabitatAssetDescriptor",
    "HabitatLayer",
    "LayerSummary",
    "RockAssetDescriptor",
    "RockLayer",
    "RockPlacementStats",
    "SceneArtifact",
    "SceneBuilder",
    "SceneConfigError",
    "SceneRecipe",
    "TerrainAnchor",
    "TerrainArtifact",
    "TerrainFrame",
    "UnknownCompatibilityProfileError",
    "load_scene_config",
    "load_terrain_artifact",
    "resolve_compatibility_policy",
]
