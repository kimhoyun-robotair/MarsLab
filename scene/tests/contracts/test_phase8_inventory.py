from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

_SOURCE_TESTS = (
    "HiRISEGen/tests/test_cli_export.py",
    "HiRISEGen/tests/test_config.py",
    "HiRISEGen/tests/test_coordinates.py",
    "HiRISEGen/tests/test_crop.py",
    "HiRISEGen/tests/test_dem_info.py",
    "HiRISEGen/tests/test_elevation.py",
    "HiRISEGen/tests/test_heightfield_mesh.py",
    "HiRISEGen/tests/test_import.py",
    "HiRISEGen/tests/test_isaac_smoke_script.py",
    "HiRISEGen/tests/test_nodata.py",
    "HiRISEGen/tests/test_texture_config.py",
    "HiRISEGen/tests/test_texture_export.py",
    "HiRISEGen/tests/test_usd_writer.py",
    "HiRISEGen/tests/test_visual_enhancement_colorize.py",
    "HiRISEGen/tests/test_visual_enhancement_config.py",
    "HiRISEGen/tests/test_visual_enhancement_e2e.py",
    "HiRISEGen/tests/test_visual_enhancement_finalize.py",
    "HiRISEGen/tests/test_visual_enhancement_metadata.py",
    "HiRISEGen/tests/test_visual_enhancement_orthomosaic.py",
    "HiRISEGen/tests/test_visual_enhancement_palette.py",
    "HiRISEGen/tests/test_visual_enhancement_sources.py",
    "HiRISEGen/tests/test_visual_enhancement_usd_binding.py",
    "RockyComposer/tests/test_authoring.py",
    "RockyComposer/tests/test_config.py",
    "RockyComposer/tests/test_ingest.py",
    "RockyComposer/tests/test_isaac_smoke.py",
    "RockyComposer/tests/test_pipeline.py",
    "RockyComposer/tests/test_placement.py",
    "RockyComposer/tests/test_proto_meta.py",
    "RockyComposer/tests/test_raster_diff.py",
    "RockyComposer/tests/test_raster_mesh_consistency.py",
    "RockyComposer/tests/test_sampling.py",
    "HabitatGen/tests/test_assetgen.py",
    "HabitatGen/tests/test_composer.py",
    "HabitatGen/tests/test_skeleton.py",
)


def test_locked_source_test_inventory_has_final_dispositions() -> None:
    # Given: the Phase-8 migration inventory for the locked source revision.
    repository_root = Path(__file__).resolve().parents[3]
    migration_map = (repository_root / "scene/MIGRATION_TEST_MAP.md").read_text(encoding="utf-8")

    # When: every source test module is looked up by its unambiguous repository path.
    missing = [
        source_test for source_test in _SOURCE_TESTS if f"`{source_test}`" not in migration_map
    ]

    # Then: all modules have a final migrated/replaced/excluded disposition.
    assert not missing
    assert "Pending" not in migration_map


def test_phase8_topology_has_documented_asset_license_roots_and_no_retired_dependency() -> None:
    # Given: the final scene package and documentation topology.
    repository_root = Path(__file__).resolve().parents[3]
    project_metadata = (repository_root / "scene/pyproject.toml").read_text(encoding="utf-8")

    # When: the Phase-8 package and asset-license boundaries are inspected.
    required_paths = (
        repository_root / "scene/README.md",
        repository_root / "CONFIGURATION_GUIDE.md",
        repository_root / "assets/rocks/LICENSES/README.md",
        repository_root / "assets/habitats/LICENSES/README.md",
    )
    retired_dependencies = ("typer", "bpy", "blender", "trimesh", "pandas", "synthterrain")

    # Then: the public guides/license roots exist and no retired direct dependency remains.
    assert all(path.is_file() for path in required_paths)
    assert not any(
        f'"{dependency}' in project_metadata.lower() for dependency in retired_dependencies
    )
