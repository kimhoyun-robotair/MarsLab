"""Final scene artifact contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from marslab_scene.contracts.files import require_artifact_file
from marslab_scene.contracts.provenance import Provenance
from marslab_scene.contracts.terrain import TerrainArtifact
from marslab_scene.errors import ContractValueError


@dataclass(frozen=True, slots=True)
class LayerSummary:
    kind: Literal["rocks", "habitat"]
    count: int

    def __post_init__(self) -> None:
        if self.count < 0:
            raise ContractValueError("layer summary count must be non-negative")


@dataclass(frozen=True, slots=True)
class SceneArtifact:
    root_dir: Path
    stage_path: Path
    runtime_package_path: Path
    manifest_path: Path
    terrain: TerrainArtifact
    layer_summaries: tuple[LayerSummary, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        require_artifact_file(self.root_dir, self.stage_path)
        require_artifact_file(self.root_dir, self.runtime_package_path)
        require_artifact_file(self.root_dir, self.manifest_path)
