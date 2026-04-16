"""Mars sun (directional light) configuration for Isaac Sim.

Creates a UsdLux DistantLight oriented by the sun position with
intensity derived from Beer's Law computation.
Requires Isaac Sim runtime.
"""

from pxr import Gf, Sdf, UsdGeom, UsdLux

from marslab.config.schema import RenderingConfig
from marslab.environment.sun_position import SunPosition


def configure_sun_light(
    stage,
    sun_pos: SunPosition,
    intensity: float,
    diffuse_fraction: float,
    rendering_config: RenderingConfig,
) -> None:
    """Configure a directional light representing the Mars sun.

    All scaling factors and colors are read from rendering_config (G5).

    Args:
        stage: USD stage.
        sun_pos: Sun position (azimuth, elevation, zenith).
        intensity: Direct beam irradiance in W/m^2 from Beer's Law.
        diffuse_fraction: Fraction of light that is diffuse (0-1).
        rendering_config: Rendering configuration with sun parameters.
    """
    sun_path = "/World/SunLight"

    existing = stage.GetPrimAtPath(sun_path)
    if existing.IsValid():
        stage.RemovePrim(Sdf.Path(sun_path))

    sun = UsdLux.DistantLight.Define(stage, sun_path)

    sun.GetIntensityAttr().Set(intensity * rendering_config.sun_intensity_scale)

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

    Args:
        stage: USD stage.
        sun_pos: Updated sun position.
        intensity: Updated direct beam irradiance in W/m^2.
        diffuse_fraction: Updated diffuse fraction (0-1).
        rendering_config: Rendering configuration with sun parameters.
    """
    sun_path = "/World/SunLight"
    prim = stage.GetPrimAtPath(sun_path)

    if not prim.IsValid():
        configure_sun_light(stage, sun_pos, intensity, diffuse_fraction, rendering_config)
        return

    sun = UsdLux.DistantLight(prim)
    sun.GetIntensityAttr().Set(intensity * rendering_config.sun_intensity_scale)

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
