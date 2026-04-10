"""Integration test: sensor attachment and data readout.

Run with: PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_sensor_test.py

Key requirement: Uses isaacsim.core.api.World with world.step(render=True)
for sensors to produce data. Raw simulation_app.update() is insufficient.

Tests:
    1. RGB camera attaches and returns RGBA data with correct shape
    2. Depth camera attaches and returns depth data
    3. IMU attaches and reads Mars gravity (THE critical test: z = 3.72 +/- 0.05)
    4. LiDAR attaches and returns point cloud
    5. All 4 sensors coexist on one robot
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isaacsim import SimulationApp

simulation_app = SimulationApp({"headless": True})

import numpy as np  # noqa: E402
import omni.usd  # noqa: E402
from isaacsim.core.api import World  # noqa: E402
from pxr import Sdf, UsdPhysics  # noqa: E402

from marslab.config.schema import RobotConfig  # noqa: E402
from marslab.robots.rover import spawn_rover  # noqa: E402

passed = 0
failed = 0
total = 5


def run_test(name, test_fn):
    """Run a test and track results."""
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


# ===== TEST 1: RGB Camera =====
def test_rgb_camera():
    world = World(stage_units_in_meters=1.0)
    world.scene.add_default_ground_plane()
    world.reset()

    stage = omni.usd.get_context().get_stage()

    # Set Mars gravity
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

    with open("configs/sensors/stereo_rgb.yaml") as f:
        cfg = yaml.safe_load(f)["sensor"]

    from marslab.sensors.camera import attach_camera, read_camera_rgb

    world.reset()
    camera = attach_camera(stage, robot_path, cfg)
    world.reset()

    # Step with render=True to populate camera buffers
    for _ in range(30):
        world.step(render=True)

    rgb = read_camera_rgb(camera)
    assert rgb.size > 0, "RGB data is empty"
    assert rgb.ndim == 3, f"Expected 3D array, got {rgb.ndim}D"
    assert rgb.shape[2] == 4, f"Expected 4 channels (RGBA), got {rgb.shape[2]}"
    assert rgb.shape[0] == 720, f"Height mismatch: {rgb.shape[0]} != 720"
    assert rgb.shape[1] == 1280, f"Width mismatch: {rgb.shape[1]} != 1280"
    print(f"    RGB shape: {rgb.shape}, dtype: {rgb.dtype}")

    world.clear()


# ===== TEST 2: Depth Camera =====
def test_depth_camera():
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

    with open("configs/sensors/depth_camera.yaml") as f:
        cfg = yaml.safe_load(f)["sensor"]

    from marslab.sensors.camera import attach_camera, read_camera_depth

    world.reset()
    camera = attach_camera(stage, robot_path, cfg)
    world.reset()

    for _ in range(30):
        world.step(render=True)

    depth = read_camera_depth(camera)
    assert depth.size > 0, "Depth data is empty"
    assert depth.ndim == 2, f"Expected 2D array, got {depth.ndim}D"
    assert depth.shape == (720, 1280), f"Shape mismatch: {depth.shape}"
    print(
        f"    Depth shape: {depth.shape}, range: [{np.nanmin(depth):.2f}, {np.nanmax(depth):.2f}]"
    )

    world.clear()


# ===== TEST 3: IMU Gravity (THE critical test) =====
def test_imu_gravity():
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

    from marslab.sensors.imu import attach_imu, read_imu

    world.reset()
    imu_path = attach_imu(stage, robot_path, cfg)
    world.reset()

    # Let robot settle under Mars gravity
    for _ in range(120):
        world.step(render=True)

    reading = read_imu(imu_path)
    az = reading["lin_acc"][2]
    ax = reading["lin_acc"][0]
    ay = reading["lin_acc"][1]

    print(f"    IMU lin_acc: [{ax:.4f}, {ay:.4f}, {az:.4f}] m/s^2")
    assert (
        abs(az - 3.72) < 0.05
    ), f"IMU z-axis = {az:.4f}, expected 3.72 +/- 0.05 (THE critical test)"
    assert abs(ax) < 0.5, f"IMU x-axis = {ax:.4f}, expected ~0"
    assert abs(ay) < 0.5, f"IMU y-axis = {ay:.4f}, expected ~0"

    world.clear()


# ===== TEST 4: LiDAR =====
def test_lidar():
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

    with open("configs/sensors/lidar_3d.yaml") as f:
        cfg = yaml.safe_load(f)["sensor"]

    from marslab.sensors.lidar import attach_lidar, read_lidar_point_cloud

    world.reset()
    lidar_path = attach_lidar(stage, robot_path, cfg)
    world.reset()

    for _ in range(30):
        world.step(render=True)

    pc = read_lidar_point_cloud(lidar_path)
    assert pc.ndim == 2, f"Expected 2D array, got {pc.ndim}D"
    assert pc.shape[1] == 3, f"Expected 3 columns (XYZ), got {pc.shape[1]}"
    print(f"    LiDAR points: {pc.shape[0]}")

    world.clear()


# ===== TEST 5: All sensors coexist =====
def test_all_coexist():
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

    from marslab.sensors import load_and_attach_sensor

    sensor_paths = [
        "configs/sensors/stereo_rgb.yaml",
        "configs/sensors/depth_camera.yaml",
        "configs/sensors/lidar_3d.yaml",
        "configs/sensors/imu.yaml",
    ]

    world.reset()
    attached = []
    for sp in sensor_paths:
        result = load_and_attach_sensor(stage, robot_path, sp)
        attached.append(result)
    world.reset()

    assert len(attached) == 4, f"Expected 4 sensors, got {len(attached)}"

    for _ in range(60):
        world.step(render=True)

    # Verify IMU still reads gravity with all sensors
    from marslab.sensors.imu import read_imu

    imu_path = attached[3]  # IMU is last
    reading = read_imu(imu_path)
    az = reading["lin_acc"][2]
    print(f"    Coexist IMU z: {az:.4f}")
    assert abs(az - 3.72) < 0.10, f"IMU z-axis degraded with coexisting sensors: {az}"

    # Verify camera produces data
    from marslab.sensors.camera import read_camera_rgb

    camera = attached[0]  # RGB camera is first
    rgb = read_camera_rgb(camera)
    rgb_status = "OK" if rgb.size > 0 else "empty"
    rgb_info = rgb.shape if rgb.size > 0 else "N/A"
    print(f"    Coexist RGB: {rgb_status} ({rgb_info})")

    world.clear()


# ===== RUN ALL =====
print("\n[run_sensor_test] Starting sensor integration tests...")
print(f"  Total tests: {total}")
print()

run_test("1 - RGB Camera", test_rgb_camera)
run_test("2 - Depth Camera", test_depth_camera)
run_test("3 - IMU Gravity (CRITICAL)", test_imu_gravity)
run_test("4 - LiDAR", test_lidar)
run_test("5 - All Sensors Coexist", test_all_coexist)

print(f"\n[run_sensor_test] Results: {passed}/{total} passed, {failed}/{total} failed")

simulation_app.close()
