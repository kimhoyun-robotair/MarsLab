"""Mars PBR material applicator for terrain meshes.

Applies physically-based rendering materials to terrain using Isaac Sim's
OmniPBR shader. Requires Isaac Sim runtime — do NOT import from offline code.
"""

import numpy as np
from isaacsim.core.api.materials.omni_pbr import OmniPBR
from pxr import UsdShade


def apply_terrain_material(
    stage,
    mesh_prim_path: str,
    albedo_range: tuple[float, float],
    seed: int,
) -> None:
    """Apply a Mars-like PBR material to a terrain mesh.

    Creates an OmniPBR material with Mars regolith appearance and binds
    it to the specified mesh prim.

    Args:
        stage: USD stage.
        mesh_prim_path: Path to the terrain mesh prim.
        albedo_range: (min, max) surface albedo for color derivation.
            Mars range: [0.10, 0.40].
        seed: Random seed for albedo sampling.

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
    # Base hue ratios from Mars surface spectroscopy (approximate)
    color = np.array([albedo * 2.5, albedo * 1.8, albedo * 1.2])
    color = np.clip(color, 0.0, 1.0)

    material_path = mesh_prim_path + "/material"
    material = OmniPBR(prim_path=material_path, name="mars_terrain")
    material.set_color(color)
    material.set_reflection_roughness(0.8)
    material.set_metallic_constant(0.0)

    # Bind material to mesh
    mesh_prim = stage.GetPrimAtPath(mesh_prim_path)
    if mesh_prim.IsValid():
        UsdShade.MaterialBindingAPI.Apply(mesh_prim)
        binding = UsdShade.MaterialBindingAPI(mesh_prim)
        mat_prim = stage.GetPrimAtPath(material_path)
        if mat_prim.IsValid():
            binding.Bind(UsdShade.Material(mat_prim))
