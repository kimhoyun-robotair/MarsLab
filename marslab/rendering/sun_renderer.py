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
