from __future__ import annotations

from pathlib import Path

from marslab.validation.models import (
    Diagnostic,
    RoverFacts,
    SceneFacts,
    Severity,
    ValidationReport,
)


def _error(code: str, message: str, path: Path) -> Diagnostic:
    return Diagnostic(code=code, severity=Severity.ERROR, message=message, path=str(path))


def evaluate_scene_facts(path: Path, facts: SceneFacts) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    if facts.default_prim is None:
        diagnostics.append(_error("scene.default_prim.missing", "stage has no default prim", path))
    if facts.default_prim is not None and not facts.default_prim.startswith("/"):
        diagnostics.append(
            _error("scene.root.invalid", "default prim is not a composed root", path)
        )
    if facts.up_axis != "Z":
        diagnostics.append(_error("scene.up_axis.invalid", "scene must use Z up-axis", path))
    if facts.meters_per_unit != 1.0:
        diagnostics.append(_error("scene.units.invalid", "scene must use metersPerUnit=1", path))
    if not facts.mesh_paths:
        diagnostics.append(_error("scene.mesh.missing", "scene contains no composed Mesh", path))
    if not facts.collision_paths:
        diagnostics.append(
            _error("scene.collision.missing", "scene contains no collision API or attributes", path)
        )
    if facts.unresolved_ids:
        diagnostics.append(
            _error(
                "scene.dependency.unresolved",
                f"unresolved dependencies: {', '.join(facts.unresolved_ids)}",
                path,
            )
        )
    return ValidationReport(
        kind="scene", path=str(path), facts=facts, diagnostics=tuple(diagnostics)
    )


def evaluate_rover_facts(
    path: Path,
    facts: RoverFacts,
    *,
    drive_joints: tuple[str, ...],
    steer_joints: tuple[str, ...],
    sensor_mounts: tuple[str, ...],
) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    if facts.default_prim is None:
        diagnostics.append(_error("rover.default_prim.missing", "stage has no default prim", path))
    if facts.up_axis != "Z":
        diagnostics.append(_error("rover.up_axis.invalid", "rover must use Z up-axis", path))
    if facts.meters_per_unit != 1.0:
        diagnostics.append(_error("rover.units.invalid", "rover must use metersPerUnit=1", path))
    if not facts.articulation_paths:
        diagnostics.append(
            _error("rover.articulation.missing", "rover has no articulation root", path)
        )
    if "Body_Chassis" not in facts.prim_names:
        diagnostics.append(_error("rover.chassis.missing", "Body_Chassis prim is missing", path))
    missing_joints = sorted((set(drive_joints) | set(steer_joints)) - facts.prim_names)
    if missing_joints:
        diagnostics.append(
            _error(
                "rover.joint.missing",
                f"configured joints missing: {', '.join(missing_joints)}",
                path,
            )
        )
    missing_mounts = sorted(set(sensor_mounts) - facts.prim_names)
    if missing_mounts:
        diagnostics.append(
            _error(
                "rover.mount.missing",
                f"sensor parent mounts missing: {', '.join(missing_mounts)}",
                path,
            )
        )
    if facts.unresolved_ids:
        diagnostics.append(
            _error(
                "rover.dependency.unresolved",
                f"unresolved dependencies: {', '.join(facts.unresolved_ids)}",
                path,
            )
        )
    return ValidationReport(
        kind="rover", path=str(path), facts=facts, diagnostics=tuple(diagnostics)
    )


__all__ = ["evaluate_rover_facts", "evaluate_scene_facts"]
