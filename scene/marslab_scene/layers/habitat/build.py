"""TerrainArtifact-to-HabitatLayer orchestration."""

from __future__ import annotations

from dataclasses import replace
from typing import assert_never

from marslab_scene.assets.habitats import load_habitat_asset
from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.config.models import HabitatEnabled
from marslab_scene.contracts.layers import FlatnessReport, HabitatLayer
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.errors import CompatibilityProfileMismatch
from marslab_scene.layers.habitat.flatness import find_flattest_anchor
from marslab_scene.layers.habitat.placement import (
    HabitatPlacementError,
    compute_transform,
    sample_anchor,
)


def place_habitat(
    terrain: TerrainArtifact,
    config: HabitatEnabled,
    *,
    policy: CompatibilityPolicy,
) -> HabitatLayer:
    """Place one habitat from an explicit manifest and return a pure layer."""
    dem_path, frame = terrain.require_sampling_surface()
    if frame.compatibility_profile != policy.name:
        raise CompatibilityProfileMismatch(
            expected=policy.name,
            actual=frame.compatibility_profile,
            artifact=terrain.manifest_path,
        )
    asset = load_habitat_asset(config.asset)
    centroid = asset.centroid_zup_m
    if policy.legacy_centroid_transform:
        if asset.legacy_centroid_zup_m is None:
            raise HabitatPlacementError("legacy habitat centroid metadata is required")
        centroid = asset.legacy_centroid_zup_m
    half_x = max(
        abs(asset.aabb_min_zup_m[0] - centroid[0]),
        abs(asset.aabb_max_zup_m[0] - centroid[0]),
    )
    half_y = max(
        abs(asset.aabb_min_zup_m[1] - centroid[1]),
        abs(asset.aabb_max_zup_m[1] - centroid[1]),
    )
    placement = config.placement
    match placement.mode:
        case "flattest":
            selected = find_flattest_anchor(
                dem_path,
                frame,
                footprint_half_x_m=half_x,
                footprint_half_y_m=half_y,
                policy=policy,
            )
            sampled_anchor, _ = sample_anchor(
                dem_path,
                frame,
                selected.anchor.projected_xy_m,
                mode="absolute",
                policy=policy,
            )
            anchor = replace(sampled_anchor, mode="flattest")
            flatness = selected.report
        case "crop_center":
            anchor, _ = sample_anchor(
                dem_path,
                frame,
                frame.origin_projected_m,
                mode="crop_center",
                policy=policy,
            )
            flatness = FlatnessReport(elevation_range_m=0.0, valid_sample_count=1)
        case "absolute":
            if placement.x is None or placement.y is None:
                raise HabitatPlacementError("absolute placement requires x and y")
            anchor, _ = sample_anchor(
                dem_path,
                frame,
                (placement.x, placement.y),
                mode="absolute",
                policy=policy,
            )
            flatness = FlatnessReport(elevation_range_m=0.0, valid_sample_count=1)
        case unreachable:
            assert_never(unreachable)
    transform = compute_transform(
        asset,
        centroid,
        anchor,
        z_align=placement.z_align,
        z_offset_m=placement.z_offset_m,
    )
    return HabitatLayer(
        asset_manifest=asset.manifest_path,
        translation_local_m=transform.translation_local_m,
        rotation_wxyz=(1.0, 0.0, 0.0, 0.0),
        anchor=anchor,
        flatness=flatness,
        aabb_min_local_m=transform.aabb_min_local_m,
        aabb_max_local_m=transform.aabb_max_local_m,
    )
