"""Regression tests for the ROS2 QoS schema + helper (Reviewer 2 #04).

These tests cover the pure-Python / pydantic surface so they run
without rclpy on the PYTHONPATH.  The one rclpy-dependent helper
(:func:`marslab.ros2_bridge.qos.to_rclpy_qos`) is exercised with a
``pytest.importorskip`` guard so the test is silently skipped in the
unit harness and active when rclpy is available (e.g. the user's
workstation with ROS 2 Jazzy sourced).

Context
-------

Before Reviewer 2 #04 every publisher and subscriber in
``marslab/ros2_bridge/`` was created with the rclpy default QoS
(``RELIABLE`` + ``VOLATILE`` + ``KEEP_LAST`` depth=10).  That caused
silent message drop against slam_toolbox (``BEST_EFFORT``) and
teleop_twist_keyboard (``BEST_EFFORT``).  The schema fields added in
this change pin the four topic families to SLAM/Nav2-friendly
defaults while leaving them overridable per-scenario.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from marslab.config.schema.ros2_bridge import QoSProfileConfig, Ros2BridgeConfig
from marslab.ros2_bridge.qos import to_omnigraph_qos_preset


class TestQoSProfileConfigDefaults:
    """``QoSProfileConfig`` keeps a RELIABLE + KEEP_LAST(10) default."""

    def test_default_reliability_is_reliable(self) -> None:
        cfg = QoSProfileConfig()
        assert cfg.reliability == "reliable"

    def test_default_durability_is_volatile(self) -> None:
        cfg = QoSProfileConfig()
        assert cfg.durability == "volatile"

    def test_default_history_is_keep_last(self) -> None:
        cfg = QoSProfileConfig()
        assert cfg.history == "keep_last"

    def test_default_depth_is_ten(self) -> None:
        cfg = QoSProfileConfig()
        assert cfg.depth == 10


class TestQoSProfileConfigValidation:
    """pydantic rejects invalid enum strings and out-of-range depth."""

    def test_invalid_reliability_raises(self) -> None:
        with pytest.raises(ValidationError):
            QoSProfileConfig(reliability="kinda_reliable")  # type: ignore[arg-type]

    def test_invalid_durability_raises(self) -> None:
        with pytest.raises(ValidationError):
            QoSProfileConfig(durability="permanent")  # type: ignore[arg-type]

    def test_invalid_history_raises(self) -> None:
        with pytest.raises(ValidationError):
            QoSProfileConfig(history="keep_three")  # type: ignore[arg-type]

    def test_depth_zero_rejected(self) -> None:
        with pytest.raises(ValidationError):
            QoSProfileConfig(depth=0)

    def test_depth_over_1000_rejected(self) -> None:
        with pytest.raises(ValidationError):
            QoSProfileConfig(depth=10_000)


class TestRos2BridgeConfigQoSFields:
    """``Ros2BridgeConfig`` exposes the four QoS fields with sane defaults."""

    def test_has_cmd_vel_qos_field(self) -> None:
        cfg = Ros2BridgeConfig()
        assert isinstance(cfg.cmd_vel_qos, QoSProfileConfig)

    def test_has_odom_qos_field(self) -> None:
        cfg = Ros2BridgeConfig()
        assert isinstance(cfg.odom_qos, QoSProfileConfig)

    def test_has_sensor_qos_field(self) -> None:
        cfg = Ros2BridgeConfig()
        assert isinstance(cfg.sensor_qos, QoSProfileConfig)

    def test_has_tf_qos_field(self) -> None:
        cfg = Ros2BridgeConfig()
        assert isinstance(cfg.tf_qos, QoSProfileConfig)

    def test_cmd_vel_default_reliable(self) -> None:
        """Matches Nav2 controller_server SystemDefault (RELIABLE)."""
        cfg = Ros2BridgeConfig()
        assert cfg.cmd_vel_qos.reliability == "reliable"
        assert cfg.cmd_vel_qos.depth == 10

    def test_odom_default_reliable(self) -> None:
        """REP-2003 SystemDefault for nav_msgs/Odometry."""
        cfg = Ros2BridgeConfig()
        assert cfg.odom_qos.reliability == "reliable"
        assert cfg.odom_qos.depth == 10

    def test_sensor_default_is_best_effort(self) -> None:
        """Hard pin: slam_toolbox compatibility.

        slam_toolbox subscribes to ``sensor_msgs/LaserScan`` with
        BEST_EFFORT.  Shipping RELIABLE on our side yields 0 messages
        received — this test prevents a silent flip back to reliable.
        """
        cfg = Ros2BridgeConfig()
        assert cfg.sensor_qos.reliability == "best_effort"
        assert cfg.sensor_qos.durability == "volatile"
        assert cfg.sensor_qos.depth == 5

    def test_tf_qos_is_transient_local(self) -> None:
        """Hard pin: late-joining subscriber compatibility.

        ``/tf_static`` must be TRANSIENT_LOCAL for late-joiners
        (slam_toolbox that boots after the bridge) to latch the sensor
        transforms.  This test prevents a silent flip to volatile.
        """
        cfg = Ros2BridgeConfig()
        assert cfg.tf_qos.reliability == "reliable"
        assert cfg.tf_qos.durability == "transient_local"
        assert cfg.tf_qos.depth == 100


class TestOmniGraphPresetMapping:
    """``to_omnigraph_qos_preset`` maps our config to Isaac Sim presets."""

    def test_best_effort_volatile_maps_to_sensor_data(self) -> None:
        cfg = QoSProfileConfig(reliability="best_effort", durability="volatile", depth=5)
        assert to_omnigraph_qos_preset(cfg) == "SensorData"

    def test_reliable_volatile_maps_to_system_default(self) -> None:
        cfg = QoSProfileConfig(reliability="reliable", durability="volatile", depth=10)
        assert to_omnigraph_qos_preset(cfg) == "SystemDefault"

    def test_transient_local_emits_warning_and_falls_back(self, caplog) -> None:
        """No Isaac Sim bundled preset is TRANSIENT_LOCAL.

        The helper must log a warning so the operator knows the
        OmniGraph side is NOT honouring the transient_local request
        (the rclpy-side publisher still does).
        """
        import logging

        # The module-level logger in ``marslab.ros2_bridge.qos`` is
        # created with its default configuration; pytest ``caplog``
        # captures via the root logger so we force propagation here
        # rather than relying on the module-level default.
        qos_logger = logging.getLogger("marslab.ros2_bridge.qos")
        prev_propagate = qos_logger.propagate
        qos_logger.propagate = True
        try:
            cfg = QoSProfileConfig(reliability="reliable", durability="transient_local", depth=100)
            with caplog.at_level(logging.WARNING):
                preset = to_omnigraph_qos_preset(cfg)
        finally:
            qos_logger.propagate = prev_propagate

        assert preset == "SystemDefault"
        assert any("transient_local" in rec.message for rec in caplog.records)


class TestToRclpyQosAdapter:
    """Optional rclpy-dependent test (skipped without rclpy)."""

    def test_to_rclpy_qos_builds_profile(self) -> None:
        pytest.importorskip("rclpy")
        from rclpy.qos import DurabilityPolicy, HistoryPolicy, ReliabilityPolicy

        from marslab.ros2_bridge.qos import to_rclpy_qos

        cfg = QoSProfileConfig(
            reliability="best_effort", durability="volatile", history="keep_last", depth=7
        )
        profile = to_rclpy_qos(cfg)
        assert profile.reliability == ReliabilityPolicy.BEST_EFFORT
        assert profile.durability == DurabilityPolicy.VOLATILE
        assert profile.history == HistoryPolicy.KEEP_LAST
        assert profile.depth == 7


class TestOmniGraphSetValuesIncludeQoS:
    """``_build_set_values`` wires ``qosProfile`` on every helper node."""

    def _default_sets(self, **kwargs) -> dict:
        from marslab.ros2_bridge.sensor_graph_builder import _build_set_values

        sets = _build_set_values(
            ns="rover",
            topics={
                "imu": "imu",
                "rgb": "rgb/image_raw",
                "depth": "depth/image_raw",
                "lidar": "lidar/points",
            },
            imu_prim_path="/World/Rover/imu",
            camera_prim_path="/World/Rover/camera",
            camera_resolution=(640, 480),
            lidar_3d_prim_path="/World/Rover/lidar3d",
            **kwargs,
        )
        return dict(sets)

    def test_pubimu_has_sensor_data_preset_by_default(self) -> None:
        sets = self._default_sets()
        assert sets["PubIMU.inputs:qosProfile"] == "SensorData"

    def test_cam_rgb_has_sensor_data_preset_by_default(self) -> None:
        sets = self._default_sets()
        assert sets["CamRGB.inputs:qosProfile"] == "SensorData"

    def test_cam_depth_has_sensor_data_preset_by_default(self) -> None:
        sets = self._default_sets()
        assert sets["CamDepth.inputs:qosProfile"] == "SensorData"

    def test_lidar3d_has_sensor_data_preset_by_default(self) -> None:
        sets = self._default_sets()
        assert sets["Lidar3DHelper.inputs:qosProfile"] == "SensorData"

    def test_pubtf_has_system_default_by_default(self) -> None:
        sets = self._default_sets()
        assert sets["PubTF.inputs:qosProfile"] == "SystemDefault"

    def test_lidar2d_qos_applied_when_included(self) -> None:
        from marslab.ros2_bridge.sensor_graph_builder import _build_set_values

        sets = dict(
            _build_set_values(
                ns="rover",
                topics={
                    "imu": "imu",
                    "rgb": "rgb/image_raw",
                    "depth": "depth/image_raw",
                    "lidar": "lidar/points",
                    "scan": "scan",
                },
                imu_prim_path="/World/Rover/imu",
                camera_prim_path="/World/Rover/camera",
                camera_resolution=(640, 480),
                lidar_3d_prim_path="/World/Rover/lidar3d",
                lidar_2d_prim_path="/World/Rover/lidar2d",
            )
        )
        assert sets["Lidar2DHelper.inputs:qosProfile"] == "SensorData"

    def test_override_preset_threaded_through(self) -> None:
        """Custom preset strings propagate to every helper."""
        sets = self._default_sets(
            sensor_qos_preset="SystemDefault", tf_qos_preset="ParameterEvents"
        )
        assert sets["PubIMU.inputs:qosProfile"] == "SystemDefault"
        assert sets["CamRGB.inputs:qosProfile"] == "SystemDefault"
        assert sets["Lidar3DHelper.inputs:qosProfile"] == "SystemDefault"
        assert sets["PubTF.inputs:qosProfile"] == "ParameterEvents"


class TestResolveQosPresets:
    """``sensor_graph._resolve_qos_presets`` reads YAML overrides."""

    def test_defaults_when_yaml_absent(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_qos_presets

        sensor_preset, tf_preset = _resolve_qos_presets({"namespace": "rover", "topics": {}})
        assert sensor_preset == "SensorData"
        # transient_local default → falls back to SystemDefault
        # (to_omnigraph_qos_preset emits a warning).
        assert tf_preset == "SystemDefault"

    def test_override_sensor_to_reliable_flips_preset(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_qos_presets

        sensor_preset, _ = _resolve_qos_presets(
            {
                "namespace": "rover",
                "topics": {},
                "sensor_qos": {"reliability": "reliable", "durability": "volatile"},
            }
        )
        # Reliable + volatile cannot map to SensorData.
        assert sensor_preset == "SystemDefault"

    def test_invalid_yaml_value_raises(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_qos_presets

        with pytest.raises(ValidationError):
            _resolve_qos_presets(
                {
                    "namespace": "rover",
                    "topics": {},
                    "sensor_qos": {"reliability": "nonsense"},
                }
            )
