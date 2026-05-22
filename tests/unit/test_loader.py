"""Unit tests for marslab.config.loader.propagate_seeds_in_dict."""

import pytest

from marslab.config.loader import propagate_seeds_in_dict


def test_propagates_seed_from_mars_env() -> None:
    """terrain.seed = mars_env.seed + 1 when both blocks present."""
    cfg = {
        "mars_env": {"seed": 10},
        "terrain": {"source": "procedural"},
    }
    out = propagate_seeds_in_dict(cfg)
    assert out["mars_env"]["seed"] == 10
    assert out["terrain"]["seed"] == 11


def test_master_seed_override() -> None:
    """master_seed kwarg overrides mars_env.seed."""
    cfg = {"mars_env": {"seed": 10}, "terrain": {"source": "procedural"}}
    out = propagate_seeds_in_dict(cfg, master_seed=99)
    assert out["mars_env"]["seed"] == 99
    assert out["terrain"]["seed"] == 100


def test_default_seed_when_absent() -> None:
    """Missing mars_env.seed defaults to 42."""
    cfg = {"mars_env": {}, "terrain": {}}
    out = propagate_seeds_in_dict(cfg)
    assert out["mars_env"]["seed"] == 42
    assert out["terrain"]["seed"] == 43


def test_missing_blocks_noop() -> None:
    """Missing mars_env or terrain block leaves cfg untouched."""
    cfg = {"mars_env": {"seed": 5}}
    out = propagate_seeds_in_dict(cfg)
    assert "terrain" not in out
    # When terrain is absent, mars_env.seed is also not mutated
    assert out["mars_env"]["seed"] == 5


def test_bool_seed_rejected() -> None:
    """bool is an int subclass; must be rejected explicitly."""
    cfg = {"mars_env": {"seed": True}, "terrain": {}}
    with pytest.raises(TypeError, match="seed must be int"):
        propagate_seeds_in_dict(cfg)


def test_negative_seed_rejected() -> None:
    """Negative seeds violate deterministic reproducibility."""
    cfg = {"mars_env": {"seed": -1}, "terrain": {}}
    with pytest.raises(ValueError, match="seed must be >= 0"):
        propagate_seeds_in_dict(cfg)


def test_string_seed_rejected() -> None:
    """Non-int seed must be rejected with TypeError."""
    cfg = {"mars_env": {"seed": "42"}, "terrain": {}}
    with pytest.raises(TypeError, match="seed must be int"):
        propagate_seeds_in_dict(cfg)
