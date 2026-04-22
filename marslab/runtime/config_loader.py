"""Runtime config loading helpers — wrap marslab.config.loader.load_and_validate()."""

from __future__ import annotations

from typing import Any, Dict, Optional

from marslab.config.loader import load_and_validate
from marslab.config.scenario_loader import load_scenario_config
from marslab.config.schema import MarsLabConfig


def load_runtime_config(config_path: str, master_seed: Optional[int] = None) -> MarsLabConfig:
    """Load + validate scenario YAML through pydantic (preferred runtime API).

    Thin wrapper around ``marslab.config.loader.load_and_validate`` so that
    scripts can depend on a single ``marslab.runtime`` facade instead of the
    deeper ``marslab.config`` module layout.

    Args:
        config_path: Path to scenario YAML or flat config.
        master_seed: Optional override for the master seed propagated to
            sub-configs.

    Returns:
        Fully validated ``MarsLabConfig`` with propagated seeds.
    """
    return load_and_validate(config_path, master_seed=master_seed)


def load_runtime_config_dict(config_path: str) -> Dict[str, Any]:
    """Legacy dict path — wraps ``scenario_loader.load_scenario_config``.

    Use when the consumer still expects the raw merged YAML dict
    (currently ``run_stage2.py`` and ``run_stage3_monolithic_new.py``).
    Prefer :func:`load_runtime_config` for new code paths that can consume
    the pydantic-validated model.

    Args:
        config_path: Path to scenario YAML or flat config.

    Returns:
        Parsed dict with ``base_config`` references deep-merged.
    """
    return load_scenario_config(config_path)
