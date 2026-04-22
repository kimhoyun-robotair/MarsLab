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

# R2-A1 (2026-04-22): the butterscotch / dusty endpoints and the
# brightness ramp coefficients moved to ``SkyDomeConfig`` so YAML
# controls them (G5). The literals are retained here as commented
# constants per feedback_no_delete_comment — they double as the pydantic
# defaults so the runtime behaviour is bit-for-bit identical.
# _CLEAR_SKY_RGB = (0.76, 0.57, 0.35)  # Bell et al. 2006 butterscotch
# _DUSTY_SKY_RGB = (0.85, 0.75, 0.60)  # dust-storm sky
# _BRIGHTNESS_MIN = 0.1                # clamp floor
# _BRIGHTNESS_DECAY = 0.3              # slope of 1 - decay * t

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
            and brightness ramp coefficients. When ``None`` (legacy call
            sites) a ``SkyDomeConfig()`` with the pre-R2-A1 defaults is
            used, so the Oracle ``run_stage3_monolithic.py`` signature
            ``compute_sky_dome_params(tau, hdri_dir)`` remains
            bit-for-bit identical.

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
    # Pre-R2-A1: brightness = max(0.1, 1.0 - 0.3 * t)
    brightness = max(cfg.brightness_min, 1.0 - cfg.brightness_decay * t)

    # Select HDRI by tau range (placeholder paths)
    if tau < 0.5:
        hdri_name = "mars_sky_clear.png"
    elif tau < 1.5:
        hdri_name = "mars_sky_moderate.png"
    else:
        hdri_name = "mars_sky_dusty.png"

    hdri_path = os.path.join(hdri_dir, hdri_name)

    return SkyDomeParams(
        base_color_rgb=(r, g, b),
        brightness=brightness,
        hdri_texture_path=hdri_path,
    )
