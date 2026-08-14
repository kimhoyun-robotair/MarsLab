from pathlib import Path

from marslab.config import RoverConfig, load_rover_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_canonical_rover_is_typed_and_paths_anchor_to_declaring_yaml() -> None:
    # Given: the canonical Rover declaration.
    rover_path = REPO_ROOT / "configs" / "rover_m2020.yaml"

    # When: the production entry loader reads it.
    rover = load_rover_config(rover_path)

    # Then: exact runtime values and the current repo-relative asset anchor are stable.
    assert isinstance(rover, RoverConfig)
    assert rover.control.wheel_radius == 0.2667
    assert rover.sensors.camera.resolution == (1280, 960)
    assert rover.spawn.orientation_rpy == (0.0, 0.0, 0.0)
    assert (
        rover.urdf_source_path
        == REPO_ROOT / "assets" / "m2020-urdf-models" / "rover" / "m2020.urdf"
    )
    assert rover.declaring_path == rover_path
