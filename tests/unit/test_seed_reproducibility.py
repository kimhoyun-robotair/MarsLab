"""End-to-end seed reproducibility tests.

Verifies that the full pipeline produces identical output when given
the same master seed. This is a MUST requirement for reproducibility.
"""

import numpy as np

from marslab.config.loader import propagate_seeds
from marslab.config.schema import MarsEnvConfig, MarsLabConfig, TerrainConfig  # noqa: F401
from marslab.environment.diffuse_fraction import compute_diffuse_fraction
from marslab.environment.light_intensity import compute_direct_intensity
from marslab.environment.sky_dome import compute_sky_dome_params
from marslab.environment.sun_position import compute_sun_position
from marslab.terrain.procedural_generator import generate_terrain
from marslab.terrain.rock_placer import sample_rocks_golombek


def _run_pipeline(master_seed: int) -> dict:
    """Run the full offline pipeline and return all outputs."""
    config = MarsLabConfig(
        mars_env=MarsEnvConfig(),
        terrain=TerrainConfig(source="procedural", procedural_preset="crater"),
    )
    config = propagate_seeds(config, master_seed=master_seed)

    elevation, meta = generate_terrain(
        preset=config.terrain.procedural_preset,
        size=config.terrain.terrain_size,
        resolution=config.terrain.terrain_resolution,
        seed=config.terrain.seed,
    )

    area = meta["width"] * meta["resolution_x"] * meta["height"] * meta["resolution_y"]
    rocks = sample_rocks_golombek(
        area_m2=area,
        k=config.terrain.rock_sfd_k,
        diameter_range=config.terrain.rock_diameter_range,
        seed=config.terrain.seed,
    )

    sun = compute_sun_position(
        config.mars_env.sun_azimuth_deg,
        config.mars_env.sun_elevation_deg,
    )
    intensity = compute_direct_intensity(
        config.mars_env.solar_constant,
        config.mars_env.dust_optical_depth,
        sun.zenith_angle_rad,
    )
    diffuse = compute_diffuse_fraction(config.mars_env.dust_optical_depth)
    sky = compute_sky_dome_params(config.mars_env.dust_optical_depth, "assets/sky/hdri/")

    return {
        "elevation": elevation,
        "rock_count": len(rocks),
        "rock_positions": [(r.x, r.y) for r in rocks[:20]],
        "sun_zenith": sun.zenith_angle_rad,
        "intensity": intensity,
        "diffuse": diffuse,
        "sky_rgb": sky.base_color_rgb,
    }


def test_full_pipeline_seed_determinism():
    """Identical master seed → identical pipeline output."""
    r1 = _run_pipeline(master_seed=42)
    r2 = _run_pipeline(master_seed=42)

    assert np.array_equal(r1["elevation"], r2["elevation"])
    assert r1["rock_count"] == r2["rock_count"]
    assert r1["rock_positions"] == r2["rock_positions"]
    assert r1["sun_zenith"] == r2["sun_zenith"]
    assert r1["intensity"] == r2["intensity"]
    assert r1["diffuse"] == r2["diffuse"]
    assert r1["sky_rgb"] == r2["sky_rgb"]


def test_different_master_seeds_differ():
    """Different master seeds → different terrain and rocks."""
    r1 = _run_pipeline(master_seed=42)
    r2 = _run_pipeline(master_seed=99)

    assert not np.array_equal(r1["elevation"], r2["elevation"])
    assert r1["rock_positions"] != r2["rock_positions"]


def test_seed_propagation_offsets():
    """Propagated seeds are deterministic offsets from master."""
    config = MarsLabConfig(
        terrain=TerrainConfig(source="procedural", procedural_preset="flat"),
    )
    c1 = propagate_seeds(config, master_seed=42)
    c2 = propagate_seeds(config, master_seed=42)

    assert c1.mars_env.seed == c2.mars_env.seed
    assert c1.terrain.seed == c2.terrain.seed
    assert c1.terrain.seed == c1.mars_env.seed + 1
