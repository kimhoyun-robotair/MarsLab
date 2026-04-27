"""World + Mars gravity + PhysxScene solver iteration setup.

Centralises the Mars gravity / solver iteration knobs so the rest of
the runtime can ignore them. ``create_world`` assumes
``boot_simulation_app`` has already been called -- the Isaac Sim
imports only resolve after Kit is alive.
"""

from __future__ import annotations

from typing import Any, Tuple


def create_world(
    physics_dt: float,
    gravity: float,
    solver_type: str = "TGS",
    solver_position_iteration_count: int = 16,
    solver_velocity_iteration_count: int = 4,
) -> Tuple[Any, Any]:
    """Create the Isaac Sim ``World`` and apply Mars physics defaults.

    Args:
        physics_dt: Physics step size in seconds (e.g. ``1/60``). The
            60 Hz default matches the SLAM / Nav2 runtime main-loop
            cadence -- physics and rendering tick at the same rate so
            sensor publishers stay in lockstep with the controller.
        gravity: Mars gravity magnitude in m/s^2 (e.g. ``3.72``).  Sign is
            normalised internally -- always applied as ``-abs(gravity)``
            along +Z.
        solver_type: ``"TGS"`` (default) or ``"PGS"``.
        solver_position_iteration_count: Written to
            ``physxScene:solverPositionIterationCount`` on ``/physicsScene``.
            The default of 16 accommodates the 29-DOF rover articulation
            with high-gain drives.
        solver_velocity_iteration_count: Written to
            ``physxScene:solverVelocityIterationCount``.

    Returns:
        ``(world, stage)`` tuple.  ``stage`` is the current USD stage
        obtained via ``omni.usd.get_context().get_stage()``.
    """
    import omni.usd
    from isaacsim.core.api import World
    from pxr import Sdf

    world = World(
        stage_units_in_meters=1.0,
        physics_dt=physics_dt,
        rendering_dt=physics_dt,
    )

    physics_ctx = world.get_physics_context()
    physics_ctx.set_gravity(-abs(float(gravity)))
    physics_ctx.set_solver_type(solver_type)

    stage = omni.usd.get_context().get_stage()

    physics_scene_prim = stage.GetPrimAtPath("/physicsScene")
    if physics_scene_prim.IsValid():
        physics_scene_prim.CreateAttribute(
            "physxScene:solverPositionIterationCount",
            Sdf.ValueTypeNames.Int,
        ).Set(int(solver_position_iteration_count))
        physics_scene_prim.CreateAttribute(
            "physxScene:solverVelocityIterationCount",
            Sdf.ValueTypeNames.Int,
        ).Set(int(solver_velocity_iteration_count))

    return world, stage


__all__ = ["create_world"]
