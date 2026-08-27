from __future__ import annotations

from pathlib import Path

import pytest
from marslab_scene.compat.profiles import resolve_compatibility_policy
from marslab_scene.config.models import OutputSettings
from marslab_scene.contracts.layers import RockLayer
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.errors import ArtifactManifestError
from marslab_scene.usd.builder import SceneBuilder
from marslab_scene.usd.validation import validate_scene_manifest

pytestmark = [pytest.mark.contract, pytest.mark.standalone_usd]


def test_existing_output_is_preserved_by_default(
    terrain_artifact: TerrainArtifact,
    rock_layer: RockLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    output_settings.directory.mkdir()
    sentinel = output_settings.directory / "user-file"
    sentinel.write_text("preserve me", encoding="utf-8")
    builder = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
    )

    # When / Then
    with pytest.raises(FileExistsError):
        builder.build(terrain=terrain_artifact, layers=(rock_layer,))
    assert sentinel.read_text(encoding="utf-8") == "preserve me"


@pytest.mark.parametrize("unsafe_target", [Path("/"), Path.home()])
def test_unsafe_output_roots_are_rejected(
    unsafe_target: Path,
    terrain_artifact: TerrainArtifact,
    output_settings: OutputSettings,
) -> None:
    # Given
    unsafe = output_settings.model_copy(update={"directory": unsafe_target})

    # When / Then
    with pytest.raises(ValueError, match="unsafe output target"):
        SceneBuilder(unsafe, policy=resolve_compatibility_policy("canonical"))


def test_unresolved_output_variable_is_rejected(
    terrain_artifact: TerrainArtifact,
    output_settings: OutputSettings,
) -> None:
    # Given
    unsafe = output_settings.model_copy(update={"directory": Path("$MISSING/scene")})

    # When / Then
    with pytest.raises(ValueError, match="unresolved variable"):
        SceneBuilder(unsafe, policy=resolve_compatibility_policy("canonical"))


def test_failed_validation_removes_only_temporary_output(
    tmp_path: Path,
    terrain_artifact: TerrainArtifact,
    rock_layer: RockLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    terrain_artifact.stage_path.write_text("#usda 1.0\n", encoding="utf-8")
    unrelated = tmp_path / "unrelated"
    unrelated.write_text("untouched", encoding="utf-8")
    builder = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
    )

    # When / Then
    with pytest.raises(ValueError, match="terrain sublayer"):
        builder.build(terrain=terrain_artifact, layers=(rock_layer,))
    assert unrelated.read_text(encoding="utf-8") == "untouched"
    assert not output_settings.directory.exists()
    assert not tuple(output_settings.directory.parent.glob(".scene-output.tmp-*"))


def test_force_publish_retains_recoverable_sibling_backup(
    terrain_artifact: TerrainArtifact,
    rock_layer: RockLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    output_settings.directory.mkdir()
    sentinel = output_settings.directory / "user-file"
    sentinel.write_text("old output", encoding="utf-8")

    # When
    artifact = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
        force=True,
    ).build(terrain=terrain_artifact, layers=(rock_layer,))

    # Then
    assert artifact.previous_output_backup is not None
    assert (artifact.previous_output_backup / "user-file").read_text(encoding="utf-8") == (
        "old output"
    )
    assert artifact.stage_path.is_file()


def test_final_manifest_rejects_dependency_checksum_corruption(
    terrain_artifact: TerrainArtifact,
    rock_layer: RockLayer,
    output_settings: OutputSettings,
) -> None:
    # Given
    artifact = SceneBuilder(
        output_settings,
        policy=resolve_compatibility_policy("canonical"),
    ).build(terrain=terrain_artifact, layers=(rock_layer,))
    report = artifact.root_dir / "semantic-scene.json"
    report.write_text("{}\n", encoding="utf-8")

    # When / Then
    with pytest.raises(ArtifactManifestError, match="checksum mismatch"):
        validate_scene_manifest(artifact.manifest_path)
