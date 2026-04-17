"""Unit tests for marslab.terrain.elevation_loader."""

import os
import tempfile
from unittest import mock

import numpy as np
import pytest

from marslab.terrain.elevation_loader import load_terrain_elevation


class TestProceduralElevation:
    def test_flat_preset(self) -> None:
        cfg = {
            "source": "procedural",
            "procedural_preset": "flat",
            "terrain_size": [32, 32],
            "terrain_resolution": 1.0,
            "seed": 42,
        }
        elev, meta, res = load_terrain_elevation(cfg)
        assert elev.shape == (32, 32)
        assert res == 1.0
        assert isinstance(meta, dict)

    def test_canyon_preset_passes_canyon_params(self) -> None:
        cfg = {
            "source": "procedural",
            "procedural_preset": "canyon",
            "terrain_size": [64, 64],
            "terrain_resolution": 0.5,
            "seed": 1,
            "canyon_depth": 20.0,
            "canyon_floor_width": 10.0,
        }
        elev, _, res = load_terrain_elevation(cfg)
        assert elev.shape == (64, 64)
        assert res == 0.5
        # Canyon should produce nonzero relief.
        assert elev.max() - elev.min() > 1.0

    def test_seed_reproducible(self) -> None:
        cfg = {
            "source": "procedural",
            "procedural_preset": "hills",
            "terrain_size": [32, 32],
            "terrain_resolution": 1.0,
            "seed": 7,
        }
        elev_a, _, _ = load_terrain_elevation(dict(cfg))
        elev_b, _, _ = load_terrain_elevation(dict(cfg))
        np.testing.assert_array_equal(elev_a, elev_b)


class TestCaveElevation:
    def test_cave_preset_stashes_cave_data(self) -> None:
        cfg = {
            "source": "procedural",
            "procedural_preset": "cave",
            "terrain_size": [80, 80],
            "terrain_resolution": 2.0,
            "seed": 42,
            "cave": {
                "tube_width_m": 40.0,
                "tube_height_ratio": 0.5,
                "cross_section_noise": 0.0,
                "tube_direction_deg": 0.0,
                "tube_curvature": 0.0,
                "ceiling_thickness_m": 10.0,
                "skylight_count": 0,
                "skylight_diameter_m": 10.0,
                "skylight_depth_m": 10.0,
                "skylight_overhang_deg": 0.0,
                "debris_cone_present": False,
                "debris_cone_count": 0,
                "debris_cone_angle_deg": 0.0,
                "breakdown_coverage_pct": 0.0,
                "breakdown_block_mean_m": 0.1,
                "breakdown_block_sigma": 0.05,
                "floor_flat_pct": 100.0,
                "ring_resolution": 16,
                "path_resolution": 20,
                # wall_albedo_range is a material param; loader must drop it.
                "wall_albedo_range": [0.05, 0.15],
            },
        }
        elev, _, res = load_terrain_elevation(cfg)
        assert elev.ndim == 2
        assert res == 2.0
        # Loader stashes full cave payload for downstream mesh builder.
        assert "_cave_data" in cfg
        assert "surface_elevation" in cfg["_cave_data"]


class TestHiriseElevation:
    def test_hirise_missing_dir_raises(self) -> None:
        cfg = {"source": "hirise"}
        with pytest.raises(ValueError, match="converted_dem_dir"):
            load_terrain_elevation(cfg)

    def test_hirise_calls_loader_and_crop(self) -> None:
        """Fake DEM directory — ensure crop params are forwarded."""
        fake_elev = np.arange(100 * 100, dtype=np.float32).reshape(100, 100)
        fake_meta = {
            "resolution_x": 0.5,
            "resolution_y": 0.5,
            "width": 100,
            "height": 100,
        }

        cropped_elev = fake_elev[10:20, 30:40]
        cropped_meta = {**fake_meta, "width": 10, "height": 10}

        with (
            mock.patch(
                "marslab.terrain.dem_loader.load_converted_dem",
                return_value=(fake_elev, fake_meta),
            ) as mock_load,
            mock.patch(
                "marslab.terrain.dem_loader.crop_dem",
                return_value=(cropped_elev, cropped_meta),
            ) as mock_crop,
            tempfile.TemporaryDirectory() as tmp,
        ):
            cfg = {
                "source": "hirise",
                "converted_dem_dir": tmp,
                "dem_crop": {"row": 10, "col": 30, "height": 10, "width": 10},
            }
            elev, meta, res = load_terrain_elevation(cfg)

            mock_load.assert_called_once_with(os.path.abspath(tmp))
            mock_crop.assert_called_once()
            assert elev.shape == (10, 10)
            assert res == 0.5
            assert meta["width"] == 10


class TestUnknownSource:
    def test_unknown_source_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown terrain source"):
            load_terrain_elevation({"source": "alien"})
