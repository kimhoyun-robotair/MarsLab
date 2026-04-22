"""Unit tests for marslab.config.schema."""

import pytest
from pydantic import ValidationError

from marslab.config.schema import (
    BenchmarkConfig,
    DynamicAtmosphereConfig,
    FogConfig,
    MarsEnvConfig,
    MarsLabConfig,
    PathTracingConfig,
    RayTracingConfig,
    RenderingConfig,
    RobotConfig,
    SkidSteerDriveConfig,
    SkyDomeConfig,
    SunSweepConfig,
    TauConstantConfig,
    TauRampConfig,
    TauSineConfig,
    TerrainConfig,
)

# --- Valid construction ---


def test_mars_env_defaults():
    """Default MarsEnvConfig is physically valid."""
    c = MarsEnvConfig()
    assert c.gravity == 3.72
    assert c.dust_optical_depth == 0.3
    assert c.seed == 42


def test_terrain_config_procedural():
    """Procedural terrain does not require dem_path."""
    c = TerrainConfig(source="procedural", procedural_preset="flat")
    assert c.dem_path is None


def test_rendering_config_defaults():
    """Default RenderingConfig is valid."""
    c = RenderingConfig()
    assert c.mode == "path_tracing"
    assert c.resolution == [1280, 720]


def test_robot_config_with_urdf():
    """Robot with urdf_path only is valid."""
    c = RobotConfig(type="rover", urdf_path="test.urdf")
    assert c.usd_asset_path is None


def test_robot_config_with_usd():
    """Robot with usd_asset_path only is valid."""
    c = RobotConfig(type="quadruped", usd_asset_path="/path/to/go2.usd")
    assert c.urdf_path is None


def test_marslab_config_full():
    """Full MarsLabConfig with all sub-configs."""
    c = MarsLabConfig(
        terrain=TerrainConfig(source="procedural", procedural_preset="flat"),
        robots=[RobotConfig(type="rover", urdf_path="test.urdf")],
        benchmark=BenchmarkConfig(),
    )
    assert len(c.robots) == 1
    assert c.benchmark is not None


def test_benchmark_optional():
    """MarsLabConfig with benchmark=None is valid."""
    c = MarsLabConfig(terrain=TerrainConfig(source="procedural", procedural_preset="flat"))
    assert c.benchmark is None


# --- Invalid / out-of-range ---


def test_gravity_too_low():
    with pytest.raises(ValidationError):
        MarsEnvConfig(gravity=2.0)


def test_gravity_too_high():
    with pytest.raises(ValidationError):
        MarsEnvConfig(gravity=5.0)


def test_dust_optical_depth_too_low():
    with pytest.raises(ValidationError):
        MarsEnvConfig(dust_optical_depth=-1.0)


def test_terrain_source_invalid():
    with pytest.raises(ValidationError):
        TerrainConfig(source="moon")


def test_rendering_mode_invalid():
    with pytest.raises(ValidationError):
        RenderingConfig(mode="rasterize")


def test_robot_no_path():
    """Robot without urdf_path or usd_asset_path raises."""
    with pytest.raises(ValidationError):
        RobotConfig(type="rover")


def test_albedo_range_inverted():
    with pytest.raises(ValidationError):
        MarsEnvConfig(surface_albedo_range=(0.5, 0.1))


def test_spawn_position_wrong_length():
    with pytest.raises(ValidationError):
        RobotConfig(type="rover", urdf_path="x.urdf", spawn_position=[0.0, 0.0])


def test_negative_seed():
    with pytest.raises(ValidationError):
        MarsEnvConfig(seed=-1)


def test_resolution_non_positive():
    with pytest.raises(ValidationError):
        RenderingConfig(resolution=[0, 720])


def test_hirise_without_any_path():
    """HiRISE source requires either dem_path or converted_dem_dir."""
    with pytest.raises(ValidationError):
        TerrainConfig(source="hirise", dem_path=None, converted_dem_dir=None)


