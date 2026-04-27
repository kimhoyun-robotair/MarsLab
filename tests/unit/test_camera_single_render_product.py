"""Unit tests for the Path 1 single-render-product collapse.

Path 1 of the Camera depth pipeline.  The historical layout used two
``IsaacCreateRenderProduct`` nodes (``RPCamera`` for RGB, ``RPDepth``
for depth) on the same camera prim.  Two separate SDG pipelines
yielded RGB/depth timestamp skew that broke RTAB-Map and
``depth_image_proc`` fusion.  NVIDIA's canonical pattern (see
``isaacsim/exts/isaacsim.ros2.bridge/isaacsim/ros2/bridge/impl/
og_shortcuts/og_rtx_sensors.py:75-227``) fans a single render product
out to every camera helper (RGB, Depth, PointCloud2, CameraInfo) so
they share one render pass and one timestamp.

These tests pin the new wiring so a future regression that
reintroduces ``RPDepth`` (or any second camera render product) fails
loudly at unit-test time instead of surfacing as a runtime SLAM bug.
"""

from __future__ import annotations

import pytest

from marslab.ros2_bridge.sensor_graph_builder import (
    _build_connections,
    _build_create_nodes,
    _build_set_values,
)


class TestSingleCameraRenderProduct:
    """Exactly ONE ``IsaacCreateRenderProduct`` exists for the camera."""

    def test_no_rpdepth_node_in_default_graph(self) -> None:
        """``RPDepth`` is absent from the default node list."""
        names = [n for n, _ in _build_create_nodes()]
        assert "RPDepth" not in names

    def test_no_rpdepth_node_when_pointcloud_enabled(self) -> None:
        """``RPDepth`` stays absent even when the PointCloud2 helper is on."""
        names = [n for n, _ in _build_create_nodes(include_pointcloud2=True)]
        assert "RPDepth" not in names

    def test_no_rpdepth_node_when_caminfo_enabled(self) -> None:
        """``RPDepth`` stays absent even when the CameraInfo helper is on."""
        names = [n for n, _ in _build_create_nodes(include_camera_info=True)]
        assert "RPDepth" not in names

    def test_no_rpdepth_node_when_all_helpers_enabled(self) -> None:
        """``RPDepth`` stays absent in the maximal helper configuration."""
        names = [
            n
            for n, _ in _build_create_nodes(
                include_lidar_2d=True,
                include_pointcloud2=True,
                include_camera_info=True,
            )
        ]
        assert "RPDepth" not in names

    def test_rpcamera_present_in_default_graph(self) -> None:
        """The shared ``RPCamera`` render product is always present."""
        names = [n for n, _ in _build_create_nodes()]
        assert "RPCamera" in names

    def test_only_one_camera_render_product_at_each_helper_combo(self) -> None:
        """Across every helper combination there is exactly one camera render product.

        The three render products used in the v1.0 graph
        (``RPCamera``, ``RPLidar3D``, optional ``RPLidar2D``) are
        sensor-specific; the camera helpers ALL fan off ``RPCamera``.
        """
        for include_lidar_2d in (False, True):
            for include_pcl in (False, True):
                for include_caminfo in (False, True):
                    nodes = _build_create_nodes(
                        include_lidar_2d=include_lidar_2d,
                        include_pointcloud2=include_pcl,
                        include_camera_info=include_caminfo,
                    )
                    rp_camera_count = sum(
                        1
                        for name, node_type in nodes
                        if name == "RPCamera"
                        and node_type == "isaacsim.core.nodes.IsaacCreateRenderProduct"
                    )
                    assert rp_camera_count == 1, (
                        f"Expected exactly one RPCamera render product, found "
                        f"{rp_camera_count} (lidar_2d={include_lidar_2d}, "
                        f"pointcloud2={include_pcl}, camera_info={include_caminfo})"
                    )


