"""Deferred Isaac Sim application bootstrap.

Consumes typed runtime settings, creates the app, optionally enables ROS2,
and performs the first update before returning the live handle.
"""

from __future__ import annotations

from importlib import import_module
from typing import Final, Protocol

from marslab.config.schema.runtime import RuntimeConfig

DEFAULT_ROS2_BRIDGE_EXTENSION: Final[str] = "isaacsim.ros2.bridge"


class SimulationAppHandle(Protocol):
    def update(self) -> None: ...

    def close(self) -> None: ...


def boot_simulation_app(
    runtime: RuntimeConfig,
    renderer: str = "RaytracedLighting",
) -> SimulationAppHandle:
    """Create a live SimulationApp and perform its first update."""
    headless = runtime.headless
    ros2_enabled = runtime.ros2_enabled
    isaacsim_module = import_module("isaacsim")
    simulation_app: SimulationAppHandle = isaacsim_module.__dict__["SimulationApp"](
        {"headless": headless, "renderer": renderer},
    )

    if ros2_enabled:
        extension_module = import_module("isaacsim.core.utils.extensions")
        extension_module.__dict__["enable_extension"](DEFAULT_ROS2_BRIDGE_EXTENSION)

    simulation_app.update()
    return simulation_app


__all__ = ["DEFAULT_ROS2_BRIDGE_EXTENSION", "SimulationAppHandle", "boot_simulation_app"]
