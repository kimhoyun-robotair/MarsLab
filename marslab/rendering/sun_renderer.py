"""Apply direct normal irradiance to the Mars directional light."""

from marslab.config.schema import RenderingConfig
from marslab.environment.sun_position import SunPosition


def configure_sun_light(
    stage,
    sun_pos: SunPosition,
    intensity: float,
    rendering_config: RenderingConfig,
) -> None:
    """Create the configured sun using the same conversion as live updates."""
    from pxr import Sdf

    path = rendering_config.sun_prim_path
    if stage.GetPrimAtPath(path).IsValid():
        stage.RemovePrim(Sdf.Path(path))
    update_sun_light(stage, sun_pos, intensity, rendering_config)


def update_sun_light(
    stage,
    sun_pos: SunPosition,
    intensity: float,
    rendering_config: RenderingConfig,
) -> None:
    """Update DNI gain and sun orientation in place, without another diffuse split."""
    from pxr import Gf, UsdGeom, UsdLux

    sun = UsdLux.DistantLight.Define(stage, rendering_config.sun_prim_path)
    sun.GetIntensityAttr().Set(intensity * rendering_config.sun_intensity_scale)
    sun.GetColorAttr().Set(Gf.Vec3f(*rendering_config.sun_color))
    sun.GetAngleAttr().Set(rendering_config.sun_angular_diameter_deg)
    xform = UsdGeom.Xformable(sun.GetPrim())
    ops = xform.GetOrderedXformOps()
    rotation = ops[0] if ops else xform.AddRotateXYZOp()
    # ENU: north is +Y, east is +X; compass azimuth increases clockwise.
    rotation.Set(Gf.Vec3f(sun_pos.elevation_deg - 90.0, 0.0, -sun_pos.azimuth_deg))
