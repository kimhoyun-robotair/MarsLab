"""Define Mars environment and rendering scenario values.
These pure models are consumed before Kit startup.
Validation rules keep physical and visual inputs bounded."""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from marslab.config.schema.common import (
    FiniteFloat,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    Rgb,
    StrictConfigModel,
)


class SunSweepConfig(StrictConfigModel):
    start_azimuth_deg: FiniteFloat = Field(ge=0.0, le=360.0)
    end_azimuth_deg: FiniteFloat = Field(ge=0.0, le=360.0)
    max_elevation_deg: FiniteFloat = Field(ge=0.0, le=90.0)


class DynamicAtmosphereConfig(StrictConfigModel):
    enabled: bool
    time_scale: PositiveFloat
    sun_sweep: SunSweepConfig
    update_interval_frames: PositiveInt


class MarsEnvConfig(StrictConfigModel):
    gravity: PositiveFloat = Field(ge=3.6, le=3.85)
    dust_optical_depth: PositiveFloat = Field(le=6.0)
    solar_constant: PositiveFloat
    sol_duration_seconds: PositiveFloat
    sun_azimuth_deg: FiniteFloat = Field(ge=0.0, le=360.0)
    sun_elevation_deg: FiniteFloat = Field(ge=0.0, le=90.0)
    physics_dt: PositiveFloat = Field(default=1.0 / 60.0, le=0.1)
    dynamic_atmosphere: DynamicAtmosphereConfig


class FogConfig(StrictConfigModel):
    enabled: bool = True
    color_amount: FiniteFloat = Field(default=1.0, ge=0.0, le=1.0)
    start_height: FiniteFloat = 0.0
    height_falloff: FiniteFloat = Field(default=0.01, ge=0.0)
    height_density_ratio: FiniteFloat = Field(default=0.5, ge=0.0, le=2.0)


class RayTracingConfig(StrictConfigModel):
    antialiasing_op: int = Field(default=3, ge=0, le=5)
    dlss_exec_mode: int = Field(default=1, ge=0, le=3)
    denoiser_indirect_diffuse: bool = True
    denoiser_reflections: bool = True


class PathTracingConfig(StrictConfigModel):
    spp: PositiveInt
    total_spp: PositiveInt
    max_bounces: PositiveInt = Field(le=64)
    denoiser_optix: bool = True


class SkyDomeConfig(StrictConfigModel):
    clear_rgb: Rgb = (0.76, 0.57, 0.35)
    dusty_rgb: Rgb = (0.85, 0.75, 0.60)
    tau_saturation: PositiveFloat = 3.0
    brightness_min: FiniteFloat = Field(default=0.1, ge=0.0, le=1.0)
    brightness_decay: NonNegativeFloat = 0.3
    hdri_clear: str = "mars_sky_clear.png"
    hdri_moderate: str = "mars_sky_moderate.png"
    hdri_dusty: str = "mars_sky_dusty.png"


class RenderingConfig(StrictConfigModel):
    mode: Literal["path_tracing", "ray_tracing"]
    sky_dome_hdri_dir: Path
    sun_intensity_scale: PositiveFloat
    sun_color: Rgb
    sun_angular_diameter_deg: PositiveFloat = Field(le=5.0)
    dome_brightness_scale: PositiveFloat
    fog_density_scale: FiniteFloat = Field(ge=0.0)
    fog_color: Rgb
    sun_prim_path: str = "/World/SunLight"
    dome_prim_path: str = "/World/DomeLight"
    fog: FogConfig = Field(default_factory=FogConfig)
    ray_tracing: RayTracingConfig = Field(default_factory=RayTracingConfig)
    path_tracing: PathTracingConfig
    sky_dome: SkyDomeConfig = Field(default_factory=SkyDomeConfig)

    @model_validator(mode="after")
    def check_colors(self) -> "RenderingConfig":
        if any(channel < 0.0 or channel > 1.0 for channel in (*self.sun_color, *self.fog_color)):
            raise ValueError("rendering RGB channels must be within [0, 1]")
        return self


__all__ = [
    "DynamicAtmosphereConfig",
    "MarsEnvConfig",
    "RenderingConfig",
]
