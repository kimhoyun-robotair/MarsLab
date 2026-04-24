"""Stage 2 runtime CLI parser.

Extracted from ``scripts/phase1/run_stage2.py`` L147-159 during R3-A2
refactor. Unlike Stage 3, ``--config`` carries a default
(``configs/mars_env.yaml``) because Stage 2 is the terrain/atmosphere
viewer and most invocations use the canonical env file.

Contract:
    --config   (default=<repo>/configs/mars_env.yaml)
    --headless (store_true)   Run Isaac Sim without GUI.
"""

from __future__ import annotations

import argparse
import os
from typing import List, Optional

from marslab.cli import add_headless_flag

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DEFAULT_CONFIG = os.path.join(_REPO_ROOT, "configs", "mars_env.yaml")


def build_stage2_parser() -> argparse.ArgumentParser:
    """Construct the Stage 2 argparse.ArgumentParser.

    Returns:
        Configured ArgumentParser mirroring run_stage2.py L147-159.
    """
    parser = argparse.ArgumentParser(
        description="Phase 1 Stage 2 runtime: Mars terrain + atmosphere viewer."
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="Path to Stage 2 YAML config (default: configs/mars_env.yaml)",
    )
    add_headless_flag(parser, help_text="Run Isaac Sim without the GUI.")
    return parser


def parse_stage2_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse Stage 2 CLI arguments.

    Args:
        argv: Optional argv list for testability. ``None`` uses ``sys.argv``.

    Returns:
        argparse.Namespace with ``config`` (str), ``headless`` (bool).
    """
    parser = build_stage2_parser()
    return parser.parse_args(argv)