def test_hirise_with_converted_dir_only():
    """HiRISE source is valid with only converted_dem_dir (no dem_path)."""
    tc = TerrainConfig(source="hirise", converted_dem_dir="assets/terrain/dem/converted")
    assert tc.converted_dem_dir == "assets/terrain/dem/converted"
    assert tc.dem_path is None


def test_hirise_with_both_paths():
    """HiRISE source is valid with both dem_path and converted_dem_dir."""
    tc = TerrainConfig(
        source="hirise",
        dem_path="foo.tif",
        converted_dem_dir="foo_converted",
    )
    assert tc.dem_path == "foo.tif"
    assert tc.converted_dem_dir == "foo_converted"


# --- Boundary values ---


def test_gravity_at_boundaries():
    """Boundary values (ge/le inclusive) are valid."""
    c_low = MarsEnvConfig(gravity=3.0)
    c_high = MarsEnvConfig(gravity=4.0)
    assert c_low.gravity == 3.0
    assert c_high.gravity == 4.0


# --- R3 (2026-04-22) G5: literal-to-YAML migration ---


def test_rendering_config_r3_new_fields_defaults():
    """R3 added 12 RenderingConfig fields; R2-A1 (2026-04-22) regrouped
    them into four nested sub-configs. Defaults still mirror the pre-R3
    Python literals."""
    c = RenderingConfig()
    assert c.sun_prim_path == "/World/SunLight"
    assert c.dome_prim_path == "/World/DomeLight"
    # R2-A1: fields moved to ray_tracing / path_tracing / fog sub-configs.
    # Legacy flat accesses retained as comments:
    #   assert c.antialiasing_op == 3
    #   assert c.dlss_exec_mode == 1
    #   assert c.denoiser_indirect_diffuse is True
    #   assert c.denoiser_reflections is True
    #   assert c.denoiser_optix_pathtracing is True
    #   assert c.fog_enabled is True
    #   assert c.fog_color_amount == 1.0
    #   assert c.fog_start_height == 0.0
    #   assert c.fog_height_falloff == 0.01
    #   assert c.fog_height_density_ratio == 0.5
    assert c.ray_tracing.antialiasing_op == 3
    assert c.ray_tracing.dlss_exec_mode == 1
    assert c.ray_tracing.denoiser_indirect_diffuse is True
    assert c.ray_tracing.denoiser_reflections is True
    assert c.path_tracing.denoiser_optix is True
    assert c.fog.enabled is True
    assert c.fog.color_amount == 1.0
    assert c.fog.start_height == 0.0
    assert c.fog.height_falloff == 0.01
    assert c.fog.height_density_ratio == 0.5


def test_rendering_config_r3_range_violation():
    """Out-of-range R3 fields raise ValidationError."""
    with pytest.raises(ValidationError):
        RenderingConfig(antialiasing_op=99)
    with pytest.raises(ValidationError):
        RenderingConfig(dlss_exec_mode=7)
    with pytest.raises(ValidationError):
        RenderingConfig(fog_color_amount=2.0)


def test_skid_steer_odom_publisher_default():
    """R3 OdomPublisherConfig submodel defaults match the ROS2 frame convention.

    R2-A3 (2026-04-22) promoted drive_damping / steer_stiffness /
    steer_damping to required fields (no Python defaults), so the
    constructor now needs them explicitly. Values mirror
    ``configs/robots/rover_m2020.yaml`` so the test does not drift from
    the runtime rover tuning.
    """
    c = SkidSteerDriveConfig(
        drive_damping=1000.0,
        steer_stiffness=50000.0,
        steer_damping=5000.0,
    )
    assert c.odom_publisher.frame_id == "odom"
    assert c.odom_publisher.child_frame_id == "base_link"
    assert c.odom_publisher.queue_size == 10


# --- R2-A1 (2026-04-22) Rendering nested sub-configs ------------------


