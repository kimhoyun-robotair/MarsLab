"""Deterministic final scene composition authoring."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, assert_never, final

from pxr import Gf, Sdf, Usd, UsdGeom, Vt

from marslab_scene.assets.habitats import load_habitat_asset
from marslab_scene.assets.rocks import load_rock_asset
from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.config.models import OutputSettings
from marslab_scene.contracts.layers import HabitatLayer, RockLayer
from marslab_scene.contracts.provenance import Provenance
from marslab_scene.contracts.scene import LayerSummary, SceneArtifact
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.errors import ContractValueError, SceneBuildError
from marslab_scene.usd._manifest import (
    SceneManifestInputs,
    validate_scene_manifest,
    write_scene_manifest,
)
from marslab_scene.usd.packaging import (
    package_usdz,
    prepare_publish_paths,
    publish_directory,
    resolve_safe_output_target,
    validate_relocated_package,
)
from marslab_scene.usd.paths import relative_reference
from marslab_scene.usd.validation import SceneValidationContract, validate_scene_stage

SceneLayer: TypeAlias = RockLayer | HabitatLayer


@dataclass(frozen=True, slots=True)
class _ResolvedLayers:
    rocks: RockLayer | None
    habitat: HabitatLayer | None


@final
class SceneBuilder:
    """Sole author of the deterministic final scene composition stage."""

    def __init__(
        self,
        output: OutputSettings,
        *,
        policy: CompatibilityPolicy,
        force: bool = False,
        output_override_applied: bool = False,
    ) -> None:
        self._output = output
        self._policy = policy
        self._force = force
        self._output_override_applied = output_override_applied
        self._target = resolve_safe_output_target(output.directory)

    def build(
        self,
        *,
        terrain: TerrainArtifact,
        layers: tuple[SceneLayer, ...],
    ) -> SceneArtifact:
        """Validate contracts, author in isolation, and atomically publish."""
        resolved = _resolve_layers(layers)
        _require_matching_profile(terrain, self._policy)
        paths = prepare_publish_paths(self._target, force=self._force)
        published = False
        try:
            _copy_contract_roots(paths.temporary, terrain, resolved)
            stage_path = paths.temporary / self._output.stage
            self._author_stage(stage_path, terrain, resolved)
            validation_contract = SceneValidationContract(
                terrain_sublayer=f"terrain/{terrain.stage_path.relative_to(terrain.root_dir).as_posix()}",
                rock_count=(
                    None if resolved.rocks is None else len(resolved.rocks.positions_local_m)
                ),
                habitat_enabled=resolved.habitat is not None,
            )
            report = validate_scene_stage(stage_path, validation_contract)
            report_path = paths.temporary / "semantic-scene.json"
            _ = report_path.write_text(
                json.dumps(report.as_mapping(), sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            package_path = paths.temporary / self._output.runtime_package
            package_usdz(stage_path, package_path)
            validate_relocated_package(package_path)
            manifest_path = paths.temporary / self._output.manifest
            write_scene_manifest(
                manifest_path,
                SceneManifestInputs(
                    stage_path=stage_path,
                    package_path=package_path,
                    report_path=report_path,
                    terrain=terrain,
                    rocks=resolved.rocks,
                    habitat=resolved.habitat,
                    policy=self._policy,
                    output_override_applied=self._output_override_applied,
                ),
            )
            _ = validate_scene_manifest(manifest_path)
            backup = publish_directory(paths, force=self._force)
            published = True
            return _scene_artifact(
                target=paths.target,
                output=self._output,
                terrain=terrain,
                layers=resolved,
                backup=backup,
            )
        finally:
            if not published and paths.temporary.exists():
                shutil.rmtree(paths.temporary)

    def _author_stage(
        self,
        stage_path: Path,
        terrain: TerrainArtifact,
        layers: _ResolvedLayers,
    ) -> None:
        stage = Usd.Stage.CreateNew(str(stage_path))
        if not stage:
            detail = f"could not create final stage: {stage_path.name}"
            raise SceneBuildError(detail)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        world = UsdGeom.Xform.Define(stage, "/World")
        stage.SetDefaultPrim(world.GetPrim())
        terrain_target = (
            stage_path.parent / "terrain" / terrain.stage_path.relative_to(terrain.root_dir)
        )
        stage.GetRootLayer().subLayerPaths = [
            relative_reference(stage_path.parent, terrain_target, root=stage_path.parent)
        ]
        UsdGeom.Xform.Define(stage, "/World/MarsTerrain")
        if layers.rocks is not None:
            _author_rocks(stage, layers.rocks)
        if layers.habitat is not None:
            _author_habitat(stage, layers.habitat)
        stage.GetRootLayer().Save()


def _resolve_layers(layers: tuple[SceneLayer, ...]) -> _ResolvedLayers:
    rocks: RockLayer | None = None
    habitat: HabitatLayer | None = None
    for layer in layers:
        match layer:
            case RockLayer():
                if rocks is not None:
                    raise ContractValueError("duplicate rock layer")
                rocks = layer
            case HabitatLayer():
                if habitat is not None:
                    raise ContractValueError("duplicate habitat layer")
                habitat = layer
            case unreachable:
                assert_never(unreachable)
    return _ResolvedLayers(rocks=rocks, habitat=habitat)


def _require_matching_profile(terrain: TerrainArtifact, policy: CompatibilityPolicy) -> None:
    frame = terrain.coordinate_frame
    if frame is not None and frame.compatibility_profile != policy.name:
        raise ContractValueError("terrain compatibility profile does not match SceneBuilder policy")


def _copy_contract_roots(
    target: Path,
    terrain: TerrainArtifact,
    layers: _ResolvedLayers,
) -> None:
    _ = shutil.copytree(terrain.root_dir, target / "terrain")
    if layers.rocks is not None:
        _ = load_rock_asset(layers.rocks.asset_manifest)
        _ = shutil.copytree(layers.rocks.asset_manifest.parent, target / "rocks")
    if layers.habitat is not None:
        _ = load_habitat_asset(layers.habitat.asset_manifest)
        _ = shutil.copytree(layers.habitat.asset_manifest.parent, target / "habitats")


def _author_rocks(stage: Usd.Stage, layer: RockLayer) -> None:
    asset = load_rock_asset(layer.asset_manifest)
    library = UsdGeom.Xform.Define(stage, "/World/RockLib")
    _ = (
        library.GetPrim()
        .GetReferences()
        .AddReference(
            relative_reference(
                Path(stage.GetRootLayer().realPath).parent,
                Path(stage.GetRootLayer().realPath).parent
                / "rocks"
                / asset.stage_path.relative_to(asset.manifest_path.parent),
                root=Path(stage.GetRootLayer().realPath).parent,
            )
        )
    )
    library.CreateVisibilityAttr(UsdGeom.Tokens.invisible)
    UsdGeom.Xform.Define(stage, "/World/Rocks")
    instancer = UsdGeom.PointInstancer.Define(stage, "/World/Rocks/Instancer")
    targets = [Sdf.Path(f"/World/RockLib/RockPrototypes/{item}") for item in asset.prototype_ids]
    instancer.CreatePrototypesRel().SetTargets(targets)
    instancer.CreatePositionsAttr(
        Vt.Vec3fArray([Gf.Vec3f(*map(float, item)) for item in layer.positions_local_m])
    )
    instancer.CreateProtoIndicesAttr(Vt.IntArray([int(item) for item in layer.prototype_indices]))
    instancer.CreateScalesAttr(Vt.Vec3fArray([Gf.Vec3f(float(item)) for item in layer.scales]))
    instancer.CreateOrientationsAttr(
        Vt.QuathArray(
            [
                Gf.Quath(float(item[0]), Gf.Vec3h(*map(float, item[1:])))
                for item in layer.orientations_wxyz
            ]
        )
    )


def _author_habitat(stage: Usd.Stage, layer: HabitatLayer) -> None:
    asset = load_habitat_asset(layer.asset_manifest)
    habitat = UsdGeom.Xform.Define(stage, "/World/Habitat")
    _ = (
        habitat.GetPrim()
        .GetReferences()
        .AddReference(
            relative_reference(
                Path(stage.GetRootLayer().realPath).parent,
                Path(stage.GetRootLayer().realPath).parent
                / "habitats"
                / asset.stage_path.relative_to(asset.manifest_path.parent),
                root=Path(stage.GetRootLayer().realPath).parent,
            )
        )
    )
    habitat.AddTranslateOp().Set(Gf.Vec3d(*layer.translation_local_m))
    rotation = layer.rotation_wxyz
    habitat.AddOrientOp().Set(Gf.Quatf(rotation[0], Gf.Vec3f(*rotation[1:])))


def _scene_artifact(
    *,
    target: Path,
    output: OutputSettings,
    terrain: TerrainArtifact,
    layers: _ResolvedLayers,
    backup: Path | None,
) -> SceneArtifact:
    summaries = tuple(
        [LayerSummary(kind="rocks", count=len(layers.rocks.positions_local_m))]
        if layers.rocks is not None
        else []
    ) + tuple([LayerSummary(kind="habitat", count=1)] if layers.habitat is not None else [])
    return SceneArtifact(
        root_dir=target,
        stage_path=target / output.stage,
        runtime_package_path=target / output.runtime_package,
        manifest_path=target / output.manifest,
        terrain=terrain,
        layer_summaries=summaries,
        provenance=Provenance(
            producer="marslab_scene",
            marslab_revision=terrain.provenance.marslab_revision,
            marslab_utils_revision=terrain.provenance.marslab_utils_revision,
            source_files=(terrain.manifest_path,),
        ),
        previous_output_backup=backup,
    )
