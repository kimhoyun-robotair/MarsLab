"""Mars PBR material applicator for terrain meshes.

Applies physically-based rendering materials to terrain using Isaac Sim's
OmniPBR shader. Supports both simple color mode and full PBR texture mode.
Requires Isaac Sim runtime — do NOT import from offline code.
"""

import os

import numpy as np
from isaacsim.core.api.materials.omni_pbr import OmniPBR
from pxr import UsdShade


def apply_terrain_material(
    stage,
    mesh_prim_path: str,
    albedo_range: tuple[float, float],
    seed: int,
    texture_dir: str | None = None,
) -> None:
    """Apply a Mars-like PBR material to a terrain mesh.

    If texture_dir is provided and contains texture files, applies full
    PBR textures (albedo, normal, roughness). Otherwise falls back to
    simple albedo-derived color.

    Args:
        stage: USD stage.
        mesh_prim_path: Path to the terrain mesh prim.
        albedo_range: (min, max) surface albedo for color derivation.
        seed: Random seed for albedo sampling.
        texture_dir: Optional path to PBR texture directory containing
            albedo.png, normal.png, roughness.png files.

    Raises:
        ValueError: If albedo_range is invalid.
    """
    if albedo_range[0] >= albedo_range[1]:
        raise ValueError(f"albedo_range must be (min, max), got {albedo_range}")
    if not (0.0 <= albedo_range[0] <= 1.0 and 0.0 <= albedo_range[1] <= 1.0):
        raise ValueError(f"albedo values must be in [0, 1], got {albedo_range}")

    rng = np.random.default_rng(seed)
    albedo = rng.uniform(albedo_range[0], albedo_range[1])

    # Mars regolith color: reddish-brown scaled by albedo
    color = np.array([albedo * 2.5, albedo * 1.8, albedo * 1.2])
    color = np.clip(color, 0.0, 1.0)

    material_path = mesh_prim_path + "/material"
    material = OmniPBR(prim_path=material_path, name="mars_terrain")
    material.set_color(color)
    material.set_reflection_roughness(0.8)
    material.set_metallic_constant(0.0)

    # Apply PBR textures if available
    if texture_dir and os.path.isdir(texture_dir):
        _apply_textures(material, texture_dir)

    # Bind material to mesh
    mesh_prim = stage.GetPrimAtPath(mesh_prim_path)
    if mesh_prim.IsValid():
        UsdShade.MaterialBindingAPI.Apply(mesh_prim)
        binding = UsdShade.MaterialBindingAPI(mesh_prim)
        mat_prim = stage.GetPrimAtPath(material_path)
        if mat_prim.IsValid():
            binding.Bind(UsdShade.Material(mat_prim))


def _apply_textures(material: OmniPBR, texture_dir: str) -> None:
    """Apply PBR texture files to an OmniPBR material.

    Looks for albedo.png, normal.png, roughness.png in texture_dir.

    Args:
        material: OmniPBR material instance.
        texture_dir: Directory containing texture files.
    """
    # OmniPBR.set_texture() only supports albedo/diffuse texture.
    # Normal and roughness maps require direct UsdShade graph manipulation
    # which is deferred to Phase B+ quality refinement.
    albedo_path = os.path.join(texture_dir, "albedo.png")
    if os.path.isfile(albedo_path):
        material.set_texture(os.path.abspath(albedo_path))
        material.set_project_uvw(True)
