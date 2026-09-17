"""Bootstrap SimulationApp at the Isaac runtime boundary.
Typed settings select headless mode and optional ROS enablement.
The first Kit update occurs before the live handle is returned."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Final, Protocol

from marslab.config.schema.runtime import RuntimeConfig

DEFAULT_ROS2_BRIDGE_EXTENSION: Final[str] = "isaacsim.ros2.bridge"


class KitAppHandle(Protocol):
    def post_quit(self, return_code: int = 0) -> None: ...


class SimulationAppHandle(Protocol):
    @property
    def app(self) -> KitAppHandle: ...

    def update(self) -> None: ...

    def close(self) -> None: ...


def close_simulation_app(simulation_app: SimulationAppHandle, exit_status: int) -> None:
    """Give Kit the process status before its supported fast shutdown."""
    simulation_app.app.post_quit(exit_status)
    logging.getLogger(__name__).info("Closing SimulationApp with exit status %d.", exit_status)
    simulation_app.close()


def boot_simulation_app(
    runtime: RuntimeConfig,
    renderer: str = "RaytracedLighting",
) -> SimulationAppHandle:
    """Create a live SimulationApp and perform its first update."""
    headless = runtime.headless
    ros2_enabled = runtime.ros2_enabled
    isaacsim_module = import_module("isaacsim")
    simulation_app: SimulationAppHandle = isaacsim_module.__dict__["SimulationApp"](
        {
            "headless": headless,
            "renderer": renderer,
            "fast_shutdown": True,
            "enable_motion_bvh": runtime.enable_motion_bvh,
        },
    )

    try:
        if ros2_enabled:
            extension_module = import_module("isaacsim.core.utils.extensions")
            if not extension_module.__dict__["enable_extension"](DEFAULT_ROS2_BRIDGE_EXTENSION):
                raise RuntimeError(f"Could not enable {DEFAULT_ROS2_BRIDGE_EXTENSION}")
        simulation_app.update()
    except BaseException:
        logging.getLogger(__name__).exception("SimulationApp boot failed.")
        try:
            close_simulation_app(simulation_app, exit_status=1)
        except Exception:
            logging.getLogger(__name__).exception("SimulationApp cleanup failed during boot.")
        raise
    return simulation_app


__all__ = [
    "DEFAULT_ROS2_BRIDGE_EXTENSION",
    "SimulationAppHandle",
    "boot_simulation_app",
    "close_simulation_app",
]
