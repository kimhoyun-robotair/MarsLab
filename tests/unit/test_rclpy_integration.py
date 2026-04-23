"""Unit tests for :mod:`marslab.ros2_bridge.rclpy_integration`.

The real ``init_rclpy_side`` depends on rclpy, which in turn needs a
running DDS fabric.  Here we patch the rclpy module and the three
factory helpers so the orchestration logic can be tested offline.
"""

from __future__ import annotations

import sys
import types
from typing import Any, Dict

import numpy as np
import pytest


@pytest.fixture
def fake_rclpy(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    """Install a stubbed ``rclpy`` package in ``sys.modules``."""

    fake = types.ModuleType("rclpy")
    fake.init_calls = []  # type: ignore[attr-defined]
    fake.created_nodes = []  # type: ignore[attr-defined]

    def fake_ok() -> bool:
        return bool(fake.init_calls)  # type: ignore[attr-defined]

    def fake_init(*, args: Any = None) -> None:
        fake.init_calls.append(args)  # type: ignore[attr-defined]

    def fake_create_node(name: str, *, parameter_overrides: Any = None) -> Any:
        node = types.SimpleNamespace(name=name, parameter_overrides=parameter_overrides)
        fake.created_nodes.append(node)  # type: ignore[attr-defined]
        return node

    fake.ok = fake_ok
    fake.init = fake_init
    fake.create_node = fake_create_node

    param_module = types.ModuleType("rclpy.parameter")

    class _Type:
        BOOL = "BOOL"

    class _Parameter:
        Type = _Type

        def __init__(self, name: str, type_: Any, value: Any) -> None:
            self.name = name
            self.type = type_
            self.value = value

    param_module.Parameter = _Parameter  # type: ignore[attr-defined]
    fake.parameter = param_module

    monkeypatch.setitem(sys.modules, "rclpy", fake)
    monkeypatch.setitem(sys.modules, "rclpy.parameter", param_module)
    return fake


class TestInitRclpySide:
    def _patch_factories(self, monkeypatch: pytest.MonkeyPatch) -> Dict[str, Any]:
        import marslab.ros2_bridge.rclpy_integration as mod

        captured: Dict[str, Any] = {}

        def fake_cmd_vel(
            node: Any,
            topic: str,
            state: Dict[str, float],
            *,
            queue_size: int,
        ) -> Any:
            captured["cmd_vel"] = (node, topic, state, queue_size)
            return types.SimpleNamespace(topic=topic)

        def fake_static_tfs(node: Any, sensor_frames: Any) -> Any:
            captured["static_tfs"] = (node, list(sensor_frames))
            return types.SimpleNamespace(kind="static_broadcaster")

        def fake_create_odom(**kwargs: Any) -> Any:
            captured["odom"] = kwargs
            return types.SimpleNamespace(kind="odom_ctx")

        monkeypatch.setattr(mod, "create_cmd_vel_subscriber", fake_cmd_vel)
        monkeypatch.setattr(mod, "publish_static_sensor_tfs", fake_static_tfs)
        monkeypatch.setattr(mod, "create_odometry_publisher", fake_create_odom)
        return captured

    def test_initialises_rclpy_when_not_ok(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {
                "cmd_vel": "cmd_vel",
                "odom": "odom",
                "imu": "imu",
                "rgb": "rgb/image_raw",
                "depth": "depth/image_raw",
                "lidar": "lidar/points",
            },
        }
        init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[("camera_link", [0.1, 0.0, 0.5])],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )

        # rclpy.init was called exactly once because ok() returned False.
        assert fake_rclpy.init_calls == [None]  # type: ignore[attr-defined]

    def test_node_name_includes_namespace(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom"},
        }
        init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
            node_name="my_runtime",
        )
        created = fake_rclpy.created_nodes  # type: ignore[attr-defined]
        assert len(created) == 1
        assert created[0].name == "rover_my_runtime"

    def test_odom_publisher_reads_yaml_overrides(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        captured = self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom"},
            "odom_publisher": {
                "queue_size": 42,
                "frame_id": "map",
                "child_frame_id": "base_footprint",
            },
        }
        init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        odom_kwargs = captured["odom"]
        assert odom_kwargs["queue_size"] == 42
        assert odom_kwargs["frame_id"] == "map"
        assert odom_kwargs["child_frame_id"] == "base_footprint"
        assert odom_kwargs["topic"] == "/rover/odom"

    def test_cmd_vel_queue_size_uses_yaml_override(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """R4-5 extension: ``cmd_vel_queue_size`` flows from ``ros2_cfg``."""
        captured = self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom"},
            "cmd_vel_queue_size": 37,
        }
        init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        # captured["cmd_vel"] layout: (node, topic, state, queue_size).
        assert captured["cmd_vel"][3] == 37

    def test_cmd_vel_queue_size_defaults_to_ten(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Absent YAML key → historical default of 10 is preserved."""
        captured = self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom"},
        }
        init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        assert captured["cmd_vel"][3] == 10

    def test_returns_bridge_context_with_twist_state(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.context import BridgeContext
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom"},
        }
        ctx = init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        assert isinstance(ctx, BridgeContext)
        assert ctx.twist_state == {"v": 0.0, "w": 0.0}
