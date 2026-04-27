"""Unit tests for marslab.ros2_bridge.cmd_vel_subscriber. Twist -> wheel state."""

from __future__ import annotations

import sys
import types
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def fake_twist_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """Install a fake ``geometry_msgs.msg.Twist`` so the subscriber
    factory imports something even though we never publish real Twist."""

    geo_msgs = types.ModuleType("geometry_msgs")
    geo_msgs_msg = types.ModuleType("geometry_msgs.msg")
    geo_msgs_msg.Twist = MagicMock()  # type: ignore[attr-defined]
    geo_msgs.msg = geo_msgs_msg  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "geometry_msgs", geo_msgs)
    monkeypatch.setitem(sys.modules, "geometry_msgs.msg", geo_msgs_msg)


def _make_node_capture_callback() -> tuple[MagicMock, Dict[str, Any]]:
    """Return a node mock plus a capture dict holding the registered cb."""
    captured: Dict[str, Any] = {}

    def fake_create_subscription(msg_type: Any, topic: str, cb: Any, queue: int) -> Any:
        captured["msg_type"] = msg_type
        captured["topic"] = topic
        captured["cb"] = cb
        captured["queue"] = queue
        return MagicMock()

    node = MagicMock()
    node.create_subscription.side_effect = fake_create_subscription
    return node, captured


class _TwistMsg:
    """Minimal duck-typed Twist replacement."""

    def __init__(self, vx: float, wz: float) -> None:
        self.linear = types.SimpleNamespace(x=vx, y=0.0, z=0.0)
        self.angular = types.SimpleNamespace(x=0.0, y=0.0, z=wz)


class TestTwistToWheelState:
    """Twist.linear.x / angular.z copy into state["v"] / state["w"]."""

    def test_linear_and_angular_written_to_state(self, fake_twist_module: None) -> None:
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, captured = _make_node_capture_callback()
        state: Dict[str, float] = {"v": 0.0, "w": 0.0}
        create_cmd_vel_subscriber(node, "/rover/cmd_vel", state, queue_size=10)
        captured["cb"](_TwistMsg(vx=0.7, wz=0.3))
        assert state["v"] == pytest.approx(0.7)
        assert state["w"] == pytest.approx(0.3)

    def test_topic_name_passed_through(self, fake_twist_module: None) -> None:
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, captured = _make_node_capture_callback()
        create_cmd_vel_subscriber(node, "/my_ns/cmd_vel", {"v": 0.0, "w": 0.0}, queue_size=10)
        assert captured["topic"] == "/my_ns/cmd_vel"

    def test_queue_size_has_no_python_default(self, fake_twist_module: None) -> None:
        """``queue_size`` has no Python default. Omitting the kwarg
        must raise ``TypeError`` -- no silent fallback."""
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, _ = _make_node_capture_callback()
        with pytest.raises(TypeError):
            create_cmd_vel_subscriber(node, "/rover/cmd_vel", {"v": 0.0, "w": 0.0})

    def test_queue_size_passed_through(self, fake_twist_module: None) -> None:
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, captured = _make_node_capture_callback()
        create_cmd_vel_subscriber(node, "/rover/cmd_vel", {"v": 0.0, "w": 0.0}, queue_size=50)
        assert captured["queue"] == 50


class TestZeroCmdProducesZeroWheel:
    """A zero Twist message must drive the wheel state to exactly 0."""

    def test_zero_cmd_sets_zero_wheel(self, fake_twist_module: None) -> None:
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, captured = _make_node_capture_callback()
        state: Dict[str, float] = {"v": 1.0, "w": 1.0}  # stale
        create_cmd_vel_subscriber(node, "/rover/cmd_vel", state, queue_size=10)
        captured["cb"](_TwistMsg(vx=0.0, wz=0.0))
        assert state["v"] == 0.0
        assert state["w"] == 0.0

    def test_subsequent_zero_after_nonzero_resets(self, fake_twist_module: None) -> None:
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, captured = _make_node_capture_callback()
        state: Dict[str, float] = {"v": 0.0, "w": 0.0}
        create_cmd_vel_subscriber(node, "/rover/cmd_vel", state, queue_size=10)
        captured["cb"](_TwistMsg(vx=0.5, wz=0.4))
        captured["cb"](_TwistMsg(vx=0.0, wz=0.0))
        assert state["v"] == 0.0
        assert state["w"] == 0.0


class TestSafetyLimitAndContract:
    """Safety: state dict must have ``v`` and ``w`` keys; factory rejects
    otherwise. Negative commands pass through (direction), huge cmds pass
    through the subscriber — the caller (cmd_vel -> wheel IK) is
    responsible for clamping per the ``SkidSteerDriveConfig`` limits."""

    def test_missing_state_key_raises(self, fake_twist_module: None) -> None:
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, _ = _make_node_capture_callback()
        with pytest.raises(KeyError):
            create_cmd_vel_subscriber(node, "/rover/cmd_vel", {"v": 0.0}, queue_size=10)
        with pytest.raises(KeyError):
            create_cmd_vel_subscriber(node, "/rover/cmd_vel", {}, queue_size=10)

    def test_negative_cmd_passes_through(self, fake_twist_module: None) -> None:
        """Reverse drive is valid — subscriber does not clamp sign."""
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, captured = _make_node_capture_callback()
        state: Dict[str, float] = {"v": 0.0, "w": 0.0}
        create_cmd_vel_subscriber(node, "/rover/cmd_vel", state, queue_size=10)
        captured["cb"](_TwistMsg(vx=-0.3, wz=-0.1))
        assert state["v"] == pytest.approx(-0.3)
        assert state["w"] == pytest.approx(-0.1)

    def test_cast_to_float_even_if_int_input(self, fake_twist_module: None) -> None:
        """Twist fields sometimes arrive as int; subscriber casts to float."""
        from marslab.ros2_bridge.cmd_vel_subscriber import create_cmd_vel_subscriber

        node, captured = _make_node_capture_callback()
        state: Dict[str, float] = {"v": 0.0, "w": 0.0}
        create_cmd_vel_subscriber(node, "/rover/cmd_vel", state, queue_size=10)
        captured["cb"](_TwistMsg(vx=1, wz=2))
        assert isinstance(state["v"], float) and state["v"] == 1.0
        assert isinstance(state["w"], float) and state["w"] == 2.0
