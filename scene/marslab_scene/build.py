"""Public recipe-to-scene orchestration."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import assert_never

from marslab_scene.compat.legacy_terrain import normalize_legacy_terrain
from marslab_scene.compat.profiles import CompatibilityPolicy, resolve_compatibility_policy
from marslab_scene.config.hirise import TextureOutputSizeSettings
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
from marslab_scene.layers.habitat.build import place_habitat
from marslab_scene.layers.rocks.build import place_rocks
from marslab_scene.terrain.hirise.build import HiriseBuildConfig, build_hirise_terrain
from marslab_scene.terrain.hirise.config import (
    ColorizationConfig,
    CropConfig,
    DetailVariationConfig,
    ElevationConfig,
    MastcamReferenceConfig,
    OrthomosaicConfig,
    TextureConfig,
    TextureMaterialConfig,
    TextureOutputSize,
    TextureUvConfig,
    UpscalingConfig,
    VisualEnhancementConfig,
    VisualPackagingConfig,
)
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
                    _hirise_build_config(recipe, dem, Path(raw_directory) / "terrain"),
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
            output.directory.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=".marslab-legacy-terrain-",
                dir=output.directory.parent,
            ) as raw_directory:
                terrain = normalize_legacy_terrain(
                    source,
                    output_dir=Path(raw_directory) / "terrain",
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
        case unreachable:
            assert_never(unreachable)


def _hirise_build_config(recipe: SceneRecipe, dem: Path, output: Path) -> HiriseBuildConfig:
    terrain = recipe.terrain
    texture_size = terrain.texture.output_size
    match texture_size:
        case "auto":
            resolved_size = "auto"
        case TextureOutputSizeSettings(width=width, height=height):
            resolved_size = TextureOutputSize(width=width, height=height)
        case unreachable:
            assert_never(unreachable)
    return HiriseBuildConfig(
        dem_path=dem,
        output_dir=output,
        crop=CropConfig(**terrain.crop.model_dump()),
        elevation=ElevationConfig(**terrain.elevation.model_dump()),
        visual_grid_size=terrain.mesh.visual_grid_size,
        collision_grid_size=terrain.mesh.collision_grid_size,
        texture=TextureConfig(
            enabled=terrain.texture.enabled,
            mode=terrain.texture.mode,
            path=terrain.texture.path,
            require_same_crs=terrain.texture.require_same_crs,
            allow_reprojection=terrain.texture.allow_reprojection,
            allow_non_georeferenced=terrain.texture.allow_non_georeferenced,
            non_georeferenced_policy=terrain.texture.non_georeferenced_policy,
            output_size=resolved_size,
            max_texture_size_px=terrain.texture.max_texture_size_px,
            resampling=terrain.texture.resampling,
            output_dir=terrain.texture.output_dir,
            output_name=terrain.texture.output_name,
            color_space=terrain.texture.color_space,
            channel_semantics=terrain.texture.channel_semantics,
            solid_color=terrain.texture.solid_color,
            material=TextureMaterialConfig(**terrain.texture.material.model_dump()),
            uv=TextureUvConfig(**terrain.texture.uv.model_dump()),
        ),
        appearance=VisualEnhancementConfig(
            enabled=terrain.appearance.enabled,
            mode=terrain.appearance.mode,
            orthomosaic=OrthomosaicConfig(**terrain.appearance.orthomosaic.model_dump()),
            mastcam_reference=MastcamReferenceConfig(
                **terrain.appearance.mastcam_reference.model_dump()
            ),
            colorization=ColorizationConfig(**terrain.appearance.colorization.model_dump()),
            upscaling=UpscalingConfig(**terrain.appearance.upscaling.model_dump()),
            detail_variation=DetailVariationConfig(
                **terrain.appearance.detail_variation.model_dump()
            ),
            packaging=VisualPackagingConfig(**terrain.appearance.packaging.model_dump()),
        ),
    )


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
