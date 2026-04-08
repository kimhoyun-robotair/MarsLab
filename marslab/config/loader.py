"""YAML configuration loading and seed propagation."""

import os

import yaml

from marslab.config.schema import MarsLabConfig


def load_config(config_path: str) -> MarsLabConfig:
    """Load and validate a MarsLab YAML configuration file.

    Args:
        config_path: Path to the YAML configuration file.

    Returns:
        Validated MarsLabConfig instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        pydantic.ValidationError: If config values fail validation.
    """
    abs_path = os.path.abspath(config_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Configuration file not found: {abs_path}")

    with open(abs_path, "r") as f:
        data = yaml.safe_load(f)

    if data is None:
        data = {}

    return MarsLabConfig(**data)


def propagate_seeds(config: MarsLabConfig, master_seed: int | None = None) -> MarsLabConfig:
    """Derive deterministic child seeds from a master seed.

    Each sub-config gets a unique seed derived from the master seed using
    simple offsets. This ensures full reproducibility from a single seed value.

    Args:
        config: The configuration to update.
        master_seed: Override master seed. If None, uses config.mars_env.seed.

    Returns:
        New MarsLabConfig with propagated seeds.
    """
    seed = master_seed if master_seed is not None else config.mars_env.seed

    updates: dict = {
        "mars_env": config.mars_env.model_copy(update={"seed": seed}),
        "terrain": config.terrain.model_copy(update={"seed": seed + 1}),
    }

    if config.benchmark is not None:
        updates["benchmark"] = config.benchmark.model_copy(update={"seed": seed + 2})

    return config.model_copy(update=updates)
