"""Unit tests for marslab.scene.structure_loader + scene schema (offline, P3)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from marslab.config.schema import MarsLabConfig, SceneConfig, StructureConfigSchema
from marslab.scene.structure_loader import StructureConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "configs" / "scenarios"


# --- StructureConfig dataclass ------------------------------------------------


def test_structure_config_defaults():
    """Dataclass defaults match the public contract in structure_loader."""
    cfg = StructureConfig(name="lander", asset_path="foo.usd", spawn_xyz=(1.0, 2.0, 3.0))
    assert cfg.spawn_rpy_deg == (0.0, 0.0, 0.0)
    assert cfg.scale == (1.0, 1.0, 1.0)
    assert cfg.static is True
    assert cfg.collision is True
    assert cfg.prim_path == ""


def test_structure_config_default_prim_path():
    """Empty prim_path derives ``/World/Structures/{name}``."""
    cfg = StructureConfig(name="habitat", asset_path="x.usd", spawn_xyz=(0, 0, 0))
    assert cfg.resolved_prim_path() == "/World/Structures/habitat"


def test_structure_config_explicit_prim_path():
    """Non-empty prim_path is passed through verbatim."""
    cfg = StructureConfig(
        name="habitat",
        asset_path="x.usd",
        spawn_xyz=(0, 0, 0),
        prim_path="/Custom/Base/Hab",
    )
    assert cfg.resolved_prim_path() == "/Custom/Base/Hab"


# --- StructureConfigSchema (pydantic mirror) ---------------------------------


def test_schema_requires_core_fields():
    """name / asset_path / spawn_xyz are required."""
    with pytest.raises(ValidationError):
        StructureConfigSchema()
    with pytest.raises(ValidationError):
        StructureConfigSchema(name="x", asset_path="y.usd")  # missing spawn_xyz


def test_schema_defaults_match_dataclass():
    """Pydantic defaults mirror the dataclass defaults byte-for-byte."""
    s = StructureConfigSchema(name="x", asset_path="y.usd", spawn_xyz=[0, 0, 0])
    assert s.spawn_rpy_deg == [0.0, 0.0, 0.0]
    assert s.scale == [1.0, 1.0, 1.0]
    assert s.static is True
    assert s.collision is True
    assert s.prim_path == ""


def test_schema_to_dataclass_parity():
    """Round-tripping through to_dataclass yields identical field values."""
    s = StructureConfigSchema(
        name="lander",
        asset_path="assets/structures/spacecraft/insight_lander.usd",
        spawn_xyz=[1.5, 2.5, 0.0],
        spawn_rpy_deg=[10.0, 20.0, 30.0],
        scale=[1.2, 1.2, 0.3],
        static=False,
        collision=True,
        prim_path="/Custom/Lander",
    )
    dc = s.to_dataclass()
    assert isinstance(dc, StructureConfig)
    assert dc.name == "lander"
    assert dc.asset_path.endswith("insight_lander.usd")
    assert dc.spawn_xyz == (1.5, 2.5, 0.0)
    assert dc.spawn_rpy_deg == (10.0, 20.0, 30.0)
    assert dc.scale == (1.2, 1.2, 0.3)
    assert dc.static is False
    assert dc.collision is True
    assert dc.prim_path == "/Custom/Lander"


def test_schema_rejects_invalid_name_whitespace():
    with pytest.raises(ValidationError):
        StructureConfigSchema(name="bad name", asset_path="x.usd", spawn_xyz=[0, 0, 0])


def test_schema_rejects_invalid_name_slash():
    with pytest.raises(ValidationError):
        StructureConfigSchema(name="bad/name", asset_path="x.usd", spawn_xyz=[0, 0, 0])


def test_schema_rejects_name_leading_digit():
    with pytest.raises(ValidationError):
        StructureConfigSchema(name="1lander", asset_path="x.usd", spawn_xyz=[0, 0, 0])


def test_schema_rejects_wrong_xyz_length():
    with pytest.raises(ValidationError):
        StructureConfigSchema(name="x", asset_path="y.usd", spawn_xyz=[1.0, 2.0])


# --- SceneConfig defaults + wiring into MarsLabConfig ------------------------


def test_scene_config_empty_default():
    """SceneConfig() has an empty structures list."""
    sc = SceneConfig()
    assert sc.structures == []


def test_marslab_config_has_scene_default():
    """MarsLabConfig.scene defaults to SceneConfig()."""
    # TerrainConfig requires source-dependent fields; use procedural preset
    # to get a valid default without a DEM file on disk.
    from marslab.config.schema.terrain import TerrainConfig

    mlc = MarsLabConfig(terrain=TerrainConfig(source="procedural", procedural_preset="flat"))
    assert isinstance(mlc.scene, SceneConfig)
    assert mlc.scene.structures == []


def test_marslab_config_scene_block_parses():
    """A scene block in the top-level dict validates through MarsLabConfig."""
    from marslab.config.schema.terrain import TerrainConfig

    mlc = MarsLabConfig(
        terrain=TerrainConfig(source="procedural", procedural_preset="flat"),
        scene={
            "structures": [
                {
                    "name": "habitat",
                    "asset_path": "assets/structures/base/habitat_module.usd",
                    "spawn_xyz": [0.0, 0.0, 0.0],
                }
            ]
        },
    )
    assert len(mlc.scene.structures) == 1
    assert mlc.scene.structures[0].name == "habitat"


# --- YAML roundtrip for the two new scenarios -------------------------------


@pytest.mark.parametrize(
    "scenario_file,expected_structure_count,rover_xy",
    [
        ("spacecraft_landing.yaml", 5, [10.0, 0.0]),
        ("mars_base.yaml", 6, [40.0, 0.0]),
    ],
)
def test_scenario_yaml_roundtrip(scenario_file, expected_structure_count, rover_xy):
    """Each scenario YAML parses, has the expected structure count, and
    the rover spawns at the documented XY.
    """
    path = SCENARIO_DIR / scenario_file
    assert path.is_file(), f"missing scenario YAML: {path}"

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    assert "scene" in data, f"{scenario_file} must declare a scene block"
    assert "structures" in data["scene"]
    assert len(data["scene"]["structures"]) == expected_structure_count

    # Validate every structure through the pydantic mirror (catches
    # invalid names / missing required fields at import time).
    for raw in data["scene"]["structures"]:
        s = StructureConfigSchema(**raw)
        assert s.asset_path.startswith("assets/structures/")
        assert s.to_dataclass().resolved_prim_path().startswith("/World/Structures/")

    # Rover spawn XY sanity check — aligns with the plan (10 m / 40 m).
    assert data["rover"]["spawn"]["xy"] == rover_xy


def test_scenario_yaml_names_unique_within_scene():
    """Structure names must be unique within a scenario so the default
    prim paths do not collide.
    """
    for scenario_file in ("spacecraft_landing.yaml", "mars_base.yaml"):
        path = SCENARIO_DIR / scenario_file
        with open(path, "r") as f:
            data = yaml.safe_load(f)
        names = [s["name"] for s in data["scene"]["structures"]]
        assert len(names) == len(set(names)), (
            f"duplicate structure names in {scenario_file}: "
            f"{[n for n in names if names.count(n) > 1]}"
        )


# --- Asset-licenses / scaffolding present ------------------------------------


def test_structure_asset_dirs_exist():
    """The placeholder asset directories ship as empty (.gitkeep) so
    that agents downstream can drop USD files in without re-creating
    the folder tree.
    """
    assert (REPO_ROOT / "assets" / "structures" / "spacecraft").is_dir()
    assert (REPO_ROOT / "assets" / "structures" / "base").is_dir()
    assert (REPO_ROOT / "assets" / "structures" / "LICENSES.md").is_file()


# --- Offline-safety smoke ----------------------------------------------------


def test_structure_loader_import_is_offline():
    """Importing the loader module does not drag in Isaac Sim or pxr.

    Regression guard for P3: any future refactor that moves a
    ``from pxr import ...`` to module scope would break offline unit
    tests on CI runners without a GPU.
    """
    import importlib
    import sys

    # Remove any cached entry then re-import -- the test must fail the
    # assertion if the module grew a top-level pxr import.
    mod_name = "marslab.scene.structure_loader"
    if mod_name in sys.modules:
        importlib.reload(sys.modules[mod_name])
    assert "pxr" not in sys.modules or os.environ.get("ISAAC_SIM_RUNNING") == "1"
    assert "omni" not in sys.modules or os.environ.get("ISAAC_SIM_RUNNING") == "1"
