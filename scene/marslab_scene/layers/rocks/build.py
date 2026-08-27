"""TerrainArtifact-to-RockLayer orchestration."""

from __future__ import annotations

import numpy as np

from marslab_scene.assets.rocks import load_rock_asset
from marslab_scene.compat.profiles import CompatibilityPolicy
from marslab_scene.config.models import RocksEnabled
from marslab_scene.contracts.layers import RockLayer, RockPlacementStats
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.errors import CompatibilityProfileMismatch
from marslab_scene.layers.rocks.input import load_rock_csv
from marslab_scene.layers.rocks.placement import RockPrototype, compute_rock_placement
from marslab_scene.terrain.sampling import sample_raw_dem_batch


def place_rocks(
    terrain: TerrainArtifact,
    config: RocksEnabled,
    *,
    policy: CompatibilityPolicy,
) -> RockLayer:
    """Place a precomputed CSV population on a terrain and return a pure layer."""
    dem_path, frame = terrain.require_sampling_surface()
    if frame.compatibility_profile != policy.name:
        raise CompatibilityProfileMismatch(
            expected=policy.name,
            actual=frame.compatibility_profile,
            artifact=terrain.manifest_path,
        )
    asset = load_rock_asset(config.asset)
    csv = load_rock_csv(config.placements)
    samples = sample_raw_dem_batch(dem_path, csv.projected_xy_m)
    placement = compute_rock_placement(
        csv.diameters_m,
        tuple(
            RockPrototype(
                id=prototype_id,
                native_diameter_m=native_diameter,
                stable_poses_wxyz=stable_poses,
            )
            for prototype_id, native_diameter, stable_poses in zip(
                asset.prototype_ids,
                asset.native_diameters_m,
                asset.stable_pose_candidates_wxyz,
                strict=True,
            )
        ),
        seed=config.seed,
        top_k=config.top_k,
        scale_clamp=config.scale_clamp,
    )
    valid = samples.valid_mask
    local_xy = np.asarray(
        [frame.projected_to_local_xy(x, y) for x, y in csv.projected_xy_m[valid]],
        dtype=np.float64,
    ).reshape((-1, 2))
    local_z = np.asarray(
        [frame.rock_z_local(value) for value in samples.raw_z_m[valid]],
        dtype=np.float64,
    )
    positions = np.column_stack((local_xy, local_z))
    return RockLayer(
        asset_manifest=asset.manifest_path,
        positions_local_m=positions,
        prototype_indices=placement.prototype_indices[valid],
        scales=placement.scales[valid],
        orientations_wxyz=placement.orientations_wxyz[valid],
        placement_source=csv.source_path,
        seed=config.seed,
        stats=RockPlacementStats(
            csv_count=len(csv.diameters_m),
            placed_count=int(np.count_nonzero(valid)),
            skipped_out_of_bounds=int(np.count_nonzero(samples.out_of_bounds_mask)),
            skipped_nodata=int(np.count_nonzero(samples.nodata_mask)),
            clamped_count=int(np.count_nonzero(placement.clamped[valid])),
        ),
    )
