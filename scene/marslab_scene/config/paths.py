"""Recipe and manifest path contracts."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from marslab_scene.errors import PathContractError


def relative_local_path(value: Path | str) -> Path:
    """Parse a recipe-relative local path."""
    raw = str(value)
    path = Path(raw)
    if path.is_absolute() or "://" in raw:
        raise PathContractError(value=value, detail="expected a relative local path")
    if not raw or raw == ".":
        raise PathContractError(value=value, detail="expected a non-empty path")
    return path


def relative_posix_path(value: Path | str) -> Path:
    """Parse a root-relative manifest POSIX path."""
    raw = str(value)
    posix_path = PurePosixPath(raw)
    if Path(raw).is_absolute() or posix_path.is_absolute() or "://" in raw or "\\" in raw:
        raise PathContractError(value=value, detail="expected a relative POSIX path")
    if not raw or raw == "." or ".." in posix_path.parts:
        raise PathContractError(value=value, detail="expected a root-relative POSIX path")
    return Path(posix_path)


def resolve_existing_file(anchor: Path, value: Path | str) -> Path:
    """Resolve a required recipe input file."""
    path = (anchor / relative_local_path(value)).resolve()
    if not path.is_file():
        raise PathContractError(value=value, detail="required file does not exist")
    return path


def resolve_manifest_file(root: Path, value: Path | str) -> Path:
    """Resolve a contained manifest file."""
    relative = relative_posix_path(value)
    path = (root / relative).resolve()
    try:
        _ = path.relative_to(root.resolve())
    except ValueError:
        raise PathContractError(value=value, detail="path escapes manifest root") from None
    if not path.is_file():
        raise PathContractError(value=value, detail="required file does not exist")
    return path
