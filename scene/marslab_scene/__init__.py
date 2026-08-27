"""MarsLab offline scene construction contracts."""

from pathlib import Path

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
    "SceneConfigError",
    "SceneRecipe",
    "TerrainAnchor",
    "TerrainArtifact",
    "TerrainFrame",
    "UnknownCompatibilityProfileError",
    "build_scene",
    "load_scene_config",
    "load_terrain_artifact",
    "resolve_compatibility_policy",
]


def build_scene(
    config_path: Path | str,
    *,
    output_dir: Path | None = None,
    force: bool = False,
) -> SceneArtifact:
    """Build one recipe without importing USD bindings before the call boundary."""
    from marslab_scene.build import build_scene as execute_build  # noqa: PLC0415

    return execute_build(config_path, output_dir=output_dir, force=force)
