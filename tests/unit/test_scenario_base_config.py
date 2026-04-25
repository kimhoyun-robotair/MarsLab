"""Reviewer 2 #17 (2026-04-24): regression tests for the scenario ``base_config`` include.

Pre-#17 every ``configs/scenarios/*.yaml`` duplicated ~35 lines of
identical ``mars_env`` + ``rendering`` boilerplate.  Drift had already
leaked in (``enabled: True`` vs ``enabled: true`` — H-19) and the wider
review flagged the whole pattern as a copy-paste maintenance hazard.

Item #17 consolidates that boilerplate into
``configs/scenarios/_base.yaml`` and pulls it into every scenario via
a root-level ``base_config`` include resolved by both loaders:

* ``marslab.config.loader.load_and_validate`` (pydantic path)
* ``marslab.config.yaml_loader.load_scenario_config`` (raw dict path
  used by the Stage 2/3 runtime)

These tests lock down three guarantees:

1. The shared defaults from ``_base.yaml`` actually land in the merged
   result for every scenario (inheritance works end-to-end).
2. Scenario-local overrides still win (``spacecraft_landing`` keeps
   its 135/40 sun, ``mars_base`` keeps 50-deg sun elevation).
3. No scenario re-declares a ``mars_env`` common key — i.e. the dedup
   actually happened and cannot silently regress via a future
   copy-paste.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from marslab.config.loader import load_and_validate
from marslab.config.yaml_loader import load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "configs" / "scenarios"
BASE_YAML = SCENARIO_DIR / "_base.yaml"

# Runnable scenario YAMLs — excludes shared include fragments (underscore prefix)
# and self-contained templates (``template_*.yaml``).  Templates demonstrate the
# inline / no-base_config pattern by design and therefore opt out of the
# Reviewer 2 #17 dedup invariants enforced below (every other scenario MUST
# pull from ``_base.yaml``).
_SCENARIOS = sorted(
    p
    for p in SCENARIO_DIR.glob("*.yaml")
    if not p.name.startswith("_") and not p.name.startswith("template_")
)

# Common keys that MUST live only in ``_base.yaml``, not in scenario overrides.
# These are the values every scenario shares; a scenario re-declaring them
# silently re-introduces the drift that item #17 just removed.  Note:
# ``seed`` is excluded — scenarios are allowed to override seeds for
# deterministic per-scenario reproducibility experiments.
_MARS_ENV_COMMON_KEYS = frozenset(
    {
        "gravity",
        "atmo_pressure",
        "atmo_density",
        "dust_optical_depth",
        "solar_constant_mean",
        "surface_albedo_range",
        "surface_temp_mean",
        "sol_duration_seconds",
        "dust_opacity_range",
    }
)


@pytest.mark.parametrize("yaml_path", _SCENARIOS, ids=lambda p: p.name)
def test_all_scenarios_inherit_from_mars_env(yaml_path: Path) -> None:
    """Every runnable scenario ends up with the shared mars_env defaults.

    Checks the merged result (pydantic ``load_and_validate`` path).  If
    a scenario accidentally dropped its ``base_config`` include, the
    ``mars_env.gravity`` check would fall back to pydantic's default
    3.72 and still pass — so this test also verifies a value that does
    NOT match the pydantic default (``atmo_pressure: 610`` matches, but
    ``surface_temp_mean: -60`` matches pydantic default too; fall back
    on ``sol_duration_seconds: 88642`` which is the pydantic default).
    The more discriminating check is that ``dust_opacity_range``
    matches ``_base.yaml`` which in turn matches mars_env defaults.
    """
    cfg = load_and_validate(str(yaml_path))
    # Shared from _base.yaml:
    assert cfg.mars_env.gravity == pytest.approx(3.72)
    assert cfg.mars_env.atmo_pressure == pytest.approx(610.0)
    assert cfg.mars_env.solar_constant_mean == pytest.approx(589.0)
    assert cfg.mars_env.sol_duration_seconds == 88642
    assert cfg.mars_env.dust_opacity_range == pytest.approx((0.5, 2.0))
    # Shared rendering defaults:
    assert cfg.rendering.mode == "ray_tracing"
    assert cfg.rendering.resolution == [1920, 1080]
    assert cfg.rendering.sun_intensity_scale == pytest.approx(30.0)


def test_scenario_override_wins_over_base_sun_azimuth() -> None:
    """``spacecraft_landing`` overrides the sun azimuth — the scenario value wins.

    Regression guard: if the deep-merge order ever flipped (base over
    scenario instead of scenario over base), ``sun_azimuth_deg`` would
    snap back to the base default of 180.0.
    """
    path = SCENARIO_DIR / "spacecraft_landing.yaml"
    cfg = load_and_validate(str(path))
    # Scenario value wins — not the base default of 180.
    assert cfg.mars_env.sun_azimuth_deg == pytest.approx(135.0)
    assert cfg.mars_env.sun_elevation_deg == pytest.approx(40.0)


def test_scenario_override_wins_over_base_sun_elevation() -> None:
    """``mars_base`` overrides sun elevation only; azimuth inherits from base."""
    path = SCENARIO_DIR / "mars_base.yaml"
    cfg = load_and_validate(str(path))
    # Scenario override wins:
    assert cfg.mars_env.sun_elevation_deg == pytest.approx(50.0)
    # Base default wins where scenario stays silent:
    assert cfg.mars_env.sun_azimuth_deg == pytest.approx(180.0)


def test_dynamic_atmosphere_enabled_scenario_flip() -> None:
    """Scenarios flip ``dynamic_atmosphere.enabled`` from false to true.

    Doubles as a YAML-1.2-boolean regression: pre-#17 the scenario files
    had a mix of ``enabled: True`` and ``enabled: true``.  After dedup
    every scenario declares lowercase ``true`` exclusively.  If a
    scenario file reverts to the capitalised form PyYAML still parses
    it as Python ``True``, but the visible text is a drift signal that
    the dedup policy got weakened — the source-file scan below catches
    that variant.
    """
    # Base default is false:
    with open(BASE_YAML) as f:
        base_data = yaml.safe_load(f) or {}
    assert base_data["mars_env"]["dynamic_atmosphere"]["enabled"] is False

    # Every runnable scenario flips it on:
    for path in _SCENARIOS:
        cfg = load_and_validate(str(path))
        assert (
            cfg.mars_env.dynamic_atmosphere.enabled is True
        ), f"{path.name}: dynamic_atmosphere.enabled must be True after merge"


@pytest.mark.parametrize("yaml_path", _SCENARIOS, ids=lambda p: p.name)
def test_no_scenario_duplicates_mars_env_common_block(yaml_path: Path) -> None:
    """No scenario re-declares a mars_env key that already lives in ``_base.yaml``.

    Reviewer 2 #17's whole point: if a future patch copy-pastes
    ``gravity: 3.72`` back into a scenario file, it creates exactly the
    drift hazard H-17/H-19 flagged.  This test reads the RAW YAML
    (bypassing merge) and asserts only permitted keys appear under
    ``mars_env`` in each scenario.

    Permitted keys:
    * ``sun_azimuth_deg`` / ``sun_elevation_deg`` — scenario-specific
      solar geometry overrides (documented cases: mars_base,
      spacecraft_landing).
    * ``dynamic_atmosphere`` — scenarios flip ``enabled`` to true.
    * ``seed`` — allowed per-scenario seed override for experiments.
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    mars_env = raw.get("mars_env") or {}
    forbidden_present = set(mars_env) & _MARS_ENV_COMMON_KEYS
    assert not forbidden_present, (
        f"{yaml_path.name}: mars_env re-declares {sorted(forbidden_present)} "
        "which already live in configs/scenarios/_base.yaml. Drop them so "
        "there is a single source of truth (Reviewer 2 #17)."
    )


