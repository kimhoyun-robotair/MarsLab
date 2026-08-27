"""Legacy metadata parsing and terrain-manifest emission."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import rasterio
import yaml
from pydantic import JsonValue

from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.config.json_value import JSON_VALUE_ADAPTER
from marslab_scene.config.models import LegacyArtifactSource
from marslab_scene.errors import LegacyTerrainNormalizationError
from marslab_scene.terrain.frame import TerrainFrame


@dataclass(frozen=True, slots=True)
class LegacyManifestInputs:
    output_dir: Path
    source: LegacyArtifactSource
    frame: TerrainFrame


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_legacy_frame(
    dem: Path,
    metadata_path: Path,
    policy: CompatibilityPolicy,
) -> TerrainFrame:
    """Map explicit legacy metadata and DEM georeferencing into TerrainFrame."""
    try:
        parsed = JSON_VALUE_ADAPTER.validate_json(metadata_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        detail = f"invalid legacy metadata: {error}"
        raise LegacyTerrainNormalizationError(detail) from error
    if not isinstance(parsed, dict):
        raise LegacyTerrainNormalizationError("legacy metadata must be an object")
    crop = parsed.get("crop", {})
    elevation = parsed.get("elevation", {})
    if not isinstance(crop, dict) or not isinstance(elevation, dict):
        raise LegacyTerrainNormalizationError("legacy crop/elevation metadata must be objects")
    declared_profile = parsed.get("compatibility_profile")
    if declared_profile is not None and declared_profile != policy.name:
        raise LegacyTerrainNormalizationError("legacy metadata compatibility profile mismatch")
    with rasterio.open(dem) as dataset:
        transform = dataset.transform
        crs = dataset.crs
        projected_crs = "" if crs is None else crs.to_wkt()
        if not projected_crs:
            raise LegacyTerrainNormalizationError("legacy DEM has no projected CRS")
    return TerrainFrame(
        projected_crs=projected_crs,
        raster_affine=(
            transform.a,
            transform.b,
            transform.c,
            transform.d,
            transform.e,
            transform.f,
        ),
        origin_projected_m=(
            _number(crop, "origin_x_geo", transform.c),
            _number(crop, "origin_y_geo", transform.f),
        ),
        z_reference_m=_number(elevation, "z_reference_m", 0.0),
        vertical_scale=_number(elevation, "vertical_scale", 1.0),
        z_offset_m=_number(elevation, "z_offset_m", 0.0),
        compatibility_profile=policy.name,
    )


def _number(section: dict[str, JsonValue], key: str, default: float) -> float:
    value = section.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        detail = f"legacy metadata field must be numeric: {key}"
        raise LegacyTerrainNormalizationError(detail)
    return float(value)


def write_legacy_manifest(inputs: LegacyManifestInputs) -> Path:
    """Record normalized files, digests, profile, and legacy-key provenance."""
    output_dir = inputs.output_dir
    source = inputs.source
    frame = inputs.frame
    files = tuple(path for path in output_dir.rglob("*") if path.is_file())
    manifest_path = output_dir / "manifest.yaml"
    manifest = {
        "schema_version": 1,
        "kind": "terrain_artifact",
        "files": {"stage": source.stage.as_posix(), "dem": source.dem.as_posix()},
        "conventions": {"up_axis": "Z", "meters_per_unit": 1.0},
        "provenance": {
            "producer": "marslab_scene.compat.legacy_terrain",
            "marslab_revision": None,
            "marslab_utils_revision": "6f30d67f036462c6fb0d520945fde01d90f525d1",
            "source_files": sorted(path.relative_to(output_dir).as_posix() for path in files),
            "legacy_key_mapping": {
                "crop.origin_x_geo": "coordinate_frame.origin_projected_m[0]",
                "crop.origin_y_geo": "coordinate_frame.origin_projected_m[1]",
                "elevation.z_reference_m": "coordinate_frame.z_reference_m",
                "elevation.vertical_scale": "coordinate_frame.vertical_scale",
                "elevation.z_offset_m": "coordinate_frame.z_offset_m",
            },
            "legacy_external_dependencies": [
                {
                    "owner_layer": dependency.owner_layer.as_posix(),
                    "authored_path_sha256": dependency.authored_path_sha256,
                    "destination": dependency.destination.as_posix(),
                    "sha256": dependency.sha256,
                    "redistribution_allowed": dependency.redistribution_allowed,
                }
                for dependency in source.external_dependencies
            ],
        },
        "digests": {
            path.relative_to(output_dir).as_posix(): _sha256(path) for path in sorted(files)
        },
        "compatibility_profile": frame.compatibility_profile,
        "coordinate_frame": {
            "projected_crs": frame.projected_crs,
            "raster_affine": list(frame.raster_affine),
            "origin_projected_m": list(frame.origin_projected_m),
            "z_reference_m": frame.z_reference_m,
            "vertical_scale": frame.vertical_scale,
            "z_offset_m": frame.z_offset_m,
        },
        "semantic_comparison_report": None,
        "seed": None,
    }
    _ = manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return manifest_path
