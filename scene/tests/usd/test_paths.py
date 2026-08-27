from __future__ import annotations

from pathlib import Path

import pytest
from marslab_scene.errors import PathContractError
from marslab_scene.usd.paths import relative_reference, resolve_local_reference

pytestmark = [pytest.mark.unit, pytest.mark.contract]


def test_relative_reference_and_containment_are_owned_by_usd_paths(tmp_path: Path) -> None:
    # Given
    root = tmp_path / "root"
    owner = root / "layers"
    target = root / "textures" / "albedo.png"
    owner.mkdir(parents=True)
    target.parent.mkdir()
    target.write_bytes(b"x")

    # When
    authored_path = relative_reference(owner, target, root=root)
    resolved = resolve_local_reference(root, owner, authored_path)

    # Then
    assert authored_path == "../textures/albedo.png"
    assert resolved == target


def test_usd_paths_reject_remote_absolute_and_root_escape(tmp_path: Path) -> None:
    # Given
    root = tmp_path / "root"
    owner = root / "layers"
    owner.mkdir(parents=True)

    # When / Then
    for token in ("https://example.invalid/a.png", "/absolute/a.png", "../../escape.png"):
        with pytest.raises(PathContractError):
            resolve_local_reference(root, owner, token, require_file=False)
