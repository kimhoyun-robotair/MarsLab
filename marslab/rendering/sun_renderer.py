"""Mars sun (directional light) configuration for Isaac Sim.

Creates a UsdLux DistantLight oriented by the sun position with
intensity derived from Beer's Law computation.
Requires Isaac Sim runtime.
"""

from pxr import Gf, Sdf, UsdGeom, UsdLux

from marslab.config.schema import RenderingConfig
from marslab.environment.sun_position import SunPosition


def _clamp_diffuse_fraction(diffuse_fraction: float) -> float:
    """Clamp diffuse fraction defensively into the [0, 1] range.

    By construction ``compute_diffuse_fraction`` (COMIMART, Vicente-Retortillo
    et al. 2015) returns a value in ``[0, 1]``. The clamp here exists to keep
    the energy partition well-formed even if a caller passes a slightly
    out-of-range value due to floating-point drift or external override.
    """
    return max(0.0, min(1.0, diffuse_fraction))


def configure_sun_light(
    stage,
    sun_pos: SunPosition,
    intensity: float,
    diffuse_fraction: float,
    rendering_config: RenderingConfig,
) -> None:
    """Configure a directional light representing the Mars sun.

    All scaling factors and colors are read from rendering_config.

    The ``diffuse_fraction`` (from COMIMART) is applied here as
    ``intensity_direct = intensity * (1 - diffuse_fraction)``. The matching
    diffuse term ``intensity * diffuse_fraction`` is applied in
    :func:`marslab.rendering.sky_renderer.configure_sky_dome` so the total
    emitted energy budget matches Beer's law and avoids double-counting the
    direct + diffuse partition.

    Args:
        stage: USD stage.
        sun_pos: Sun position (azimuth, elevation, zenith).
        intensity: Direct beam irradiance in W/m^2 from Beer's Law.
        diffuse_fraction: Fraction of light that is diffuse (0-1).
        rendering_config: Rendering configuration with sun parameters.
    """
    sun_path = rendering_config.sun_prim_path

    existing = stage.GetPrimAtPath(sun_path)
    if existing.IsValid():
        stage.RemovePrim(Sdf.Path(sun_path))

    sun = UsdLux.DistantLight.Define(stage, sun_path)

    df = _clamp_diffuse_fraction(diffuse_fraction)
    sun.GetIntensityAttr().Set(intensity * (1.0 - df) * rendering_config.sun_intensity_scale)

    r, g, b = rendering_config.sun_color
    sun.GetColorAttr().Set(Gf.Vec3f(r, g, b))

    sun.GetAngleAttr().Set(rendering_config.sun_angular_diameter_deg)

    # Orient light by azimuth and elevation
    xform = UsdGeom.Xformable(sun.GetPrim())
    xform.ClearXformOpOrder()
    rot_op = xform.AddRotateXYZOp()
    rot_op.Set(Gf.Vec3f(-(90.0 - sun_pos.elevation_deg), 0.0, sun_pos.azimuth_deg))


def update_sun_light(
    stage,
    sun_pos: SunPosition,
    intensity: float,
    diffuse_fraction: float,
    rendering_config: RenderingConfig,
) -> None:
    """Update an existing sun light's position and intensity.

    Unlike configure_sun_light(), this function modifies existing USD prim
    attributes in-place rather than deleting and recreating the prim.
    This avoids flicker during the dynamic atmosphere render loop.

    Falls back to configure_sun_light() if the prim does not exist.

    The ``diffuse_fraction`` (from COMIMART) is applied here as
    ``intensity_direct = intensity * (1 - diffuse_fraction)``. The matching
    diffuse term ``intensity * diffuse_fraction`` is applied in
    :func:`marslab.rendering.sky_renderer.configure_sky_dome` so the total
    emitted energy budget matches Beer's law and avoids double-counting the
    direct + diffuse partition.

    Args:
        stage: USD stage.
        sun_pos: Updated sun position.
        intensity: Updated direct beam irradiance in W/m^2.
        diffuse_fraction: Updated diffuse fraction (0-1).
        rendering_config: Rendering configuration with sun parameters.
    """
    sun_path = rendering_config.sun_prim_path
    prim = stage.GetPrimAtPath(sun_path)

    if not prim.IsValid():
        configure_sun_light(stage, sun_pos, intensity, diffuse_fraction, rendering_config)
        return

    sun = UsdLux.DistantLight(prim)
    df = _clamp_diffuse_fraction(diffuse_fraction)
    sun.GetIntensityAttr().Set(intensity * (1.0 - df) * rendering_config.sun_intensity_scale)

    r, g, b = rendering_config.sun_color
    sun.GetColorAttr().Set(Gf.Vec3f(r, g, b))

    # Update rotation in-place
    xform = UsdGeom.Xformable(prim)
    ops = xform.GetOrderedXformOps()
    if ops:
        ops[0].Set(Gf.Vec3f(-(90.0 - sun_pos.elevation_deg), 0.0, sun_pos.azimuth_deg))
    else:
        rot_op = xform.AddRotateXYZOp()
        rot_op.Set(Gf.Vec3f(-(90.0 - sun_pos.elevation_deg), 0.0, sun_pos.azimuth_deg))
