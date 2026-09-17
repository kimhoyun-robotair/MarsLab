"""Resolve rover spawn clearance against cooked scene colliders before physics starts."""

from __future__ import annotations

import logging
import math
from typing import Any

_LOG = logging.getLogger(__name__)


def resolve_spawn_clearance(
    stage: Any,
    scene_root_path: str,
    rover_root_path: str,
    minimum_position: tuple[float, float, float],
    clearance: float,
) -> tuple[float, float, float]:
    """Sweep conservative collider bounds downward without advancing the simulation."""
    import omni.timeline
    from omni.physx import get_physx_interface, get_physx_scene_query_interface
    from pxr import Usd, UsdGeom, UsdPhysics

    if not omni.timeline.get_timeline_interface().is_stopped():
        raise RuntimeError("Spawn clearance must be resolved before the first Play")
    bounds = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [
            UsdGeom.Tokens.default_,
            UsdGeom.Tokens.render,
            UsdGeom.Tokens.proxy,
            UsdGeom.Tokens.guide,
        ],
        useExtentsHint=False,
        ignoreVisibility=True,
    )
    scene_bounds = bounds.ComputeWorldBound(
        stage.GetPrimAtPath(scene_root_path)
    ).ComputeAlignedRange()
    if scene_bounds.IsEmpty():
        raise RuntimeError(f"Scene has no bounds for spawn clearance: {scene_root_path}")
    top = float(scene_bounds.GetMax()[2]) + max(clearance, 0.1) + 1.0
    bottom = float(scene_bounds.GetMin()[2])
    colliders = []
    for prim in Usd.PrimRange(stage.GetPrimAtPath(rover_root_path), Usd.TraverseInstanceProxies()):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        if not UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get():
            continue
        box = bounds.ComputeWorldBound(prim).ComputeAlignedRange()
        if box.IsEmpty():
            raise RuntimeError(f"Rover collider has no bounds: {prim.GetPath()}")
        colliders.append((str(prim.GetPath()), box))
    if not colliders:
        raise RuntimeError(f"Rover has no enabled colliders: {rover_root_path}")

    physx = get_physx_interface()
    query = get_physx_scene_query_interface()
    required_z = minimum_position[2]
    limiting_pair = None
    supported_colliders = 0
    hits: list[tuple[float, str]] = []

    def scene_hit(hit: Any) -> bool:
        path = str(hit.collision)
        if path == scene_root_path or path.startswith(f"{scene_root_path}/"):
            hits.append((float(hit.distance), path))
        return True

    try:
        # World.reset initializes by stepping; force-load only cooks the query scene.
        physx.force_load_physics_from_usd()
        for collider_path, box in colliders:
            lower, upper = box.GetMin(), box.GetMax()
            half = tuple(max(1e-5, float(upper[i] - lower[i]) * 0.5) for i in range(3))
            center = tuple(float(upper[i] + lower[i]) * 0.5 for i in range(3))
            hits.clear()

            query.sweep_box_all(
                half,
                (center[0], center[1], top + half[2]),
                (0.0, 0.0, 0.0, 1.0),
                (0.0, 0.0, -1.0),
                top - bottom + 2.0 * half[2] + 1.0,
                scene_hit,
                True,
            )
            if not hits:
                continue
            supported_colliders += 1
            distance, surface = min(hits)
            candidate_z = top - distance - (float(lower[2]) - minimum_position[2]) + clearance
            if not math.isfinite(candidate_z):
                raise RuntimeError(f"Non-finite spawn clearance for {collider_path}")
            if candidate_z > required_z:
                required_z = candidate_z
                limiting_pair = (collider_path, surface)
    finally:
        # The first reset must load the final authored pose, not these provisional objects.
        physx.release_physics_objects()

    if supported_colliders == 0:
        raise RuntimeError(f"No scene support below rover footprint at {minimum_position[:2]}")

    _LOG.info(
        "Spawn collider clearance: minimum_z=%.6f resolved_z=%.6f clearance=%.3f "
        "colliders=%d limiting_pair=%s",
        minimum_position[2],
        required_z,
        clearance,
        len(colliders),
        limiting_pair,
    )
    return minimum_position[0], minimum_position[1], required_z


__all__ = ["resolve_spawn_clearance"]
