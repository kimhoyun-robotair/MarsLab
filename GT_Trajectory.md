# GT_Trajectory & Wheel Odometry Split

이 문서는 2026-05-22 에 단행한 ROS2 토픽 재배치 — `/rover/odom` 이 가지던 두 역할 (GT + odometry) 을 분리하여 **GT 는 `/rover/GT_Trajectory` 로**, **실제 dead-reckoning odometry 는 새 wheel-encoder 적분기를 통해 `/rover/odom` 으로** 발행하도록 바꾼 작업의 배경과 사용법을 정리한다.

## 왜 분리했나

리팩토 직전까지 `/rover/odom` 은 다음 두 가지를 동시에 차지하고 있었다.

1. **데이터 출처**: `articulation.get_world_poses()` — PhysX 솔버가 매 step 마다 계산한 rigid-body world pose. 즉 시뮬레이션의 **정답 (ground truth)** 그 자체이며, 초기 pose 를 기준으로 frame 만 `odom` 으로 옮긴 것.
2. **토픽 이름**: `/rover/odom` (`nav_msgs/Odometry`) — ROS 컨벤션상 odometry 추정값이 와야 할 자리.

이 둘이 동일하다는 사실은 `MarsLab-Utils/GT/ate_analysis/ate_report.txt` 의 RMSE 가 **0.7 mm** 로 찍히는 결과로 그대로 드러났다. 보고서 본문에도 직접 명시되어 있다:

> "The rmse of ~0.7 mm reflects only the consistency between Isaac Sim's physics-integration ground-truth pose and the articulation-pose-read used to publish /rover/odom. Both originate from the same simulation step; this is NOT a measure of real SLAM accuracy."

즉 ATE 측정값이 **자기 자신과의 비교** 였다. 논문 quality 의 SLAM 평가가 불가능하다.

해법은 두 책임을 두 토픽으로 분리하는 것이다.

- `/rover/GT_Trajectory` — PhysX articulation pose 그대로 (frame shift 만 적용). ATE 측정 시 **참조값 (reference)**.
- `/rover/odom` — wheel-joint 회전속도를 skid-steer FK 로 적분하고 slip + Gaussian noise 를 주입한 **추정값 (estimate)**. SLAM 입력 및 ATE 측정 시 **비교 대상**.

## 어떻게 분리했나

| 영역 | 변경 |
|---|---|
| `configs/rover_m2020.yaml` | `topics:` 에 `gt_trajectory: "GT_Trajectory"` 추가. 최상위에 `wheel_odometry:` 블록 신설 (left/right joint 이름, track width, slip, sigma_omega, seed). |
| `marslab/ros2_bridge/wheel_odometry_publisher.py` | **신규 모듈.** `WheelOdometryContext` + `create_wheel_odometry_publisher()` + `publish_wheel_odometry()`. Skid-steer FK: `v = r·(ω_L + ω_R)/2`, `ω_z = r·(ω_R − ω_L)/W`. slip 은 `(1−s)` 곱셈, noise 는 `N(0, σ_ω)` 가산. Pose 는 Euler 적분 (yaw-only). |
| `marslab/ros2_bridge/rclpy_integration.py` | 기존 `create_odometry_publisher()` 호출의 topic 을 `topics["gt_trajectory"]` 로 바꾸고, frame_id="world" / child_frame_id="base_link_gt" / `publish_tf=False` 로 강제. 신규 wheel-odom publisher 를 `topics["odom"]` 으로 추가 발행. `publish_odom_tf` 플래그는 이제 wheel-odom 의 TF 권한을 제어한다. |
| `marslab/ros2_bridge/context.py` | `BridgeContext` 에 `wheel_odom_ctx: Optional[WheelOdometryContext]` 필드 추가. |
| `marslab/runtime/main_loop.py` | `LoopContext.wheel_odom_ctx` 필드 + `_publish_wheel_odometry()` 함수 + 매 step 호출. |
| `marslab/runtime/loop_context.py` | `bridge.wheel_odom_ctx` 를 `LoopContext.wheel_odom_ctx` 로 전달. |
| `marslab/main.py` | `_build_wheel_odom_params()` 헬퍼 추가 — YAML 의 `wheel_odometry:` 블록을 읽어 joint name 을 articulation DOF index 로 resolve. `init_rclpy_side(wheel_odom_params=...)` 로 전달. |

테스트 코드는 사용자 지시에 따라 추가하지 않았다.

## ATE 비교 시 어떤 토픽을 써야 하나