def test_fog_config_defaults():
    """FogConfig defaults mirror the pre-R2-A1 flat ``fog_*`` literals."""
    c = FogConfig()
    assert c.enabled is True
    assert c.color_amount == 1.0
    assert c.start_height == 0.0
    assert c.height_falloff == 0.01
    assert c.height_density_ratio == 0.5


def test_fog_config_color_amount_out_of_range():
    """``color_amount`` must live in [0, 1]."""
    with pytest.raises(ValidationError):
        FogConfig(color_amount=1.5)
    with pytest.raises(ValidationError):
        FogConfig(color_amount=-0.1)


def test_fog_config_negative_falloff_rejected():
    """Negative ``height_falloff`` violates the ``ge=0`` constraint."""
    with pytest.raises(ValidationError):
        FogConfig(height_falloff=-0.5)


def test_fog_config_height_density_ratio_bounds():
    """``height_density_ratio`` must stay within [0, 2]."""
    with pytest.raises(ValidationError):
        FogConfig(height_density_ratio=2.5)
    with pytest.raises(ValidationError):
        FogConfig(height_density_ratio=-0.1)


def test_ray_tracing_config_defaults():
    """RayTracingConfig defaults match render_settings.py literals."""
    c = RayTracingConfig()
    assert c.antialiasing_op == 3
    assert c.dlss_exec_mode == 1
    assert c.denoiser_indirect_diffuse is True
    assert c.denoiser_reflections is True


def test_ray_tracing_config_antialiasing_out_of_range():
    """``antialiasing_op`` outside [0, 5] is rejected."""
    with pytest.raises(ValidationError):
        RayTracingConfig(antialiasing_op=9)
    with pytest.raises(ValidationError):
        RayTracingConfig(antialiasing_op=-1)


def test_ray_tracing_config_dlss_exec_mode_bounds():
    """``dlss_exec_mode`` must stay within [0, 3]."""
    with pytest.raises(ValidationError):
        RayTracingConfig(dlss_exec_mode=4)


def test_path_tracing_config_defaults():
    """PathTracingConfig defaults: spp=32, total_spp=256, max_bounces=8."""
    c = PathTracingConfig()
    assert c.spp == 32
    assert c.total_spp == 256
    assert c.max_bounces == 8
    assert c.denoiser_optix is True


def test_path_tracing_config_spp_too_high():
    """``spp`` upper bound is 256."""
    with pytest.raises(ValidationError):
        PathTracingConfig(spp=999)


def test_path_tracing_config_max_bounces_zero_rejected():
    """``max_bounces=0`` violates the ``ge=1`` constraint."""
    with pytest.raises(ValidationError):
        PathTracingConfig(max_bounces=0)


def test_path_tracing_config_total_spp_negative():
    """``total_spp`` must be >= 1."""
    with pytest.raises(ValidationError):
        PathTracingConfig(total_spp=-10)


def test_sky_dome_config_defaults():
    """SkyDomeConfig defaults mirror the legacy Bell et al. 2006 RGB."""
    c = SkyDomeConfig()
    assert c.clear_rgb == (0.76, 0.57, 0.35)
    assert c.dusty_rgb == (0.85, 0.75, 0.60)
    assert c.brightness_min == 0.1
    assert c.brightness_decay == 0.3


def test_sky_dome_config_brightness_min_out_of_range():
    """``brightness_min`` must be in [0, 1]."""
    with pytest.raises(ValidationError):
        SkyDomeConfig(brightness_min=1.5)
    with pytest.raises(ValidationError):
        SkyDomeConfig(brightness_min=-0.1)


def test_sky_dome_config_negative_decay_rejected():
    """``brightness_decay`` cannot be negative (``ge=0``)."""
    with pytest.raises(ValidationError):
        SkyDomeConfig(brightness_decay=-0.5)


