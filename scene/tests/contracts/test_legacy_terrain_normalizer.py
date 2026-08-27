from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import rasterio
import yaml
from marslab_scene.compat.legacy_terrain import normalize_legacy_terrain
from marslab_scene.compat.profiles import resolve_compatibility_policy
from marslab_scene.config.models import LegacyArtifactSource, LegacyExternalDependency
from marslab_scene.errors import LegacyTerrainNormalizationError
from pxr import Sdf, Usd
from rasterio.transform import from_origin

pytestmark = [pytest.mark.contract, pytest.mark.standalone_usd]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _fixture(tmp_path: Path, authored_path: str) -> tuple[Path, Path]:
    root = tmp_path / "legacy"
    root.mkdir()
    dem = root / "terrain.tif"
    with rasterio.open(
        dem,
        "w",
        driver="GTiff",
        width=2,
        height=2,
        count=1,
        dtype="float32",
        crs="EPSG:32612",
        transform=from_origin(100.0, 200.0, 2.5, 3.0),
    ) as dataset:
        dataset.write(np.array([[10.0, 11.0], [12.0, 13.0]], dtype=np.float32), 1)
    (root / "metadata.json").write_text(
        json.dumps(
            {
                "crop": {"origin_x_geo": 102.5, "origin_y_geo": 197.0},
                "elevation": {"z_reference_m": 10.0, "vertical_scale": 1.5, "z_offset_m": 2.0},
                "compatibility_profile": "canonical",
            }
        ),
        encoding="utf-8",
    )
    stage = Usd.Stage.CreateNew(str(root / "terrain.usda"))
    world = stage.DefinePrim("/World", "Xform")
    stage.SetDefaultPrim(world)
    material = stage.DefinePrim("/World/Material", "Shader")
    material.CreateAttribute("inputs:file", Sdf.ValueTypeNames.Asset).Set(
        Sdf.AssetPath(authored_path)
    )
    stage.GetRootLayer().Save()
    replacement = tmp_path / "replacement.png"
    replacement.write_bytes(b"replacement-texture")
    return root, replacement


def _source(
    root: Path, replacement: Path, authored_path: str, **updates: str | bool
) -> LegacyArtifactSource:
    values: dict[str, str | bool] = {
        "owner_layer": "terrain.usda",
        "authored_path_sha256": f"sha256:{_token_digest(authored_path)}",
        "source": str(replacement),
        "destination": "dependencies/albedo.png",
        "sha256": f"sha256:{_sha256(replacement)}",
        "redistribution_allowed": True,
    }
    values.update(updates)
    dependency = LegacyExternalDependency.model_construct(
        owner_layer=Path(str(values["owner_layer"])),
        authored_path_sha256=str(values["authored_path_sha256"]),
        source=Path(str(values["source"])),
        destination=Path(str(values["destination"])),
        sha256=str(values["sha256"]),
        redistribution_allowed=True,
    )
    return LegacyArtifactSource.model_construct(
        type="legacy_artifact",
        root=root,
        stage=Path("terrain.usda"),
        dem=Path("terrain.tif"),
        metadata=Path("metadata.json"),
        external_dependencies=(dependency,),
    )