| 역할 | 토픽 | 메시지 타입 | 출처 |
|---|---|---|---|
| **Ground truth (참조)** | `/rover/GT_Trajectory` | `nav_msgs/Odometry` | PhysX articulation pose, frame_id=`world`, child=`base_link_gt` |
| **Ground truth (대체)** | `/rover/ground_truth/pose` | `geometry_msgs/PoseStamped` | `MarsLab-Utils/GT/gt_publisher` add-on (optional) |
| **Odometry estimate (측정)** | `/rover/odom` | `nav_msgs/Odometry` | Wheel-encoder FK + slip + Gaussian noise, frame_id=`odom`, child=`base_link` |
| **SLAM estimate (측정)** | `/rover/slam_pose` (외부 stack) | — | slam_toolbox / cartographer 등에서 publish |

### `MarsLab-Utils/GT/ate_analysis/analyze_ate.py`

기존 스크립트는 다음 두 토픽을 비교한다:

```python
TOPIC_GT   = "/rover/ground_truth/pose"   # geometry_msgs/PoseStamped
TOPIC_ODOM = "/rover/odom"                # nav_msgs/Odometry
```

이번 리팩토 이후:

- `TOPIC_GT` 는 그대로 둬도 된다 (`gt_publisher` add-on 이 제공).
- `TOPIC_ODOM` 도 그대로 — 단 이제 **실제로 의미 있는 wheel-odometry vs GT 비교** 가 된다. 0.7 mm 가 아니라 wheel slip / noise 누적에 따른 진짜 drift 가 측정된다.
- `TOPIC_GT` 를 `/rover/GT_Trajectory` 로 바꿔도 동일 결과 (다만 메시지 타입이 `nav_msgs/Odometry` 라서 `pose.pose` 경로로 한 단계 더 들어가야 한다).

### SLAM ATE 측정 워크플로 (논문용)

1. `marslab/main.py` 로 시뮬레이션 시작 → `/rover/GT_Trajectory`, `/rover/odom`, `/joint_states`, `/lidar/points`, `/scan` 등 동시 발행.
2. 외부에서 `slam_toolbox` 등을 launch — `/rover/odom` 을 odometry 입력으로, `/scan` 또는 `/lidar/points` 를 센서 입력으로 받아 `/rover/slam_pose` 같은 추정값 발행.
3. `ros2 bag record -o ate_run …` 로 `/rover/GT_Trajectory` + `/rover/slam_pose` 동시 캡처.
4. `analyze_ate.py` 의 `TOPIC_ODOM` 을 `/rover/slam_pose` 로 바꿔서 실행 → SLAM 의 진짜 ATE 산출.

Baseline (wheel-only) 측정은 `TOPIC_ODOM = "/rover/odom"` 그대로 두면 된다.

## Wheel odometry 수학 (참고)

`marslab/ros2_bridge/wheel_odometry_publisher.py` 에서 매 step 마다 다음을 수행한다.

```
ω_L_raw = mean(joint_velocities[left_indices])
ω_R_raw = mean(joint_velocities[right_indices])

ω_L = ω_L_raw · (1 − slip_left)  + N(0, σ_ω)
ω_R = ω_R_raw · (1 − slip_right) + N(0, σ_ω)

v   = r · (ω_L + ω_R) / 2
ω_z = r · (ω_R − ω_L) / W

θ += ω_z · dt
x += v · cos(θ) · dt
y += v · sin(θ) · dt
```

- `r` = `control.wheel_radius` (0.2667 m)
- `W` = `wheel_odometry.track_width` (= `control.track_middle` 기본값 2.369 m)
- `slip_*`, `σ_ω`, `seed` = `wheel_odometry:` YAML 블록
- `dt` = ROS clock 시간차 (max 0, last_stamp 없으면 0)

Yaw-only quaternion (`qw=cos(θ/2)`, `qz=sin(θ/2)`) 로 publish 되며 z 좌표는 0 으로 고정 (planar dead-reckoning).

## 토픽 / TF 권한 정리

- `/rover/GT_Trajectory` 는 `publish_tf=False` 로 강제 — TF tree 에 GT 가 끼어들지 않는다.
- `/rover/odom` 의 TF 발행 여부는 `ros2.publish_odom_tf` 플래그가 제어한다. 외부 SLAM 스택이 `odom → base_link` 를 발행한다면 `false` 로 두고, wheel-only 동작 시에는 `true` 로 켜면 된다.

## 참고 파일

- `marslab/ros2_bridge/wheel_odometry_publisher.py` — FK 적분기 본체
- `marslab/ros2_bridge/rclpy_integration.py` — 두 publisher 의 wiring
- `marslab/runtime/main_loop.py::_publish_wheel_odometry` — step 마다 호출
- `configs/rover_m2020.yaml` — `topics`, `wheel_odometry` 블록
- `MarsLab-Utils/GT/ate_analysis/analyze_ate.py` — ATE 분석 스크립트 (그대로 사용 가능)
