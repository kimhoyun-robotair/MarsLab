"""Unit tests for marslab.cli.stage3_args + stage2_args (offline, P3)."""

from __future__ import annotations

import argparse

import pytest

from marslab.cli.stage2_args import (
    DEFAULT_CONFIG as STAGE2_DEFAULT_CONFIG,
)
from marslab.cli.stage2_args import (
    build_stage2_parser,
    parse_stage2_args,
)
from marslab.cli.stage3_args import build_stage3_parser, parse_stage3_args

# ---------------------------------------------------------------------------
# Stage 3
# ---------------------------------------------------------------------------


def test_build_stage3_parser_returns_argparse_parser() -> None:
    """``build_stage3_parser`` returns a concrete ``ArgumentParser``."""
    parser = build_stage3_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test_stage3_config_is_required() -> None:
    """Omitting ``--config`` must raise ``SystemExit`` (argparse convention)."""
    with pytest.raises(SystemExit):
        parse_stage3_args([])


def test_stage3_minimum_args_defaults_bools_to_false() -> None:
    """Only ``--config`` → ``headless`` and ``no_ros2`` both default to ``False``."""
    ns = parse_stage3_args(["--config", "foo.yaml"])
    assert ns.config == "foo.yaml"
    assert ns.headless is False
    assert ns.no_ros2 is False


def test_stage3_all_flags_set() -> None:
    """``--config + --headless + --no-ros2`` activates all booleans."""
    ns = parse_stage3_args(["--config", "foo.yaml", "--headless", "--no-ros2"])
    assert ns.config == "foo.yaml"
    assert ns.headless is True
    assert ns.no_ros2 is True


def test_stage3_rejects_unknown_argument() -> None:
    """Unrecognised flags must fail with ``SystemExit``."""
    with pytest.raises(SystemExit):
        parse_stage3_args(["--config", "foo.yaml", "--not-a-real-flag"])


def test_stage3_argv_override() -> None:
    """``parse_stage3_args(argv=...)`` uses the provided argv, not sys.argv."""
    ns = parse_stage3_args(["--config", "x"])
    assert ns.config == "x"


# ---------------------------------------------------------------------------
# Stage 2
# ---------------------------------------------------------------------------


def test_stage2_default_config_points_to_mars_env_yaml() -> None:
    """No ``--config`` → default ends with ``mars_env.yaml``."""
    ns = parse_stage2_args([])
    assert ns.config.endswith("mars_env.yaml")
    assert ns.config == STAGE2_DEFAULT_CONFIG
    assert ns.headless is False


def test_stage2_explicit_config_and_headless() -> None:
    """``--config custom.yaml --headless`` propagates both values."""
    ns = parse_stage2_args(["--config", "custom.yaml", "--headless"])
    assert ns.config == "custom.yaml"
    assert ns.headless is True


def test_build_stage2_parser_returns_argparse_parser() -> None:
    """``build_stage2_parser`` returns a concrete ``ArgumentParser``."""
    parser = build_stage2_parser()
    assert isinstance(parser, argparse.ArgumentParser)
