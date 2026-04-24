"""Integration test: ``/scan`` topic QoS matches slam_toolbox expectations.

Reviewer 2 #4 fixed the QoS profile taxonomy across the ros2_bridge; this
integration test is the end-to-end witness that the 2D LaserScan actually
lands on ``/rover/scan`` in a form slam_toolbox can consume.

slam_toolbox's scan subscriber uses ``QoSProfile(depth=5,
reliability=BEST_EFFORT, durability=VOLATILE, history=KEEP_LAST)``.
A publisher with ``RELIABLE`` durability+reliability is compatible
(reliable satisfies best-effort).  This test's pass criterion is simply
that ``rclpy`` can create a subscription on the same QoS slam_toolbox
uses, and that at least one ``sensor_msgs/LaserScan`` message arrives
within a 30 s budget while the Stage-3 runtime ticks.

Invoke via::

    scripts/isaac_python.sh scripts/run_integration_test.py \
        tests/integration/test_slam_toolbox_receives_scan.py
"""

from __future__ import annotations

import contextlib
import os
import sys
import time

import pytest

isaacsim = pytest.importorskip(
    "isaacsim",
    reason="Isaac Sim not available; run via scripts/isaac_python.sh",
)
rclpy_mod = pytest.importorskip(
    "rclpy",
    reason="Isaac Sim bundled rclpy not importable; run via scripts/isaac_python.sh",
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


@pytest.mark.integration
def test_scan_topic_visible_to_slam_toolbox_qos() -> None:
    """Subscribe on slam_toolbox-compatible QoS and assert a message arrives."""
    from sensor_msgs.msg import LaserScan  # noqa: PLC0415

    from marslab.robots.rover import spawn_rover  # noqa: PLC0415
    from marslab.ros2_bridge.rclpy_integration import init_rclpy_side  # noqa: PLC0415
    from marslab.ros2_bridge.sensor_graph import build_sensor_graph  # noqa: PLC0415
    from marslab.runtime.stage2_boot import run_stage2_boot  # noqa: PLC0415
    from marslab.runtime.stage2_scene import setup_stage2_scene  # noqa: PLC0415
    from marslab.sensors.sensor_spawner import spawn_sensors  # noqa: PLC0415
    from marslab.sim.boot import boot_simulation_app  # noqa: PLC0415

    simulation_app = boot_simulation_app(headless=True)
    bridge = None
    try:
        config_path = os.path.join(REPO_ROOT, "configs/scenarios/jezero_flat.yaml")
        boot = run_stage2_boot(config_path, repo_root=REPO_ROOT)
        scene = setup_stage2_scene(boot)
        world = scene.world
        stage = scene.stage

        rover_cfg = boot.config["rover"]
        ros2_cfg = rover_cfg["ros2"]
        sensors_cfg = rover_cfg["sensors"]
        usd_rel = rover_cfg["usd_path"]
        usd_abs = (
            usd_rel if os.path.isabs(usd_rel) else os.path.abspath(os.path.join(REPO_ROOT, usd_rel))
        )
        from marslab.config.scenario_loader import resolve_spawn_pose  # noqa: PLC0415

        spawn_xyz = resolve_spawn_pose(rover_cfg, boot.elevation, boot.metadata, boot.resolution)
        spawned = spawn_rover(stage, rover_cfg, usd_abs, spawn_xyz)

        handles = spawn_sensors(stage, sensors_cfg, ros2_cfg, spawned.rigid_body_path)
        camera_cfg = sensors_cfg["camera"]
        build_sensor_graph(
            ros2_cfg=ros2_cfg,
            camera_prim_path=handles.camera_prim_path,
            camera_resolution=tuple(camera_cfg["resolution"]),
            lidar_3d_prim_path=handles.lidar_3d_prim_path,
            imu_prim_path=handles.imu_prim_path,
            lidar_2d_prim_path=handles.lidar_2d_prim_path,
        )

        world.reset()
        bridge = init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=[],
            init_pos_world=spawn_xyz,
            init_quat_world=(1.0, 0.0, 0.0, 0.0),
            node_name="integration_scan_probe",
        )

        import rclpy  # noqa: PLC0415
        from rclpy.qos import (  # noqa: PLC0415
            QoSDurabilityPolicy,
            QoSHistoryPolicy,
            QoSProfile,
            QoSReliabilityPolicy,
        )

        # slam_toolbox default scan subscriber QoS.
        slam_qos = QoSProfile(
            depth=5,
            reliability=QoSReliabilityPolicy.BEST_EFFORT,
            durability=QoSDurabilityPolicy.VOLATILE,
            history=QoSHistoryPolicy.KEEP_LAST,
        )

        ns = ros2_cfg["namespace"]
        scan_topic = f"/{ns}/{ros2_cfg['topics']['scan']}"

        received = {"count": 0}

        def _cb(_msg: LaserScan) -> None:  # noqa: ANN001 — ROS2 callback
            received["count"] += 1

        sub = bridge.node.create_subscription(LaserScan, scan_topic, _cb, slam_qos)

        deadline = time.time() + 30.0
        while time.time() < deadline and received["count"] == 0:
            world.step(render=False)
            rclpy.spin_once(bridge.node, timeout_sec=0.01)

        bridge.node.destroy_subscription(sub)
        assert received["count"] > 0, (
            f"No LaserScan messages on {scan_topic} within 30 s under "
            "slam_toolbox-compatible QoS. Check Example_Rotary_2D profile "
            "and sensor_graph OmniGraph wiring."
        )
    finally:
        if bridge is not None:
            with contextlib.suppress(Exception):
                bridge.node.destroy_node()
            with contextlib.suppress(Exception):
                import rclpy  # noqa: PLC0415

                rclpy.shutdown()
        simulation_app.close()
