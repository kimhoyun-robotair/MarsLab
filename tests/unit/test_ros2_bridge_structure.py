"""Import-level tests for marslab.ros2_bridge (pure-Python surface, offline)."""

from __future__ import annotations

import pytest


class TestPackageSurface:
    def test_toplevel_exports(self) -> None:
        import marslab.ros2_bridge as bridge

        for name in (
            "BridgeContext",
            "GRAPH_PATH",
            "OdometryPublisherContext",
            "SensorGraphHandle",
            "build_sensor_graph",
            "build_static_sensor_transforms",
            "create_cmd_vel_subscriber",
            "create_odometry_publisher",
            "init_rclpy_side",
            "publish_odometry",
            "publish_static_sensor_tfs",
        ):
            assert hasattr(bridge, name), f"missing public symbol: {name}"

    def test_graph_path_has_stage3_marker(self) -> None:
        from marslab.ros2_bridge import GRAPH_PATH

        assert "Stage3" in GRAPH_PATH
        assert GRAPH_PATH.startswith("/World/")


class TestSensorGraphOfflineHelpers:
    """The private builders are pure — no Isaac Sim imports."""

    def test_create_nodes_lists_required_sensors(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _build_create_nodes

        nodes = [n for n, _ in _build_create_nodes()]
        # C2+: ``PubJointState`` replaced ``PubTF`` as the canonical TF
        # authority (ROS-standard ``robot_state_publisher`` workflow).
        for required in (
            "OnTick",
            "ReadSimTime",
            "PubClock",
            "PubJointState",
            "ReadIMU",
            "PubIMU",
            "CamRGB",
            "CamDepth",
            "Lidar3DHelper",
        ):
            assert required in nodes

    def test_connections_reference_only_declared_nodes(self) -> None:
        from marslab.ros2_bridge.sensor_graph import (
            _build_connections,
            _build_create_nodes,
        )

        declared = {n for n, _ in _build_create_nodes()}
        for src, dst in _build_connections():
            src_node = src.split(".", 1)[0]
            dst_node = dst.split(".", 1)[0]
            assert src_node in declared, f"undeclared source node: {src_node}"
            assert dst_node in declared, f"undeclared dest node: {dst_node}"

    def test_set_values_publishes_joint_states(self) -> None:
        """C2+: ``ROS2PublishJointState`` publishes on ``<ns>/joint_states``.

        ROS-side ``robot_state_publisher`` reads ``/joint_states`` +
        the latched ``/robot_description`` and emits the full link
        tree TF on the canonical ``/tf`` topic.  Single TF authority
        replaces the legacy ``PubTF``-on-``/tf_raw`` +
        ``topic_tools relay`` workflow.
        """
        from marslab.ros2_bridge.sensor_graph import _build_set_values

        sets = _build_set_values(
            ns="rover",
            topics={
                "imu": "imu",
                "rgb": "rgb/image_raw",
                "depth": "depth/image_raw",
                "lidar": "lidar/points",
                "joint_states": "joint_states",
            },
            imu_prim_path="/World/Rover/imu",
            camera_prim_path="/World/Rover/camera",
            camera_resolution=(640, 480),
            lidar_3d_prim_path="/World/Rover/lidar3d",
            articulation_root_prim_path="/World/Rover",
            parent_anchor_prim_path="/World/odom_anchor",
        )
        as_dict = dict(sets)
        assert as_dict["PubJointState.inputs:topicName"] == "/rover/joint_states"
        assert "PubTF.inputs:topicName" not in as_dict

    def test_set_values_namespaces_imu_and_rgb(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _build_set_values

        sets = dict(
            _build_set_values(
                ns="rover",
                topics={
                    "imu": "imu",
                    "rgb": "rgb/image_raw",
                    "depth": "depth/image_raw",
                    "lidar": "lidar/points",
                },
                imu_prim_path="/World/Rover/imu",
                camera_prim_path="/World/Rover/camera",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/World/Rover/lidar3d",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
            )
        )
        assert sets["PubIMU.inputs:topicName"] == "/rover/imu"
        assert sets["CamRGB.inputs:topicName"] == "/rover/rgb/image_raw"
        assert sets["Lidar3DHelper.inputs:topicName"] == "/rover/lidar/points"


class TestTfBroadcasterValidation:
    """build_static_sensor_transforms imports ``geometry_msgs`` lazily."""

    def test_rejects_bad_translation_length(self) -> None:
        pytest.importorskip("geometry_msgs")
        from marslab.ros2_bridge.tf_broadcaster import (
            build_static_sensor_transforms,
        )

        with pytest.raises(ValueError, match="3 elements"):
            build_static_sensor_transforms([("camera_link", [0.0, 1.0])])

    def test_translation_broadcast_is_identity(self) -> None:
        """YAML local_translation is in the REP-103 base_link frame.

        With the spawn-time 180-degree X-roll removed, ``base_link``
        aligns with REP-103 (X forward, Y left, Z up) and
        ``local_translation`` broadcasts as-is.
        """
        pytest.importorskip("geometry_msgs")
        from marslab.ros2_bridge.tf_broadcaster import (
            build_static_sensor_transforms,
        )

        msgs = build_static_sensor_transforms([("camera_link", [0.3, 0.2, -2.1])])
        assert len(msgs) == 1
        t = msgs[0].transform.translation
        assert t.x == pytest.approx(0.3)
        assert t.y == pytest.approx(0.2)
        assert t.z == pytest.approx(-2.1)
