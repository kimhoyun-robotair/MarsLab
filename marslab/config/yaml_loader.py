"""YAML loading + deep merge + base_config include for scenario configs.

Public surface:
    ``read_yaml(path) -> dict``
    ``deep_merge(base, override) -> dict``
    ``load_scenario_config(scenario_path) -> dict``

All functions are offline and have zero Isaac Sim / ROS2 dependencies
(P3 offline-testable).
"""

from __future__ import annotations

import copy
import os
from typing import Any, Dict, Optional

import yaml

# Two ``..`` segments: this file lives at ``marslab/config/yaml_loader.py``;
# parent of ``config/`` is ``marslab/`` and its parent is the repo root.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

__all__ = ["REPO_ROOT", "deep_merge", "load_scenario_config", "read_yaml"]


def read_yaml(path: str) -> Dict[str, Any]:
    """Load a YAML file, returning an empty dict for empty files.

    Args:
        path: Absolute or CWD-relative path to a ``.yaml`` / ``.yml`` file.

    Returns:
        Parsed mapping. An empty file returns ``{}``.

    Raises:
        FileNotFoundError: If ``path`` does not exist. The message lists
            up to 8 sibling YAMLs in the same directory so the caller
            can spot typos quickly.
        ValueError: If the YAML root is not a mapping.
    """
    if not os.path.isfile(path):
        # List up to 8 sibling YAMLs so a mistyped path (trailing ``2``,
        # ``.yml`` vs ``.yaml``) is diagnosable without a separate ``ls``.
        parent = os.path.dirname(path) or "."
        nearby: list[str] = []
        if os.path.isdir(parent):
            for name in sorted(os.listdir(parent)):
                if name.endswith((".yaml", ".yml")):
                    nearby.append(name)
                if len(nearby) >= 8:
                    break
        msg = f"Config not found: {path!r}"
        if nearby:
            msg += f" (nearby YAMLs in {parent}: {', '.join(nearby)})"
        raise FileNotFoundError(msg)
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be a mapping: {path}")
    return data


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge two dicts; override wins, lists are replaced.

    Args:
        base: The lower-priority dictionary.  Not mutated.
        override: The higher-priority dictionary.  Not mutated.

    Returns:
        A new dict containing the merge.  Nested dicts are merged
        recursively; non-dict values in ``override`` replace the
        corresponding value in ``base``.  Keys only in ``base`` are
        preserved verbatim.
    """
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _resolve_path(path: str, anchor_dir: Optional[str]) -> str:
    """Expand a path against ``anchor_dir`` or the repo root."""
    if os.path.isabs(path):
        return path
    if anchor_dir is not None:
        candidate = os.path.abspath(os.path.join(anchor_dir, path))
        if os.path.isfile(candidate):
            return candidate
    return os.path.abspath(os.path.join(REPO_ROOT, path))


def load_scenario_config(scenario_path: str) -> Dict[str, Any]:
    """Load a scenario YAML, resolving root and rover ``base_config`` keys.

    Two independent ``base_config`` mechanisms run in order:

    1. **Root-level** ``base_config``: points at a sibling YAML
       (typically ``_base.yaml``) holding the shared ``mars_env`` +
       ``rendering`` defaults so scenario files only keep their real
       overrides.  The scenario dict is deep-merged ON TOP of the base
       dict (scenario wins, lists are replaced).
    2. **Rover-level** ``rover.base_config``: pre-existing mechanism
       that merges ``configs/rover_m2020.yaml`` into the
       scenario's ``rover:`` subtree.  Runs after the root merge so the
       final dict is ``{root_base} + scenario + rover:{robot_base +
       scenario.rover}``.

    Args:
        scenario_path: Path to the scenario YAML.  Relative paths are
            resolved against the current working directory first, then
            against repo root.

    Returns:
        Fully merged config dict.  Both ``base_config`` keys (root-level
        and ``rover.base_config``) are stripped from the result.

    Raises:
        ValueError: If ``scenario_path`` contains internal whitespace
            that does not correspond to a real file on disk.  This
            usually means the CLI value got pasted with a trailing
            token (``2>&1`` is a shell redirection, not an argparse
            argument).
        FileNotFoundError: If ``scenario_path`` or either referenced
            ``base_config`` file is missing.
    """
    scenario_path = str(scenario_path).strip()
    resolved = scenario_path
    if not os.path.isabs(resolved):
        resolved = os.path.abspath(resolved)
        if not os.path.isfile(resolved):
            resolved = os.path.abspath(os.path.join(REPO_ROOT, scenario_path))
    if any(ch.isspace() for ch in scenario_path) and not os.path.isfile(resolved):
        raise ValueError(
            f"Scenario path contains embedded whitespace: {scenario_path!r}. "
            "Did you paste a shell redirection like `2>&1` into --config? "
            "Redirections belong after the command, outside argparse."
        )
    scenario_cfg = read_yaml(resolved)
    scenario_dir = os.path.dirname(resolved)

    # Fold a root-level ``base_config`` into the scenario dict before
    # anything else. Pointed at ``configs/scenarios/_base.yaml`` so the
    # shared mars_env/rendering boilerplate does not repeat across
    # scenario files.  Scenario overrides win over the base; non-dict
    # collisions replace outright (see ``deep_merge``).
    if "base_config" in scenario_cfg:
        root_base_ref = scenario_cfg.pop("base_config")
        root_base_full = _resolve_path(str(root_base_ref), scenario_dir)
        if not os.path.isfile(root_base_full):
            raise FileNotFoundError(
                f"Root base_config referenced by {resolved} not found: {root_base_full}"
            )
        scenario_cfg = deep_merge(read_yaml(root_base_full), scenario_cfg)

    rover_override = scenario_cfg.get("rover")
    if not isinstance(rover_override, dict):
        # No rover block -- scenario-only (terrain / structure only).
        return scenario_cfg

    base_path = rover_override.get("base_config")
    if base_path is None:
        # Scenario declares rover inline without referencing a base.
        merged = copy.deepcopy(scenario_cfg)
        merged["rover"] = copy.deepcopy(rover_override)
        return merged

    base_full = _resolve_path(str(base_path), scenario_dir)
    base_cfg = read_yaml(base_full)

    merged_rover_inputs = copy.deepcopy(rover_override)
    merged_rover_inputs.pop("base_config", None)

    merged_rover = deep_merge(base_cfg, merged_rover_inputs)

    merged_cfg = copy.deepcopy(scenario_cfg)
    merged_cfg["rover"] = merged_rover
    # Legacy alias normalisation: sensors.lidar (single entry) → lidar_3d.
    sensors = merged_rover.get("sensors")
    if isinstance(sensors, dict) and "lidar" in sensors and "lidar_3d" not in sensors:
        sensors["lidar_3d"] = sensors.pop("lidar")
    return merged_cfg
