"""Standalone launch file for ``robot_state_publisher`` + MarsLab's URDF + ``/joint_states``.

The MarsLab Stage-3 OmniGraph publishes ``sensor_msgs/JointState`` on
``/<ns>/joint_states`` (see ``Ros2BridgeConfig.publish_joint_states``).
This launch file pairs that topic with a ``robot_state_publisher``
instance that consumes the rover URDF as a ROS parameter (NOT a topic
-- ``robot_description`` is a parameter on the
``robot_state_publisher`` node, even though late-joining tools like
RViz also accept it on a latched topic of the same name).

Mesh-path rewrite reuses
:func:`marslab.ros2_bridge.robot_description_publisher.rewrite_mesh_paths_to_file_uri`
so the relative ``./meshes/X`` references in the JPL URDF resolve to
absolute ``file://`` URIs that ``robot_state_publisher`` propagates
into the URDF parameter for downstream RViz consumption.

Usage::

    ros2 launch /home/<user>/MarsLab/launch/rover_state_publisher.launch.py

Companion to ``marslab/isaac_python.sh marslab/main.py`` --
the Isaac Sim run publishes ``/rover/joint_states`` and
``/rover/robot_description``; this launch file feeds the URDF
(parameter) + ``/joint_states`` (topic) into
``robot_state_publisher`` so the canonical ``/tf`` topic carries the
full link-tree TF (Body_Chassis -> Body_Wheel*, ...).

Override the URDF path or the namespace via launch args::

    ros2 launch rover_state_publisher.launch.py \\
        urdf_path:=/path/to/m2020.urdf namespace:=rover2
"""

from __future__ import annotations

import os

from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from launch import LaunchDescription


def _sanitize_urdf_for_robot_state_publisher(urdf_text: str) -> str:
    """Strip floating-joint orphans so robot_state_publisher emits a complete TF tree.

    The JPL m2020 URDF declares two joints with ``type="floating"``:

    * ``JointRoot`` (parent ``ground`` / child ``Body_Chassis``) -- a
      6-DOF placeholder that the URDF visualization tool populates at
      runtime.  ``robot_state_publisher`` does not propagate floating
      joints to ``/tf`` (no joint-state message defines a 6-DOF pose),
      leaving ``ground`` an orphan root that fires
      ``"No transform from [ground] to [Body_Chassis]"`` on every RViz
      ``RobotModel`` display.
    * ``Joint_MHS_DebrisShield`` (parent ``Body_Chassis`` / child
      ``Body_MHS_DebrisShield``) -- the same floating-joint pattern,
      surfacing as ``"No transform from [Body_MHS_DebrisShield] to
      [Body_Chassis]"``.

    The fix is the same one ``tools/convert_urdf_to_usd.py``
    already applies on the USD side (``_DEBRIS_SHIELD_RE`` at
    ``:66`` flips floating -> fixed; ``sanitize_urdf`` at
    ``:69-146`` strips ``JointRoot`` + ``ground`` outright).  This
    helper mirrors those edits in-memory for the rclpy-side
    ``robot_state_publisher`` consumer so the URDF on disk stays
    byte-identical to the NASA upstream.

    Args:
        urdf_text: Raw URDF XML string.

    Returns:
        Sanitized URDF string with the floating-joint orphans removed.
    """
    import re

    from marslab.ros2_bridge.robot_description_publisher import (
        _GROUND_LINK_RE,
        _JOINT_ROOT_BLOCK_RE,
    )

    out = _JOINT_ROOT_BLOCK_RE.sub("", urdf_text)
    out = _GROUND_LINK_RE.sub("", out)
    out = re.sub(
        r'(<joint\s+name="Joint_MHS_DebrisShield"\s+type=")floating(")',
        r"\1fixed\2",
        out,
    )
    return out


