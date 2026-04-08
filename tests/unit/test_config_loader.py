"""Unit tests for marslab.config.loader."""

import pytest
from pydantic import ValidationError

from marslab.config.loader import load_config, propagate_seeds
from marslab.config.schema import MarsLabConfig


def test_load_config_valid():
    """Load the master config file successfully."""
    c = load_config("configs/mars_env.yaml")
    assert isinstance(c, MarsLabConfig)
    assert c.mars_env.gravity == 3.72
    assert c.terrain.source == "hirise"
    assert len(c.robots) == 1
    assert c.robots[0].type == "rover"


def test_load_config_file_not_found():
    """Missing file raises FileNotFoundError with full path."""
    with pytest.raises(FileNotFoundError, match="nonexistent.yaml"):
        load_config("nonexistent.yaml")


def test_load_config_invalid_values(tmp_path):
    """Invalid config values raise ValidationError."""
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("mars_env:\n  gravity: 99.0\n")
    with pytest.raises(ValidationError):
        load_config(str(bad_yaml))


def test_load_config_empty_yaml(tmp_path):
    """Empty YAML file produces defaults (terrain needs procedural for no dem_path)."""
    empty_yaml = tmp_path / "empty.yaml"
    empty_yaml.write_text("terrain:\n  source: procedural\n")
    c = load_config(str(empty_yaml))
    assert isinstance(c, MarsLabConfig)
    assert c.mars_env.gravity == 3.72


def test_propagate_seeds_master():
    """Master seed propagates to all sub-configs."""
    c = MarsLabConfig(
        terrain=TerrainConfig(source="procedural"),
        benchmark=BenchmarkConfig(),
    )
    result = propagate_seeds(c, master_seed=123)
    assert result.mars_env.seed == 123
    assert result.terrain.seed == 124
    assert result.benchmark.seed == 125


def test_propagate_seeds_deterministic():
    """Same master seed produces identical results."""
    c = MarsLabConfig(terrain=TerrainConfig(source="procedural"))
    r1 = propagate_seeds(c, master_seed=42)
    r2 = propagate_seeds(c, master_seed=42)
    assert r1.mars_env.seed == r2.mars_env.seed
    assert r1.terrain.seed == r2.terrain.seed


def test_propagate_seeds_different():
    """Different master seeds produce different child seeds."""
    c = MarsLabConfig(terrain=TerrainConfig(source="procedural"))
    r1 = propagate_seeds(c, master_seed=42)
    r2 = propagate_seeds(c, master_seed=99)
    assert r1.terrain.seed != r2.terrain.seed


def test_propagate_seeds_uses_existing():
    """Without master_seed, uses mars_env.seed."""
    c = MarsLabConfig(
        mars_env=MarsEnvConfig(seed=100),
        terrain=TerrainConfig(source="procedural"),
    )
    result = propagate_seeds(c)
    assert result.mars_env.seed == 100
    assert result.terrain.seed == 101


# Need these imports for test_propagate_seeds_master
from marslab.config.schema import BenchmarkConfig, MarsEnvConfig, TerrainConfig  # noqa: E402
