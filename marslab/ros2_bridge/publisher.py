"""ROS2 sensor data publishers via Isaac Sim native bridge.

Uses isaacsim.ros2.bridge OmniGraph nodes for high-performance
C++ publishing. All params from YAML config (G5).
Requires Isaac Sim runtime with ROS2 Jazzy/Humble.
"""

import omni.graph.core as og
import omni.replicator.core as rep
import usdrt.Sdf
from isaacsim.core.utils.extensions import enable_extension

from marslab.ros2_bridge.topic_config import build_topic_name, get_default_sub_topic


def enable_ros2_bridge() -> None:
    """Enable the Isaac Sim ROS2 bridge extension."""
    enable_extension("isaacsim.ros2.bridge")


def setup_camera_publisher(
    camera_prim_path: str,
    topic_name: str,
    frame_id: str,
    camera_type: str = "rgb",
) -> None:
    """Create OmniGraph nodes to publish camera data to ROS2.

    Uses ROS2CameraHelper node which reads directly from the
    camera render product.

    Args:
        camera_prim_path: USD prim path of the camera sensor.
        topic_name: ROS2 topic name (e.g., "/rover_0/stereo_rgb/image_raw").
        frame_id: TF frame ID for the message header.
        camera_type: "rgb" or "depth".
    """
    graph_path = f"/ROS2{camera_prim_path.replace('/', '_')}_{camera_type}"

    og.Controller.edit(
        {
            "graph_path": graph_path,
            "evaluator_name": "push",
            "pipeline_stage": og.GraphPipelineStage.GRAPH_PIPELINE_STAGE_ONDEMAND,
        },
        {
            og.Controller.Keys.CREATE_NODES: [
                ("OnTick", "omni.graph.action.OnTick"),
                ("CreateViewport", "isaacsim.core.nodes.IsaacCreateViewport"),
                ("GetRenderProduct", "isaacsim.core.nodes.IsaacGetViewportRenderProduct"),
                ("SetCamera", "isaacsim.core.nodes.IsaacSetCameraOnRenderProduct"),
                ("CameraHelper", "isaacsim.ros2.bridge.ROS2CameraHelper"),
            ],
            og.Controller.Keys.CONNECT: [
                ("OnTick.outputs:tick", "CreateViewport.inputs:execIn"),
                ("CreateViewport.outputs:execOut", "GetRenderProduct.inputs:execIn"),
                ("CreateViewport.outputs:viewport", "GetRenderProduct.inputs:viewport"),
                ("GetRenderProduct.outputs:execOut", "SetCamera.inputs:execIn"),
                (
                    "GetRenderProduct.outputs:renderProductPath",
                    "SetCamera.inputs:renderProductPath",
                ),
                ("SetCamera.outputs:execOut", "CameraHelper.inputs:execIn"),
                (
                    "GetRenderProduct.outputs:renderProductPath",
                    "CameraHelper.inputs:renderProductPath",
                ),
            ],
            og.Controller.Keys.SET_VALUES: [
                ("CameraHelper.inputs:topicName", topic_name),
                ("CameraHelper.inputs:frameId", frame_id),
                ("CameraHelper.inputs:type", camera_type),
                ("SetCamera.inputs:cameraPrim", [usdrt.Sdf.Path(camera_prim_path)]),
            ],
        },
    )

    # Evaluate once to register in SDG pipeline
    graph = og.get_graph_by_path(graph_path)
    if graph:
        og.Controller.evaluate_sync(graph)


