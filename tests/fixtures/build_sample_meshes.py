"""Generate tiny .obj/.stl fixtures used by structure_assets tests.

Run once (or whenever the fixture format needs refreshing) via
``python3 tests/fixtures/build_sample_meshes.py``. Output is committed
into ``tests/fixtures/`` -- the files stay under 1 KB each so we can
keep them in-tree without bloating the repository.

Why generate procedurally instead of shipping artist-authored meshes:
  * The tests only need a syntactically valid .obj / .stl that ``trimesh``
    can round-trip. A unit cube is sufficient.
  * Procedural generation keeps the diff reviewable -- any future change
    to the fixture is a one-line edit to this script, not an opaque
    binary diff.
"""

from __future__ import annotations

from pathlib import Path

import trimesh


def main() -> None:
    """Write ``sample_rock.obj`` and ``sample_rock.stl`` into this dir."""
    out_dir = Path(__file__).resolve().parent
    # Tetrahedron = the smallest closed surface (4 triangles, 4 verts) that
    # ``trimesh`` round-trips cleanly through both OBJ and STL exporters.
    # Box (12 triangles) blows the binary STL past ~1 KB; the tetra keeps
    # both files comfortably under that bar.
    verts = [
        [0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0],
        [0.0, 1.0, 0.0],
        [0.0, 0.0, 1.0],
    ]
    faces = [
        [0, 2, 1],
        [0, 1, 3],
        [0, 3, 2],
        [1, 2, 3],
    ]
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)

    obj_path = out_dir / "sample_rock.obj"
    stl_path = out_dir / "sample_rock.stl"

    # ASCII OBJ + binary STL: STL ASCII is verbose (3 lines per facet);
    # binary STL of 4 triangles is 84 bytes header + 4 * 50 = 284 bytes
    # total. OBJ ASCII for 4 verts + 4 faces is well under 200 bytes.
    obj_path.write_text(trimesh.exchange.obj.export_obj(mesh))
    stl_bytes = trimesh.exchange.stl.export_stl(mesh)
    stl_path.write_bytes(stl_bytes)

    print(f"wrote {obj_path} ({obj_path.stat().st_size} bytes)")
    print(f"wrote {stl_path} ({stl_path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
