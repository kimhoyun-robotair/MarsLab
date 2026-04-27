"""Internal PBR shader-input helpers shared between terrain and rock material wiring.

Used by material_applicator (terrain mesh PBR) and rock_instancer (rock cluster PBR).

Both call sites previously open-coded an identical three-step wiring sequence
(albedo via OmniPBR wrapper, then normal/roughness via direct UsdShade shader
inputs). This module collapses that sequence into a single entry point so the
shader-input names, asset-path conversion, and roughness influence factor live
in one place.
"""

from __future__ import annotations

import os
from typing import Any


def apply_pbr_textures(
    material: Any,
    texture_dir: str,
    project_uvw: bool = True,
) -> None:
    """Apply PBR textures (albedo + normal + roughness) to an OmniPBR material.

    Looks for ``albedo.png``, ``normal.png``, ``roughness.png`` under
    ``texture_dir``. Existing files are bound to the corresponding
    OmniPBR shader inputs; missing files are silently skipped (the
    material falls back to its base color / scalar values).

    Albedo is wired through the OmniPBR Python wrapper
    (``set_texture`` + ``set_project_uvw``). Normal and roughness maps
    are bound directly on the underlying ``UsdShade.Shader`` because
    the OmniPBR wrapper does not expose dedicated setters for them.
    The shader-input names (``normalmap_texture``,
    ``reflectionroughness_texture``,
    ``reflection_roughness_texture_influence``) match the OmniPBR.mdl
    schema shipped with Isaac Sim.

    Args:
        material: An ``isaacsim.core.api.materials.omni_pbr.OmniPBR``
            instance (or duck-type compatible mock). The Isaac Sim
            import is deferred to the call site.
        texture_dir: Directory containing the PBR maps. Missing
            directory is treated the same as missing files.
        project_uvw: If True, sets the world-space UVW projection flag
            on the material via ``set_project_uvw(True)`` (recommended
            for meshes without authored UVs, e.g. rock prototypes). If
            False, calls ``set_project_uvw(False)`` so authored UVs are
            used (recommended for terrain meshes with explicit UV
            coordinates).

    Returns:
        None.
    """
    # pxr.Sdf is only available inside Isaac Sim runtime; import lazily
    # so this module remains importable from offline unit tests that
    # mock ``material``.
    from pxr import Sdf  # noqa: PLC0415

    # Albedo / diffuse texture via OmniPBR wrapper. The wrapper also
    # owns the UV-projection flag, so we always pair the two calls.
    albedo_path = os.path.join(texture_dir, "albedo.png")
    if os.path.isfile(albedo_path):
        material.set_texture(os.path.abspath(albedo_path))
        material.set_project_uvw(bool(project_uvw))

    shader = material.shaders_list[0]

    # Normal map (OmniPBR.mdl input: normalmap_texture).
    normal_path = os.path.join(texture_dir, "normal.png")
    if os.path.isfile(normal_path):
        shader.CreateInput("normalmap_texture", Sdf.ValueTypeNames.Asset).Set(
            Sdf.AssetPath(os.path.abspath(normal_path))
        )

    # Roughness map (OmniPBR.mdl input: reflectionroughness_texture).
    # The companion influence factor must be set to 1.0 to actually
    # sample the texture; without it OmniPBR keeps the scalar
    # roughness constant.
    roughness_path = os.path.join(texture_dir, "roughness.png")
    if os.path.isfile(roughness_path):
        shader.CreateInput("reflectionroughness_texture", Sdf.ValueTypeNames.Asset).Set(
            Sdf.AssetPath(os.path.abspath(roughness_path))
        )
        shader.CreateInput("reflection_roughness_texture_influence", Sdf.ValueTypeNames.Float).Set(
            1.0
        )
