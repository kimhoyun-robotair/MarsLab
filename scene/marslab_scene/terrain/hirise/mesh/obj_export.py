"""Debug OBJ export helpers."""

from __future__ import annotations

from pathlib import Path

from marslab_scene.terrain.hirise.mesh.heightfield import MeshData


def write_obj(mesh: MeshData, path: Path | str) -> None:
    """Write a debug Wavefront OBJ mesh."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as stream:
        for vertex in mesh.vertices:
            _ = stream.write(f"v {vertex[0]} {vertex[1]} {vertex[2]}\n")
        for face in mesh.faces:
            one_based = face + 1
            _ = stream.write(f"f {one_based[0]} {one_based[1]} {one_based[2]}\n")
