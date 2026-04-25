# Colored RGB-D Point Cloud (XYZRGB)

Isaac Sim 5.1 의 `ROS2CameraHelper` 노드는 다음 `type` 토큰만 지원한다 (출처:
`/home/hoyunkim/isaacsim/exts/isaacsim.ros2.bridge/ogn/docs/OgnROS2CameraHelper.rst:53`):

```
rgb, depth, depth_pcl, instance_segmentation,
semantic_segmentation, bbox_2d_tight, bbox_2d_loose, bbox_3d
```

`depth_pcl` 은 **XYZ-only** point cloud 를 publish 한다. **XYZRGB (color point
cloud)** 타입은 Isaac Sim 측에서 직접 제공하지 않으므로, 표준 ROS 2 패턴으로
external fusion 을 사용한다.

## 권장: `depth_image_proc/point_cloud_xyzrgb_node`

Jazzy 부터 `image_pipeline` 패키지에 포함되어 있다. RGB image, depth image,
camera_info 를 받아 XYZRGB PointCloud2 를 합성해 publish 한다.

### 1. 패키지 설치 (Ubuntu 24.04 + ROS 2 Jazzy 기준)

```bash
sudo apt install ros-jazzy-image-pipeline
```

### 2. Launch 한 번에 띄우기 (composable container)

`launch/colored_pointcloud.launch.py` (사용자가 작성):

```python
from launch import LaunchDescription
from launch_ros.actions import ComposableNodeContainer
from launch_ros.descriptions import ComposableNode


def generate_launch_description():
    container = ComposableNodeContainer(
        name="rover_xyzrgb_container",
        namespace="",
        package="rclcpp_components",
        executable="component_container",
        composable_node_descriptions=[
            ComposableNode(
                package="depth_image_proc",
                plugin="depth_image_proc::PointCloudXyzrgbNode",
                name="point_cloud_xyzrgb_node",
                remappings=[
                    ("rgb/image_rect_color", "/rover/rgb/image_raw"),
                    ("rgb/camera_info", "/rover/rgb/camera_info"),
                    ("depth_registered/image_rect", "/rover/depth/image_raw"),
                    ("points", "/rover/depth/points_xyzrgb"),
                ],
            ),
        ],
        output="screen",
    )
    return LaunchDescription([container])
```

### 3. 실행

```bash
ros2 launch <your_package> colored_pointcloud.launch.py
```

`/rover/depth/points_xyzrgb` 토픽이 RViz `PointCloud2` Color Transformer
"RGB8" 로 설정하면 컬러 point cloud 로 시각화된다.

## 주의사항

1. **camera_info 토픽이 필요하다.** MarsLab 의 현 OmniGraph 는 RGB camera info
   를 publish 하므로 `/rover/rgb/camera_info` 가 자동으로 흐른다 (확인:
   `ros2 topic list | grep camera_info`).
2. **Frame_id 일치.** RGB image, depth image, output point cloud 모두
   `camera_optical_frame` 을 frame_id 로 가지고 있어야 한다 (Day 5 fix-up
   에서 모두 optical frame 으로 통일됨).
3. **Depth registered.** 이상적으로 depth 가 RGB 와 동일 viewpoint 로 align
   되어 있어야 한다. MarsLab 은 단일 RTX 카메라에서 RGB 와 depth 를 동시
   render 하므로 native align 상태 — 추가 registration 노드 불필요.
4. **샘플링 비용.** XYZRGB 는 XYZ 보다 4 배 페이로드 (RGB packed UINT32 추가).
   30 Hz × 640×480 = 약 9 MB/s. SLAM 만 하려면 XYZ 만 사용 권장.

## v1.5 follow-up

Native Isaac Sim 노드로 XYZRGB 를 직접 publish 하려면 custom OmniGraph
node 를 작성해야 한다 (replicator API + `ROS2PublishPointCloud` 결합).
v1.5 backlog 에 기록.
