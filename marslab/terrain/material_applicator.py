"""Mars PBR material applicator for terrain meshes.

Applies physically-based rendering materials to terrain using Isaac Sim's
OmniPBR shader. Supports both simple color mode and full PBR texture mode.
Requires Isaac Sim runtime — do NOT import from offline code.
"""

import os

import numpy as np
from isaacsim.core.api.materials.omni_pbr import OmniPBR
from pxr import Sdf, UsdShade


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
    """Apply full PBR texture set to an OmniPBR material.

    Applies albedo via OmniPBR wrapper, and normal/roughness maps
    via direct UsdShade shader input (OmniPBR.mdl input names).
    Texture directory is swappable via YAML config (G5).

    Args:
        material: OmniPBR material instance.
        texture_dir: Directory containing albedo.png, normal.png, roughness.png.
    """
    shader = material.shaders_list[0]  # Direct access to UsdShade.Shader

    # Albedo/diffuse texture (via OmniPBR wrapper)
    albedo_path = os.path.join(texture_dir, "albedo.png")
    if os.path.isfile(albedo_path):
        material.set_texture(os.path.abspath(albedo_path))
        material.set_project_uvw(False)  # Use mesh UV coords (uv_scale=1.0 for 1:1)

    # Normal map (direct UsdShade — OmniPBR.mdl input: normalmap_texture)
    normal_path = os.path.join(texture_dir, "normal.png")
    if os.path.isfile(normal_path):
        shader.CreateInput("normalmap_texture", Sdf.ValueTypeNames.Asset).Set(
            Sdf.AssetPath(os.path.abspath(normal_path))
        )

    # Roughness map (direct UsdShade — OmniPBR.mdl input: reflectionroughness_texture)
    roughness_path = os.path.join(texture_dir, "roughness.png")
    if os.path.isfile(roughness_path):
        shader.CreateInput("reflectionroughness_texture", Sdf.ValueTypeNames.Asset).Set(
            Sdf.AssetPath(os.path.abspath(roughness_path))
        )
        shader.CreateInput("reflection_roughness_texture_influence", Sdf.ValueTypeNames.Float).Set(
            1.0
        )
