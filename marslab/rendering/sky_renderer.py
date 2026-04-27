"""Mars sky dome light configuration for Isaac Sim.

Creates a UsdLux DomeLight with Mars-appropriate color and brightness
derived from the environment module's SkyDomeParams.
Requires Isaac Sim runtime.
"""

import os

from pxr import Gf, Sdf, UsdLux

from marslab.config.schema import RenderingConfig
from marslab.environment.sky_dome import SkyDomeParams


def configure_sky_dome(
    stage,
    sky_params: SkyDomeParams,
    diffuse_fraction: float,
    rendering_config: RenderingConfig,
) -> None:
    """Configure a dome light for the Mars sky.

    Dome light intensity is scaled by diffuse_fraction to represent
    the proportion of irradiance arriving as scattered skylight.
    All scaling factors are read from ``rendering_config``.

    Args:
        stage: USD stage.
        sky_params: Sky dome parameters from compute_sky_dome_params().
        diffuse_fraction: Fraction of total irradiance that is diffuse (0-1).
        rendering_config: Rendering configuration with dome parameters.
    """
    dome_path = rendering_config.dome_prim_path

    existing = stage.GetPrimAtPath(dome_path)
    if existing.IsValid():
        stage.RemovePrim(Sdf.Path(dome_path))

    dome = UsdLux.DomeLight.Define(stage, dome_path)

    r, g, b = sky_params.base_color_rgb
    dome.GetColorAttr().Set(Gf.Vec3f(r, g, b))

    base_intensity = sky_params.brightness * rendering_config.dome_brightness_scale
    dome.GetIntensityAttr().Set(base_intensity * diffuse_fraction)

    # Apply HDRI texture if file exists
    if sky_params.hdri_texture_path and os.path.isfile(sky_params.hdri_texture_path):
        dome.GetTextureFileAttr().Set(sky_params.hdri_texture_path)


def update_sky_dome(
    stage,
    sky_params: SkyDomeParams,
    diffuse_fraction: float,
    rendering_config: RenderingConfig,
) -> None:
    """Update an existing dome light's color and intensity.

    Unlike configure_sky_dome(), this function modifies existing USD prim
    attributes in-place rather than deleting and recreating the prim.
    This avoids flicker during the dynamic atmosphere render loop.

    Falls back to configure_sky_dome() if the prim does not exist.

    Args:
        stage: USD stage.
        sky_params: Updated sky dome parameters.
        diffuse_fraction: Updated diffuse fraction (0-1).
        rendering_config: Rendering configuration with dome parameters.
    """
    dome_path = rendering_config.dome_prim_path
    prim = stage.GetPrimAtPath(dome_path)

    if not prim.IsValid():
        configure_sky_dome(stage, sky_params, diffuse_fraction, rendering_config)
        return

    dome = UsdLux.DomeLight(prim)

    r, g, b = sky_params.base_color_rgb
    dome.GetColorAttr().Set(Gf.Vec3f(r, g, b))

    base_intensity = sky_params.brightness * rendering_config.dome_brightness_scale
    dome.GetIntensityAttr().Set(base_intensity * diffuse_fraction)
