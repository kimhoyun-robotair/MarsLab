from __future__ import annotations

import json
import stat
import subprocess
import zipfile
from pathlib import Path

from marslab.validation.models import Diagnostic, JsonValue, Severity, ValidationReport
from marslab.validation.paths import find_repo_root, safe_archive_member, safe_path, sha256
from marslab.validation.rover_file import validate_rover_file


def _diagnostic(code: str, message: str, path: Path) -> Diagnostic:
    return Diagnostic(code=code, severity=Severity.ERROR, message=message, path=str(path))


def validate_usdz_package(path: Path) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    metadata: list[tuple[str, str | int | bool]] = []
    if not path.is_file():
        diagnostics.append(_diagnostic("scene.file.missing", "scene package is missing", path))
        return ValidationReport(
            kind="scene-package", path=str(path), diagnostics=tuple(diagnostics)
        )
    try:
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            metadata.append(("member_count", len(members)))
            if not members:
                diagnostics.append(_diagnostic("scene.zip.empty", "USDZ contains no members", path))
            for member in members:
                if not safe_archive_member(member.filename):
                    diagnostics.append(
                        _diagnostic(
                            "scene.zip.unsafe_member",
                            f"unsafe package member: {member.filename}",
                            path,
                        )
                    )
                mode = member.external_attr >> 16
                if stat.S_ISLNK(mode):
                    diagnostics.append(
                        _diagnostic(
                            "scene.zip.symlink_member",
                            f"symlink package member: {member.filename}",
                            path,
                        )
                    )
            metadata.append(("default_layer", members[0].filename if members else ""))
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        diagnostics.append(_diagnostic("scene.zip.corrupt", f"unreadable USDZ: {exc}", path))
    metadata_path = path.with_name("metadata.json")
    if metadata_path.is_file() and not diagnostics:
        try:
            source = json.loads(metadata_path.read_text(encoding="utf-8"))
            package = source["package"]
            validation = source["validation"]
            expected_size = package["size_bytes"]
            expected_hash = package["sha256"]
            expected_layer = validation["default_layer"]
            expected_members = validation["member_count"]
            observed = dict(metadata)
            if path.stat().st_size != expected_size:
                diagnostics.append(
                    _diagnostic("scene.metadata.size_mismatch", "package size changed", path)
                )
            if sha256(path) != expected_hash:
                diagnostics.append(
                    _diagnostic("scene.metadata.hash_mismatch", "package checksum changed", path)
                )
            if observed.get("default_layer") != expected_layer:
                diagnostics.append(
                    _diagnostic(
                        "scene.metadata.default_layer_mismatch", "default layer changed", path
                    )
                )
            if observed.get("member_count") != expected_members:
                diagnostics.append(
                    _diagnostic(
                        "scene.metadata.member_count_mismatch", "member inventory changed", path
                    )
                )
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            diagnostics.append(
                _diagnostic("scene.metadata.invalid", "scene metadata is malformed", metadata_path)
            )
    return ValidationReport(
        kind="scene-package",
        path=str(path),
        diagnostics=tuple(diagnostics),
        metadata=tuple(metadata),
    )


def _check_file_map(
    root: Path,
    files: dict[str, str],
    diagnostics: list[Diagnostic],
    manifest_path: Path,
) -> None:
    for relative, expected in sorted(files.items()):
        candidate = safe_path(root, relative)
        if candidate is None:
            diagnostics.append(
                _diagnostic(
                    "rover.manifest.unsafe_path", f"unsafe manifest path: {relative}", manifest_path
                )
            )
        elif not candidate.is_file():
            diagnostics.append(
                _diagnostic(
                    "rover.manifest.file_missing", f"manifest file missing: {relative}", candidate
                )
            )
        elif sha256(candidate) != expected:
            diagnostics.append(
                _diagnostic(
                    "rover.manifest.hash_mismatch", f"checksum mismatch: {relative}", candidate
                )
            )


def _mapping(value: JsonValue) -> dict[str, JsonValue] | None:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        return None
    return value


def _string_map(value: JsonValue) -> dict[str, str] | None:
    mapping = _mapping(value)
    if mapping is None or not all(isinstance(item, str) for item in mapping.values()):
        return None
    return {key: item for key, item in mapping.items() if isinstance(item, str)}


