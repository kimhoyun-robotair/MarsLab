"""RTX render mode configuration for Isaac Sim.

Switches between path-tracing (data generation) and ray-tracing (interactive).
Requires Isaac Sim runtime.
"""

import carb


def set_render_mode(mode: str) -> None:
    """Configure RTX rendering mode.

    Args:
        mode: Either 'path_tracing' (photorealistic, slow) or
            'ray_tracing' (real-time, fast).

    Raises:
        ValueError: If mode is not recognized.
    """
    if mode not in ("path_tracing", "ray_tracing"):
        raise ValueError(f"Unknown render mode '{mode}', expected: path_tracing, ray_tracing")

    settings = carb.settings.get_settings()

    if mode == "path_tracing":
        settings.set("/rtx/rendermode", "PathTracing")
        settings.set("/rtx/pathtracing/spp", 64)
        settings.set("/rtx/pathtracing/totalSpp", 256)
        settings.set("/rtx/pathtracing/maxBounces", 8)
        settings.set("/rtx/pathtracing/optixDenoiser/enabled", True)
    else:
        settings.set("/rtx/rendermode", "RayTracedLighting")
        settings.set("/rtx/shadows/enabled", True)
        settings.set("/rtx/reflections/enabled", True)
        settings.set("/rtx/directLighting/enabled", True)
