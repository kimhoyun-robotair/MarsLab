"""Backward-compat shim for the R2 split (2026-04-22).

Re-exports ``load_scenario_config``, ``resolve_spawn_pose``, ``deep_merge``
from the post-split sibling modules so existing imports in scripts/tests
keep working. New code should import from ``marslab.config.yaml_loader``
and ``marslab.config.spawn_resolver`` directly.
"""

from marslab.config.spawn_resolver import resolve_spawn_pose
from marslab.config.yaml_loader import deep_merge, load_scenario_config

__all__ = ["deep_merge", "load_scenario_config", "resolve_spawn_pose"]