def setup_imu_publisher(
    imu_prim_path: str,
    topic_name: str,
    frame_id: str,
) -> None:
    """Create OmniGraph nodes to publish IMU data to ROS2.

    Uses IsaacReadIMU → ROS2PublishImu pipeline.

    Args:
        imu_prim_path: USD prim path of the IMU sensor.
        topic_name: ROS2 topic name (e.g., "/rover_0/imu_sensor/data").
        frame_id: TF frame ID.
    """
    graph_path = f"/ROS2{imu_prim_path.replace('/', '_')}"

    og.Controller.edit(
        {"graph_path": graph_path, "evaluator_name": "execution"},
        {
            og.Controller.Keys.CREATE_NODES: [
                ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("ReadIMU", "isaacsim.sensors.physics.IsaacReadIMU"),
                ("PublishIMU", "isaacsim.ros2.bridge.ROS2PublishImu"),
            ],
            og.Controller.Keys.CONNECT: [
                ("OnPlaybackTick.outputs:tick", "ReadIMU.inputs:execIn"),
                ("ReadIMU.outputs:execOut", "PublishIMU.inputs:execIn"),
                ("ReadIMU.outputs:linAcc", "PublishIMU.inputs:linearAcceleration"),
                ("ReadIMU.outputs:angVel", "PublishIMU.inputs:angularVelocity"),
                ("ReadIMU.outputs:orientation", "PublishIMU.inputs:orientation"),
                ("ReadSimTime.outputs:simulationTime", "PublishIMU.inputs:timeStamp"),
            ],
            og.Controller.Keys.SET_VALUES: [
                ("ReadIMU.inputs:imuPrim", [usdrt.Sdf.Path(imu_prim_path)]),
                ("ReadIMU.inputs:readGravity", True),
                ("PublishIMU.inputs:topicName", topic_name),
                ("PublishIMU.inputs:frameId", frame_id),
            ],
        },
    )


def setup_lidar_publisher(
    lidar_prim_path: str,
    topic_name: str,
    frame_id: str,
) -> None:
    """Create Replicator writer to publish LiDAR data to ROS2.

    Uses RtxLidarROS2PublishPointCloud writer.

    Args:
        lidar_prim_path: USD prim path of the LiDAR sensor.
        topic_name: ROS2 topic name (e.g., "/rover_0/lidar_3d/points").
        frame_id: TF frame ID.
    """
    # RTX LiDAR needs a render product
    hydra_texture = rep.create.render_product(lidar_prim_path, [1, 1], name="Isaac")

    writer = rep.writers.get("RtxLidar" + "ROS2PublishPointCloud")
    writer.initialize(topicName=topic_name, frameId=frame_id)
    writer.attach([hydra_texture])


def setup_clock_publisher() -> None:
    """Create OmniGraph nodes to publish simulation clock to ROS2."""
    og.Controller.edit(
        {"graph_path": "/ROS2_Clock", "evaluator_name": "execution"},
        {
            og.Controller.Keys.CREATE_NODES: [
                ("OnPlaybackTick", "omni.graph.action.OnPlaybackTick"),
                ("ReadSimTime", "isaacsim.core.nodes.IsaacReadSimulationTime"),
                ("PublishClock", "isaacsim.ros2.bridge.ROS2PublishClock"),
            ],
            og.Controller.Keys.CONNECT: [
                ("OnPlaybackTick.outputs:tick", "PublishClock.inputs:execIn"),
                ("ReadSimTime.outputs:simulationTime", "PublishClock.inputs:timeStamp"),
            ],
            og.Controller.Keys.SET_VALUES: [
                ("PublishClock.inputs:topicName", "clock"),
            ],
        },
    )


def setup_all_publishers(
    robot_name: str,
    sensor_prim_paths: dict[str, str],
    sensor_configs: dict[str, dict],
) -> list[str]:
    """Set up ROS2 publishers for all sensors on a robot.

    Args:
        robot_name: Robot identifier (e.g., "rover_0").
        sensor_prim_paths: Map of sensor_name → prim_path.
        sensor_configs: Map of sensor_name → config dict from YAML.

    Returns:
        List of created topic names.
    """
    topics = []

    for sensor_name, prim_path in sensor_prim_paths.items():
        cfg = sensor_configs.get(sensor_name, {})
        sensor_type = cfg.get("type", "")
        sub_topic = cfg.get("ros2_topic", get_default_sub_topic(sensor_type, sensor_name))
        frame_id = cfg.get("ros2_frame_id", f"{robot_name}/{sensor_name}")
        topic = build_topic_name(robot_name, sensor_name, sub_topic)

        try:
            if sensor_type == "camera":
                cam_type = "depth" if cfg.get("enable_depth", False) else "rgb"
                setup_camera_publisher(prim_path, topic, frame_id, cam_type)
            elif sensor_type == "imu":
                setup_imu_publisher(prim_path, topic, frame_id)
            elif sensor_type == "lidar":
                setup_lidar_publisher(prim_path, topic, frame_id)
            else:
                print(f"  [ros2] Unknown sensor type '{sensor_type}' for {sensor_name}")
                continue

            topics.append(topic)
            print(f"  [ros2] {sensor_name} → {topic}")
        except Exception as e:
            print(f"  [ros2] Warning: Failed to setup publisher for {sensor_name}: {e}")

    return topics
