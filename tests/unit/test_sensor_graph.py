"""Unit tests for marslab.ros2_bridge.sensor_graph orchestrator invariants."""

from __future__ import annotations

import pytest

from marslab.ros2_bridge import sensor_graph
from marslab.ros2_bridge.sensor_graph import GRAPH_PATH
from marslab.ros2_bridge.sensor_graph_builder import (
    _build_connections,
    _build_create_nodes,
    _build_set_values,
    _ns_topic,
)


class TestGraphSpecDict:
    """The graph path is a stable string and the builder surface is
    re-exported from ``sensor_graph`` for legacy callers."""

    def test_graph_path_constant_is_world_scoped(self) -> None:
        assert GRAPH_PATH == "/World/Stage3ROS2Graph"

    def test_sensor_graph_reexports_builder_helpers(self) -> None:
        """The list-builders live in ``sensor_graph_builder``;
        ``sensor_graph`` re-exports them for backward compat."""
        assert sensor_graph._build_create_nodes is _build_create_nodes
        assert sensor_graph._build_connections is _build_connections
        assert sensor_graph._build_set_values is _build_set_values
        assert sensor_graph._ns_topic is _ns_topic

    def test_ns_topic_helper_prepends_namespace(self) -> None:
        assert _ns_topic("rover", "imu") == "/rover/imu"
        assert _ns_topic("alpha", "rgb/image_raw") == "/alpha/rgb/image_raw"


class TestRgbDepthImuBranches:
    """The graph must wire RGB, Depth, IMU, and LiDAR branches each off
    of ``OnTick``."""

    @pytest.fixture
    def topics(self) -> dict:
        return {
            "imu": "imu",
            "rgb": "rgb/image_raw",
            "depth": "depth/image_raw",
            "lidar": "lidar/points",
        }

    def test_rgb_depth_imu_lidar_nodes_exist(self) -> None:
        names = {n for n, _ in _build_create_nodes()}
        assert {"CamRGB", "CamDepth", "PubIMU", "Lidar3DHelper"} <= names

    def test_rgb_topic_set(self, topics: dict) -> None:
        sv = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/Imu",
                camera_prim_path="/W/Cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/Lidar",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sv["CamRGB.inputs:topicName"] == "/rover/rgb/image_raw"
        assert sv["CamRGB.inputs:type"] == "rgb"

    def test_depth_topic_set(self, topics: dict) -> None:
        sv = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/Imu",
                camera_prim_path="/W/Cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/Lidar",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sv["CamDepth.inputs:topicName"] == "/rover/depth/image_raw"
        assert sv["CamDepth.inputs:type"] == "depth"

    def test_imu_topic_set(self, topics: dict) -> None:
        sv = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/Imu",
                camera_prim_path="/W/Cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/Lidar",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sv["PubIMU.inputs:topicName"] == "/rover/imu"
        assert sv["ReadIMU.inputs:imuPrim"] == ["/W/Imu"]

    def test_lidar_topic_and_type(self, topics: dict) -> None:
        sv = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/Imu",
                camera_prim_path="/W/Cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/Lidar",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sv["Lidar3DHelper.inputs:topicName"] == "/rover/lidar/points"
        assert sv["Lidar3DHelper.inputs:type"] == "point_cloud"

    def test_articulation_tf_uses_tf_raw_topic(self, topics: dict) -> None:
        """Articulation TF publishes on ``/tf_raw``, kept separate from ``/tf``.

        The OmniGraph ``PubTF`` and the rclpy ``TransformBroadcaster``
        intentionally do NOT share one ``/tf`` topic: empirically the
        two backends emit duplicated / out-of-phase frames when they
        co-publish, which jitters Nav2's TF buffer and breaks RViz.
        See memory ``feedback_no_tf_consolidation``.
        """
        sv = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/Imu",
                camera_prim_path="/W/Cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/Lidar",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sv["PubTF.inputs:topicName"] == "/tf_raw"


class TestSeedDeterminism:
    """Same inputs -> identical list outputs, every call."""

    @pytest.fixture
    def topics(self) -> dict:
        return {
            "imu": "imu",
            "rgb": "rgb/image_raw",
            "depth": "depth/image_raw",
            "lidar": "lidar/points",
        }

    def test_create_nodes_deterministic(self) -> None:
        assert _build_create_nodes() == _build_create_nodes()

    def test_connections_deterministic(self) -> None:
        assert _build_connections() == _build_connections()

    def test_set_values_deterministic(self, topics: dict) -> None:
        a = _build_set_values(
            ns="rover",
            topics=topics,
            imu_prim_path="/W/Imu",
            camera_prim_path="/W/Cam",
            camera_resolution=(640, 480),
            lidar_3d_prim_path="/W/Lidar",
            articulation_root_prim_path="/World/Rover",
            parent_anchor_prim_path="/World/odom_anchor",
        )
        b = _build_set_values(
            ns="rover",
            topics=topics,
            imu_prim_path="/W/Imu",
            camera_prim_path="/W/Cam",
            camera_resolution=(640, 480),
            lidar_3d_prim_path="/W/Lidar",
            articulation_root_prim_path="/World/Rover",
            parent_anchor_prim_path="/World/odom_anchor",
        )
        assert a == b

    def test_camera_resolution_values_cast_to_int(self, topics: dict) -> None:
        """Even if float resolution slips in, builder casts via ``int(...)``."""
        sv = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/Imu",
                camera_prim_path="/W/Cam",
                camera_resolution=(640.7, 480.3),
                lidar_3d_prim_path="/W/Lidar",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sv["RPCamera.inputs:width"] == 640
        assert sv["RPCamera.inputs:height"] == 480
