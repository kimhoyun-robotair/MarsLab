"""Integration test: TF tree completeness and runtime extrinsic match.

This test boots the Stage-3 runtime headless (mirroring
``tests/integration/test_robot_spawn_ros2_topics.py``), waits for the
articulation joint chain to be published on ``/tf_raw`` and the static
sensor frames on ``/tf_static``, then asserts:

1. **Both TF topics produce at least one message within budget**.
   ``/tf_static`` is latched (TRANSIENT_LOCAL) so it should arrive in
   one tick; ``/tf_raw`` requires the OmniGraph tick. The OmniGraph
   ``ROS2PublishTransformTree`` publishes the articulation chain on
   ``/tf_raw``. The rclpy ``TransformBroadcaster`` publishes
   ``odom -> base_link`` on ``/tf`` only when ``publish_odom_tf=True``
   (default ``False`` in v1.0).
2. **The static TF tree contains an edge for every sensor declared in
   the YAML**: ``base_link -> camera_link``, ``base_link -> lidar_link``,
   ``base_link -> scan_frame`` (if lidar_2d is configured), and
   ``base_link -> imu_link``. The parent frame is always ``base_link``.
3. **Each sensor's static TF translation matches the YAML
   ``local_translation`` to within 1 cm**, broadcast identity (no
   Y/Z flip) since the broadcaster now emits the YAML values
   unmodified.
4. **Each sensor's static TF rotation is identity** -- the static
   broadcaster currently emits identity for orientation; when that
   changes, this test will need to be updated to cross-check
   ``local_orientation_rpy_deg``.

The integration test is gated on ``pytest.importorskip("isaacsim")``
and ``importorskip("rclpy")`` so it skips cleanly on a workstation
without the Isaac Sim Kit app.

Invocation::

    marslab/isaac_python.sh tools/run_integration_test.py \\
        tests/integration/test_tf_tree_completeness.py
"""

from __future__ import annotations

import contextlib
import math
import os
import sys
import time
from typing import Dict, List, Tuple

import pytest

