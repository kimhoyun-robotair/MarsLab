"""MarsLab: slam_toolbox + Nav2 + rviz2 combined launch.

Companion to scripts/phase1/run_stage3_monolithic.py for ROS2 Jazzy.
Isaac Sim must already be running so /rover/scan, /rover/odom, /tf,
/tf_static, /clock are live before this launch fires up rviz.

Topic remap: Nav2's controller_server and velocity_smoother publish on
/cmd_vel by default; we globally remap that to /rover/cmd_vel to reach
the monolithic rover subscriber. Keep this remap intact -- without it
Nav2 generates plans but the rover never moves.

Usage:
    ros2 launch launch/marslab_slam_nav.launch.py

Arguments:
    slam_params  -- slam_toolbox YAML (default: configs/slam/slam_toolbox_async.yaml)
    nav2_params  -- Nav2 YAML (default: configs/nav2/nav2_params.yaml)
    rviz         -- "true"/"false" to launch rviz2 with the preset layout
    rviz_config  -- rviz config path (default: launch/rviz/marslab_slam_nav.rviz)

Interactive goal sending (smoke verification):
    1. Wait ~5-10 s after launch for slam_toolbox to publish /map.
    2. In rviz toolbar, click "2D Goal Pose".
    3. Click-drag on the map to set a goal pose.
    4. Nav2 bt_navigator picks up /goal_pose and drives the rover.
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap

from launch import LaunchDescription


def generate_launch_description() -> LaunchDescription:
    repo_root = Path(__file__).resolve().parents[1]
    default_slam = str(repo_root / "configs" / "slam" / "slam_toolbox_async.yaml")
    default_nav2 = str(repo_root / "configs" / "nav2" / "nav2_params.yaml")
    default_rviz = str(repo_root / "launch" / "rviz" / "marslab_slam_nav.rviz")
    default_slam_launch = str(repo_root / "launch" / "slam_toolbox.launch.py")

    nav2_bringup_dir = get_package_share_directory("nav2_bringup")
    nav2_navigation_launch = str(Path(nav2_bringup_dir) / "launch" / "navigation_launch.py")

    slam_params_arg = DeclareLaunchArgument(
        "slam_params",
        default_value=default_slam,
        description="slam_toolbox YAML parameter file.",
    )
    nav2_params_arg = DeclareLaunchArgument(
        "nav2_params",
        default_value=default_nav2,
        description="Nav2 YAML parameter file.",
    )
    rviz_arg = DeclareLaunchArgument(
        "rviz",
        default_value="true",
        description="Launch rviz2 with the preset layout.",
    )
    rviz_config_arg = DeclareLaunchArgument(
        "rviz_config",
        default_value=default_rviz,
        description="rviz2 configuration file.",
    )

    slam_include = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(default_slam_launch),
        launch_arguments={
            "params_file": LaunchConfiguration("slam_params"),
        }.items(),
    )

    # Nav2 bringup with global /cmd_vel -> /rover/cmd_vel remap.
    # SetRemap must wrap the IncludeLaunchDescription inside a GroupAction so
    # the remap applies to all nav2 nodes composed below.
    nav2_group = GroupAction(
        actions=[
            SetRemap(src="/cmd_vel", dst="/rover/cmd_vel"),
            SetRemap(src="cmd_vel", dst="/rover/cmd_vel"),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(nav2_navigation_launch),
                launch_arguments={
                    "use_sim_time": "true",
                    "params_file": LaunchConfiguration("nav2_params"),
                    "autostart": "true",
                    "use_composition": "False",
                    "use_respawn": "False",
                }.items(),
            ),
        ]
    )

    rviz_node = Node(
        package="rviz2",
        executable="rviz2",
        name="rviz2",
        output="screen",
        arguments=["-d", LaunchConfiguration("rviz_config")],
        parameters=[{"use_sim_time": True}],
        condition=IfCondition(LaunchConfiguration("rviz")),
    )

    return LaunchDescription(
        [
            slam_params_arg,
            nav2_params_arg,
            rviz_arg,
            rviz_config_arg,
            slam_include,
            nav2_group,
            rviz_node,
        ]
    )
