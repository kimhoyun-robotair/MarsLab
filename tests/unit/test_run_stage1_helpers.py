"""Unit tests for the pure helpers in ``scripts/phase1/run_stage1.py``.

These tests intentionally exercise only the Isaac-Sim-free helper layer:
``load_config``, ``clamp``, ``clamp_twist``, ``skid_steer_targets``,
``resolve_joint_indices``, and ``rpy_to_quat``. The Isaac Sim integration paths in ``main()``
are exercised by the Stage 1 smoke run on the user's workstation.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path
from typing import Any

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_STAGE1_PATH = REPO_ROOT / "scripts" / "phase1" / "run_stage1.py"


def _load_run_stage1_module() -> Any:
    """Load run_stage1.py as a module without executing ``main``.

    The top-level module imports only ``numpy`` and ``yaml``; Isaac Sim is
    lazily imported inside ``main()``, so importing the file in a plain
    Python interpreter is safe.
    """
    spec = importlib.util.spec_from_file_location("run_stage1", RUN_STAGE1_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["run_stage1"] = module
    spec.loader.exec_module(module)
    return module


run_stage1 = _load_run_stage1_module()


# --- clamp / clamp_twist ------------------------------------------------


def test_clamp_inside_range_returns_value():
    assert run_stage1.clamp(0.3, -1.0, 1.0) == pytest.approx(0.3)


def test_clamp_below_low_returns_low():
    assert run_stage1.clamp(-5.0, -1.0, 1.0) == pytest.approx(-1.0)


def test_clamp_above_high_returns_high():
    assert run_stage1.clamp(5.0, -1.0, 1.0) == pytest.approx(1.0)


def test_clamp_inverted_bounds_raises():
    with pytest.raises(ValueError):
        run_stage1.clamp(0.0, 1.0, -1.0)


def test_clamp_twist_symmetric_limits():
    v, w = run_stage1.clamp_twist(2.0, -3.0, 0.5, 0.5)
    assert v == pytest.approx(0.5)
    assert w == pytest.approx(-0.5)


# --- skid_steer_targets -------------------------------------------------


def test_skid_steer_forward_only():
    targets = run_stage1.skid_steer_targets(v=0.5, w=0.0, wheel_track=2.9, wheel_radius=0.2667)
    assert targets.shape == (6,)
    assert targets.dtype == np.float32
    expected = 0.5 / 0.2667
    np.testing.assert_allclose(targets, np.full(6, expected), rtol=1e-5)


def test_skid_steer_in_place_rotation_is_antisymmetric():
    targets = run_stage1.skid_steer_targets(v=0.0, w=0.4, wheel_track=2.0, wheel_radius=0.25)
    # left 3 should be negative, right 3 should be positive, equal magnitudes
    assert np.all(targets[:3] < 0.0)
    assert np.all(targets[3:] > 0.0)
    np.testing.assert_allclose(targets[:3], -targets[3:], rtol=1e-5)


def test_skid_steer_reverse():
    targets = run_stage1.skid_steer_targets(v=-0.3, w=0.0, wheel_track=2.9, wheel_radius=0.2667)
    expected = -0.3 / 0.2667
    np.testing.assert_allclose(targets, np.full(6, expected), rtol=1e-5)


def test_skid_steer_left_right_split_equations():
    v, w = 0.2, 0.1
    track, radius = 2.9, 0.2667
    targets = run_stage1.skid_steer_targets(v=v, w=w, wheel_track=track, wheel_radius=radius)
    expected_l = (v - w * track / 2.0) / radius
    expected_r = (v + w * track / 2.0) / radius
    np.testing.assert_allclose(targets[:3], np.full(3, expected_l), rtol=1e-5)
    np.testing.assert_allclose(targets[3:], np.full(3, expected_r), rtol=1e-5)


def test_skid_steer_invalid_radius_raises():
    with pytest.raises(ValueError, match="wheel_radius"):
        run_stage1.skid_steer_targets(v=0.1, w=0.0, wheel_track=2.9, wheel_radius=0.0)


def test_skid_steer_invalid_track_raises():
    with pytest.raises(ValueError, match="wheel_track"):
        run_stage1.skid_steer_targets(v=0.1, w=0.0, wheel_track=-1.0, wheel_radius=0.25)


# --- resolve_joint_indices ----------------------------------------------


def test_resolve_joint_indices_success():
    dof_names = ["A", "LF_DRIVE", "B", "RR_DRIVE", "LM_DRIVE"]
    indices = run_stage1.resolve_joint_indices(dof_names, ["LF_DRIVE", "RR_DRIVE"])
    assert indices == [1, 3]


def test_resolve_joint_indices_preserves_requested_order():
    dof_names = ["X", "Y", "Z"]
    assert run_stage1.resolve_joint_indices(dof_names, ["Z", "X"]) == [2, 0]


def test_resolve_joint_indices_missing_raises():
    with pytest.raises(ValueError, match="not present"):
        run_stage1.resolve_joint_indices(["A", "B"], ["A", "MISSING"])


# --- load_config --------------------------------------------------------


VALID_CONFIG = textwrap.dedent("""
    physics:
      gravity: 9.81
      time_step: 0.01667
      rendering_dt: 0.01667
    rover:
      usd_path: "assets/robots/rover/m2020.usd"
      prim_path: "/World/Rover"
      spawn_position: [0.0, 0.0, 1.0]
    ros2:
      namespace: "rover"
      topics:
        cmd_vel: "cmd_vel"
      rates:
        imu: 100
    sensors:
      camera:
        parent_link: "Body_Chassis"
    control:
      wheel_radius: 0.2667
      wheel_track: 2.9
      max_linear_velocity: 0.5
      max_angular_velocity: 0.5
      drive_joint_names:
        - LF_DRIVE
        - LM_DRIVE
        - LR_DRIVE
        - RF_DRIVE
        - RM_DRIVE
        - RR_DRIVE
      steer_joint_names:
        - LF_STEER
        - LR_STEER
        - RF_STEER
        - RR_STEER
    """).strip()


def _write(tmp_path, body: str) -> str:
    path = tmp_path / "phase1.yaml"
    path.write_text(body, encoding="utf-8")
    return str(path)


def test_load_config_success(tmp_path):
    cfg = run_stage1.load_config(_write(tmp_path, VALID_CONFIG))
    assert cfg["control"]["wheel_radius"] == pytest.approx(0.2667)
    assert len(cfg["control"]["drive_joint_names"]) == 6
    assert len(cfg["control"]["steer_joint_names"]) == 4


def test_load_config_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        run_stage1.load_config("/nonexistent/phase1.yaml")


def test_load_config_missing_section_raises(tmp_path):
    body = VALID_CONFIG.replace("control:", "other:")
    with pytest.raises(ValueError, match="control"):
        run_stage1.load_config(_write(tmp_path, body))


def _drop_line(body: str, needle: str) -> str:
    lines = [ln for ln in body.splitlines() if needle not in ln]
    return "\n".join(lines) + "\n"


def test_load_config_wrong_drive_joint_count_raises(tmp_path):
    body = _drop_line(VALID_CONFIG, "RR_DRIVE")
    with pytest.raises(ValueError, match="drive_joint_names"):
        run_stage1.load_config(_write(tmp_path, body))


def test_load_config_wrong_steer_joint_count_raises(tmp_path):
    body = _drop_line(VALID_CONFIG, "RR_STEER")
    with pytest.raises(ValueError, match="steer_joint_names"):
        run_stage1.load_config(_write(tmp_path, body))


def test_load_config_non_positive_radius_raises(tmp_path):
    body = VALID_CONFIG.replace("wheel_radius: 0.2667", "wheel_radius: 0")
    with pytest.raises(ValueError, match="wheel_radius"):
        run_stage1.load_config(_write(tmp_path, body))


# --- rpy_to_quat ----------------------------------------------------------


def test_rpy_to_quat_identity():
    """RPY = (0, 0, 0) → identity quaternion (1, 0, 0, 0)."""
    w, x, y, z = run_stage1.rpy_to_quat(0.0, 0.0, 0.0)
    np.testing.assert_allclose([w, x, y, z], [1.0, 0.0, 0.0, 0.0], atol=1e-12)


def test_rpy_to_quat_90deg_yaw():
    """RPY = (0, 0, pi/2) → quat (cos(pi/4), 0, 0, sin(pi/4))."""
    w, x, y, z = run_stage1.rpy_to_quat(0.0, 0.0, np.pi / 2.0)
    expected_w = np.cos(np.pi / 4.0)
    expected_z = np.sin(np.pi / 4.0)
    np.testing.assert_allclose([w, x, y, z], [expected_w, 0.0, 0.0, expected_z], atol=1e-12)


def test_rpy_to_quat_180deg_roll():
    """RPY = (pi, 0, 0) → quat (0, 1, 0, 0)."""
    w, x, y, z = run_stage1.rpy_to_quat(np.pi, 0.0, 0.0)
    np.testing.assert_allclose([w, x, y, z], [0.0, 1.0, 0.0, 0.0], atol=1e-12)
