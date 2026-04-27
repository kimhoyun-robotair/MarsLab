"""Thin CLI entry point for the MarsLab v1.0 Stage 3 rover runtime.

This wrapper is the modular entry point for the Stage 3 rover runtime.
It parses ``--scenario`` / ``--headless`` / ``--no-ros2`` and delegates
to :func:`scripts.phase1.main.main`, which drives the refactored
facades in ``marslab.runtime``, ``marslab.robots``, ``marslab.sensors``,
and ``marslab.ros2_bridge``.

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
    """Delegate to :func:`scripts.phase1.main.main` after argument translation.

    The downstream runner uses ``--config`` rather than ``--scenario``, so we
    re-inject the translated argv before calling into it.  This keeps
    ``run_marslab.py`` a thin, genuinely executable CLI facade without
    duplicating the Isaac Sim boot + sensor wiring.

    Args:
        argv: Optional argv list for tests; ``None`` means ``sys.argv``.

    Returns:
        Process exit code (``0`` on normal shutdown).
    """
    args = parse_args(argv)
    scenario = args.scenario.strip()

    forwarded: List[str] = ["run_marslab", "--config", scenario]
    if args.headless:
        forwarded.append("--headless")
    if args.no_ros2:
        forwarded.append("--no-ros2")

    original_argv = sys.argv
    try:
        sys.argv = forwarded
        from scripts.phase1.main import main as _stage3_main

        return int(_stage3_main())
    finally:
        sys.argv = original_argv


if __name__ == "__main__":
    raise SystemExit(main())