def _build_robot_description(urdf_path: str) -> str:
    """Read the URDF, sanitize floating joints, rewrite relative mesh paths.

    Two transforms applied in order:

    1. :func:`_sanitize_urdf_for_robot_state_publisher` -- strip the
       ``JointRoot`` + ``ground`` block and convert
       ``Joint_MHS_DebrisShield`` from floating to fixed so
       ``robot_state_publisher`` emits the full TF tree without the
       "No transform from [ground] / [Body_MHS_DebrisShield]"
       warnings.
    2. :func:`marslab.ros2_bridge.robot_description_publisher.rewrite_mesh_paths_to_file_uri`
       -- rewrite ``./meshes/X`` references to absolute ``file://``
       URIs so RViz can resolve them.

    Args:
        urdf_path: Absolute path to ``m2020.urdf``.

    Returns:
        The sanitized + mesh-rewritten URDF string ready to feed into
        the ``robot_description`` parameter.
    """
    from marslab.ros2_bridge.robot_description_publisher import rewrite_mesh_paths_to_file_uri

    abs_urdf_path = os.path.abspath(os.path.expanduser(urdf_path))
    if not os.path.isfile(abs_urdf_path):
        raise FileNotFoundError(
            f"URDF not found at {abs_urdf_path!r}. " "Set urdf_path:=<abs path> when launching."
        )
    with open(abs_urdf_path, encoding="utf-8") as fh:
        urdf_text = fh.read()
    urdf_text = _sanitize_urdf_for_robot_state_publisher(urdf_text)
    return rewrite_mesh_paths_to_file_uri(urdf_text, os.path.dirname(abs_urdf_path))


def _launch_setup(context, *args, **kwargs) -> list:
    """Resolve substitutions, then declare the node with the URDF parameter."""
    urdf_path = LaunchConfiguration("urdf_path").perform(context)
    namespace = LaunchConfiguration("namespace").perform(context)
    publish_frequency = float(LaunchConfiguration("publish_frequency").perform(context))

    robot_description = _build_robot_description(urdf_path)

    return [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            namespace=namespace,
            output="screen",
            parameters=[
                {
                    "robot_description": robot_description,
                    "use_sim_time": True,
                    "publish_frequency": publish_frequency,
                }
            ],
        ),
        # ``base_link -> Body_Chassis`` connector (identity transform).
        #
        # The MarsLab odometry publisher (``odom_publisher.child_frame_id =
        # base_link`` in the rover YAML) broadcasts ``odom -> base_link``
        # using the PhysX articulation root pose, which is itself X-rolled
        # in world by the spawn-time ``spawn_orientation_rpy = [pi, 0, 0]``
        # compensation for the JPL m2020 URDF's graphics-style link-frame
        # author convention.  This bakes the X-roll into ``odom ->
        # base_link``.  Combined with this connector being identity, the
        # ``odom -> base_link -> Body_Chassis`` chain inherits the X-roll
        # so the URDF chain (``Body_Chassis -> Body_RockerLeft -> ...``)
        # publishes mesh poses that line up with the world axes when an
        # RViz Fixed Frame is set to ``odom`` or to a downstream SLAM map
        # frame (e.g. RTAB-Map ``map``).
        #
        # An earlier iteration of this connector applied an explicit
        # 180-deg X-roll on the wrapper, which made RViz Fixed Frame =
        # base_link render correctly but caused Fixed Frame = odom and
        # Fixed Frame = map to render the rover upside-down (the X-roll
        # and the wrapper compensation chained into a double-correction
        # depending on which Fixed Frame the consumer picked).  The
        # identity wrapper yields a single canonical X-roll that travels
        # from ``odom`` through ``base_link`` into the URDF chain, so
        # every Fixed Frame upstream of ``base_link`` (odom, map, world,
        # ...) renders the rover in the same canonical pose.
        Node(
            package="tf2_ros",
            executable="static_transform_publisher",
            name="base_link_to_chassis",
            namespace=namespace,
            output="screen",
            arguments=[
                "--x",
                "0",
                "--y",
                "0",
                "--z",
                "0",
                "--roll",
                "0",
                "--pitch",
                "0",
                "--yaw",
                "0",
                "--frame-id",
                "base_link",
                "--child-frame-id",
                "Body_Chassis",
            ],
        ),
    ]


def generate_launch_description() -> LaunchDescription:
    default_urdf = os.path.expanduser("~/MarsLab/assets/m2020-urdf-models/rover/m2020.urdf")
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "urdf_path",
                default_value=default_urdf,
                description=(
                    "Absolute path to m2020.urdf.  Defaults to the JPL URDF in the "
                    "MarsLab assets/ submodule."
                ),
            ),
            DeclareLaunchArgument(
                "namespace",
                default_value="rover",
                description=(
                    "ROS namespace.  Must match the rover.ros2.namespace value "
                    "in the scenario YAML so the joint_states topic resolves to "
                    "/<namespace>/joint_states."
                ),
            ),
            DeclareLaunchArgument(
                "publish_frequency",
                default_value="50.0",
                description=(
                    "robot_state_publisher tick rate (Hz).  Matches "
                    "rover.ros2.rates.joint_states by default so /tf and "
                    "/joint_states publish at identical cadence."
                ),
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
