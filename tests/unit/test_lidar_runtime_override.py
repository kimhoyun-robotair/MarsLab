"""Sprint Day 3 Task H1 (2026-04-25): runtime LiDAR JSON override.

These tests cover the helper added to
:mod:`marslab.sensors.sensor_spawner` that materialises a runtime JSON
copy of an Isaac Sim bundled LiDAR profile with the YAML-supplied
``range_min`` / ``range_max`` / ``rotation_rate_hz`` numerics patched
in.  Without this layer the YAML numerics validate via pydantic and
then never reach Isaac Sim at runtime — Reviewer 2 flagged this as
high-severity finding H1 in ``~/MarsLab/tmp/day2_code_review.md``.

Acceptance criteria covered here:

1. The helper round-trips ``range_min: 0.5 -> profile.nearRangeM: 0.5``,
   ``range_max -> profile.farRangeM``, ``rotation_rate_hz -> profile.scanRateBaseHz``
   exactly (assert_almost_equal).
2. The bundled JSON file is located under either
   ``omni.sensors.nv.common`` (Example_Rotary*) or
   ``isaacsim.sensors.rtx`` (vendor profiles).
3. A missing profile name raises ``FileNotFoundError`` with both
   search globs in the message.
4. Hash-based filename: identical (base, overrides) pairs produce the
   same generated path, so regeneration is idempotent.
5. Empty overrides return the bundled JSON path directly (no copy).
6. Descriptive-only YAML keys (``horizontal_fov_deg`` etc.) are NOT
   patched into the JSON — they pass through ``_collect_runtime_lidar_overrides``
   without effect.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from marslab.sensors.sensor_spawner import (
    _collect_runtime_lidar_overrides,
    _hash_runtime_overrides,
    _locate_lidar_profile_json,
    _write_runtime_lidar_profile,
)


# ---------------------------------------------------------------------------
# _locate_lidar_profile_json
# ---------------------------------------------------------------------------
class TestLocateLidarProfileJson:
    """Acceptance criterion 2: bundled profiles are found on disk."""

    def test_example_rotary_found(self) -> None:
        path = _locate_lidar_profile_json("Example_Rotary")
        assert os.path.isfile(path)
        assert path.endswith("Example_Rotary.json")
        # Must come from the omni.sensors.nv.common extscache dir.
        assert "omni.sensors.nv.common" in path

    def test_example_rotary_2d_found(self) -> None:
        path = _locate_lidar_profile_json("Example_Rotary_2D")
        assert os.path.isfile(path)
        assert path.endswith("Example_Rotary_2D.json")

    def test_velodyne_vls128_found_in_rtx_tree(self) -> None:
        """Vendor profiles live under isaacsim.sensors.rtx/data/lidar_configs.

        ``Velodyne_VLS128`` is shipped in BOTH search trees but the
        nv.common copy wins because it is searched first; either match
        is a valid acceptance.
        """
        path = _locate_lidar_profile_json("Velodyne_VLS128")
        assert os.path.isfile(path)
        assert "Velodyne_VLS128.json" in os.path.basename(path)

    def test_missing_profile_raises_with_both_globs(self) -> None:
        with pytest.raises(FileNotFoundError) as excinfo:
            _locate_lidar_profile_json("DoesNotExist_Profile_xyz")
        msg = str(excinfo.value)
        # Both search locations must appear in the message so the
        # operator can verify against the live install.
        assert "omni.sensors.nv.common" in msg
        assert "isaacsim.sensors.rtx" in msg

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            _locate_lidar_profile_json("")

    def test_absolute_existing_path_short_circuits(self, tmp_path: Path) -> None:
        """If the caller already passed a full path (escape-hatch flow),
        return it unchanged."""
        custom = tmp_path / "custom.json"
        custom.write_text("{}")
        result = _locate_lidar_profile_json(str(custom))
        assert result == str(custom)


# ---------------------------------------------------------------------------
# _collect_runtime_lidar_overrides
# ---------------------------------------------------------------------------
class TestCollectRuntimeOverrides:
    """Acceptance criterion 6: only the 3 runtime-overridable keys flow."""

    def test_collects_all_three_keys(self) -> None:
        cfg = {
            "range_min": 0.5,
            "range_max": 50.0,
            "rotation_rate_hz": 20.0,
            "local_translation": [0.0, 0.0, 0.0],
        }
        out = _collect_runtime_lidar_overrides(cfg)
        assert out == {"range_min": 0.5, "range_max": 50.0, "rotation_rate_hz": 20.0}

    def test_descriptive_keys_ignored(self) -> None:
        """``horizontal_fov_deg`` etc. are documentation-only — they must
        NOT make it into the override dict."""
        cfg = {
            "horizontal_fov_deg": 270.0,
            "vertical_fov_deg": 30.0,
            "horizontal_resolution_deg": 0.25,
            "vertical_resolution_deg": 1.875,
            "rotation_rate_hz": 10.0,
        }
        out = _collect_runtime_lidar_overrides(cfg)
        assert out == {"rotation_rate_hz": 10.0}

    def test_none_values_filtered(self) -> None:
        cfg = {"range_min": None, "range_max": 50.0, "rotation_rate_hz": None}
        out = _collect_runtime_lidar_overrides(cfg)
        assert out == {"range_max": 50.0}

    def test_empty_cfg_returns_empty(self) -> None:
        assert _collect_runtime_lidar_overrides({}) == {}


# ---------------------------------------------------------------------------
# _hash_runtime_overrides — reproducibility (Acceptance #4)
# ---------------------------------------------------------------------------
class TestHashRuntimeOverrides:
    def test_same_inputs_same_hash(self) -> None:
        h1 = _hash_runtime_overrides("Example_Rotary", {"range_max": 50.0})
        h2 = _hash_runtime_overrides("Example_Rotary", {"range_max": 50.0})
        assert h1 == h2

    def test_different_overrides_different_hash(self) -> None:
        h1 = _hash_runtime_overrides("Example_Rotary", {"range_max": 50.0})
        h2 = _hash_runtime_overrides("Example_Rotary", {"range_max": 100.0})
        assert h1 != h2

    def test_different_base_different_hash(self) -> None:
        h1 = _hash_runtime_overrides("Example_Rotary", {"range_max": 50.0})
        h2 = _hash_runtime_overrides("Example_Rotary_2D", {"range_max": 50.0})
        assert h1 != h2

    def test_dict_ordering_does_not_change_hash(self) -> None:
        h1 = _hash_runtime_overrides("Example_Rotary", {"range_min": 0.5, "range_max": 50.0})
        h2 = _hash_runtime_overrides("Example_Rotary", {"range_max": 50.0, "range_min": 0.5})
        assert h1 == h2


# ---------------------------------------------------------------------------
# _write_runtime_lidar_profile — Acceptance #1, #5
# ---------------------------------------------------------------------------
class TestWriteRuntimeLidarProfile:
    """Acceptance #1: round-trip ``range_max: 0.5 -> nearRangeM: 0.5``."""

    def test_round_trip_range_min(self, tmp_path: Path) -> None:
        out_path = _write_runtime_lidar_profile(
            base_profile_name="Example_Rotary",
            overrides={"range_min": 0.5},
            output_dir=str(tmp_path),
        )
        assert os.path.isfile(out_path)
        with open(out_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        assert payload["profile"]["nearRangeM"] == pytest.approx(0.5, abs=1e-9)

    def test_round_trip_range_max(self, tmp_path: Path) -> None:
        out_path = _write_runtime_lidar_profile(
            base_profile_name="Example_Rotary",
            overrides={"range_max": 50.0},
            output_dir=str(tmp_path),
        )
        with open(out_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        assert payload["profile"]["farRangeM"] == pytest.approx(50.0, abs=1e-9)

    def test_round_trip_rotation_rate(self, tmp_path: Path) -> None:
        out_path = _write_runtime_lidar_profile(
            base_profile_name="Example_Rotary",
            overrides={"rotation_rate_hz": 20.0},
            output_dir=str(tmp_path),
        )
        with open(out_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        assert payload["profile"]["scanRateBaseHz"] == pytest.approx(20.0, abs=1e-9)

    def test_round_trip_all_three(self, tmp_path: Path) -> None:
        out_path = _write_runtime_lidar_profile(
            base_profile_name="Example_Rotary",
            overrides={
                "range_min": 0.3,
                "range_max": 75.0,
                "rotation_rate_hz": 15.0,
            },
            output_dir=str(tmp_path),
        )
        with open(out_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        prof = payload["profile"]
        assert prof["nearRangeM"] == pytest.approx(0.3, abs=1e-9)
        assert prof["farRangeM"] == pytest.approx(75.0, abs=1e-9)
        assert prof["scanRateBaseHz"] == pytest.approx(15.0, abs=1e-9)

    def test_other_profile_keys_preserved(self, tmp_path: Path) -> None:
        """Sanity check: emitter tables, intensity processing, etc. must
        survive the override step untouched."""
        out_path = _write_runtime_lidar_profile(
            base_profile_name="Example_Rotary",
            overrides={"range_max": 50.0},
            output_dir=str(tmp_path),
        )
        with open(out_path, "r", encoding="utf-8") as f:
            generated = json.load(f)

        base_path = _locate_lidar_profile_json("Example_Rotary")
        with open(base_path, "r", encoding="utf-8") as f:
            base = json.load(f)

        # Top-level keys identical
        assert set(generated.keys()) == set(base.keys())
        # Per-emitter table preserved
        assert generated["profile"]["emitterStates"] == base["profile"]["emitterStates"]
        # Untouched scalar preserved
        assert generated["profile"]["nearRangeM"] == base["profile"]["nearRangeM"]
        # Touched scalar applied
        assert generated["profile"]["farRangeM"] == 50.0

    def test_2d_profile_round_trip(self, tmp_path: Path) -> None:
        out_path = _write_runtime_lidar_profile(
            base_profile_name="Example_Rotary_2D",
            overrides={"rotation_rate_hz": 40.0, "range_max": 10.0},
            output_dir=str(tmp_path),
        )
        with open(out_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        assert payload["profile"]["scanRateBaseHz"] == pytest.approx(40.0, abs=1e-9)
        assert payload["profile"]["farRangeM"] == pytest.approx(10.0, abs=1e-9)

    def test_idempotent_filename(self, tmp_path: Path) -> None:
        """Acceptance #4: identical overrides produce the same filename."""
        p1 = _write_runtime_lidar_profile(
            "Example_Rotary", {"range_max": 50.0}, output_dir=str(tmp_path)
        )
        p2 = _write_runtime_lidar_profile(
            "Example_Rotary", {"range_max": 50.0}, output_dir=str(tmp_path)
        )
        assert p1 == p2

    def test_different_overrides_different_filename(self, tmp_path: Path) -> None:
        p1 = _write_runtime_lidar_profile(
            "Example_Rotary", {"range_max": 50.0}, output_dir=str(tmp_path)
        )
        p2 = _write_runtime_lidar_profile(
            "Example_Rotary", {"range_max": 100.0}, output_dir=str(tmp_path)
        )
        assert p1 != p2

    def test_empty_overrides_returns_bundled_path(self, tmp_path: Path) -> None:
        """Acceptance #5: no overrides -> point at the bundled JSON directly."""
        bundled = _locate_lidar_profile_json("Example_Rotary")
        out = _write_runtime_lidar_profile("Example_Rotary", {}, output_dir=str(tmp_path))
        assert out == bundled

    def test_descriptive_only_overrides_returns_bundled_path(self, tmp_path: Path) -> None:
        """Acceptance #6: passing only descriptive keys (e.g. fov) is
        treated as no-op — those keys are not in the runtime-overridable
        whitelist, so the helper returns the bundled JSON unchanged."""
        bundled = _locate_lidar_profile_json("Example_Rotary")
        out = _write_runtime_lidar_profile(
            "Example_Rotary",
            {"horizontal_fov_deg": 270.0, "vertical_resolution_deg": 1.0},
            output_dir=str(tmp_path),
        )
        assert out == bundled

    def test_filename_contains_base_and_hash(self, tmp_path: Path) -> None:
        out = _write_runtime_lidar_profile(
            "Example_Rotary", {"range_max": 50.0}, output_dir=str(tmp_path)
        )
        basename = os.path.basename(out)
        assert basename.startswith("marslab_Example_Rotary_")
        assert basename.endswith(".json")
        # Hash segment is 16 hex chars per the helper.
        hash_segment = basename[len("marslab_Example_Rotary_") : -len(".json")]
        assert len(hash_segment) == 16
        assert all(c in "0123456789abcdef" for c in hash_segment)

    def test_missing_base_profile_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            _write_runtime_lidar_profile(
                "DoesNotExist_xyz",
                {"range_max": 50.0},
                output_dir=str(tmp_path),
            )

    def test_default_output_dir_under_marslab_tmp(self) -> None:
        """Acceptance: per user policy, generated files land under
        ``~/MarsLab/tmp/runtime_lidar_profiles`` (NOT ``/tmp``)."""
        out = _write_runtime_lidar_profile("Example_Rotary", {"range_max": 50.0})
        marslab_tmp = os.path.expanduser("~/MarsLab/tmp/runtime_lidar_profiles")
        assert out.startswith(marslab_tmp)
        assert os.path.isfile(out)
