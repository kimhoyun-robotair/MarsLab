"""Source validation for Task 12 visual enhancement inputs."""

from __future__ import annotations

from pathlib import Path

import rasterio
from rasterio.crs import CRS

from marslab_scene.terrain.hirise.config import PipelineConfig
from marslab_scene.terrain.hirise.ingest.dem_info import DemInfo
from marslab_scene.terrain.hirise.ingest.geotiff import RasterCrop


class VisualEnhancementSourceError(ValueError):
    """Raised when Task 12 visual source inputs are invalid."""


def validate_visual_enhancement_sources(
    config: PipelineConfig,
    info: DemInfo,
    crop: RasterCrop,
) -> None:
    """Validate Task 12 DEM/orthomosaic/Mastcam input source compatibility."""
    visual = config.visual_enhancement
    if not visual.enabled or visual.mode == "none":
        return

    if visual.orthomosaic.path is None:
        raise VisualEnhancementSourceError(
            "visual_enhancement.orthomosaic.path is required when visual enhancement is enabled"
        )

    dem_crs = CRS.from_wkt(info.crs_wkt) if info.crs_wkt else None
    _validate_orthomosaic(
        visual.orthomosaic.path,
        dem_crs=dem_crs,
        crop_bounds=crop.bounds,
        require_same_crs=visual.orthomosaic.require_same_crs,
    )

    if visual.mode == "orthomosaic_mastcam_palette":
        if visual.mastcam_reference.path is None:
            raise VisualEnhancementSourceError(
                "mastcam_reference.path is required for mode=orthomosaic_mastcam_palette"
            )
        _validate_mastcam_reference(visual.mastcam_reference.path)


def _validate_orthomosaic(
    path: Path,
    *,
    dem_crs: CRS | None,
    crop_bounds: tuple[float, float, float, float],
    require_same_crs: bool,
) -> None:
    if not path.exists():
        raise VisualEnhancementSourceError(f"Orthomosaic path does not exist: {path}")

    try:
        with rasterio.open(path) as dataset:
            if dataset.count < 1:
                raise VisualEnhancementSourceError("Orthomosaic must have at least one band")
            if require_same_crs:
                if dataset.crs is None or dem_crs is None or dataset.crs != dem_crs:
                    raise VisualEnhancementSourceError(
                        "DEM/orthomosaic CRS mismatch; Task 12 does not reproject"
                    )
            if not _bounds_overlap(crop_bounds, dataset.bounds):
                raise VisualEnhancementSourceError(
                    "Orthomosaic does not overlap the DEM crop bounds"
                )
    except VisualEnhancementSourceError:
        raise
    except Exception as exc:
        raise VisualEnhancementSourceError(f"Could not open orthomosaic: {path}") from exc


def _validate_mastcam_reference(path: Path) -> None:
    if not path.exists():
        raise VisualEnhancementSourceError(f"Mastcam reference path does not exist: {path}")
    try:
        with rasterio.open(path) as dataset:
            if dataset.count < 1:
                raise VisualEnhancementSourceError(
                    "Mastcam reference image must have at least one band"
                )
            if dataset.width < 1 or dataset.height < 1:
                raise VisualEnhancementSourceError("Mastcam reference image is empty")
    except VisualEnhancementSourceError:
        raise
    except Exception as exc:
        msg = f"Could not open Mastcam reference image: {path}"
        raise VisualEnhancementSourceError(msg) from exc


def _bounds_overlap(
    a: tuple[float, float, float, float],
    b: object,
) -> bool:
    left_a, bottom_a, right_a, top_a = a
    left_b = float(b.left)
    bottom_b = float(b.bottom)
    right_b = float(b.right)
    top_b = float(b.top)
    return left_a < right_b and right_a > left_b and bottom_a < top_b and top_a > bottom_b
