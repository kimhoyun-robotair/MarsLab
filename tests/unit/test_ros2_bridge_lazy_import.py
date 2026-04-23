"""Regression tests that ``marslab.ros2_bridge`` imports lazily.

R4-4 (2026-04-22) inspection found that ``rclpy`` / ``geometry_msgs``
/ ``sensor_msgs`` / ``nav_msgs`` were already pushed to function-body
scope during earlier refactors.  These tests pin that invariant so
nobody accidentally reintroduces a module-level ROS2 import.

We cannot test ``init_rclpy_side`` "causes rclpy to load" directly
without a real DDS fabric, so we stick to the negative assertions.
"""

from __future__ import annotations

import importlib
import sys
from typing import Iterable


def _prune(modnames: Iterable[str]) -> None:
    """Remove ``modnames`` and any submodules from ``sys.modules``."""
    for key in list(sys.modules):
        for m in modnames:
            if key == m or key.startswith(m + "."):
                sys.modules.pop(key, None)


ROS2_MODULES = ("rclpy", "geometry_msgs", "sensor_msgs", "nav_msgs", "tf2_ros")


class TestLazyROS2Imports:
    def test_importing_package_does_not_load_rclpy(self) -> None:
        _prune(ROS2_MODULES + ("marslab.ros2_bridge",))
        importlib.import_module("marslab.ros2_bridge")
        for mod in ROS2_MODULES:
            assert (
                mod not in sys.modules
            ), f"{mod} leaked into sys.modules via marslab.ros2_bridge import"

    def test_importing_sensor_graph_does_not_load_omni(self) -> None:
        _prune(ROS2_MODULES + ("marslab.ros2_bridge", "omni"))
        importlib.import_module("marslab.ros2_bridge.sensor_graph")
        assert "omni.graph.core" not in sys.modules

    def test_importing_sensor_graph_builder_stays_pure_python(self) -> None:
        _prune(ROS2_MODULES + ("marslab.ros2_bridge", "omni"))
        importlib.import_module("marslab.ros2_bridge.sensor_graph_builder")
        for mod in ROS2_MODULES:
            assert (
                mod not in sys.modules
            ), f"{mod} leaked into sys.modules via sensor_graph_builder import"
        assert "omni" not in sys.modules

    def test_importing_rclpy_integration_defers_rclpy(self) -> None:
        _prune(ROS2_MODULES + ("marslab.ros2_bridge",))
        importlib.import_module("marslab.ros2_bridge.rclpy_integration")
        assert "rclpy" not in sys.modules
