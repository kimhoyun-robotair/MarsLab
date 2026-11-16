---
title: Rover physics
description: Authored mass properties, contact materials and rocker-bogie suspension.
permalink: /reference/physics/
---

The rover USD owns geometry, collision shapes, articulation structure, mass,
inertia, and center of mass. Configuration owns chassis damping, wheel contact
materials, and joint drives without rewriting the source asset. Mass, inertia,
and center-of-mass override keys are not accepted in the configuration.

The default Perseverance source rover's rigid-body masses total 951.64 kg.
Its 20 links with visual meshes
use uniform-density solid convex hulls to estimate their link-local centers of
mass and full inertia tensors. These are geometry-based approximations, not
measured flight-rover mass distributions. The supplied URDF and USD physics
layers contain the authored mass properties. The active rover also includes
the LiDAR attachment masses described below.

The passive rocker differential uses the two joints in
`rover.suspension.differential_joint_names`. Runtime inspects their authored axes
to determine the sign of the PhysX mimic coupling. In the default profile this
constrains `LEFT_DIFFERENTIAL + RIGHT_DIFFERENTIAL = 0`. Both rocker position
stiffnesses remain zero; damping is configurable. Startup validates the coupling
before physics begins. `chassis.container_prim_name`, `rigid_body_prim_name`, and
`joints_prim_name` identify the selected asset's hierarchy.

## Default Perseverance rover and LiDAR assets

`rover.usd_path` selects `assets/robots/perseverance/m2020_lidar.usda`, which composes
the base `m2020.usd` and both sensor USD assets. Preserve the base rover's
configuration layers and textures alongside it. `rover.urdf_source_path` selects
`assets/robots/perseverance/m2020_lidar.urdf`; its mesh references use the local files in
`assets/robots/perseverance/meshes/` and the sensor OBJ/MTL files.

The attachments add **5.688155 kg**, bringing the authored rover mass to
**957.328155 kg**. Their mass is merged into the chassis rigid body.
Runtime reads the authored USD/URDF; design records are not runtime inputs. Blender
working files, asset generation, and rebuild commands are outside this
distribution.

## Physics tuning

Tune in this order:

1. Confirm `chassis.rigid_body_prim_name`, wheel link names, and joint names.
2. Confirm the source USD mass properties and tune chassis damping.
3. Set wheel static/dynamic friction and restitution.
4. Tune passive rocker and bogie damping.
5. Tune active drive and steering gains.

Static friction must not be lower than dynamic friction. Wheel links name the
six `Body_Wheel*` rigid bodies, each with enabled collision shapes. Startup
checks each collider's effective physics material, including instance proxies,
before reset. Joint and link lists must match the USD exactly; missing bodies,
colliders, or ineffective overrides stop startup. Physics material bindings do
not change the visual materials. Runtime logs separate requested settings from
the values read back from USD.
