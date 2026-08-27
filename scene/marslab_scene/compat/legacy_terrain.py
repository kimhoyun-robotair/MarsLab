"""Fail-closed conversion of explicitly described legacy terrain artifacts."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from pxr import Sdf, Usd, UsdUtils

from marslab_scene.compat.legacy_manifest import (
    LegacyManifestInputs,
    load_legacy_frame,
    write_legacy_manifest,
)
from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.config.models import LegacyArtifactSource, LegacyExternalDependency
from marslab_scene.contracts.terrain import TerrainArtifact, load_terrain_artifact
from marslab_scene.errors import LegacyTerrainNormalizationError, PathContractError
from marslab_scene.usd.paths import relative_reference, resolve_local_reference


@dataclass(frozen=True, slots=True)
class _DependencyCopy:
    source: Path
    destination: Path
    allowlist_key: tuple[str, str] | None


@dataclass(frozen=True, slots=True)
class _NormalizationContext:
    root: Path
    output_root: Path
    entries: dict[tuple[str, str], LegacyExternalDependency]


@dataclass(frozen=True, slots=True)
class _LayerRewriteResult:
    destination: Path
    nested_layers: tuple[tuple[Path, Path], ...]
    used_allowlist: frozenset[tuple[str, str]]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _contained_entrypoint(root: Path, relative: Path) -> Path:
    lexical = root / relative
    if lexical.is_symlink():
        detail = f"entrypoint is a symlink: {relative}"
        raise LegacyTerrainNormalizationError(detail)
    try:
        path = resolve_local_reference(root, root, relative.as_posix())
    except PathContractError as error:
        raise LegacyTerrainNormalizationError(str(error)) from error
    return path


def _allowlist(
    dependencies: tuple[LegacyExternalDependency, ...],
) -> dict[tuple[str, str], LegacyExternalDependency]:
    entries: dict[tuple[str, str], LegacyExternalDependency] = {}
    for dependency in dependencies:
        key = (dependency.owner_layer.as_posix(), dependency.authored_path_sha256)
        if key in entries:
            raise LegacyTerrainNormalizationError("duplicate owner/token allowlist entry")
        entries[key] = dependency
    return entries


def _external_copy(
    owner_relative: Path,
    token: str,
    entries: dict[tuple[str, str], LegacyExternalDependency],
    output_root: Path,
) -> _DependencyCopy:
    token_hash = "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()
    entry = entries.get((owner_relative.as_posix(), token_hash))
    if entry is None:
        detail = f"external dependency is absent from exact owner/token allowlist: {owner_relative}"
        raise LegacyTerrainNormalizationError(detail)
    if entry.source.is_symlink():
        raise LegacyTerrainNormalizationError(
            "allowlisted replacement source is not a regular file"
        )
    source = entry.source.resolve()
    if not source.is_file():
        raise LegacyTerrainNormalizationError(
            "allowlisted replacement source is not a regular file"
        )
    if _sha256(source) != entry.sha256.removeprefix("sha256:"):
        raise LegacyTerrainNormalizationError("allowlisted replacement digest mismatch")
    destination = (output_root / entry.destination).resolve()
    try:
        _ = destination.relative_to(output_root.resolve())
    except ValueError:
        raise LegacyTerrainNormalizationError(
            "allowlisted destination escapes normalized root"
        ) from None
    return _DependencyCopy(
        source=source,
        destination=destination,
        allowlist_key=(owner_relative.as_posix(), token_hash),
    )


def _dependency_copy(
    context: _NormalizationContext,
    owner: Path,
    owner_relative: Path,
    token: str,
) -> _DependencyCopy:
    if "://" in token or token.startswith("file:"):
        raise LegacyTerrainNormalizationError("remote URI dependency is forbidden")
    lexical = owner.parent / token
    if lexical.is_symlink():
        return _external_copy(
            owner_relative,
            token,
            context.entries,
            context.output_root,
        )
    try:
        source = resolve_local_reference(context.root, owner.parent, token)
    except PathContractError:
        return _external_copy(
            owner_relative,
            token,
            context.entries,
            context.output_root,
        )
    relative = source.relative_to(context.root.resolve())
    return _DependencyCopy(
        source=source,
        destination=context.output_root / relative,
        allowlist_key=None,
    )


def _copy_layer_graph(
    root: Path,
    root_layer: Path,
    output_root: Path,
    entries: dict[tuple[str, str], LegacyExternalDependency],
) -> tuple[Path, ...]:
    context = _NormalizationContext(root=root, output_root=output_root, entries=entries)
    pending = [(root_layer, root_layer.relative_to(root))]
    copied: dict[Path, Path] = {}
    used_allowlist: set[tuple[str, str]] = set()
    while pending:
        source_layer, source_relative = pending.pop()
        if source_layer in copied:
            continue
        result = _rewrite_layer(context, source_layer, source_relative)
        copied[source_layer] = result.destination
        pending.extend(result.nested_layers)
        used_allowlist.update(result.used_allowlist)
    if used_allowlist != set(entries):
        raise LegacyTerrainNormalizationError(
            "legacy external dependency allowlist has unused entry"
        )
    return tuple(copied.values())


def _rewrite_layer(
    context: _NormalizationContext,
    source_layer: Path,
    source_relative: Path,
) -> _LayerRewriteResult:
    destination_layer = context.output_root / source_relative
    destination_layer.parent.mkdir(parents=True, exist_ok=True)
    _ = shutil.copy2(source_layer, destination_layer)
    source_sdf = Sdf.Layer.FindOrOpen(str(source_layer))
    destination_sdf = Sdf.Layer.FindOrOpen(str(destination_layer))
    if not source_sdf or not destination_sdf:
        detail = f"USD layer cannot be opened: {source_relative}"
        raise LegacyTerrainNormalizationError(detail)
    asset_attributes = tuple(_asset_attributes(source_sdf))
    reference_tokens = tuple(source_sdf.GetExternalReferences())
    attribute_tokens = tuple(attribute.default.path for attribute in asset_attributes)
    authored_tokens = (*reference_tokens, *attribute_tokens)
    if len(authored_tokens) != len(set(authored_tokens)):
        raise LegacyTerrainNormalizationError("owner layer has ambiguous duplicate asset token")
    nested_layers: list[tuple[Path, Path]] = []
    used_allowlist: set[tuple[str, str]] = set()
    for token in authored_tokens:
        dependency = _dependency_copy(context, source_layer, source_relative, token)
        if dependency.allowlist_key is not None:
            used_allowlist.add(dependency.allowlist_key)
        dependency.destination.parent.mkdir(parents=True, exist_ok=True)
        dependency_destination = _materialize_dependency(
            context,
            dependency,
            nested_layers,
        )
        replacement = relative_reference(
            destination_layer.parent,
            dependency_destination,
            root=context.output_root,
        )
        if token in reference_tokens:
            _ = destination_sdf.UpdateExternalReference(token, replacement)
        for attribute in _asset_attributes(destination_sdf):
            if attribute.default.path == token:
                attribute.default = Sdf.AssetPath(replacement)
    destination_sdf.Save()
    return _LayerRewriteResult(
        destination=destination_layer,
        nested_layers=tuple(nested_layers),
        used_allowlist=frozenset(used_allowlist),
    )


def _materialize_dependency(
    context: _NormalizationContext,
    dependency: _DependencyCopy,
    nested_layers: list[tuple[Path, Path]],
) -> Path:
    if dependency.source.suffix.lower() not in {".usd", ".usda", ".usdc"}:
        _ = shutil.copy2(dependency.source, dependency.destination)
        return dependency.destination
    destination = dependency.destination
    if dependency.source.is_relative_to(context.root):
        destination = context.output_root / dependency.source.relative_to(context.root)
    nested_layers.append((dependency.source, destination.relative_to(context.output_root)))
    return destination


def _asset_attributes(layer: Sdf.Layer) -> Iterator[Sdf.AttributeSpec]:
    pending = list(layer.rootPrims)
    while pending:
        prim = pending.pop()
        pending.extend(prim.nameChildren.values())
        for attribute in prim.attributes.values():
            if isinstance(attribute.default, Sdf.AssetPath) and attribute.default.path:
                yield attribute


def normalize_legacy_terrain(
    source: LegacyArtifactSource,
    *,
    output_dir: Path,
    policy: CompatibilityPolicy,
) -> TerrainArtifact:
    """Create a schema-v1 artifact without mutating or discovering the legacy root."""
    root = source.root.resolve()
    if not root.is_dir():
        raise LegacyTerrainNormalizationError("legacy root is not a directory")
    if output_dir.exists():
        raise LegacyTerrainNormalizationError("normalized output already exists")
    stage = _contained_entrypoint(root, source.stage)
    dem = _contained_entrypoint(root, source.dem)
    metadata_path = _contained_entrypoint(root, source.metadata)
    output_dir.mkdir(parents=True)
    entries = _allowlist(source.external_dependencies)
    _ = _copy_layer_graph(root, stage, output_dir, entries)
    normalized_dem = output_dir / source.dem
    normalized_metadata = output_dir / source.metadata
    normalized_dem.parent.mkdir(parents=True, exist_ok=True)
    normalized_metadata.parent.mkdir(parents=True, exist_ok=True)
    _ = shutil.copy2(dem, normalized_dem)
    _ = shutil.copy2(metadata_path, normalized_metadata)
    frame = load_legacy_frame(normalized_dem, metadata_path, policy)
    stage_path = output_dir / source.stage
    opened = Usd.Stage.Open(str(stage_path))
    if not opened:
        raise LegacyTerrainNormalizationError("normalized USD stage cannot be opened")
    _, _, unresolved = UsdUtils.ComputeAllDependencies(str(stage_path))
    if unresolved:
        detail = f"normalized USD has unresolved dependencies: {unresolved}"
        raise LegacyTerrainNormalizationError(detail)
    manifest_path = write_legacy_manifest(
        LegacyManifestInputs(output_dir=output_dir, source=source, frame=frame)
    )
    return load_terrain_artifact(manifest_path, profile=policy.name)
