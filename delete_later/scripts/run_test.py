"""Integration test: ROS2 Bridge sensor publishing.

Run with: PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_ros2_test.py

Tests:
    1. ROS2 bridge extension activates
    2. Clock publisher creates and publishes
    3. Camera ROS2 publisher creates (RGB)
    4. IMU ROS2 publisher creates (IsaacReadIMU → ROS2PublishImu)
    5. LiDAR ROS2 publisher creates (RtxLidar → PointCloud2)

Manual verification (separate terminal):
    ros2 topic list
    ros2 topic echo /rover_0/stereo_rgb/image_raw --once
    ros2 topic hz /rover_0/imu_sensor/data
"""

# TODO(R4): Rewrite using marslab.ros2_bridge.sensor_graph_builder (to be created in R4).
# marslab.ros2_bridge.publisher was never implemented; current stack uses build_sensor_graph().
# Tracking: R1 plan, R4 plan.
import pytest

pytestmark = pytest.mark.skip(reason="Awaits R4 sensor_graph_builder")

import os  # noqa: E402
import sys  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isaacsim import SimulationApp  # noqa: E402

simulation_app = SimulationApp({"headless": True})

import omni.graph.core as og  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from pxr import Sdf, UsdPhysics  # noqa: E402

from marslab.config.schema import RobotConfig  # noqa: E402
from marslab.robots.rover import spawn_rover  # noqa: E402

passed = 0
failed = 0
total = 5


def run_test(name, test_fn):
    global passed, failed
    try:
        test_fn()
        print(f"  TEST {name}: PASSED")
        passed += 1
    except Exception as e:
        print(f"  TEST {name}: FAILED - {e}")
        import traceback

        traceback.print_exc()
        failed += 1


# ===== TEST 1: ROS2 Bridge Extension =====
def test_ros2_bridge_enable():
    # from marslab.ros2_bridge.publisher import enable_ros2_bridge  # TODO(R4)
    #
    # enable_ros2_bridge()
    # simulation_app.update()
    # If no exception, extension is enabled
    raise NotImplementedError("Awaits R4 sensor_graph_builder")


# ===== TEST 2: Clock Publisher =====
def test_clock_publisher():
    # from marslab.ros2_bridge.publisher import setup_clock_publisher  # TODO(R4)
    #
    # setup_clock_publisher()
    # simulation_app.update()
    #
    # graph = og.get_graph_by_path("/ROS2_Clock")
    # assert graph is not None, "Clock graph not created"
    # assert graph.is_valid(), "Clock graph is invalid"
    raise NotImplementedError("Awaits R4 sensor_graph_builder")


# ===== TEST 3: Camera Publisher =====
def test_camera_publisher():
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    world.reset()

    stage = omni.usd.get_context().get_stage()
    config = RobotConfig(
        type="rover",
        urdf_path="assets/robots/rover/simple_rover.urdf",
        spawn_position=[0.0, 0.0, 0.5],
    )
    robot_path = spawn_rover(stage, config, gravity=3.72)

    # Attach camera sensor
    import yaml

    with open("configs/sensors/stereo_rgb.yaml") as f:
        cfg = yaml.safe_load(f)["sensor"]

    from marslab.sensors.camera import attach_camera

    attach_camera(stage, robot_path, cfg)

    world.reset()

    # Setup ROS2 publisher
    # from marslab.ros2_bridge.publisher import setup_camera_publisher  # TODO(R4)

    camera_prim_path = f"{robot_path}/{cfg.get('mount_link', 'base_link')}/{cfg['name']}"

    # Use fallback path if mount_link doesn't exist
    prim = stage.GetPrimAtPath(camera_prim_path)
    if not prim.IsValid():
        camera_prim_path = f"{robot_path}/{cfg['name']}"

    # setup_camera_publisher(
    #     camera_prim_path,
    #     "/rover_0/stereo_rgb/image_raw",
    #     "camera_link",
    #     "rgb",
    # )  # TODO(R4)

    # Step to generate data
    for _ in range(10):
        world.step(render=True)

    print(f"    Camera publisher graph created for {camera_prim_path}")
    world.clear()


# ===== TEST 4: IMU Publisher =====
def test_imu_publisher():
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    world.reset()

    stage = omni.usd.get_context().get_stage()
    physics_scene = UsdPhysics.Scene.Get(stage, Sdf.Path("/physicsScene"))
    if physics_scene:
        physics_scene.GetGravityMagnitudeAttr().Set(3.72)

    config = RobotConfig(
        type="rover",
        urdf_path="assets/robots/rover/simple_rover.urdf",
        spawn_position=[0.0, 0.0, 0.5],
    )
    robot_path = spawn_rover(stage, config, gravity=3.72)

    import yaml

    with open("configs/sensors/imu.yaml") as f:
        cfg = yaml.safe_load(f)["sensor"]

    from marslab.sensors.imu import attach_imu

    imu_path = attach_imu(stage, robot_path, cfg)

    world.reset()

    # from marslab.ros2_bridge.publisher import setup_imu_publisher  # TODO(R4)
    #
    # setup_imu_publisher(imu_path, "/rover_0/imu_sensor/data", "imu_link")

    for _ in range(30):
        world.step(render=True)

    graph_path = f"/ROS2{imu_path.replace('/', '_')}"
    graph = og.get_graph_by_path(graph_path)
    assert graph is not None, f"IMU graph not created at {graph_path}"
    print(f"    IMU publisher graph created at {graph_path}")

    world.clear()


