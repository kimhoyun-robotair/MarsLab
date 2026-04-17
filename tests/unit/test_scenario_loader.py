"""Unit tests for marslab.config.scenario_loader."""

import os
import tempfile

import numpy as np
import pytest
import yaml

from marslab.config.scenario_loader import (
    deep_merge,
    load_scenario_config,
    resolve_spawn_pose,
)


class TestDeepMerge:
    def test_disjoint_keys(self) -> None:
        base = {"a": 1}
        override = {"b": 2}
        assert deep_merge(base, override) == {"a": 1, "b": 2}

    def test_override_wins_on_leaf(self) -> None:
        base = {"a": 1, "b": 2}
        override = {"b": 99}
        assert deep_merge(base, override) == {"a": 1, "b": 99}

    def test_nested_merge(self) -> None:
        base = {"rover": {"damping": 1.0, "mass": 10.0}, "ros2": {"rate": 100}}
        override = {"rover": {"damping": 5.0}}
        result = deep_merge(base, override)
        assert result == {
            "rover": {"damping": 5.0, "mass": 10.0},
            "ros2": {"rate": 100},
        }

    def test_lists_replaced_not_concatenated(self) -> None:
        base = {"joints": ["a", "b", "c"]}
        override = {"joints": ["x"]}
        assert deep_merge(base, override) == {"joints": ["x"]}

    def test_inputs_not_mutated(self) -> None:
        base = {"a": {"x": 1}}
        override = {"a": {"y": 2}}
        deep_merge(base, override)
        assert base == {"a": {"x": 1}}
        assert override == {"a": {"y": 2}}

    def test_override_non_dict_replaces_dict(self) -> None:
        base = {"sensors": {"camera": {"fov": 60}}}
        override = {"sensors": None}
        assert deep_merge(base, override) == {"sensors": None}


class TestLoadScenarioConfig:
    @staticmethod
    def _write(tmpdir: str, name: str, data: dict) -> str:
        path = os.path.join(tmpdir, name)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f)
        return path

    def test_merge_with_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            # Base file stores the rover/sensors/control/ros2 blocks at the
            # top level (matches configs/robots/rover_m2020.yaml layout).
            base = {
                "usd_path": "assets/robots/rover/m2020.usd",
                "control": {"drive_damping": 1000.0, "max_steer_angle": 0.7},
                "sensors": {"imu": {"rate": 100}, "lidar": {"profile": "foo"}},
            }
            self._write(tmp, "rover_base.yaml", base)
            scenario = {
                "mars_env": {"gravity": 3.72},
                "terrain": {"source": "procedural"},
                "rendering": {"mode": "path_tracing"},
                "rover": {
                    "base_config": "rover_base.yaml",
                    "spawn": {"mode": "dem_center", "z_offset": 0.5},
                    "control": {"drive_damping": 500.0},
                },
            }
            sc_path = self._write(tmp, "scenario.yaml", scenario)

            cfg = load_scenario_config(sc_path)
            rover = cfg["rover"]
            # Scenario override wins.
            assert rover["control"]["drive_damping"] == 500.0
            # Untouched base values preserved.
            assert rover["control"]["max_steer_angle"] == 0.7
            assert rover["usd_path"] == "assets/robots/rover/m2020.usd"
            # Scenario-only fields passed through.
            assert rover["spawn"] == {"mode": "dem_center", "z_offset": 0.5}
            # base_config key removed.
            assert "base_config" not in rover
            # Top-level non-rover sections preserved.
            assert cfg["mars_env"]["gravity"] == 3.72
            # lidar alias normalised.
            assert "lidar_3d" in rover["sensors"]
            assert "lidar" not in rover["sensors"]

    def test_scenario_only_no_rover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario = {
                "mars_env": {"gravity": 3.72},
                "terrain": {"source": "procedural"},
                "rendering": {"mode": "path_tracing"},
            }
            path = self._write(tmp, "no_rover.yaml", scenario)
            cfg = load_scenario_config(path)
            assert "rover" not in cfg
            assert cfg["mars_env"]["gravity"] == 3.72

    def test_inline_rover_without_base(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario = {
                "mars_env": {"gravity": 3.72},
                "terrain": {},
                "rendering": {},
                "rover": {"usd_path": "foo.usd", "spawn": {"mode": "absolute"}},
            }
            path = self._write(tmp, "inline.yaml", scenario)
            cfg = load_scenario_config(path)
            assert cfg["rover"]["usd_path"] == "foo.usd"

    def test_missing_base_file_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scenario = {
                "rover": {"base_config": "does_not_exist.yaml"},
            }
            path = self._write(tmp, "bad.yaml", scenario)
            with pytest.raises(FileNotFoundError):
                load_scenario_config(path)

    def test_trailing_whitespace_stripped(self) -> None:
        # A trailing newline or spaces (copy/paste artefact) must not break
        # the loader: strip() at entry makes "foo.yaml\n" resolve like "foo.yaml".
        with tempfile.TemporaryDirectory() as tmp:
            scenario = {"mars_env": {"gravity": 3.72}}
            path = self._write(tmp, "trailing.yaml", scenario)
            cfg = load_scenario_config(path + "\n  ")
            assert cfg["mars_env"]["gravity"] == 3.72

    def test_embedded_whitespace_raises_with_hint(self) -> None:
        # A stray trailing token (e.g. `... .yaml 2` from a mis-pasted `2>&1`)
        # must surface as a ValueError with a whitespace hint — not a bare
        # FileNotFoundError that obscures the root cause.
        with tempfile.TemporaryDirectory() as tmp:
            scenario = {"mars_env": {"gravity": 3.72}}
            path = self._write(tmp, "good.yaml", scenario)
            with pytest.raises(ValueError, match="whitespace"):
                load_scenario_config(path + " 2")

    def test_missing_file_lists_nearby(self) -> None:
        # When the user mistypes a filename, the FileNotFoundError message
        # must include sibling YAMLs so they can spot the typo without a
        # separate `ls` step.
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "alpha.yaml", {"a": 1})
            self._write(tmp, "beta.yaml", {"b": 2})
            bogus = os.path.join(tmp, "does_not_exist.yaml")
            with pytest.raises(FileNotFoundError) as excinfo:
                load_scenario_config(bogus)
            msg = str(excinfo.value)
            assert "alpha.yaml" in msg
            assert "beta.yaml" in msg


