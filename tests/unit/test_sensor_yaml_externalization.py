"""Sprint Day 2 Task D + E (2026-04-25): sensor YAML externalization.

These tests cover the new ``CameraConfig`` / ``Lidar3DConfig`` /
``Lidar2DConfig`` / ``IMUConfig`` / ``SensorsConfig`` schemas declared in
:mod:`marslab.config.schema.robot`.

Acceptance criteria covered here:

1. Every sensor parameter (range_min, range_max, horizontal_fov_deg,
   vertical_fov_deg, horizontal_resolution_deg, vertical_resolution_deg,
   rotation_rate_hz, profile_name, profile_json_path, usd_profile) round-
   trips through pydantic without being silently dropped (``extra='forbid'``).
2. Backward compat: a YAML using the legacy ``profile`` key (pre-Task-D)
   still loads via the ``mode='before'`` migration validator.
3. ``configs/robots/rover_m2020.yaml`` validates against ``SensorsConfig``.
4. Both presets in ``configs/sensors/`` validate against the matching
   per-sensor pydantic model.
5. ``profile_name`` and ``profile_json_path`` are mutually exclusive.
6. Range / FOV / clipping-range bounds enforced.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from marslab.config.schema.robot import (
    CameraConfig,
    IMUConfig,
    Lidar2DConfig,
    Lidar3DConfig,
    SensorsConfig,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
ROVER_YAML = REPO_ROOT / "configs" / "robots" / "rover_m2020.yaml"
SENSORS_DIR = REPO_ROOT / "configs" / "sensors"


def _minimal_lidar3d_payload() -> dict:
    """Smallest valid payload for ``Lidar3DConfig``."""
    return {
        "local_translation": [0.3, 0.0, -0.5],
        "range_min": 0.5,
        "range_max": 100.0,
        "horizontal_fov_deg": 360.0,
        "vertical_fov_deg": 30.0,
        "horizontal_resolution_deg": 0.4,
        "vertical_resolution_deg": 1.875,
        "rotation_rate_hz": 10.0,
        "profile_name": "Example_Rotary",
    }


def _minimal_lidar2d_payload() -> dict:
    return {
        "local_translation": [0.3, 0.0, -0.25],
        "range_min": 0.5,
        "range_max": 50.0,
        "horizontal_fov_deg": 360.0,
        "horizontal_resolution_deg": 0.25,
        "rotation_rate_hz": 30.0,
        "profile_name": "Example_Rotary_2D",
    }


def _minimal_camera_payload() -> dict:
    return {
        "local_translation": [0.3, 0.0, -2.1],
        "local_orientation_rpy_deg": [180.0, 0.0, 0.0],
        "resolution": [640, 480],
        "focal_length": 24.0,
        "clipping_range": [0.1, 1000.0],
    }


def _minimal_imu_payload() -> dict:
    return {"local_translation": [0.0, 0.0, 0.0]}


# ---------------------------------------------------------------------------
# Lidar3DConfig
# ---------------------------------------------------------------------------
class TestLidar3DConfig:
    """Acceptance criterion 1: every numeric LiDAR field round-trips."""

    def test_full_payload_loads(self) -> None:
        cfg = Lidar3DConfig(**_minimal_lidar3d_payload())
        assert cfg.range_min == 0.5
        assert cfg.range_max == 100.0
        assert cfg.horizontal_fov_deg == 360.0
        assert cfg.vertical_fov_deg == 30.0
        assert cfg.horizontal_resolution_deg == 0.4
        assert cfg.vertical_resolution_deg == 1.875
        assert cfg.rotation_rate_hz == 10.0
        assert cfg.profile_name == "Example_Rotary"
        assert cfg.profile_json_path is None
        assert cfg.usd_profile is None

    def test_legacy_profile_key_migrated(self) -> None:
        """Acceptance #5: pre-Task-D YAML using ``profile`` still loads."""
        payload = _minimal_lidar3d_payload()
        del payload["profile_name"]
        payload["profile"] = "Example_Rotary"
        cfg = Lidar3DConfig(**payload)
        assert cfg.profile_name == "Example_Rotary"

    def test_both_profile_and_profile_name_rejected(self) -> None:
        """Migrating ``profile`` -> ``profile_name`` is one-way: when the
        YAML already declares ``profile_name`` the legacy ``profile`` key
        is left alone, then ``extra='forbid'`` rejects it.  This is the
        safe failure mode — silently dropping a stale ``profile: ...``
        line could mask a half-finished migration where the user set both
        keys to different values.
        """
        payload = _minimal_lidar3d_payload()
        payload["profile"] = "Velodyne_VLP16"  # legacy stale value
        with pytest.raises(ValidationError, match="extra_forbidden|Extra inputs"):
            Lidar3DConfig(**payload)

    def test_extra_field_rejected(self) -> None:
        """``extra='forbid'`` blocks typos like ``rage_min`` (sic)."""
        payload = _minimal_lidar3d_payload()
        payload["rage_min"] = 0.5
        with pytest.raises(ValidationError):
            Lidar3DConfig(**payload)

    def test_range_max_must_exceed_range_min(self) -> None:
        payload = _minimal_lidar3d_payload()
        payload["range_min"] = 50.0
        payload["range_max"] = 10.0
        with pytest.raises(ValidationError, match="range_max"):
            Lidar3DConfig(**payload)

    def test_negative_range_rejected(self) -> None:
        payload = _minimal_lidar3d_payload()
        payload["range_min"] = -1.0
        with pytest.raises(ValidationError):
            Lidar3DConfig(**payload)

    def test_horizontal_fov_capped_at_360(self) -> None:
        payload = _minimal_lidar3d_payload()
        payload["horizontal_fov_deg"] = 720.0
        with pytest.raises(ValidationError):
            Lidar3DConfig(**payload)

    def test_profile_name_and_json_path_mutually_exclusive(self) -> None:
        payload = _minimal_lidar3d_payload()
        payload["profile_json_path"] = "/tmp/custom.json"
        with pytest.raises(ValidationError, match="pick one"):
            Lidar3DConfig(**payload)

    def test_at_least_one_profile_required(self) -> None:
        payload = _minimal_lidar3d_payload()
        del payload["profile_name"]
        with pytest.raises(ValidationError, match="profile_name"):
            Lidar3DConfig(**payload)

    def test_profile_json_path_alone_is_valid(self) -> None:
        """The escape hatch on its own is enough."""
        payload = _minimal_lidar3d_payload()
        del payload["profile_name"]
        payload["profile_json_path"] = "/abs/path/custom_lidar.json"
        cfg = Lidar3DConfig(**payload)
        assert cfg.profile_json_path == "/abs/path/custom_lidar.json"
        assert cfg.profile_name is None

    def test_usd_profile_round_trip(self) -> None:
        """Acceptance criterion (Task E): ``usd_profile`` string survives."""
        payload = _minimal_lidar3d_payload()
        payload["usd_profile"] = "Velodyne_VLP16"
        cfg = Lidar3DConfig(**payload)
        assert cfg.usd_profile == "Velodyne_VLP16"


