"""Unit tests for marslab.ros2_bridge.odometry_publisher (R8-5). Stubs rclpy/nav_msgs/tf2_ros."""

from __future__ import annotations

import sys
import types
from typing import Any, List
from unittest.mock import MagicMock

import numpy as np
import pytest

from tests.unit.conftest import (
    FakeOdometry,
    FakeStamp,
    FakeTransformBroadcaster,
    FakeTransformStamped,
)


@pytest.fixture
def fake_ros2_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install fake ``nav_msgs`` / ``geometry_msgs`` / ``tf2_ros`` modules."""

    nav_msgs = types.ModuleType("nav_msgs")
    nav_msgs_msg = types.ModuleType("nav_msgs.msg")
    nav_msgs_msg.Odometry = FakeOdometry  # type: ignore[attr-defined]
    nav_msgs.msg = nav_msgs_msg  # type: ignore[attr-defined]

    geo_msgs = types.ModuleType("geometry_msgs")
    geo_msgs_msg = types.ModuleType("geometry_msgs.msg")
    geo_msgs_msg.TransformStamped = FakeTransformStamped  # type: ignore[attr-defined]
    geo_msgs_msg.Twist = MagicMock()  # type: ignore[attr-defined]
    geo_msgs.msg = geo_msgs_msg  # type: ignore[attr-defined]

    tf2_ros = types.ModuleType("tf2_ros")
    tf2_ros.TransformBroadcaster = FakeTransformBroadcaster  # type: ignore[attr-defined]
    tf2_ros.StaticTransformBroadcaster = MagicMock()  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "nav_msgs", nav_msgs)
    monkeypatch.setitem(sys.modules, "nav_msgs.msg", nav_msgs_msg)
    monkeypatch.setitem(sys.modules, "geometry_msgs", geo_msgs)
    monkeypatch.setitem(sys.modules, "geometry_msgs.msg", geo_msgs_msg)
    monkeypatch.setitem(sys.modules, "tf2_ros", tf2_ros)


def _make_node(stamp_seq: List[FakeStamp]) -> MagicMock:
    """Node stub whose clock returns successive stamps from ``stamp_seq``."""
    node = MagicMock()
    publisher = MagicMock()
    node.create_publisher.return_value = publisher

    iterator = iter(stamp_seq)

    def to_msg() -> FakeStamp:
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

        node = _make_node([FakeStamp(1, 0)])
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

        node = _make_node([FakeStamp(0, 0)])
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

        node = _make_node([FakeStamp(5, 0)])
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

        node = _make_node([FakeStamp(0, 0)])
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

        node = _make_node([FakeStamp(0, 0)])
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

        stamps = [FakeStamp(10, 0), FakeStamp(11, 500_000_000)]
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


class TestPublishTfFlag:
    """``publish_tf=False`` (S3 default) skips TF broadcast but keeps Odometry."""

    def test_publish_tf_false_creates_no_broadcaster(self, fake_ros2_modules: None) -> None:
        from marslab.ros2_bridge.odometry_publisher import create_odometry_publisher

        node = _make_node([FakeStamp(1, 0)])
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            publish_tf=False,
        )
        assert ctx.tf_broadcaster is None
        assert ctx.publish_tf is False

    def test_publish_tf_false_skips_send_transform(self, fake_ros2_modules: None) -> None:
        from marslab.ros2_bridge.odometry_publisher import (
            create_odometry_publisher,
            publish_odometry,
        )

        node = _make_node([FakeStamp(1, 0)])
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            publish_tf=False,
        )
        publish_odometry(
            ctx=ctx,
            cur_pos_world=np.array([1.0, 0.0, 0.0]),
            cur_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            linear_vel_world=np.zeros(3),
            angular_vel_world=np.zeros(3),
        )
        # Odometry message still published unconditionally so SLAM /
        # Nav2 consumers see motion estimates.
        assert ctx.publisher.publish.call_count == 1
        # ``tf_broadcaster`` is None so there is nothing to send to.

    def test_publish_tf_default_is_true_for_back_compat(self, fake_ros2_modules: None) -> None:
        """Pre-S3 callers (no kwarg) get the legacy dual-publisher behaviour."""
        from marslab.ros2_bridge.odometry_publisher import create_odometry_publisher

        node = _make_node([FakeStamp(1, 0)])
        ctx = create_odometry_publisher(
            node=node,
            topic="/rover/odom",
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        assert ctx.publish_tf is True
        assert ctx.tf_broadcaster is not None
