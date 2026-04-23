"""Seed propagation regression for ``run_stage3_monolithic_new.py`` (R1-6a).

The twin monolithic runner consumes the raw dict returned by
:func:`marslab.config.scenario_loader.load_scenario_config` rather than a
:class:`MarsLabConfig`. G7 still requires that
``terrain.seed == mars_env.seed + 1``; these tests lock down the dict-level
helper :func:`marslab.config.loader.propagate_seeds_in_dict` and verify that
the twin imports and calls it.

Oracle (``run_stage3_monolithic.py``, md5 ``d4e147cd…``) is explicitly
excluded — it is frozen and does not propagate seeds.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path

from marslab.config.loader import propagate_seeds_in_dict

REPO_ROOT = Path(__file__).resolve().parents[2]
TWIN_PATH = REPO_ROOT / "scripts" / "phase1" / "run_stage3_monolithic_new.py"


def test_propagate_seeds_in_dict_default_master():
    """With no master override, uses ``mars_env.seed`` as the anchor."""
    cfg = {"mars_env": {"seed": 7}, "terrain": {}}
    out = propagate_seeds_in_dict(cfg)
    assert out is cfg  # in-place mutation
    assert out["mars_env"]["seed"] == 7
    assert out["terrain"]["seed"] == 8


def test_propagate_seeds_in_dict_explicit_master():
    """Explicit ``master_seed`` wins over the ``mars_env`` value."""
    cfg = {"mars_env": {"seed": 1}, "terrain": {"seed": 99}}
    propagate_seeds_in_dict(cfg, master_seed=42)
    assert cfg["mars_env"]["seed"] == 42
    assert cfg["terrain"]["seed"] == 43


def test_propagate_seeds_in_dict_default_seed_when_missing():
    """Missing ``mars_env.seed`` falls back to the library default (42)."""
    cfg = {"mars_env": {}, "terrain": {}}
    propagate_seeds_in_dict(cfg)
    assert cfg["mars_env"]["seed"] == 42
    assert cfg["terrain"]["seed"] == 43


def test_propagate_seeds_in_dict_noop_when_blocks_missing():
    """Omitting either ``mars_env`` or ``terrain`` leaves the dict untouched."""
    cfg = {"mars_env": {"seed": 5}}
    propagate_seeds_in_dict(cfg)
    assert cfg == {"mars_env": {"seed": 5}}


def test_propagate_seeds_in_dict_determinism():
    """Same input → same output across repeated calls (G7)."""
    master = 123
    a = {"mars_env": {"seed": 0}, "terrain": {"seed": 0}}
    b = {"mars_env": {"seed": 0}, "terrain": {"seed": 0}}
    propagate_seeds_in_dict(a, master_seed=master)
    propagate_seeds_in_dict(b, master_seed=master)
    assert a == b


def test_propagate_seeds_in_dict_rejects_float_seed():
    """Float seed in YAML (``seed: 42.0``) raises rather than silently truncating."""
    import pytest

    cfg = {"mars_env": {"seed": 42.0}, "terrain": {}}
    with pytest.raises(TypeError, match="must be int"):
        propagate_seeds_in_dict(cfg)


def test_propagate_seeds_in_dict_rejects_string_seed():
    """String seed (``seed: "42"``) raises — the pydantic twin enforces int."""
    import pytest

    cfg = {"mars_env": {"seed": "42"}, "terrain": {}}
    with pytest.raises(TypeError, match="must be int"):
        propagate_seeds_in_dict(cfg)


def test_propagate_seeds_in_dict_rejects_bool_seed():
    """``bool`` is an ``int`` subclass in Python; exclude explicitly."""
    import pytest

    cfg = {"mars_env": {"seed": True}, "terrain": {}}
    with pytest.raises(TypeError, match="must be int"):
        propagate_seeds_in_dict(cfg)


def test_propagate_seeds_in_dict_rejects_negative_seed():
    """Negative master seeds are a G7-reproducibility smell; reject loudly."""
    import pytest

    cfg = {"mars_env": {"seed": 1}, "terrain": {}}
    with pytest.raises(ValueError, match=">= 0"):
        propagate_seeds_in_dict(cfg, master_seed=-5)


def test_twin_imports_propagate_seeds_in_dict():
    """The twin runner imports ``propagate_seeds_in_dict`` at module scope."""
    assert TWIN_PATH.is_file(), f"Twin not found: {TWIN_PATH}"
    source = TWIN_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "marslab.config.loader":
            for alias in node.names:
                imported_names.add(alias.name)
    assert "propagate_seeds_in_dict" in imported_names, (
        "Twin must import propagate_seeds_in_dict from marslab.config.loader "
        "so that terrain.seed == mars_env.seed + 1 holds at runtime (G7)."
    )


def test_twin_calls_propagate_seeds_in_dict_after_load():
    """The twin invokes ``propagate_seeds_in_dict`` after ``load_scenario_config``."""
    source = TWIN_PATH.read_text(encoding="utf-8")
    load_idx = source.find("load_scenario_config(config_path)")
    propagate_idx = source.find("propagate_seeds_in_dict(cfg)")
    assert load_idx != -1, "load_scenario_config call missing"
    assert propagate_idx != -1, "propagate_seeds_in_dict call missing"
    assert (
        propagate_idx > load_idx
    ), "propagate_seeds_in_dict must be invoked AFTER load_scenario_config"


def test_oracle_still_unmodified():
    """Oracle must not gain a ``propagate_seeds_in_dict`` call (frozen)."""
    oracle_path = REPO_ROOT / "scripts" / "phase1" / "run_stage3_monolithic.py"
    if not oracle_path.is_file():
        return
    source = oracle_path.read_text(encoding="utf-8")
    assert "propagate_seeds_in_dict" not in source, (
        "Oracle (run_stage3_monolithic.py) is frozen — it must not import or "
        "call propagate_seeds_in_dict. The twin holds the paper-experiment path."
    )
    # 2026-04-23: user-authorized one-off Oracle migration to drop the
    # `scripts/phase1/ackermann.py` re-export shim. The import was swapped
    # to `marslab.robots.rover_control`; functionally identical (same
    # function objects). Pre-migration md5 was
    # ``d4e147cd2345f927db18c4d7ad33b854``.
    expected_md5 = "beefa12579dd43f3da27b1dae3c6f852"
    import hashlib

    actual_md5 = hashlib.md5(oracle_path.read_bytes()).hexdigest()
    assert actual_md5 == expected_md5, (
        f"Oracle md5 drift: got {actual_md5}, expected {expected_md5}. "
        "The Oracle file must never change without user approval."
    )


def test_propagate_seeds_in_dict_matches_pydantic_semantics():
    """Dict helper mirrors the pydantic ``propagate_seeds`` rule exactly."""
    from marslab.config.loader import propagate_seeds
    from marslab.config.schema import MarsEnvConfig, MarsLabConfig, TerrainConfig

    for master in (0, 42, 99):
        pyd = MarsLabConfig(
            mars_env=MarsEnvConfig(),
            terrain=TerrainConfig(source="procedural", procedural_preset="flat"),
        )
        pyd = propagate_seeds(pyd, master_seed=master)

        dct: dict = {"mars_env": {"seed": 0}, "terrain": {"seed": 0}}
        propagate_seeds_in_dict(dct, master_seed=master)

        assert dct["mars_env"]["seed"] == pyd.mars_env.seed
        assert dct["terrain"]["seed"] == pyd.terrain.seed


def test_twin_file_exists_and_is_not_oracle():
    """Sanity: twin and Oracle are distinct files (the twin is modifiable)."""
    oracle_path = REPO_ROOT / "scripts" / "phase1" / "run_stage3_monolithic.py"
    assert TWIN_PATH.resolve() != oracle_path.resolve()
    assert os.path.getsize(TWIN_PATH) > 0
