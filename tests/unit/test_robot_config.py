"""Unit tests for robot configuration validation."""

import pytest
from pydantic import ValidationError

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


def test_robot_config_both_paths():
    """Robot with both urdf and usd paths is valid."""
    c = RobotConfig(type="rover", urdf_path="a.urdf", usd_asset_path="b.usd")
    assert c.urdf_path == "a.urdf"
    assert c.usd_asset_path == "b.usd"