isaacsim = pytest.importorskip(
    "isaacsim",
    reason="Isaac Sim not available; run via marslab/isaac_python.sh",
)
rclpy_mod = pytest.importorskip(
    "rclpy",
    reason="Isaac Sim bundled rclpy not importable; run via marslab/isaac_python.sh",
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


# ---------------------------------------------------------------------------
# Constants -- kept near the top so a reviewer can adjust budgets/tolerances.
# ---------------------------------------------------------------------------

# Position tolerance in meters.
POS_TOL_M = 0.01
# Orientation tolerance in degrees. Currently the static broadcaster
# emits identity rotation, so any non-trivial assertion is trivially
# within tolerance.
ROT_TOL_DEG = 0.1
# How long to wait for messages on /tf_raw and /tf_static.
TF_BUDGET_S = 30.0
# rclpy spin-once timeout per loop tick.
SPIN_TIMEOUT_S = 0.01

# Frame map: YAML sensor key -> broadcast child_frame_id.
SENSOR_FRAME_MAP: Tuple[Tuple[str, str], ...] = (
    ("camera", "camera_link"),
    ("lidar_3d", "lidar_link"),
    ("lidar_2d", "scan_frame"),
    ("imu", "imu_link"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _quat_wxyz_to_rpy_deg(w: float, x: float, y: float, z: float) -> Tuple[float, float, float]:
    """ZYX-intrinsic Euler decomposition used only for the rotation tolerance check."""
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)
    sinp = 2.0 * (w * y - z * x)
    pitch = math.copysign(math.pi / 2.0, sinp) if abs(sinp) >= 1.0 else math.asin(sinp)
    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return (math.degrees(roll), math.degrees(pitch), math.degrees(yaw))


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_tf_tree_contains_all_sensor_frames() -> None:
    """Every declared sensor publishes a static TF that matches its YAML.

    Boots the Stage-3 runtime, subscribes to ``/tf_static`` (latched)
    and ``/tf_raw`` (live joint chain), and confirms that every sensor
    declared in the rover YAML appears as a ``base_link -> <frame>``
    edge whose translation matches the YAML to within
    :data:`POS_TOL_M` and whose rotation is within
    :data:`ROT_TOL_DEG` of the identity quaternion.
    """
    from tf2_msgs.msg import TFMessage  # noqa: PLC0415

    from marslab.config.scenario_loader import resolve_spawn_pose  # noqa: PLC0415
    from marslab.robots.rover import spawn_rover  # noqa: PLC0415
    from marslab.ros2_bridge.rclpy_integration import init_rclpy_side  # noqa: PLC0415
    from marslab.runtime.stage2_boot import run_stage2_boot  # noqa: PLC0415
    from marslab.runtime.stage2_scene import setup_stage2_scene  # noqa: PLC0415
    from marslab.sim.boot import boot_simulation_app  # noqa: PLC0415

    simulation_app = boot_simulation_app(headless=True)
    bridge = None
    try:
        config_path = os.path.join(REPO_ROOT, "configs/scenarios/jezero_flat.yaml")
        boot = run_stage2_boot(config_path, repo_root=REPO_ROOT)
        scene = setup_stage2_scene(boot)
        world = scene.world
        stage = scene.stage
        assert stage is not None, "USD stage missing after stage-2 scene setup"

        rover_cfg = boot.config["rover"]
        ros2_cfg = rover_cfg["ros2"]
        usd_rel = rover_cfg["usd_path"]
        usd_abs = (
            usd_rel if os.path.isabs(usd_rel) else os.path.abspath(os.path.join(REPO_ROOT, usd_rel))
        )
        spawn_xyz = resolve_spawn_pose(rover_cfg, boot.elevation, boot.metadata, boot.resolution)
        spawn_rover(stage, rover_cfg, usd_abs, spawn_xyz)
        world.reset()

        # Build the same sensor_frames list the runtime entry point does.
        # We need this both to drive the static broadcaster and to compare
        # the received TF translation against the YAML.
        sensors_cfg = rover_cfg["sensors"]
        camera_cfg = sensors_cfg["camera"]
        lidar_3d_cfg = sensors_cfg.get("lidar_3d") or sensors_cfg.get("lidar")
        lidar_2d_cfg = sensors_cfg.get("lidar_2d")
        imu_cfg = sensors_cfg["imu"]

        sensor_frames: List[Tuple[str, list]] = [
            ("camera_link", list(camera_cfg["local_translation"])),
            ("lidar_link", list(lidar_3d_cfg["local_translation"])),
            ("imu_link", list(imu_cfg["local_translation"])),
        ]
        if lidar_2d_cfg is not None:
            sensor_frames.append(("scan_frame", list(lidar_2d_cfg["local_translation"])))

        bridge = init_rclpy_side(
            ros2_cfg=ros2_cfg,
            sensor_frames=sensor_frames,
            init_pos_world=spawn_xyz,
            init_quat_world=(1.0, 0.0, 0.0, 0.0),
            node_name="integration_tf_probe",
        )

        import rclpy  # noqa: PLC0415

        # Capture every TransformStamped sent on /tf_raw and /tf_static.
        # /tf_static is latched (TRANSIENT_LOCAL) so a late subscriber
        # still receives the original batch.
        from rclpy.qos import (  # noqa: PLC0415
            DurabilityPolicy,
            HistoryPolicy,
            QoSProfile,
            ReliabilityPolicy,
        )

        latched = QoSProfile(
            depth=10,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
        )

        static_msgs: List = []
        live_msgs: List = []

        def _on_static(msg: TFMessage) -> None:  # noqa: ANN001 -- ROS2 callback
            static_msgs.extend(msg.transforms)

        def _on_live(msg: TFMessage) -> None:  # noqa: ANN001 -- ROS2 callback
            live_msgs.extend(msg.transforms)

        sub_static = bridge.node.create_subscription(TFMessage, "/tf_static", _on_static, latched)
        sub_live = bridge.node.create_subscription(TFMessage, "/tf_raw", _on_live, 10)

        deadline = time.time() + TF_BUDGET_S
        expected_children = {child for child, _ in sensor_frames}
        while time.time() < deadline:
            world.step(render=False)
            rclpy.spin_once(bridge.node, timeout_sec=SPIN_TIMEOUT_S)
            received = {tf.child_frame_id for tf in static_msgs}
            if expected_children.issubset(received) and live_msgs:
                break

        bridge.node.destroy_subscription(sub_static)
        bridge.node.destroy_subscription(sub_live)

        # --- Assertion 1: /tf_static delivered each expected edge ----------
        received_children = {tf.child_frame_id for tf in static_msgs}
        missing = expected_children - received_children
        assert not missing, (
            f"/tf_static missing sensor edges: {missing}. "
            f"Got: {sorted(received_children)}. "
            f"Check publish_static_sensor_tfs and the sensor_frames list "
            f"in marslab/main.py."
        )

        # --- Assertion 2: /tf_raw received at least one joint-chain message
        assert live_msgs, (
            "No /tf_raw messages received within budget. The articulation "
            "joint TF publisher (PubTF in "
            "marslab/ros2_bridge/sensor_graph_builder.py) did not tick -- "
            "check OmniGraph wiring. PubTF publishes on /tf_raw; the "
            "rclpy TransformBroadcaster only writes to /tf when "
            "publish_odom_tf=True (default False in v1.0)."
        )

        # --- Assertion 3: parent frame is base_link for every static edge --
        for tf in static_msgs:
            if tf.child_frame_id in expected_children:
                assert tf.header.frame_id == "base_link", (
                    f"Static TF {tf.child_frame_id}: parent frame is "
                    f"'{tf.header.frame_id}', expected 'base_link'."
                )

        # --- Assertion 4: translation matches YAML within 1 cm -------------
        # Build expected map from YAML. The broadcaster emits the YAML
        # values identity (no Y/Z flip).
        expected_xyz: Dict[str, Tuple[float, float, float]] = {}
        for child, xyz in sensor_frames:
            expected_xyz[child] = (float(xyz[0]), float(xyz[1]), float(xyz[2]))

        for tf in static_msgs:
            if tf.child_frame_id not in expected_xyz:
                continue
            exp = expected_xyz[tf.child_frame_id]
            actual = (
                float(tf.transform.translation.x),
                float(tf.transform.translation.y),
                float(tf.transform.translation.z),
            )
            for axis_idx, axis_name in enumerate(("x", "y", "z")):
                delta = abs(actual[axis_idx] - exp[axis_idx])
                assert delta <= POS_TOL_M, (
                    f"{tf.child_frame_id} translation.{axis_name} "
                    f"= {actual[axis_idx]:.6f}, expected {exp[axis_idx]:.6f} "
                    f"(YAML identity), delta {delta:.4f} > {POS_TOL_M} m. "
                    f"Check rover_m2020.yaml local_translation."
                )

        # --- Assertion 5: rotation within 0.1 deg of identity --------------
        # The static broadcaster currently authors identity quaternions
        # for sensors. Once orientation is added, replace this with a
        # YAML cross-check.
        for tf in static_msgs:
            if tf.child_frame_id not in expected_children:
                continue
            q = tf.transform.rotation
            r, p, y = _quat_wxyz_to_rpy_deg(float(q.w), float(q.x), float(q.y), float(q.z))
            for axis_name, val in (("roll", r), ("pitch", p), ("yaw", y)):
                assert abs(val) <= ROT_TOL_DEG, (
                    f"{tf.child_frame_id} {axis_name}={val:.4f} deg "
                    f"exceeds tolerance {ROT_TOL_DEG} deg of identity. "
                    f"tf_broadcaster currently authors identity rotation; "
                    f"if this assertion fires, the broadcaster gained "
                    f"orientation and the YAML cross-check needs to be "
                    f"upgraded."
                )
    finally:
        if bridge is not None:
            with contextlib.suppress(Exception):
                bridge.node.destroy_node()
            with contextlib.suppress(Exception):
                import rclpy  # noqa: PLC0415

                rclpy.shutdown()
        simulation_app.close()
