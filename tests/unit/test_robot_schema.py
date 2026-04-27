"""Module-focused tests for marslab.config.schema.robot.RobotConfig."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from marslab.config.schema import RobotConfig
from marslab.config.schema.robot import (
    OdometryCovarianceConfig,
    OdomPublisherConfig,
)


class TestRobotSpecLoad:
    """Valid RobotConfig construction variants."""

    def test_rover_with_urdf_path_only(self) -> None:
        c = RobotConfig(type="rover", urdf_path="assets/robots/rover.urdf")
        assert c.type == "rover"
        assert c.urdf_path == "assets/robots/rover.urdf"
        assert c.usd_asset_path is None

    def test_quadruped_with_usd_asset_only(self) -> None:
        c = RobotConfig(type="quadruped", usd_asset_path="Isaac/Robots/Unitree/Go2/go2.usd")
        assert c.urdf_path is None
        assert c.usd_asset_path == "Isaac/Robots/Unitree/Go2/go2.usd"

    def test_both_urdf_and_usd_allowed(self) -> None:
        """Declaring both paths is valid — the runtime chooses based on
        robot type."""
        c = RobotConfig(
            type="humanoid",
            urdf_path="assets/robots/h1.urdf",
            usd_asset_path="Isaac/Robots/Unitree/H1/h1.usd",
        )
        assert c.urdf_path is not None and c.usd_asset_path is not None

    def test_neither_urdf_nor_usd_rejected(self) -> None:
        with pytest.raises(ValidationError):
            RobotConfig(type="rover")


class TestSensorListTyping:
    """``sensor_config_paths`` and ``spawn_position`` typing rules."""

    def test_sensor_config_paths_default_empty_list(self) -> None:
        c = RobotConfig(type="rover", urdf_path="x.urdf")
        assert c.sensor_config_paths == []

    def test_sensor_config_paths_accepts_list_of_strings(self) -> None:
        paths = ["configs/sensors/camera.yaml", "configs/sensors/lidar.yaml"]
        c = RobotConfig(type="rover", urdf_path="x.urdf", sensor_config_paths=paths)
        assert c.sensor_config_paths == paths

    def test_spawn_position_default_half_meter_up(self) -> None:
        """Default spawn is ``[0, 0, 0.5]`` so ``fix_base=False`` rovers
        settle onto terrain instead of starting penetrated."""
        c = RobotConfig(type="rover", urdf_path="x.urdf")
        assert c.spawn_position == [0.0, 0.0, 0.5]

    def test_spawn_position_must_have_three_components(self) -> None:
        with pytest.raises(ValidationError):
            RobotConfig(type="rover", urdf_path="x.urdf", spawn_position=[0.0, 0.0])
        with pytest.raises(ValidationError):
            RobotConfig(type="rover", urdf_path="x.urdf", spawn_position=[0.0, 0.0, 0.0, 0.1])

    def test_spawn_position_accepts_negative_values(self) -> None:
        """Spawning at negative X/Y (other side of DEM origin) is valid."""
        c = RobotConfig(type="rover", urdf_path="x.urdf", spawn_position=[-60.0, -60.0, 0.7])
        assert c.spawn_position == [-60.0, -60.0, 0.7]


class TestUrdfPathResolve:
    """URDF / USD paths are *strings* at the schema layer — resolution
    to an absolute file is the caller's job. The schema must still
    accept the common input shapes."""

    @pytest.mark.parametrize(
        "path",
        [
            "assets/robots/rover.urdf",
            "/abs/path/to/rover.urdf",
            "./relative/rover.urdf",
            "../../weird/rover.urdf",
        ],
    )
    def test_urdf_path_variants_accepted(self, path: str) -> None:
        c = RobotConfig(type="rover", urdf_path=path)
        assert c.urdf_path == path

    def test_prim_path_override(self) -> None:
        """``prim_path`` override lets multiple quadrupeds coexist."""
        c = RobotConfig(
            type="quadruped",
            usd_asset_path="go2.usd",
            prim_path="/World/quadruped_0",
        )
        assert c.prim_path == "/World/quadruped_0"

    def test_prim_path_default_none(self) -> None:
        """Default ``prim_path=None`` triggers the ``/World/{type}`` fallback."""
        c = RobotConfig(type="rover", urdf_path="x.urdf")
        assert c.prim_path is None


class TestBroaderRobotFields:
    """Broader-than-drive fields on RobotConfig."""

    def test_drive_field_optional(self) -> None:
        """Non-teleop robots (rotorcraft, quadruped) do not need a drive block."""
        c = RobotConfig(type="rotorcraft", urdf_path="x.urdf")
        assert c.drive is None

    def test_odometry_covariance_default_shape(self) -> None:
        """Placeholder covariance is 6x6 diagonal."""
        cov = OdometryCovarianceConfig()
        assert len(cov.pose_diag) == 6
        assert len(cov.twist_diag) == 6

    def test_odom_publisher_defaults_match_slam_nav_convention(self) -> None:
        """Frame IDs must match ``configs/slam/*.yaml`` and Nav2 defaults."""
        p = OdomPublisherConfig()
        assert p.frame_id == "odom"
        assert p.child_frame_id == "base_link"
        assert 1 <= p.queue_size <= 100

    def test_odom_publisher_queue_size_bounds(self) -> None:
        with pytest.raises(ValidationError):
            OdomPublisherConfig(queue_size=0)
        with pytest.raises(ValidationError):
            OdomPublisherConfig(queue_size=200)
