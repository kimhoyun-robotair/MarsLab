"""Backward-compat shim re-exporting the scenario-loader public surface.

Re-exports ``load_scenario_config``, ``resolve_spawn_pose``, ``deep_merge``
from the sibling modules so existing imports in scripts/tests keep
working.
"""

from marslab.config.spawn_resolver import resolve_spawn_pose
from marslab.config.yaml_loader import deep_merge, load_scenario_config

__all__ = ["deep_merge", "load_scenario_config", "resolve_spawn_pose"]
