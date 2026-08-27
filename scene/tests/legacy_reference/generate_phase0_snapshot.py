#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = [
#     "numpy>=1.26",
# ]
# ///

# ─── How to run ───
# 1. Use the existing HabitatGen Python 3.12 environment from MarsLab-Utils.
# 2. Add the HiRISEGen, RockyComposer, and HabitatGen source roots to PYTHONPATH.
# 3. Run with --input, --output, and --source-revision; see PROVENANCE.md.
# ─────────────────

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from habitatgen.composer.placement.transform import compute_transform
from hirisegen.config import ElevationConfig
from hirisegen.dem.elevation import normalize_elevation
from rockycomposer.library.proto_meta import ProtoMeta
from rockycomposer.placement.selection import select_prototypes_batch


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate the Phase-0 legacy semantic snapshot")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    return parser


def _prototype(native_diameter: float, index: int) -> ProtoMeta:
    return ProtoMeta(
        name=f"rock_{index:03d}",
        prim_path=f"/World/RockPrototypes/rock_{index:03d}",
        mesh_bbox=(native_diameter, native_diameter, native_diameter),
        native_diameter=native_diameter,
        stable_face_indices=np.array([0], dtype=np.int32),
        density_kg_m3=2600.0,
        mesh_vertices=np.array(
            [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            dtype=np.float32,
        ),
        mesh_faces=np.array([(0, 1, 2)], dtype=np.int32),
    )


def main() -> int:
    args = _parser().parse_args()
    input_bytes = args.input.read_bytes()
    fixture = json.loads(input_bytes)
    dem = fixture["dem"]
    rocks = fixture["rocks"]
    habitat = fixture["habitat"]
    seed = int(fixture["seed"])

    raw_values = np.array(
        [[np.nan if value is None else value for value in row] for row in dem["raw_elevation_m"]],
        dtype=np.float64,
    )
    elevation = normalize_elevation(
        raw_values,
        np.isfinite(raw_values),
        ElevationConfig(
            normalization="manual",
            manual_reference_m=float(dem["manual_reference_m"]),
            vertical_scale=float(dem["vertical_scale"]),
            z_offset_m=float(dem["z_offset_m"]),
        ),
    )

    native_diameters = [float(value) for value in rocks["native_diameters_m"]]
    prototypes = [_prototype(value, index + 1) for index, value in enumerate(native_diameters)]
    prototype_indices, scales, clamped = select_prototypes_batch(
        np.asarray(rocks["diameters_m"], dtype=np.float64),
        prototypes,
        np.random.default_rng(seed),
        k=int(rocks["top_k"]),
        scale_clamp=(float(rocks["scale_clamp"][0]), float(rocks["scale_clamp"][1])),
    )

    transform = compute_transform(
        asset_centroid_zup=habitat["asset_centroid_zup_m"],
        asset_aabb_min_zup=habitat["asset_aabb_min_zup_m"],
        asset_aabb_max_zup=habitat["asset_aabb_max_zup_m"],
        anchor_x=float(habitat["anchor_xy_m"][0]),
        anchor_y=float(habitat["anchor_xy_m"][1]),
        dem_z_local=float(habitat["dem_z_local_m"]),
        z_align=str(habitat["z_align"]),
        asset_body_floor_z=float(habitat["asset_body_floor_z_m"]),
        z_offset_m=float(habitat["z_offset_m"]),
    )

    semantic_outputs = {
        "habitat": {
            "aabb_max_in_scene_m": transform.aabb_max_in_scene,
            "aabb_min_in_scene_m": transform.aabb_min_in_scene,
            "translation_m": [transform.tx, transform.ty, transform.tz],
        },
        "hirise": {
            "local_max_m": elevation.local_max_m,
            "local_min_m": elevation.local_min_m,
            "local_z_m": [
                [None if not np.isfinite(value) else float(value) for value in row]
                for row in elevation.local_z
            ],
            "raw_max_m": elevation.raw_max_m,
            "raw_min_m": elevation.raw_min_m,
            "z_reference_m": elevation.z_reference_m,
        },
        "rocks": {
            "clamped": clamped.tolist(),
            "prototype_indices": prototype_indices.tolist(),
            "scales": scales.tolist(),
        },
    }
    semantic_bytes = json.dumps(semantic_outputs, sort_keys=True, separators=(",", ":")).encode()
    snapshot = {
        "fixture_schema": 1,
        "input_sha256": hashlib.sha256(input_bytes).hexdigest(),
        "seed": seed,
        "semantic_outputs": semantic_outputs,
        "semantic_sha256": hashlib.sha256(semantic_bytes).hexdigest(),
        "source_revision": args.source_revision,
    }
    args.output.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
