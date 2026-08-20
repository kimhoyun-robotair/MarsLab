# RGB-D color point clouds

MarsLab's Camera render product publishes RGB, depth, CameraInfo, and an XYZ
`PointCloud2` stream. The retained point cloud is intentionally XYZ-only;
color fusion is a separate ROS 2 consumer.

## Inputs

Use the matching Camera topics in the default namespace:

- `/rover/rgb/image_raw`
- `/rover/rgb/camera_info`
- `/rover/depth/image_raw`

All three messages use the Camera optical frame. The RGB and depth images are
rendered by the same Camera product, so no registration stage is required for
the supplied configuration.

## Optional fusion

Install the Jazzy image pipeline package and run the standard
`depth_image_proc` XYZRGB node in the ROS companion environment:

```bash
sudo apt install ros-jazzy-image-pipeline
ros2 run depth_image_proc point_cloud_xyzrgb_node \
  --ros-args \
  -r rgb/image_rect_color:=/rover/rgb/image_raw \
  -r rgb/camera_info:=/rover/rgb/camera_info \
  -r depth_registered/image_rect:=/rover/depth/image_raw \
  -r points:=/rover/depth/points_xyzrgb
```

The fused `/rover/depth/points_xyzrgb` output is external to MarsLab. Keep the
original `/rover/depth/points` stream for consumers that need XYZ only.
