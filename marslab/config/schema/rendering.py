"""Rendering schema: RTX mode, resolution, sun/dome/fog parameters.

Leaf model -- no cross-domain references.

The rendering literals previously hardcoded in the ``rendering/``
consumers are surfaced here so all configurable parameters live in
YAML:

- ``sun_prim_path`` / ``dome_prim_path`` -- prim path literals from
  ``sun_renderer.py`` and ``sky_renderer.py``.
- ``antialiasing_op`` / ``dlss_exec_mode`` / ``denoiser_*`` -- RTX
  post-processing knobs from ``render_settings.py``.
- ``fog_*`` -- five fog literals from ``atmosphere_fog.py``.

These flat fields are re-grouped into four nested sub-configs:
``FogConfig``, ``RayTracingConfig``, ``PathTracingConfig``, and
``SkyDomeConfig``.  A pre-validator (``_migrate_flat_to_nested``)
accepts the legacy flat keys so existing YAML files do not have to
change.
"""

from typing import Any, Literal, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "FogConfig",
    "PathTracingConfig",
    "RayTracingConfig",
    "RenderingConfig",
    "SkyDomeConfig",
]


# Every BaseModel in this module declares ``extra="forbid"`` so unknown
# keys in ``rendering:`` YAML blocks fail loudly instead of being
# silently dropped.  See the sibling note in
# ``marslab/config/schema/mars_env.py`` for the full rationale.
# ``RenderingConfig`` keeps its legacy flat-to-nested migrator
# (``_migrate_flat_to_nested``) which pops flat keys from the input dict
# BEFORE forbid-validation runs, so legacy YAMLs keep loading.


class FogConfig(BaseModel):
    """RTX atmosphere-fog knobs consumed by ``atmosphere_fog.py``.

    Migrated from the flat ``fog_*`` fields previously declared on
    ``RenderingConfig``.
    """

    model_config = ConfigDict(extra="forbid")

    enabled: bool = Field(
        default=True, description="Master switch written to ``/rtx/fog/enabled``."
    )
    color_amount: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Value written to ``/rtx/fog/fogColorAmount``.",
    )
    start_height: float = Field(
        default=0.0,
        description=(
            "World-Z (metres) below which fog density is full strength. "
            "Written to ``/rtx/fog/fogStartHeight``."
        ),
    )
    height_falloff: float = Field(
        default=0.01,
        ge=0.0,
        description="Exponential falloff above ``start_height`` (``/rtx/fog/fogHeightFalloff``).",
    )
    height_density_ratio: float = Field(
        default=0.5,
        ge=0.0,
        le=2.0,
        description=(
            "Multiplier applied to the tau-derived density when setting "
            "``/rtx/fog/fogHeightDensity`` (ratio of height to distance density)."
        ),
    )


class RayTracingConfig(BaseModel):
    """RTX ray-tracing / post-processing knobs consumed by ``render_settings.py``.

    Migrated from the flat ``antialiasing_op``, ``dlss_exec_mode``,
    ``denoiser_indirect_diffuse`` and ``denoiser_reflections`` fields
    previously declared on ``RenderingConfig``.
    """

    model_config = ConfigDict(extra="forbid")

    antialiasing_op: int = Field(
        default=3,
        ge=0,
        le=5,
        description="``/rtx/post/aa/op``. 0=off, 1=FXAA, 2=TAA, 3=DLAA, 4=DLSS, 5=reserved.",
    )
    dlss_exec_mode: int = Field(
        default=1,
        ge=0,
        le=3,
        description="``/rtx/post/dlss/execMode``. 0=Performance, 1=Balanced, 2=Quality, 3=Auto.",
    )
    denoiser_indirect_diffuse: bool = Field(
        default=True, description="Enable the indirect-diffuse denoiser in RTX mode."
    )
    denoiser_reflections: bool = Field(
        default=True, description="Enable the reflections denoiser in RTX mode."
    )


class PathTracingConfig(BaseModel):
    """Path-tracing knobs consumed by ``render_settings.py``.

    Migrated from the flat ``spp``, ``total_spp``, ``max_bounces`` and
    ``denoiser_optix_pathtracing`` fields previously declared on
    ``RenderingConfig``.
    """

    model_config = ConfigDict(extra="forbid")

    spp: int = Field(default=32, ge=1, le=256, description="Samples per pixel per frame.")
    total_spp: int = Field(default=256, ge=1, description="Total accumulated samples.")
    max_bounces: int = Field(default=8, ge=1, le=64, description="Max ray bounces.")
    denoiser_optix: bool = Field(
        default=True,
        description="Enable OptiX denoiser in path_tracing. Ignored if ``mode='ray_tracing'``.",
    )


