"""Argparse contract for ``scripts/run_marslab.py``.

Offline: exercises the argparse layer only -- the module is loaded
by path so importing it does not bootstrap Isaac Sim.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_MARSLAB = REPO_ROOT / "scripts" / "run_marslab.py"


def _load_module():
    """Import ``scripts/run_marslab.py`` by absolute path."""
    spec = importlib.util.spec_from_file_location("marslab_cli_entry", RUN_MARSLAB)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_parser_returns_argparse_parser() -> None:
    """``build_parser`` yields a usable :class:`argparse.ArgumentParser`."""
    mod = _load_module()
    parser = mod.build_parser()
    assert parser.prog.endswith(".py") or "marslab" in parser.prog.lower() or parser.prog
    # Round-trip: known-good args parse successfully.
    ns = parser.parse_args(["--scenario", "configs/scenarios/jezero_flat.yaml"])
    assert ns.scenario == "configs/scenarios/jezero_flat.yaml"
    assert ns.headless is False
    assert ns.no_ros2 is False


def test_parse_args_headless_flag() -> None:
    """``--headless`` flips the boolean to ``True``."""
    mod = _load_module()
    ns = mod.parse_args(
        [
            "--scenario",
            "configs/scenarios/jezero_flat.yaml",
            "--headless",
        ]
    )
    assert ns.headless is True
    assert ns.no_ros2 is False


def test_parse_args_no_ros2_flag() -> None:
    """``--no-ros2`` flips the boolean to ``True``."""
    mod = _load_module()
    ns = mod.parse_args(
        [
            "--scenario",
            "configs/scenarios/jezero_flat.yaml",
            "--no-ros2",
        ]
    )
    assert ns.no_ros2 is True


def test_scenario_is_required() -> None:
    """Omitting ``--scenario`` triggers the argparse ``SystemExit``."""
    mod = _load_module()
    with pytest.raises(SystemExit):
        mod.parse_args([])


def test_help_text_contains_all_flags() -> None:
    """``--help`` surfaces every advertised CLI flag."""
    mod = _load_module()
    parser = mod.build_parser()
    help_text = parser.format_help()
    assert "--scenario" in help_text
    assert "--headless" in help_text
    assert "--no-ros2" in help_text


def test_module_is_thin_wrapper() -> None:
    """The entry point stays a thin wrapper (LOC budget sanity check).

    The wrapper targets ~68-72 LOC; we allow a reasonable margin for
    docstrings but guard against accidental code duplication.
    """
    source = RUN_MARSLAB.read_text(encoding="utf-8")
    lines = source.splitlines()
    assert len(lines) < 200, f"run_marslab.py grew to {len(lines)} LOC -- extract further"


def test_module_import_does_not_boot_isaac_sim() -> None:
    """Importing ``run_marslab`` must not trigger ``SimulationApp`` boot."""
    # If the module imported anything Isaac-Sim-dependent at top level, the
    # import below would fail in this offline test environment.
    sys.modules.pop("marslab_cli_entry", None)
    _load_module()
