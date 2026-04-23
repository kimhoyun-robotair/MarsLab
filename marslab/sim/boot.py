"""SimulationApp boot helper.

``boot_simulation_app`` mirrors the previous inline logic in
``scripts/phase1/run_stage3_monolithic_new.py`` L396-415 so the rest
of the runtime can stay focused on scenario construction.

Must be called **before** any ``omni.*`` / ``isaacsim.*`` / ``rclpy``
imports.  The Kit app has to be alive first; otherwise those imports
fail at module level.
"""

from __future__ import annotations

from typing import Any

DEFAULT_ROS2_BRIDGE_EXTENSION = "isaacsim.ros2.bridge"


def boot_simulation_app(
    headless: bool = False,
    renderer: str = "RaytracedLighting",
    ros2_bridge_extension: str = DEFAULT_ROS2_BRIDGE_EXTENSION,
) -> Any:
    """Instantiate ``SimulationApp`` and enable the ROS2 bridge extension.

    Args:
        headless: Pass ``True`` for CI / remote runs without a Kit
            viewport; ``False`` keeps the Kit window.
        renderer: Isaac Sim renderer name.  ``"RaytracedLighting"``
            matches the Stage-3 default.
        ros2_bridge_extension: Extension id to ``enable_extension``
            after the app has booted.  Override only for tests.

    Returns:
        The live ``SimulationApp`` instance.  Callers should keep a
        reference and call ``.close()`` at shutdown.
    """
    from isaacsim import SimulationApp

    simulation_app = SimulationApp({"headless": bool(headless), "renderer": renderer})

    from isaacsim.core.utils.extensions import enable_extension

    enable_extension(ros2_bridge_extension)
    simulation_app.update()
    return simulation_app


__all__ = ["boot_simulation_app", "DEFAULT_ROS2_BRIDGE_EXTENSION"]