class TestResolveSpawnPose:
    def _flat_elevation(self) -> tuple[np.ndarray, dict, float]:
        # 101x101 grid at 1m resolution, flat z=10.
        return np.full((101, 101), 10.0, dtype=np.float32), {}, 1.0

    def test_absolute_mode_ignores_terrain(self) -> None:
        cfg = {"spawn": {"mode": "absolute", "xy": [5.0, -3.0], "z": 2.5}}
        x, y, z = resolve_spawn_pose(cfg, None, None, 1.0)
        assert (x, y, z) == (5.0, -3.0, 2.5)

    def test_absolute_falls_back_to_z_offset(self) -> None:
        cfg = {"spawn": {"mode": "absolute", "xy": [0.0, 0.0], "z_offset": 1.0}}
        x, y, z = resolve_spawn_pose(cfg, None, None, 1.0)
        assert z == 1.0

    def test_dem_center_samples_flat(self) -> None:
        elev, meta, res = self._flat_elevation()
        cfg = {"spawn": {"mode": "dem_center", "z_offset": 0.5}}
        x, y, z = resolve_spawn_pose(cfg, elev, meta, res)
        # 101x101 @ 1m → mesh centre at ((101-1)/2, (101-1)/2) = (50, 50).
        assert (x, y) == (50.0, 50.0)
        # Flat z=10 normalised to 0 (nanmin subtracted) + 0.5 z_offset.
        assert z == pytest.approx(0.5)

    def test_dem_center_subtracts_datum_offset(self) -> None:
        # Mars datum regression: raw DEM at ~-2575 m must not leak through.
        # jezero_flat real log showed Spawn z = -2572.888 before the fix.
        elev = np.full((50, 80), -2575.0, dtype=np.float32)
        cfg = {"spawn": {"mode": "dem_center", "z_offset": 0.5}}
        x, y, z = resolve_spawn_pose(cfg, elev, {}, 1.0)
        # 80 cols → mesh_center_x = (80-1)/2 = 39.5; 50 rows → 24.5.
        assert x == pytest.approx(39.5)
        assert y == pytest.approx(24.5)
        # Raw -2575 minus nanmin(-2575) == 0, plus 0.5 offset.
        assert z == pytest.approx(0.5)

    def test_dem_relative_uses_offset(self) -> None:
        elev = np.zeros((101, 101), dtype=np.float32)
        # Mesh centre at (50, 50). xy=[10, 10] → world (60, 60) → sample
        # elev[row=60, col=60]. Place the 5m peak there.
        elev[60, 60] = 5.0
        cfg = {"spawn": {"mode": "dem_relative", "xy": [10.0, 10.0], "z_offset": 0.0}}
        x, y, z = resolve_spawn_pose(cfg, elev, {}, 1.0)
        assert (x, y) == (60.0, 60.0)
        assert z == pytest.approx(5.0)

    def test_dem_relative_bilinear(self) -> None:
        elev = np.zeros((11, 11), dtype=np.float32)
        elev[5, 5] = 0.0
        elev[5, 6] = 2.0
        # Offset x=+0.5m (half a cell east of centre) should sample midway.
        cfg = {"spawn": {"mode": "dem_relative", "xy": [0.5, 0.0], "z_offset": 0.0}}
        _, _, z = resolve_spawn_pose(cfg, elev, {}, 1.0)
        assert z == pytest.approx(1.0, abs=1e-5)

    def test_invalid_mode_raises(self) -> None:
        elev, meta, res = self._flat_elevation()
        cfg = {"spawn": {"mode": "weird", "xy": [0, 0]}}
        with pytest.raises(ValueError, match="spawn.mode"):
            resolve_spawn_pose(cfg, elev, meta, res)

    def test_missing_elevation_raises_for_dem_mode(self) -> None:
        cfg = {"spawn": {"mode": "dem_center"}}
        with pytest.raises(ValueError, match="elevation grid"):
            resolve_spawn_pose(cfg, None, None, 1.0)

    def test_bad_xy_raises(self) -> None:
        cfg = {"spawn": {"mode": "absolute", "xy": [1.0]}}
        with pytest.raises(ValueError, match="spawn.xy"):
            resolve_spawn_pose(cfg, None, None, 1.0)
