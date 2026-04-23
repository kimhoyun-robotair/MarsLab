"""Unit tests for :mod:`marslab.ros2_bridge.tf_broadcaster`.

R8-5 (2026-04-23). Covers the body-frame Y/Z flip (180 deg X-roll USD
import convention), identity quaternion normalization, and determinism
across repeated calls with the same seed-equivalent input list.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import Any, List
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Fake geometry_msgs.msg.TransformStamped and tf2_ros modules
# ---------------------------------------------------------------------------


@dataclass
class _FakeVec3:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class _FakeQuat:
    w: float = 1.0
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0


@dataclass
class _FakeTransform:
    translation: _FakeVec3 = field(default_factory=_FakeVec3)
    rotation: _FakeQuat = field(default_factory=_FakeQuat)


@dataclass
class _FakeHeader:
    frame_id: str = ""


@dataclass
class _FakeTransformStamped:
    header: _FakeHeader = field(default_factory=_FakeHeader)
    child_frame_id: str = ""
    transform: _FakeTransform = field(default_factory=_FakeTransform)


class _FakeStaticBroadcaster:
    def __init__(self, node: Any) -> None:
        self.node = node
        self.sent: List[Any] = []

    def sendTransform(self, msgs: Any) -> None:  # noqa: N802
        # tf2_ros accepts either a single msg or a list.
        if isinstance(msgs, list):
            self.sent.extend(msgs)
        else:
            self.sent.append(msgs)


@pytest.fixture
def fake_ros2_tf_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    geo_msgs = types.ModuleType("geometry_msgs")
    geo_msgs_msg = types.ModuleType("geometry_msgs.msg")
    geo_msgs_msg.TransformStamped = _FakeTransformStamped  # type: ignore[attr-defined]
    geo_msgs.msg = geo_msgs_msg  # type: ignore[attr-defined]

    tf2_ros = types.ModuleType("tf2_ros")
    tf2_ros.StaticTransformBroadcaster = _FakeStaticBroadcaster  # type: ignore[attr-defined]
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
        for a, b in zip(first, second):
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
        """``publish_static_sensor_tfs`` sends every transform exactly once."""
        from marslab.ros2_bridge.tf_broadcaster import publish_static_sensor_tfs

        node = MagicMock()
        sensors = [
            ("camera_link", [0.1, 0.0, 0.5]),
            ("lidar_link", [0.0, 0.0, 0.8]),
        ]
        broadcaster = publish_static_sensor_tfs(node, sensors)
        # Our fake stores the sent msgs so len reflects the broadcast call.
        assert len(broadcaster.sent) == 2
