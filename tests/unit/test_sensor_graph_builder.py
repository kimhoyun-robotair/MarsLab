"""Unit tests for marslab.ros2_bridge.sensor_graph_builder helpers (no Isaac Sim)."""

from __future__ import annotations

import pytest


class TestBuildCreateNodes:
    def test_returns_expected_node_type_mapping(self) -> None:
        from marslab.ros2_bridge.sensor_graph_builder import _build_create_nodes

        nodes = dict(_build_create_nodes())
        assert nodes["OnTick"] == "omni.graph.action.OnPlaybackTick"
        assert nodes["ReadSimTime"] == "isaacsim.core.nodes.IsaacReadSimulationTime"
        assert nodes["PubTF"] == "isaacsim.ros2.bridge.ROS2PublishRawTransformTree"
        assert nodes["Lidar3DHelper"] == "isaacsim.ros2.bridge.ROS2RtxLidarHelper"

    def test_node_list_has_no_duplicates(self) -> None:
        from marslab.ros2_bridge.sensor_graph_builder import _build_create_nodes

        names = [n for n, _ in _build_create_nodes()]
        assert len(names) == len(set(names))


class TestBuildConnections:
    def test_every_endpoint_refers_to_declared_node(self) -> None:
        from marslab.ros2_bridge.sensor_graph_builder import (
            _build_connections,
            _build_create_nodes,
        )

        declared = {n for n, _ in _build_create_nodes()}
        for src, dst in _build_connections():
            assert src.split(".", 1)[0] in declared, src
            assert dst.split(".", 1)[0] in declared, dst

    def test_imu_triad_wires_all_three_measurements(self) -> None:
        from marslab.ros2_bridge.sensor_graph_builder import _build_connections

        edges = set(_build_connections())
        assert ("ReadIMU.outputs:angVel", "PubIMU.inputs:angularVelocity") in edges
        assert ("ReadIMU.outputs:linAcc", "PubIMU.inputs:linearAcceleration") in edges
        assert ("ReadIMU.outputs:orientation", "PubIMU.inputs:orientation") in edges


class TestBuildSetValues:
    @pytest.fixture
    def topics(self) -> dict:
        return {
            "imu": "imu",
            "rgb": "rgb/image_raw",
            "depth": "depth/image_raw",
            "lidar": "lidar/points",
        }

    def test_camera_resolution_is_cast_to_int(self, topics: dict) -> None:
        from marslab.ros2_bridge.sensor_graph_builder import _build_set_values

        sets = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/imu",
                camera_prim_path="/W/cam",
                camera_resolution=(640.0, 480.0),  # float in, int out
                lidar_3d_prim_path="/W/lidar3d",
            )
        )
        assert sets["RPCamera.inputs:width"] == 640
        assert isinstance(sets["RPCamera.inputs:width"], int)
        assert sets["RPCamera.inputs:height"] == 480
        assert isinstance(sets["RPCamera.inputs:height"], int)

    def test_joint_tf_goes_to_tf_raw(self, topics: dict) -> None:
        from marslab.ros2_bridge.sensor_graph_builder import _build_set_values

        sets = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/imu",
                camera_prim_path="/W/cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/lidar3d",
            )
        )
        assert sets["PubTF.inputs:topicName"] == "/tf_raw"

    def test_topic_names_namespaced(self, topics: dict) -> None:
        from marslab.ros2_bridge.sensor_graph_builder import _build_set_values

        sets = dict(
            _build_set_values(
                ns="rover0",
                topics=topics,
                imu_prim_path="/W/imu",
                camera_prim_path="/W/cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/lidar3d",
            )
        )
        assert sets["PubIMU.inputs:topicName"] == "/rover0/imu"
        assert sets["CamRGB.inputs:topicName"] == "/rover0/rgb/image_raw"
        assert sets["CamDepth.inputs:topicName"] == "/rover0/depth/image_raw"
        assert sets["Lidar3DHelper.inputs:topicName"] == "/rover0/lidar/points"


class TestBackwardCompat:
    """Old import paths stay functional via re-export."""

    def test_sensor_graph_reexports_helpers(self) -> None:
        from marslab.ros2_bridge import sensor_graph as orch
        from marslab.ros2_bridge import sensor_graph_builder as bld

        assert orch._build_create_nodes is bld._build_create_nodes
        assert orch._build_connections is bld._build_connections
        assert orch._build_set_values is bld._build_set_values
