"""Schema tests for R2-4a drive-API required fields on SkidSteerDriveConfig."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from marslab.config.schema import SkidSteerDriveConfig


def _baseline_kwargs(**overrides) -> dict:
    """Minimum keyword set to instantiate ``SkidSteerDriveConfig``.

    Mirrors the values in ``configs/robots/rover_m2020.yaml`` so the test
    tracks the runtime rover tuning.
    """
    base = {
        "drive_damping": 1000.0,
        "steer_stiffness": 50000.0,
        "steer_damping": 5000.0,
        "drive_max_force": 1000000.0,
        "steer_max_force": 100000.0,
        "suspension_damping": 50.0,
        "drive_type": "acceleration",
    }
    base.update(overrides)
    return base


class TestRequiredness:
    """Every new R2-4a field is required — no Python default fallback."""

    @pytest.mark.parametrize(
        "missing_key",
        ["drive_max_force", "steer_max_force", "suspension_damping", "drive_type"],
    )
    def test_omitting_field_rejects(self, missing_key: str) -> None:
        kwargs = _baseline_kwargs()
        kwargs.pop(missing_key)
        with pytest.raises(ValidationError):
            SkidSteerDriveConfig(**kwargs)


class TestBounds:
    """Numeric fields enforce PhysX-safe ranges."""

    def test_drive_max_force_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SkidSteerDriveConfig(**_baseline_kwargs(drive_max_force=0.0))
        with pytest.raises(ValidationError):
            SkidSteerDriveConfig(**_baseline_kwargs(drive_max_force=-1.0))

    def test_steer_max_force_must_be_positive(self) -> None:
        with pytest.raises(ValidationError):
            SkidSteerDriveConfig(**_baseline_kwargs(steer_max_force=0.0))
        with pytest.raises(ValidationError):
            SkidSteerDriveConfig(**_baseline_kwargs(steer_max_force=-0.1))

    def test_suspension_damping_allows_zero(self) -> None:
        """``suspension_damping=0`` leaves suspension undamped — legal."""
        cfg = SkidSteerDriveConfig(**_baseline_kwargs(suspension_damping=0.0))
        assert cfg.suspension_damping == pytest.approx(0.0)

    def test_suspension_damping_rejects_negative(self) -> None:
        with pytest.raises(ValidationError):
            SkidSteerDriveConfig(**_baseline_kwargs(suspension_damping=-0.01))


class TestDriveTypeLiteral:
    """``drive_type`` is a strict ``Literal[...]``; random strings reject."""

    @pytest.mark.parametrize("drive_type", ["acceleration", "force"])
    def test_valid_drive_types(self, drive_type: str) -> None:
        cfg = SkidSteerDriveConfig(**_baseline_kwargs(drive_type=drive_type))
        assert cfg.drive_type == drive_type

    def test_unknown_drive_type_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SkidSteerDriveConfig(**_baseline_kwargs(drive_type="velocity"))
        with pytest.raises(ValidationError):
            SkidSteerDriveConfig(**_baseline_kwargs(drive_type=""))


class TestRoverM2020Parity:
    """Values in the runtime rover YAML load cleanly and round-trip."""

    def test_rover_m2020_values_accepted(self) -> None:
        """``configs/robots/rover_m2020.yaml`` literal values must validate."""
        cfg = SkidSteerDriveConfig(**_baseline_kwargs())
        assert cfg.drive_max_force == pytest.approx(1000000.0)
        assert cfg.steer_max_force == pytest.approx(100000.0)
        assert cfg.suspension_damping == pytest.approx(50.0)
        assert cfg.drive_type == "acceleration"


class TestDriveApiSetupDictContract:
    """``drive_api_setup`` now reads these keys with ``[]`` (no fallback).

    The test reads the source rather than invoking the function (Isaac
    Sim would be required). Any future regression that re-introduces a
    ``.get(key, <literal>)`` fallback for one of the four R2-4a keys
    fails this test.
    """

    def test_no_fallback_for_required_keys(self) -> None:
        from pathlib import Path

        source_path = (
            Path(__file__).resolve().parents[2] / "marslab" / "robots" / "drive_api_setup.py"
        )
        source = source_path.read_text(encoding="utf-8")
        for key in (
            "drive_max_force",
            "steer_max_force",
            "suspension_damping",
            "drive_type",
            "drive_damping",
            "steer_stiffness",
            "steer_damping",
        ):
            assert f'control_cfg.get("{key}"' not in source, (
                f"drive_api_setup.py must not use .get({key!r}, <literal>) — "
                "R2-4a promoted these to required SkidSteerDriveConfig fields."
            )
            assert f'control_cfg["{key}"]' in source, (
                f"drive_api_setup.py must read {key!r} via control_cfg[{key!r}] "
                "so a missing YAML key raises KeyError immediately."
            )
