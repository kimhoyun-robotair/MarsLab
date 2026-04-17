"""Pure-Python tests for the Nav2 waypoint runner helpers.

DEPRECATED (2026-04-17): ``scripts/eval/nav2_waypoint_runner.py`` and
``configs/nav2/waypoints/`` were removed during Stage 3 cleanup when the
SLAM/Nav2 stack was deferred to a later session.  The original tests
are preserved below (commented) for future reactivation; the live
module applies ``pytest.mark.skip`` so collection continues cleanly.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(
    reason="Nav2 waypoint runner removed in Stage 3 cleanup (2026-04-17).",
)


# --- Original tests (preserved for reactivation) ---
# import math
# from pathlib import Path
#
# import yaml
#
# from scripts.eval.nav2_waypoint_runner import load_waypoints_yaml, yaw_to_quat
#
# REPO_ROOT = Path(__file__).resolve().parents[2]
# WAYPOINTS_DIR = REPO_ROOT / "configs/nav2/waypoints"
# SCENARIOS = ("flat", "rocks", "crater", "canyon", "cave")
#
#
# class TestYawToQuat:
#     def test_zero_yaw_identity(self) -> None:
#         qx, qy, qz, qw = yaw_to_quat(0.0)
#         assert (qx, qy, qz) == (0.0, 0.0, 0.0)
#         assert qw == pytest.approx(1.0)
#
#     def test_ninety_deg_yaw_half_root_two(self) -> None:
#         qx, qy, qz, qw = yaw_to_quat(math.pi / 2)
#         assert qx == 0.0
#         assert qy == 0.0
#         assert qz == pytest.approx(math.sqrt(0.5))
#         assert qw == pytest.approx(math.sqrt(0.5))
#
#     def test_quat_norm_is_unit(self) -> None:
#         for yaw in (0.1, 1.2, -2.3, math.pi):
#             qx, qy, qz, qw = yaw_to_quat(yaw)
#             norm = math.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
#             assert norm == pytest.approx(1.0, abs=1e-9)
#
#
# class TestLoadWaypointsYaml:
#     @pytest.mark.parametrize("scenario", SCENARIOS)
#     def test_shipped_waypoints_parse(self, scenario: str) -> None:
#         poses = load_waypoints_yaml(WAYPOINTS_DIR / f"{scenario}.yaml")
#         assert len(poses) >= 2
#         for p in poses:
#             assert "xy" in p and len(p["xy"]) == 2
#             assert isinstance(float(p["xy"][0]), float)
#             assert isinstance(float(p["xy"][1]), float)
#             # yaw_deg is optional but defaults to 0.0 in the runner.
#             if "yaw_deg" in p:
#                 assert -360.0 <= float(p["yaw_deg"]) <= 360.0
#
#     def test_rejects_missing_top_level_poses(self, tmp_path: Path) -> None:
#         bad = tmp_path / "bad.yaml"
#         bad.write_text(yaml.safe_dump({"not_poses": []}))
#         with pytest.raises(ValueError, match="'poses'"):
#             load_waypoints_yaml(bad)
#
#     def test_rejects_empty_pose_list(self, tmp_path: Path) -> None:
#         bad = tmp_path / "empty.yaml"
#         bad.write_text(yaml.safe_dump({"poses": []}))
#         with pytest.raises(ValueError, match="non-empty"):
#             load_waypoints_yaml(bad)
