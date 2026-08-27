"""UV/ST generation for REP-103 local ENU terrain meshes."""

from __future__ import annotations

import numpy as np
from pydantic import JsonValue

from marslab_scene.terrain.hirise.mesh.heightfield import MeshData


def build_vertex_uvs_from_local_xy(vertices: np.ndarray) -> np.ndarray:
    """Build vertex UVs where U increases east and V increases north."""
    points = np.asarray(vertices, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] < 2:
        msg = "vertices must be an Nx3-like array"
        raise ValueError(msg)

    x = points[:, 0]
    y = points[:, 1]
    x_span = float(np.max(x) - np.min(x))
    y_span = float(np.max(y) - np.min(y))
    if x_span <= 0 or y_span <= 0:
        msg = "mesh vertices must span non-zero X and Y ranges for UV generation"
        raise ValueError(msg)

    u = (x - float(np.min(x))) / x_span
    v = (y - float(np.min(y))) / y_span
    return np.column_stack((u, v)).astype(np.float32)


def build_face_varying_uvs(mesh: MeshData) -> np.ndarray:
    """Return face-varying UVs ordered like flattened face vertex indices."""
    vertex_uvs = build_vertex_uvs_from_local_xy(mesh.vertices)
    return vertex_uvs[np.asarray(mesh.faces, dtype=np.int64).ravel()]


def uv_metadata() -> dict[str, JsonValue]:
    """Return the documented Task 11 UV convention."""
    return {
        "u_axis": "+X east",
        "v_axis": "+Y north",
        "u_west": 0.0,
        "u_east": 1.0,
        "v_south": 0.0,
        "v_north": 1.0,
        "image_row_0": "north/top",
        "v_flip_applied": False,
        "interpolation": "faceVarying",
    }
