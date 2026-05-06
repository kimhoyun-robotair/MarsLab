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
from typing import Optional

from marslab.config.schema import SkyDomeConfig

_DEFAULT_SKY_DOME_CONFIG = SkyDomeConfig()


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


def compute_sky_dome_params(
    tau: float,
    hdri_dir: str,
    sky_cfg: Optional[SkyDomeConfig] = None,
) -> SkyDomeParams:
    """Compute sky dome parameters from dust optical depth.

    Interpolates between clear-sky butterscotch and dusty-sky colors
    based on tau. Brightness decreases with higher tau as more light
    is scattered and absorbed.

    Args:
        tau: Dust optical depth (>= 0).
        hdri_dir: Directory containing HDRI sky textures.
        sky_cfg: Sky-dome sub-config carrying the interpolation endpoints
            and brightness ramp coefficients. When ``None`` a
            ``SkyDomeConfig()`` with default values is used.

    Returns:
        SkyDomeParams with color, brightness, and texture path.

    Raises:
        ValueError: If tau is negative.
    """
    if tau < 0:
        raise ValueError(f"tau must be >= 0, got {tau}")

    cfg = sky_cfg if sky_cfg is not None else _DEFAULT_SKY_DOME_CONFIG

    # Interpolation factor: 0 at tau=0 (clear), 1 at tau>=3.0 (dusty)
    t = min(tau / 3.0, 1.0)

    clear = cfg.clear_rgb
    dusty = cfg.dusty_rgb
    r = clear[0] + t * (dusty[0] - clear[0])
    g = clear[1] + t * (dusty[1] - clear[1])
    b = clear[2] + t * (dusty[2] - clear[2])

    # Brightness: high at low tau, drops at high tau.
    brightness = max(cfg.brightness_min, 1.0 - cfg.brightness_decay * t)

    # Select HDRI by tau range. Filenames live in ``SkyDomeConfig`` so a
    # different HDRI set can be plugged in via YAML without source edit.
    if tau < 0.5:
        hdri_name = cfg.hdri_clear
    elif tau < 1.5:
        hdri_name = cfg.hdri_moderate
    else:
        hdri_name = cfg.hdri_dusty

    hdri_path = os.path.join(hdri_dir, hdri_name)

    return SkyDomeParams(
        base_color_rgb=(r, g, b),
        brightness=brightness,
        hdri_texture_path=hdri_path,
    )
