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

    return MarsLabConfig(**(data or {}))


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

    return config.model_copy(update=updates)


def propagate_seeds_in_dict(cfg: dict, master_seed: int | None = None) -> dict:
    """Dict-level twin of :func:`propagate_seeds` for flows that skip pydantic.

    Runtime scripts that consume the raw dict returned by
    :func:`marslab.config.scenario_loader.load_scenario_config` (rather than
    constructing a :class:`MarsLabConfig`) still need G7's invariant that
    ``terrain.seed == mars_env.seed + 1`` so every randomised stage receives
    a deterministic, distinct seed. This helper enforces that invariant on
    the dict path.

    The function mutates and returns ``cfg`` in place. Missing ``mars_env``
    or ``terrain`` blocks are left untouched — callers that skip terrain
    (e.g. structure-only tests) are free to omit them.

    Args:
        cfg: Config dict, typically the output of ``load_scenario_config``.
        master_seed: Optional master seed. Defaults to ``cfg['mars_env']['seed']``
            or 42 if absent.

    Returns:
        The same ``cfg`` dict with ``mars_env.seed`` and ``terrain.seed``
        populated according to the propagation rule.
    """
    mars_cfg = cfg.get("mars_env")
    terrain_cfg = cfg.get("terrain")
    if not isinstance(mars_cfg, dict) or not isinstance(terrain_cfg, dict):
        return cfg
    raw = master_seed if master_seed is not None else mars_cfg.get("seed", 42)
    # Tight type check: pydantic ``propagate_seeds`` receives a typed ``int``
    # from ``MarsEnvConfig``; this dict path must enforce the same contract so
    # a ``seed: 42.0`` YAML author gets a loud error instead of silent
    # truncation, and a negative seed (G7 reproducibility smell) is rejected.
    # ``bool`` is an ``int`` subclass in Python -- exclude explicitly.
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise TypeError(f"mars_env.seed must be int, got {type(raw).__name__}: {raw!r}")
    if raw < 0:
        raise ValueError(
            f"mars_env.seed must be >= 0 for deterministic G7 reproducibility; got {raw}"
        )
    seed = raw
    mars_cfg["seed"] = seed
    terrain_cfg["seed"] = seed + 1
    return cfg


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

    data = read_yaml(abs_path)  # read_yaml returns {} for empty, raises on non-mapping.

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
        data = deep_merge(read_yaml(base_abs), data)

    return propagate_seeds(MarsLabConfig(**data), master_seed=master_seed)
