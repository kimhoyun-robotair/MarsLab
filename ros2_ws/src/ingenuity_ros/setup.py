from glob import glob
from setuptools import find_packages, setup

package_name = 'ingenuity_ros'
setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'LICENSE']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools', 'numpy', 'pymavlink', 'PyYAML'],
    zip_safe=True,
    maintainer='Package maintainer',
    maintainer_email='maintainer@example.invalid',
    description='MarsLab ArduPilot SITL command, telemetry, and keyboard adapters.',
    license='MIT',
    entry_points={'console_scripts': [
        'autopilot = ingenuity_ros.ardupilot_node:main',
        'keyboard = ingenuity_ros.keyboard_node:main',
    ]},
)
