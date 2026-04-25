"""Reviewer 2 #12 (2026-04-24): regression tests for ``extra="forbid"``.

Pydantic v2 defaults to ``extra="ignore"`` on ``BaseModel``.  For a
YAML-first project like MarsLab that silent-drop semantics is a bug:
a typo in a scenario YAML (``gravty`` instead of ``gravity``, or a
whole unexpected block like ``canyon_depth`` at the terrain level)
survives ``pydantic.ValidationError`` and whatever Python literal
happens to be in the runtime fallback path ships to PhysX / OmniGraph
/ rendering.  Item #12 flips every schema model to ``extra="forbid"``.

This module locks that choice in with three test families:

1. ``test_<model>_rejects_unknown_field``: one per schema BaseModel,
   constructs with a clearly-bogus key and asserts a ValidationError.
   Any future schema refactor that drops ``extra="forbid"`` on a model
   immediately fails this suite.
2. ``test_procedural_canyon_config_*``: pins the new nested
   :class:`ProceduralCanyonConfig` surface -- field names, the legacy
   flat-key migrator on :class:`TerrainConfig`, and the
   ``procedural_preset='canyon'`` conditional requirement.
3. ``test_all_scenario_yamls_pass_validation`` and
   ``test_config_schema_has_forbid_everywhere`` -- full-repo regression
   gates.  The first loads every ``configs/scenarios/*.yaml`` through
   ``load_and_validate`` and asserts the result; the second greps the
   schema source files for the forbid opt-in and fails the moment
   someone adds a new BaseModel without it.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from marslab.config.loader import load_and_validate
from marslab.config.schema import (
    CaveConfig,
    CaveGeometryConfig,
    DemCropConfig,
    DynamicAtmosphereConfig,
    FogConfig,
    MarsEnvConfig,
    MarsLabConfig,
    OdometryCovarianceConfig,
    PathTracingConfig,
    ProceduralCanyonConfig,
    RayTracingConfig,
    RenderingConfig,
    RobotConfig,
    Ros2BridgeConfig,
    SceneConfig,
    SkidSteerDriveConfig,
    SkyDomeConfig,
    StructureConfigSchema,
    SunSweepConfig,
    TauConstantConfig,
    TauRampConfig,
    TauSineConfig,
    TerrainConfig,
)
from marslab.config.schema.robot import OdomPublisherConfig
from marslab.config.schema.ros2_bridge import QoSProfileConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "marslab" / "config" / "schema"

# Full set of BaseModel subclasses exported by marslab.config.schema.
# Every one of these MUST declare ``model_config = ConfigDict(extra="forbid")``.
# Models that need additional required fields are constructed with a
# minimal valid payload + one ``__bogus__`` key; pydantic catches the
# bogus key via ``extra="forbid"`` before required-field validation
# runs, so the payload only needs to be structurally valid.
ALL_SCHEMA_MODELS = [
    MarsEnvConfig,
    SunSweepConfig,
    TauConstantConfig,
    TauRampConfig,
    TauSineConfig,
    DynamicAtmosphereConfig,
    FogConfig,
    RayTracingConfig,
    PathTracingConfig,
    SkyDomeConfig,
    RenderingConfig,
    OdometryCovarianceConfig,
    OdomPublisherConfig,
    QoSProfileConfig,
    Ros2BridgeConfig,
    DemCropConfig,
    CaveGeometryConfig,
    CaveConfig,
    ProceduralCanyonConfig,
    TerrainConfig,
    StructureConfigSchema,
    SceneConfig,
    RobotConfig,
    MarsLabConfig,
]

# Minimal valid payload for models that have required fields. Models
# without required fields get ``{}`` (no required payload needed).
_BASE_PAYLOADS: dict[type, dict] = {
    DemCropConfig: {"row": 0, "col": 0, "height": 1, "width": 1},
    SkidSteerDriveConfig: {
        "drive_damping": 1000.0,
        "steer_stiffness": 50000.0,
        "steer_damping": 5000.0,
        "drive_max_force": 1000000.0,
        "steer_max_force": 100000.0,
        "suspension_damping": 50.0,
        "drive_type": "acceleration",
    },
    RobotConfig: {"type": "rover", "urdf_path": "x.urdf"},
    ProceduralCanyonConfig: {
        "canyon_depth": 40.0,
        "canyon_floor_width": 30.0,
        "canyon_total_width": 80.0,
    },
    StructureConfigSchema: {
        "name": "x",
        "asset_path": "x.usd",
        "spawn_xyz": [0.0, 0.0, 0.0],
    },
    # MarsLabConfig's default TerrainConfig uses source='hirise' which
    # requires dem_path or converted_dem_dir.  Supply a procedural
    # terrain to avoid that unrelated error so the bogus-key assertion
    # is the failure under test.
    MarsLabConfig: {
        "terrain": {"source": "procedural", "procedural_preset": "flat"},
    },
}


@pytest.mark.parametrize("model_cls", ALL_SCHEMA_MODELS, ids=lambda m: m.__name__)
def test_schema_model_rejects_unknown_field(model_cls: type) -> None:
    """Every exported schema BaseModel rejects a bogus key via ``extra='forbid'``.

    Reviewer 2 #12 (2026-04-24).  The bogus key is deliberately named
    ``__reviewer2_forbid_probe__`` so it cannot collide with any future
    legitimate field.  The test does NOT care whether the base payload
    is semantically valid -- pydantic runs the extra-key check before
    required-field validation, so as long as ``extra='forbid'`` is on
    the bogus key triggers the expected ValidationError.
    """
    payload = dict(_BASE_PAYLOADS.get(model_cls, {}))
    payload["__reviewer2_forbid_probe__"] = 42
    with pytest.raises(ValidationError) as excinfo:
        model_cls(**payload)
    # Pydantic v2 labels forbid violations as ``extra_forbidden``.  Pin
    # the error type so a future downgrade to ``extra='allow'`` that
    # still raises (on a different rule) does not quietly pass this.
    assert "extra_forbidden" in str(excinfo.value) or "Extra inputs" in str(excinfo.value)


# ------------------------------------------------------------------ SkidSteer
# The SkidSteerDriveConfig required-field set is large (seven PhysX
# tunables from R2-A3 / R2-4a) so it needs its own tailored test --
# constructing it with ``__bogus__`` alone would miss those required
# fields and the bogus-key assertion would fire inside a chain of
# other validation errors, hiding intent.


def test_skid_steer_drive_config_rejects_unknown_field() -> None:
    """SkidSteerDriveConfig: bogus key on an otherwise-valid payload fails."""
    payload = dict(_BASE_PAYLOADS[SkidSteerDriveConfig])
    payload["wheel_radious"] = 0.15  # sic: typo
    with pytest.raises(ValidationError) as excinfo:
        SkidSteerDriveConfig(**payload)
    assert "wheel_radious" in str(excinfo.value)


# ------------------------------------------------------------------ Canyon


def test_procedural_canyon_config_accepts_canyon_fields() -> None:
    """ProceduralCanyonConfig captures every ``canyon_*`` YAML key.

    The scenario YAML (``configs/scenarios/procedural_canyon.yaml``)
    declares exactly these seven keys -- the new model must accept all
    of them so ``extra='forbid'`` does not regress the scenario.
    """
    cfg = ProceduralCanyonConfig(
        canyon_depth=40.0,
        canyon_floor_width=30.0,
        canyon_total_width=80.0,
        canyon_curvature=0.3,
        canyon_craters=2,
        canyon_crater_radius_range=(5.0, 15.0),
        canyon_crater_depth_range=(2.0, 6.0),
    )
    assert cfg.canyon_depth == 40.0
    assert cfg.canyon_floor_width == 30.0
    assert cfg.canyon_total_width == 80.0
    assert cfg.canyon_crater_radius_range == (5.0, 15.0)


def test_procedural_canyon_config_total_must_exceed_floor() -> None:
    """``canyon_total_width`` must exceed ``canyon_floor_width``.

    Regression: earlier YAML could have author-inverted these two
    widths and nothing caught it.
    """
    with pytest.raises(ValidationError):
        ProceduralCanyonConfig(
            canyon_depth=40.0,
            canyon_floor_width=80.0,
            canyon_total_width=30.0,  # inverted
        )


def test_terrain_config_migrates_legacy_flat_canyon_keys() -> None:
    """Legacy flat ``canyon_*`` keys are folded into ``terrain.canyon``.

    The pre-validator on ``TerrainConfig`` mirrors the RenderingConfig
    R2-A1 flat→nested migration: keeps pre-item-#12 scenario YAMLs
    loading without edits.
    """
    t = TerrainConfig(
        source="procedural",
        procedural_preset="canyon",
        canyon_depth=40.0,
        canyon_floor_width=30.0,
        canyon_total_width=80.0,
        canyon_curvature=0.3,
    )
    assert t.canyon is not None
    assert t.canyon.canyon_depth == 40.0
    assert t.canyon.canyon_curvature == 0.3


def test_terrain_config_canyon_preset_requires_canyon_block() -> None:
    """``procedural_preset='canyon'`` without a canyon block raises."""
    with pytest.raises(ValidationError):
        TerrainConfig(source="procedural", procedural_preset="canyon")


def test_terrain_config_explicit_canyon_dict_wins_over_flat() -> None:
    """When both flat keys and the nested dict are present, the nested dict wins."""
    t = TerrainConfig(
        source="procedural",
        procedural_preset="canyon",
        canyon={
            "canyon_depth": 50.0,
            "canyon_floor_width": 20.0,
            "canyon_total_width": 60.0,
        },
        canyon_depth=999.0,  # ignored -- nested block wins
        canyon_floor_width=999.0,
        canyon_total_width=999.0,
    )
    assert t.canyon is not None
    assert t.canyon.canyon_depth == 50.0


# ------------------------------------------------------------------ MarsLabConfig


def test_marslab_config_accepts_rover_opaque_block() -> None:
    """Scenario YAMLs put rover tuning under ``rover:`` (opaque dict).

    Reviewer 2 #12 accepts ``rover`` as a typed ``dict[str, Any] | None``
    rather than a strict schema -- promoting it is tracked under item
    #17.  Verify the dict survives construction without losing keys.
    """
    c = MarsLabConfig(
        terrain=TerrainConfig(source="procedural", procedural_preset="flat"),
        rover={"base_config": "configs/robots/rover_m2020.yaml", "enabled": True},
    )
    assert c.rover is not None
    assert c.rover["enabled"] is True
    assert c.rover["base_config"].endswith("rover_m2020.yaml")


def test_marslab_config_strips_top_level_base_config_key() -> None:
    """A stray ``base_config:`` at MarsLabConfig root does NOT fail forbid.

    The key is expected to be popped by the top-level loader, but some
    direct-construction call sites (test fixtures, visualizers) forget.
    The ``_strip_base_config_key`` pre-validator absorbs that case so
    forbid stays tight without punishing the legacy path.
    """
    c = MarsLabConfig(
        base_config="configs/robots/rover_m2020.yaml",
        terrain=TerrainConfig(source="procedural", procedural_preset="flat"),
    )
    assert c.terrain.procedural_preset == "flat"


def test_marslab_config_rejects_unknown_root_key() -> None:
    """A genuinely bogus root key still raises ValidationError.

    Ensures the base_config escape hatch above does not accidentally
    open the door for every other typo at the root.
    """
    with pytest.raises(ValidationError):
        MarsLabConfig(mars_envs={})  # plural typo


# ------------------------------------------------------------------ Scenario YAMLs


_SCENARIO_DIR = REPO_ROOT / "configs" / "scenarios"
# Reviewer 2 #17 (2026-04-24): YAMLs prefixed with ``_`` (e.g. ``_base.yaml``)
# are shared include fragments, not complete scenarios — they declare only
# the common ``mars_env`` + ``rendering`` blocks and are pulled in by every
# real scenario via the root-level ``base_config`` mechanism. Exclude them
# from the full-validation sweep so the sweep stays focused on "does every
# runnable scenario round-trip through pydantic cleanly?".
# 2026-04-25: template_*.yaml are self-contained UX templates (Items 1+2);
# they validate via load_and_validate but live outside the ship-with set.
# Their dedicated tests live in ``tests/unit/test_scenario_templates.py``.
_SCENARIO_YAMLS = sorted(
    p
    for p in _SCENARIO_DIR.glob("*.yaml")
    if not p.name.startswith("_") and not p.name.startswith("template_")
)


@pytest.mark.parametrize("yaml_path", _SCENARIO_YAMLS, ids=lambda p: p.name)
def test_all_scenario_yamls_pass_validation(yaml_path: Path) -> None:
    """Every ``configs/scenarios/*.yaml`` loads through ``load_and_validate``.

    Reviewer 2 #12 (2026-04-24).  If a new scenario adds a typo or a
    legitimately new field not yet in the schema, this test fails
    immediately rather than silently shipping the drop.
    """
    config = load_and_validate(str(yaml_path))
    assert isinstance(config, MarsLabConfig)
    assert config.mars_env.gravity == pytest.approx(3.72)


def test_procedural_canyon_yaml_populates_canyon_block() -> None:
    """Specifically: procedural_canyon.yaml promotes its flat keys.

    This is the reveal case that motivated item #12.  Before forbid
    was on, the seven ``canyon_*`` keys were silently dropped and the
    resulting ``TerrainConfig`` had ``canyon is None`` -- the only
    reason the scenario rendered was the runtime read the raw YAML
    dict, bypassing pydantic.
    """
    path = _SCENARIO_DIR / "procedural_canyon.yaml"
    config = load_and_validate(str(path))
    assert config.terrain.procedural_preset == "canyon"
    assert config.terrain.canyon is not None
    assert config.terrain.canyon.canyon_depth == pytest.approx(40.0)
    assert config.terrain.canyon.canyon_floor_width == pytest.approx(30.0)
    assert config.terrain.canyon.canyon_total_width == pytest.approx(80.0)


# ------------------------------------------------------------------ Source grep


def _schema_files() -> list[Path]:
    """Return every ``.py`` file in ``marslab/config/schema/`` except ``__init__``."""
    return sorted(p for p in SCHEMA_DIR.glob("*.py") if p.name != "__init__.py")


def _models_defined_in(source: str) -> list[str]:
    """Return names of ``class X(BaseModel):`` declarations in ``source``.

    Uses ``ast`` rather than grep so subclass hierarchies like
    ``class X(ParentModel):`` where ``ParentModel`` is itself a
    BaseModel subclass are caught.  For MarsLab the schema modules
    subclass ``BaseModel`` directly so a name-based check suffices,
    but the ast walk is more future-proof.
    """
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        # Only count direct BaseModel subclasses -- helpers that
        # subclass something else (NamedTuple, Enum) would show up
        # otherwise.  MarsLab's schema modules only use BaseModel,
        # so the bare-name match is sufficient.
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "BaseModel":
                names.append(node.name)
                break
    return names


def _has_extra_forbid(source: str, class_name: str) -> bool:
    """Return True iff the class body contains ``ConfigDict(extra="forbid")``.

    Uses ``ast`` to avoid false positives from docstrings or comments.
    Walks the class body looking for an assignment target named
    ``model_config`` whose RHS is ``ConfigDict(extra="forbid")``.
    """
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if "model_config" not in targets:
                continue
            call = stmt.value
            if not isinstance(call, ast.Call):
                continue
            func = call.func
            if not (isinstance(func, ast.Name) and func.id == "ConfigDict"):
                continue
            for kw in call.keywords:
                if kw.arg == "extra":
                    val = kw.value
                    if isinstance(val, ast.Constant) and val.value == "forbid":
                        return True
        return False
    return False


def test_config_schema_has_forbid_everywhere() -> None:
    """Every ``class X(BaseModel):`` under ``marslab/config/schema`` pins forbid.

    Reviewer 2 #12 (2026-04-24).  A future refactor that introduces a
    new BaseModel without ``ConfigDict(extra='forbid')`` fails this
    test immediately, preventing silent-drop regressions from
    reappearing as the schema grows.
    """
    missing: list[str] = []
    for path in _schema_files():
        source = path.read_text(encoding="utf-8")
        for model_name in _models_defined_in(source):
            if not _has_extra_forbid(source, model_name):
                missing.append(f"{path.name}::{model_name}")
    assert (
        not missing
    ), "Schema models missing ``model_config = ConfigDict(extra='forbid')``: " + ", ".join(missing)


def test_scenario_yaml_roundtrip_drops_no_keys_from_terrain() -> None:
    """Load every scenario through pydantic and re-dump; assert no terrain field vanished.

    Sentinel for the silent-drop class of bug that Reviewer 2 #12
    targets.  Terrain is the densest block (and the one where
    item #12 revealed the ``canyon_*`` drop), so it is the
    highest-signal subject.  The assertion is "every key that was in
    the scenario's ``terrain:`` block ends up in the pydantic model
    (either directly or via a known migrator)".  Legacy flat
    ``canyon_*`` keys map to ``terrain.canyon.canyon_*``; all other
    keys map to themselves.
    """
    for yaml_path in _SCENARIO_YAMLS:
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        raw_terrain = raw.get("terrain") or {}
        cfg = load_and_validate(str(yaml_path))
        for key in raw_terrain:
            # Legacy flat canyon keys migrate to terrain.canyon
            if key.startswith("canyon_") and key != "canyon":
                assert cfg.terrain.canyon is not None, f"{yaml_path.name}: canyon block absent"
                assert hasattr(
                    cfg.terrain.canyon, key
                ), f"{yaml_path.name}: terrain.{key} lost after migration"
            else:
                assert hasattr(
                    cfg.terrain, key
                ), f"{yaml_path.name}: terrain.{key} lost (silent drop?)"
