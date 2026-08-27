"""USD asset-token and containment operations."""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath

from marslab_scene.errors import PathContractError


def resolve_local_reference(
    root: Path,
    owner: Path,
    token: str,
    *,
    require_file: bool = True,
) -> Path:
    """Resolve one local USD token without permitting a root escape."""
    if "://" in token or token.startswith("file:"):
        raise PathContractError(value=token, detail="remote URI is not a local USD reference")
    raw = Path(token)
    if raw.is_absolute():
        raise PathContractError(value=token, detail="absolute USD reference is forbidden")
    resolved_root = root.resolve()
    resolved = (owner.resolve() / raw).resolve()
    try:
        _ = resolved.relative_to(resolved_root)
    except ValueError:
        raise PathContractError(value=token, detail="USD reference escapes artifact root") from None
    if require_file and not resolved.is_file():
        raise PathContractError(value=token, detail="USD reference is not a regular file")
    return resolved


def relative_reference(owner: Path, target: Path, *, root: Path) -> str:
    """Author a POSIX reference between two files contained by one root."""
    resolved_root = root.resolve()
    resolved_owner = owner.resolve()
    resolved_target = target.resolve()
    for path in (resolved_owner, resolved_target):
        try:
            _ = path.relative_to(resolved_root)
        except ValueError:
            raise PathContractError(value=path, detail="USD path escapes artifact root") from None
    token = PurePosixPath(os.path.relpath(resolved_target, resolved_owner)).as_posix()
    if token.startswith("/"):
        raise PathContractError(value=token, detail="expected a relative USD reference")
    return token
