"""Launch the external URDF articulation and the identity chassis connector."""

from __future__ import annotations

import os

from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from launch import LaunchDescription


def _sanitize_urdf_for_robot_state_publisher(urdf_text: str) -> str:
    """Prepare the supplied URDF for robot_state_publisher."""
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
    """Read, prepare, and make the URDF mesh references absolute."""
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
    """Resolve launch arguments and create the URDF and identity nodes."""
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
                description="Absolute path to the M2020 URDF in the initialized submodule.",
            ),
            DeclareLaunchArgument(
                "namespace",
                default_value="rover",
                description="ROS namespace; match rover.ros2.namespace in configs/config.yaml.",
            ),
            DeclareLaunchArgument(
                "publish_frequency",
                default_value="50.0",
                description="robot_state_publisher cadence in Hz.",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
