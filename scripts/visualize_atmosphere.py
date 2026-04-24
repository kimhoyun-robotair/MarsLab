"""Offline atmosphere visualization for developer review.

Generates four plots without Isaac Sim:
    1. Direct intensity vs tau (Beer's Law)
    2. Diffuse fraction vs tau (COMIMART)
    3. Sky color swatches across tau values
    4. Total irradiance breakdown (direct + diffuse) vs tau

Run: python3 scripts/visualize_atmosphere.py

Output: work_log/atmosphere_visualization.png
"""

import math
import os

import matplotlib.pyplot as plt
import numpy as np

from marslab.config.loader import load_and_validate
from marslab.environment.diffuse_fraction import compute_diffuse_fraction
from marslab.environment.light_intensity import compute_direct_intensity
from marslab.environment.sky_dome import compute_sky_dome_params

# Lowest tau plotted in the sweeps.  Kept as a module-level constant because
# it anchors the figure's horizontal axis, not the physics.  The upper bound
# comes from ``mars_env.dust_opacity_range`` (configs/mars_env.yaml) so the
# R3 G5 literal migration only removes values that belong to the physics.
_PLOT_TAU_MIN = 0.05
_PLOT_TAU_SAMPLES = 100


def main() -> None:
    """Generate atmosphere visualization plots."""
    cfg = load_and_validate("configs/mars_env.yaml")
    solar_constant = cfg.mars_env.solar_constant_mean
    zenith = math.radians(90.0 - cfg.mars_env.sun_elevation_deg)
    tau_hi = cfg.mars_env.dust_opacity_range[1]
    taus = np.linspace(_PLOT_TAU_MIN, tau_hi, _PLOT_TAU_SAMPLES)

    direct = [compute_direct_intensity(solar_constant, t, zenith) for t in taus]
    diffuse_frac = [compute_diffuse_fraction(t) for t in taus]

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Plot 1: Direct intensity vs tau
    ax1 = axes[0, 0]
    ax1.plot(taus, direct, "b-", linewidth=2)
    ax1.set_title("Direct Beam Irradiance (Beer's Law)")
    ax1.set_xlabel("Dust Optical Depth (tau)")
    ax1.set_ylabel("Irradiance (W/m²)")
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=0, color="k", linewidth=0.5)

    # Plot 2: Diffuse fraction vs tau
    ax2 = axes[0, 1]
    ax2.plot(taus, diffuse_frac, "r-", linewidth=2)
    ax2.axhspan(0.29, 0.38, alpha=0.2, color="green", label="tau=0.3 range")
    ax2.axhspan(0.50, 0.53, alpha=0.2, color="orange", label="tau=1.0 range")
    ax2.set_title("Diffuse Fraction (COMIMART)")
    ax2.set_xlabel("Dust Optical Depth (tau)")
    ax2.set_ylabel("Diffuse Fraction")
    ax2.legend(fontsize=8)
    ax2.grid(True, alpha=0.3)

    # Plot 3: Sky color swatches
    ax3 = axes[1, 0]
    swatch_taus = [0.1, 0.3, 0.5, 1.0, 1.5, 2.0, 3.0]
    for i, t in enumerate(swatch_taus):
        sky = compute_sky_dome_params(t, "assets/sky/hdri/")
        color = sky.base_color_rgb
        ax3.barh(i, 1, color=color, edgecolor="black", linewidth=0.5)
        ax3.text(
            0.5, i, f"tau={t:.1f}  B={sky.brightness:.2f}", ha="center", va="center", fontsize=9
        )
    ax3.set_yticks(range(len(swatch_taus)))
    ax3.set_yticklabels([f"tau={t}" for t in swatch_taus])
    ax3.set_xlim(0, 1)
    ax3.set_title("Mars Sky Color by Tau")
    ax3.set_xlabel("")
    ax3.tick_params(bottom=False, labelbottom=False)

    # Plot 4: Total irradiance breakdown
    ax4 = axes[1, 1]
    direct_part = list(direct)
    total = [
        d / (1.0 - df) if df < 1.0 else d for d, df in zip(direct_part, diffuse_frac, strict=False)
    ]

    ax4.fill_between(taus, 0, direct_part, alpha=0.6, label="Direct", color="gold")
    ax4.fill_between(taus, direct_part, total, alpha=0.6, label="Diffuse", color="lightskyblue")
    ax4.plot(taus, total, "k-", linewidth=1.5, label="Total")
    ax4.set_title("Irradiance Breakdown")
    ax4.set_xlabel("Dust Optical Depth (tau)")
    ax4.set_ylabel("Irradiance (W/m²)")
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    os.makedirs("work_log", exist_ok=True)
    fig.tight_layout()
    fig.savefig("work_log/atmosphere_visualization.png", dpi=150)
    plt.close(fig)
    print("Saved: work_log/atmosphere_visualization.png")


if __name__ == "__main__":
    main()
