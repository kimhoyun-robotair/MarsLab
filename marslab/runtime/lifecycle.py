"""Wrap one simulation phase with ordered cleanup ownership.
Failures preserve the primary status while cleanup still runs.
The module does not own individual bridge or world resources."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from marslab.runtime.loop_context import LoopContext
from marslab.runtime.main_loop import run_main_loop

logger = logging.getLogger(__name__)


class RclpyShutdown(Protocol):
    def __call__(self) -> None: ...


class NodeHandle(Protocol):
    def destroy_node(self) -> None: ...


class BridgeContextHandle(Protocol):
    node: NodeHandle


class SimulationAppHandle(Protocol):
    def close(self) -> None: ...


class LoopRunner(Protocol):
    def __call__(self, ctx: LoopContext) -> int: ...


@dataclass(frozen=True, slots=True)
class CleanupResources:
    bridge: BridgeContextHandle | None = None
    rclpy_shutdown: RclpyShutdown | None = None
    simulation_app: SimulationAppHandle | None = None


@dataclass(frozen=True, slots=True)
class LifecycleResult:
    status: int
    run_error: Exception | None
    cleanup_errors: tuple[tuple[str, Exception], ...]


def run_phase(ctx: LoopContext) -> int:
    """Invoke the existing main loop without changing its behavior."""
    return run_main_loop(ctx)


def cleanup_phase(resources: CleanupResources) -> tuple[tuple[str, Exception], ...]:
    """Release concrete handles in reverse creation order."""
    errors: list[tuple[str, Exception]] = []

    if resources.bridge is not None:
        _destroy_bridge_node(resources.bridge, errors)
    if resources.rclpy_shutdown is not None:
        _shutdown_rclpy(resources.rclpy_shutdown, errors)
    if resources.simulation_app is not None:
        _close_simulation_app(resources.simulation_app, errors)

    return tuple(errors)


def run_with_cleanup(
    ctx: LoopContext,
    resources: CleanupResources,
    runner: LoopRunner = run_phase,
) -> LifecycleResult:
    """Run once, always clean up, and retain the primary failure/status."""
    run_error: Exception | None = None
    try:
        status = runner(ctx)
    except Exception as error:  # noqa: BLE001
        status = 1
        run_error = error

    cleanup_errors = cleanup_phase(resources)
    if run_error is not None:
        logger.error(
            "Simulation run failed.",
            exc_info=(type(run_error), run_error, run_error.__traceback__),
        )
    for operation, cleanup_error in cleanup_errors:
        logger.error(
            "Cleanup failed at %s.",
            operation,
            exc_info=(type(cleanup_error), cleanup_error, cleanup_error.__traceback__),
        )
    if status != 0:
        return LifecycleResult(status=status, run_error=run_error, cleanup_errors=cleanup_errors)
    if cleanup_errors:
        return LifecycleResult(status=1, run_error=None, cleanup_errors=cleanup_errors)
    return LifecycleResult(status=0, run_error=None, cleanup_errors=())


def _destroy_bridge_node(
    bridge: BridgeContextHandle,
    errors: list[tuple[str, Exception]],
) -> None:
    try:
        bridge.node.destroy_node()
    except Exception as error:  # noqa: BLE001
        errors.append(("bridge.node.destroy_node", error))


def _shutdown_rclpy(
    shutdown: RclpyShutdown,
    errors: list[tuple[str, Exception]],
) -> None:
    try:
        shutdown()
    except Exception as error:  # noqa: BLE001
        errors.append(("rclpy.shutdown", error))


def _close_simulation_app(
    simulation_app: SimulationAppHandle,
    errors: list[tuple[str, Exception]],
) -> None:
    try:
        simulation_app.close()
    except Exception as error:  # noqa: BLE001
        errors.append(("simulation_app.close", error))


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
