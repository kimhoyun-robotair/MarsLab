"""Typed errors raised at scene package boundaries."""

from __future__ import annotations

from pathlib import Path

from typing_extensions import override


class SceneConfigError(Exception):
    path: Path
    detail: str

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(path, detail)

    @override
    def __str__(self) -> str:
        return f"invalid scene config {self.path}: {self.detail}"


class ArtifactManifestError(Exception):
    path: Path
    detail: str

    def __init__(self, path: Path, detail: str) -> None:
        self.path = path
        self.detail = detail
        super().__init__(path, detail)

    @override
    def __str__(self) -> str:
        return f"invalid artifact manifest {self.path}: {self.detail}"


class PathContractError(Exception):
    value: Path | str
    detail: str

    def __init__(self, value: Path | str, detail: str) -> None:
        self.value = value
        self.detail = detail
        super().__init__(value, detail)

    @override
    def __str__(self) -> str:
        return f"invalid path {self.value!s}: {self.detail}"


class UnknownCompatibilityProfileError(Exception):
    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__(name)

    @override
    def __str__(self) -> str:
        return f"unknown compatibility profile: {self.name}"


class CompatibilityProfileMismatch(Exception):
    expected: str
    actual: str
    artifact: Path

    def __init__(self, expected: str, actual: str, artifact: Path) -> None:
        self.expected = expected
        self.actual = actual
        self.artifact = artifact
        super().__init__(expected, actual, artifact)

    @override
    def __str__(self) -> str:
        return (
            f"compatibility profile mismatch for {self.artifact}: "
            f"expected {self.expected}, got {self.actual}"
        )


class SamplingSurfaceUnavailable(Exception):
    artifact: Path

    def __init__(self, artifact: Path) -> None:
        self.artifact = artifact
        super().__init__(artifact)

    @override
    def __str__(self) -> str:
        return f"terrain artifact has no DEM/frame sampling surface: {self.artifact}"


class ContractValueError(ValueError):
    detail: str

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)

    @override
    def __str__(self) -> str:
        return self.detail


class SceneBuildError(RuntimeError):
    detail: str

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)

    @override
    def __str__(self) -> str:
        return self.detail


class SceneFeatureUnavailable(RuntimeError):
    feature: str

    def __init__(self, feature: str) -> None:
        self.feature = feature
        super().__init__(feature)

    @override
    def __str__(self) -> str:
        return f"scene feature is unavailable: {self.feature}"
