"""USD helpers that pin TF frame names via ``isaac:nameOverride``.

Two responsibilities:

1. :func:`apply_nameoverride` -- write ``isaac:nameOverride="<frame>"``
   on an existing prim so :class:`isaacsim.ros2.bridge.ROS2PublishTransformTree`
   uses the override instead of the raw prim name when it serialises a
   ``geometry_msgs/TransformStamped`` ``frame_id`` / ``child_frame_id``.
2. :func:`create_odom_anchor` -- define a new ``Xform`` prim at the
   rover's *initial* world position and pin its frame name to ``"odom"``.
   The anchor becomes the ``parentPrim`` of ``PubTF`` so the published
   chain reads ``odom -> base_link -> {wheels, sensors}`` instead of
   ``world -> Body_Chassis -> ...``.

Citations (verified against the local Isaac Sim 5.1 install):

* ``isaac:nameOverride`` is declared as a string applied schema attribute
  in
  ``/home/hoyunkim/isaacsim/exts/isaacsim.robot.schema/usd/schema/isaac/robot_schema/__init__.py:42``
  -- prefix ``isaac:``, type ``Sdf.ValueTypeNames.String``.
* The non-Raw ``ROS2PublishTransformTree`` consumes the override when
  serialising frame names; the unit tests that pin behaviour are at
  ``/home/hoyunkim/isaacsim/exts/isaacsim.ros2.bridge/isaacsim/ros2/bridge/tests/test_pose_tree.py:154-156``
  (sets ``nameOverride``) and ``:215-229`` (verifies the published
  parent ``frame_id`` matches the override string).  The OGN node is
  declared ``Has State? = False``
  (``OgnROS2PublishTransformTree.rst:61``), so the override is read on
  every ``compute()`` tick rather than cached at edit-time -- making
  the apply-then-edit ordering flexible.

Design notes:

* The ``pxr`` import is performed *inside* each function so the module
  stays importable on the offline unit-test path (``pxr`` ships with
  Isaac Sim, not the system Python).  Tests inject a duck-typed stage
  whose ``GetPrimAtPath`` / ``DefinePrim`` return mocks, mirroring the
  pattern in ``marslab/robots/rover.py``.
* Missing-prim handling matches ``find_rigid_body_path`` in
  ``marslab/robots/rover.py`` -- log a single warning and return
  ``False`` so a typo in the prim path does not abort the whole spawn.
"""

from __future__ import annotations

import logging
from typing import Tuple

# Canonical USD path of the stationary ``odom`` anchor prim created by
# :func:`create_odom_anchor`.  Both :func:`marslab.robots.rover.spawn_rover`
# and ``marslab/main.py`` reference this path; keeping the
# string in one place removes the drift risk of a duplicated literal.
DEFAULT_ODOM_ANCHOR_PATH = "/World/odom_anchor"

__all__ = [
    "DEFAULT_ODOM_ANCHOR_PATH",
    "apply_nameoverride",
    "create_odom_anchor",
]

logger = logging.getLogger(__name__)


def apply_nameoverride(stage: object, prim_path: str, frame_name: str) -> bool:
    """Apply ``isaac:nameOverride="<frame_name>"`` to an existing prim.

    Args:
        stage: USD stage handle (or a duck-typed mock with
            ``GetPrimAtPath``).  The ``pxr.Sdf`` import lives inside the
            function body so this module loads on the offline-test path
            where ``pxr`` is absent.  See ``marslab/robots/rover.py`` for
            the same deferred-import pattern.
        prim_path: USD path of the prim that should receive the override
            (e.g. ``/World/Rover/Body_Chassis/Body_Chassis`` for the
            rover articulation root).
        frame_name: The ROS frame_id string the TF publisher must emit
            for this prim.  Typically ``"base_link"`` for the rover root
            or ``"odom"`` for the parent anchor.

    Returns:
        ``True`` when the attribute landed on a valid prim; ``False``
        when the prim was missing (a single warning is logged in that
        case so a typo never silently swallows the wiring).

    Notes:
        ``isaac:nameOverride`` is declared at
        ``isaacsim/exts/isaacsim.robot.schema/usd/schema/isaac/robot_schema/__init__.py:42``
        as a string applied-schema attribute.  Always created with
        ``custom=True`` so an existing applied-schema occurrence is
        reused rather than fighting USD's strict type system.
    """
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        logger.warning(
            "[tf_nameoverrides] prim missing at %s; isaac:nameOverride=%r skipped.",
            prim_path,
            frame_name,
        )
        return False

    from pxr import (
        Sdf,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    attr = prim.CreateAttribute("isaac:nameOverride", Sdf.ValueTypeNames.String, True)
    attr.Set(str(frame_name))
    return True


def create_odom_anchor(
    stage: object,
    anchor_path: str,
    anchor_xyz: Tuple[float, float, float],
    frame_name: str = "odom",
) -> bool:
    """Define an ``Xform`` anchor prim that PubTF uses as ``parentPrim``.

    The non-Raw ``ROS2PublishTransformTree`` walks from a ``parentPrim``
    target outward.  Without a dedicated stationary anchor it would
    publish ``world -> base_link -> ...`` (REP-105 violation).  Creating
    a stationary ``Xform`` at the rover's initial world position and
    naming it ``"odom"`` lets PubTF emit the canonical chain
    ``odom -> base_link -> {wheels, sensors}``.  The anchor's pose is
    the rover's spawn pose, mirroring the baseline that
    :func:`marslab.ros2_bridge.odometry_math.compute_odom_delta`
    subtracts.

    Args:
        stage: USD stage handle (duck-typed in tests).
        anchor_path: USD path for the new anchor prim (typically
            :data:`DEFAULT_ODOM_ANCHOR_PATH`).
        anchor_xyz: World-frame ``(x, y, z)`` of the rover at ``t=0``.
            The anchor stays put after spawn, so the relative chain
            ``anchor -> base_link`` matches the rclpy odometry baseline.
        frame_name: ROS frame_id string the TF publisher emits for the
            anchor.  Default ``"odom"`` (REP-105 odom frame).

    Returns:
        ``True`` after the anchor is defined and the override applied.

    Notes:
        ``UsdGeom.Xform.Define`` is idempotent on the same path -- a
        second call returns the existing prim.  Translation is set via
        ``AddTranslateOp`` which Stage-3 also uses for the rover root
        in ``marslab/robots/rover.py``.  ``isaac:nameOverride`` is
        applied via :func:`apply_nameoverride` so both helpers share
        a single attribute-creation code path.
    """
    from pxr import (
        Gf,
        Sdf,
        UsdGeom,
    )  # noqa: PLC0415  -- Isaac Sim runtime dependency, deferred to function scope

    xform = UsdGeom.Xform.Define(stage, anchor_path)
    prim = xform.GetPrim()
    xform.ClearXformOpOrder()
    translate_op = xform.AddTranslateOp()
    translate_op.Set(Gf.Vec3d(float(anchor_xyz[0]), float(anchor_xyz[1]), float(anchor_xyz[2])))

    attr = prim.CreateAttribute("isaac:nameOverride", Sdf.ValueTypeNames.String, True)
    attr.Set(str(frame_name))
    return True
