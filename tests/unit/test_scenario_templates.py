"""Self-contained scenario template validation.

The ship-with scenarios in ``configs/scenarios/*.yaml`` use a 3-file
chain (scenario YAML + ``_base.yaml`` +
``configs/robots/rover_m2020.yaml``) that is correct for production
but cognitively heavy for a 3rd party who just wants to read one file
end-to-end.

The two self-contained templates and a DEM conversion config lock in
the following contract:

1. Both templates round-trip through ``load_and_validate`` without
   raising.
2. The procedural template uses ``rocky_plain`` (the SLAM/Nav
   benchmark default) -- if a future patch silently swaps the preset,
   this test flags it.
3. The HiRISE template references a converted DEM dir even though the
   directory itself may be empty at config-load time (the loader does
   not read DEM content during validation).
4. Neither template carries a ``base_config`` include (that is the
   whole point of "self-contained").
5. The DEM conversion config exposes the keys
   ``scripts/convert_dem.py`` actually reads (``terrain.source``,
   ``terrain.dem_path``, ``terrain.converted_dem_dir``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from marslab.config.loader import load_and_validate
from marslab.config.schema import MarsLabConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIO_DIR = REPO_ROOT / "configs" / "scenarios"
DEM_CONVERSION_DIR = REPO_ROOT / "configs" / "dem_conversion"

TEMPLATE_PROCEDURAL = SCENARIO_DIR / "template_single_file.yaml"
TEMPLATE_HIRISE = SCENARIO_DIR / "template_hirise.yaml"
DEM_CONVERSION_SAMPLE = DEM_CONVERSION_DIR / "sample_jezero.yaml"


def test_template_single_file_validates() -> None:
    """The procedural self-contained template loads through pydantic.

    Assert returned type, plus a handful of leaf values we explicitly
    authored, so a regression where pydantic
    silently fell back to a default would still trip this test.
    """
    cfg = load_and_validate(str(TEMPLATE_PROCEDURAL))
    assert isinstance(cfg, MarsLabConfig)
    # Authored values (NOT pydantic defaults — must come from the YAML):
    assert cfg.terrain.source == "procedural"
    assert cfg.terrain.procedural_preset == "rocky_plain"
    assert cfg.terrain.scenario_name == "template_single_file"
    # Shared mars_env values (the WHOLE point: not delegated to _base.yaml):
    assert cfg.mars_env.gravity == pytest.approx(3.72)
    assert cfg.mars_env.atmo_pressure == pytest.approx(610.0)
    assert cfg.mars_env.dynamic_atmosphere.enabled is True
    # Rover block survived as opaque dict (MarsLabConfig.rover: dict | None):
    assert cfg.rover is not None
    assert cfg.rover.get("enabled") is True
    # No base_config residue at validated-config level (loader pops it):
    # (cannot test on cfg directly; checked via raw YAML in dedicated test)


def test_template_hirise_validates_without_dem_files() -> None:
    """The HiRISE template validates structurally even with no DEM on disk.

    The loader chain (read_yaml -> deep_merge -> MarsLabConfig) only
    reads ``terrain.source`` / ``terrain.dem_crop`` / ``terrain.
    converted_dem_dir`` keys. The DEM ``elevation.npy`` content is read
    by the runtime, not the validator, so this test passes even if the
    asset directory is empty in a fresh checkout.
    """
    cfg = load_and_validate(str(TEMPLATE_HIRISE))
    assert isinstance(cfg, MarsLabConfig)
    assert cfg.terrain.source == "hirise"
    assert cfg.terrain.scenario_name == "template_hirise"
    # dem_crop authored values:
    assert cfg.terrain.dem_crop is not None
    assert cfg.terrain.dem_crop.row == 180
    assert cfg.terrain.dem_crop.col == 0
    assert cfg.terrain.dem_crop.height == 200
    assert cfg.terrain.dem_crop.width == 200
    # converted_dem_dir survived deep-merge:
    assert cfg.terrain.converted_dem_dir == "assets/mars_assets/DEM/jezero_crater"


@pytest.mark.parametrize(
    "yaml_path",
    [TEMPLATE_PROCEDURAL, TEMPLATE_HIRISE],
    ids=lambda p: p.name,
)
def test_template_yaml_has_no_base_config_include(yaml_path: Path) -> None:
    """Templates demonstrate the inline / self-contained pattern by not
    referencing ``_base.yaml`` or ``configs/robots/rover_m2020.yaml``.

    Regression guard: if a future patch silently re-introduces a
    ``base_config:`` include the whole UX point of these templates is
    lost — and they would also start tripping the
    ``test_no_scenario_duplicates_mars_env_common_block`` invariant
    that the ship-with scenarios are subject to.
    """
    with open(yaml_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    assert (
        "base_config" not in raw
    ), f"{yaml_path.name}: must NOT use root-level base_config (templates are self-contained)"
    rover = raw.get("rover") or {}
    assert (
        "base_config" not in rover
    ), f"{yaml_path.name}: rover.base_config must be absent (templates inline the rover block)"


def test_template_single_file_inlines_rover_sensors() -> None:
    """Self-contained means the camera + LiDAR + IMU blocks are inline.

    Validates the core 3rd-party UX claim: reading ONE file is enough
    to understand sensor wiring. If the template ever delegated this
    block back to ``configs/robots/rover_m2020.yaml`` via
    ``rover.base_config``, this assertion would break.
    """
    with open(TEMPLATE_PROCEDURAL, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    sensors = ((raw.get("rover") or {}).get("sensors")) or {}
    for required in ("camera", "lidar_3d", "lidar_2d", "imu"):
        assert required in sensors, f"template_single_file: rover.sensors.{required} missing"
    # Camera resolution authored inline (not delegated):
    assert sensors["camera"]["resolution"] == [640, 480]
    assert sensors["lidar_3d"]["profile_name"] == "Example_Rotary"


def test_dem_conversion_sample_validates_and_exposes_required_fields() -> None:
    """The DEM conversion config validates and carries every key
    ``scripts/convert_dem.py`` reads.

    Consumer (scripts/convert_dem.py:39, 46, 51-58):
        * ``config.terrain.source`` (must == "hirise")
        * ``config.terrain.dem_path``
        * ``config.terrain.converted_dem_dir`` (optional, falls back to
          a derived directory when None)
    """
    cfg = load_and_validate(str(DEM_CONVERSION_SAMPLE))
    assert isinstance(cfg, MarsLabConfig)
    assert cfg.terrain.source == "hirise"
    assert cfg.terrain.dem_path == "<your_local_download_path>/jezero_crater.tif"
    assert cfg.terrain.converted_dem_dir == "assets/mars_assets/DEM/jezero_crater"


def test_dem_conversion_and_hirise_template_share_converted_dir() -> None:
    """The 2-step workflow only works if the conversion output dir matches
    the scenario template's ``converted_dem_dir``.

    Without this invariant, running ``scripts/convert_dem.py`` produces
    files in directory A while ``template_hirise.yaml`` looks in
    directory B at runtime — silent data loss for the user.
    """
    conv_cfg = load_and_validate(str(DEM_CONVERSION_SAMPLE))
    scen_cfg = load_and_validate(str(TEMPLATE_HIRISE))
    assert conv_cfg.terrain.converted_dem_dir == scen_cfg.terrain.converted_dem_dir, (
        "DEM conversion output dir must match scenario template dir; "
        f"conversion={conv_cfg.terrain.converted_dem_dir!r} vs "
        f"scenario={scen_cfg.terrain.converted_dem_dir!r}"
    )
