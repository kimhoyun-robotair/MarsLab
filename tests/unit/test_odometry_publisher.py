"""Unit tests for :mod:`marslab.ros2_bridge.odometry_publisher`.

R8-5 (2026-04-23). The publisher depends on ``rclpy``, ``nav_msgs`` and
``tf2_ros`` so the test stubs those with ``unittest.mock`` / local
types (mirrors the pattern in ``test_rclpy_integration.py``).

Focus areas (per R8 plan):
* TF frame_id / child_frame_id propagation
* body-frame twist correctness (``world_twist_to_body``)
* single mocked ``publish`` call (no real rclpy spin)
* header stamp monotonicity across two calls
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass, field
from typing import Any, List
from unittest.mock import MagicMock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Fake ROS2 message + tf2_ros modules.  Installed once per test via fixture.
# ---------------------------------------------------------------------------


@dataclass
class _FakeStamp:
    sec: int = 0
    nanosec: int = 0


@dataclass
class _FakeHeader:
    stamp: _FakeStamp = field(default_factory=_FakeStamp)
    frame_id: str = ""


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
class _FakeTransformStamped:
    header: _FakeHeader = field(default_factory=_FakeHeader)
    child_frame_id: str = ""
    transform: _FakeTransform = field(default_factory=_FakeTransform)


@dataclass
class _FakePose:
    position: _FakeVec3 = field(default_factory=_FakeVec3)
    orientation: _FakeQuat = field(default_factory=_FakeQuat)


@dataclass
class _FakePoseWithCov:
    pose: _FakePose = field(default_factory=_FakePose)


@dataclass
class _FakeTwist:
    linear: _FakeVec3 = field(default_factory=_FakeVec3)
    angular: _FakeVec3 = field(default_factory=_FakeVec3)


@dataclass
class _FakeTwistWithCov:
    twist: _FakeTwist = field(default_factory=_FakeTwist)


@dataclass
class _FakeOdometry:
    header: _FakeHeader = field(default_factory=_FakeHeader)
    child_frame_id: str = ""
    pose: _FakePoseWithCov = field(default_factory=_FakePoseWithCov)
    twist: _FakeTwistWithCov = field(default_factory=_FakeTwistWithCov)


class _FakeTransformBroadcaster:
    def __init__(self, node: Any) -> None:  # noqa: D401 - signature mirrors tf2_ros
        self.node = node
        self.sent: List[_FakeTransformStamped] = []

    def sendTransform(self, tf_msg: _FakeTransformStamped) -> None:  # noqa: N802
        self.sent.append(tf_msg)


@pytest.fixture
def fake_ros2_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install fake ``nav_msgs`` / ``geometry_msgs`` / ``tf2_ros`` modules."""

    nav_msgs = types.ModuleType("nav_msgs")
    nav_msgs_msg = types.ModuleType("nav_msgs.msg")
    nav_msgs_msg.Odometry = _FakeOdometry  # type: ignore[attr-defined]
    nav_msgs.msg = nav_msgs_msg  # type: ignore[attr-defined]

    geo_msgs = types.ModuleType("geometry_msgs")
    geo_msgs_msg = types.ModuleType("geometry_msgs.msg")
    geo_msgs_msg.TransformStamped = _FakeTransformStamped  # type: ignore[attr-defined]
    geo_msgs_msg.Twist = MagicMock()  # type: ignore[attr-defined]
    geo_msgs.msg = geo_msgs_msg  # type: ignore[attr-defined]

    tf2_ros = types.ModuleType("tf2_ros")
    tf2_ros.TransformBroadcaster = _FakeTransformBroadcaster  # type: ignore[attr-defined]
    tf2_ros.StaticTransformBroadcaster = MagicMock()  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "nav_msgs", nav_msgs)
    monkeypatch.setitem(sys.modules, "nav_msgs.msg", nav_msgs_msg)
    monkeypatch.setitem(sys.modules, "geometry_msgs", geo_msgs)
    monkeypatch.setitem(sys.modules, "geometry_msgs.msg", geo_msgs_msg)
    monkeypatch.setitem(sys.modules, "tf2_ros", tf2_ros)


