"""Unit tests for marslab.config.schema."""

import pytest
from pydantic import ValidationError

from marslab.config.schema import (
    BenchmarkConfig,
    MarsEnvConfig,
    MarsLabConfig,
    RenderingConfig,
    RobotConfig,
    TerrainConfig,
)

# --- Valid construction ---


def test_mars_env_defaults():
    """Default MarsEnvConfig is physically valid."""
    c = MarsEnvConfig()
    assert c.gravity == 3.72
    assert c.dust_optical_depth == 0.3
    assert c.seed == 42


def test_terrain_config_procedural():
    """Procedural terrain does not require dem_path."""
    c = TerrainConfig(source="procedural", procedural_preset="flat")
    assert c.dem_path is None


def test_rendering_config_defaults():
    """Default RenderingConfig is valid."""
    c = RenderingConfig()
    assert c.mode == "path_tracing"
    assert c.resolution == [1280, 720]


def test_robot_config_with_urdf():
    """Robot with urdf_path only is valid."""
    c = RobotConfig(type="rover", urdf_path="test.urdf")
    assert c.usd_asset_path is None


def test_robot_config_with_usd():
    """Robot with usd_asset_path only is valid."""
    c = RobotConfig(type="quadruped", usd_asset_path="/path/to/go2.usd")
    assert c.urdf_path is None


def test_marslab_config_full():
    """Full MarsLabConfig with all sub-configs."""
    c = MarsLabConfig(
        terrain=TerrainConfig(source="procedural", procedural_preset="flat"),
        robots=[RobotConfig(type="rover", urdf_path="test.urdf")],
        benchmark=BenchmarkConfig(),
    )
    assert len(c.robots) == 1
    assert c.benchmark is not None


def test_benchmark_optional():
    """MarsLabConfig with benchmark=None is valid."""
    c = MarsLabConfig(terrain=TerrainConfig(source="procedural", procedural_preset="flat"))
    assert c.benchmark is None


# --- Invalid / out-of-range ---


def test_gravity_too_low():
    with pytest.raises(ValidationError):
        MarsEnvConfig(gravity=2.0)


def test_gravity_too_high():
    with pytest.raises(ValidationError):
        MarsEnvConfig(gravity=5.0)


def test_dust_optical_depth_too_low():
    with pytest.raises(ValidationError):
        MarsEnvConfig(dust_optical_depth=-1.0)


def test_terrain_source_invalid():
    with pytest.raises(ValidationError):
        TerrainConfig(source="moon")


def test_rendering_mode_invalid():
    with pytest.raises(ValidationError):
        RenderingConfig(mode="rasterize")


def test_robot_no_path():
    """Robot without urdf_path or usd_asset_path raises."""
    with pytest.raises(ValidationError):
        RobotConfig(type="rover")


def test_albedo_range_inverted():
    with pytest.raises(ValidationError):
        MarsEnvConfig(surface_albedo_range=(0.5, 0.1))


def test_spawn_position_wrong_length():
    with pytest.raises(ValidationError):
        RobotConfig(type="rover", urdf_path="x.urdf", spawn_position=[0.0, 0.0])


def test_negative_seed():
    with pytest.raises(ValidationError):
        MarsEnvConfig(seed=-1)


def test_resolution_non_positive():
    with pytest.raises(ValidationError):
        RenderingConfig(resolution=[0, 720])


def test_hirise_without_any_path():
    """HiRISE source requires either dem_path or converted_dem_dir."""
    with pytest.raises(ValidationError):
        TerrainConfig(source="hirise", dem_path=None, converted_dem_dir=None)


def test_hirise_with_converted_dir_only():
    """HiRISE source is valid with only converted_dem_dir (no dem_path)."""
    tc = TerrainConfig(source="hirise", converted_dem_dir="assets/terrain/dem/converted")
    assert tc.converted_dem_dir == "assets/terrain/dem/converted"
    assert tc.dem_path is None


def test_hirise_with_both_paths():
    """HiRISE source is valid with both dem_path and converted_dem_dir."""
    tc = TerrainConfig(
        source="hirise",
        dem_path="foo.tif",
        converted_dem_dir="foo_converted",
    )
    assert tc.dem_path == "foo.tif"
    assert tc.converted_dem_dir == "foo_converted"


# --- Boundary values ---


def test_gravity_at_boundaries():
    """Boundary values (ge/le inclusive) are valid."""
    c_low = MarsEnvConfig(gravity=3.0)
    c_high = MarsEnvConfig(gravity=4.0)
    assert c_low.gravity == 3.0
    assert c_high.gravity == 4.0
