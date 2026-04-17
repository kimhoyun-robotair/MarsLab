"""RTX render mode configuration for Isaac Sim.

Switches between path-tracing (data generation) and ray-tracing (interactive).
All parameters read from config (G5).
Requires Isaac Sim runtime.
"""

import carb

from marslab.config.schema import RenderingConfig


def set_render_mode(rendering_config: RenderingConfig) -> None:
    """Configure RTX rendering mode from config.

    Args:
        rendering_config: Rendering configuration with mode and quality params.

    Raises:
        ValueError: If mode is not recognized.
    """
    mode = rendering_config.mode
    if mode not in ("path_tracing", "ray_tracing"):
        raise ValueError(f"Unknown render mode '{mode}', expected: path_tracing, ray_tracing")

    settings = carb.settings.get_settings()

    if mode == "path_tracing":
        settings.set("/rtx/rendermode", "PathTracing")
        settings.set("/rtx/pathtracing/spp", rendering_config.spp)
        settings.set("/rtx/pathtracing/totalSpp", rendering_config.total_spp)
        settings.set("/rtx/pathtracing/maxBounces", rendering_config.max_bounces)
        settings.set("/rtx/pathtracing/optixDenoiser/enabled", True)
    else:
        settings.set("/rtx/rendermode", "RayTracedLighting")
        settings.set("/rtx/shadows/enabled", True)
        settings.set("/rtx/reflections/enabled", True)
        settings.set("/rtx/directLighting/enabled", True)
        # Post-processing: denoise Monte Carlo variance and apply DLSS Quality
        # AA. Operates on pixel space after radiance is computed, so Mars
        # atmospheric physics (Beer's law, COMIMART, dust scattering) in
        # marslab/environment/* is untouched.
        settings.set("/rtx/indirectDiffuse/denoiser/enabled", True)
        settings.set("/rtx/reflections/denoiser/enabled", True)
        settings.set("/rtx/post/aa/op", 3)
        settings.set("/rtx/post/dlss/execMode", 1)
