from pathlib import Path

from marslab.config import ScenarioConfig, load_scenario_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_canonical_scenario_is_typed_and_paths_anchor_to_declaring_yaml() -> None:
    # Given: the canonical standalone scenario declaration.
    scenario_path = REPO_ROOT / "configs" / "default.yaml"

    # When: the production scenario loader composes it.
    scenario = load_scenario_config(str(scenario_path))

    # Then: consumer-visible values and declaring-file-relative path text are stable.
    assert isinstance(scenario, ScenarioConfig)
    assert scenario.mars_env.gravity == 3.72
    assert scenario.mars_env.dynamic_atmosphere.time_scale == 200.0
    assert scenario.rendering.resolution == (1920, 1080)
    assert scenario.rendering.sky_dome_hdri_dir == REPO_ROOT / "assets" / "mars_sky"
    assert scenario.declaring_path == scenario_path
