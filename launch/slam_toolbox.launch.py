"""slam_toolbox standalone launch for MarsLab jezero_flat smoke.

Launches async_slam_toolbox_node with use_sim_time=True against the
running Isaac Sim publishers (/rover/scan, /tf, /tf_static, /clock).

Usage:
    ros2 launch launch/slam_toolbox.launch.py

Arguments:
    params_file -- Path to slam_toolbox_async.yaml (default: repo-relative).
"""

from pathlib import Path

from ament_index_python.packages import get_package_share_directory  # noqa: F401
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from launch import LaunchDescription


def generate_launch_description() -> LaunchDescription:
    repo_root = Path(__file__).resolve().parents[1]
    default_params = str(repo_root / "configs" / "slam" / "slam_toolbox_async.yaml")
    scan_fix_script = str(repo_root / "scripts" / "ros2" / "scan_header_fix.py")

    params_file_arg = DeclareLaunchArgument(
        "params_file",
        default_value=default_params,
        description="slam_toolbox YAML parameter file.",
    )

    # LaserScan header normalization: Isaac Sim publishes angle_max with
    # exclusive-end semantics (angle_max = angle_min + N*increment), while
    # Open Karto expects inclusive-end ((angle_max - angle_min)/increment + 1
    # == len(ranges)).  Without this republisher slam_toolbox drops every scan
    # with "LaserRangeScan contains N range readings, expected N+1".
    scan_fix_proc = ExecuteProcess(
        cmd=["python3", scan_fix_script],
        name="scan_header_fix",
        output="screen",
    )

    slam_node = Node(
        package="slam_toolbox",
        executable="async_slam_toolbox_node",
        name="slam_toolbox",
        output="screen",
        parameters=[
            LaunchConfiguration("params_file"),
            {"use_sim_time": True},
        ],
    )

    return LaunchDescription([params_file_arg, scan_fix_proc, slam_node])
