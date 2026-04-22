"""Backward-compat shim for the R2 split (2026-04-22).

R2 split this 279-LOC module into two domain-focused siblings:

- ``marslab.config.yaml_loader`` — ``read_yaml``, ``deep_merge``,
  ``load_scenario_config``.
- ``marslab.config.spawn_resolver`` — ``resolve_spawn_pose``.

This file re-exports the public symbols so existing imports in
``scripts/phase1/run_stage3_monolithic.py`` (Oracle, L71-74),
``scripts/phase1/run_stage3.py``, and ``tests/unit/test_scenario_loader.py``
keep working without edits. New code should import directly from the
sibling modules.
"""

from marslab.config.spawn_resolver import resolve_spawn_pose
from marslab.config.yaml_loader import (
    REPO_ROOT,
    deep_merge,
    load_scenario_config,
)
from marslab.config.yaml_loader import (
    read_yaml as _read_yaml,
)

__all__ = [
    "REPO_ROOT",
    "_read_yaml",
    "deep_merge",
    "load_scenario_config",
    "resolve_spawn_pose",
]
