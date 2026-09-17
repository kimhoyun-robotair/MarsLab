"""Wrap one simulation phase with ordered cleanup ownership.
Failures preserve the primary status while cleanup still runs.
The module does not own individual bridge or world resources."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from marslab.runtime.main_loop import LoopContext, run_main_loop
from marslab.sim.boot import SimulationAppHandle, close_simulation_app

logger = logging.getLogger(__name__)


class RclpyShutdown(Protocol):
    def __call__(self) -> None: ...


class NodeHandle(Protocol):
    def destroy_node(self) -> None: ...


class BridgeContextHandle(Protocol):
    node: NodeHandle


class AtmospherePanelHandle(Protocol):
    def close(self) -> None: ...


class LoopRunner(Protocol):
    def __call__(self, ctx: LoopContext) -> int: ...


@dataclass(slots=True)
class CleanupResources:
    bridge: BridgeContextHandle | None = None
    rclpy_shutdown: RclpyShutdown | None = None
    atmosphere_panel: AtmospherePanelHandle | None = None
    simulation_app: SimulationAppHandle | None = None


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    status: int
    run_error: Exception | None
    cleanup_errors: tuple[tuple[str, Exception], ...]


def run_phase(ctx: LoopContext) -> int:
    """Invoke the existing main loop without changing its behavior."""
    return run_main_loop(ctx)


def cleanup_phase(
    resources: CleanupResources, *, exit_status: int = 0
) -> tuple[tuple[str, Exception], ...]:
    """Release concrete handles in reverse creation order."""
    errors: list[tuple[str, Exception]] = []
    bridge, resources.bridge = resources.bridge, None
    shutdown, resources.rclpy_shutdown = resources.rclpy_shutdown, None
    panel, resources.atmosphere_panel = resources.atmosphere_panel, None
    app, resources.simulation_app = resources.simulation_app, None
    operations = (
        ("bridge.node.destroy_node", bridge.node.destroy_node if bridge is not None else None),
        ("rclpy.shutdown", shutdown),
        ("atmosphere_panel.close", panel.close if panel is not None else None),
    )
    for operation, release in operations:
        if release is None:
            continue
        try:
            release()
            logger.info("Cleanup completed: %s", operation)
        except Exception as error:  # noqa: BLE001
            errors.append((operation, error))
            logger.exception("Cleanup failed at %s.", operation)
    if app is not None:
        try:
            close_simulation_app(app, exit_status=exit_status or int(bool(errors)))
        except Exception as error:  # noqa: BLE001
            errors.append(("simulation_app.close", error))
            logger.exception("Cleanup failed at simulation_app.close.")
    return tuple(errors)


def run_with_cleanup(
    ctx: LoopContext,
    resources: CleanupResources,
    runner: LoopRunner = run_phase,
) -> LifecycleResult:
    """Run once, always clean up, and retain the primary failure/status."""
    run_error: Exception | None = None
    status = 1
    try:
        status = runner(ctx)
    except Exception as error:  # noqa: BLE001
        status = 1
        run_error = error
        logger.exception("Simulation run failed.")
    finally:
        cleanup_errors = cleanup_phase(resources, exit_status=status)
    if status != 0:
        return LifecycleResult(status=status, run_error=run_error, cleanup_errors=cleanup_errors)
    if cleanup_errors:
        return LifecycleResult(status=1, run_error=None, cleanup_errors=cleanup_errors)
    return LifecycleResult(status=0, run_error=None, cleanup_errors=())


__all__ = [
    "BridgeContextHandle",
    "CleanupResources",
    "LifecycleResult",
    "LoopRunner",
    "NodeHandle",
    "RclpyShutdown",
    "SimulationAppHandle",
    "cleanup_phase",
    "run_phase",
    "run_with_cleanup",
]
