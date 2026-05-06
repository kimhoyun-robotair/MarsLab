"""Runtime config loading helpers — wrap marslab.config.loader.load_and_validate()."""

from __future__ import annotations

from typing import Any, Dict

from marslab.config.scenario_loader import load_scenario_config


def load_runtime_config_dict(config_path: str) -> Dict[str, Any]:
    """Legacy dict path — wraps ``scenario_loader.load_scenario_config``.

    The runtime currently consumes the raw merged YAML dict (used by
    ``marslab/main.py``) rather than a pydantic-validated model. New
    code paths that need pydantic validation should call
    :func:`marslab.config.loader.load_and_validate` directly.

    Args:
        config_path: Path to scenario YAML or flat config.

    Returns:
        Parsed dict with ``base_config`` references deep-merged.
    """
    return load_scenario_config(config_path)
