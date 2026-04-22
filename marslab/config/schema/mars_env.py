"""Mars environmental parameters (gravity, atmosphere, solar, albedo, seed).

Split from marslab.config.schema (R2, 2026-04-22). See
delete_later/schema.py for the pre-split original.

R2-A2 (2026-04-22) added ``DynamicAtmosphereConfig`` (plus the
``SunSweepConfig`` / ``TauConstantConfig`` / ``TauRampConfig`` /
``TauSineConfig`` leaves) so the previously-untyped
``mars_env.dynamic_atmosphere`` YAML block gets pydantic validation.
See ``refactoring/_risks.md`` §4.1 for the risk record and
``scripts/phase1/run_stage2.py`` L365-408 for the dict.get() parsing
that this migration replaces.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "DynamicAtmosphereConfig",
    "MarsEnvConfig",
    "SunSweepConfig",
    "TauConstantConfig",
    "TauRampConfig",
    "TauSineConfig",
]


class SunSweepConfig(BaseModel):
    """Azimuth / elevation envelope for the diurnal sun sweep.

    Matches the ``mars_env.dynamic_atmosphere.sun_sweep`` YAML block.
    Consumed by ``compute_sol_sun_position`` via
    ``scripts/phase1/run_stage2.py``.
    """

    start_azimuth_deg: float = Field(
        default=90.0,
        ge=0.0,
        le=360.0,
        description="Sunrise azimuth in degrees (0=N, 90=E, 180=S, 270=W).",
    )
    end_azimuth_deg: float = Field(
        default=270.0,
        ge=0.0,
        le=360.0,
        description="Sunset azimuth in degrees.",
    )
    max_elevation_deg: float = Field(
        default=60.0,
        ge=0.0,
        le=90.0,
        description=(
            "Noon peak elevation in degrees. Jezero crater (18.4 deg N) "
            "peaks near 60 deg at equinox."
        ),
    )


class TauConstantConfig(BaseModel):
    """Parameters for ``tau_profile='constant'``.

    Matches the ``mars_env.dynamic_atmosphere.tau_constant`` YAML block.
    Passed through to ``compute_tau_constant``.
    """

    base_tau: float = Field(
        default=0.3,
        ge=0.0,
        description="Fixed dust optical depth held across the full sol.",
    )


class TauRampConfig(BaseModel):
    """Parameters for ``tau_profile='ramp'``.

    Matches the ``mars_env.dynamic_atmosphere.tau_ramp`` YAML block.
    Models a dust storm onset (start < end) or dissipation
    (start > end). Forwarded to ``compute_tau_ramp``.
    """

    start_tau: float = Field(
        default=0.3,
        ge=0.0,
        description="Tau at time_of_sol_fraction = 0.",
    )
    end_tau: float = Field(
        default=2.0,
        ge=0.0,
        description="Tau at time_of_sol_fraction = 1.",
    )


class TauSineConfig(BaseModel):
    """Parameters for ``tau_profile='sine'``.

    Matches the ``mars_env.dynamic_atmosphere.tau_sine`` YAML block.
    ``tau(t) = base_tau + amplitude * sin(2*pi*t/period_fraction)``,
    clamped to 0. Forwarded to ``compute_tau_sine``.
    """

    base_tau: float = Field(
        default=0.5,
        ge=0.0,
        description="Mean optical depth around which tau oscillates.",
    )
    amplitude: float = Field(
        default=0.3,
        ge=0.0,
        description="Peak-to-mean amplitude of the sine oscillation.",
    )
    period_fraction: float = Field(
        default=1.0,
        gt=0.0,
        description=(
            "Period as fraction of one sol. 1.0 = one oscillation per "
            "sol, 0.5 = two cycles per sol."
        ),
    )


class DynamicAtmosphereConfig(BaseModel):
    """Runtime sun sweep + tau profile for the dynamic atmosphere loop.

    Matches the ``mars_env.dynamic_atmosphere`` YAML block. Consumed by
    ``scripts/phase1/run_stage2.py`` and the phase-3 runtime. Every
    field defaults so existing scenario YAMLs that omit some keys
    continue to validate (backward-compat guarantee).
    """

    enabled: bool = Field(
        default=False,
        description=(
            "Master switch. When False the run-loop stays with the "
            "static sun pose configured by ``mars_env.sun_azimuth_deg`` "
            "and ``mars_env.sun_elevation_deg``."
        ),
    )
    time_scale: float = Field(
        default=200.0,
        gt=0.0,
        description=(
            "Real-time to Mars-sol acceleration factor. 200x makes a "
            "24.66-hour sol elapse in ~7.4 minutes of wall clock."
        ),
    )
    update_interval_frames: int = Field(
        default=10,
        ge=1,
        description="Recompute sun/fog/sky every N rendered frames.",
    )
    sun_sweep: SunSweepConfig = Field(
        default_factory=SunSweepConfig,
        description="Azimuth / elevation envelope for the diurnal sun sweep.",
    )
    tau_profile: Literal["constant", "ramp", "sine"] = Field(
        default="constant",
        description=(
            "Tau temporal profile. See ``marslab.environment.tau_profile`` "
            "for the implementations."
        ),
    )
    tau_constant: TauConstantConfig = Field(
        default_factory=TauConstantConfig,
        description="Parameters used when ``tau_profile='constant'``.",
    )
    tau_ramp: TauRampConfig = Field(
        default_factory=TauRampConfig,
        description="Parameters used when ``tau_profile='ramp'``.",
    )
    tau_sine: TauSineConfig = Field(
        default_factory=TauSineConfig,
        description="Parameters used when ``tau_profile='sine'``.",
    )


class MarsEnvConfig(BaseModel):
    """Mars environmental parameters."""

    gravity: float = Field(default=3.72, ge=3.0, le=4.0, description="Surface gravity in m/s^2")
    atmo_pressure: float = Field(
        default=610, ge=400, le=1200, description="Atmospheric pressure in Pa"
    )
    atmo_density: float = Field(
        default=0.020, ge=0.005, le=0.05, description="Atmospheric density in kg/m^3"
    )
    dust_optical_depth: float = Field(
        default=0.3, ge=0.05, le=6.0, description="Dust optical depth (tau)"
    )
    solar_constant_mean: float = Field(
        default=589, ge=480, le=730, description="Solar constant in W/m^2 at 1.52 AU"
    )
    surface_albedo_range: tuple[float, float] = Field(
        default=(0.10, 0.40), description="Surface albedo min/max"
    )
    surface_temp_mean: float = Field(
        default=-60, ge=-140, le=30, description="Mean surface temperature in Celsius"
    )
    sol_duration_seconds: int = Field(
        default=88642, ge=80000, le=95000, description="Sol duration in seconds"
    )
    dust_opacity_range: tuple[float, float] = Field(
        default=(0.5, 2.0), description="Tau range for domain randomization"
    )
    sun_azimuth_deg: float = Field(
        default=180.0, ge=0.0, le=360.0, description="Sun azimuth in degrees (0=N, 90=E, 180=S)"
    )
    sun_elevation_deg: float = Field(
        default=45.0, ge=0.0, le=90.0, description="Sun elevation above horizon in degrees"
    )
    seed: int = Field(default=42, ge=0)

    # R2-A2 (2026-04-22): structured replacement for the previously
    # untyped ``mars_env.dynamic_atmosphere`` dict. ``default_factory``
    # guarantees backward-compat for any config that omits the block
    # entirely (the Wk1 probe configs do).
    dynamic_atmosphere: DynamicAtmosphereConfig = Field(
        default_factory=DynamicAtmosphereConfig,
        description=(
            "Runtime sun sweep + tau profile. See " "``DynamicAtmosphereConfig`` for nested fields."
        ),
    )

    @model_validator(mode="after")
    def check_ranges(self) -> "MarsEnvConfig":
        """Validate that range tuples are ordered (min < max)."""
        if self.surface_albedo_range[0] >= self.surface_albedo_range[1]:
            raise ValueError(
                f"surface_albedo_range must be (min, max) with min < max, "
                f"got {self.surface_albedo_range}"
            )
        if self.dust_opacity_range[0] >= self.dust_opacity_range[1]:
            raise ValueError(
                f"dust_opacity_range must be (min, max) with min < max, "
                f"got {self.dust_opacity_range}"
            )
        return self
