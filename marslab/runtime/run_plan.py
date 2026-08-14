from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import assert_never

from pydantic import model_validator

from marslab.config import load_rover_config, load_scenario_config
from marslab.config.schema.common import FiniteFloat, StrictConfigModel
from marslab.config.schema.rover import ControlConfig, RoverConfig, SensorsConfig, SpawnConfig
from marslab.config.schema.rover_ros2 import Ros2BridgeConfig
from marslab.config.schema.scenario import MarsEnvConfig, ScenarioConfig


class RunMode(StrEnum):
    VALIDATE = "validate"
    RUN = "run"


class InputErrorKind(StrEnum):
    MISSING = "missing"
    CONFLICT = "conflict"
    UNREADABLE = "unreadable"


@dataclass(frozen=True, slots=True)
class RunPlanInputError(Exception):
    kind: InputErrorKind
    field: str
    path: Path | None = None

    def __str__(self) -> str:
        suffix = f": {self.path}" if self.path is not None else ""
        return f"{self.field} is {self.kind.value}{suffix}"


class RunPlanRequest(StrictConfigModel):
    scene_path: str | Path | None
    rover_usd_path: str | Path | None
    scenario_path: str | Path | None
    rover_yaml_path: str | Path | None
    legacy_scene_path: str | Path | None = None
    output_dir: str | Path | None = None
    log_path: str | Path | None = None
    headless: bool = False
    ros2_enabled: bool = True
    atmosphere_enabled: bool = True
    z_offset: FiniteFloat | None = 0.1
    sun_azimuth_deg: FiniteFloat | None = None
    sun_elevation_deg: FiniteFloat | None = None


class ResolvedInputs(StrictConfigModel):
    scene: Path
    rover_usd: Path
    scenario_yaml: Path
    rover_yaml: Path
    output_dir: Path
    log_path: Path

    @model_validator(mode="after")
    def paths_are_absolute(self) -> ResolvedInputs:
        if not all(
            path.is_absolute()
            for path in (
                self.scene,
                self.rover_usd,
                self.scenario_yaml,
                self.rover_yaml,
                self.output_dir,
                self.log_path,
            )
        ):
            raise ValueError("resolved input paths must be absolute")
        return self


class ExecutionPolicy(StrictConfigModel):
    validate_assets: bool
    boot_simulation: bool
    run_loop: bool
    headless: bool
    ros2_enabled: bool
    atmosphere_enabled: bool


class RunPlan(StrictConfigModel):
    mode: RunMode
    execution: ExecutionPolicy
    resolved_inputs: ResolvedInputs
    scenario: ScenarioConfig
    rover: RoverConfig

    @property
    def spawn(self) -> SpawnConfig:
        return self.rover.spawn

    @property
    def control(self) -> ControlConfig:
        return self.rover.control

    @property
    def sensors(self) -> SensorsConfig:
        return self.rover.sensors

    @property
    def ros2(self) -> Ros2BridgeConfig:
        return self.rover.ros2

    @property
    def atmosphere(self) -> MarsEnvConfig:
        return self.scenario.mars_env

    @property
    def seed(self) -> int | None:
        return self.rover.sensors.seed


def _canonical_path(path: str | Path, cwd: Path) -> Path:
    candidate = Path(path).expanduser()
    return (candidate if candidate.is_absolute() else cwd / candidate).resolve(strict=False)


def _required_file(value: str | Path | None, field: str, cwd: Path) -> Path:
    if value is None or not str(value).strip():
        raise RunPlanInputError(kind=InputErrorKind.MISSING, field=field)
    path = _canonical_path(value, cwd)
    if not path.is_file():
        raise RunPlanInputError(kind=InputErrorKind.MISSING, field=field, path=path)
    mode = path.stat().st_mode
    readable_bits = stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH
    if mode & readable_bits == 0 or not os.access(path, os.R_OK):
        raise RunPlanInputError(kind=InputErrorKind.UNREADABLE, field=field, path=path)
    return path


