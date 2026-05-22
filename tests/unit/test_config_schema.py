"""Unit tests for marslab.config.schema."""

import pytest
from pydantic import ValidationError

from marslab.config.schema import (
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
)

# --- Valid construction ---


def test_mars_env_defaults():
    """Default MarsEnvConfig is physically valid."""
    c = MarsEnvConfig()
    assert c.gravity == 3.72
    assert c.dust_optical_depth == 0.3
    assert c.seed == 42


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
        robots=[RobotConfig(type="rover", urdf_path="test.urdf")],
    )
    assert len(c.robots) == 1


# --- Invalid / out-of-range ---


@pytest.mark.parametrize(
    "field,value",
    [
        ("gravity", 3.0),
        ("gravity", 4.0),
        ("dust_optical_depth", -1.0),
    ],
    ids=["gravity_too_low", "gravity_too_high", "dust_optical_depth_too_low"],
)
def test_mars_env_bounds_reject(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        MarsEnvConfig(**{field: value})


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


# --- Boundary values ---


def test_gravity_at_boundaries():
    """Boundary values (ge/le inclusive) are valid."""
    c_low = MarsEnvConfig(gravity=3.6)
    c_high = MarsEnvConfig(gravity=3.85)
    assert c_low.gravity == 3.6
    assert c_high.gravity == 3.85


# --- Literal-to-YAML migration: rendering sub-configs ---


def test_rendering_config_extended_fields_defaults():
    """RenderingConfig defaults are grouped into four nested sub-configs
    (ray_tracing / path_tracing / fog / sky_dome). Values still mirror the
    documented Isaac Sim render-settings defaults."""
    c = RenderingConfig()
    assert c.sun_prim_path == "/World/SunLight"
    assert c.dome_prim_path == "/World/DomeLight"
    # Fields are grouped under ray_tracing / path_tracing / fog sub-configs.
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


def test_rendering_config_extended_range_violation():
    """Out-of-range fields on the rendering sub-configs raise ValidationError."""
    with pytest.raises(ValidationError):
        RenderingConfig(antialiasing_op=99)
    with pytest.raises(ValidationError):
        RenderingConfig(dlss_exec_mode=7)
    with pytest.raises(ValidationError):
        RenderingConfig(fog_color_amount=2.0)


def test_skid_steer_odom_publisher_default():
    """OdomPublisherConfig submodel defaults match the ROS2 frame convention.

    drive_damping / steer_stiffness / steer_damping / drive_max_force /
    steer_max_force / suspension_damping / drive_type are required
    fields (no Python defaults). Values mirror
    ``configs/rover_m2020.yaml`` so the test does not drift from
    the runtime rover tuning.
    """
    c = SkidSteerDriveConfig(
        drive_damping=1000.0,
        steer_stiffness=50000.0,
        steer_damping=5000.0,
        drive_max_force=1000000.0,
        steer_max_force=100000.0,
        suspension_damping=50.0,
        drive_type="acceleration",
    )
    assert c.odom_publisher.frame_id == "odom"
    assert c.odom_publisher.child_frame_id == "base_link"
    assert c.odom_publisher.queue_size == 10


# --- Rendering nested sub-configs ------------------


def test_fog_config_defaults():
    """FogConfig defaults mirror the canonical flat ``fog_*`` literals."""
    c = FogConfig()
    assert c.enabled is True
    assert c.color_amount == 1.0
    assert c.start_height == 0.0
    assert c.height_falloff == 0.01
    assert c.height_density_ratio == 0.5


@pytest.mark.parametrize(
    "field,value",
    [
        ("color_amount", 1.5),
        ("color_amount", -0.1),
        ("height_falloff", -0.5),
        ("height_density_ratio", 2.5),
        ("height_density_ratio", -0.1),
    ],
    ids=[
        "color_amount_above_1",
        "color_amount_negative",
        "height_falloff_negative",
        "height_density_ratio_above_2",
        "height_density_ratio_negative",
    ],
)
def test_fog_config_bounds_reject(field: str, value: float) -> None:
    """Fog scalar bounds: color_amount in [0,1], height_falloff>=0, ratio in [0,2]."""
    with pytest.raises(ValidationError):
        FogConfig(**{field: value})


def test_ray_tracing_config_defaults():
    """RayTracingConfig defaults match render_settings.py literals."""
    c = RayTracingConfig()
    assert c.antialiasing_op == 3
    assert c.dlss_exec_mode == 1
    assert c.denoiser_indirect_diffuse is True
    assert c.denoiser_reflections is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("antialiasing_op", 9),
        ("antialiasing_op", -1),
        ("dlss_exec_mode", 4),
    ],
    ids=["antialiasing_op_above_5", "antialiasing_op_negative", "dlss_exec_mode_above_3"],
)
def test_ray_tracing_config_bounds_reject(field: str, value: int) -> None:
    """RayTracingConfig: antialiasing_op in [0,5], dlss_exec_mode in [0,3]."""
    with pytest.raises(ValidationError):
        RayTracingConfig(**{field: value})


def test_path_tracing_config_defaults():
    """PathTracingConfig defaults: spp=32, total_spp=256, max_bounces=8."""
    c = PathTracingConfig()
    assert c.spp == 32
    assert c.total_spp == 256
    assert c.max_bounces == 8
    assert c.denoiser_optix is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("spp", 999),
        ("max_bounces", 0),
        ("total_spp", -10),
    ],
    ids=["spp_above_256", "max_bounces_zero", "total_spp_negative"],
)
def test_path_tracing_config_bounds_reject(field: str, value: int) -> None:
    """PathTracingConfig: spp<=256, max_bounces>=1, total_spp>=1."""
    with pytest.raises(ValidationError):
        PathTracingConfig(**{field: value})


