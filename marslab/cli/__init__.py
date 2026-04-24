"""MarsLab CLI argparse builders.

Pure Python package (argparse only). No Isaac Sim imports.

Modules:
    stage2_args: Stage 2 terrain/atmosphere viewer parser.
    stage3_args: Stage 3 monolithic rover+scene+ROS2 parser.

Shared spine:
    :func:`add_headless_flag` — ``--headless`` store_true used by both stages.
"""

from __future__ import annotations

import argparse


def add_headless_flag(parser: argparse.ArgumentParser, help_text: str) -> None:
    """Attach the shared ``--headless`` flag to *parser*.

    Both Stage 2 and Stage 3 parsers expose an identically-shaped
    ``--headless`` store_true; only the help string differs between them.

    Args:
        parser: Target parser to mutate in place.
        help_text: Help string to register (verbatim per-stage wording).
    """
    parser.add_argument(
        "--headless",
        action="store_true",
        help=help_text,
    )