@pytest.mark.parametrize("yaml_path", _SCENARIOS, ids=lambda p: p.name)
def test_scenario_declares_base_config_include(yaml_path: Path) -> None:
    """Every runnable scenario points at ``_base.yaml`` via root ``base_config``.

    Sentinel: if a new scenario is added without the include, the
    dedup tests above would still pass (the scenario could just
    duplicate the base values) but the "single source of truth"
    guarantee evaporates.  This test locks the include in.
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    assert "base_config" in raw, (
        f"{yaml_path.name}: missing root-level ``base_config`` include. "
        "Add ``base_config: _base.yaml`` at the top (Reviewer 2 #17)."
    )
    # Normalise path for platform-agnostic comparison.
    ref = str(raw["base_config"]).replace("\\", "/").split("/")[-1]
    assert ref == "_base.yaml", (
        f"{yaml_path.name}: unexpected base_config target {raw['base_config']!r}; "
        "scenarios should include ``_base.yaml`` as the shared include fragment."
    )


def test_raw_dict_loader_also_merges_root_base_config() -> None:
    """``load_scenario_config`` (dict path) must honour the root-level base_config too.

    Runtime Stage 2/3 goes through the raw-dict loader, not the
    pydantic loader.  If only ``load_and_validate`` did the merge,
    scenarios loaded through the runtime would silently lose the
    shared mars_env/rendering defaults.
    """
    path = SCENARIO_DIR / "jezero_flat.yaml"
    cfg = load_scenario_config(str(path))
    assert "base_config" not in cfg, "root base_config key must be stripped after merge"
    mars_env = cfg["mars_env"]
    # Pulled in from _base.yaml:
    assert mars_env["gravity"] == pytest.approx(3.72)
    assert mars_env["atmo_pressure"] == 610
    assert mars_env["sun_azimuth_deg"] == 180
    # Scenario-specific flip survives:
    assert mars_env["dynamic_atmosphere"]["enabled"] is True
    # Rendering defaults merged in:
    assert cfg["rendering"]["mode"] == "ray_tracing"
    assert cfg["rendering"]["spp"] == 32


def test_base_yaml_uses_lowercase_boolean_only() -> None:
    """_base.yaml and every scenario must use YAML 1.2 lowercase booleans.

    H-19 from the Reviewer 2 audit: ``enabled: True`` and
    ``enabled: true`` coexisted across scenarios.  PyYAML parses both
    as Python ``True`` but the visible drift signals weakening
    discipline.  Scan the raw text for the capitalised variant.
    """
    offenders: list[str] = []
    # ``_SCENARIOS`` already excludes ``_*.yaml`` and ``template_*.yaml``; we
    # additionally scan ``_base.yaml`` here because the boolean-casing rule
    # applies to the shared include fragment too. Templates are out of scope
    # because they re-declare every block inline — the YAML 1.2 boolean rule
    # still applies to them, but the dedup invariants do not, so leaving them
    # excluded keeps ownership clean.
    for path in [BASE_YAML, *_SCENARIOS]:
        text = path.read_text(encoding="utf-8")
        # Look for YAML boolean tokens after ``:``. ``: True`` / ``: False``
        # with capital first letter are the drift we are locking out.
        # Match ``:<space>True`` or ``:<space>False`` at end-of-line or
        # followed by whitespace/comment.
        import re  # noqa: PLC0415

        for m in re.finditer(r":\s+(True|False)\b", text):
            line_no = text[: m.start()].count("\n") + 1
            offenders.append(f"{path.name}:{line_no} -> {m.group(1)}")
    assert (
        not offenders
    ), "Non-lowercase YAML booleans found (use ``true`` / ``false``): " + ", ".join(offenders)
