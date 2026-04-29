"""Unit tests for marslab.config.loader.load_and_validate."""

from pathlib import Path

import pytest
import yaml

from marslab.config.loader import load_and_validate
from marslab.config.schema import MarsLabConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_load_and_validate_scenario_with_base_config():
    """jezero_flat.yaml carries rover.base_config; mars_env/terrain/rendering validate."""
    path = REPO_ROOT / "configs" / "scenarios" / "jezero_flat.yaml"
    config = load_and_validate(str(path))
    assert isinstance(config, MarsLabConfig)
    assert config.mars_env.gravity == pytest.approx(3.72)


def test_load_and_validate_flat_yaml(tmp_path):
    """A flat YAML with no ``base_config`` loads directly."""
    flat = tmp_path / "minimal_flat.yaml"
    flat.write_text(
        yaml.safe_dump(
            {
                "mars_env": {"seed": 42},
                "terrain": {
                    "source": "procedural",
                    "procedural_preset": "crater",
                    "terrain_size": [256, 256],
                    "terrain_resolution": 1.0,
                },
                "rendering": {"mode": "ray_tracing"},
            }
        )
    )
    config = load_and_validate(str(flat))
    assert isinstance(config, MarsLabConfig)


def test_load_and_validate_auto_seed_propagation():
    """propagate_seeds is called automatically; terrain.seed == mars_env.seed + 1."""
    path = REPO_ROOT / "configs" / "scenarios" / "jezero_flat.yaml"
    config = load_and_validate(str(path))
    assert config.terrain.seed == config.mars_env.seed + 1


def test_load_and_validate_missing_file():
    with pytest.raises(FileNotFoundError):
        load_and_validate("/does/not/exist.yaml")


def test_load_and_validate_missing_base(tmp_path):
    """Top-level base_config pointing to a non-existent file raises FileNotFoundError."""
    bad = tmp_path / "bad.yaml"
    bad.write_text(yaml.safe_dump({"base_config": "./missing.yaml"}))
    with pytest.raises(FileNotFoundError):
        load_and_validate(str(bad))