def test_normalized_legacy_artifact_relocates_without_original_root(tmp_path: Path) -> None:
    # Given
    authored_path = "/missing/legacy/albedo.png"
    root, replacement = _fixture(tmp_path, authored_path)

    # When
    artifact = normalize_legacy_terrain(
        _source(root, replacement, authored_path),
        output_dir=tmp_path / "normalized",
        policy=resolve_compatibility_policy("canonical"),
    )
    shutil.rmtree(root)
    relocated = tmp_path / "relocated"
    shutil.copytree(artifact.root_dir, relocated)

    # Then
    stage = Usd.Stage.Open(str(relocated / "terrain.usda"))
    assert stage
    assert (relocated / "dependencies/albedo.png").read_bytes() == b"replacement-texture"
    text = (relocated / "terrain.usda").read_text(encoding="utf-8")
    assert "/missing/legacy" not in text
    assert "../" not in text
    manifest = yaml.safe_load((relocated / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["compatibility_profile"] == "canonical"
    assert (
        manifest["provenance"]["legacy_key_mapping"]["elevation.z_reference_m"]
        == "coordinate_frame.z_reference_m"
    )
    recorded = manifest["provenance"]["legacy_external_dependencies"][0]
    assert recorded["owner_layer"] == "terrain.usda"
    assert recorded["destination"] == "dependencies/albedo.png"
    assert recorded["redistribution_allowed"] is True


@pytest.mark.parametrize(
    ("authored_path", "error"),
    [
        ("/ordinary/absolute.png", "allowlist"),
        ("../escape.png", "allowlist"),
        ("missing.png", "allowlist"),
        ("https://example.invalid/remote.png", "remote URI"),
    ],
)
def test_unallowlisted_external_reference_fails_closed(
    tmp_path: Path, authored_path: str, error: str
) -> None:
    # Given
    root, _ = _fixture(tmp_path, authored_path)
    source = LegacyArtifactSource.model_construct(
        type="legacy_artifact",
        root=root,
        stage=Path("terrain.usda"),
        dem=Path("terrain.tif"),
        metadata=Path("metadata.json"),
        external_dependencies=(),
    )

    # When / Then
    with pytest.raises(LegacyTerrainNormalizationError, match=error):
        normalize_legacy_terrain(
            source,
            output_dir=tmp_path / "rejected",
            policy=resolve_compatibility_policy("canonical"),
        )


def test_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    # Given
    authored_path = "/missing/legacy/albedo.png"
    root, replacement = _fixture(tmp_path, authored_path)
    source = _source(root, replacement, authored_path, sha256=f"sha256:{'0' * 64}")

    # When / Then
    with pytest.raises(LegacyTerrainNormalizationError, match="digest"):
        normalize_legacy_terrain(
            source, output_dir=tmp_path / "out", policy=resolve_compatibility_policy("canonical")
        )


def test_allowlisted_replacement_symlink_fails_closed(tmp_path: Path) -> None:
    # Given
    authored_path = "/missing/legacy/albedo.png"
    root, replacement = _fixture(tmp_path, authored_path)
    replacement_link = tmp_path / "replacement-link.png"
    replacement_link.symlink_to(replacement)
    source = _source(root, replacement_link, authored_path)

    # When / Then
    with pytest.raises(LegacyTerrainNormalizationError, match="regular file"):
        normalize_legacy_terrain(
            source,
            output_dir=tmp_path / "symlink-replacement",
            policy=resolve_compatibility_policy("canonical"),
        )


def test_absolute_symlink_and_special_replacement_fail_closed(tmp_path: Path) -> None:
    # Given
    authored_path = "linked.png"
    root, _replacement = _fixture(tmp_path, authored_path)
    external = tmp_path / "external.png"
    external.write_bytes(b"external")
    (root / authored_path).symlink_to(external)
    source = LegacyArtifactSource.model_construct(
        type="legacy_artifact",
        root=root,
        stage=Path("terrain.usda"),
        dem=Path("terrain.tif"),
        metadata=Path("metadata.json"),
        external_dependencies=(),
    )

    # When / Then
    with pytest.raises(LegacyTerrainNormalizationError, match="allowlist"):
        normalize_legacy_terrain(
            source,
            output_dir=tmp_path / "symlink",
            policy=resolve_compatibility_policy("canonical"),
        )

    fifo = tmp_path / "replacement-fifo"
    fifo.mkdir()
    special_dependency = LegacyExternalDependency.model_construct(
        owner_layer=Path("terrain.usda"),
        authored_path_sha256=f"sha256:{_token_digest(authored_path)}",
        source=fifo,
        destination=Path("dependencies/albedo.png"),
        sha256=f"sha256:{'0' * 64}",
        redistribution_allowed=True,
    )
    special = LegacyArtifactSource.model_construct(
        type="legacy_artifact",
        root=root,
        stage=Path("terrain.usda"),
        dem=Path("terrain.tif"),
        metadata=Path("metadata.json"),
        external_dependencies=(special_dependency,),
    )
    with pytest.raises(LegacyTerrainNormalizationError, match="regular file"):
        normalize_legacy_terrain(
            special,
            output_dir=tmp_path / "special",
            policy=resolve_compatibility_policy("canonical"),
        )


def test_nested_layer_escape_requires_nested_owner_allowlist(tmp_path: Path) -> None:
    # Given
    root, _replacement = _fixture(tmp_path, "nested.usda")
    nested = root / "nested.usda"
    nested.write_text(
        '#usda 1.0\n\ndef Xform "Nested"\n{\n    asset escaped = @../../escape.png@\n}\n',
        encoding="utf-8",
    )
    source = LegacyArtifactSource.model_construct(
        type="legacy_artifact",
        root=root,
        stage=Path("terrain.usda"),
        dem=Path("terrain.tif"),
        metadata=Path("metadata.json"),
        external_dependencies=(),
    )

    # When / Then
    with pytest.raises(LegacyTerrainNormalizationError, match="allowlist"):
        normalize_legacy_terrain(
            source, output_dir=tmp_path / "nested", policy=resolve_compatibility_policy("canonical")
        )