def test_sky_dome_config_defaults():
    """SkyDomeConfig defaults mirror the legacy Bell et al. 2006 RGB."""
    c = SkyDomeConfig()
    assert c.clear_rgb == (0.76, 0.57, 0.35)
    assert c.dusty_rgb == (0.85, 0.75, 0.60)
    assert c.brightness_min == 0.1
    assert c.brightness_decay == 0.3


@pytest.mark.parametrize(
    "field,value",
    [
        ("brightness_min", 1.5),
        ("brightness_min", -0.1),
        ("brightness_decay", -0.5),
    ],
    ids=["brightness_min_above_1", "brightness_min_negative", "brightness_decay_negative"],
)
def test_sky_dome_config_bounds_reject(field: str, value: float) -> None:
    """SkyDomeConfig: brightness_min in [0,1], brightness_decay>=0."""
    with pytest.raises(ValidationError):
        SkyDomeConfig(**{field: value})


def test_rendering_nested_structure_access():
    """RenderingConfig exposes nested sub-configs at the expected paths."""
    c = RenderingConfig()
    assert isinstance(c.fog, FogConfig)
    assert isinstance(c.ray_tracing, RayTracingConfig)
    assert isinstance(c.path_tracing, PathTracingConfig)
    assert isinstance(c.sky_dome, SkyDomeConfig)


def test_backward_compat_old_yaml_flat_fog():
    """Legacy flat ``fog_*`` keys migrate into ``FogConfig`` via
    ``model_validator(mode='before')``. Simulates a legacy flat YAML."""
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


# --- DynamicAtmosphere config tree ----------------


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


@pytest.mark.parametrize(
    "kwargs",
    [
        {"time_scale": 0.0},
        {"time_scale": -10.0},
        {"update_interval_frames": 0},
        {"tau_profile": "gaussian"},
    ],
    ids=[
        "time_scale_zero",
        "time_scale_negative",
        "update_interval_frames_zero",
        "tau_profile_unknown",
    ],
)
def test_dynamic_atmosphere_bounds_reject(kwargs: dict) -> None:
    """DynamicAtmosphereConfig: time_scale>0, update_interval_frames>=1, tau_profile literal."""
    with pytest.raises(ValidationError):
        DynamicAtmosphereConfig(**kwargs)


def test_sun_sweep_config_defaults():
    """SunSweepConfig defaults to sunrise=E (90), sunset=W (270)."""
    c = SunSweepConfig()
    assert c.start_azimuth_deg == 90.0
    assert c.end_azimuth_deg == 270.0
    assert c.max_elevation_deg == 60.0


@pytest.mark.parametrize(
    "field,value",
    [
        ("start_azimuth_deg", 361.0),
        ("end_azimuth_deg", -1.0),
        ("max_elevation_deg", 95.0),
    ],
    ids=["start_az_above_360", "end_az_negative", "max_elev_above_90"],
)
def test_sun_sweep_bounds_reject(field: str, value: float) -> None:
    """SunSweepConfig: azimuths in [0,360], max_elevation in [0,90]."""
    with pytest.raises(ValidationError):
        SunSweepConfig(**{field: value})


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


@pytest.mark.parametrize(
    "start,end",
    [(-0.5, 1.0), (0.5, -1.0)],
    ids=["start_negative", "end_negative"],
)
def test_tau_ramp_negative_tau_rejected(start: float, end: float) -> None:
    """Both ramp endpoints must be >= 0."""
    with pytest.raises(ValidationError):
        TauRampConfig(start_tau=start, end_tau=end)


def test_tau_sine_config_defaults():
    """TauSineConfig defaults: base=0.5, amplitude=0.3, period=1.0."""
    c = TauSineConfig()
    assert c.base_tau == 0.5
    assert c.amplitude == 0.3
    assert c.period_fraction == 1.0


@pytest.mark.parametrize(
    "field,value",
    [
        ("period_fraction", 0.0),
        ("period_fraction", -1.0),
        ("amplitude", -0.1),
    ],
    ids=["period_fraction_zero", "period_fraction_negative", "amplitude_negative"],
)
def test_tau_sine_bounds_reject(field: str, value: float) -> None:
    """TauSineConfig: period_fraction>0, amplitude>=0."""
    with pytest.raises(ValidationError):
        TauSineConfig(**{field: value})


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


# --- Absorbed from test_atmosphere_schema.py ----------


@pytest.mark.parametrize("profile", ["constant", "ramp", "sine"])
def test_tau_profile_literal_valid(profile: str) -> None:
    """``tau_profile`` accepts the three literal values."""
    cfg = DynamicAtmosphereConfig(tau_profile=profile)
    assert cfg.tau_profile == profile


def test_tau_profile_literal_unknown_rejected() -> None:
    """``tau_profile`` rejects strings outside the Literal set."""
    with pytest.raises(ValidationError):
        DynamicAtmosphereConfig(tau_profile="linear")


def test_dynamic_atmosphere_model_copy_is_independent() -> None:
    """``model_copy`` does not mutate the source (seed-propagation safety)."""
    base = DynamicAtmosphereConfig(time_scale=200.0)
    modified = base.model_copy(update={"time_scale": 50.0})
    assert base.time_scale == pytest.approx(200.0)
    assert modified.time_scale == pytest.approx(50.0)


def test_marslab_config_yaml_roundtrip_preserves_dynamic_atmosphere(tmp_path) -> None:
    """YAML -> MarsLabConfig roundtrip preserves dynamic_atmosphere fields."""
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
