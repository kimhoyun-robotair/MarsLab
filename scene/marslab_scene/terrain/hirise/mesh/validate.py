"""Mesh validation helpers."""

from __future__ import annotations

from typing import Protocol

import numpy as np


class MeshArrays(Protocol):
    @property
    def vertices(self) -> np.ndarray:
        """Return mesh vertices."""
        ...

    @property
    def faces(self) -> np.ndarray:
        """Return triangular face indices."""
        ...


class MeshValidationError(ValueError):
    """Raised when mesh data is invalid."""


def validate_mesh_data(mesh: MeshArrays) -> None:
    """Validate mesh array shapes and finite vertex coordinates."""
    if mesh.vertices.ndim != 2 or mesh.vertices.shape[1] != 3:
        msg = "mesh vertices must have shape (N, 3)"
        raise MeshValidationError(msg)
    if mesh.faces.ndim != 2 or mesh.faces.shape[1] != 3:
        msg = "mesh faces must have shape (M, 3)"
        raise MeshValidationError(msg)
    if not np.isfinite(mesh.vertices).all():
        msg = "mesh vertices must contain only finite values"
        raise MeshValidationError(msg)
    if mesh.faces.size and (mesh.faces.min() < 0 or mesh.faces.max() >= len(mesh.vertices)):
        msg = "mesh faces reference vertices outside the vertex array"
        raise MeshValidationError(msg)


def validate_normals_up(mesh: MeshArrays) -> None:
    """Validate that all non-degenerate face normals point upward."""
    validate_mesh_data(mesh)
    triangles = mesh.vertices[mesh.faces]
    edge_a = triangles[:, 1] - triangles[:, 0]
    edge_b = triangles[:, 2] - triangles[:, 0]
    normals = np.cross(edge_a, edge_b)
    z_components = normals[:, 2]
    nondegenerate = np.linalg.norm(normals, axis=1) > 0
    if not nondegenerate.any():
        msg = "mesh has no non-degenerate faces"
        raise MeshValidationError(msg)
    if not np.all(z_components[nondegenerate] > 0):
        msg = "mesh face normals must have positive Z"
        raise MeshValidationError(msg)
