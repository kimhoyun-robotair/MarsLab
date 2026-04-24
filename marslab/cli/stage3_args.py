"""Stage 3 monolithic runtime CLI parser.

Extracted from ``scripts/phase1/run_stage3_monolithic.py`` (Oracle) L230-251
during R3-A2 refactor. The Oracle remains untouched (diff=0); this module
mirrors its ``parse_args()`` contract so the writable twin
(``run_stage3_monolithic_new.py``) and any future Stage 3 consumers can
share a single source of truth.

Contract:
    --config   (required)     Path to Stage 3 scenario YAML.
    --headless (store_true)   Run Isaac Sim without GUI.
    --no-ros2  (store_true)   Skip rclpy / OmniGraph ROS2 bridge.

Whitespace stripping of ``args.config`` is intentionally left to the caller
(Oracle L248-250 strips after parse). Keeping the parser pure means unit
tests can exercise argparse behavior without coupling to path sanitation.
"""

from __future__ import annotations

import argparse
from typing import List, Optional

from marslab.cli import add_headless_flag


def build_stage3_parser() -> argparse.ArgumentParser:
    """Construct the Stage 3 argparse.ArgumentParser.

    Returns:
        Configured ArgumentParser mirroring Oracle L230-246.
    """
    parser = argparse.ArgumentParser(
        description="Phase 1 Stage 3 monolithic runtime: rover + scene + ROS2."
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to Stage 3 scenario YAML (e.g. configs/scenarios/jezero_flat.yaml).",
    )
    add_headless_flag(parser, help_text="Run Isaac Sim without the GUI. Default is GUI mode.")
    parser.add_argument(
        "--no-ros2",
        action="store_true",
        help="Skip rclpy / OmniGraph ROS2 bridge (offline rover+scene diagnostic).",
    )
    return parser


def parse_stage3_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse Stage 3 CLI arguments.

    Args:
        argv: Optional argv list for testability. ``None`` uses ``sys.argv``.

    Returns:
        argparse.Namespace with ``config`` (str), ``headless`` (bool),
        ``no_ros2`` (bool).
    """
    parser = build_stage3_parser()
    return parser.parse_args(argv)
