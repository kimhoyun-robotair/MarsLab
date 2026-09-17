"""Launch the external URDF articulation and the identity chassis connector."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from launch import LaunchDescription


def _build_robot_description(urdf_path: str) -> str:
    """Load the sibling helper when ROS loads this launch file by absolute path."""
    helper_path = Path(__file__).resolve().with_name("companion_urdf.py")
    spec = importlib.util.spec_from_file_location("marslab_companion_urdf", helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load companion URDF helper at {helper_path}")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper.build_robot_description(urdf_path)


def _launch_setup(context, *args, **kwargs) -> list[Node]:
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
    default_urdf = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "assets",
            "robots",
            "rover",
            "m2020_lidar.urdf",
        )
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "urdf_path",
                default_value=default_urdf,
                description="Absolute path to the M2020 URDF with mounted LiDAR housings.",
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
