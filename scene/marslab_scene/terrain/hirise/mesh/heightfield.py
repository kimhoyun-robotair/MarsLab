"""Heightfield mesh construction."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from marslab_scene.terrain.frame import build_local_xy_grid


@dataclass(frozen=True, slots=True)
class MeshData:
    """Triangular mesh data."""

    vertices: np.ndarray
    faces: np.ndarray
    bounds: tuple[float, float, float, float, float, float]


def build_heightfield_mesh(z: np.ndarray, size_x_m: float, size_y_m: float) -> MeshData:
    """Build a REP-103 local ENU heightfield mesh from a 2D Z array."""
    from marslab_scene.terrain.hirise.mesh.validate import validate_mesh_data

    z_values = np.asarray(z, dtype=np.float64)
    if z_values.ndim != 2:
        msg = "z must be a 2D array"
        raise ValueError(msg)

    height, width = z_values.shape
    x, y = build_local_xy_grid(width=width, height=height, size_x_m=size_x_m, size_y_m=size_y_m)
    vertices = np.column_stack((x.ravel(), y.ravel(), z_values.ravel()))
    faces = build_faces(height=height, width=width)
    bounds = (
        float(np.min(vertices[:, 0])),
        float(np.max(vertices[:, 0])),
        float(np.min(vertices[:, 1])),
        float(np.max(vertices[:, 1])),
        float(np.min(vertices[:, 2])),
        float(np.max(vertices[:, 2])),
    )
    mesh = MeshData(vertices=vertices, faces=faces, bounds=bounds)
    validate_mesh_data(mesh)
    return mesh


def build_faces(height: int, width: int) -> np.ndarray:
    """Build up-facing triangle faces for a regular grid."""
    if height < 2 or width < 2:
        msg = "height and width must be >= 2"
        raise ValueError(msg)

    faces: list[list[int]] = []
    for row in range(height - 1):
        for col in range(width - 1):
            v00 = row * width + col
            v10 = row * width + col + 1
            v01 = (row + 1) * width + col
            v11 = (row + 1) * width + col + 1
            faces.append([v00, v01, v10])
            faces.append([v10, v01, v11])

    return np.asarray(faces, dtype=np.int64)