def test_rendering_nested_structure_access():
    """RenderingConfig exposes nested sub-configs at the expected paths."""
    c = RenderingConfig()
    assert isinstance(c.fog, FogConfig)
    assert isinstance(c.ray_tracing, RayTracingConfig)
    assert isinstance(c.path_tracing, PathTracingConfig)
    assert isinstance(c.sky_dome, SkyDomeConfig)


def test_backward_compat_old_yaml_flat_fog():
    """Legacy flat ``fog_*`` keys migrate into ``FogConfig`` via
    ``model_validator(mode='before')``. Simulates a pre-R2-A1 YAML."""
    legacy = {
        "fog_enabled": False,
        "fog_color_amount": 0.5,
        "fog_start_height": 2.0,
        "fog_height_falloff": 0.05,
        "fog_height_density_ratio": 1.0,
    }
    c = RenderingConfig(**legacy)
    assert c.fog.enabled is False
    assert c.fog.color_amount == 0.5
    assert c.fog.start_height == 2.0
    assert c.fog.height_falloff == 0.05
    assert c.fog.height_density_ratio == 1.0


def test_backward_compat_old_yaml_flat_ray_tracing():
    """Legacy flat ``antialiasing_op`` / ``dlss_exec_mode`` /
    ``denoiser_*`` keys migrate into ``RayTracingConfig``."""
    legacy = {
        "antialiasing_op": 2,
        "dlss_exec_mode": 2,
        "denoiser_indirect_diffuse": False,
        "denoiser_reflections": False,
    }
    c = RenderingConfig(**legacy)
    assert c.ray_tracing.antialiasing_op == 2
    assert c.ray_tracing.dlss_exec_mode == 2
    assert c.ray_tracing.denoiser_indirect_diffuse is False
    assert c.ray_tracing.denoiser_reflections is False


def test_backward_compat_old_yaml_flat_path_tracing():
    """Legacy flat ``spp`` / ``total_spp`` / ``max_bounces`` /
    ``denoiser_optix_pathtracing`` keys migrate into ``PathTracingConfig``."""
    legacy = {
        "spp": 16,
        "total_spp": 128,
        "max_bounces": 4,
        "denoiser_optix_pathtracing": False,
    }
    c = RenderingConfig(**legacy)
    assert c.path_tracing.spp == 16
    assert c.path_tracing.total_spp == 128
    assert c.path_tracing.max_bounces == 4
    assert c.path_tracing.denoiser_optix is False


def test_backward_compat_nested_precedence_over_flat():
    """When both the flat and nested keys are present, the nested dict
    wins (explicit user intent is preserved)."""
    mixed = {
        "spp": 16,
        "path_tracing": {"spp": 64},
    }
    c = RenderingConfig(**mixed)
    assert c.path_tracing.spp == 64


# --- R2-A2 (2026-04-22) DynamicAtmosphere config tree ----------------


def test_dynamic_atmosphere_config_defaults():
    """DynamicAtmosphereConfig defaults: disabled, tau_profile=constant."""
    c = DynamicAtmosphereConfig()
    assert c.enabled is False
    assert c.time_scale == 200.0
    assert c.update_interval_frames == 10
    assert c.tau_profile == "constant"
    assert isinstance(c.sun_sweep, SunSweepConfig)
    assert isinstance(c.tau_constant, TauConstantConfig)
    assert isinstance(c.tau_ramp, TauRampConfig)
    assert isinstance(c.tau_sine, TauSineConfig)


def test_dynamic_atmosphere_time_scale_must_be_positive():
    """``time_scale`` must be > 0."""
    with pytest.raises(ValidationError):
        DynamicAtmosphereConfig(time_scale=0.0)
    with pytest.raises(ValidationError):
        DynamicAtmosphereConfig(time_scale=-10.0)


def test_dynamic_atmosphere_update_interval_frames_min():
    """``update_interval_frames`` must be >= 1."""
    with pytest.raises(ValidationError):
        DynamicAtmosphereConfig(update_interval_frames=0)


