"""Runtime artifact filesystem invariants."""

from __future__ import annotations

from pathlib import Path

from marslab_scene.errors import ContractValueError


def require_artifact_file(root: Path, path: Path) -> None:
    """Require a regular file contained by an artifact root."""
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        detail = f"artifact root directory does not exist: {root}"
        raise ContractValueError(detail)
    resolved_path = path.resolve()
    try:
        _ = resolved_path.relative_to(resolved_root)
    except ValueError:
        detail = f"artifact file escapes root directory: {path}"
        raise ContractValueError(detail) from None
    if not resolved_path.is_file():
        detail = f"required file does not exist: {path}"
        raise ContractValueError(detail)