class TestAllCameraHelpersBindToRPCamera:
    """RGB / Depth / PointCloud2 / CameraInfo all consume the same ``RPCamera``."""

    def test_camrgb_consumes_rpcamera(self) -> None:
        edges = set(_build_connections())
        assert (
            "RPCamera.outputs:renderProductPath",
            "CamRGB.inputs:renderProductPath",
        ) in edges
        assert ("RPCamera.outputs:execOut", "CamRGB.inputs:execIn") in edges

    def test_camdepth_consumes_rpcamera(self) -> None:
        """``CamDepth`` is rewired off the shared ``RPCamera`` (was ``RPDepth``)."""
        edges = set(_build_connections())
        assert (
            "RPCamera.outputs:renderProductPath",
            "CamDepth.inputs:renderProductPath",
        ) in edges
        assert ("RPCamera.outputs:execOut", "CamDepth.inputs:execIn") in edges

    def test_no_rpdepth_edges_anywhere(self) -> None:
        """No edge mentions the retired ``RPDepth`` node."""
        for include_pcl in (False, True):
            for include_caminfo in (False, True):
                edges = _build_connections(
                    include_pointcloud2=include_pcl,
                    include_camera_info=include_caminfo,
                )
                for src, dst in edges:
                    assert "RPDepth" not in src, src
                    assert "RPDepth" not in dst, dst

    def test_campcl_consumes_rpcamera(self) -> None:
        edges = set(_build_connections(include_pointcloud2=True))
        assert (
            "RPCamera.outputs:renderProductPath",
            "CamPCL.inputs:renderProductPath",
        ) in edges

    def test_caminfo_consumes_rpcamera(self) -> None:
        edges = set(_build_connections(include_camera_info=True))
        assert (
            "RPCamera.outputs:renderProductPath",
            "CamInfo.inputs:renderProductPath",
        ) in edges

    def test_all_camera_helpers_consume_rpcamera_simultaneously(self) -> None:
        """Maximal config: RGB + Depth + PointCloud2 + CameraInfo all on ``RPCamera``."""
        edges = set(_build_connections(include_pointcloud2=True, include_camera_info=True))
        consumers = ("CamRGB", "CamDepth", "CamPCL", "CamInfo")
        for consumer in consumers:
            assert (
                "RPCamera.outputs:renderProductPath",
                f"{consumer}.inputs:renderProductPath",
            ) in edges, f"{consumer} must bind to the shared RPCamera render product"


class TestHelperResetSimulationTimeOnStop:
    """``resetSimulationTimeOnStop=True`` is set on every helper consumer.

    Verified against the OGN spec: ``IsaacCreateRenderProduct`` does NOT
    expose this attribute (``OgnIsaacCreateRenderProduct.ogn:12-37``).
    The flag belongs on each ROS2 helper -- see canonical wiring at
    ``isaacsim.ros2.bridge/.../og_rtx_sensors.py:87,160,189,217``.
    """

    @pytest.fixture
    def topics(self) -> dict:
        return {
            "imu": "imu",
            "rgb": "rgb/image_raw",
            "depth": "depth/image_raw",
            "lidar": "lidar/points",
            "points": "depth/points",
            "camera_info": "rgb/camera_info",
            "scan": "scan",
        }

    def test_rpcamera_does_not_carry_reset_flag(self, topics: dict) -> None:
        """Regression guard: the flag must NOT be on RPCamera.

        Setting it on ``IsaacCreateRenderProduct`` raises
        ``OmniGraphError: Attribute named 'inputs:resetSimulationTimeOnStop'
        does not refer to a legal og.Attribute`` at runtime and crashes
        Kit on shutdown via the SDG plugin teardown path.
        """
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
                include_pointcloud2=True,
                include_camera_info=True,
                lidar_2d_prim_path="/W/lidar2d",
            )
        )
        assert "RPCamera.inputs:resetSimulationTimeOnStop" not in sets
        assert "RPLidar2D.inputs:resetSimulationTimeOnStop" not in sets
        assert "RPLidar3D.inputs:resetSimulationTimeOnStop" not in sets

    def test_camera_helpers_have_reset_flag(self, topics: dict) -> None:
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
                include_pointcloud2=True,
                include_camera_info=True,
            )
        )
        assert sets["CamRGB.inputs:resetSimulationTimeOnStop"] is True
        assert sets["CamDepth.inputs:resetSimulationTimeOnStop"] is True
        assert sets["CamPCL.inputs:resetSimulationTimeOnStop"] is True
        assert sets["CamInfo.inputs:resetSimulationTimeOnStop"] is True

    def test_lidar_helpers_have_reset_flag(self, topics: dict) -> None:
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
                lidar_2d_prim_path="/W/lidar2d",
            )
        )
        assert sets["Lidar3DHelper.inputs:resetSimulationTimeOnStop"] is True
        assert sets["Lidar2DHelper.inputs:resetSimulationTimeOnStop"] is True
