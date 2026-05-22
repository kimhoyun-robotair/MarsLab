"""Unit tests for the RGB-D depth -> PointCloud2 OmniGraph wiring.

The wiring adds a second ``isaacsim.ros2.bridge.ROS2CameraHelper``
node fed off the existing depth render product with
``inputs:type='depth_pcl'`` so the RGB-D camera publishes a
``sensor_msgs/PointCloud2`` topic at the depth-camera rate
(RealSense D435/D455-style). Source citation:

* ``isaacsim/exts/isaacsim.ros2.bridge/isaacsim/ros2/bridge/ogn/python/
  nodes/OgnROS2CameraHelper.py`` -- the ``depth_pcl`` token routes
  through ``ROS2PublishPointCloud`` with ``DistanceToImagePlane`` as
  the source render variable.
* ``isaacsim/exts/isaacsim.ros2.bridge/ogn/docs/OgnROS2CameraHelper.rst``
  -- allowed-tokens list confirms ``depth_pcl`` is a valid value for
  ``inputs:type``.

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
    """Default ``rover.ros2.topics`` block including the new ``points`` key."""
    return {
        "imu": "imu",
        "rgb": "rgb/image_raw",
        "depth": "depth/image_raw",
        "points": "depth/points",
        "lidar": "lidar/points",
    }


class TestBuildCreateNodesPointCloud2:
    """``_build_create_nodes`` appends ``CamPCL`` only when requested."""

    def test_pointcloud2_absent_by_default(self) -> None:
        names = [n for n, _ in _build_create_nodes()]
        assert "CamPCL" not in names

    def test_pointcloud2_appended_when_flag_true(self) -> None:
        nodes = dict(_build_create_nodes(include_pointcloud2=True))
        assert "CamPCL" in nodes
        assert nodes["CamPCL"] == "isaacsim.ros2.bridge.ROS2CameraHelper"

    def test_pointcloud2_does_not_add_render_product(self) -> None:
        """``CamPCL`` reuses the shared ``RPCamera`` -- no extra IsaacCreateRenderProduct."""
        nodes_off = [n for n, _ in _build_create_nodes(include_pointcloud2=False)]
        nodes_on = [n for n, _ in _build_create_nodes(include_pointcloud2=True)]
        # Exactly one node is added (CamPCL) and it is not a RenderProduct.
        added = set(nodes_on) - set(nodes_off)
        assert added == {"CamPCL"}

    def test_pointcloud2_combines_with_lidar_2d(self) -> None:
        """Both flags can be true simultaneously; node names stay unique."""
        nodes = _build_create_nodes(include_lidar_2d=True, include_pointcloud2=True)
        names = [n for n, _ in nodes]
        assert len(names) == len(set(names))
        assert {"CamPCL", "Lidar2DHelper", "RPLidar2D"} <= set(names)


class TestBuildConnectionsPointCloud2:
    """Edges for the ``CamPCL`` helper trigger off OnTick + share ``RPCamera``."""

    def test_pointcloud2_edges_absent_by_default(self) -> None:
        edges = set(_build_connections())
        assert ("OnTick.outputs:tick", "CamPCL.inputs:execIn") not in edges

    def test_pointcloud2_edges_present_when_flag_true(self) -> None:
        edges = set(_build_connections(include_pointcloud2=True))
        assert ("OnTick.outputs:tick", "CamPCL.inputs:execIn") in edges
        # Path 1 collapse: ``CamPCL`` consumes the single shared
        # ``RPCamera`` render product so RGB / Depth / PointCloud2
        # stay frame-locked on one render pass.
        assert (
            "RPCamera.outputs:renderProductPath",
            "CamPCL.inputs:renderProductPath",
        ) in edges

    def test_no_dedicated_pointcloud_render_product(self) -> None:
        """``CamPCL`` is wired off the shared ``RPCamera``, not a new render product."""
        edges = set(_build_connections(include_pointcloud2=True))
        bad = {(s, d) for (s, d) in edges if d == "CamPCL.inputs:renderProductPath"}
        # Only one feed and it must come from the shared RPCamera.
        assert len(bad) == 1
        src, _ = bad.pop()
        assert src == "RPCamera.outputs:renderProductPath"

    def test_every_endpoint_refers_to_declared_node(self) -> None:
        declared = {n for n, _ in _build_create_nodes(include_pointcloud2=True)}
        for src, dst in _build_connections(include_pointcloud2=True):
            assert src.split(".", 1)[0] in declared, src
            assert dst.split(".", 1)[0] in declared, dst


class TestBuildSetValuesPointCloud2:
    """SET_VALUES bind the ``depth_pcl`` type, the namespaced topic, and QoS."""

    def test_pointcloud2_values_absent_by_default(self, topics: dict) -> None:
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
        assert "CamPCL.inputs:type" not in sv

    def test_pointcloud2_type_token_is_depth_pcl(self, topics: dict) -> None:
        """Allowed-token list (OgnROS2CameraHelper.rst:53) requires ``depth_pcl``."""
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
                include_pointcloud2=True,
            )
        )
        assert sv["CamPCL.inputs:type"] == "depth_pcl"

    def test_pointcloud2_topic_namespaced(self, topics: dict) -> None:
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
                include_pointcloud2=True,
            )
        )
        assert sv["CamPCL.inputs:topicName"] == "/rover/depth/points"

    def test_pointcloud2_frame_id_is_camera_optical_frame(self, topics: dict) -> None:
        """frame_id is the optical-convention child frame.

        Isaac Sim's ROS2CameraHelper emits PointCloud2 in the optical
        frame convention (Z forward, X right, Y down). The static TF
        ``camera_link -> camera_optical_frame`` is published by
        ``tf_broadcaster.publish_static_sensor_tfs``; both depth and
        PointCloud2 reference the optical frame so RViz /
        image_pipeline / depth_image_proc see correct geometry.
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
                include_pointcloud2=True,
            )
        )
        assert sv["CamPCL.inputs:frameId"] == "camera_optical_frame"
        # RGB and Depth must agree — they share the same image_pipeline contract.
        assert sv["CamRGB.inputs:frameId"] == "camera_optical_frame"
        assert sv["CamDepth.inputs:frameId"] == "camera_optical_frame"

    def test_pointcloud2_qos_reuses_sensor_preset(self, topics: dict) -> None:
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
                include_pointcloud2=True,
            )
        )
        assert sv["CamPCL.inputs:qosProfile"] == "SensorData"

    def test_pointcloud2_skipped_when_topic_key_absent(self) -> None:
        """No ``points`` key -> SET_VALUES omits the CamPCL bindings."""
        no_points_topics = {
            "imu": "imu",
            "rgb": "rgb/image_raw",
            "depth": "depth/image_raw",
            "lidar": "lidar/points",
        }
        sv = dict(
            _build_set_values(
                ns="rover",
                topics=no_points_topics,
                imu_prim_path="/W/Imu",
                camera_prim_path="/W/Cam",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/W/Lidar",
                articulation_root_prim_path="/World/Rover",
                parent_anchor_prim_path="/World/odom_anchor",
                include_pointcloud2=True,
            )
        )
        assert "CamPCL.inputs:type" not in sv


