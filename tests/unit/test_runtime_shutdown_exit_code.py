"""Regression tests for runtime shutdown exit codes.

``os._exit(0)`` was previously used in ``marslab/main.py``; the
call reports success to the shell when ``simulation_app.close()``
raises. The fix replaces ``0`` with ``1`` so CI / pytest observe a
genuine failure. The ``os._exit`` call itself is retained (not
``sys.exit``) to bypass Kit's ``atexit`` SIGSEGV hazard documented in
``tests/visual_inspection/checklist.md``.

The tests here are textual guards: the affected runtime paths require
Isaac Sim / rclpy imports that are not offline-importable, so we
instead lock in the source-level invariant (no ``os._exit(0)`` in the
shutdown teardown block). Reverting to ``os._exit(0)`` will fail CI.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_source(relative: str) -> str:
    return (REPO_ROOT / relative).read_text(encoding="utf-8")


def test_main_uses_exit_code_1_on_close_failure():
    """``marslab/main.py`` must use ``os._exit(1)``."""
    source = _load_source("marslab/main.py")
    assert "simulation_app.close()" in source
    assert "os._exit(1)" in source, (
        "main.py shutdown path must use os._exit(1) -- reverting to "
        "os._exit(0) hides Kit teardown failures from CI."
    )
    shutdown_idx = source.rfind("simulation_app.close()")
    tail = source[shutdown_idx:]
    assert "os._exit(0)" not in tail, "main.py teardown reverted to os._exit(0)."
