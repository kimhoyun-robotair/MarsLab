from __future__ import annotations

from marslab.config.schema.rover import RoverConfig


def format_physics_override_summary(rover: RoverConfig) -> str:
    com = ", ".join(str(float(value)) for value in rover.com_offset)
    chassis_inertia = ", ".join(
        str(float(value))
        for value in (
            rover.chassis.inertia_xx,
            rover.chassis.inertia_yy,
            rover.chassis.inertia_zz,
        )
    )
    wheel_inertia = ", ".join(
        str(float(value))
        for value in (
            rover.wheels.inertia_spin,
            rover.wheels.inertia_transverse,
            rover.wheels.inertia_transverse,
        )
    )
    return "\n".join(
        (
            "marslab.physics.overrides_applied",
            "  rigid body:",
            f"    prim name: {rover.chassis.rigid_body_prim_name}",
            f"    center of mass: [{com}] m",
            f"    angular damping: {float(rover.angular_damping)}",
            f"    linear damping: {float(rover.linear_damping)}",
            "  chassis:",
            f"    mass: {float(rover.chassis.mass)} kg",
            f"    diagonal inertia: [{chassis_inertia}] kg*m^2",
            "  wheels:",
            f"    links: {', '.join(rover.wheels.link_names)}",
            f"    mass per wheel: {float(rover.wheels.mass)} kg",
            f"    diagonal inertia: [{wheel_inertia}] kg*m^2",
            f"    static friction: {float(rover.wheels.friction_static)}",
            f"    dynamic friction: {float(rover.wheels.friction_dynamic)}",
            f"    restitution: {float(rover.wheels.restitution)}",
            "  drive:",
            f"    joints: {', '.join(rover.control.drive_joint_names)}",
            f"    damping: {float(rover.control.drive_damping)}",
            f"    max force: {float(rover.control.drive_max_force)}",
            f"    type: {rover.control.drive_type}",
            "  steer:",
            f"    joints: {', '.join(rover.control.steer_joint_names)}",
            f"    stiffness: {float(rover.control.steer_stiffness)}",
            f"    damping: {float(rover.control.steer_damping)}",
            f"    max force: {float(rover.control.steer_max_force)}",
            "  suspension:",
            f"    rocker joints: {', '.join(rover.suspension.rocker_joint_names)}",
            f"    rocker damping: {float(rover.suspension.rocker_damping)}",
            f"    bogie joints: {', '.join(rover.suspension.bogie_joint_names)}",
            f"    bogie damping: {float(rover.suspension.bogie_damping)}",
        )
    )


__all__ = ["format_physics_override_summary"]
