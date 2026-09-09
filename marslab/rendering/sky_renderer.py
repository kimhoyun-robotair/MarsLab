"""Apply the tau-indexed sky fraction and appearance to the dome light."""

import warnings
from pathlib import Path

from pxr import Gf, Sdf, UsdLux

from marslab.config.schema import RenderingConfig
from marslab.environment.sky_dome import SkyDomeParams


def configure_sky_dome(
    stage,
    sky_params: SkyDomeParams,
    diffuse_fraction: float,
    rendering_config: RenderingConfig,
) -> None:
    """Create the dome using the same sky fraction and texture as live updates."""
    path = rendering_config.dome_prim_path
    if stage.GetPrimAtPath(path).IsValid():
        stage.RemovePrim(Sdf.Path(path))
    update_sky_dome(stage, sky_params, diffuse_fraction, rendering_config)


def update_sky_dome(
    stage,
    sky_params: SkyDomeParams,
    diffuse_fraction: float,
    rendering_config: RenderingConfig,
) -> None:
    """Apply the retained sky scale and replace or clear the texture in place."""
    dome = UsdLux.DomeLight.Define(stage, rendering_config.dome_prim_path)
    dome.GetColorAttr().Set(Gf.Vec3f(*sky_params.base_color_rgb))
    dome.GetIntensityAttr().Set(
        diffuse_fraction * sky_params.brightness * rendering_config.dome_brightness_scale
    )
    texture = dome.GetTextureFileAttr()
    path = sky_params.hdri_texture_path
    if path and Path(path).is_file():
        texture.Set(path)
    else:
        texture.Clear()
        if path:
            warnings.warn(f"Sky texture missing: {Path(path).name}", RuntimeWarning, stacklevel=2)