# ---------------------------------------------------------------------------
# Lidar2DConfig
# ---------------------------------------------------------------------------
class TestLidar2DConfig:
    def test_full_payload_loads(self) -> None:
        cfg = Lidar2DConfig(**_minimal_lidar2d_payload())
        assert cfg.range_max == 50.0
        assert cfg.profile_name == "Example_Rotary_2D"
        assert cfg.rotation_rate_hz == 30.0

    def test_legacy_profile_key_migrated(self) -> None:
        payload = _minimal_lidar2d_payload()
        del payload["profile_name"]
        payload["profile"] = "Example_Rotary_2D"
        cfg = Lidar2DConfig(**payload)
        assert cfg.profile_name == "Example_Rotary_2D"

    def test_no_vertical_fov_field(self) -> None:
        """2D scanners are planar — vertical fields should be rejected."""
        payload = _minimal_lidar2d_payload()
        payload["vertical_fov_deg"] = 30.0
        with pytest.raises(ValidationError):
            Lidar2DConfig(**payload)


# ---------------------------------------------------------------------------
# CameraConfig
# ---------------------------------------------------------------------------
class TestCameraConfig:
    def test_full_payload_loads(self) -> None:
        cfg = CameraConfig(**_minimal_camera_payload())
        assert cfg.resolution == [640, 480]
        assert cfg.focal_length == 24.0
        assert cfg.clipping_range == [0.1, 1000.0]

    def test_clipping_range_far_must_exceed_near(self) -> None:
        payload = _minimal_camera_payload()
        payload["clipping_range"] = [10.0, 1.0]
        with pytest.raises(ValidationError, match="far"):
            CameraConfig(**payload)

    def test_clipping_range_near_must_be_positive(self) -> None:
        payload = _minimal_camera_payload()
        payload["clipping_range"] = [0.0, 1000.0]
        with pytest.raises(ValidationError, match="near"):
            CameraConfig(**payload)

    def test_focal_length_must_be_positive(self) -> None:
        payload = _minimal_camera_payload()
        payload["focal_length"] = -5.0
        with pytest.raises(ValidationError):
            CameraConfig(**payload)

    def test_extra_field_rejected(self) -> None:
        payload = _minimal_camera_payload()
        payload["focal_lenght"] = 24.0  # typo
        with pytest.raises(ValidationError):
            CameraConfig(**payload)


