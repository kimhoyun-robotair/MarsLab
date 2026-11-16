---
title: Wheel odometry
description: Encoder-based motion estimation, noise and odometry TF ownership.
permalink: /reference/odometry/
---

Wheel odometry solves planar velocity from six wheel encoders and the four
measured steering angles. It shares wheelbase, steering-axle offset, track, and
radius geometry with the drive controller, applies configured slip and
angular-rate noise, and integrates planar arcs. It never reads ground truth.

- Increase `slip_left` or `slip_right` only to model systematic wheel slip.
- Tune geometry in `rover.control`; the separate `track_width` key is removed.
- Use six nonnegative covariance values in the documented component order.
- Set `rover.wheel_odometry.enabled: false` to disable the wheel estimate.
- Set `wheel_odom.publish_tf: false` when an external localization system owns
  dynamic `odom` to `base_link` TF.