class TestSchemaPublishPointCloud2:
    """``Ros2BridgeConfig.publish_pointcloud2`` defaults to True."""

    def test_default_is_true(self) -> None:
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        cfg = Ros2BridgeConfig()
        assert cfg.publish_pointcloud2 is True

    def test_explicit_false_accepted(self) -> None:
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        cfg = Ros2BridgeConfig(publish_pointcloud2=False)
        assert cfg.publish_pointcloud2 is False

    def test_extra_keys_still_forbidden(self) -> None:
        """``extra='forbid'`` from the parent schema must still apply."""
        from pydantic import ValidationError

        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError):
            Ros2BridgeConfig(publish_pointcloud_2=True)  # typo: trailing underscore.


class TestResolvePublishPointCloud2:
    """``Ros2BridgeConfig.publish_pointcloud2`` is the canonical knob.

    The orchestrator reads it via ``_resolve_ros2_bridge_options`` --
    these tests exercise the same path the production code takes.
    """

    def test_absent_key_returns_schema_default(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_ros2_bridge_options

        opts = _resolve_ros2_bridge_options({"namespace": "rover"})
        assert bool(opts.publish_pointcloud2) is True

    def test_explicit_true_returned(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_ros2_bridge_options

        assert (
            bool(_resolve_ros2_bridge_options({"publish_pointcloud2": True}).publish_pointcloud2)
            is True
        )

    def test_explicit_false_returned(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_ros2_bridge_options

        assert (
            bool(_resolve_ros2_bridge_options({"publish_pointcloud2": False}).publish_pointcloud2)
            is False
        )


class TestBuildSensorGraphCallableInvocation:
    """Mock OmniGraph; verify ``build_sensor_graph`` wires ``CamPCL`` end-to-end.

    OmniGraph (``omni.graph.core``) is not importable without Isaac Sim, so we
    install a fake module on ``sys.modules`` before calling
    ``build_sensor_graph``.  The fake records every ``og.Controller.edit``
    call so we can assert the expected node / edge / set-value lists were
    submitted -- this is the unit-test equivalent of "did Isaac Sim see the
    PointCloud2 wiring?".
    """

    @pytest.fixture
    def mock_og(self, monkeypatch: pytest.MonkeyPatch) -> MagicMock:
        """Install a fake ``omni.graph.core`` module with a Controller stub.

        The real ``og.Controller.edit`` returns a 4-tuple
        ``(graph_handle, nodes, prims, ports)``; the fake returns four
        ``MagicMock``s so the orchestrator's tuple unpacking still works.
        """
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
        # Build the parent ``omni`` and ``omni.graph`` placeholders so the
        # nested import in build_sensor_graph (`import omni.graph.core as og`)
        # resolves cleanly under monkeypatched sys.modules.
        omni = sys.modules.get("omni") or types.ModuleType("omni")
        graph_mod = sys.modules.get("omni.graph") or types.ModuleType("omni.graph")
        monkeypatch.setitem(sys.modules, "omni", omni)
        monkeypatch.setitem(sys.modules, "omni.graph", graph_mod)
        monkeypatch.setitem(sys.modules, "omni.graph.core", og)
        return controller

    def test_build_sensor_graph_invokes_controller_edit(
        self, mock_og: MagicMock, topics: dict
    ) -> None:
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": topics,
            "publish_pointcloud2": True,
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
        assert mock_og.edit.call_count == 1

    def test_build_sensor_graph_appends_campcl_when_flag_true(
        self, mock_og: MagicMock, topics: dict
    ) -> None:
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": topics,
            "publish_pointcloud2": True,
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
        # Controller.edit(setup_dict, mutations_dict) -- second positional arg.
        _, mutations = mock_og.edit.call_args.args
        node_names = [n for n, _ in mutations["CREATE_NODES"]]
        edges = mutations["CONNECT"]
        values = dict(mutations["SET_VALUES"])

        assert "CamPCL" in node_names
        assert ("OnTick.outputs:tick", "CamPCL.inputs:execIn") in edges
        # Path 1 collapse: shared ``RPCamera`` render product.
        assert (
            "RPCamera.outputs:renderProductPath",
            "CamPCL.inputs:renderProductPath",
        ) in edges
        assert values["CamPCL.inputs:type"] == "depth_pcl"
        assert values["CamPCL.inputs:topicName"] == "/rover/depth/points"
        # Optical-frame convention (REP-105).
        assert values["CamPCL.inputs:frameId"] == "camera_optical_frame"

    def test_build_sensor_graph_skips_campcl_when_flag_false(
        self, mock_og: MagicMock, topics: dict
    ) -> None:
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": topics,
            "publish_pointcloud2": False,
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
        assert "CamPCL" not in node_names
        assert "CamPCL.inputs:type" not in values

    def test_build_sensor_graph_skips_campcl_when_topic_missing(self, mock_og: MagicMock) -> None:
        """Even with the flag on, no ``topics["points"]`` -> no PointCloud2 helper."""
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": {
                "imu": "imu",
                "rgb": "rgb/image_raw",
                "depth": "depth/image_raw",
                "lidar": "lidar/points",
            },
            "publish_pointcloud2": True,
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
        assert "CamPCL" not in node_names

    def test_build_sensor_graph_default_includes_campcl(
        self, mock_og: MagicMock, topics: dict
    ) -> None:
        """Default (key absent in YAML) wires the PointCloud2 helper."""
        from marslab.ros2_bridge.sensor_graph import build_sensor_graph

        ros2_cfg = {
            "namespace": "rover",
            "topics": topics,
            # publish_pointcloud2 intentionally omitted.
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
        assert "CamPCL" in node_names
