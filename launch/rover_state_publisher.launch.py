"""Launch the external URDF articulation and the identity chassis connector."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

from launch import LaunchDescription


def _load_companion_helper() -> ModuleType:
    """Load the sibling helper when ROS loads this launch file by absolute path."""
    helper_path = Path(__file__).resolve().with_name("companion_urdf.py")
    spec = importlib.util.spec_from_file_location("marslab_companion_urdf", helper_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load companion URDF helper at {helper_path}")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    return helper


def _launch_setup(context, *args, **kwargs) -> list[Node]:
    """Resolve launch arguments and create the URDF and identity nodes."""
    publish_frequency = float(LaunchConfiguration("publish_frequency").perform(context))

    helper = _load_companion_helper()
    settings = helper.resolve_companion_settings(
        LaunchConfiguration("config").perform(context),
        robot=LaunchConfiguration("robot").perform(context),
        urdf_path=LaunchConfiguration("urdf_path").perform(context),
        namespace=LaunchConfiguration("namespace").perform(context),
        joint_states_topic=LaunchConfiguration("joint_states_topic").perform(context),
    )
    namespace = settings["namespace"]
    robot_description = helper.build_robot_description(settings["urdf_path"])
    root_frame = helper.robot_root_link(robot_description)

    nodes = [
        Node(
            package="robot_state_publisher",
            executable="robot_state_publisher",
            namespace=namespace,
            output="screen",
            parameters=[
                {
                    "robot_description": ParameterValue(robot_description, value_type=str),
                    "use_sim_time": True,
                    "publish_frequency": publish_frequency,
                }
            ],
            remappings=[("joint_states", settings["joint_states_topic"])],
        ),
    ]
    if root_frame == "base_link":
        return nodes
    nodes.append(
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
                root_frame,
            ],
        )
    )
    return nodes


def generate_launch_description() -> LaunchDescription:
    default_config = str(Path(__file__).resolve().parents[1] / "configs" / "config.yaml")
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "config",
                default_value=default_config,
                description="Scenario YAML; use the same --config as marslab/main.py.",
            ),
            DeclareLaunchArgument(
                "robot",
                default_value="",
                description="Rover profile override; empty follows the scenario's robot selector.",
            ),
            DeclareLaunchArgument(
                "urdf_path",
                default_value="",
                description="Optional URDF override; defaults to the selected rover profile.",
            ),
            DeclareLaunchArgument(
                "namespace",
                default_value="",
                description="Optional ROS namespace override; defaults to rover.ros2.namespace.",
            ),
            DeclareLaunchArgument(
                "joint_states_topic",
                default_value="",
                description=(
                    "Optional joint-state topic override; "
                    "defaults to rover.ros2.topics.joint_states."
                ),
            ),
            DeclareLaunchArgument(
                "publish_frequency",
                default_value="50.0",
                description="robot_state_publisher cadence in Hz.",
            ),
            OpaqueFunction(function=_launch_setup),
        ]
    )
