from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from marslab.config import load_rover_config, load_scenario_config
from marslab.config.schema.rover_sensors import DisabledSensorConfig

REPO_ROOT = Path(__file__).resolve().parents[2]


def _canonical(path: str) -> dict[str, object]:
    return yaml.safe_load((REPO_ROOT / path).read_text(encoding="utf-8"))


def _write_yaml(tmp_path: Path, name: str, data: dict[str, object]) -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _child(data: dict[str, object], key: str) -> dict[str, object]:
    match data[key]:
        case dict() as child:
            return child
        case invalid:
            raise AssertionError(f"expected mapping at {key}, got {invalid!r}")


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_scenario_rejects_non_finite_number(tmp_path: Path, invalid: float) -> None:
    # Given: a canonical scenario with a non-finite runtime scalar.
    scenario = _canonical("configs/default.yaml")
    _child(scenario, "mars_env")["gravity"] = invalid
    path = _write_yaml(tmp_path, "scenario.yaml", scenario)

    # When/Then: parsing fails at the production boundary.
    with pytest.raises(ValidationError):
        load_scenario_config(path)


def test_scenario_rejects_unknown_key(tmp_path: Path) -> None:
    # Given: a canonical scenario with an undeclared key.
    scenario = _canonical("configs/default.yaml")
    scenario["generation"] = {"terrain": True}
    path = _write_yaml(tmp_path, "scenario.yaml", scenario)

    # When/Then: strict schema parsing rejects the key.
    with pytest.raises(ValidationError):
        load_scenario_config(path)


@pytest.mark.parametrize(
    ("field_path", "invalid"),
    [
        (("sensors", "camera", "local_translation"), [0.0, 1.0]),
        (("control", "wheel_radius"), 0.0),
        (("chassis", "mass"), -1.0),
    ],
)
def test_rover_rejects_invalid_physical_values(
    tmp_path: Path,
    field_path: tuple[str, ...],
    invalid: object,
) -> None:
    # Given: a canonical Rover with one invalid physical declaration.
    rover = _canonical("configs/rover_m2020.yaml")
    target = rover
    for key in field_path[:-1]:
        target = _child(target, key)
    target[field_path[-1]] = invalid
    path = _write_yaml(tmp_path, "rover.yaml", rover)

    # When/Then: production parsing rejects it before runtime acquisition.
    with pytest.raises(ValidationError):
        load_rover_config(path)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("usd_path", "../assets/robots/rover/m2020.usd"),
        ("base_config", "rover_base.yaml"),
        ("spawn_position", [0.0, 0.0, 0.0]),
        ("spawn_orientation_rpy", [0.0, 0.0, 0.0]),
    ],
)
def test_rover_rejects_removed_root_field(tmp_path: Path, field_name: str, value: object) -> None:
    # Given: a removed Rover root field is restored to a canonical declaration.
    rover = _canonical("configs/rover_m2020.yaml")
    rover[field_name] = value
    path = _write_yaml(tmp_path, "rover.yaml", rover)

    # When/Then: strict parsing rejects the removed field rather than retaining it.
    with pytest.raises(ValidationError):
        load_rover_config(path)


def test_enabled_sensor_requires_nonempty_parent(tmp_path: Path) -> None:
    # Given: an enabled canonical sensor without a declared parent link.
    rover = _canonical("configs/rover_m2020.yaml")
    _child(_child(rover, "sensors"), "camera").pop("parent_link")
    path = _write_yaml(tmp_path, "rover.yaml", rover)

    # When/Then: production parsing rejects the impossible enabled state.
    with pytest.raises(ValidationError):
        load_rover_config(path)


def test_runtime_loader_does_not_leak_raw_dicts() -> None:
    # Given: both canonical production configuration inputs.
    scenario_path = REPO_ROOT / "configs" / "default.yaml"
    rover_path = REPO_ROOT / "configs" / "rover_m2020.yaml"

    # When: both cross their production parsing boundaries.
    scenario = load_scenario_config(scenario_path)
    rover = load_rover_config(rover_path)

    # Then: callers receive frozen domain models, never mappings.
    assert not isinstance(scenario, dict)
    assert not isinstance(rover, dict)
    with pytest.raises(ValidationError):
        scenario.mars_env.__class__.model_validate(
            {**scenario.mars_env.model_dump(), "gravity": "3.72"}
        )


def test_disabled_sensor_may_omit_acquisition_fields(tmp_path: Path) -> None:
    # Given: a canonical Rover with its camera explicitly disabled.
    rover = _canonical("configs/rover_m2020.yaml")
    _child(rover, "sensors")["camera"] = {"enabled": False}
    path = _write_yaml(tmp_path, "rover.yaml", rover)

    # When: the production boundary parses the Rover declaration.
    config = load_rover_config(path)

    # Then: the disabled variant needs no parent or acquisition fields.
    assert isinstance(config.sensors.camera, DisabledSensorConfig)


def test_production_models_are_frozen() -> None:
    # Given: the canonical typed scenario.
    scenario = load_scenario_config(REPO_ROOT / "configs" / "default.yaml")

    # When/Then: runtime code cannot mutate validated state.
    field_name = "gravity"
    with pytest.raises(ValidationError, match="frozen"):
        setattr(scenario.mars_env, field_name, 3.71)
