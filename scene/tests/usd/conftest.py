from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from marslab_scene.config.models import OutputSettings
from marslab_scene.contracts.layers import (
    FlatnessReport,
    HabitatLayer,
    RockLayer,
    RockPlacementStats,
    TerrainAnchor,
)
from marslab_scene.contracts.provenance import Provenance
from marslab_scene.contracts.terrain import TerrainArtifact

_FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures/assets"


@pytest.fixture
def terrain_artifact(tmp_path: Path) -> TerrainArtifact:
    root = tmp_path / "terrain-source"
    root.mkdir()
    stage = root / "terrain.usda"
    stage.write_text(
        """#usda 1.0
(
    defaultPrim = "World"
    metersPerUnit = 1
    upAxis = "Z"
)
def Xform "World"
{
    def Xform "MarsTerrain"
    {
        def Mesh "VisualMesh"
        {
            int[] faceVertexCounts = [3]
            int[] faceVertexIndices = [0, 1, 2]
            point3f[] points = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        }
    }
}
""",
        encoding="utf-8",
    )
    manifest = root / "manifest.yaml"
    manifest.write_text("kind: terrain_artifact\n", encoding="utf-8")
    return TerrainArtifact(
        root_dir=root,
        stage_path=stage,
        dem_path=None,
        manifest_path=manifest,
        coordinate_frame=None,
        provenance=Provenance(
            producer="phase6-test",
            marslab_revision=None,
            marslab_utils_revision=None,
            source_files=(stage,),
        ),
    )


@pytest.fixture
def rock_layer() -> RockLayer:
    return RockLayer(
        asset_manifest=_FIXTURE_ROOT / "rocks/manifest.yaml",
        positions_local_m=np.asarray([[1.0, 2.0, 3.0]], dtype=np.float64),
        prototype_indices=np.asarray([0], dtype=np.int32),
        scales=np.asarray([1.25], dtype=np.float64),
        orientations_wxyz=np.asarray([[1.0, 0.0, 0.0, 0.0]], dtype=np.float64),
        placement_source=None,
        seed=42,
        stats=RockPlacementStats(
            csv_count=1,
            placed_count=1,
            skipped_out_of_bounds=0,
            skipped_nodata=0,
            clamped_count=0,
        ),
    )


@pytest.fixture
def habitat_layer() -> HabitatLayer:
    return HabitatLayer(
        asset_manifest=_FIXTURE_ROOT / "habitats/manifest.yaml",
        translation_local_m=(4.0, 5.0, 6.0),
        rotation_wxyz=(1.0, 0.0, 0.0, 0.0),
        anchor=TerrainAnchor(
            projected_xy_m=(1004.0, 1995.0),
            local_xyz_m=(4.0, 5.0, 6.0),
            dem_row_column=(2, 3),
            mode="flattest",
        ),
        flatness=FlatnessReport(elevation_range_m=0.25, valid_sample_count=9),
        aabb_min_local_m=(3.0, 4.5, 6.0),
        aabb_max_local_m=(5.0, 5.5, 7.5),
    )


@pytest.fixture
def output_settings(tmp_path: Path) -> OutputSettings:
    settings = OutputSettings(
        directory=Path("scene-output"),
        stage=Path("scene.usda"),
        runtime_package=Path("scene.usdz"),
        manifest=Path("manifest.yaml"),
    )
    return settings.model_copy(update={"directory": tmp_path / "scene-output"})
