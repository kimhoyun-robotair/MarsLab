"""Unit tests for marslab.ros2_bridge.sensor_graph_builder helpers (no Isaac Sim)."""

from __future__ import annotations

import pytest


class TestBuildCreateNodes:
    def test_returns_expected_node_type_mapping(self) -> None:
        """C2+ default: PubJointState replaces PubTF."""
        from marslab.ros2_bridge.sensor_graph_builder import _build_create_nodes

        nodes = dict(_build_create_nodes())
        assert nodes["OnTick"] == "omni.graph.action.OnPlaybackTick"
        assert nodes["ReadSimTime"] == "isaacsim.core.nodes.IsaacReadSimulationTime"
        # ROS-standard pattern: Isaac Sim publishes joint state, ROS
        # ``robot_state_publisher`` reads URDF + joint_state and emits
        # the full /tf tree.  Replaces the legacy ``PubTF``-on-
        # ``/tf_raw`` workflow that required ``topic_tools relay``.
        assert nodes["PubJointState"] == "isaacsim.ros2.bridge.ROS2PublishJointState"
        assert "PubTF" not in nodes
        assert nodes["Lidar3DHelper"] == "isaacsim.ros2.bridge.ROS2RtxLidarHelper"

    def test_legacy_pubtf_still_buildable(self) -> None:
        """``publish_joint_states=False`` restores the legacy PubTF wiring."""
        from marslab.ros2_bridge.sensor_graph_builder import _build_create_nodes

        nodes = dict(_build_create_nodes(publish_joint_states=False))
        assert nodes["PubTF"] == "isaacsim.ros2.bridge.ROS2PublishTransformTree"
        assert "PubJointState" not in nodes

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
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sets["RPCamera.inputs:width"] == 640
        assert isinstance(sets["RPCamera.inputs:width"], int)
        assert sets["RPCamera.inputs:height"] == 480
        assert isinstance(sets["RPCamera.inputs:height"], int)

    def test_camera_resolution_only_set_on_rpcamera(self, topics: dict) -> None:
        """Single shared render product: width/height live on ``RPCamera`` only.

        After the Path 1 collapse there is no ``RPDepth`` node and no
        secondary render product.  This test guards against a regression
        where someone reintroduces dual-render-product wiring (which
        previously caused RGB/depth timestamp skew breaking RTAB-Map).
        """
        from marslab.ros2_bridge.sensor_graph_builder import _build_set_values

        sets = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/imu",
                camera_prim_path="/W/cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/lidar3d",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert "RPDepth.inputs:width" not in sets
        assert "RPDepth.inputs:height" not in sets
        assert "RPDepth.inputs:cameraPrim" not in sets

    def test_joint_state_publishes_on_canonical_topic(self, topics: dict) -> None:
        """C2+ default: ``ROS2PublishJointState`` replaces ``PubTF``.

        ROS-side ``robot_state_publisher`` consuming ``/joint_states`` +
        the latched ``/robot_description`` produces the full link-tree
        TF on the canonical ``/tf`` topic.  Single TF authority -- no
        ``topic_tools relay`` required.  Topic name is namespaced and
        comes from ``ros2.topics.joint_states``.
        """
        from marslab.ros2_bridge.sensor_graph_builder import _build_set_values

        topics_with_js = dict(topics)
        topics_with_js["joint_states"] = "joint_states"
        sets = dict(
            _build_set_values(
                ns="rover",
                topics=topics_with_js,
                imu_prim_path="/W/imu",
                camera_prim_path="/W/cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/lidar3d",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sets["PubJointState.inputs:topicName"] == "/rover/joint_states"
        # Legacy PubTF must not coexist; running both would yield two
        # authorities for the kinematic chain.
        assert "PubTF.inputs:topicName" not in sets

    def test_legacy_pubtf_topic_when_publish_joint_states_false(self, topics: dict) -> None:
        """``publish_joint_states=False`` restores ``PubTF.inputs:topicName='/tf_raw'``.

        Backwards-compat path for v0.7 scenarios that rely on
        ``topic_tools relay /tf_raw /tf``.  Pinning the topic name
        guards against a regression that would silently swap the
        relay-driven workflow.
        """
        from marslab.ros2_bridge.sensor_graph_builder import _build_set_values

        sets = dict(
            _build_set_values(
                ns="rover",
                topics=topics,
                imu_prim_path="/W/imu",
                camera_prim_path="/W/cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/lidar3d",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
                publish_joint_states=False,
            )
        )
        assert sets["PubTF.inputs:topicName"] == "/tf_raw"
        assert "PubJointState.inputs:topicName" not in sets

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
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
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