def validate_rover_manifest(
    manifest_path: Path, *, require_ros_companion: bool
) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    try:
        raw: JsonValue = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        diagnostics.append(
            _diagnostic("rover.manifest.invalid", f"unreadable manifest: {exc}", manifest_path)
        )
        return ValidationReport(
            kind="rover-manifest", path=str(manifest_path), diagnostics=tuple(diagnostics)
        )
    data = _mapping(raw)
    bundle_files = _string_map(data.get("bundle_files")) if data is not None else None
    submodule = _mapping(data.get("submodule")) if data is not None else None
    if data is None or data.get("schema_version") != 1 or bundle_files is None or submodule is None:
        diagnostics.append(
            _diagnostic(
                "rover.manifest.schema", "manifest does not match schema version 1", manifest_path
            )
        )
        return ValidationReport(
            kind="rover-manifest", path=str(manifest_path), diagnostics=tuple(diagnostics)
        )
    _check_file_map(manifest_path.parent, bundle_files, diagnostics, manifest_path)
    repo_root = find_repo_root(manifest_path)
    submodule_path = submodule.get("path")
    expected_commit = submodule.get("commit")
    companion_files = _string_map(submodule.get("files"))
    urdf = submodule.get("ros_companion_urdf")
    if repo_root is None or not isinstance(submodule_path, str):
        diagnostics.append(
            _diagnostic(
                "rover.manifest.repo_missing", "repository root is unavailable", manifest_path
            )
        )
        return ValidationReport(
            kind="rover-manifest", path=str(manifest_path), diagnostics=tuple(diagnostics)
        )
    checkout = safe_path(repo_root, submodule_path)
    if checkout is None or not (checkout / ".git").exists():
        diagnostics.append(
            _diagnostic(
                "rover.submodule.uninitialized",
                "initialize the pinned Rover submodule",
                manifest_path,
            )
        )
        return ValidationReport(
            kind="rover-manifest", path=str(manifest_path), diagnostics=tuple(diagnostics)
        )
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        capture_output=True,
        check=False,
        text=True,
    )
    actual_commit = result.stdout.strip()
    if result.returncode != 0:
        diagnostics.append(
            _diagnostic(
                "rover.submodule.uninitialized",
                "submodule checkout is not a Git worktree",
                checkout,
            )
        )
    elif not isinstance(expected_commit, str) or actual_commit != expected_commit:
        diagnostics.append(
            _diagnostic(
                "rover.submodule.commit_mismatch",
                f"expected {expected_commit}, found {actual_commit}",
                checkout,
            )
        )
    if require_ros_companion:
        if not isinstance(urdf, str) or safe_path(checkout, urdf) is None:
            diagnostics.append(
                _diagnostic("rover.ros.urdf_missing", "invalid companion URDF path", manifest_path)
            )
        else:
            urdf_path = safe_path(checkout, urdf)
            if urdf_path is None or not urdf_path.is_file():
                diagnostics.append(
                    _diagnostic("rover.ros.urdf_missing", "companion URDF is missing", checkout)
                )
        if companion_files is None:
            diagnostics.append(
                _diagnostic(
                    "rover.manifest.schema", "companion checksum map is missing", manifest_path
                )
            )
        else:
            _check_file_map(checkout, companion_files, diagnostics, manifest_path)
    known_warnings = data.get("known_warnings")
    if isinstance(known_warnings, list):
        for warning in known_warnings:
            item = _mapping(warning)
            if item is None:
                continue
            code = item.get("code")
            message = item.get("message")
            count = item.get("count")
            if isinstance(code, str) and isinstance(message, str) and isinstance(count, int):
                diagnostics.append(
                    Diagnostic(
                        code=code,
                        severity=Severity.WARNING,
                        message=f"{message} (baseline count: {count})",
                        path=str(manifest_path),
                    )
                )
    return ValidationReport(
        kind="rover-manifest", path=str(manifest_path), diagnostics=tuple(diagnostics)
    )


__all__ = ["validate_rover_file", "validate_rover_manifest", "validate_usdz_package"]
