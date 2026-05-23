"""Unit tests for marslab.ros2_bridge.rclpy_integration (rclpy patched for offline)."""

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

    # ``init_rclpy_side`` resolves QoS
    # profiles via ``marslab.ros2_bridge.qos.to_rclpy_qos`` which imports
    # ``rclpy.qos``.  Stub the enum / QoSProfile surface so the offline
    # fake rclpy can satisfy the adapter without installing ROS 2.
    qos_module = types.ModuleType("rclpy.qos")

    class _ReliabilityPolicy:
        RELIABLE = "RELIABLE"
        BEST_EFFORT = "BEST_EFFORT"

    class _DurabilityPolicy:
        VOLATILE = "VOLATILE"
        TRANSIENT_LOCAL = "TRANSIENT_LOCAL"

    class _HistoryPolicy:
        KEEP_LAST = "KEEP_LAST"
        KEEP_ALL = "KEEP_ALL"

    class _QoSProfile:
        """Minimal stand-in that records the kwargs for later inspection."""

        def __init__(
            self,
            reliability: Any = None,
            durability: Any = None,
            history: Any = None,
            depth: int = 10,
        ) -> None:
            self.reliability = reliability
            self.durability = durability
            self.history = history
            self.depth = depth

    qos_module.ReliabilityPolicy = _ReliabilityPolicy  # type: ignore[attr-defined]
    qos_module.DurabilityPolicy = _DurabilityPolicy  # type: ignore[attr-defined]
    qos_module.HistoryPolicy = _HistoryPolicy  # type: ignore[attr-defined]
    qos_module.QoSProfile = _QoSProfile  # type: ignore[attr-defined]
    fake.qos = qos_module  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "rclpy", fake)
    monkeypatch.setitem(sys.modules, "rclpy.parameter", param_module)
    monkeypatch.setitem(sys.modules, "rclpy.qos", qos_module)
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
            qos: Any = None,
        ) -> Any:
            # ``qos`` is a keyword arg on the QoS-aware factory.
            # Record it so downstream assertions can pin the QoS contract.
            captured["cmd_vel"] = (node, topic, state, queue_size)
            captured["cmd_vel_qos"] = qos
            return types.SimpleNamespace(topic=topic)

        def fake_static_tfs(node: Any, sensor_frames: Any, **kwargs: Any) -> Any:
            # ``qos`` keyword added by the QoS-aware factory; swallow transparently.
            captured["static_tfs"] = (node, list(sensor_frames))
            captured["static_tfs_kwargs"] = kwargs
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
                "gt_trajectory": "GT_Trajectory",
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
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom", "gt_trajectory": "GT_Trajectory"},
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
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom", "gt_trajectory": "GT_Trajectory"},
            "odom_publisher": {
                "queue_size": 42,
                "gt_frame_id": "map",
                "gt_child_frame_id": "base_footprint",
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
        assert odom_kwargs["topic"] == "/rover/GT_Trajectory"

    def test_cmd_vel_queue_size_uses_yaml_override(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """``cmd_vel_queue_size`` flows from ``ros2_cfg``."""
        captured = self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom", "gt_trajectory": "GT_Trajectory"},
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
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom", "gt_trajectory": "GT_Trajectory"},
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
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom", "gt_trajectory": "GT_Trajectory"},
        }
        ctx = init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        assert isinstance(ctx, BridgeContext)
        assert ctx.twist_state == {"v": 0.0, "w": 0.0}

    def test_cmd_vel_qos_threaded_through_by_default(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default ``cmd_vel_qos`` lands on the subscriber.

        The default :class:`Ros2BridgeConfig` ships RELIABLE for the
        command channel; the fake ``rclpy.qos.QoSProfile`` records the
        exact reliability so a silent flip (regression) is caught.
        """
        captured = self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom", "gt_trajectory": "GT_Trajectory"},
        }
        init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        cmd_qos = captured["cmd_vel_qos"]
        assert cmd_qos is not None
        assert cmd_qos.reliability == "RELIABLE"
        assert cmd_qos.depth == 10

    def test_sensor_qos_override_flows_into_odom(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Overriding ``odom_qos`` in YAML changes the publisher QoS.

        Catches the regression where ``init_rclpy_side`` would drop
        the YAML block on the floor.
        """
        captured = self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom", "gt_trajectory": "GT_Trajectory"},
            "odom_qos": {
                "reliability": "best_effort",
                "durability": "volatile",
                "history": "keep_last",
                "depth": 3,
            },
        }
        init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        odom_kwargs = captured["odom"]
        assert odom_kwargs["odom_qos"] is not None
        assert odom_kwargs["odom_qos"].reliability == "BEST_EFFORT"
        assert odom_kwargs["odom_qos"].depth == 3

    def test_tf_qos_reaches_static_broadcaster(
        self,
        fake_rclpy: types.ModuleType,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Default ``tf_qos`` (TRANSIENT_LOCAL) reaches the static TF path."""
        captured = self._patch_factories(monkeypatch)
        from marslab.ros2_bridge.rclpy_integration import init_rclpy_side

        ros2_cfg = {
            "namespace": "rover",
            "topics": {"cmd_vel": "cmd_vel", "odom": "odom", "gt_trajectory": "GT_Trajectory"},
        }
        init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[("camera_link", [0.1, 0.0, 0.5])],
            init_pos_world=np.zeros(3),
            init_quat_world=np.array([1.0, 0.0, 0.0, 0.0]),
        )
        tf_kwargs = captured["static_tfs_kwargs"]
        assert "qos" in tf_kwargs
        assert tf_kwargs["qos"].durability == "TRANSIENT_LOCAL"
        assert tf_kwargs["qos"].depth == 100
