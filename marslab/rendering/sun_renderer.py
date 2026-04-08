"""Mars sun (directional light) configuration for Isaac Sim.

Creates a UsdLux DistantLight oriented by the sun position with
intensity derived from Beer's Law computation.
Requires Isaac Sim runtime.
"""


from pxr import Gf, Sdf, UsdGeom, UsdLux

from marslab.environment.sun_position import SunPosition


def configure_sun_light(
    stage,
    sun_pos: SunPosition,
    intensity: float,
    diffuse_fraction: float,
) -> None:
    """Configure a directional light representing the Mars sun.

    Args:
        stage: USD stage.
        sun_pos: Sun position (azimuth, elevation, zenith).
        intensity: Direct beam irradiance in W/m^2 from Beer's Law.
        diffuse_fraction: Fraction of light that is diffuse (0-1).
            Used to scale dome light contribution.
    """
    sun_path = "/World/SunLight"

    existing = stage.GetPrimAtPath(sun_path)
    if existing.IsValid():
        stage.RemovePrim(Sdf.Path(sun_path))

    sun = UsdLux.DistantLight.Define(stage, sun_path)

    # Scale intensity for Isaac Sim (W/m^2 → light units)
    sun.GetIntensityAttr().Set(intensity * 5.0)

    # Warm Mars sunlight color
    sun.GetColorAttr().Set(Gf.Vec3f(1.0, 0.95, 0.85))

    # Angular diameter of sun from Mars (~0.35 degrees)
    sun.GetAngleAttr().Set(0.35)

    # Orient light by azimuth and elevation
    xform = UsdGeom.Xformable(sun.GetPrim())
    xform.ClearXformOpOrder()

    # DistantLight default direction is -Z, so we rotate to match sun position
    rot_op = xform.AddRotateXYZOp()
    # X rotation = -(90 - elevation) to tilt from horizon
    # Z rotation = azimuth
    rot_op.Set(Gf.Vec3f(-(90.0 - sun_pos.elevation_deg), 0.0, sun_pos.azimuth_deg))
