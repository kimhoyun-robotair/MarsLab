from __future__ import annotations

from marslab.config.schema.rover import RoverConfig


def format_physics_override_summary(rover: RoverConfig) -> str:
    return "\n".join(
        (
            "marslab.physics.requested_settings",
            "  mass, inertia, center of mass: supplied USD (no YAML overrides)",
            "  rigid body:",
            f"    prim name: {rover.chassis.rigid_body_prim_name}",
            f"    angular damping: {float(rover.angular_damping)}",
            f"    linear damping: {float(rover.linear_damping)}",
            "  wheels:",
            f"    links: {', '.join(rover.wheels.link_names)}",
            f"    static friction: {float(rover.wheels.friction_static)}",
            f"    dynamic friction: {float(rover.wheels.friction_dynamic)}",
            f"    restitution: {float(rover.wheels.restitution)}",
            "  drive:",
            f"    joints: {', '.join(rover.control.drive_joint_names)}",
            f"    damping: {float(rover.control.drive_damping)}",
            f"    max force: {float(rover.control.drive_max_force)}",
            f"    parking brake stiffness: {float(rover.control.brake_stiffness)}",
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
