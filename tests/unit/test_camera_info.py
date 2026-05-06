"""Unit tests for the RGB ``CameraInfo`` OmniGraph wiring.

The wiring adds an ``isaacsim.ros2.bridge.ROS2CameraInfoHelper`` node
fed off the existing RGB render product so the camera publishes
``sensor_msgs/CameraInfo`` (intrinsics K / P / R / D, width, height)
in lock-step with ``rgb/image_raw``. Source citations:

* ``isaacsim/exts/isaacsim.ros2.bridge/docs/ogn/
  OgnROS2CameraInfoHelper.rst`` -- *"This node automates the
  CameraInfo message pipeline for monocular and stereo cameras."*
* ``OgnROS2CameraInfoHelper.rst`` -- input list confirms ``execIn``,
  ``renderProductPath``, ``topicName``, ``frameId``, ``qosProfile``
  are all that the node accepts; intrinsics are derived internally
  from the underlying USD ``Camera`` prim.

These tests stay offline: the OmniGraph orchestrator is exercised via
``unittest.mock`` so no Isaac Sim or GPU is required. The pure
list-builders (``_build_create_nodes`` / ``_build_connections`` /
``_build_set_values``) are import-clean Python.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from marslab.ros2_bridge.sensor_graph_builder import (
    _build_connections,
    _build_create_nodes,
    _build_set_values,
)


@pytest.fixture
def topics() -> dict:
    """Default ``rover.ros2.topics`` block including the new ``camera_info`` key."""
    return {
        "imu": "imu",
        "rgb": "rgb/image_raw",
        "depth": "depth/image_raw",
        "points": "depth/points",
        "camera_info": "rgb/camera_info",
        "lidar": "lidar/points",
    }


class TestBuildCreateNodesCameraInfo:
    """``_build_create_nodes`` appends ``CamInfo`` only when requested."""

    def test_camera_info_absent_by_default(self) -> None:
        names = [n for n, _ in _build_create_nodes()]
        assert "CamInfo" not in names

    def test_camera_info_appended_when_flag_true(self) -> None:
        nodes = dict(_build_create_nodes(include_camera_info=True))
        assert "CamInfo" in nodes
        assert nodes["CamInfo"] == "isaacsim.ros2.bridge.ROS2CameraInfoHelper"

    def test_camera_info_does_not_add_render_product(self) -> None:
        """``CamInfo`` reuses ``RPCamera`` -- no extra IsaacCreateRenderProduct."""
        nodes_off = [n for n, _ in _build_create_nodes(include_camera_info=False)]
        nodes_on = [n for n, _ in _build_create_nodes(include_camera_info=True)]
        added = set(nodes_on) - set(nodes_off)
        assert added == {"CamInfo"}

    def test_camera_info_combines_with_pointcloud2_and_lidar2d(self) -> None:
        """All three flags can be true simultaneously; node names stay unique."""
        nodes = _build_create_nodes(
            include_lidar_2d=True,
            include_pointcloud2=True,
            include_camera_info=True,
        )
        names = [n for n, _ in nodes]
        assert len(names) == len(set(names))
        assert {"CamInfo", "CamPCL", "Lidar2DHelper", "RPLidar2D"} <= set(names)


class TestBuildConnectionsCameraInfo:
    """Edges for the ``CamInfo`` helper trigger off OnTick + share RPCamera."""

    def test_camera_info_edges_absent_by_default(self) -> None:
        edges = set(_build_connections())
        assert ("OnTick.outputs:tick", "CamInfo.inputs:execIn") not in edges

    def test_camera_info_edges_present_when_flag_true(self) -> None:
        edges = set(_build_connections(include_camera_info=True))
        assert ("OnTick.outputs:tick", "CamInfo.inputs:execIn") in edges
        assert (
            "RPCamera.outputs:renderProductPath",
            "CamInfo.inputs:renderProductPath",
        ) in edges

    def test_camera_info_uses_shared_rpcamera_render_product(self) -> None:
        """``CamInfo`` is wired off the shared ``RPCamera`` render product.

        The OmniGraph CameraInfo Helper extracts intrinsics from the
        underlying USD ``Camera`` prim every tick.  Reusing the single
        shared ``RPCamera`` render product (Path 1 collapse) keeps the
        intrinsics timestamp-aligned with ``rgb/image_raw`` and depth,
        which downstream ``image_proc`` / ``depth_image_proc`` /
        RTAB-Map rectify nodes assume.
        """
        edges = set(_build_connections(include_camera_info=True))
        feeders = {(s, d) for (s, d) in edges if d == "CamInfo.inputs:renderProductPath"}
        assert len(feeders) == 1
        src, _ = feeders.pop()
        assert src == "RPCamera.outputs:renderProductPath"

    def test_every_endpoint_refers_to_declared_node(self) -> None:
        declared = {n for n, _ in _build_create_nodes(include_camera_info=True)}
        for src, dst in _build_connections(include_camera_info=True):
            assert src.split(".", 1)[0] in declared, src
            assert dst.split(".", 1)[0] in declared, dst


class TestBuildSetValuesCameraInfo:
    """SET_VALUES bind the topic name, the optical frame, and the QoS preset."""

    def test_camera_info_values_absent_by_default(self, topics: dict) -> None:
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
        assert "CamInfo.inputs:topicName" not in sv

    def test_camera_info_topic_namespaced(self, topics: dict) -> None:
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
                include_camera_info=True,
            )
        )
        assert sv["CamInfo.inputs:topicName"] == "/rover/rgb/camera_info"

    def test_camera_info_frame_id_is_camera_optical_frame(self, topics: dict) -> None:
        """``CameraInfo`` frame_id matches RGB / Depth / PointCloud2 (REP-105).

        Visual SLAM pipelines (RTAB-Map, ORB-SLAM3) require the
        ``CameraInfo`` ``header.frame_id`` to match the corresponding
        ``Image`` header.  Both reference ``camera_optical_frame``.
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
                include_camera_info=True,
            )
        )
        assert sv["CamInfo.inputs:frameId"] == "camera_optical_frame"
        assert sv["CamRGB.inputs:frameId"] == "camera_optical_frame"

    def test_camera_info_qos_reuses_sensor_preset(self, topics: dict) -> None:
        """QoS comes from the ``sensor_qos_preset`` argument (BEST_EFFORT)."""
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
                sensor_qos_preset="SensorData",
                include_camera_info=True,
            )
        )
        assert sv["CamInfo.inputs:qosProfile"] == "SensorData"

    def test_camera_info_skipped_when_topic_key_absent(self) -> None:
        """No ``camera_info`` key -> SET_VALUES omits the CamInfo bindings.

        Mirrors the ``points`` guard so a scenario YAML can disable a
        single helper by removing its topic key without flipping the
        schema flag.
        """
        no_caminfo_topics = {
            "imu": "imu",
            "rgb": "rgb/image_raw",
            "depth": "depth/image_raw",
            "lidar": "lidar/points",
        }
        sv = dict(
            _build_set_values(
                ns="rover",
                topics=no_caminfo_topics,
                imu_prim_path="/W/Imu",
                camera_prim_path="/W/Cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/Lidar",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
                include_camera_info=True,
            )
        )
        assert "CamInfo.inputs:topicName" not in sv

    def test_camera_info_does_not_forward_resolution(self, topics: dict) -> None:
        """``ROS2CameraInfoHelper`` derives width/height from the render product.

        Asserting the absence of width/height bindings on the CamInfo
        node guards against a future regression where someone tries to
        duplicate the RPCamera resolution onto the CameraInfo helper
        (the node has no such input -- per
        ``OgnROS2CameraInfoHelper.rst:32-52``).
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
                include_camera_info=True,
            )
        )
        assert "CamInfo.inputs:width" not in sv
        assert "CamInfo.inputs:height" not in sv


class TestSchemaPublishCameraInfo:
    """``Ros2BridgeConfig.publish_camera_info`` defaults to True."""

    def test_default_is_true(self) -> None:
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        cfg = Ros2BridgeConfig()
        assert cfg.publish_camera_info is True

    def test_explicit_false_accepted(self) -> None:
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        cfg = Ros2BridgeConfig(publish_camera_info=False)
        assert cfg.publish_camera_info is False

    def test_extra_keys_still_forbidden(self) -> None:
        """``extra='forbid'`` from the parent schema must still apply."""
        from pydantic import ValidationError

        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError):
            Ros2BridgeConfig(publish_camera_information=True)  # typo.


class TestResolvePublishCameraInfo:
    """``Ros2BridgeConfig.publish_camera_info`` is the canonical knob.

    The orchestrator reads it via ``_resolve_ros2_bridge_options`` --
    these tests exercise the same path the production code takes.
    """

    def test_absent_key_returns_schema_default(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_ros2_bridge_options

        assert bool(_resolve_ros2_bridge_options({"namespace": "rover"}).publish_camera_info) is True

    def test_explicit_true_returned(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_ros2_bridge_options

        assert (
            bool(_resolve_ros2_bridge_options({"publish_camera_info": True}).publish_camera_info)
            is True
        )

    def test_explicit_false_returned(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_ros2_bridge_options

        assert (
            bool(_resolve_ros2_bridge_options({"publish_camera_info": False}).publish_camera_info)
            is False
        )


class TestBuildSensorGraphCameraInfoInvocation:
    """Mock OmniGraph; verify ``build_sensor_graph`` wires ``CamInfo`` end-to-end.

    OmniGraph (``omni.graph.core``) is not importable without Isaac Sim, so we
    install a fake module on ``sys.modules`` before calling
    ``build_sensor_graph``.  The fake records every ``og.Controller.edit``
    call so we can assert the expected node / edge / set-value lists were
    submitted.
    """

    @pytest.fixture
    def mock_og(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        og = types.ModuleType("omni.graph.core")
        controller = MagicMock(name="Controller")
        controller.Keys = types.SimpleNamespace(
            CREATE_NODES="CREATE_NODES",
            CONNECT="CONNECT",
            SET_VALUES="SET_VALUES",
        )
        controller.edit = MagicMock(
            return_value=(MagicMock(), MagicMock(), MagicMock(), MagicMock())
        )
        og.Controller = controller  # type: ignore[attr-defined]
        omni = sys.modules.get("omni") or types.ModuleType("omni")
        graph_mod = sys.modules.get("omni.graph") or types.ModuleType("omni.graph")
        monkeypatch.setitem(sys.modules, "omni", omni)
        monkeypatch.setitem(sys.modules, "omni.graph", graph_mod)
        monkeypatch.setitem(sys.modules, "omni.graph.core", og)
        return controller

    def test_build_sensor_graph_appends_caminfo_when_flag_true(
        self, mock_og: MagicMock, topics: dict
    ) -> None:
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": topics,
            "publish_camera_info": True,
        }
        build_sensor_graph(
            ros2_cfg=ros2_cfg,
            camera_prim_path="/World/Cam",
            camera_resolution=(640, 480),
            lidar_3d_prim_path="/World/Lidar3D",
            imu_prim_path="/World/IMU",
            articulation_root_prim_path="/World/Rover",
            parent_anchor_prim_path="/World/odom_anchor",
        )
        _, mutations = mock_og.edit.call_args.args
        node_names = [n for n, _ in mutations["CREATE_NODES"]]
        edges = mutations["CONNECT"]
        values = dict(mutations["SET_VALUES"])

        assert "CamInfo" in node_names
        assert ("OnTick.outputs:tick", "CamInfo.inputs:execIn") in edges
        assert (
            "RPCamera.outputs:renderProductPath",
            "CamInfo.inputs:renderProductPath",
        ) in edges
        assert values["CamInfo.inputs:topicName"] == "/rover/rgb/camera_info"
        assert values["CamInfo.inputs:frameId"] == "camera_optical_frame"

    def test_build_sensor_graph_skips_caminfo_when_flag_false(
        self, mock_og: MagicMock, topics: dict
    ) -> None:
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": topics,
            "publish_camera_info": False,
        }
        build_sensor_graph(
            ros2_cfg=ros2_cfg,
            camera_prim_path="/World/Cam",
            camera_resolution=(640, 480),
            lidar_3d_prim_path="/World/Lidar3D",
            imu_prim_path="/World/IMU",
            articulation_root_prim_path="/World/Rover",
            parent_anchor_prim_path="/World/odom_anchor",
        )
        _, mutations = mock_og.edit.call_args.args
        node_names = [n for n, _ in mutations["CREATE_NODES"]]
        values = dict(mutations["SET_VALUES"])
        assert "CamInfo" not in node_names
        assert "CamInfo.inputs:topicName" not in values

    def test_build_sensor_graph_skips_caminfo_when_topic_missing(self, mock_og: MagicMock) -> None:
        """Even with the flag on, no ``topics["camera_info"]`` -> no CameraInfo helper."""
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": {
                "imu": "imu",
                "rgb": "rgb/image_raw",
                "depth": "depth/image_raw",
                "lidar": "lidar/points",
            },
            "publish_camera_info": True,
        }
        build_sensor_graph(
            ros2_cfg=ros2_cfg,
            camera_prim_path="/World/Cam",
            camera_resolution=(640, 480),
            lidar_3d_prim_path="/World/Lidar3D",
            imu_prim_path="/World/IMU",
            articulation_root_prim_path="/World/Rover",
            parent_anchor_prim_path="/World/odom_anchor",
        )
        _, mutations = mock_og.edit.call_args.args
        node_names = [n for n, _ in mutations["CREATE_NODES"]]
        assert "CamInfo" not in node_names

    def test_build_sensor_graph_default_includes_caminfo(
        self, mock_og: MagicMock, topics: dict
    ) -> None:
        """Default (key absent in YAML) wires the CameraInfo helper."""
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": topics,
            # publish_camera_info intentionally omitted.
        }
        build_sensor_graph(
            ros2_cfg=ros2_cfg,
            camera_prim_path="/World/Cam",
            camera_resolution=(640, 480),
            lidar_3d_prim_path="/World/Lidar3D",
            imu_prim_path="/World/IMU",
            articulation_root_prim_path="/World/Rover",
            parent_anchor_prim_path="/World/odom_anchor",
        )
        _, mutations = mock_og.edit.call_args.args
        node_names = [n for n, _ in mutations["CREATE_NODES"]]
        assert "CamInfo" in node_names
