"""Mars sky dome light configuration for Isaac Sim.

Creates a UsdLux DomeLight with Mars-appropriate color and brightness
derived from the environment module's SkyDomeParams.
Requires Isaac Sim runtime.
"""

import os

from pxr import Gf, Sdf, UsdLux

from marslab.environment.sky_dome import SkyDomeParams


def configure_sky_dome(stage, sky_params: SkyDomeParams) -> None:
    """Configure a dome light for the Mars sky.

    Args:
        stage: USD stage.
        sky_params: Sky dome parameters from compute_sky_dome_params().
    """
    dome_path = "/World/DomeLight"

    # Remove existing dome light if present
    existing = stage.GetPrimAtPath(dome_path)
    if existing.IsValid():
        stage.RemovePrim(Sdf.Path(dome_path))

    dome = UsdLux.DomeLight.Define(stage, dome_path)

    r, g, b = sky_params.base_color_rgb
    dome.GetColorAttr().Set(Gf.Vec3f(r, g, b))
    dome.GetIntensityAttr().Set(sky_params.brightness * 1000.0)

    # Apply HDRI texture if file exists
    if sky_params.hdri_texture_path and os.path.isfile(sky_params.hdri_texture_path):
        dome.GetTextureFileAttr().Set(sky_params.hdri_texture_path)
