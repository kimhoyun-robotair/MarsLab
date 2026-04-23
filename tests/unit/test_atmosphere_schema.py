"""Schema tests for ``DynamicAtmosphereConfig`` and its leaf sub-configs (R2-3a).

The pydantic layer was introduced in R2-A2 (2026-04-22) to replace the
previously-untyped ``mars_env.dynamic_atmosphere`` YAML block. These tests
lock down:

* defaults (backward-compat for YAML that omits the block)
* bounded fields (azimuth 0-360, elevation 0-90, positive ``time_scale``)
* ``tau_profile`` literal whitelist
* YAML round-trip via ``MarsLabConfig`` to catch regressions in the root
  aggregator's import path

All tests are offline (no Isaac Sim, no GPU).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from marslab.config.schema import (
    DynamicAtmosphereConfig,
    MarsEnvConfig,
    MarsLabConfig,
    SunSweepConfig,
    TauConstantConfig,
    TauRampConfig,
    TauSineConfig,
)


class TestDefaults:
    """All fields default so pre-R2-A2 YAML configs still validate."""

    def test_dynamic_atmosphere_defaults(self) -> None:
        cfg = DynamicAtmosphereConfig()
        assert cfg.enabled is False
        assert cfg.time_scale == 200.0
        assert cfg.update_interval_frames == 10
        assert cfg.tau_profile == "constant"
        assert isinstance(cfg.sun_sweep, SunSweepConfig)
        assert isinstance(cfg.tau_constant, TauConstantConfig)
        assert isinstance(cfg.tau_ramp, TauRampConfig)
        assert isinstance(cfg.tau_sine, TauSineConfig)

    def test_sun_sweep_defaults(self) -> None:
        cfg = SunSweepConfig()
        assert cfg.start_azimuth_deg == pytest.approx(90.0)
        assert cfg.end_azimuth_deg == pytest.approx(270.0)
        assert cfg.max_elevation_deg == pytest.approx(60.0)

    def test_tau_constant_default(self) -> None:
        assert TauConstantConfig().base_tau == pytest.approx(0.3)

    def test_tau_ramp_defaults(self) -> None:
        cfg = TauRampConfig()
        assert cfg.start_tau == pytest.approx(0.3)
        assert cfg.end_tau == pytest.approx(2.0)

    def test_tau_sine_defaults(self) -> None:
        cfg = TauSineConfig()
        assert cfg.base_tau == pytest.approx(0.5)
        assert cfg.amplitude == pytest.approx(0.3)
        assert cfg.period_fraction == pytest.approx(1.0)


class TestBounds:
    """Bounded fields reject out-of-range values at validation time."""

    def test_sun_sweep_azimuth_bounds(self) -> None:
        with pytest.raises(ValidationError):
            SunSweepConfig(start_azimuth_deg=-1.0)
        with pytest.raises(ValidationError):
            SunSweepConfig(start_azimuth_deg=361.0)
        with pytest.raises(ValidationError):
            SunSweepConfig(end_azimuth_deg=400.0)

    def test_sun_sweep_elevation_bounds(self) -> None:
        with pytest.raises(ValidationError):
            SunSweepConfig(max_elevation_deg=-0.1)
        with pytest.raises(ValidationError):
            SunSweepConfig(max_elevation_deg=91.0)

    def test_time_scale_positive(self) -> None:
        with pytest.raises(ValidationError):
            DynamicAtmosphereConfig(time_scale=0.0)
        with pytest.raises(ValidationError):
            DynamicAtmosphereConfig(time_scale=-5.0)

    def test_update_interval_min_one(self) -> None:
        with pytest.raises(ValidationError):
            DynamicAtmosphereConfig(update_interval_frames=0)

    def test_tau_constant_nonneg(self) -> None:
        with pytest.raises(ValidationError):
            TauConstantConfig(base_tau=-0.01)

    def test_tau_ramp_nonneg(self) -> None:
        with pytest.raises(ValidationError):
            TauRampConfig(start_tau=-0.01, end_tau=0.5)
        with pytest.raises(ValidationError):
            TauRampConfig(start_tau=0.3, end_tau=-0.01)

    def test_tau_sine_bounds(self) -> None:
        with pytest.raises(ValidationError):
            TauSineConfig(base_tau=-0.01)
        with pytest.raises(ValidationError):
            TauSineConfig(amplitude=-0.1)
        with pytest.raises(ValidationError):
            TauSineConfig(period_fraction=0.0)


class TestTauProfileLiteral:
    """The ``tau_profile`` field is a strict Literal; random strings reject."""

    @pytest.mark.parametrize("profile", ["constant", "ramp", "sine"])
    def test_valid_profiles(self, profile: str) -> None:
        cfg = DynamicAtmosphereConfig(tau_profile=profile)
        assert cfg.tau_profile == profile

    def test_unknown_profile_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DynamicAtmosphereConfig(tau_profile="linear")


class TestMarsEnvIntegration:
    """``MarsEnvConfig`` auto-injects a default ``DynamicAtmosphereConfig``."""

    def test_mars_env_has_dynamic_atmosphere_default(self) -> None:
        cfg = MarsEnvConfig()
        assert isinstance(cfg.dynamic_atmosphere, DynamicAtmosphereConfig)
        assert cfg.dynamic_atmosphere.enabled is False

    def test_mars_env_accepts_nested_dict(self) -> None:
        cfg = MarsEnvConfig(
            dynamic_atmosphere={
                "enabled": True,
                "time_scale": 100.0,
                "tau_profile": "sine",
                "tau_sine": {"base_tau": 0.4, "amplitude": 0.2, "period_fraction": 0.5},
                "sun_sweep": {
                    "start_azimuth_deg": 80.0,
                    "end_azimuth_deg": 280.0,
                    "max_elevation_deg": 70.0,
                },
            }
        )
        dyn = cfg.dynamic_atmosphere
        assert dyn.enabled is True
        assert dyn.time_scale == pytest.approx(100.0)
        assert dyn.tau_profile == "sine"
        assert dyn.tau_sine.base_tau == pytest.approx(0.4)
        assert dyn.sun_sweep.max_elevation_deg == pytest.approx(70.0)


class TestYamlRoundtrip:
    """YAML → MarsLabConfig survives without losing fields."""

    def test_roundtrip_via_marslab_config(self, tmp_path) -> None:
        import yaml

        payload = {
            "mars_env": {
                "dust_optical_depth": 0.5,
                "dynamic_atmosphere": {
                    "enabled": True,
                    "tau_profile": "ramp",
                    "tau_ramp": {"start_tau": 0.2, "end_tau": 1.8},
                },
            },
            "terrain": {"source": "procedural", "procedural_preset": "flat"},
        }
        path = tmp_path / "scenario.yaml"
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        config = MarsLabConfig(**data)

        assert config.mars_env.dynamic_atmosphere.enabled is True
        assert config.mars_env.dynamic_atmosphere.tau_profile == "ramp"
        assert config.mars_env.dynamic_atmosphere.tau_ramp.start_tau == pytest.approx(0.2)
        assert config.mars_env.dynamic_atmosphere.tau_ramp.end_tau == pytest.approx(1.8)


class TestImmutability:
    """Pydantic model_copy leaves the source untouched (seed propagation safety)."""

    def test_model_copy_is_independent(self) -> None:
        base = DynamicAtmosphereConfig(time_scale=200.0)
        modified = base.model_copy(update={"time_scale": 50.0})
        assert base.time_scale == pytest.approx(200.0)
        assert modified.time_scale == pytest.approx(50.0)
