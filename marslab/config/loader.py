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


def load_and_validate(
    config_path: str,
    master_seed: int | None = None,
) -> MarsLabConfig:
    """Load a MarsLab scenario or flat YAML and return a validated config.

    Resolves the ``base_config`` key if present (scenario YAML pattern) by
    deep-merging the referenced file with scenario overrides winning, then
    validates the result as a ``MarsLabConfig`` and propagates seeds.

    Args:
        config_path: Path to scenario YAML or flat config.
        master_seed: Optional override for the master seed.

    Returns:
        Fully validated ``MarsLabConfig`` with propagated seeds.

    Raises:
        FileNotFoundError: If ``config_path`` or its ``base_config`` reference
            is missing.
        pydantic.ValidationError: If merged data fails schema validation.
    """
    from marslab.config.yaml_loader import deep_merge, read_yaml  # noqa: PLC0415

    abs_path = os.path.abspath(config_path)
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Configuration file not found: {abs_path}")

    data = read_yaml(abs_path)
    if not isinstance(data, dict):
        data = {}

    if "base_config" in data:
        base_rel = data.pop("base_config")
        anchor_dir = os.path.dirname(abs_path)
        base_abs = (
            base_rel
            if os.path.isabs(base_rel)
            else os.path.normpath(os.path.join(anchor_dir, base_rel))
        )
        if not os.path.isfile(base_abs):
            raise FileNotFoundError(f"base_config referenced by {abs_path} not found: {base_abs}")
        base = read_yaml(base_abs)
        if not isinstance(base, dict):
            base = {}
        data = deep_merge(base, data)

    config = MarsLabConfig(**data)
    config = propagate_seeds(config, master_seed=master_seed)
    return config
