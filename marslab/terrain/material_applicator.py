"""Mars PBR material applicator for terrain meshes.

Applies physically-based rendering materials to terrain using Isaac
Sim's OmniPBR shader. Supports both simple color mode and full PBR
texture mode. Requires Isaac Sim runtime -- do NOT import from offline
code.
"""

import os

import numpy as np
from isaacsim.core.api.materials.omni_pbr import OmniPBR
from pxr import UsdShade

from marslab.terrain._pbr_helpers import apply_pbr_textures

# RGB channel multipliers applied to a sampled scalar albedo to fake a
# Mars regolith colour cast without paying for a full spectroscopic
# render. Mars regolith spectroscopy ratios; tunable for paper figures.
TERRAIN_REGOLITH_RGB_RATIO: tuple[float, float, float] = (2.5, 1.8, 1.2)
# Cave interior basalt is unoxidised, so the colour is gray-black with
# the red channel only marginally above blue. Mars basalt spectroscopy
# ratios; tunable for paper figures.
CAVE_BASALT_RGB_RATIO: tuple[float, float, float] = (1.2, 1.0, 0.9)


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
    r_mul, g_mul, b_mul = TERRAIN_REGOLITH_RGB_RATIO
    color = np.array([albedo * r_mul, albedo * g_mul, albedo * b_mul])
    color = np.clip(color, 0.0, 1.0)

    material_path = mesh_prim_path + "/material"
    material = OmniPBR(prim_path=material_path, name="mars_terrain")
    material.set_color(color)
    material.set_reflection_roughness(0.8)
    material.set_metallic_constant(0.0)

    # Apply PBR textures if available. Terrain meshes carry authored
    # UV coordinates (uv_scale=1.0 for 1:1 sampling), so disable
    # world-space UVW projection.
    if texture_dir and os.path.isdir(texture_dir):
        apply_pbr_textures(material, texture_dir, project_uvw=False)

    # Bind material to mesh
    mesh_prim = stage.GetPrimAtPath(mesh_prim_path)
    if mesh_prim.IsValid():
        UsdShade.MaterialBindingAPI.Apply(mesh_prim)
        binding = UsdShade.MaterialBindingAPI(mesh_prim)
        mat_prim = stage.GetPrimAtPath(material_path)
        if mat_prim.IsValid():
            binding.Bind(UsdShade.Material(mat_prim))


def apply_cave_material(
    stage,
    mesh_prim_path: str,
    albedo_range: tuple[float, float] = (0.05, 0.15),
    seed: int = 42,
    texture_dir: str | None = None,
) -> None:
    """Apply dark basalt PBR material for cave interior surfaces.

    Cave walls/ceiling use much darker albedo than surface terrain
    (unoxidized basalt). Color is gray-black instead of reddish-brown.

    Args:
        stage: USD stage.
        mesh_prim_path: Path to the cave mesh prim.
        albedo_range: (min, max) albedo for dark basalt (0.05-0.15).
        seed: Random seed for albedo sampling.
        texture_dir: Optional path to PBR texture directory.
    """
    if albedo_range[0] >= albedo_range[1]:
        raise ValueError(f"albedo_range must be (min, max), got {albedo_range}")
    if not (0.0 <= albedo_range[0] <= 1.0 and 0.0 <= albedo_range[1] <= 1.0):
        raise ValueError(f"albedo values must be in [0, 1], got {albedo_range}")

    rng = np.random.default_rng(seed)
    albedo = rng.uniform(albedo_range[0], albedo_range[1])

    # Cave interior: gray-black basalt (not reddish -- unoxidised)
    r_mul, g_mul, b_mul = CAVE_BASALT_RGB_RATIO
    color = np.array([albedo * r_mul, albedo * g_mul, albedo * b_mul])
    color = np.clip(color, 0.0, 1.0)

    material_path = mesh_prim_path + "/cave_material"
    material = OmniPBR(prim_path=material_path, name="cave_basalt")
    material.set_color(color)
    material.set_reflection_roughness(0.85)
    material.set_metallic_constant(0.0)

    if texture_dir and os.path.isdir(texture_dir):
        apply_pbr_textures(material, texture_dir, project_uvw=False)

    mesh_prim = stage.GetPrimAtPath(mesh_prim_path)
    if mesh_prim.IsValid():
        UsdShade.MaterialBindingAPI.Apply(mesh_prim)
        binding = UsdShade.MaterialBindingAPI(mesh_prim)
        mat_prim = stage.GetPrimAtPath(material_path)
        if mat_prim.IsValid():
            binding.Bind(UsdShade.Material(mat_prim))
