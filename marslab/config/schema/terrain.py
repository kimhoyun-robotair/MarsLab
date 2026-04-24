"""Terrain schemas: DEM crop, cave (lava tube), terrain generation.

Split from marslab.config.schema (R2, 2026-04-22). Intra-file order:
``DemCropConfig`` -> ``CaveConfig`` -> ``TerrainConfig`` so the later
models reference the earlier ones without forward-ref strings.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "CaveConfig",
    "CaveGeometryConfig",
    "DemCropConfig",
    "ProceduralCanyonConfig",
    "TerrainConfig",
]


# Reviewer 2 #12 (2026-04-24): every terrain-schema BaseModel opts into
# ``extra="forbid"`` so unknown keys fail loudly.  The public rationale
# lives in ``marslab/config/schema/mars_env.py``.  One concrete reveal
# from flipping this on: ``configs/scenarios/procedural_canyon.yaml``
# had seven ``canyon_*`` keys at the terrain level that
# ``TerrainConfig`` did not declare, so pydantic v2 silently threw them
# away.  The new :class:`ProceduralCanyonConfig` below captures them
# under ``terrain.canyon`` (and a ``model_validator(mode="before")``
# shim on ``TerrainConfig`` folds the legacy flat keys into the nested
# block).


class CaveGeometryConfig(BaseModel):
    """Fine-grained cave geometry knobs surfaced to YAML (R5).

    The top-level :class:`CaveConfig` already exposes the high-impact
    cave parameters (tube width, curvature, skylight counts, etc.).
    This nested block surfaces nine additional tuning parameters that
    previously lived as in-code constants so scenario YAMLs can adjust
    centerline sweep shape and surface-cap noise without patching
    Python.

    YAMLs that omit the ``geometry`` block keep the previous behaviour
    by virtue of the defaults below.
    """

    model_config = ConfigDict(extra="forbid")

    centerline_path_length_factor: float = Field(
        default=1.1,
        gt=0,
        description="Path length multiplier vs. longest domain side.",
    )
    centerline_freq_ratio_secondary: float = Field(
        default=2.3,
        gt=0,
        description="Secondary harmonic frequency as a ratio of the primary.",
    )
    centerline_secondary_amp_ratio: float = Field(
        default=0.3,
        ge=0,
        description="Secondary harmonic amplitude as a fraction of the primary.",
    )
    centerline_amp_domain_ratio: float = Field(
        default=0.15,
        ge=0,
        description="Primary perturbation amplitude as a fraction of the short domain side.",
    )
    cross_section_smooth_sigma: tuple[float, float] = Field(
        default=(3.0, 2.0),
        description="gaussian_filter sigma for (stations, ring) on cross-section noise.",
    )
    floor_debris_height_scale: float = Field(
        default=0.3,
        ge=0,
        description="Height scale factor applied to smoothed floor debris noise.",
    )
    surface_noise_sigma: float = Field(
        default=10.0,
        gt=0,
        description="Gaussian sigma for surface-cap elevation noise.",
    )
    surface_noise_amplitude_m: float = Field(
        default=2.0,
        ge=0,
        description="Peak-ish amplitude (sigma-normalized) of surface noise in meters.",
    )
    debris_cone_diameter_ratio: float = Field(
        default=0.15,
        gt=0,
        description="Debris cone base diameter as a fraction of the tube width.",
    )

    @model_validator(mode="after")
    def check_smooth_sigma(self) -> "CaveGeometryConfig":
        """Ensure both gaussian sigmas are positive."""
        sig_stations, sig_ring = self.cross_section_smooth_sigma
        if sig_stations <= 0 or sig_ring <= 0:
            raise ValueError(
                "cross_section_smooth_sigma entries must both be > 0, "
                f"got {self.cross_section_smooth_sigma}"
            )
        return self


class DemCropConfig(BaseModel):
    """Row/column crop window into a pre-loaded HiRISE DEM.

    Added for Wk2 #1-#3 (2026-04-14) so scenario YAMLs can carve
    distinct regions (plain, rim, delta) out of the shared Jezero DEM
    without committing multiple GeoTIFFs to the repo. All values are
    pixel indices into the source elevation array.
    """

    model_config = ConfigDict(extra="forbid")

    row: int = Field(ge=0, description="Top-left row index of the crop window")
    col: int = Field(ge=0, description="Top-left column index of the crop window")
    height: int = Field(ge=1, description="Crop window height in pixels")
    width: int = Field(ge=1, description="Crop window width in pixels")


class CaveConfig(BaseModel):
    """Mars lava tube cave parameters for procedural generation.

    Science basis: Sauro et al. 2020, Cushing 2007/2012, Theinat 2020,
    Blair 2017, Blank 2024 (BRAILLE). See work_log/scene_generation/mars_cave.md.
    """

    model_config = ConfigDict(extra="forbid")

    tube_width_m: float = Field(
        default=200.0,
        ge=80.0,
        le=300.0,
        description="Lava tube width in meters (Sauro 2020: 80-300m, mode 200m)",
    )
    tube_height_ratio: float = Field(
        default=0.5,
        ge=0.25,
        le=0.6,
        description="Height/width ratio for half-ellipse cross-section (W:H 2:1 to 3:1)",
    )
    cross_section_noise: float = Field(
        default=0.20,
        ge=0.0,
        le=0.4,
        description="±fraction of Gaussian noise on cross-section radius (Chwala 2024)",
    )
    tube_direction_deg: float = Field(
        default=0.0,
        ge=0.0,
        le=360.0,
        description="Tube axis direction in degrees (0=along Y axis, 90=along X axis)",
    )
    tube_curvature: float = Field(
        default=0.15,
        ge=0.0,
        le=0.5,
        description="Sinusoidal curvature amplitude factor for centerline",
    )
    ceiling_thickness_m: float = Field(
        default=50.0,
        ge=20.0,
        le=100.0,
        description="Rock ceiling thickness above tube crown (Sauro 2018: 30-80m)",
    )
    skylight_count: int = Field(
        default=10,
        ge=0,
        le=20,
        description="Number of skylights (ceiling collapse openings) along the tube",
    )
    skylight_diameter_m: float = Field(
        default=20.0,
        ge=5.0,
        le=250.0,
        description="Skylight opening diameter in meters (5-250m)",
    )
    skylight_depth_m: float = Field(
        default=110.0,
        ge=20.0,
        le=200.0,
        description=(
            "Skylight depth from surface to tube ceiling (Cushing 2007: 68-178m). "
            "Default 110m keeps a 10m margin above the default tube ceiling "
            "(tube_width_m*tube_height_ratio = 200*0.5 = 100m) so ``CaveConfig()`` "
            "with default ``skylight_count=10`` passes ``check_cave_ranges`` "
            "without user intervention."
        ),
    )
    skylight_overhang_deg: float = Field(
        default=5.0,
        ge=0.0,
        le=15.0,
        description="Inward overhang angle of skylight walls (Cushing 2012)",
    )
    debris_cone_present: bool = Field(
        default=True,
        description="Whether debris cones are placed inside the tube",
    )
    debris_cone_count: int = Field(
        default=5,
        ge=0,
        le=20,
        description="Number of debris cones randomly placed inside the tube",
    )
    debris_cone_angle_deg: float = Field(
        default=30.0,
        ge=20.0,
        le=40.0,
        description="Angle of repose for debris cone (Cushing 2012: ~30 deg)",
    )
    breakdown_coverage_pct: float = Field(
        default=25.0,
        ge=0.0,
        le=80.0,
        description="Floor area covered by breakdown blocks (Blank 2024: 10-80%)",
    )
    breakdown_block_mean_m: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description=(
            "Arithmetic mean block diameter in meters (Blank 2024: mean "
            "0.5m). Internally the lognormal draw is mean-corrected so "
            "E[diameter] equals this value."
        ),
    )
    breakdown_block_sigma: float = Field(
        default=0.3,
        ge=0.05,
        le=1.0,
        description=(
            "Standard deviation of the underlying normal distribution "
            "(sigma argument to numpy.random.Generator.lognormal)."
        ),
    )
    floor_flat_pct: float = Field(
        default=70.0,
        ge=20.0,
        le=100.0,
        description="Percentage of floor that is flat vs debris-covered",
    )
    wall_albedo_range: tuple[float, float] = Field(
        default=(0.05, 0.15),
        description="Cave wall/ceiling albedo range (dark basalt, Rodriguez 2021)",
    )
    ring_resolution: int = Field(
        default=40,
        ge=12,
        le=120,
        description="Number of vertices per cross-section ring",
    )
    path_resolution: int = Field(
        default=100,
        ge=20,
        le=400,
        description="Number of cross-sections along the tube centerline",
    )
    geometry: CaveGeometryConfig = Field(
        default_factory=CaveGeometryConfig,
        description=(
            "Fine-grained centerline/surface/debris geometry knobs (R5). "
            "Omit to keep pre-R5 defaults."
        ),
    )

    @model_validator(mode="after")
    def check_cave_ranges(self) -> "CaveConfig":
        """Validate cave parameter consistency."""
        if self.wall_albedo_range[0] >= self.wall_albedo_range[1]:
            raise ValueError(
                f"wall_albedo_range must be (min, max) with min < max, "
                f"got {self.wall_albedo_range}"
            )
        tube_height = self.tube_width_m * self.tube_height_ratio
        if self.skylight_count > 0 and self.skylight_depth_m < tube_height:
            raise ValueError(
                f"skylight_depth_m ({self.skylight_depth_m}) must be >= tube height "
                f"({tube_height:.1f}m = width * ratio) for the shaft to reach the tube"
            )
        return self


class ProceduralCanyonConfig(BaseModel):
    """Procedural-canyon preset knobs used by ``marslab.terrain.procedural``.

    Reviewer 2 #12 (2026-04-24) introduced this model to give the
    ``canyon_*`` keys in ``configs/scenarios/procedural_canyon.yaml`` a
    schema-validated home.  Before ``extra="forbid"`` was turned on,
    those keys were read directly from the untyped YAML dict by
    ``marslab.terrain.procedural.generate_canyon_terrain`` and pydantic
    silently dropped them from ``TerrainConfig`` — the only reason the
    canyon scenario still rendered was that the consumer bypassed
    pydantic entirely.  With forbid on, the keys have to land somewhere;
    this block is that landing pad.

    Field names mirror the YAML keys 1:1 so grep-ability across scenario
    files, this schema, and the consumer is trivial.  A legacy
    ``model_validator(mode="before")`` on :class:`TerrainConfig` folds
    the historical flat ``canyon_*`` keys into ``terrain.canyon`` so
    existing YAMLs keep loading without edits.
    """

    model_config = ConfigDict(extra="forbid")

    canyon_depth: float = Field(
        ...,
        gt=0.0,
        description=(
            "Depth from rim to floor in metres.  Matches ``canyon_depth`` in "
            "``configs/scenarios/procedural_canyon.yaml`` (currently 40.0)."
        ),
    )
    canyon_floor_width: float = Field(
        ...,
        gt=0.0,
        description=(
            "Traversable floor width (metres) — the flat corridor between the "
            "two rims.  YAML field ``canyon_floor_width``."
        ),
    )
    canyon_total_width: float = Field(
        ...,
        gt=0.0,
        description=(
            "Full top-of-rim to top-of-rim width (metres).  Must exceed "
            "``canyon_floor_width`` — enforced by ``check_widths`` below."
        ),
    )
    canyon_curvature: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Sinusoidal curvature amplitude as a fraction of floor width.  "
            "0 = dead-straight canyon.  Matches ``canyon_curvature``."
        ),
    )
    canyon_craters: int = Field(
        default=0,
        ge=0,
        description=(
            "Number of craters to cut into the canyon floor for Nav2 "
            "obstacle tests.  YAML field ``canyon_craters``."
        ),
    )
    canyon_crater_radius_range: tuple[float, float] = Field(
        default=(5.0, 15.0),
        description=(
            "(min, max) crater radius in metres.  YAML field " "``canyon_crater_radius_range``."
        ),
    )
    canyon_crater_depth_range: tuple[float, float] = Field(
        default=(2.0, 6.0),
        description=(
            "(min, max) crater depth in metres.  YAML field " "``canyon_crater_depth_range``."
        ),
    )

    @model_validator(mode="after")
    def check_widths(self) -> "ProceduralCanyonConfig":
        """Total width must exceed floor width and ranges must be ordered."""
        if self.canyon_total_width <= self.canyon_floor_width:
            raise ValueError(
                "canyon_total_width must exceed canyon_floor_width "
                f"(got total={self.canyon_total_width}, floor={self.canyon_floor_width})"
            )
        r_lo, r_hi = self.canyon_crater_radius_range
        if r_lo <= 0.0 or r_hi <= 0.0 or r_lo >= r_hi:
            raise ValueError(
                "canyon_crater_radius_range must be (min, max) with 0 < min < max, "
                f"got {self.canyon_crater_radius_range}"
            )
        d_lo, d_hi = self.canyon_crater_depth_range
        if d_lo <= 0.0 or d_hi <= 0.0 or d_lo >= d_hi:
            raise ValueError(
                "canyon_crater_depth_range must be (min, max) with 0 < min < max, "
                f"got {self.canyon_crater_depth_range}"
            )
        return self


# Historical flat YAML keys that have to be migrated into
# ``terrain.canyon`` when ``extra="forbid"`` kicks in on ``TerrainConfig``.
# Declared at module scope (rather than inside the migrator) so the same
# set is referenced by the regression test in ``tests/unit``.
_LEGACY_CANYON_FLAT_KEYS = (
    "canyon_depth",
    "canyon_floor_width",
    "canyon_total_width",
    "canyon_curvature",
    "canyon_craters",
    "canyon_crater_radius_range",
    "canyon_crater_depth_range",
)


class TerrainConfig(BaseModel):
    """Terrain generation parameters."""

    model_config = ConfigDict(extra="forbid")

    source: Literal["hirise", "procedural"] = Field(default="hirise")
    scenario_name: str | None = Field(
        default=None,
        description="Human-readable scenario identifier (e.g. 'basic_mars'). "
        "Propagated to visualizations and LOG entries; purely informational.",
    )
    dem_path: str | None = Field(default=None, description="Path to HiRISE DEM GeoTIFF")
    converted_dem_dir: str | None = Field(
        default=None,
        description="Directory containing pre-converted elevation.npy and metadata.json",
    )
    dem_crop: DemCropConfig | None = Field(
        default=None,
        description="Optional sub-window crop into the loaded DEM. When set, "
        "scenario builders use only this region instead of the full DEM.",
    )
    rock_sfd_k: float = Field(
        default=0.05, ge=0, le=0.15, description="Golombek CFA fraction (0=no rocks)"
    )
    rock_diameter_range: tuple[float, float] = Field(
        default=(0.20, 3.0), description="Rock diameter range in meters (< 20cm as texture)"
    )
    semantic_classes: list[str] = Field(
        default=["soil", "bedrock", "sand", "big_rock"],
        description="AI4Mars-compatible terrain classes",
    )
    terrain_size: tuple[int, int] = Field(
        default=(256, 256), description="Procedural terrain size (rows, cols) in pixels"
    )
    terrain_resolution: float = Field(
        default=1.0, ge=0.1, le=10.0, description="Meters per pixel for procedural terrain"
    )
    procedural_preset: str | None = Field(
        default=None,
        description="Procedural preset: flat, crater, hills, rocky_plain, canyon, cave",
    )
    cave: CaveConfig | None = Field(
        default=None,
        description="Cave (lava tube) generation parameters. Required when "
        "procedural_preset is 'cave'.",
    )
    canyon: ProceduralCanyonConfig | None = Field(
        default=None,
        description=(
            "Procedural canyon preset knobs. Required when "
            "``procedural_preset='canyon'``. Reviewer 2 #12 (2026-04-24) "
            "introduced this field; the legacy flat ``canyon_*`` YAML keys "
            "are auto-migrated into this block by ``_migrate_flat_canyon_keys``."
        ),
    )
    texture_dir: str | None = Field(
        default=None, description="Path to PBR texture directory (albedo.png, normal.png, etc.)"
    )
    rock_color: tuple[float, float, float] = Field(
        default=(0.42, 0.28, 0.20), description="Mars rock base color RGB (reddish-brown)"
    )
    rock_roughness: float = Field(
        default=0.92, ge=0.0, le=1.0, description="Rock surface roughness"
    )
    rock_mesh_dir: str | None = Field(
        default=None, description="Rock OBJ mesh directory (null = Sphere fallback)"
    )
    rock_texture_dir: str | None = Field(
        default=None, description="Rock PBR texture directory (null = color only)"
    )
    uv_scale: float = Field(default=16.0, ge=1.0, description="Texture UV tiling factor")
    seed: int = Field(default=42, ge=0)

    @model_validator(mode="before")
    @classmethod
    def _migrate_flat_canyon_keys(cls, data):
        """Fold legacy flat ``canyon_*`` YAML keys into ``terrain.canyon``.

        Reviewer 2 #12 (2026-04-24).  ``configs/scenarios/procedural_canyon.yaml``
        historically put ``canyon_depth`` / ``canyon_floor_width`` / ``...`` at
        the ``terrain:`` top level.  With ``extra="forbid"`` on, those keys
        would now be rejected.  This pre-validator migrates them into the
        nested :class:`ProceduralCanyonConfig` block (``terrain.canyon``) so
        the existing YAML keeps loading without edits.  If ``terrain.canyon``
        is already provided explicitly, the nested dict wins and the flat
        keys are dropped silently (explicit user intent beats the shim).
        """
        if not isinstance(data, dict):
            return data
        present = {k: data[k] for k in _LEGACY_CANYON_FLAT_KEYS if k in data}
        if not present:
            return data
        existing = data.get("canyon")
        if isinstance(existing, dict) and existing:
            # Explicit canyon: dict wins, drop legacy flat keys.
            for k in _LEGACY_CANYON_FLAT_KEYS:
                data.pop(k, None)
            return data
        # No explicit canyon block — lift the flat keys wholesale.
        data["canyon"] = present
        for k in _LEGACY_CANYON_FLAT_KEYS:
            data.pop(k, None)
        return data

    @model_validator(mode="after")
    def check_terrain(self) -> "TerrainConfig":
        """Validate conditional requirements and range ordering."""
        if self.source == "hirise" and self.dem_path is None and self.converted_dem_dir is None:
            raise ValueError("dem_path or converted_dem_dir is required when source is 'hirise'")
        if self.source == "procedural" and self.procedural_preset is None:
            raise ValueError("procedural_preset is required when source is 'procedural'")
        if self.rock_diameter_range[0] >= self.rock_diameter_range[1]:
            raise ValueError(
                f"rock_diameter_range must be (min, max) with min < max, "
                f"got {self.rock_diameter_range}"
            )
        return self

    @model_validator(mode="after")
    def _check_canyon_required(self) -> "TerrainConfig":
        """``procedural_preset='canyon'`` requires the ``canyon`` block.

        Reviewer 2 #12 (2026-04-24).  Kept as a separate validator (rather
        than folded into ``check_terrain``) so the error message stays
        scoped to the canyon-specific failure mode.
        """
        if (
            self.source == "procedural"
            and self.procedural_preset == "canyon"
            and self.canyon is None
        ):
            raise ValueError(
                "terrain.canyon is required when procedural_preset='canyon'. "
                "Provide canyon_depth / canyon_floor_width / canyon_total_width "
                "(see marslab.config.schema.terrain.ProceduralCanyonConfig)."
            )
        return self