# ---------------------------------------------------------------------------
# IMUConfig
# ---------------------------------------------------------------------------
class TestIMUConfig:
    def test_full_payload_loads(self) -> None:
        cfg = IMUConfig(**_minimal_imu_payload())
        assert cfg.local_translation == [0.0, 0.0, 0.0]
        assert cfg.local_orientation_rpy_deg == [0.0, 0.0, 0.0]

    def test_translation_required(self) -> None:
        with pytest.raises(ValidationError):
            IMUConfig(local_orientation_rpy_deg=[0.0, 0.0, 0.0])

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError):
            IMUConfig(local_translation=[0.0, 0.0, 0.0], range_max=100.0)


# ---------------------------------------------------------------------------
# SensorsConfig (parent)
# ---------------------------------------------------------------------------
class TestSensorsConfig:
    def _full_payload(self) -> dict:
        return {
            "camera": _minimal_camera_payload(),
            "lidar_3d": _minimal_lidar3d_payload(),
            "lidar_2d": _minimal_lidar2d_payload(),
            "imu": _minimal_imu_payload(),
        }

    def test_full_payload_loads(self) -> None:
        cfg = SensorsConfig(**self._full_payload())
        assert cfg.camera.focal_length == 24.0
        assert cfg.lidar_3d.range_max == 100.0
        assert cfg.lidar_2d is not None
        assert cfg.lidar_2d.profile_name == "Example_Rotary_2D"
        assert cfg.imu.local_translation == [0.0, 0.0, 0.0]

    def test_lidar_2d_optional(self) -> None:
        payload = self._full_payload()
        del payload["lidar_2d"]
        cfg = SensorsConfig(**payload)
        assert cfg.lidar_2d is None

    def test_camera_required(self) -> None:
        payload = self._full_payload()
        del payload["camera"]
        with pytest.raises(ValidationError):
            SensorsConfig(**payload)

    def test_lidar_3d_required(self) -> None:
        payload = self._full_payload()
        del payload["lidar_3d"]
        with pytest.raises(ValidationError):
            SensorsConfig(**payload)

    def test_imu_required(self) -> None:
        payload = self._full_payload()
        del payload["imu"]
        with pytest.raises(ValidationError):
            SensorsConfig(**payload)

    def test_extra_top_level_sensor_rejected(self) -> None:
        """A future ``magnetometer`` block must extend the schema, not slip in."""
        payload = self._full_payload()
        payload["magnetometer"] = {"local_translation": [0.0, 0.0, 0.0]}
        with pytest.raises(ValidationError):
            SensorsConfig(**payload)


# ---------------------------------------------------------------------------
# Real-file integration: rover_m2020.yaml + presets validate.
# ---------------------------------------------------------------------------
class TestRoverYamlValidates:
    """Acceptance #3: ``configs/robots/rover_m2020.yaml`` parses cleanly."""

    def test_rover_yaml_sensors_block(self) -> None:
        with ROVER_YAML.open() as f:
            data = yaml.safe_load(f)
        cfg = SensorsConfig(**data["sensors"])
        # Spot-check: the Task D fields actually flow from the YAML.
        assert cfg.lidar_3d.range_min == 0.5
        assert cfg.lidar_3d.range_max == 100.0
        assert cfg.lidar_3d.profile_name == "Example_Rotary"
        assert cfg.lidar_2d is not None
        assert cfg.lidar_2d.profile_name == "Example_Rotary_2D"


