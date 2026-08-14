from __future__ import annotations

import argparse
import importlib
import json
import os
import tempfile
from pathlib import Path

from marslab.config import load_rover_config
from marslab.config.schema.rover_sensors import DisabledSensorConfig
from marslab.validation.lightweight import (
    validate_rover_file,
    validate_rover_manifest,
    validate_usdz_package,
)
from marslab.validation.models import Diagnostic, Severity, StageOpenError, ValidationReport
from marslab.validation.openusd import inspect_rover, inspect_scene
from marslab.validation.semantic import evaluate_rover_facts, evaluate_scene_facts


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m marslab.validation.assets")
    parser.add_argument("--scene", action="append", required=True, type=Path)
    parser.add_argument("--rover-manifest", required=True, type=Path)
    parser.add_argument("--rover-usd", required=True, type=Path)
    parser.add_argument("--rover-yaml", required=True, type=Path)
    parser.add_argument("--json-dir", required=True, type=Path)
    parser.add_argument("--require-ros-companion", action="store_true")
    return parser


def _merge(primary: ValidationReport, secondary: ValidationReport) -> ValidationReport:
    return ValidationReport(
        kind=secondary.kind,
        path=secondary.path,
        facts=secondary.facts,
        diagnostics=primary.diagnostics + secondary.diagnostics,
        metadata=primary.metadata + secondary.metadata,
    )


def _known_warnings(scene: Path) -> tuple[Diagnostic, ...]:
    metadata_path = scene.with_name("metadata.json")
    try:
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        failures = data["validation"].get("package_compliance_failures", [])
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return ()
    if not isinstance(failures, list):
        return ()
    return tuple(
        Diagnostic(
            code="scene.compliance.known_source",
            severity=Severity.WARNING,
            message=str(message),
            path=str(scene),
        )
        for message in failures
    )


def _write_report(directory: Path, name: str, report: ValidationReport) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"validate-{name}.json"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{destination.name}.", dir=directory)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(report.to_dict(), stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _lightweight_reports(
    args: argparse.Namespace,
) -> tuple[list[ValidationReport], ValidationReport]:
    scene_reports = [validate_usdz_package(path.resolve()) for path in args.scene]
    rover_report = validate_rover_manifest(
        args.rover_manifest.resolve(),
        require_ros_companion=args.require_ros_companion,
    )
    rover_report = _merge(rover_report, validate_rover_file(args.rover_usd.resolve()))
    return scene_reports, rover_report


def _write_all(
    output: Path, scenes: list[ValidationReport], rover: ValidationReport, scene_paths: list[Path]
) -> None:
    for path, report in zip(scene_paths, scenes, strict=True):
        _write_report(output, path.stem, report)
    _write_report(output, "rover", rover)


def _stage_failure(kind: str, path: Path, error: StageOpenError | RuntimeError) -> ValidationReport:
    return ValidationReport(
        kind=kind,
        path=str(path),
        diagnostics=(
            Diagnostic(
                code=f"{kind}.stage.open_failed",
                severity=Severity.ERROR,
                message=f"OpenUSD could not inspect stage: {error}",
                path=str(path),
            ),
        ),
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    scene_paths = [path.resolve() for path in args.scene]
    scene_reports, rover_report = _lightweight_reports(args)
    if any(not report.ok for report in [*scene_reports, rover_report]):
        _write_all(args.json_dir, scene_reports, rover_report, scene_paths)
        return 1
    rover_config = load_rover_config(args.rover_yaml)
    enabled_mounts = tuple(
        sensor.parent_link
        for sensor in (
            rover_config.sensors.camera,
            rover_config.sensors.lidar_3d,
            rover_config.sensors.lidar_2d,
            rover_config.sensors.imu,
        )
        if not isinstance(sensor, DisabledSensorConfig)
    )
    isaacsim = importlib.import_module("isaacsim")
    app = isaacsim.SimulationApp({"headless": True})
    exit_code = 1
    try:
        semantic_scenes = []
        for path, package_report in zip(scene_paths, scene_reports, strict=True):
            try:
                semantic = evaluate_scene_facts(path, inspect_scene(path))
            except (StageOpenError, RuntimeError) as error:
                semantic = _stage_failure("scene", path, error)
            warnings = ValidationReport(
                kind="scene",
                path=str(path),
                diagnostics=_known_warnings(path),
            )
            semantic_scenes.append(_merge(package_report, _merge(warnings, semantic)))
        rover_path = args.rover_usd.resolve()
        try:
            rover_semantic = evaluate_rover_facts(
                rover_path,
                inspect_rover(rover_path),
                drive_joints=tuple(rover_config.control.drive_joint_names),
                steer_joints=tuple(rover_config.control.steer_joint_names),
                sensor_mounts=enabled_mounts,
            )
        except (StageOpenError, RuntimeError) as error:
            rover_semantic = _stage_failure("rover", rover_path, error)
        rover_report = _merge(rover_report, rover_semantic)
        _write_all(args.json_dir, semantic_scenes, rover_report, scene_paths)
        exit_code = 0 if all(report.ok for report in [*semantic_scenes, rover_report]) else 1
    finally:
        try:
            app.app.post_quit(exit_code)
        finally:
            try:
                app.close()
            except SystemExit as error:
                if error.code not in (None, 0):
                    raise
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
