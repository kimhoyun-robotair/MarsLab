"""Seed propagation for raw-dict YAML configs (no pydantic dependency).

The passthrough pipeline (``atmosphere_boot``) reads scenario YAMLs as
raw dicts and never constructs ``MarsLabConfig``. Only the dict-level
seed-propagation helper survives here; the typed ``load_and_validate``
path was retired with the legacy ``marslab/main.py`` pipeline.
"""


def propagate_seeds_in_dict(cfg: dict, master_seed: int | None = None) -> dict:
    """Enforce ``terrain.seed == mars_env.seed + 1`` on a raw config dict.

    Runtime scripts that consume the raw dict returned by
    :func:`marslab.config.yaml_loader.load_scenario_config` (rather than
    constructing a :class:`MarsLabConfig`) still need the deterministic
    seeding invariant that ``terrain.seed == mars_env.seed + 1`` so every
    randomised stage receives a deterministic, distinct seed. This helper
    enforces that invariant on the dict path.

    Operates on a raw ``dict`` (no pydantic validation) so it works
    before any schema construction; performs explicit type / range
    checking that pydantic would otherwise catch on the typed path; and
    mutates and returns the dict in place.

    Missing ``mars_env`` or ``terrain`` blocks are left untouched —
    callers that skip terrain (e.g. the USDA-external passthrough) are
    free to omit them.

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
    # ``bool`` is an ``int`` subclass in Python -- exclude explicitly so a
    # ``seed: true`` YAML author gets a loud error instead of silent
    # truncation, and a negative seed (a reproducibility smell) is rejected.
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise TypeError(f"mars_env.seed must be int, got {type(raw).__name__}: {raw!r}")
    if raw < 0:
        raise ValueError(f"mars_env.seed must be >= 0 for deterministic reproducibility; got {raw}")
    seed = raw
    mars_cfg["seed"] = seed
    terrain_cfg["seed"] = seed + 1
    return cfg
