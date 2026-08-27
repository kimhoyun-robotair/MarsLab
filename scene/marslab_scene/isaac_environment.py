"""Isaac-bundled pxr activation for public authoring scripts."""

from __future__ import annotations

from importlib import import_module
from typing import Protocol


class PxrRuntimeHandle(Protocol):
    def update(self) -> None: ...

    def close(self) -> None: ...


def ensure_pxr_runtime(*, headless: bool = True) -> PxrRuntimeHandle | None:
    """Return a temporary Kit app only when pxr requires Isaac initialization."""
    try:
        _ = import_module("pxr")
    except ModuleNotFoundError:
        isaacsim = import_module("isaacsim")
        app: PxrRuntimeHandle = isaacsim.__dict__["SimulationApp"](
            {"headless": headless, "fast_shutdown": True}
        )
        return app
    return None
