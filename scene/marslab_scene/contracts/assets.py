"""Validated reusable asset descriptors."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from marslab_scene.contracts.files import require_artifact_file


@dataclass(frozen=True, slots=True)
class RockAssetDescriptor:
    manifest_path: Path
    stage_path: Path
    prototype_ids: tuple[str, ...]
    native_diameters_m: tuple[float, ...]
    stable_pose_candidates_wxyz: tuple[tuple[tuple[float, float, float, float], ...], ...] = ()
    license_path: Path | None = None
    attribution: str = ""
    bundle_digest: str = ""

    def __post_init__(self) -> None:
        root = self.manifest_path.parent
        require_artifact_file(root, self.manifest_path)
        require_artifact_file(root, self.stage_path)
        if self.license_path is not None:
            require_artifact_file(root, self.license_path)


@dataclass(frozen=True, slots=True)
class HabitatAssetDescriptor:
    manifest_path: Path
    stage_path: Path
    centroid_zup_m: tuple[float, float, float]
    aabb_min_zup_m: tuple[float, float, float]
    aabb_max_zup_m: tuple[float, float, float]
    body_floor_z_m: float
    license_path: Path | None = None
    attribution: str = ""
    bundle_digest: str = ""

    def __post_init__(self) -> None:
        root = self.manifest_path.parent
        require_artifact_file(root, self.manifest_path)
        require_artifact_file(root, self.stage_path)
        if self.license_path is not None:
            require_artifact_file(root, self.license_path)
