"""Atomic output publication and relocatable USDZ packaging."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pxr import Usd, UsdUtils

from marslab_scene.errors import ContractValueError, SceneBuildError


@dataclass(frozen=True, slots=True)
class PublishPaths:
    target: Path
    temporary: Path


def prepare_publish_paths(target: Path, *, force: bool) -> PublishPaths:
    """Allocate a same-filesystem sibling directory for an isolated build."""
    resolved = resolve_safe_output_target(target)
    if resolved.exists() and not force:
        raise FileExistsError(resolved)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(prefix=f".{resolved.name}.tmp-", dir=resolved.parent)
    ).resolve()
    return PublishPaths(target=resolved, temporary=temporary)


def resolve_safe_output_target(target: Path) -> Path:
    """Resolve and reject filesystem roots that must never be build targets."""
    resolved = target.expanduser().resolve()
    repository_root = Path(__file__).resolve().parents[3]
    if resolved in {Path("/"), Path.home().resolve(), repository_root}:
        detail = f"unsafe output target: {resolved}"
        raise ContractValueError(detail)
    if any("$" in part for part in resolved.parts):
        raise ContractValueError("unsafe output target contains an unresolved variable")
    return resolved


def package_usdz(stage_path: Path, package_path: Path) -> None:
    """Package a composed stage and its dependency closure as USDZ."""
    result = UsdUtils.CreateNewUsdzPackage(
        str(stage_path),
        str(package_path),
    )
    if not result or not package_path.is_file():
        detail = f"could not package runtime USDZ: {package_path.name}"
        raise SceneBuildError(detail)


def validate_relocated_package(package_path: Path) -> None:
    """Open a package copy in an empty directory and require dependency closure."""
    with tempfile.TemporaryDirectory(
        prefix=".marslab-usdz-check-",
        dir=package_path.parent.parent,
    ) as raw_directory:
        relocated = Path(raw_directory) / package_path.name
        _ = shutil.copy2(package_path, relocated)
        stage = Usd.Stage.Open(str(relocated))
        if not stage:
            raise SceneBuildError("relocated runtime USDZ cannot be opened")
        _, _, unresolved = UsdUtils.ComputeAllDependencies(str(relocated))
        if unresolved:
            detail = f"relocated runtime USDZ has unresolved dependencies: {sorted(unresolved)}"
            raise SceneBuildError(detail)


def publish_directory(paths: PublishPaths, *, force: bool) -> Path | None:
    """Atomically publish a validated directory and retain forced-output backup."""
    backup: Path | None = None
    if paths.target.exists():
        if not force:
            raise FileExistsError(paths.target)
        backup = _available_backup_path(paths.target)
        _ = paths.target.rename(backup)
    try:
        _ = paths.temporary.replace(paths.target)
    except OSError:
        if backup is not None:
            _ = backup.rename(paths.target)
        raise
    return backup


def _available_backup_path(target: Path) -> Path:
    index = 1
    while True:
        candidate = target.with_name(f".{target.name}.backup-{index}")
        if not candidate.exists():
            return candidate
        index += 1
