"""Unit tests for marslab.ros2_bridge.tf_broadcaster (R8-5). Y/Z flip + quat normalization."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import pytest

from tests.unit.conftest import FakeStaticTransformBroadcaster, FakeTransformStamped


@pytest.fixture
def fake_ros2_tf_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    geo_msgs = types.ModuleType("geometry_msgs")
    geo_msgs_msg = types.ModuleType("geometry_msgs.msg")
    geo_msgs_msg.TransformStamped = FakeTransformStamped  # type: ignore[attr-defined]
    geo_msgs.msg = geo_msgs_msg  # type: ignore[attr-defined]

    tf2_ros = types.ModuleType("tf2_ros")
    tf2_ros.StaticTransformBroadcaster = FakeStaticTransformBroadcaster  # type: ignore[attr-defined]
    tf2_ros.TransformBroadcaster = MagicMock()  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "geometry_msgs", geo_msgs)
    monkeypatch.setitem(sys.modules, "geometry_msgs.msg", geo_msgs_msg)
    monkeypatch.setitem(sys.modules, "tf2_ros", tf2_ros)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTfTree:
    """Parent/child frame naming and list length."""

    def test_parent_frame_default_base_link(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        msgs = build_static_sensor_transforms([("camera_link", [0.1, 0.0, 0.5])])
        assert len(msgs) == 1
        assert msgs[0].header.frame_id == "base_link"
        assert msgs[0].child_frame_id == "camera_link"

    def test_parent_frame_override(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        msgs = build_static_sensor_transforms(
            [("lidar_link", [0.0, 0.0, 0.3])],
            parent_frame_id="chassis",
        )
        assert msgs[0].header.frame_id == "chassis"

    def test_emits_one_msg_per_sensor(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        sensors = [
            ("camera_link", [0.1, 0.0, 0.5]),
            ("lidar_link", [0.0, 0.0, 0.8]),
            ("imu_link", [0.0, 0.05, 0.1]),
        ]
        msgs = build_static_sensor_transforms(sensors)
        assert len(msgs) == 3
        assert [m.child_frame_id for m in msgs] == [s[0] for s in sensors]

    def test_rejects_wrong_translation_length(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        with pytest.raises(ValueError):
            build_static_sensor_transforms([("camera_link", [0.1, 0.0])])


class TestQuatNormalization:
    """Identity quaternion (w=1, x=y=z=0) must be emitted as-is, with unit norm."""

    def test_identity_quat_emitted(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        (msg,) = build_static_sensor_transforms([("camera_link", [0.0, 0.0, 0.0])])
        q = msg.transform.rotation
        assert (q.w, q.x, q.y, q.z) == (1.0, 0.0, 0.0, 0.0)

    def test_identity_quat_has_unit_norm(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        (msg,) = build_static_sensor_transforms([("camera_link", [1.0, 2.0, 3.0])])
        q = msg.transform.rotation
        norm_sq = q.w * q.w + q.x * q.x + q.y * q.y + q.z * q.z
        assert norm_sq == pytest.approx(1.0, abs=1e-12)

    def test_body_frame_y_z_flipped_per_180deg_roll_convention(
        self, fake_ros2_tf_modules: None
    ) -> None:
        """YAML author sits in post-roll body frame; broadcaster flips Y/Z."""
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        (msg,) = build_static_sensor_transforms([("camera_link", [0.5, 2.0, 3.0])])
        assert msg.transform.translation.x == pytest.approx(0.5)
        assert msg.transform.translation.y == pytest.approx(-2.0)
        assert msg.transform.translation.z == pytest.approx(-3.0)


class TestSeedDeterminism:
    """Calling the builder repeatedly with the same input list must yield
    bitwise-identical output — no implicit randomness anywhere."""

    def test_same_input_yields_same_output(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        sensors = [
            ("camera_link", [0.1, 0.0, 0.5]),
            ("lidar_link", [0.0, 0.0, 0.8]),
        ]
        first = build_static_sensor_transforms(sensors)
        second = build_static_sensor_transforms(sensors)
        for a, b in zip(first, second, strict=False):
            assert a.header.frame_id == b.header.frame_id
            assert a.child_frame_id == b.child_frame_id
            assert (
                a.transform.translation.x,
                a.transform.translation.y,
                a.transform.translation.z,
            ) == (
                b.transform.translation.x,
                b.transform.translation.y,
                b.transform.translation.z,
            )

    def test_iterable_consumed_independently(self, fake_ros2_tf_modules: None) -> None:
        """Passing a generator must not leak state between calls."""
        from marslab.ros2_bridge.tf_broadcaster import build_static_sensor_transforms

        def gen():
            yield ("camera_link", [0.1, 0.0, 0.5])
            yield ("lidar_link", [0.0, 0.0, 0.8])

        out = build_static_sensor_transforms(gen())
        assert len(out) == 2

    def test_publish_static_sensor_tfs_uses_broadcaster(self, fake_ros2_tf_modules: None) -> None:
        """``publish_static_sensor_tfs`` sends every transform exactly once.

        Day 5 (2026-04-25): when ``camera_link`` is in the sensor list,
        a ``camera_link → camera_optical_frame`` transform is appended
        automatically (REP-105 optical convention for RViz / image
        pipeline).  So 2 sensors with camera_link → 3 broadcast msgs.
        """
        from marslab.ros2_bridge.tf_broadcaster import publish_static_sensor_tfs

        node = MagicMock()
        sensors = [
            ("camera_link", [0.1, 0.0, 0.5]),
            ("lidar_link", [0.0, 0.0, 0.8]),
        ]
        broadcaster = publish_static_sensor_tfs(node, sensors)
        # 2 sensor frames + 1 camera_optical_frame = 3 transforms.
        assert len(broadcaster.sent) == 3
        child_frames = [m.child_frame_id for m in broadcaster.sent]
        assert "camera_link" in child_frames
        assert "lidar_link" in child_frames
        assert "camera_optical_frame" in child_frames

    def test_publish_static_sensor_tfs_skips_optical_frame_without_camera(
        self, fake_ros2_tf_modules: None
    ) -> None:
        """No ``camera_link`` in sensors → no optical-frame transform.

        Cave / canyon scenarios that strip the camera should not
        broadcast a stub optical frame.
        """
        from marslab.ros2_bridge.tf_broadcaster import publish_static_sensor_tfs

        node = MagicMock()
        sensors = [("lidar_link", [0.0, 0.0, 0.8])]
        broadcaster = publish_static_sensor_tfs(node, sensors)
        assert len(broadcaster.sent) == 1
        assert broadcaster.sent[0].child_frame_id == "lidar_link"


class TestCameraOpticalFrameTransform:
    """Day 5 (2026-04-25): camera_link → camera_optical_frame static TF.

    REP-105 standard: camera_link is REP-103 body convention
    (X forward, Y left, Z up); camera_optical_frame is optical
    (Z forward, X right, Y down).  RPY = (-π/2, 0, -π/2) →
    quaternion (x, y, z, w) = (-0.5, 0.5, -0.5, 0.5).
    """

    def test_default_frame_names(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import (
            build_camera_optical_frame_transform,
        )

        msg = build_camera_optical_frame_transform()
        assert msg.header.frame_id == "camera_link"
        assert msg.child_frame_id == "camera_optical_frame"

    def test_custom_frame_names(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import (
            build_camera_optical_frame_transform,
        )

        msg = build_camera_optical_frame_transform("front_cam_link", "front_cam_optical")
        assert msg.header.frame_id == "front_cam_link"
        assert msg.child_frame_id == "front_cam_optical"

    def test_translation_is_identity(self, fake_ros2_tf_modules: None) -> None:
        from marslab.ros2_bridge.tf_broadcaster import (
            build_camera_optical_frame_transform,
        )

        msg = build_camera_optical_frame_transform()
        assert msg.transform.translation.x == 0.0
        assert msg.transform.translation.y == 0.0
        assert msg.transform.translation.z == 0.0

    def test_rotation_is_optical_quaternion(self, fake_ros2_tf_modules: None) -> None:
        """Quaternion matches ``tf_transformations.quaternion_from_euler(-π/2, 0, -π/2)``."""
        from marslab.ros2_bridge.tf_broadcaster import (
            build_camera_optical_frame_transform,
        )

        msg = build_camera_optical_frame_transform()
        assert msg.transform.rotation.x == -0.5
        assert msg.transform.rotation.y == 0.5
        assert msg.transform.rotation.z == -0.5
        assert msg.transform.rotation.w == 0.5

    def test_quaternion_is_unit_magnitude(self, fake_ros2_tf_modules: None) -> None:
        """Sanity: |q| == 1 for a valid rotation quaternion."""
        import math

        from marslab.ros2_bridge.tf_broadcaster import (
            build_camera_optical_frame_transform,
        )

        msg = build_camera_optical_frame_transform()
        q = msg.transform.rotation
        magnitude = math.sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w)
        assert math.isclose(magnitude, 1.0, abs_tol=1e-9)
