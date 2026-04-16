"""Offline visualization of dynamic atmosphere parameters.

Generates a 4-panel figure showing the diurnal evolution of Mars
atmospheric parameters over one sol (no Isaac Sim required):

1. Sun trajectory: azimuth + elevation vs time-of-sol
2. Tau profiles: constant / ramp / sine comparison
3. Direct irradiance: Beer's Law intensity over sol
4. Sky color swatches: sky dome color at 6 time points

Usage:
    python3 scripts/visualize_dynamic_atmosphere.py
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from marslab.environment.light_intensity import compute_direct_intensity  # noqa: E402
from marslab.environment.sky_dome import compute_sky_dome_params  # noqa: E402
from marslab.environment.sun_position import compute_sol_sun_position  # noqa: E402
from marslab.environment.tau_profile import compute_tau  # noqa: E402

OUTPUT_DIR = os.path.join(REPO_ROOT, "work_log", "scene_generation")
OUTPUT_PNG = os.path.join(OUTPUT_DIR, "dynamic_atmosphere_visualization.png")

HDRI_DIR = os.path.join(REPO_ROOT, "assets", "sky", "hdri")
SOLAR_CONSTANT = 589.0  # W/m^2 at 1.52 AU


def main() -> None:
    t_values = np.linspace(0.0, 1.0, 200)

    # --- Panel 1: Sun trajectory ---
    azimuths = []
    elevations = []
    for t in t_values:
        pos = compute_sol_sun_position(t)
        azimuths.append(pos.azimuth_deg)
        elevations.append(pos.elevation_deg)

    # --- Panel 2: Tau profiles ---
    tau_constant = [compute_tau("constant", t, base_tau=0.3) for t in t_values]
    tau_ramp = [compute_tau("ramp", t, start_tau=0.3, end_tau=2.0) for t in t_values]
    tau_sine = [
        compute_tau("sine", t, base_tau=0.5, amplitude=0.3, period_fraction=1.0) for t in t_values
    ]

    # --- Panel 3: Direct irradiance ---
    intensity_const = []
    intensity_ramp = []
    for t in t_values:
        pos = compute_sol_sun_position(t)
        i_c = compute_direct_intensity(SOLAR_CONSTANT, 0.3, pos.zenith_angle_rad)
        i_r = compute_direct_intensity(
            SOLAR_CONSTANT,
            compute_tau("ramp", t, start_tau=0.3, end_tau=2.0),
            pos.zenith_angle_rad,
        )
        intensity_const.append(i_c)
        intensity_ramp.append(i_r)

    # --- Panel 4: Sky color swatches ---
    swatch_times = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    swatch_colors_const = []
    swatch_colors_ramp = []
    for t in swatch_times:
        tau_c = compute_tau("constant", min(t, 0.999), base_tau=0.3)
        tau_r = compute_tau("ramp", min(t, 0.999), start_tau=0.3, end_tau=2.0)
        sky_c = compute_sky_dome_params(tau_c, HDRI_DIR)
        sky_r = compute_sky_dome_params(tau_r, HDRI_DIR)
        swatch_colors_const.append(sky_c.base_color_rgb)
        swatch_colors_ramp.append(sky_r.base_color_rgb)

    # --- Plot ---
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Panel 1: Sun trajectory
    ax1 = axes[0, 0]
    ax1_twin = ax1.twinx()
    hours = t_values * 24.66  # Mars sol in hours
    ln1 = ax1.plot(hours, azimuths, "b-", label="Azimuth")
    ln2 = ax1_twin.plot(hours, elevations, "r-", label="Elevation")
    ax1.set_xlabel("Time of Sol (hours)")
    ax1.set_ylabel("Azimuth (deg)", color="b")
    ax1_twin.set_ylabel("Elevation (deg)", color="r")
    ax1.set_title("Sun Trajectory Over One Sol")
    lns = ln1 + ln2
    ax1.legend(lns, [line.get_label() for line in lns], loc="upper left")
    ax1.grid(True, alpha=0.3)

    # Panel 2: Tau profiles
    ax2 = axes[0, 1]
    ax2.plot(hours, tau_constant, "g-", label="Constant (tau=0.3)")
    ax2.plot(hours, tau_ramp, "r-", label="Ramp (0.3 -> 2.0)")
    ax2.plot(hours, tau_sine, "b-", label="Sine (0.5 +/- 0.3)")
    ax2.set_xlabel("Time of Sol (hours)")
    ax2.set_ylabel("Dust Optical Depth (tau)")
    ax2.set_title("Tau Profiles: Dust Storm Scenarios")
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim(0, 2.5)

    # Panel 3: Direct irradiance
    ax3 = axes[1, 0]
    ax3.plot(hours, intensity_const, "g-", label="Constant tau=0.3 (clear)")
    ax3.plot(hours, intensity_ramp, "r-", label="Ramp tau 0.3->2.0 (storm)")
    ax3.set_xlabel("Time of Sol (hours)")
    ax3.set_ylabel("Direct Irradiance (W/m^2)")
    ax3.set_title("Direct Solar Irradiance (Beer's Law)")
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim(0, 500)

    # Panel 4: Sky color swatches
    ax4 = axes[1, 1]
    ax4.set_title("Sky Dome Color Over Sol")
    ax4.set_xlim(0, len(swatch_times))
    ax4.set_ylim(0, 2)

    for i, t in enumerate(swatch_times):
        # Top row: constant tau
        c_const = swatch_colors_const[i]
        rect_const = plt.Rectangle((i, 1), 1, 1, facecolor=c_const, edgecolor="black")
        ax4.add_patch(rect_const)

        # Bottom row: ramp tau
        c_ramp = swatch_colors_ramp[i]
        rect_ramp = plt.Rectangle((i, 0), 1, 1, facecolor=c_ramp, edgecolor="black")
        ax4.add_patch(rect_ramp)

        ax4.text(i + 0.5, 2.05, f"t={t:.1f}", ha="center", va="bottom", fontsize=8)

    ax4.text(-0.3, 1.5, "Constant\ntau=0.3", ha="right", va="center", fontsize=8)
    ax4.text(-0.3, 0.5, "Ramp\n0.3->2.0", ha="right", va="center", fontsize=8)
    ax4.set_xticks([])
    ax4.set_yticks([])
    ax4.set_aspect("equal")

    fig.suptitle(
        "MarsLab Dynamic Atmosphere: Diurnal Cycle Over One Sol\n"
        "(Solar constant = 589 W/m^2, Jezero crater 18.4 deg N)",
        fontsize=13,
        fontweight="bold",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.94])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    fig.savefig(OUTPUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[visualize_dynamic_atmosphere] Saved: {OUTPUT_PNG}")


if __name__ == "__main__":
    main()