def test_dynamic_atmosphere_tau_profile_literal():
    """``tau_profile`` accepts only {constant, ramp, sine}."""
    with pytest.raises(ValidationError):
        DynamicAtmosphereConfig(tau_profile="gaussian")


def test_sun_sweep_config_defaults():
    """SunSweepConfig defaults to sunrise=E (90), sunset=W (270)."""
    c = SunSweepConfig()
    assert c.start_azimuth_deg == 90.0
    assert c.end_azimuth_deg == 270.0
    assert c.max_elevation_deg == 60.0


def test_sun_sweep_azimuth_out_of_range():
    """Azimuth must be in [0, 360]."""
    with pytest.raises(ValidationError):
        SunSweepConfig(start_azimuth_deg=361.0)
    with pytest.raises(ValidationError):
        SunSweepConfig(end_azimuth_deg=-1.0)


def test_sun_sweep_elevation_out_of_range():
    """``max_elevation_deg`` must be in [0, 90]."""
    with pytest.raises(ValidationError):
        SunSweepConfig(max_elevation_deg=95.0)


def test_tau_constant_config_defaults():
    """TauConstantConfig default base_tau = 0.3."""
    c = TauConstantConfig()
    assert c.base_tau == 0.3


def test_tau_constant_negative_rejected():
    """``base_tau`` must be >= 0."""
    with pytest.raises(ValidationError):
        TauConstantConfig(base_tau=-0.1)


def test_tau_ramp_config_defaults():
    """TauRampConfig defaults: 0.3 -> 2.0 (dust storm onset)."""
    c = TauRampConfig()
    assert c.start_tau == 0.3
    assert c.end_tau == 2.0


def test_tau_ramp_negative_tau_rejected():
    """Both ramp endpoints must be >= 0."""
    with pytest.raises(ValidationError):
        TauRampConfig(start_tau=-0.5, end_tau=1.0)
    with pytest.raises(ValidationError):
        TauRampConfig(start_tau=0.5, end_tau=-1.0)


def test_tau_sine_config_defaults():
    """TauSineConfig defaults: base=0.5, amplitude=0.3, period=1.0."""
    c = TauSineConfig()
    assert c.base_tau == 0.5
    assert c.amplitude == 0.3
    assert c.period_fraction == 1.0


def test_tau_sine_period_fraction_must_be_positive():
    """``period_fraction`` must be > 0."""
    with pytest.raises(ValidationError):
        TauSineConfig(period_fraction=0.0)
    with pytest.raises(ValidationError):
        TauSineConfig(period_fraction=-1.0)


def test_tau_sine_negative_amplitude_rejected():
    """``amplitude`` must be >= 0."""
    with pytest.raises(ValidationError):
        TauSineConfig(amplitude=-0.1)


def test_mars_env_embeds_dynamic_atmosphere_by_default():
    """MarsEnvConfig auto-fills ``dynamic_atmosphere`` with defaults."""
    c = MarsEnvConfig()
    assert isinstance(c.dynamic_atmosphere, DynamicAtmosphereConfig)
    assert c.dynamic_atmosphere.enabled is False
    # Nested leaf should also be present.
    assert c.dynamic_atmosphere.sun_sweep.max_elevation_deg == 60.0


def test_mars_env_dynamic_atmosphere_custom_dict():
    """MarsEnvConfig accepts nested dict for dynamic_atmosphere."""
    c = MarsEnvConfig(
        dynamic_atmosphere={
            "enabled": True,
            "tau_profile": "sine",
            "tau_sine": {"base_tau": 0.7, "amplitude": 0.2, "period_fraction": 0.5},
        }
    )
    assert c.dynamic_atmosphere.enabled is True
    assert c.dynamic_atmosphere.tau_profile == "sine"
    assert c.dynamic_atmosphere.tau_sine.period_fraction == 0.5