class SkyDomeConfig(BaseModel):
    """Sky-dome color / brightness ramp consumed by ``environment/sky_dome.py``.

    Migrates the four previously hardcoded literals (``_CLEAR_SKY_RGB``,
    ``_DUSTY_SKY_RGB``, brightness floor 0.1, brightness decay 0.3) out
    of ``marslab/environment/sky_dome.py`` into YAML so all configurable
    parameters live in YAML.
    """

    model_config = ConfigDict(extra="forbid")

    clear_rgb: Tuple[float, float, float] = Field(
        default=(0.76, 0.57, 0.35),
        description=(
            "Butterscotch clear-sky RGB at tau=0. Mirrors legacy ``_CLEAR_SKY_RGB`` "
            "(Bell et al. 2006 MER Pancam)."
        ),
    )
    dusty_rgb: Tuple[float, float, float] = Field(
        default=(0.85, 0.75, 0.60),
        description=(
            "Dust-storm sky RGB used as interpolation endpoint at tau >= 3. "
            "Mirrors legacy ``_DUSTY_SKY_RGB``."
        ),
    )
    brightness_min: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Lower clamp for sky-dome brightness. Was 0.1 in ``compute_sky_dome_params``.",
    )
    brightness_decay: float = Field(
        default=0.3,
        ge=0.0,
        description=(
            "Slope of brightness = 1 - decay * t where t is the tau interpolation factor. "
            "Previously the 0.3 multiplier in ``compute_sky_dome_params``."
        ),
    )


class RenderingConfig(BaseModel):
    """Rendering configuration."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["path_tracing", "ray_tracing"] = Field(default="path_tracing")
    sky_dome_hdri_dir: str = Field(default="assets/sky/hdri/")
    resolution: list[int] = Field(
        default=[1280, 720], min_length=2, max_length=2, description="[width, height] in pixels"
    )
    sun_intensity_scale: float = Field(
        default=30.0, ge=0.1, description="W/m^2 to Isaac Sim light units scale"
    )
    sun_color: list[float] = Field(
        default=[1.0, 0.95, 0.85], min_length=3, max_length=3, description="Sun light RGB [0-1]"
    )
    sun_angular_diameter_deg: float = Field(
        default=0.35, ge=0.1, le=5.0, description="Sun angular diameter from Mars"
    )
    dome_brightness_scale: float = Field(
        default=5000.0, ge=1.0, description="Sky dome brightness multiplier"
    )
    fog_density_scale: float = Field(
        default=0.002, ge=0.0, description="Tau to fog density conversion factor"
    )
    fog_color: list[float] = Field(
        default=[0.78, 0.62, 0.42],
        min_length=3,
        max_length=3,
        description="Mars dust haze fog RGB [0-1]",
    )

    # Prim path overrides for the sun and dome lights.
    sun_prim_path: str = Field(
        default="/World/SunLight",
        description=(
            "USD prim path for DistantLight from ``sun_renderer.py``. Override for scenarios "
            "spawning multiple sun lights or non-default stage layouts."
        ),
    )
    dome_prim_path: str = Field(
        default="/World/DomeLight",
        description=(
            "USD prim path for DomeLight from ``sky_renderer.py``. Override for scenarios "
            "with multiple dome lights."
        ),
    )

    # Nested sub-configs replace the historical flat fields.
    fog: FogConfig = Field(default_factory=FogConfig)
    ray_tracing: RayTracingConfig = Field(default_factory=RayTracingConfig)
    path_tracing: PathTracingConfig = Field(default_factory=PathTracingConfig)
    sky_dome: SkyDomeConfig = Field(default_factory=SkyDomeConfig)

    @model_validator(mode="before")
    @classmethod
    def _migrate_flat_to_nested(cls, data: Any) -> Any:
        """Accept the legacy flat YAML keys and fold them into the nested
        sub-configs. Scenario YAMLs that still use flat keys keep loading
        without edits. Any explicit nested value wins over the flat shim
        (i.e. nested takes precedence)."""
        if not isinstance(data, dict):
            return data

        flat_to_fog = {
            "fog_enabled": "enabled",
            "fog_color_amount": "color_amount",
            "fog_start_height": "start_height",
            "fog_height_falloff": "height_falloff",
            "fog_height_density_ratio": "height_density_ratio",
        }
        flat_to_rt = {
            "antialiasing_op": "antialiasing_op",
            "dlss_exec_mode": "dlss_exec_mode",
            "denoiser_indirect_diffuse": "denoiser_indirect_diffuse",
            "denoiser_reflections": "denoiser_reflections",
        }
        flat_to_pt = {
            "spp": "spp",
            "total_spp": "total_spp",
            "max_bounces": "max_bounces",
            "denoiser_optix_pathtracing": "denoiser_optix",
        }

        def _merge(section_key: str, mapping: dict[str, str]) -> None:
            existing = data.get(section_key)
            if existing is None or not isinstance(existing, dict):
                existing = {}
            migrated: dict[str, Any] = {}
            for flat_key, nested_key in mapping.items():
                if flat_key in data and nested_key not in existing:
                    migrated[nested_key] = data[flat_key]
            if migrated:
                merged = {**migrated, **existing}
                data[section_key] = merged

        _merge("fog", flat_to_fog)
        _merge("ray_tracing", flat_to_rt)
        _merge("path_tracing", flat_to_pt)

        # Purge flat keys so pydantic does not complain about "extra"
        # fields. The legacy field definitions above are commented out,
        # so the model has no home for them.
        for flat_key in list(flat_to_fog) + list(flat_to_rt) + list(flat_to_pt):
            data.pop(flat_key, None)

        return data

    @model_validator(mode="after")
    def check_resolution(self) -> "RenderingConfig":
        """Resolution values must be positive."""
        if any(v <= 0 for v in self.resolution):
            raise ValueError(f"Resolution values must be positive, got {self.resolution}")
        return self
