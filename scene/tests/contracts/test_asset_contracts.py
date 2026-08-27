from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from marslab_scene.assets import load_habitat_asset, load_rock_asset
from pxr import Usd

pytestmark = [pytest.mark.contract, pytest.mark.standalone_usd]

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "assets"


def test_rock_loader_validates_synthetic_bundle_with_real_usd() -> None:
    # Given
    manifest = _FIXTURES / "rocks" / "manifest.yaml"

    # When
    asset = load_rock_asset(manifest)

    # Then
    assert asset.prototype_ids == ("rock_one",)
    assert Usd.Stage.Open(str(asset.stage_path)).GetDefaultPrim().GetPath().pathString == "/World"


def test_habitat_loader_validates_synthetic_bundle_with_real_usd() -> None:
    # Given
    manifest = _FIXTURES / "habitats" / "manifest.yaml"

    # When
    asset = load_habitat_asset(manifest)

    # Then
    assert asset.centroid_zup_m == (0.0, 0.0, 0.75)
    assert Usd.Stage.Open(str(asset.stage_path)).GetDefaultPrim().GetPath().pathString == "/Habitat"


def test_asset_loaders_resolve_after_bundle_root_is_relocated(tmp_path: Path) -> None:
    # Given
    relocated = tmp_path / "different-absolute-root" / "assets"
    shutil.copytree(_FIXTURES, relocated)

    # When
    rock = load_rock_asset(relocated / "rocks" / "manifest.yaml")
    habitat = load_habitat_asset(relocated / "habitats" / "manifest.yaml")

    # Then
    assert rock.stage_path.is_relative_to(relocated)
    assert habitat.stage_path.is_relative_to(relocated)


def test_asset_bundle_digest_is_stable_across_relocation(tmp_path: Path) -> None:
    # Given
    relocated = tmp_path / "relocated"
    shutil.copytree(_FIXTURES, relocated)

    # When
    original = load_rock_asset(_FIXTURES / "rocks" / "manifest.yaml")
    copied = load_rock_asset(relocated / "rocks" / "manifest.yaml")

    # Then
    assert original.bundle_digest == copied.bundle_digest
