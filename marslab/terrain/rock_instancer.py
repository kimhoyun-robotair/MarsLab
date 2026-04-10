"""Rock 3D instancing on terrain for Isaac Sim.

Places rocks as 3D USD primitives on the terrain surface using
PointInstancer for efficient rendering. Rocks are positioned by
interpolating terrain elevation at each (x, y) coordinate.
Requires Isaac Sim runtime — do NOT import from offline code.
"""

import numpy as np
from pxr import Gf, Sdf, UsdGeom

from marslab.terrain.rock_placer import RockPlacement


def place_rocks_on_terrain(
    stage,
    rocks: list[RockPlacement],
    elevation: np.ndarray,
    resolution: float,
    prim_path: str = "/World/Rocks",
    seed: int = 42,
) -> None:
    """Place rocks as 3D instanced primitives on the terrain.

    Creates a PointInstancer with sphere prototypes scaled by rock
    diameter. Each rock is placed at the terrain surface height.

    Args:
        stage: USD stage.
        rocks: List of RockPlacement from sample_rocks_golombek().
        elevation: 2D terrain elevation array (rows, cols).
        resolution: Terrain meters per pixel.
        prim_path: USD path for the instancer.
        seed: Random seed for rotation randomization.
    """
    if not rocks:
        return

    rng = np.random.default_rng(seed)
    rows, cols = elevation.shape
    elev = np.nan_to_num(elevation, nan=0.0)

    # Create prototype rock shapes (3 size variants)
    proto_container_path = prim_path + "/Prototypes"
    stage.DefinePrim(Sdf.Path(proto_container_path), "Scope")

    proto_paths = []
    for i, (sx, sy, sz) in enumerate([(1.0, 1.0, 0.6), (1.2, 0.8, 0.7), (0.9, 1.1, 0.5)]):
        proto_path = f"{proto_container_path}/rock_{i}"
        sphere = UsdGeom.Sphere.Define(stage, proto_path)
        sphere.GetRadiusAttr().Set(0.5)
        xform = UsdGeom.Xformable(sphere.GetPrim())
        scale_op = xform.AddScaleOp()
        scale_op.Set(Gf.Vec3f(sx, sy, sz))
        proto_paths.append(proto_path)

    # Build instancer data
    positions = []
    orientations = []
    scales = []
    proto_indices = []

    for rock in rocks:
        # Interpolate terrain z at (x, y)
        col_f = rock.x / resolution
        row_f = rock.y / resolution
        col_i = int(np.clip(col_f, 0, cols - 1))
        row_i = int(np.clip(row_f, 0, rows - 1))
        z = float(elev[row_i, col_i])

        positions.append(Gf.Vec3f(rock.x, rock.y, z))

        # Random yaw rotation
        yaw = rng.uniform(0, 360)
        half_yaw = np.radians(yaw / 2)
        orientations.append(Gf.Quath(float(np.cos(half_yaw)), 0.0, 0.0, float(np.sin(half_yaw))))

        # Scale from diameter
        s = rock.diameter / 1.0
        scales.append(Gf.Vec3f(s, s, s * (rock.height / rock.diameter)))

        # Random prototype selection
        proto_indices.append(int(rng.integers(0, len(proto_paths))))

    # Create PointInstancer
    instancer = UsdGeom.PointInstancer.Define(stage, prim_path)

    # Set prototypes
    rel = instancer.GetPrototypesRel()
    for p in proto_paths:
        rel.AddTarget(Sdf.Path(p))

    instancer.GetProtoIndicesAttr().Set(proto_indices)
    instancer.GetPositionsAttr().Set(positions)
    instancer.GetOrientationsAttr().Set(orientations)
    instancer.GetScalesAttr().Set(scales)

    # Apply semantic label for annotation
    prim = stage.GetPrimAtPath(prim_path)
    if prim.IsValid():
        prim.CreateAttribute("semanticLabel", Sdf.ValueTypeNames.String).Set("big_rock")
