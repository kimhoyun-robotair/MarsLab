import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
from pydantic import ValidationError

from marslab.runtime.run_plan import (
    InputErrorKind,
    RunMode,
    RunPlanInputError,
    RunPlanRequest,
    build_run_plan,
    serialize_resolved_inputs,
    serialize_run_plan,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _request(**overrides: str | Path | bool | float | None) -> RunPlanRequest:
    values: dict[str, str | Path | bool | float | None] = {
        "scene_path": "assets/scene/jezero_plain/jezero_plain.usdz",
        "rover_usd_path": "assets/robots/rover/m2020.usd",
        "scenario_path": "configs/default.yaml",
        "rover_yaml_path": "configs/rover_m2020.yaml",
        "output_dir": "outputs/refactor",
        "log_path": "outputs/refactor/run-plan.json",
    }
    values.update(overrides)
    return RunPlanRequest.model_validate(values)


def test_resolved_inputs_are_identical_when_validate_and_run_share_inputs() -> None:
    # Given: identical real CLI/data inputs for both command modes.
    request = _request()

    # When: the public builder prepares validation and execution plans.
    validate_plan = build_run_plan(request, RunMode.VALIDATE, cwd=REPO_ROOT)
    run_plan = build_run_plan(request, RunMode.RUN, cwd=REPO_ROOT)

    # Then: the shared input serialization is byte-identical and all paths are absolute.
    assert serialize_resolved_inputs(validate_plan.resolved_inputs) == serialize_resolved_inputs(
        run_plan.resolved_inputs
    )
    assert all(
        path.is_absolute()
        for path in (
            run_plan.resolved_inputs.scene,
            run_plan.resolved_inputs.rover_usd,
            run_plan.resolved_inputs.scenario_yaml,
            run_plan.resolved_inputs.rover_yaml,
            run_plan.resolved_inputs.output_dir,
            run_plan.resolved_inputs.log_path,
        )
    )


def test_plans_differ_only_by_mode_and_execution_policy() -> None:
    # Given: one canonical request.
    request = _request(headless=True, ros2_enabled=False)

    # When: both supported modes are serialized through the same builder.
    validate_data = json.loads(
        serialize_run_plan(build_run_plan(request, RunMode.VALIDATE, cwd=REPO_ROOT))
    )
    run_data = json.loads(serialize_run_plan(build_run_plan(request, RunMode.RUN, cwd=REPO_ROOT)))
    validate_specific = {key: validate_data.pop(key) for key in ("mode", "execution")}
    run_specific = {key: run_data.pop(key) for key in ("mode", "execution")}

    # Then: only the declared command behavior differs.
    assert validate_data == run_data
    assert validate_specific == {
        "mode": "validate",
        "execution": {
            "atmosphere_enabled": True,
            "boot_simulation": False,
            "headless": True,
            "ros2_enabled": False,
            "run_loop": False,
            "validate_assets": True,
        },
    }
    assert run_specific == {
        "mode": "run",
        "execution": {
            "atmosphere_enabled": True,
            "boot_simulation": True,
            "headless": True,
            "ros2_enabled": False,
            "run_loop": True,
            "validate_assets": True,
        },
    }


def test_plan_exposes_frozen_typed_runtime_settings_and_sanitized_json() -> None:
    # Given: CLI overrides that differ from YAML defaults.
    request = _request(sun_azimuth_deg=135.0, sun_elevation_deg=40.0)

    # When: the request crosses the preparation boundary.
    plan = build_run_plan(request, RunMode.RUN, cwd=REPO_ROOT)
    serialized = serialize_run_plan(plan)

    # Then: consumers receive typed settings and deterministic sanitized output.
    assert plan.control.wheel_radius == 0.2667
    assert plan.sensors.seed == 42
    assert plan.ros2.namespace == "rover"
    assert plan.atmosphere.sun_azimuth_deg == 135.0
    assert plan.atmosphere.sun_elevation_deg == 40.0
    assert plan.spawn.orientation_rpy == (0.0, 0.0, 0.0)
    assert plan.seed == 42
    assert serialized == serialize_run_plan(plan)
    assert "declaring_path" not in serialized
    assert "argv" not in serialized
    with pytest.raises(ValidationError):
        plan.atmosphere.sun_azimuth_deg = 90.0


@pytest.mark.parametrize(
    ("field", "value", "kind"),
    [
        ("scene_path", None, InputErrorKind.MISSING),
        ("rover_usd_path", "missing.usd", InputErrorKind.MISSING),
        ("scenario_path", "missing.yaml", InputErrorKind.MISSING),
        ("rover_yaml_path", "missing.yaml", InputErrorKind.MISSING),
    ],
)
def test_invalid_required_input_fails_before_boot_sentinel(
    field: str,
    value: str | None,
    kind: InputErrorKind,
) -> None:
    # Given: a missing required CLI input and a boot sentinel after preparation.
    request = _request(**{field: value})
    booted = False

    # When: preparation rejects the request.
    with pytest.raises(RunPlanInputError) as caught:
        build_run_plan(request, RunMode.RUN, cwd=REPO_ROOT)
        booted = True

    # Then: the typed diagnostic is raised before boot can be reached.
    assert caught.value.kind is kind
    assert caught.value.field == field
    assert booted is False


def test_conflicting_scene_aliases_fail_before_boot_sentinel() -> None:
    # Given: canonical and legacy scene flags point to different readable files.
    request = _request(legacy_scene_path="assets/robots/rover/m2020.usd")
    booted = False

    # When: the resolver encounters the conflicting declarations.
    with pytest.raises(RunPlanInputError) as caught:
        build_run_plan(request, RunMode.VALIDATE, cwd=REPO_ROOT)
        booted = True

    # Then: a typed conflict is returned before boot.
    assert caught.value.kind is InputErrorKind.CONFLICT
    assert caught.value.field == "scene_path"
    assert booted is False


def test_unreadable_input_fails_before_boot_sentinel(tmp_path: Path) -> None:
    # Given: an existing input file with every read permission bit removed.
    unreadable = tmp_path / "scenario.yaml"
    unreadable.write_text("mars_env: {}\n", encoding="utf-8")
    unreadable.chmod(0)
    request = _request(scenario_path=unreadable)
    booted = False

    # When: preparation checks the input surface.
    try:
        with pytest.raises(RunPlanInputError) as caught:
            build_run_plan(request, RunMode.RUN, cwd=REPO_ROOT)
            booted = True
    finally:
        unreadable.chmod(0o600)

    # Then: unreadability is distinguished from absence before boot.
    assert caught.value.kind is InputErrorKind.UNREADABLE
    assert caught.value.field == "scenario_path"
    assert booted is False


def test_request_rejects_unknown_and_nonfinite_cli_values_before_boot() -> None:
    # Given: raw CLI-shaped values with either an unknown key or NaN override.
    valid = _request().model_dump(mode="python")

    # When/Then: the strict request boundary rejects both malformed variants.
    with pytest.raises(ValidationError):
        RunPlanRequest.model_validate({**valid, "unexpected": True})
    with pytest.raises(ValidationError):
        RunPlanRequest.model_validate({**valid, "sun_azimuth_deg": float("nan")})


def test_relative_cli_paths_use_explicit_cwd_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: relative CLI paths declared from an explicit working directory.
    scene = tmp_path / "scene.usdz"
    rover_usd = tmp_path / "rover.usd"
    scene.write_bytes(b"scene")
    rover_usd.write_bytes(b"rover")
    request = RunPlanRequest(
        scene_path=scene.name,
        rover_usd_path=rover_usd.name,
        scenario_path=REPO_ROOT / "configs/default.yaml",
        rover_yaml_path=REPO_ROOT / "configs/rover_m2020.yaml",
    )

    # When: the plan is built with that CLI working directory.
    plan = build_run_plan(request, RunMode.VALIDATE, cwd=tmp_path)

    # Then: CLI values are canonicalized against it and remain stable afterwards.
    assert plan.resolved_inputs.scene == scene
    assert plan.resolved_inputs.rover_usd == rover_usd
    original = plan.resolved_inputs.scene
    monkeypatch.chdir(REPO_ROOT)
    assert plan.resolved_inputs.scene == original
    with pytest.raises((FrozenInstanceError, ValidationError)):
        plan.resolved_inputs.scene = REPO_ROOT
