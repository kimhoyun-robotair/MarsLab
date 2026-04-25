"""Unit tests for marslab.terrain.terrain_loader facade + DEM-path resolver (offline, R3-A3)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from marslab.terrain import load_scenario_terrain as reexport_load_terrain
from marslab.terrain import resolve_dem_paths as reexport_resolve_dem_paths
from marslab.terrain.terrain_loader import load_scenario_terrain, resolve_dem_paths

# ---------------------------------------------------------------------------
# load_scenario_terrain — procedural / cave / hirise / unknown
# ---------------------------------------------------------------------------


def test_load_scenario_terrain_procedural_flat() -> None:
    """Procedural ``flat`` source returns (ndarray, dict, float)."""
    cfg = {
        "source": "procedural",
        "procedural_preset": "flat",
        "terrain_size": [32, 32],
        "terrain_resolution": 1.0,
        "seed": 42,
    }
    elevation, metadata, resolution = load_scenario_terrain(cfg)
    assert isinstance(elevation, np.ndarray)
    assert elevation.shape == (32, 32)
    assert isinstance(metadata, dict)
    assert isinstance(resolution, float)
    assert resolution == 1.0


def test_load_scenario_terrain_cave_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cave preset routes through ``cave.orchestrator.generate_cave_mesh``.

    Stubbed so the test does not execute trimesh-heavy generation.
    """
    fake_elevation = np.zeros((40, 40), dtype=np.float32)
    fake_cave = {
        "surface_elevation": fake_elevation,
        "metadata": {"preset": "cave", "tube_width_m": 200.0},
        "tube_mesh": None,
        "ceiling_mesh": None,
    }

    def fake_generate_cave_mesh(**_kwargs: object) -> dict:
        return fake_cave

    monkeypatch.setattr(
        "marslab.terrain.cave.orchestrator.generate_cave_mesh",
        fake_generate_cave_mesh,
    )

    cfg = {
        "source": "procedural",
        "procedural_preset": "cave",
        "terrain_size": [40, 40],
        "terrain_resolution": 1.0,
        "seed": 42,
        "cave": {"tube_width_m": 200.0, "tube_height_ratio": 0.5},
    }
    elevation, metadata, resolution = load_scenario_terrain(cfg)
    assert isinstance(elevation, np.ndarray)
    assert elevation.shape == (40, 40)
    assert metadata.get("preset") == "cave"
    assert resolution == 1.0
    # Loader stashes the full cave payload back into the cfg for downstream.
    assert cfg["_cave_data"] is fake_cave


def test_load_scenario_terrain_hirise_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """HiRISE source calls ``dem_loader.load_converted_dem`` via the facade.

    ``crop_dem`` is skipped when ``dem_crop`` is absent; we verify only the
    loader hand-off here.
    """
    calls: list[str] = []

    fake_elevation = np.ones((10, 10), dtype=np.float32)
    fake_metadata = {"resolution_x": 1.25}

    def fake_load_converted_dem(dem_dir: str) -> tuple[np.ndarray, dict]:
        calls.append(dem_dir)
        return fake_elevation, fake_metadata

    monkeypatch.setattr(
        "marslab.terrain.dem_loader.load_converted_dem",
        fake_load_converted_dem,
    )

    cfg = {
        "source": "hirise",
        "converted_dem_dir": "/abs/path/to/dem",
        "terrain_resolution": 1.0,
    }
    elevation, metadata, resolution = load_scenario_terrain(cfg)
    assert elevation is fake_elevation
    assert metadata is fake_metadata
    # ``resolution_m`` picked up from metadata when present.
    assert resolution == pytest.approx(1.25)
    assert calls == ["/abs/path/to/dem"]


def test_load_scenario_terrain_unknown_source_raises() -> None:
    """Unknown ``source`` value propagates as ``ValueError``."""
    cfg = {"source": "martian_moonbeam"}
    with pytest.raises(ValueError, match="Unknown terrain source"):
        load_scenario_terrain(cfg)


# ---------------------------------------------------------------------------
# resolve_dem_paths
# ---------------------------------------------------------------------------


def test_resolve_dem_paths_procedural_returns_empty() -> None:
    """Procedural scenarios have no DEM assets — result is an empty dict."""
    cfg = {"source": "procedural"}
    paths = resolve_dem_paths(cfg)
    assert paths == {}


def test_resolve_dem_paths_hirise_absolute_dir() -> None:
    """Absolute ``converted_dem_dir`` → three canonical keys as Path objects."""
    cfg = {"source": "hirise", "converted_dem_dir": "/abs/dem/jezero"}
    paths = resolve_dem_paths(cfg)
    assert "converted_dir" in paths
    assert "elevation_npy" in paths
    assert "metadata_json" in paths
    for value in paths.values():
        assert isinstance(value, Path)
    assert paths["converted_dir"] == Path("/abs/dem/jezero").resolve()
    assert paths["elevation_npy"].name == "elevation.npy"
    assert paths["metadata_json"].name == "metadata.json"


def test_resolve_dem_paths_hirise_relative_is_resolved_against_repo_root(
    tmp_path: Path,
) -> None:
    """Relative ``converted_dem_dir`` is joined onto ``repo_root``."""
    repo_root = tmp_path  # tmp_path is already absolute and exists.
    cfg = {
        "source": "hirise",
        "converted_dem_dir": "assets/terrain/dem/foo",
    }
    paths = resolve_dem_paths(cfg, repo_root=str(repo_root))
    expected = (repo_root / "assets/terrain/dem/foo").resolve()
    assert paths["converted_dir"] == expected
    assert paths["elevation_npy"] == expected / "elevation.npy"
    assert paths["metadata_json"] == expected / "metadata.json"


def test_resolve_dem_paths_texture_dir_key_present() -> None:
    """``texture_dir`` key is emitted as a Path when configured."""
    cfg = {
        "source": "hirise",
        "converted_dem_dir": "/abs/dem",
        "texture_dir": "/abs/textures/mars",
    }
    paths = resolve_dem_paths(cfg)
    assert "texture_dir" in paths
    assert isinstance(paths["texture_dir"], Path)
    assert paths["texture_dir"] == Path("/abs/textures/mars").resolve()


def test_resolve_dem_paths_rock_mesh_dir_key_present() -> None:
    """``rock_mesh_dir`` key is emitted as a Path when configured."""
    cfg = {
        "source": "hirise",
        "converted_dem_dir": "/abs/dem",
        "rock_mesh_dir": "/abs/rocks",
    }
    paths = resolve_dem_paths(cfg)
    assert "rock_mesh_dir" in paths
    assert isinstance(paths["rock_mesh_dir"], Path)
    assert paths["rock_mesh_dir"] == Path("/abs/rocks").resolve()


# ---------------------------------------------------------------------------
# Package-level re-export
# ---------------------------------------------------------------------------


def test_package_reexports_match_module_symbols() -> None:
    """``from marslab.terrain import ...`` must succeed and return the same objects."""
    assert reexport_load_terrain is load_scenario_terrain
    assert reexport_resolve_dem_paths is resolve_dem_paths