def _make_node(stamp_seq: List[_FakeStamp]) -> MagicMock:
    """Node stub whose clock returns successive stamps from ``stamp_seq``."""
    node = MagicMock()
    publisher = MagicMock()
    node.create_publisher.return_value = publisher

    iterator = iter(stamp_seq)

    def to_msg() -> _FakeStamp:
        return next(iterator)

    def now() -> Any:
        obj = MagicMock()
        obj.to_msg = to_msg
        return obj

    clock = MagicMock()
    clock.now = now
    node.get_clock.return_value = clock
    return node


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateOdometryPublisher:
    def test_frame_ids_propagate_into_context(self, fake_ros2_modules: None) -> None:
        from marslab.ros2_bridge.odometry_publisher import create_odometry_publisher

        node = _make_node([_FakeStamp(1, 0)])
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=np.array([0.0, 0.0, 0.0]),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            queue_size=7,
            frame_id="map",
            child_frame_id="base_footprint",
        )
        assert ctx.frame_id == "map"
        assert ctx.child_frame_id == "base_footprint"
        node.create_publisher.assert_called_once()
        assert node.create_publisher.call_args.args[2] == 7

    def test_init_pose_is_copied_not_referenced(self, fake_ros2_modules: None) -> None:
        from marslab.ros2_bridge.odometry_publisher import create_odometry_publisher

        node = _make_node([_FakeStamp(0, 0)])
        init_pos = np.array([1.0, 2.0, 3.0])
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=init_pos,
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        init_pos[0] = 99.0
        assert ctx.init_pos_world[0] == pytest.approx(1.0)


class TestPublishOdometrySingleCall:
    def test_publishes_once_and_sets_frame_ids(self, fake_ros2_modules: None) -> None:
        from marslab.ros2_bridge.odometry_publisher import (
            create_odometry_publisher,
            publish_odometry,
        )

        node = _make_node([_FakeStamp(5, 0)])
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=np.array([0.0, 0.0, 0.0]),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        publish_odometry(
            ctx=ctx,
            cur_pos_world=np.array([1.0, 2.0, 0.0]),
            cur_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            linear_vel_world=np.array([0.5, 0.0, 0.0]),
            angular_vel_world=np.array([0.0, 0.0, 0.1]),
        )
        # publisher.publish was called exactly once.
        assert ctx.publisher.publish.call_count == 1
        odom_arg = ctx.publisher.publish.call_args.args[0]
        assert odom_arg.header.frame_id == "odom"
        assert odom_arg.child_frame_id == "base_link"

    def test_body_twist_matches_world_twist_at_identity_quat(self, fake_ros2_modules: None) -> None:
        """At ``quat=identity`` the body frame aligns with world, so the
        twist must pass through unchanged."""
        from marslab.ros2_bridge.odometry_publisher import (
            create_odometry_publisher,
            publish_odometry,
        )

        node = _make_node([_FakeStamp(0, 0)])
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=np.array([0.0, 0.0, 0.0]),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        publish_odometry(
            ctx=ctx,
            cur_pos_world=np.array([0.0, 0.0, 0.0]),
            cur_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            linear_vel_world=np.array([0.7, 0.0, 0.0]),
            angular_vel_world=np.array([0.0, 0.0, 0.3]),
        )
        odom = ctx.publisher.publish.call_args.args[0]
        assert odom.twist.twist.linear.x == pytest.approx(0.7, abs=1e-5)
        assert odom.twist.twist.angular.z == pytest.approx(0.3, abs=1e-5)

    def test_tf_broadcast_uses_same_frames_as_odometry(self, fake_ros2_modules: None) -> None:
        from marslab.ros2_bridge.odometry_publisher import (
            create_odometry_publisher,
            publish_odometry,
        )

        node = _make_node([_FakeStamp(0, 0)])
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=np.array([0.0, 0.0, 0.0]),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            frame_id="odom",
            child_frame_id="base_link",
        )
        publish_odometry(
            ctx=ctx,
            cur_pos_world=np.array([1.0, 0.0, 0.0]),
            cur_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            linear_vel_world=np.zeros(3),
            angular_vel_world=np.zeros(3),
        )
        assert len(ctx.tf_broadcaster.sent) == 1
        tf_msg = ctx.tf_broadcaster.sent[0]
        assert tf_msg.header.frame_id == "odom"
        assert tf_msg.child_frame_id == "base_link"
        assert tf_msg.transform.translation.x == pytest.approx(1.0, abs=1e-5)


class TestHeaderStampMonotonic:
    """Two consecutive publish calls must not regress the stamp."""

    def test_stamp_monotonic_non_decreasing(self, fake_ros2_modules: None) -> None:
        from marslab.ros2_bridge.odometry_publisher import (
            create_odometry_publisher,
            publish_odometry,
        )

        stamps = [_FakeStamp(10, 0), _FakeStamp(11, 500_000_000)]
        node = _make_node(stamps)
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        for _ in range(2):
            publish_odometry(
                ctx=ctx,
                cur_pos_world=np.zeros(3),
                cur_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
                linear_vel_world=np.zeros(3),
                angular_vel_world=np.zeros(3),
            )
        a, b = (
            ctx.publisher.publish.call_args_list[0].args[0].header.stamp,
            ctx.publisher.publish.call_args_list[1].args[0].header.stamp,
        )
        assert (b.sec, b.nanosec) >= (a.sec, a.nanosec)
