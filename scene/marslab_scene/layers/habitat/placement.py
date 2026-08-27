"""Habitat anchor sampling and transform calculation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, assert_never

import numpy as np
import rasterio

from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.contracts.assets import HabitatAssetDescriptor
from marslab_scene.contracts.layers import TerrainAnchor
from marslab_scene.terrain.frame import TerrainFrame
from marslab_scene.terrain.sampling import sample_raw_dem_batch

ZAlignment = Literal["body_floor_to_surface", "aabb_min_to_surface", "center", "none"]


class HabitatPlacementError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class HabitatTransform:
    translation_local_m: tuple[float, float, float]
    aabb_min_local_m: tuple[float, float, float]
    aabb_max_local_m: tuple[float, float, float]


def sample_anchor(
    dem_path: Path,
    frame: TerrainFrame,
    projected_xy_m: tuple[float, float],
    *,
    mode: Literal["crop_center", "absolute"],
    policy: CompatibilityPolicy,
) -> tuple[TerrainAnchor, float]:
    """Sample one requested anchor with profile-specific edge behavior."""
    with rasterio.open(dem_path) as dataset:
        transform = dataset.transform
        column_float, row_float = (~transform) * projected_xy_m
        row = math.floor(row_float)
        column = math.floor(column_float)
        in_bounds = 0 <= row < dataset.height and 0 <= column < dataset.width
        if not in_bounds and not policy.clamp_single_anchor_to_edge:
            raise HabitatPlacementError("habitat anchor is outside the DEM")
        row = int(np.clip(row, 0, dataset.height - 1))
        column = int(np.clip(column, 0, dataset.width - 1))
        sample_xy = projected_xy_m
        if not in_bounds:
            sample_xy = transform * (float(column), float(row))
    samples = sample_raw_dem_batch(dem_path, np.asarray([sample_xy], dtype=np.float64))
    if not samples.valid_mask[0]:
        reason = "nodata" if samples.nodata_mask[0] else "outside"
        detail = f"habitat anchor samples {reason} terrain"
        raise HabitatPlacementError(detail)
    raw_z = float(samples.raw_z_m[0])
    local_x, local_y = frame.projected_to_local_xy(*projected_xy_m)
    surface_z = frame.habitat_z_local(raw_z)
    return (
        TerrainAnchor(
            projected_xy_m=projected_xy_m,
            local_xyz_m=(local_x, local_y, surface_z),
            dem_row_column=(row, column),
            mode=mode,
        ),
        raw_z,
    )


def compute_transform(
    asset: HabitatAssetDescriptor,
    centroid_zup_m: tuple[float, float, float],
    anchor: TerrainAnchor,
    *,
    z_align: ZAlignment,
    z_offset_m: float,
) -> HabitatTransform:
    """Align neutral Z-up habitat metadata to a sampled terrain anchor."""
    translation_x = anchor.local_xyz_m[0] - centroid_zup_m[0]
    translation_y = anchor.local_xyz_m[1] - centroid_zup_m[1]
    match z_align:
        case "body_floor_to_surface":
            translation_z = anchor.local_xyz_m[2] - asset.body_floor_z_m
        case "aabb_min_to_surface":
            translation_z = anchor.local_xyz_m[2] - asset.aabb_min_zup_m[2]
        case "center":
            center_z = (asset.aabb_min_zup_m[2] + asset.aabb_max_zup_m[2]) / 2.0
            translation_z = anchor.local_xyz_m[2] - center_z
        case "none":
            translation_z = 0.0
        case unreachable:
            assert_never(unreachable)
    translation = (translation_x, translation_y, translation_z + z_offset_m)
    minimum = (
        asset.aabb_min_zup_m[0] + translation[0],
        asset.aabb_min_zup_m[1] + translation[1],
        asset.aabb_min_zup_m[2] + translation[2],
    )
    maximum = (
        asset.aabb_max_zup_m[0] + translation[0],
        asset.aabb_max_zup_m[1] + translation[1],
        asset.aabb_max_zup_m[2] + translation[2],
    )
    return HabitatTransform(
        translation_local_m=translation,
        aabb_min_local_m=minimum,
        aabb_max_local_m=maximum,
    )