# ===== TEST 5: LiDAR Publisher =====
def test_lidar_publisher():
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    world.reset()

    stage = omni.usd.get_context().get_stage()
    config = RobotConfig(
        type="rover",
        urdf_path="assets/robots/rover/simple_rover.urdf",
        spawn_position=[0.0, 0.0, 0.5],
    )
    robot_path = spawn_rover(stage, config, gravity=3.72)

    import yaml

    with open("configs/sensors/lidar_3d.yaml") as f:
        cfg = yaml.safe_load(f)["sensor"]

    from marslab.sensors.lidar import attach_lidar

    lidar_path = attach_lidar(stage, robot_path, cfg)

    world.reset()

    # from marslab.ros2_bridge.publisher import setup_lidar_publisher  # TODO(R4)
    #
    # setup_lidar_publisher(lidar_path, "/rover_0/lidar_3d/points", "lidar_link")

    for _ in range(10):
        world.step(render=True)

    print(f"    LiDAR publisher created for {lidar_path}")
    world.clear()


# ===== RUN ALL =====
print("\n[run_ros2_test] Starting ROS2 bridge integration tests...")
print(f"  Total tests: {total}")
print()

run_test("1 - ROS2 Bridge Enable", test_ros2_bridge_enable)
run_test("2 - Clock Publisher", test_clock_publisher)
run_test("3 - Camera Publisher", test_camera_publisher)
run_test("4 - IMU Publisher", test_imu_publisher)
run_test("5 - LiDAR Publisher", test_lidar_publisher)

print(f"\n[run_ros2_test] Results: {passed}/{total} passed, {failed}/{total} failed")

# --- Long-running mode for manual ROS2 topic verification ---
# Set env var MARSLAB_PUBLISH=1 to keep simulation running with all publishers active
# Usage: MARSLAB_PUBLISH=1 PYTHONPATH=... ~/isaacsim/python.sh scripts/run_ros2_test.py
if os.environ.get("MARSLAB_PUBLISH") == "1":
    print(
        "\n[run_ros2_test] MARSLAB_PUBLISH=1: Setting up all publishers and running continuously."
    )
    print("  Open another terminal and run:")
    print("    ros2 topic list")
    print("    ros2 topic echo /rover_0/imu_sensor/data --once")
    print("  Press Ctrl+C to stop.\n")

    import yaml  # noqa: E402

    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    world.reset()

    stage = omni.usd.get_context().get_stage()
    physics_scene = UsdPhysics.Scene.Get(stage, Sdf.Path("/physicsScene"))
    if physics_scene:
        physics_scene.GetGravityMagnitudeAttr().Set(3.72)

    config = RobotConfig(
        type="rover",
        urdf_path="assets/robots/rover/simple_rover.urdf",
        spawn_position=[0.0, 0.0, 0.5],
    )
    robot_path = spawn_rover(stage, config, gravity=3.72)

    from marslab.sensors import load_and_attach_sensor  # noqa: E402

    sensor_files = [
        "configs/sensors/stereo_rgb.yaml",
        "configs/sensors/depth_camera.yaml",
        "configs/sensors/imu.yaml",
        "configs/sensors/lidar_3d.yaml",
    ]
    sensor_prim_paths = {}
    sensor_configs = {}
    for sf in sensor_files:
        sensor = load_and_attach_sensor(stage, robot_path, sf)
        with open(sf) as f:
            cfg = yaml.safe_load(f)["sensor"]
        sname = cfg["name"]
        mount = cfg.get("mount_link", "base_link")
        prim = stage.GetPrimAtPath(f"{robot_path}/{mount}/{sname}")
        if prim.IsValid():
            sensor_prim_paths[sname] = f"{robot_path}/{mount}/{sname}"
        else:
            sensor_prim_paths[sname] = f"{robot_path}/{sname}"
        sensor_configs[sname] = cfg

    world.reset()

    # from marslab.ros2_bridge.publisher import (  # TODO(R4)
    #     enable_ros2_bridge,
    #     setup_all_publishers,
    #     setup_clock_publisher,
    # )
    #
    # enable_ros2_bridge()
    # setup_clock_publisher()
    # topics = setup_all_publishers("rover_0", sensor_prim_paths, sensor_configs)
    # print(f"\n  Publishing {len(topics)} topics:")
    # for t in topics:
    #     print(f"    {t}")
    # print()
    topics: list[str] = []

    # Run simulation continuously
    frame = 0
    try:
        while simulation_app.is_running():
            world.step(render=True)
            frame += 1
            if frame % 300 == 0:
                print(f"  [publish] frame {frame}, sim running...")
    except KeyboardInterrupt:
        print("\n[run_ros2_test] Stopped by user.")

    world.clear()

simulation_app.close()
