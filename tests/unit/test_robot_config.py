"""Unit tests for robot configuration validation."""

import pytest
from pydantic import ValidationError

from marslab.config.loader import load_config
from marslab.config.schema import RobotConfig


def test_robot_config_with_urdf():
    """Robot with urdf_path is valid."""
    c = RobotConfig(type="rover", urdf_path="test.urdf")
    assert c.type == "rover"
    assert c.urdf_path == "test.urdf"
    assert c.usd_asset_path is None


def test_robot_config_with_usd():
    """Robot with usd_asset_path is valid."""
    c = RobotConfig(type="quadruped", usd_asset_path="/path/go2.usd")
    assert c.urdf_path is None


def test_robot_config_no_path_raises():
    """Robot without any path raises."""
    with pytest.raises(ValidationError):
        RobotConfig(type="rover")


def test_robot_config_spawn_position_default():
    """Default spawn position is [0, 0, 0.5]."""
    c = RobotConfig(type="rover", urdf_path="test.urdf")
    assert c.spawn_position == [0.0, 0.0, 0.5]


def test_robot_config_spawn_position_wrong_length():
    with pytest.raises(ValidationError):
        RobotConfig(type="rover", urdf_path="test.urdf", spawn_position=[0.0, 0.0])


def test_robot_config_from_mars_env():
    """Robot config loads correctly from mars_env.yaml.

    Wk1 #4 (2026-04-14): rover re-enabled with fix_base=False.
    rotorcraft and quadruped remain commented out in the YAML (Wk2+ scope).
    """
    config = load_config("configs/mars_env.yaml")
    assert len(config.robots) == 1
    rover = config.robots[0]
    assert rover.type == "rover"
    assert rover.urdf_path is not None
    assert "simple_rover.urdf" in rover.urdf_path
    # Raised from 0.30 to 0.50 on 2026-04-14 to give a 0.20 m drop gap on
    # sloped spawn cells (code-quality-reviewer C1). Wheel bottoms sit at
    # spawn_z - 0.30 due to base_link geometry; 0.50 leaves 0.20 m above
    # the terrain surface.
    assert rover.spawn_position == [0.0, 0.0, 0.50]
    # All four sensor configs attached: stereo, depth, lidar, imu.
    assert len(rover.sensor_config_paths) == 4
    assert any("imu" in p for p in rover.sensor_config_paths)


def test_robot_config_both_paths():
    """Robot with both urdf and usd paths is valid."""
    c = RobotConfig(type="rover", urdf_path="a.urdf", usd_asset_path="b.usd")
    assert c.urdf_path == "a.urdf"
    assert c.usd_asset_path == "b.usd"