def _scene_path(request: RunPlanRequest, cwd: Path) -> Path:
    scene = _required_file(request.scene_path, "scene_path", cwd)
    if request.legacy_scene_path is None:
        return scene
    legacy = _required_file(request.legacy_scene_path, "legacy_scene_path", cwd)
    if legacy != scene:
        raise RunPlanInputError(kind=InputErrorKind.CONFLICT, field="scene_path", path=legacy)
    return scene


def _execution_policy(request: RunPlanRequest, mode: RunMode) -> ExecutionPolicy:
    match mode:
        case RunMode.VALIDATE:
            boot_simulation = False
            run_loop = False
        case RunMode.RUN:
            boot_simulation = True
            run_loop = True
        case unreachable:
            assert_never(unreachable)
    return ExecutionPolicy(
        validate_assets=True,
        boot_simulation=boot_simulation,
        run_loop=run_loop,
        headless=request.headless,
        ros2_enabled=request.ros2_enabled,
        atmosphere_enabled=request.atmosphere_enabled,
    )


def _apply_overrides(request: RunPlanRequest, scenario: ScenarioConfig) -> ScenarioConfig:
    mars_values = scenario.mars_env.model_dump(mode="python")
    if request.sun_azimuth_deg is not None:
        mars_values["sun_azimuth_deg"] = request.sun_azimuth_deg
    if request.sun_elevation_deg is not None:
        mars_values["sun_elevation_deg"] = request.sun_elevation_deg
    mars_env = MarsEnvConfig.model_validate(mars_values)
    return ScenarioConfig(
        declaring_path=scenario.declaring_path,
        mars_env=mars_env,
        rendering=scenario.rendering,
    )


def _apply_spawn_override(request: RunPlanRequest, rover: RoverConfig) -> RoverConfig:
    if rover.spawn.z_offset is not None or request.z_offset is None:
        return rover
    spawn = SpawnConfig.model_validate(
        {**rover.spawn.model_dump(mode="python"), "z_offset": request.z_offset}
    )
    return rover.model_copy(update={"spawn": spawn})


def build_run_plan(
    request: RunPlanRequest,
    mode: RunMode,
    *,
    cwd: Path | None = None,
) -> RunPlan:
    cli_cwd = (cwd or Path.cwd()).expanduser().resolve(strict=True)
    scene = _scene_path(request, cli_cwd)
    rover_usd = _required_file(request.rover_usd_path, "rover_usd_path", cli_cwd)
    scenario_yaml = _required_file(request.scenario_path, "scenario_path", cli_cwd)
    rover_yaml = _required_file(request.rover_yaml_path, "rover_yaml_path", cli_cwd)
    output_dir = _canonical_path(request.output_dir or "outputs", cli_cwd)
    log_path = _canonical_path(
        request.log_path or output_dir / "run-plan.json",
        cli_cwd,
    )
    scenario = _apply_overrides(request, load_scenario_config(scenario_yaml))
    rover = _apply_spawn_override(request, load_rover_config(rover_yaml))
    return RunPlan(
        mode=mode,
        execution=_execution_policy(request, mode),
        resolved_inputs=ResolvedInputs(
            scene=scene,
            rover_usd=rover_usd,
            scenario_yaml=scenario_yaml,
            rover_yaml=rover_yaml,
            output_dir=output_dir,
            log_path=log_path,
        ),
        scenario=scenario,
        rover=rover,
    )


def serialize_resolved_inputs(resolved_inputs: ResolvedInputs) -> str:
    return resolved_inputs.model_dump_json()


def serialize_run_plan(plan: RunPlan) -> str:
    return plan.model_dump_json(
        exclude={
            "scenario": {"declaring_path"},
            "rover": {"declaring_path"},
        }
    )


__all__ = [
    "ExecutionPolicy",
    "InputErrorKind",
    "ResolvedInputs",
    "RunMode",
    "RunPlan",
    "RunPlanInputError",
    "RunPlanRequest",
    "build_run_plan",
    "serialize_resolved_inputs",
    "serialize_run_plan",
]
