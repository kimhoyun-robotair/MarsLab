"""Public scene recipe loader."""

from __future__ import annotations

from pathlib import Path
from typing import assert_never

import yaml
from pydantic import JsonValue, ValidationError

from marslab_scene.compat.profiles import resolve_compatibility_policy
from marslab_scene.config.json_value import JSON_VALUE_ADAPTER
from marslab_scene.config.models import (
    ArtifactSource,
    HabitatDisabled,
    HabitatEnabled,
    HiriseSource,
    LegacyArtifactSource,
    RocksDisabled,
    RocksEnabled,
    SceneRecipe,
)
from marslab_scene.config.paths import resolve_existing_file
from marslab_scene.errors import PathContractError, SceneConfigError


def _load_yaml(path: Path) -> JsonValue:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise SceneConfigError(path=path, detail=str(error)) from error
    return JSON_VALUE_ADAPTER.validate_python(raw)


def load_scene_config(path: Path | str) -> SceneRecipe:
    """Load and resolve a strict scene recipe."""
    config_path = Path(path).expanduser().resolve()
    try:
        recipe = SceneRecipe.model_validate(_load_yaml(config_path))
        _ = resolve_compatibility_policy(recipe.scene.compatibility_profile)
        anchor = config_path.parent
        source = recipe.terrain.source
        match source:
            case HiriseSource(dem=dem):
                resolved_source = source.model_copy(
                    update={"dem": resolve_existing_file(anchor, dem)}
                )
            case ArtifactSource(manifest=manifest):
                resolved_source = source.model_copy(
                    update={"manifest": resolve_existing_file(anchor, manifest)}
                )
            case LegacyArtifactSource():
                resolved_source = source
            case unreachable:
                assert_never(unreachable)
        rocks = recipe.layers.rocks
        match rocks:
            case RocksEnabled(asset=asset, placements=placements):
                resolved_rocks = rocks.model_copy(
                    update={
                        "asset": resolve_existing_file(anchor, asset),
                        "placements": resolve_existing_file(anchor, placements),
                    }
                )
            case RocksDisabled():
                resolved_rocks = rocks
            case unreachable:
                assert_never(unreachable)
        habitat = recipe.layers.habitat
        match habitat:
            case HabitatEnabled(asset=asset):
                resolved_habitat = habitat.model_copy(
                    update={"asset": resolve_existing_file(anchor, asset)}
                )
            case HabitatDisabled():
                resolved_habitat = habitat
            case unreachable:
                assert_never(unreachable)
        return recipe.model_copy(
            update={
                "terrain": recipe.terrain.model_copy(update={"source": resolved_source}),
                "layers": recipe.layers.model_copy(
                    update={"rocks": resolved_rocks, "habitat": resolved_habitat}
                ),
                "output": recipe.output.model_copy(
                    update={"directory": (anchor / recipe.output.directory).resolve()}
                ),
            }
        )
    except (ValidationError, PathContractError) as error:
        raise SceneConfigError(path=config_path, detail=str(error)) from error
