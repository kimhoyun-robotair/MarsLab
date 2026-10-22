"""Launch the selected flight backend using MarsLab's canonical config."""
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def launch_nodes(context):
    import yaml

    path = LaunchConfiguration('marslab_config').perform(context)
    with open(path, encoding='utf-8') as stream:
        backend = yaml.safe_load(stream)['drone'].get('flight_backend', 'ardupilot')
    if backend == 'external_wrench':
        return []
    if backend != 'ardupilot':
        raise ValueError(f'Unsupported flight backend: {backend}')
    return [Node(package='ingenuity_ros', executable='autopilot', name='ingenuity_ardupilot',
                 parameters=[{'marslab_config': path, 'use_sim_time': False,
                              'ardupilot_source': LaunchConfiguration('ardupilot_source').perform(context)}],
                 output='screen')]


def generate_launch_description():
    from marslab.flight.ardupilot_setup import DEFAULT_SOURCE

    return LaunchDescription([
        DeclareLaunchArgument('marslab_config', description='Path to the shared MarsLab config YAML'),
        DeclareLaunchArgument('ardupilot_source', default_value=str(DEFAULT_SOURCE),
                             description='Pinned Mars-gravity ArduPilot source/build directory'),
        OpaqueFunction(function=launch_nodes),
    ])
