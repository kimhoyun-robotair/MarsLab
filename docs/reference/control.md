---
title: Rover control
description: Geometry, steering, pivot turns, command timeout and drive tuning.
permalink: /reference/control/
---

`rover.control` defines rover geometry, velocity limits, joint ownership, and
command ramping in each profile. The shared six-wheel controller supports the
four steerable corner wheels and the two fixed middle wheels; it has no rover
name switch. Wheel odometry uses the same dimensions and ordering.

`drive_type` supports:

| Mode | Meaning |
| --- | --- |
| `acceleration` | Selects the PhysX DriveAPI acceleration mode. This is the supplied default. |
| `force` | Selects the PhysX DriveAPI force mode. Re-tune damping and maximum force when selecting it. |

In both modes the controller sends wheel angular-velocity targets and steering
angle targets. `drive_type` selects how PhysX applies the drive response.

Important tuning groups:

- Geometry: `wheel_radius`, `wheelbase`, `steering_axle_offset`, `track_steer`, `track_middle`
- Limits: `max_linear_velocity`, `max_angular_velocity`, `max_steer_angle`
- Drive: damping, maximum force, and wheel acceleration rate
- Steering: stiffness, damping, maximum force, ramp rate, and alignment tolerance
- Braking feel: `decel_multiplier`
- Parking hold: `brake_stiffness` (default `50000.0`; `0` disables it)

The parking brake latches measured wheel angles when all commanded wheel rates
finish ramping to zero, then holds those targets with the configured position
stiffness. A nonzero drive target releases the hold; Stop clears the latch.
Tune this gain together with the drive mode, damping and maximum force.

Drive and steering lists require six and four unique, disjoint joints in their
documented wheel order. `command_timeout` defaults to 0.5 simulated seconds;
publish commands continuously while driving. Stale or nonfinite commands
request a controlled stop using the configured deceleration ramp. Pause freezes
expiry; Stop clears the command. A zero Twist or timeout retains the current
steering orientation while braking, rather than straightening moving wheels.

Ordinary driving reduces excessive yaw rate before computing both steering and
wheel rates, so they describe the same feasible arc. A command with zero linear
speed and nonzero yaw rate selects a pivot turn: the four corner wheels point
along tangents around the middle axle, and the two wheel banks counter-rotate.
The default Perseverance `max_steer_angle` is `0.9` rad (51.57 degrees). Each profile must
allow the pivot angles required by its geometry; insufficient steering travel
fails preflight. Before physics reset, startup also checks this configured
travel against each steering joint's USD limits without changing those limits.

`steering_axle_offset` is the forward displacement of the front/rear axle
midpoint from the nonsteering middle axle, in meters. It defaults to zero; the
Perseverance profile uses `0.05502`, matching its USD wheel centers. Front and rear
wheel positions are therefore `wheelbase/2 + offset` and `-wheelbase/2 + offset`,
with middle wheels at zero. The default Perseverance pivot angles are approximately
48.12 degrees at the front and 45.33 degrees at the rear. Control and wheel
odometry use this same geometry.

For a material steering change, the controller brakes first, steers after measured
wheel-angle excursion divided by elapsed time over a 0.20 s simulation-time
window falls below `steering_stop_speed` (default `0.05` rad/s), and resumes driving
only after measured steering is within `steering_alignment_tolerance` (default
`0.02` rad) of the target. Wheel-rate ramping uses a common proportional change
so acceleration and braking preserve the commanded wheel-speed ratios.
