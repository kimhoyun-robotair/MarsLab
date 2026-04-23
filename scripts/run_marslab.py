"""Thin CLI entry point for the MarsLab v1.0 Stage 3 rover runtime (R6-2).

This wrapper is the *modular* counterpart to
``scripts/phase1/run_stage3_monolithic_new.py`` (twin) and
``scripts/phase1/run_stage3_monolithic.py`` (frozen Oracle).  It exists so
future callers can bypass the monolithic twin entirely once the end-to-end
Isaac Sim smoke test has confirmed parity.  Until that smoke passes, both
entry points coexist.

Usage::

    scripts/isaac_python.sh scripts/run_marslab.py \\
        --scenario configs/scenarios/jezero_flat.yaml

    scripts/isaac_python.sh scripts/run_marslab.py \\
        --scenario configs/scenarios/jezero_flat.yaml --headless --no-ros2
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def build_parser() -> argparse.ArgumentParser:
    """Construct the ``run_marslab`` argparse parser.

    Returns:
        ArgumentParser accepting ``--scenario``, ``--headless``, ``--no-ros2``.
    """
    parser = argparse.ArgumentParser(
        description="MarsLab Stage 3 rover runtime (modular entrypoint).",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Path to a Stage 3 scenario YAML (e.g. configs/scenarios/jezero_flat.yaml).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Isaac Sim without the GUI.",
    )
    parser.add_argument(
        "--no-ros2",
        action="store_true",
        help="Skip rclpy / OmniGraph ROS2 bridge for offline rover+scene diagnostics.",
    )
    return parser


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse ``run_marslab`` CLI arguments.

    Args:
        argv: Optional argv list for tests; ``None`` means ``sys.argv``.

    Returns:
        ``argparse.Namespace`` with ``scenario``, ``headless``, ``no_ros2``.
    """
    return build_parser().parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Delegate to the monolithic twin after argument translation.

    Until the end-to-end Isaac Sim smoke test confirms parity between this
    modular entry point and ``run_stage3_monolithic_new.py``, this function
    re-dispatches into the twin's ``main()`` using the positional arguments
    the twin already understands.  This keeps ``run_marslab.py`` genuinely
    executable today (so CI smoke tests pass) without duplicating the
    ~600 LOC of Isaac Sim boot + sensor wiring.

    Args:
        argv: Optional argv list for tests; ``None`` means ``sys.argv``.

    Returns:
        Process exit code (``0`` on normal shutdown).
    """
    args = parse_args(argv)
    scenario = args.scenario.strip()

    # Re-inject into argv so the twin's argparse (``--config`` flavour) sees
    # the same scenario path. This keeps the two entry points byte-exact
    # while the modular extraction matures.
    forwarded: List[str] = ["run_marslab", "--config", scenario]
    if args.headless:
        forwarded.append("--headless")
    if args.no_ros2:
        forwarded.append("--no-ros2")

    original_argv = sys.argv
    try:
        sys.argv = forwarded
        from scripts.phase1.run_stage3_monolithic_new import main as _twin_main

        return int(_twin_main())
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())
