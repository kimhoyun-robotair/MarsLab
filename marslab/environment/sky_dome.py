"""Mars sky dome color and brightness computation.

Computes sky appearance parameters as a function of dust optical depth.
At low tau the Mars sky is the iconic butterscotch color; at high tau
the sky brightens and shifts toward uniform haze.

Reference:
    Bell et al. (2006). Chromaticity of the Martian sky as observed by
    the Mars Exploration Rover Pancam instruments. JGR Planets.
"""

import os
from dataclasses import dataclass

# Butterscotch sky at low tau (clear Mars sky, Bell et al. 2006)
_CLEAR_SKY_RGB = (0.76, 0.57, 0.35)

# Dusty sky at high tau (dust storm, washed out)
_DUSTY_SKY_RGB = (0.85, 0.75, 0.60)


@dataclass
class SkyDomeParams:
    """Parameters for configuring the sky dome in rendering.

    Attributes:
        base_color_rgb: Sky color as (R, G, B) in [0, 1] range.
        brightness: Sky dome brightness multiplier (0-1).
        hdri_texture_path: Path to HDRI texture file for the dome.
    """

    base_color_rgb: tuple[float, float, float]
    brightness: float
    hdri_texture_path: str


def compute_sky_dome_params(tau: float, hdri_dir: str) -> SkyDomeParams:
    """Compute sky dome parameters from dust optical depth.

    Interpolates between clear-sky butterscotch and dusty-sky colors
    based on tau. Brightness decreases with higher tau as more light
    is scattered and absorbed.

    Args:
        tau: Dust optical depth (>= 0).
        hdri_dir: Directory containing HDRI sky textures.

    Returns:
        SkyDomeParams with color, brightness, and texture path.

    Raises:
        ValueError: If tau is negative.
    """
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")

    # Interpolation factor: 0 at tau=0 (clear), 1 at tau>=3.0 (dusty)
    t = min(tau / 3.0, 1.0)

    r = _CLEAR_SKY_RGB[0] + t * (_DUSTY_SKY_RGB[0] - _CLEAR_SKY_RGB[0])
    g = _CLEAR_SKY_RGB[1] + t * (_DUSTY_SKY_RGB[1] - _CLEAR_SKY_RGB[1])
    b = _CLEAR_SKY_RGB[2] + t * (_DUSTY_SKY_RGB[2] - _CLEAR_SKY_RGB[2])

    # Brightness: high at low tau, drops at high tau
    brightness = max(0.1, 1.0 - 0.3 * t)

    # Select HDRI by tau range (placeholder paths — actual assets in Week 6)
    if tau < 0.5:
        hdri_name = "mars_sky_clear.hdr"
    elif tau < 1.5:
        hdri_name = "mars_sky_moderate.hdr"
    else:
        hdri_name = "mars_sky_dusty.hdr"

    hdri_path = os.path.join(hdri_dir, hdri_name)

    return SkyDomeParams(
        base_color_rgb=(r, g, b),
        brightness=brightness,
        hdri_texture_path=hdri_path,
    )