class TestPresetsValidate:
    """Acceptance #6: every YAML in ``configs/sensors/`` validates."""

    def test_velodyne_vlp16_preset_loads_as_lidar_3d(self) -> None:
        # Day 3 H1 fix-up (2026-04-25, post-integration smoke): Isaac Sim
        # 5.1 does NOT register Velodyne_VLP16 OR Velodyne_VLS128 in
        # SUPPORTED_LIDAR_CONFIGS — only Ouster_VLS_128 is the closest
        # VLS-class scanner that ships, so the preset falls back to that.
        # See ``~/MarsLab/tmp/task_H1_finding.md``.
        path = SENSORS_DIR / "velodyne_vlp16.yaml"
        with path.open() as f:
            data = yaml.safe_load(f)
        cfg = Lidar3DConfig(**data)
        assert cfg.profile_name == "Ouster_VLS_128"
        assert cfg.usd_profile is None
        assert cfg.range_max == 100.0

    def test_hokuyo_ust_10lx_preset_loads_as_lidar_2d(self) -> None:
        # Day 3 H1 fix-up (2026-04-25): Isaac Sim 5.1 does NOT bundle
        # Hokuyo_UST_10LX.json; the preset uses Example_Rotary_2D as the
        # base profile.  See ``~/MarsLab/tmp/task_H1_finding.md``.
        path = SENSORS_DIR / "hokuyo_ust_10lx.yaml"
        with path.open() as f:
            data = yaml.safe_load(f)
        cfg = Lidar2DConfig(**data)
        assert cfg.profile_name == "Example_Rotary_2D"
        assert cfg.range_max == 10.0
        assert cfg.horizontal_fov_deg == 270.0

    def test_sensors_dir_has_two_presets(self) -> None:
        files = sorted(p.name for p in SENSORS_DIR.glob("*.yaml"))
        assert "velodyne_vlp16.yaml" in files
        assert "hokuyo_ust_10lx.yaml" in files


# ---------------------------------------------------------------------------
# Sensor spawner profile resolver — backward compat surface
# ---------------------------------------------------------------------------
class TestResolveLidarProfile:
    """``spawn_sensors`` is also called with raw dicts (integration test
    harness, scenario YAML before pydantic).  ``_resolve_lidar_profile``
    must therefore accept all three keys and prefer them in the documented
    order.
    """

    def test_profile_name_preferred_over_legacy(self) -> None:
        from marslab.sensors.sensor_spawner import _resolve_lidar_profile

        cfg = {"profile_name": "Example_Rotary", "profile": "Velodyne_VLP16"}
        assert _resolve_lidar_profile(cfg) == "Example_Rotary"

    def test_profile_json_path_wins_outright(self) -> None:
        from marslab.sensors.sensor_spawner import _resolve_lidar_profile

        cfg = {
            "profile_json_path": "/tmp/custom.json",
            "profile_name": "Example_Rotary",
        }
        assert _resolve_lidar_profile(cfg) == "/tmp/custom.json"

    def test_legacy_profile_alone_still_works(self) -> None:
        from marslab.sensors.sensor_spawner import _resolve_lidar_profile

        cfg = {"profile": "Example_Rotary"}
        assert _resolve_lidar_profile(cfg) == "Example_Rotary"

    def test_no_profile_raises_keyerror(self) -> None:
        from marslab.sensors.sensor_spawner import _resolve_lidar_profile

        with pytest.raises(KeyError):
            _resolve_lidar_profile({"local_translation": [0.0, 0.0, 0.0]})


