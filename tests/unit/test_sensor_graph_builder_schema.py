"""Unit tests for marslab.config.schema.ros2_bridge.Ros2BridgeConfig."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestGraphPathValidation:
    """``Ros2BridgeConfig.graph_path`` enforces USD prim-path hygiene."""

    def test_default_matches_legacy_constant(self) -> None:
        """Default must equal the historical ``GRAPH_PATH`` literal."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig
        from marslab.ros2_bridge.sensor_graph import GRAPH_PATH

        cfg = Ros2BridgeConfig()
        assert cfg.graph_path == GRAPH_PATH
        assert cfg.graph_path == "/World/Stage3ROS2Graph"

    def test_rover_m2020_value_accepted(self) -> None:
        """The actual runtime prim path loads cleanly."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        cfg = Ros2BridgeConfig(graph_path="/World/Stage3ROS2Graph")
        assert cfg.graph_path == "/World/Stage3ROS2Graph"

    def test_custom_path_accepted(self) -> None:
        """Any ``/``-prefixed, whitespace-free string is valid."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        cfg = Ros2BridgeConfig(graph_path="/Scenarios/Stage4/MultiRoverGraph")
        assert cfg.graph_path == "/Scenarios/Stage4/MultiRoverGraph"

    def test_empty_string_rejected(self) -> None:
        """``graph_path=""`` fails the non-empty check."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError, match="non-empty"):
            Ros2BridgeConfig(graph_path="")

    def test_missing_leading_slash_rejected(self) -> None:
        """Relative prim paths are invalid in USD."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError, match="must start with '/'"):
            Ros2BridgeConfig(graph_path="World/Stage3ROS2Graph")

    def test_internal_whitespace_rejected(self) -> None:
        """Whitespace anywhere in the prim path fails validation."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError, match="must not contain whitespace"):
            Ros2BridgeConfig(graph_path="/World/Stage3 ROS2Graph")

    def test_leading_whitespace_rejected(self) -> None:
        """Leading space also fails the whitespace check (slash test passes first)."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError):
            Ros2BridgeConfig(graph_path=" /World/Stage3ROS2Graph")

    def test_tab_rejected(self) -> None:
        """Tab characters are treated as whitespace."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError, match="whitespace"):
            Ros2BridgeConfig(graph_path="/World/\tStage3ROS2Graph")


class TestCmdVelQueueSizeValidation:
    """``cmd_vel_queue_size`` lives in the same schema block."""

    def test_default_is_ten(self) -> None:
        """Default preserves the historical ``queue_size=10`` literal."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        cfg = Ros2BridgeConfig()
        assert cfg.cmd_vel_queue_size == 10

    def test_zero_rejected(self) -> None:
        """``ge=1`` bound rejects zero-depth queues."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError):
            Ros2BridgeConfig(cmd_vel_queue_size=0)

    def test_negative_rejected(self) -> None:
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError):
            Ros2BridgeConfig(cmd_vel_queue_size=-5)

    def test_upper_bound_enforced(self) -> None:
        """``le=1000`` bound catches accidental huge queues."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        with pytest.raises(ValidationError):
            Ros2BridgeConfig(cmd_vel_queue_size=1001)

    def test_boundary_values_accepted(self) -> None:
        """Both ``1`` and ``1000`` are inclusive."""
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig

        assert Ros2BridgeConfig(cmd_vel_queue_size=1).cmd_vel_queue_size == 1
        assert Ros2BridgeConfig(cmd_vel_queue_size=1000).cmd_vel_queue_size == 1000


class TestResolveGraphPath:
    """``sensor_graph._resolve_graph_path`` is the shared validation entry."""

    def test_absent_key_returns_module_default(self) -> None:
        from marslab.ros2_bridge.sensor_graph import GRAPH_PATH, _resolve_graph_path

        assert _resolve_graph_path({"namespace": "rover"}) == GRAPH_PATH

    def test_present_key_is_returned(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_graph_path

        result = _resolve_graph_path({"graph_path": "/Custom/Graph"})
        assert result == "/Custom/Graph"

    def test_invalid_key_raises_via_schema(self) -> None:
        """A bad prim path surfaces the pydantic ``ValidationError``."""
        from marslab.ros2_bridge.sensor_graph import _resolve_graph_path

        with pytest.raises(ValidationError):
            _resolve_graph_path({"graph_path": "no-leading-slash"})

    def test_empty_string_raises_via_schema(self) -> None:
        from marslab.ros2_bridge.sensor_graph import _resolve_graph_path

        with pytest.raises(ValidationError):
            _resolve_graph_path({"graph_path": ""})


class TestPackageReexport:
    """Aggregator exposes the new schema for top-level imports."""

    def test_importable_from_schema_package(self) -> None:
        from marslab.config.schema import Ros2BridgeConfig as Exported
        from marslab.config.schema.ros2_bridge import Ros2BridgeConfig as Direct

        assert Exported is Direct
