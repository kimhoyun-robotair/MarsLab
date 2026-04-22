"""Pure-Python numerical helpers for MarsLab (no Isaac Sim, no ROS2).

This package consolidates previously duplicated math utilities into a
single offline-testable namespace (P3 offline-first testing).  Modules
here must not import from ``marslab.ros2_bridge`` or ``marslab.robots``
— dependency flows strictly *from* those packages *into* ``marslab.math``.

Current contents:

* :mod:`marslab.math.quaternion` — scalar-first ``[w, x, y, z]``
  quaternion algebra and ZYX intrinsic RPY ↔ quaternion conversion.
"""
