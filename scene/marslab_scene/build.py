"""Public recipe-to-scene orchestration."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from marslab_scene.compat.profiles import CompatibilityPolicy, resolve_compatibility_policy
from marslab_scene.config.loader import load_scene_config
from marslab_scene.config.models import (
    ArtifactSource,
    HabitatDisabled,
    HabitatEnabled,
    HiriseSource,
    LegacyArtifactSource,
    OutputSettings,
    RocksDisabled,
    RocksEnabled,
    SceneRecipe,
)
from marslab_scene.contracts.scene import SceneArtifact
from marslab_scene.contracts.terrain import TerrainArtifact, load_terrain_artifact
from marslab_scene.errors import SceneFeatureUnavailable
from marslab_scene.layers.habitat.build import place_habitat
from marslab_scene.layers.rocks.build import place_rocks
from marslab_scene.terrain.hirise.build import HiriseBuildConfig, build_hirise_terrain
from marslab_scene.usd.builder import SceneBuilder, SceneLayer


@dataclass(frozen=True, slots=True)
class _BuildOptions:
    output: OutputSettings
    policy: CompatibilityPolicy
    force: bool
    output_override_applied: bool


def build_scene(
    config_path: Path | str,
    *,
    output_dir: Path | None = None,
    force: bool = False,
) -> SceneArtifact:
    """Build, validate, package, and atomically publish one scene recipe."""
    recipe = load_scene_config(config_path)
    policy = resolve_compatibility_policy(recipe.scene.compatibility_profile)
    output = recipe.output
    override_applied = output_dir is not None
    if output_dir is not None:
        output = output.model_copy(update={"directory": output_dir.expanduser().resolve()})

    source = recipe.terrain.source
    match source:
        case ArtifactSource(manifest=manifest):
            terrain = load_terrain_artifact(manifest, profile=policy.name)
            return _compose_scene(
                terrain,
                recipe,
                _BuildOptions(
                    output=output,
                    policy=policy,
                    force=force,
                    output_override_applied=override_applied,
                ),
            )
        case HiriseSource(dem=dem):
            output.directory.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".marslab-terrain-",
                dir=output.directory.parent,
            ) as raw_directory:
                terrain = build_hirise_terrain(
                    HiriseBuildConfig(dem_path=dem, output_dir=Path(raw_directory) / "terrain"),
                    policy=policy,
                )
                return _compose_scene(
                    terrain,
                    recipe,
                    _BuildOptions(
                        output=output,
                        policy=policy,
                        force=force,
                        output_override_applied=override_applied,
                    ),
                )
        case LegacyArtifactSource():
            raise SceneFeatureUnavailable(feature="legacy_artifact normalizer")
        case unreachable:
            assert_never(unreachable)


def _compose_scene(
    terrain: TerrainArtifact,
    recipe: SceneRecipe,
    options: _BuildOptions,
) -> SceneArtifact:
    layers: list[SceneLayer] = []
    rocks_config = recipe.layers.rocks
    match rocks_config:
        case RocksEnabled():
            layers.append(place_rocks(terrain, rocks_config, policy=options.policy))
        case RocksDisabled():
            pass
        case unreachable:
            assert_never(unreachable)
    habitat_config = recipe.layers.habitat
    match habitat_config:
        case HabitatEnabled():
            layers.append(place_habitat(terrain, habitat_config, policy=options.policy))
        case HabitatDisabled():
            pass
        case unreachable:
            assert_never(unreachable)
    return SceneBuilder(
        options.output,
        policy=options.policy,
        force=options.force,
        output_override_applied=options.output_override_applied,
    ).build(terrain=terrain, layers=tuple(layers))