# ---------------------------------------------------------------------------
# Sprint Day 3 Task H1 (2026-04-25): YAML numerics flow into runtime JSON.
#
# Closes Reviewer 2 finding H1 from ``~/MarsLab/tmp/day2_code_review.md``:
# the seven YAML numerics added in Day 2 were validated by pydantic and
# then dropped on the floor.  These tests prove the three runtime-
# overridable keys (``range_min``, ``range_max``, ``rotation_rate_hz``)
# actually reach a generated JSON file that ``LidarRtx.config_file_name``
# would consume.  The other four (FOV/resolution) are descriptive-only
# and intentionally NOT overridden — see ``_LidarBaseConfig`` docstring.
# ---------------------------------------------------------------------------
class TestYamlNumericsFlowToJson:
    """Acceptance criterion (Day 3 H1): YAML overrides hit Isaac Sim."""

    def test_range_max_round_trip_to_far_range_m(self, tmp_path) -> None:
        """``range_max: 50.0`` in YAML -> ``profile.farRangeM: 50.0`` in JSON."""
        import json as _json

        from marslab.sensors.sensor_spawner import _write_runtime_lidar_profile

        # Simulate the rover_m2020.yaml lidar_3d block with a runtime
        # override (50 m max range vs the bundled Example_Rotary's 200 m).
        yaml_payload = _minimal_lidar3d_payload()
        yaml_payload["range_max"] = 50.0

        # Validate the schema first — full YAML pipeline.
        cfg = Lidar3DConfig(**yaml_payload).model_dump()

        # The runtime helper sees the validated config dict.
        out = _write_runtime_lidar_profile(
            base_profile_name=cfg["profile_name"],
            overrides={"range_max": cfg["range_max"]},
            output_dir=str(tmp_path),
        )
        with open(out, "r") as f:
            generated = _json.load(f)
        assert generated["profile"]["farRangeM"] == pytest.approx(50.0, abs=1e-9)

    def test_range_min_round_trip(self, tmp_path) -> None:
        import json as _json

        from marslab.sensors.sensor_spawner import _write_runtime_lidar_profile

        yaml_payload = _minimal_lidar3d_payload()
        yaml_payload["range_min"] = 0.5
        cfg = Lidar3DConfig(**yaml_payload).model_dump()

        out = _write_runtime_lidar_profile(
            base_profile_name=cfg["profile_name"],
            overrides={"range_min": cfg["range_min"]},
            output_dir=str(tmp_path),
        )
        with open(out, "r") as f:
            generated = _json.load(f)
        assert generated["profile"]["nearRangeM"] == pytest.approx(0.5, abs=1e-9)

    def test_rotation_rate_round_trip(self, tmp_path) -> None:
        import json as _json

        from marslab.sensors.sensor_spawner import _write_runtime_lidar_profile

        yaml_payload = _minimal_lidar3d_payload()
        yaml_payload["rotation_rate_hz"] = 20.0
        cfg = Lidar3DConfig(**yaml_payload).model_dump()

        out = _write_runtime_lidar_profile(
            base_profile_name=cfg["profile_name"],
            overrides={"rotation_rate_hz": cfg["rotation_rate_hz"]},
            output_dir=str(tmp_path),
        )
        with open(out, "r") as f:
            generated = _json.load(f)
        assert generated["profile"]["scanRateBaseHz"] == pytest.approx(20.0, abs=1e-9)

    def test_descriptive_keys_do_not_modify_json(self, tmp_path) -> None:
        """Acceptance: ``horizontal_fov_deg`` etc. validate but DO NOT
        reach Isaac Sim.  This guards the v1.5 follow-up boundary —
        when emitterStates auto-generation lands, this test should fail
        and be rewritten."""
        from marslab.sensors.sensor_spawner import (
            _collect_runtime_lidar_overrides,
            _write_runtime_lidar_profile,
        )

        yaml_payload = _minimal_lidar3d_payload()
        # Edit only descriptive fields — the helper must produce no diff.
        yaml_payload["horizontal_fov_deg"] = 180.0
        yaml_payload["vertical_resolution_deg"] = 0.5
        cfg = Lidar3DConfig(**yaml_payload).model_dump()

        # The collector strips descriptive keys.
        overrides = _collect_runtime_lidar_overrides(
            {
                "horizontal_fov_deg": cfg["horizontal_fov_deg"],
                "vertical_resolution_deg": cfg["vertical_resolution_deg"],
            }
        )
        assert overrides == {}

        # And the writer no-ops, returning the bundled JSON path.
        from marslab.sensors.sensor_spawner import _locate_lidar_profile_json

        bundled = _locate_lidar_profile_json("Example_Rotary")
        out = _write_runtime_lidar_profile("Example_Rotary", overrides, output_dir=str(tmp_path))
        assert out == bundled

    def test_lidar_2d_yaml_overrides_flow(self, tmp_path) -> None:
        """The same runtime-override flow works for the 2D LiDAR block."""
        import json as _json

        from marslab.sensors.sensor_spawner import _write_runtime_lidar_profile

        yaml_payload = _minimal_lidar2d_payload()
        yaml_payload["range_max"] = 10.0
        yaml_payload["rotation_rate_hz"] = 40.0
        cfg = Lidar2DConfig(**yaml_payload).model_dump()

        out = _write_runtime_lidar_profile(
            base_profile_name=cfg["profile_name"],
            overrides={
                "range_max": cfg["range_max"],
                "rotation_rate_hz": cfg["rotation_rate_hz"],
            },
            output_dir=str(tmp_path),
        )
        with open(out, "r") as f:
            generated = _json.load(f)
        assert generated["profile"]["farRangeM"] == pytest.approx(10.0, abs=1e-9)
        assert generated["profile"]["scanRateBaseHz"] == pytest.approx(40.0, abs=1e-9)
