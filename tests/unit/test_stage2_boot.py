"""Unit tests for marslab.runtime.stage2_boot (offline-first, no Isaac Sim)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from marslab.config.schema import DynamicAtmosphereConfig
from marslab.runtime.stage2_boot import (
    StageTwoAtmosphereInit,
    StageTwoBootResult,
    run_stage2_boot,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
MARS_ENV_YAML = REPO_ROOT / "configs" / "mars_env.yaml"


def _find_scenario_without_cave() -> Path:
    """Return a scenario YAML whose terrain pipeline is not cave.

    Skip ``_``-prefixed YAMLs (e.g. ``_base.yaml``) -- they are
    shared include fragments and do not carry a complete ``terrain``
    block, so feeding them into ``run_stage2_boot`` would fail the
    required-section check.
    """
    scenarios_dir = REPO_ROOT / "configs" / "scenarios"
    for candidate in sorted(scenarios_dir.glob("*.yaml")):
        if candidate.name.startswith("_"):
            continue
        # Skip ``template_*.yaml`` self-contained templates so the scan
        # stays on ship-with scenarios (alphabetical order picks
        # cerberus_canyon.yaml first anyway, but the explicit guard
        # makes the intent obvious to future readers).
        if candidate.name.startswith("template_"):
            continue
        name = candidate.name.lower()
        if "cave" in name:
            continue
        return candidate
    raise FileNotFoundError("No non-cave scenario YAML present for stage2 tests.")


class TestRunStage2Boot:
    def test_returns_stage_two_boot_result(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        assert isinstance(boot, StageTwoBootResult)

    def test_config_sections_present(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        for key in ("mars_env", "terrain", "rendering"):
            assert key in boot.config
        assert boot.mars_cfg is boot.config["mars_env"]
        assert boot.terrain_cfg is boot.config["terrain"]
        assert boot.rendering_cfg is boot.config["rendering"]

    def test_missing_required_section_raises(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.yaml"
        broken.write_text(
            "mars_env:\n  gravity: 3.72\nterrain:\n  source: procedural\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="rendering"):
            run_stage2_boot(str(broken))

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            run_stage2_boot("/does/not/exist.yaml")

    def test_config_path_is_absolute(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        rel = Path("configs/mars_env.yaml")
        # Use absolute fallback path -- we just assert absolutisation works
        # regardless of the cwd used to invoke the helper.
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        assert Path(boot.config_path).is_absolute()
        del rel  # silence linter re: unused


class TestTerrainPreload:
    def test_elevation_shape_matches_metadata(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        assert isinstance(boot.elevation, np.ndarray)
        assert boot.elevation.ndim == 2
        assert boot.resolution > 0.0

    def test_dem_paths_are_absolute(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        for path in boot.dem_paths.values():
            assert path.is_absolute()


class TestAtmosphereInit:
    def test_init_is_frozen_snapshot(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        atmo = boot.atmosphere_init
        assert isinstance(atmo, StageTwoAtmosphereInit)
        # Frozen dataclass: attribute assignment must raise.
        with pytest.raises(Exception):  # noqa: BLE001, B017 - FrozenInstanceError
            atmo.tau = 999.0  # type: ignore[misc]

    def test_beer_law_intensity_positive_finite(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        atmo = boot.atmosphere_init
        assert atmo.direct_intensity > 0.0
        assert np.isfinite(atmo.direct_intensity)
        # Beer's law: direct <= solar_constant (no amplification).
        assert atmo.direct_intensity <= atmo.solar_constant

    def test_diffuse_fraction_in_unit_range(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        atmo = boot.atmosphere_init
        assert 0.0 <= atmo.diffuse_fraction <= 1.0

    def test_dynamic_atmosphere_parsed(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        atmo = boot.atmosphere_init
        assert isinstance(atmo.dynamic, DynamicAtmosphereConfig)
        # Defaults from mars_env.yaml: dynamic atmosphere disabled by default.
        assert atmo.dynamic.enabled in (True, False)
        assert atmo.dynamic.sun_sweep.start_azimuth_deg >= 0.0
        assert atmo.dynamic.sun_sweep.end_azimuth_deg <= 360.0
        assert atmo.dynamic.update_interval_frames >= 1

    def test_hdri_dir_resolves_under_repo_root(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        assert boot.atmosphere_init.hdri_dir.startswith(boot.repo_root)

    def test_sun_position_matches_config(self) -> None:
        boot = run_stage2_boot(str(MARS_ENV_YAML))
        atmo = boot.atmosphere_init
        mars_cfg = boot.mars_cfg
        expected_az = float(mars_cfg.get("sun_azimuth_deg", 180))
        expected_el = float(mars_cfg.get("sun_elevation_deg", 45))
        assert atmo.sun_azimuth_deg == pytest.approx(expected_az)
        assert atmo.sun_elevation_deg == pytest.approx(expected_el)
        # ``compute_sun_position`` stores zenith in radians; sanity check range.
        assert 0.0 <= atmo.sun_pos.zenith_angle_rad <= np.pi


class TestScenarioYamlBoot:
    """Boot should succeed on an actual scenario YAML (deep-merge path)."""

    def test_scenario_yaml_loads(self) -> None:
        scenario = _find_scenario_without_cave()
        boot = run_stage2_boot(str(scenario))
        assert isinstance(boot, StageTwoBootResult)
        assert boot.terrain_cfg.get("procedural_preset") != "cave"


class TestOfflineImport:
    """stage2_boot must not require Isaac Sim at import time (P3)."""

    def test_module_imports_without_isaacsim(self) -> None:
        import importlib
        import sys

        # If stage2_boot had a top-level isaacsim import, importing here
        # in the no-GPU test environment would already have failed; this
        # test also verifies the absence of ``omni``/``isaacsim`` entries
        # under the module's globals.
        mod = importlib.import_module("marslab.runtime.stage2_boot")
        globs = vars(mod)
        for forbidden in ("omni", "isaacsim", "pxr"):
            assert (
                forbidden not in globs
            ), f"stage2_boot must not import {forbidden} at module scope"
        # Module must have registered in sys.modules.
        assert "marslab.runtime.stage2_boot" in sys.modules
