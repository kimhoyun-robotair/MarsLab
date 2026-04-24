"""Source-level verification that the twin runner delegates to R6-1 (R6).

The Oracle runtime (``run_stage3_monolithic.py``) is frozen at
md5 ``beefa12579dd43f3da27b1dae3c6f852`` (post 2026-04-23 ackermann-shim
migration; pre-migration md5 ``d4e147cd2345f927db18c4d7ad33b854``); it
must *not* pick up the new ``marslab.runtime.main_loop`` import.  The
writable twin -- now ``scripts/phase1/run_stage4.py`` after the
2026-04-24 decomposition -- is the delegation target for R6-1 and must
both import and call :func:`run_main_loop` exactly once.

These are grep-style assertions on source text — no Isaac Sim, no execution.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TWIN_PATH = REPO_ROOT / "scripts" / "phase1" / "run_stage4.py"
ORACLE_PATH = REPO_ROOT / "scripts" / "phase1" / "run_stage3_monolithic.py"


def test_twin_imports_run_main_loop() -> None:
    """Twin source must reference ``marslab.runtime.main_loop``."""
    source = TWIN_PATH.read_text(encoding="utf-8")
    assert "from marslab.runtime.main_loop import" in source
    assert "run_main_loop" in source


def test_twin_imports_loop_state_dataclasses() -> None:
    """Twin must pull in the three state dataclasses from R6-1."""
    source = TWIN_PATH.read_text(encoding="utf-8")
    for symbol in ("ControlState", "AtmosphereLoopState", "OdomPublishState", "LoopContext"):
        assert symbol in source, f"twin does not reference {symbol}"


def test_twin_calls_run_main_loop() -> None:
    """The twin must invoke ``run_main_loop(ctx)`` (any whitespace inside parens)."""
    source = TWIN_PATH.read_text(encoding="utf-8")
    assert "run_main_loop(ctx)" in source


def test_oracle_does_not_import_main_loop() -> None:
    """The frozen Oracle must remain untouched — no R6-1 import."""
    source = ORACLE_PATH.read_text(encoding="utf-8")
    assert "marslab.runtime.main_loop" not in source
    assert "run_main_loop" not in source


def test_oracle_md5_unchanged() -> None:
    """Hard lock on the Oracle md5 hash.

    2026-04-23: user-authorized one-off migration swapped the
    ``from ackermann import ackermann_command`` shim for the canonical
    ``marslab.robots.rover_control`` import (functionally identical —
    same function objects). New md5 below; R6 must not touch it again
    without user approval.
    """
    import hashlib

    digest = hashlib.md5(ORACLE_PATH.read_bytes()).hexdigest()
    assert (
        digest == "beefa12579dd43f3da27b1dae3c6f852"
    ), f"Oracle md5 drifted to {digest}; run_stage3_monolithic.py is frozen."
