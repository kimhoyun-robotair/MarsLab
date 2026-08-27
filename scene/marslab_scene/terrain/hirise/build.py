"""HiRISE GeoTIFF to TerrainArtifact orchestration."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final

import yaml

from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.contracts.provenance import Provenance
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.terrain.elevation import normalize_elevation
from marslab_scene.terrain.frame import TerrainFrame
from marslab_scene.terrain.hirise.appearance.prepare import prepare_visual_enhancement
from marslab_scene.terrain.hirise.appearance.validation import validate_visual_enhancement_sources
from marslab_scene.terrain.hirise.config import (
    CoordinatesConfig,
    CropConfig,
    ElevationConfig,
    InputConfig,
    MeshConfig,
    PhysicsConfig,
    PipelineConfig,
    ProcessingConfig,
    ResampleConfig,
    TextureConfig,
    UsdConfig,
    VisualEnhancementConfig,
)
from marslab_scene.terrain.hirise.dem.crop import (
    compute_crop_origin_projected,
    compute_crop_window,
)
from marslab_scene.terrain.hirise.dem.nodata import build_valid_mask, fill_nodata
from marslab_scene.terrain.hirise.dem.resample import resample_elevation
from marslab_scene.terrain.hirise.ingest.dem_info import inspect_dem, validate_dem_for_mvp
from marslab_scene.terrain.hirise.ingest.geotiff import read_dem_window, write_cropped_geotiff
from marslab_scene.terrain.hirise.mesh.heightfield import build_heightfield_mesh
from marslab_scene.terrain.hirise.texture.prepare import prepare_texture
from marslab_scene.usd.terrain import write_terrain_stage

_MARSLAB_UTILS_REVISION: Final = "6f30d67f036462c6fb0d520945fde01d90f525d1"


@dataclass(frozen=True, slots=True)
class HiriseBuildConfig:
    """Typed public boundary for a standalone terrain build."""

    dem_path: Path
    output_dir: Path
    crop: CropConfig = field(default_factory=CropConfig)
    elevation: ElevationConfig = field(default_factory=ElevationConfig)
    visual_grid_size: int = 513
    collision_grid_size: int = 257
    fill_nodata: str = "nearest"
    resample_method: str = "bilinear"
    texture: TextureConfig = field(default_factory=TextureConfig)
    appearance: VisualEnhancementConfig = field(default_factory=VisualEnhancementConfig)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved_config_digest(config: HiriseBuildConfig) -> str:
    payload = {
        "crop": asdict(config.crop),
        "elevation": asdict(config.elevation),
        "visual_grid_size": config.visual_grid_size,
        "collision_grid_size": config.collision_grid_size,
        "fill_nodata": config.fill_nodata,
        "resample_method": config.resample_method,
        "texture": asdict(config.texture),
        "appearance": asdict(config.appearance),
    }
    encoded = json.dumps(payload, default=str, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _pipeline_config(config: HiriseBuildConfig) -> PipelineConfig:
    return PipelineConfig(
        input=InputConfig(path=config.dem_path),
        crop=config.crop,
        resample=ResampleConfig(method=config.resample_method),
        coordinates=CoordinatesConfig(),
        processing=ProcessingConfig(fill_nodata=config.fill_nodata),
        elevation=config.elevation,
        mesh=MeshConfig(
            visual_grid_size=config.visual_grid_size,
            collision_grid_size=config.collision_grid_size,
            write_visual_obj=False,
            write_collision_obj=False,
        ),
        usd=UsdConfig(output_dir=config.output_dir),
        physics=PhysicsConfig(),
        texture=config.texture,
        visual_enhancement=config.appearance,
    )


def build_hirise_terrain(
    config: HiriseBuildConfig,
    *,
    policy: CompatibilityPolicy,
) -> TerrainArtifact:
    """Build a relocatable terrain sub-stage and its artifact manifest."""
    dem_path = config.dem_path.expanduser().resolve()
    if not dem_path.is_file():
        raise FileNotFoundError(dem_path)
    output_dir = config.output_dir.expanduser().resolve()
    if output_dir.exists():
        raise FileExistsError(output_dir)
    output_dir.mkdir(parents=True)
    pipeline = _pipeline_config(
        HiriseBuildConfig(
            dem_path=dem_path,
            output_dir=output_dir,
            crop=config.crop,
            elevation=config.elevation,
            visual_grid_size=config.visual_grid_size,
            collision_grid_size=config.collision_grid_size,
            fill_nodata=config.fill_nodata,
            resample_method=config.resample_method,
            texture=config.texture,
            appearance=config.appearance,
        )
    )
    info = inspect_dem(dem_path)
    validate_dem_for_mvp(info)
    window = compute_crop_window(info, pipeline.crop)
    crop = read_dem_window(dem_path, window)
    validate_visual_enhancement_sources(pipeline, info, crop)
    valid_mask = build_valid_mask(crop.array, info.nodata) & ~crop.mask
    filled = fill_nodata(crop.array, valid_mask, pipeline.processing.fill_nodata)
    elevation = normalize_elevation(filled, valid_mask, pipeline.elevation)
    visual_z = resample_elevation(
        elevation.local_z,
        pipeline.mesh.visual_grid_size,
        pipeline.resample.method,
    )
    collision_z = resample_elevation(
        elevation.local_z,
        pipeline.mesh.collision_grid_size,
        pipeline.resample.method,
    )
    visual_mesh = build_heightfield_mesh(visual_z, pipeline.crop.width_m, pipeline.crop.height_m)
    collision_mesh = build_heightfield_mesh(
        collision_z,
        pipeline.crop.width_m,
        pipeline.crop.height_m,
    )
    enhancement = prepare_visual_enhancement(
        pipeline,
        crop,
        source_width=visual_z.shape[1],
        source_height=visual_z.shape[0],
    )
    texture = (
        enhancement.prepared_texture
        if enhancement is not None
        else prepare_texture(pipeline, info, crop, elevation, visual_z)
    )
    stage_path = write_terrain_stage(visual_mesh, collision_mesh, pipeline, texture)
    cropped_dem = write_cropped_geotiff(
        output_dir / "cropped_dem.tif",
        crop,
        crs_wkt=info.crs_wkt,
        nodata=info.nodata,
    )
    origin = compute_crop_origin_projected(
        crop.transform,
        width=crop.array.shape[1],
        height=crop.array.shape[0],
    )
    frame = TerrainFrame(
        projected_crs=info.crs_wkt or "",
        raster_affine=(
            crop.transform.a,
            crop.transform.b,
            crop.transform.c,
            crop.transform.d,
            crop.transform.e,
            crop.transform.f,
        ),
        origin_projected_m=origin,
        z_reference_m=elevation.z_reference_m,
        vertical_scale=elevation.vertical_scale,
        z_offset_m=elevation.z_offset_m,
        compatibility_profile=policy.name,
    )
    semantic_report = output_dir / "semantic-terrain.json"
    _ = semantic_report.write_text(
        json.dumps(
            {
                "crop_shape": list(crop.array.shape),
                "visual_vertices": len(visual_mesh.vertices),
                "visual_faces": len(visual_mesh.faces),
                "collision_vertices": len(collision_mesh.vertices),
                "collision_faces": len(collision_mesh.faces),
                "elevation_reference_m": elevation.z_reference_m,
                "elevation_min_m": elevation.local_min_m,
                "elevation_max_m": elevation.local_max_m,
            },
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    manifest_path = output_dir / "manifest.yaml"
    _ = manifest_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "kind": "terrain_artifact",
                "files": {"stage": stage_path.name, "dem": cropped_dem.name},
                "conventions": {"up_axis": "Z", "meters_per_unit": 1.0},
                "provenance": {
                    "producer": "marslab_scene",
                    "marslab_revision": None,
                    "marslab_utils_revision": _MARSLAB_UTILS_REVISION,
                    "source_files": [cropped_dem.name],
                },
                "digests": {
                    "input_file": _sha256(dem_path),
                    "resolved_config": _resolved_config_digest(config),
                    "semantic_report": _sha256(semantic_report),
                    "stage": _sha256(stage_path),
                    "dem": _sha256(cropped_dem),
                },
                "compatibility_profile": policy.name,
                "semantic_comparison_report": semantic_report.name,
                "seed": config.appearance.detail_variation.seed,
                "coordinate_frame": {
                    "projected_crs": frame.projected_crs,
                    "raster_affine": list(frame.raster_affine),
                    "origin_projected_m": list(frame.origin_projected_m),
                    "z_reference_m": frame.z_reference_m,
                    "vertical_scale": frame.vertical_scale,
                    "z_offset_m": frame.z_offset_m,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return TerrainArtifact(
        root_dir=output_dir,
        stage_path=stage_path,
        dem_path=cropped_dem,
        manifest_path=manifest_path,
        coordinate_frame=frame,
        provenance=Provenance(
            producer="marslab_scene",
            marslab_revision=None,
            marslab_utils_revision=_MARSLAB_UTILS_REVISION,
            source_files=(cropped_dem,),
        ),
    )
