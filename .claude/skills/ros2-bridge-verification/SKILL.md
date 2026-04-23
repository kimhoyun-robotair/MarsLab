---
name: ros2-bridge-verification
description: "MarsLab ROS2 브리지 검증. cmd_vel/TF/odometry/sensor publisher 토픽 레이트 측정, TF 체인 정합성 점검, QoS 프로파일 확인, ROS2 ↔ Isaac Sim 데이터 일관성 검증. 'ROS2 토픽 안 떠', '/cmd_vel 점검', 'TF 체인 깨졌어', 'odometry 레이트 측정', '센서 publisher 다시 검증', 'QoS 확인', 'ROS2 브리지 다시', 'topic hz 측정' 등의 요청에 반드시 사용. ROS2 통신 디버깅 시 이 스킬을 따른다."
---

# ros2-bridge-verification — MarsLab ROS2 브리지 검증

MarsLab의 `marslab/ros2_bridge/` 모듈이 Isaac Sim과 ROS2 간 데이터를 정확하고 일관된 레이트로 주고받는지 검증하는 워크플로우. Wk2 cmd_vel/TF/odometry 신규 구현 + Wk3 SLAM 통합의 전제 조건.

## Why this matters
ROS2 브리지의 버그는 다운스트림 SLAM·Nav2가 통째로 실패하게 만든다. 토픽이 "보이는데" 실제 데이터 shape이 잘못되거나 레이트가 명세보다 낮으면 SLAM 맵이 발산한다. 단순 `ros2 topic list`로 존재만 확인하는 것은 충분하지 않다 — **shape·rate·TF 체인 일관성**까지 검증해야 한다.

## 워크플로우

### Step 1: 토픽 스펙 문서 작성/업데이트
- `_workspace/ros2_topic_spec.md`에 다음을 표로 정리:

  | 토픽 | 타입 | 방향 | 레이트(Hz) | QoS | publisher 코드 | subscriber/소비자 |
  |------|------|------|----------|-----|--------------|----------------|
  | `/rover/cmd_vel` | `geometry_msgs/Twist` | 외부→sim | 10 | reliable, depth=10 | cmd_vel_subscriber.py | wheel control |
  | `/rover/odom` | `nav_msgs/Odometry` | sim→외부 | 30 | reliable | odometry.py | SLAM |
  | `/tf` | `tf2_msgs/TFMessage` | sim→외부 | 30 | reliable | tf_broadcaster.py | Nav2 |
  | `/rover/rgb/image_raw` | `sensor_msgs/Image` | sim→외부 | 10 | best_effort | publisher.py | perception |
  | ... | | | | | | |

- 이 문서가 `slam-nav-integrator`와 `robotics-mobility-lead` 사이의 진실 공급원.

### Step 2: 정적 검증 (오프라인)
- ros2_bridge/*.py를 grep으로 훑어 다음 체크:
  - publisher 생성 시 QoS 명시 여부
  - msg type import가 ros2 표준인가, 임의 자체 정의 아닌가
  - TF frame_id 네이밍이 CLAUDE.md 컨벤션 `/{robot_name}/{sensor_type}` 준수
  - seed 가 필요한 곳(노이즈 모델)에 파라미터화 되어있는가
- `tests/unit/test_ros2_bridge_contracts.py` 작성 — msg shape 검증을 mock으로 단위화.

### Step 3: 동적 검증 (사용자가 Isaac Sim + ROS2 실행)
사용자에게 다음 명령 실행 요청:
```
ros2 topic list
ros2 topic hz /rover/odom
ros2 topic hz /rover/rgb/image_raw
ros2 topic echo /tf --once
ros2 run tf2_tools view_frames
```

확인할 것:
- 모든 토픽이 spec과 일치하게 존재하는가
- 측정 hz가 spec ±10% 이내인가 (PLAN.md §6.2 기준)
- TF 체인이 `odom → base_link → {sensor_frames}` 로 끊김 없이 연결되는가
- `tf2_echo`로 임의 두 frame 간 변환이 가능한가

사용자에게서 결과를 받아 `_workspace/{wk}_ros2_bridge_verification.md`에 기록.

### Step 4: 실패 시 디버깅
- **토픽 없음**: launch 파일 로딩 확인, namespace 충돌 확인.
- **레이트 부족**: Isaac Sim render 모드(path-tracing은 느림), 노드 callback 블로킹, QoS depth 부족 점검.
- **TF 체인 끊김**: tf_broadcaster 가 일부 frame을 누락. base_link를 root로 모든 sensor frame이 등록되었는지 확인.
- **shape 불일치**: msg의 frame_id, header.stamp, child_frame_id 누락 확인.

수정은 `robotics-mobility-lead`가 담당. 이 스킬은 진단·증거 수집까지.

### Step 5: SLAM 입력 직전 sanity check
`slam-nav-integrator`가 SLAM 통합 시작 전:
- `/scan` 또는 LiDAR PointCloud2의 frame_id가 robot frame과 일치
- `/odom`의 child_frame_id가 base_link 와 일치
- `/tf`의 odom→base_link transform이 dynamic하게 갱신

이 셋 모두 OK면 Wk3 SLAM 통합 진행.

## 안전 원칙
- 외부 ROS2 패키지(slam_toolbox, nav2_*) 코드를 복사해서 marslab 안에 넣지 않는다(G3). launch·config로만 연동.
- 토픽 네이밍은 CLAUDE.md 컨벤션 엄수.
- QoS는 SLAM/Nav2 패키지가 기대하는 프로파일과 호환되어야 한다. 기본값 가정 금지.
- Isaac Sim integration test는 사용자가 직접 실행. 에이전트는 명령·기대 결과만 준비.

## 후속 작업 키워드
"ROS2 토픽 다시 점검", "TF 체인 재검증", "topic hz 다시 측정", "QoS 재조정", "브리지 회귀 점검", "SLAM 입력 sanity check" 등 후속 요청에도 사용. 이전 `_workspace/{wk}_ros2_bridge_verification.md`를 Read로 비교.

## 테스트 프롬프트
1. "/cmd_vel 보내는데 rover가 안 움직여. ROS2 브리지 점검해줘."
2. "SLAM 시작 전 토픽 sanity check 돌려줘."
3. "TF 체인 깨진 것 같음. 디버깅."
