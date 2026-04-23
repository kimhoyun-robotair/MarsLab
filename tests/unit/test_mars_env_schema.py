"""Module-focused tests for ``marslab.config.schema.mars_env``.

R8-5 (2026-04-23) added this file to exercise ``MarsEnvConfig`` at the
domain-module level (field existence, invalid tau rejection, default
gravity, YAML round-trip) independently of the aggregated
``test_config_schema.py`` suite. Coverage here intentionally does not
duplicate the existing atmosphere / dynamic-atmosphere tests — it
focuses on the leaf ``MarsEnvConfig`` invariants that matter for the
Mars physics guarantees called out in CLAUDE.md Testing Requirements.
"""

from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from marslab.config.schema import MarsEnvConfig, MarsLabConfig
from marslab.config.schema.mars_env import DynamicAtmosphereConfig


class TestFieldExistence:
    """Every declared ``MarsEnvConfig`` field must surface on the model."""

    def test_all_expected_fields_present(self) -> None:
        expected = {
            "gravity",
            "atmo_pressure",
            "atmo_density",
            "dust_optical_depth",
            "solar_constant_mean",
            "surface_albedo_range",
            "surface_temp_mean",
            "sol_duration_seconds",
            "dust_opacity_range",
            "sun_azimuth_deg",
            "sun_elevation_deg",
            "seed",
            "dynamic_atmosphere",
        }
        got = set(MarsEnvConfig.model_fields.keys())
        missing = expected - got
        assert not missing, f"MarsEnvConfig missing expected fields: {missing}"

    def test_dynamic_atmosphere_is_nested_model(self) -> None:
        """``dynamic_atmosphere`` default-factory must yield the nested type."""
        cfg = MarsEnvConfig()
        assert isinstance(cfg.dynamic_atmosphere, DynamicAtmosphereConfig)


class TestDefaultGravity:
    """Mars gravity default is a load-bearing number — lock it down."""

    def test_default_gravity_exactly_3_72(self) -> None:
        """``MarsEnvConfig().gravity`` must equal 3.72 m/s^2."""
        assert MarsEnvConfig().gravity == pytest.approx(3.72, abs=1e-9)

    def test_gravity_lower_bound_inclusive(self) -> None:
        """``ge=3.0`` is inclusive — 3.0 must validate."""
        assert MarsEnvConfig(gravity=3.0).gravity == 3.0

    def test_gravity_upper_bound_inclusive(self) -> None:
        """``le=4.0`` is inclusive — 4.0 must validate."""
        assert MarsEnvConfig(gravity=4.0).gravity == 4.0


class TestInvalidTau:
    """``dust_optical_depth`` aka tau must reject non-physical values."""

    def test_negative_tau_rejected(self) -> None:
        with pytest.raises(ValidationError):
            MarsEnvConfig(dust_optical_depth=-0.1)

    def test_tau_below_minimum_rejected(self) -> None:
        """Schema floor is 0.05 (clear-sky rounding)."""
        with pytest.raises(ValidationError):
            MarsEnvConfig(dust_optical_depth=0.0)

    def test_tau_above_storm_ceiling_rejected(self) -> None:
        """``le=6.0`` — a tau of 10 (hypothetical global storm) is rejected."""
        with pytest.raises(ValidationError):
            MarsEnvConfig(dust_optical_depth=10.0)

    def test_tau_within_range_accepted(self) -> None:
        cfg = MarsEnvConfig(dust_optical_depth=1.5)
        assert cfg.dust_optical_depth == 1.5


class TestYamlRoundtrip:
    """YAML load -> MarsEnvConfig -> dict -> yaml.dump -> reload must be stable."""

    def test_mars_env_roundtrip_preserves_defaults(self) -> None:
        """model_dump followed by yaml.safe_dump then yaml.safe_load must
        reconstruct an equivalent config."""
        original = MarsEnvConfig()
        dumped = original.model_dump()
        serialized = yaml.safe_dump(dumped)
        reloaded = yaml.safe_load(serialized)
        rebuilt = MarsEnvConfig(**reloaded)
        assert rebuilt.gravity == original.gravity
        assert rebuilt.dust_optical_depth == original.dust_optical_depth
        assert rebuilt.seed == original.seed

    def test_mars_env_embedded_in_marslab_config_roundtrip(self) -> None:
        """Round-trip through the root aggregator must not drop fields."""
        cfg = MarsLabConfig(
            terrain={"source": "procedural", "procedural_preset": "flat"},
        )
        data = cfg.model_dump()
        yaml_blob = yaml.safe_dump(data)
        rebuilt = MarsLabConfig(**yaml_safe_load_non_none(yaml_blob))
        assert rebuilt.mars_env.gravity == cfg.mars_env.gravity
        assert (
            rebuilt.mars_env.dynamic_atmosphere.enabled == cfg.mars_env.dynamic_atmosphere.enabled
        )


def yaml_safe_load_non_none(blob: str) -> dict:
    """Helper: yaml.safe_load but guarantees a dict (empty if None)."""
    data = yaml.safe_load(blob)
    return data if isinstance(data, dict) else {}
