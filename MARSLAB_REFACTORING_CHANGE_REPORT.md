# MarsLab runtime-refactor-v2 누적 변경 보고서

이 문서는 `marslab-runtime-refactor-v2`의 실행 기록이다. 기준선과 각 G1–G7
단계의 파일·심볼·`+/-` LOC, 에이전트 검증, 사용자 승인 토큰을 누적한다.
Isaac Sim/ROS 2 실행은 에이전트가 수행하거나 성공으로 주장하지 않는다.

## 기준선

- 기준 시각: 2026-08-17 (Asia/Seoul)
- `HEAD`: `e6a1c580657e81979a48de2435fa7306a54fc2c7`
- 기준 `git status --short`:

  ```text
   M .gitignore
  ?? MARSLAB_STALE_RESIDUE_AUDIT.md
  ?? MarsLab.pdf
  ?? MarsLab_refactoring.md
  ?? package-lock.json
  ```

- 추적 파일 수: `101` (`git ls-files | wc -l`).
- 추적 텍스트 LOC: `13272`줄. 재현 방법은 다음과 같다.

  ```bash
  git ls-files -z | xargs -0 -r file --mime-type | awk -F: '$2 ~ /text\// {print $1}' | xargs -r wc -l
  ```

  위 명령은 추적 파일 중 MIME이 `text/`인 파일만 골라 `wc -l`을 실행하며,
  마지막 합계가 기준선 결과다. 원문은
  `.omo/evidence/marslab-runtime-refactor-v2/task-1/baseline.txt`에 보관한다.

- 보호할 dirty 경로: `.gitignore`, `MarsLab.pdf`,
  `MARSLAB_STALE_RESIDUE_AUDIT.md`, `package-lock.json`.
  기준선에서 함께 dirty인 `MarsLab_refactoring.md`도 권위 문서로 보존한다.
- 역사 보존: 기존 `MARSLAB_S01_S03_CHANGE_REPORT.md`,
  `MARSLAB_S04_S05_REMOVAL_REPORT.md`, 모든 기존 `.omo` evidence와 완료된
  audit plan은 삭제·수정하지 않는다.

## 실패 우선 pin

기준선에서 다음 real-surface proof를 실행했다.

```bash
test -f MARSLAB_REFACTORING_CHANGE_REPORT.md && rg -n '^## (기준선|단계)|configs/config.yaml|APPROVE G1' MARSLAB_REFACTORING_CHANGE_REPORT.md
```

결과는 exit `1` (RED, 파일 부재)이며 출력은 없었다. 원문은
`.omo/evidence/marslab-runtime-refactor-v2/task-1/failing-first.txt`이다.

## 권위 결정과 퇴역 계획

- 제품 리팩터링 범위의 유일한 권위는 `MarsLab_refactoring.md`다.
- 퇴역한 계획 이름은 `.omo/plans/marslab-reference-runtime-refactor.md`와
  `.omo/plans/marslab-unification-refactor.md`다. 두 계획의 validator,
  RunPlan, doctor/validate/release-check, 이중 저장소 통합 의도는 재활성화하지
  않는다. 완료된 `marslab-v0-5-readonly-audit`와
  `marslab-stale-artifact-comment-audit` 계획·증거는 역사로 남긴다.
- 공식 실행 명령은 오직 다음 하나다.

  ```bash
  marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
  ```

  `main.py`는 필수 `--config` 하나만 받고 `--usda`, `--scene`,
  `--rover-usd`, `--scenario`, `--rover-yaml` 및 runtime override/console
  CLI를 제공하지 않는다.
- Scene USDZ와 Rover USD는 완성된 runtime 입력이다. runtime USD authoring,
  URDF 변환, RunPlan, asset-content validator, MarsLab-Utils 의존성은 없다.
- Python 3.11 Isaac 경계, strict immutable typed config, 한 번의 YAML 해석,
  기존 Isaac Sim 5.1 Camera/IMU/LidarRtx API를 유지한다.
- 센서 acquisition은 ROS와 독립적으로 만든다. 지원 출력은 Camera(RGB,
  Depth, CameraInfo 및 Camera 기반 PointCloud2), IMU, 3D LiDAR이며 2D LiDAR와
  LaserScan은 없다. 평가용 GT Pose와 노이즈 Wheel Odom은 서로 다른 출력으로
  모두 유지한다.
- GT Pose는 `map`/`base_link_gt` topic-only이며 TF를 발행하지 않는다.
  Wheel Odom은 `odom`/`base_link` topic이고 `wheel_odom.publish_tf`가
  `odom→base_link`의 단일 MarsLab authority를 선택한다.
- ROS 표준 `base_link`와 USD 루트 `Body_Chassis`를 모두 유지한다. companion
  launch의 단 하나의 identity static TF만 `base_link→Body_Chassis`를 연결하며,
  nameOverride·odom_anchor·`/tf_raw`·root rename·parent-anchor 우회 경로는 없다.
- AtmospherePanel은 유지한다. 테스트와 GitHub Actions는 정책상 삭제 대상이며,
  사용자 합의 없는 새 테스트는 추가하지 않는다.
- 모든 수정 source의 주석·docstring은 간결하게 유지한다: 모듈 요약 3–6줄,
  함수 역할 한 줄, 타입을 반복하는 Args/Returns·리뷰 이력·코드 재진술 금지.

## 통합 config 계약

정본은 `configs/config.yaml` 하나이며 모든 상대 경로는 이 파일이 선언된
디렉터리를 기준으로 해석한다. 최종 의도한 root는 다음과 같다.

```yaml
scene:
  usdz_path: <scene USDZ>
runtime:
  headless: <bool>
  ros2_enabled: <bool>
  atmosphere_enabled: <bool>
mars_env: <existing Mars environment fields>
rendering: <existing rendering fields>
rover:
  usd_path: <rover USD>
  <current rover fields nested below rover>
wheel_odom:
  publish_tf: <bool>
```

Camera, IMU, 3D LiDAR acquisition은 enable flag 없이 필수다. 태양 설정은
`mars_env`에만, spawn Z는 `rover.spawn.z_offset`에만 둔다. 중복 YAML/CLI
defaults, overlay/alias 및 제거된 2D LiDAR 키는 허용하지 않는다.

## 최종 runtime 계약

실행은 `--config`를 한 번 parse하고 경로를 고정한 뒤 `SimulationApp` 경계를
연다. 순서는 precheck/config → Scene USDZ/world → Rover spawn·physics →
Camera/IMU/3D LiDAR acquisition → 선택적 ROS 2/AtmospherePanel → LoopContext와
physics loop이며, 종료는 ROS·센서/graph·world/timeline·SimulationApp의 생성
역순 cleanup이다. raw YAML 재독, runtime USD authoring/변환, 별도 RunPlan은 없다.
센서 prim/render product/runtime handle은 ROS가 꺼져도 만들고, Python copy와
ROS transport는 실제 consumer가 있을 때만 수행하며 중복 센서를 만들지 않는다.

## 모델 라우팅과 QA 정책

- 일반 라우팅: LOW → `lazycodex-worker-low` (Luna), MEDIUM → Terra,
  HIGH·architecture/high-quality review → Sol. 실제 Task 1 경로는 **LOW/Luna**다.
- 에이전트는 YAML·CLI 정의, 정적 검색, 포맷/타입/컴파일, Git 상태만 검증한다.
  Kit boot, physics, rover, sensor, OmniGraph, ROS topic/TF/QoS/timestamp,
  cleanup, AtmospherePanel은 **PENDING USER** Isaac QA이며 PASS를 주장하지 않는다.
- 각 단계 승인 토큰은 침묵이나 명령 성공으로 추론하지 않는다. 사용자가 정확히
  `APPROVE G1`…`APPROVE G6`, 마지막에 `APPROVE RUNTIME-V2`를 보내야 다음
  단계가 열린다.

## G1–G7 재사용 단계 템플릿

| 단계 | 내부 작업 | 승인 토큰 | 변경 파일/심볼 및 누적 `+/-` LOC | 에이전트 명령·exit·증거 | 사용자 전용 QA/관찰 | 다음 unlock |
|---|---|---|---|---|---|---|
| G1 | Tasks 1–7, integrated config/schema | `APPROVE G1` (원문: `좋아 Approve G1`) | integrated config/schema · **`+284/-71`** | `<command>` · `<exit>` · `<evidence>` | **`G1 config facade PASS`**; stage commit: `8e25e38e4937ce4cdc1a3a8fb7b591448bad0168` (`refactor(config): add canonical runtime configuration`, 12 committed paths) | **Task8 (G2)** unlocked |
| G2 | Tasks 8–10, CLI/Python 3.11 launcher | `APPROVE G2` | product delta `+46/-103` (net `-57`) | non-Isaac contract checks PASS; evidence below | Isaac/Kit boot remains user-only | **Task11 (G3) unlocked** |
| G3 | Tasks 11–15, lifecycle/main loop | `APPROVE G3` | `<path>` · `<symbol>` · `+<n>/-<n>` | `<command>` · `<exit>` · `<evidence>` | `PENDING USER`: boot/physics/control/cleanup | G4 |
| G4 | Tasks 16–23, Camera/IMU/3D LiDAR and 2D deletion | `APPROVE G4` | `<path>` · `<symbol>` · `+<n>/-<n>` | `<command>` · `<exit>` · `<evidence>` | `PENDING USER`: retained sensor outputs | G5 |
| G5 | Tasks 24–28, ROS/TF/GT/Wheel integration | `APPROVE G5` | `<path>` · `<symbol>` · `+<n>/-<n>` | `<command>` · `<exit>` · `<evidence>` | `PENDING USER`: topics, QoS, single TF owners | G6 |
| G6 | Tasks 29–34, repository cleanup/documentation | `APPROVE G6` | `<path>` · `<symbol>` · `+<n>/-<n>` | `<command>` · `<exit>` · `<evidence>` | `PENDING USER`: diff/docs inspection | G7 |
| G7 | Tasks 35–36, final static gate and U1–U3 handoff | `APPROVE RUNTIME-V2` | `<path>` · `<symbol>` · `+<n>/-<n>` | `<command>` · `<exit>` · `<evidence>` | `PENDING USER`: exact Isaac/ROS U1–U3 results | F1–F4 |

각 단계 기록에는 승인 시각, 사용자가 본 결과, reviewed SHA, 다음 작업을 함께
추가한다. 승인 전 상태는 `PENDING USER`다.

## 누적 per-task 변경 표

| Task | 단계 | 실제 role/model | 파일 | 심볼/구간 | `+LOC` | `-LOC` | 명령/exit | evidence | 사용자 QA 상태 |
|---:|---|---|---|---|---:|---:|---|---|---|
| 1 | G1 | LOW/Luna (`lazycodex-worker-low`) | `MARSLAB_REFACTORING_CHANGE_REPORT.md` | 기준선·계약·G1–G7 템플릿 | `178` | `0` | see task-1 evidence | `.omo/evidence/marslab-runtime-refactor-v2/task-1/` | PENDING USER; Isaac 미실행 |

이 표는 이후 Task 2–36에서 exact file/symbol과 실제 `git diff --numstat`의
`+/-`를 행 단위로 누적한다. evidence와 report 외 파일은 이 Task 1에서 바꾸지
않는다.

## Task 1 검증 기록

- 역할/모델: LOW/Luna, `lazycodex-worker-low`.
- 보호 경로 checksum/status 비교, stale-state(현재 HEAD와 report checksum),
  misleading-success(명령 exit와 실제 report 내용)를 evidence에 기록한다.
- `malformed_input`, `prompt_injection`, `cancel_resume`, `hung_or_long_commands`,
  `flaky_tests`, `repeated_interruptions`: N/A. 이 문서·정적 명령 단계에서
  해당 입력/장기 실행/재시도 표면이 없다.
- 실행/수동 QA 결과는 `.omo/evidence/marslab-runtime-refactor-v2/task-1/`의
  `verification.txt`, `manual-qa.md`, `DoneClaim.md`에 고정한다.

## 승인 로그

| 단계 | 승인 토큰 | 시각 | 사용자 관찰 요약 | reviewed SHA | unlock |
|---|---|---|---|---|---|
| G1 | `APPROVE G1` | 2026-08-17 18:25:11 KST (+09:00) | `G1 config facade PASS`; cumulative **`+284/-71`** | `8e25e38e4937ce4cdc1a3a8fb7b591448bad0168` — `refactor(config): add canonical runtime configuration`; **12 committed paths** | **Task8 (G2) unlocked** |
| G2 | `좋아 이해했어. Approve G2` → `APPROVE G2` | `2026-08-17T19:54:41+09:00` | G2 non-Isaac contract checks PASS; product `+46/-103` (net `-57`) | `c0d3e09584469085a795d9941c4624a2082224c6` — `refactor(runtime): simplify config-driven startup`; 5 committed paths | **Task11 (G3) unlocked** |
| G3 | PENDING USER | — | — | — | — |
| G4 | PENDING USER | — | — | — | — |
| G5 | PENDING USER | — | — | — | — |
| G6 | PENDING USER | — | — | — | — |
| G7 | PENDING USER (`APPROVE RUNTIME-V2`) | — | — | — | — |

## Task 2 — 통합 YAML key/consumer 계약

### 계약 원칙

- 실제 현재 소비값을 통합 정본 `configs/config.yaml`의 한 위치에만 배치한다. 모든
  상대 경로는 **선언 파일인 `configs/config.yaml`의 디렉터리**를 기준으로
  해석한다. Scene과 Rover USD, URDF, HDRI, 3D LiDAR profile 경로에 별도
  기준·overlay·alias를 두지 않는다.
- 태양 위치의 출처는 `mars_env.sun_azimuth_deg`와
  `mars_env.sun_elevation_deg`뿐이다. `rendering`의 기존 intensity/color/diameter
  값이나 CLI에 위치 값을 복제하지 않는다. spawn Z의 출처는
  `rover.spawn.z_offset`뿐이며 `--z-offset` fallback을 만들지 않는다.
- Camera(RGB/Depth/CameraInfo/Camera PointCloud2), IMU, 3D LiDAR acquisition은
  항상 생성되는 필수 surface다. 세 센서에는 `enabled` 키를 두지 않는다.
  `rover.sensors.camera.depth_sensor.enabled`는 acquisition gate가 아니라 선택적
  depth simulation mode만 나타낸다. 2D LiDAR/LaserScan와 그 키는 계약에서
  제외한다.
- GT Pose와 Wheel Odom은 합치지 않는다. GT는
  `rover.ros2.topics.gt_trajectory`(map/base_link_gt, topic-only), Wheel은
  `rover.ros2.topics.odom`(odom/base_link)으로 서로 다른 topic을 사용한다.
  `wheel_odom.publish_tf`만 `odom→base_link` 동적 TF authority를 선택한다.

### 정본 root와 leaf inventory

```yaml
scene:
  usdz_path: <Scene USDZ; configs/config.yaml 기준 상대 경로>
runtime:
  headless: <bool>
  ros2_enabled: <bool>
  atmosphere_enabled: <bool>
mars_env: <현재 default.yaml의 모든 mars_env leaf>
rendering: <현재 default.yaml의 모든 rendering leaf>
rover:
  usd_path: <Rover USD; configs/config.yaml 기준 상대 경로>
  urdf_source_path: <configs/config.yaml 기준 상대 경로>
  prim_path: <USD prim>
  spawn: {mode, xy, z_offset, orientation_rpy}
  com_offset: <Vec3>
  angular_damping: <float>
  linear_damping: <float>
  chassis: {mass, inertia_xx, inertia_yy, inertia_zz}
  wheels: {mass, inertia_spin, inertia_transverse, friction_static,
           friction_dynamic, restitution}
  suspension: {rocker_damping, bogie_damping}
  ros2: <retained ROS 2 topics/rates/frames/QoS fields>
  sensors: <seed, mandatory camera/IMU/3D LiDAR and camera depth fields>
  control: <현재 control leaf 전부>
  wheel_odometry: <현재 wheel_odometry leaf 전부>
wheel_odom:
  publish_tf: <bool; 유일한 odom→base_link dynamic-TF switch>
```

`mars_env` leaf는 `gravity`, `dust_optical_depth`, `solar_constant`,
`sol_duration_seconds`, `sun_azimuth_deg`, `sun_elevation_deg`,
`physics_dt`, `dynamic_atmosphere.{enabled,time_scale,sun_sweep.{start_azimuth_deg,
end_azimuth_deg,max_elevation_deg},tau_profile,tau_constant.{base_tau},
tau_ramp.{start_tau,end_tau},tau_sine.{base_tau,amplitude,period_fraction},
update_interval_frames}`다. `rendering` leaf는
`{mode,sky_dome_hdri_dir,resolution,sun_intensity_scale,sun_color,
sun_angular_diameter_deg,dome_brightness_scale,fog_density_scale,fog_color,
sun_prim_path,dome_prim_path,fog.{enabled,color_amount,start_height,
height_falloff,height_density_ratio},ray_tracing.{antialiasing_op,dlss_exec_mode,
denoiser_indirect_diffuse,denoiser_reflections},path_tracing.{spp,total_spp,
max_bounces,denoiser_optix},sky_dome.{clear_rgb,dusty_rgb,tau_saturation,
brightness_min,brightness_decay,hdri_clear,hdri_moderate,hdri_dusty}}`다. 이 목록은
현재 두 YAML에 선언된 값과 runtime이 실제로 소비하는 strict-schema fields를
함께 고정하며, schema/Python default를 또 다른 YAML overlay로 복제하지 않는다.

`rover.ros2`의 retained leaf는 `namespace`,
`topics.{cmd_vel,robot_description,imu,imu_noisy,odom,gt_trajectory,rgb,depth,
points,camera_info,lidar,joint_states}`, `rates.{imu,odom,rgb,depth,points,
camera_info,lidar,joint_states}`, `odom_publisher.{frame_id,child_frame_id,
queue_size,gt_frame_id,gt_child_frame_id}`, `sensor_parent_frame_id`,
`graph_path`, `cmd_vel_queue_size`, `publish_pointcloud2`,
`publish_camera_info`, `publish_robot_description`, `publish_joint_states`,
`cmd_vel_qos`, `odom_qos`, `sensor_qos`, `tf_qos`다. `scan` topic/rate,
`enable_isaac_nameoverride`, `rename_root_to_base_link`, 그리고 기존
`publish_odom_tf` 이름은 retained leaf가 아니다.

`rover.sensors`의 retained leaf는 `seed`, `camera.{
local_translation,local_orientation_rpy_deg,resolution,focal_length,
clipping_range,depth_sensor.{enabled,baseline_mm,min_distance_m,max_distance_m,
noise_mean,noise_sigma,confidence_threshold,max_disparity_pixel}}`,
`lidar_3d.{local_translation,local_orientation_rpy_deg,range_min,
range_max,horizontal_fov_deg,vertical_fov_deg,rotation_rate_hz,profile_name,
profile_json_path,usd_profile,variant}`, `imu.{local_translation,
local_orientation_rpy_deg,sigma_lin_acc,sigma_ang_vel}`다. 이 계약에서는
`camera.enabled`, `imu.enabled`, `lidar_3d.enabled`를 선언하지 않는다. 현재
`sensor_spawner`와 `sensor_frames`는 `parent_link`를 읽지 않으므로 그
documentation-only field도 제거한다.

`rover.control`은 `wheel_radius`, `wheelbase`, `track_steer`, `track_middle`,
`max_linear_velocity`, `max_angular_velocity`, `drive_joint_names`,
`steer_joint_names`, `suspension_joint_names`, `suspension_damping`,
`drive_damping`, `drive_max_force`, `steer_stiffness`, `steer_damping`,
`steer_max_force`, `drive_type`, `negate_steer`, `max_wheel_accel_rate`,
`max_steer_angle`, `steer_ramp_rate`, `decel_multiplier`, `debug_logging`다.
`rover.wheel_odometry`는 `enabled`, `left_wheel_joints`, `right_wheel_joints`,
`track_width`, `slip_left`, `slip_right`, `sigma_omega`, `pose_diag`,
`twist_diag`를 보존한다. `wheel_odom.publish_tf`는 이 수치/토픽 필드와
중복되지 않는 별도 authority key다.

### Consumer-to-key reconciliation

| 현재 consumer (정적 source symbol) | 통합 key | 판정 |
|---|---|---|
| `main.main`: `args.usda` 및 `_reference_user_usda` | `scene.usdz_path` | `--usda` 제거 후 단일 Scene 입력 |
| `main.main`: `args.headless` | `runtime.headless` | CLI flag 제거 |
| `main.main`: `args.no_ros2` 분기 | `runtime.ros2_enabled` | inverse CLI flag/중복 default 제거 |
| `main.main`: `args.no_atmosphere` 및 AtmospherePanel gate | `runtime.atmosphere_enabled` | inverse CLI flag/중복 default 제거 |
| `runtime.atmosphere_boot.boot_atmosphere`, `main`: `mars_env_model` | `mars_env.*` including `physics_dt` and `dynamic_atmosphere.tau_*` | sun·gravity·dust·sol·physics tick·dynamic atmosphere 단일 출처 |
| `runtime.atmosphere_boot.boot_atmosphere`, rendering callbacks | `rendering.*` | fog/sky/path-tracing 포함 |
| `main`: `_PRE_S05_ROVER_USD_PATH`, `spawn_rover` | `rover.usd_path` | 하드코딩/별도 `--rover-usd` 제거 |
| `main._load_rover_cfg`, `main._resolve_spawn`, `robots.rover.spawn_rover` | `rover.urdf_source_path`, `rover.prim_path`, `rover.spawn.*`, `rover.com_offset`, `rover.angular_damping`, `rover.linear_damping` | Rover spawn 입력을 한 block으로 고정 |
| `robots.rover._apply_*_physics` | `rover.chassis.*`, `rover.wheels.*`, `rover.suspension.*` | 질량/관성/마찰/감쇠 모두 1회 매핑 |
| `robots.drive_api_setup.configure_drives`, `reinforce_pd_gains` | `rover.control.{drive_joint_names,steer_joint_names,suspension_joint_names,suspension_damping,drive_damping,drive_max_force,steer_stiffness,steer_damping,steer_max_force,drive_type}` | drive/steer 물리 설정 |
| `runtime.loop_context`, `runtime.main_loop`, `robots.rover_control` | `rover.control.{wheel_radius,wheelbase,track_steer,track_middle,max_linear_velocity,max_angular_velocity,negate_steer,max_wheel_accel_rate,max_steer_angle,steer_ramp_rate,decel_multiplier,debug_logging}` | 제어 계산/제한 |
| `main.spawn_sensors`, `runtime.sensor_frames` | `rover.sensors.seed`, `rover.sensors.camera.*`, `rover.sensors.imu.*`, `rover.sensors.lidar_3d.*` | 세 acquisition 필수; 2D consumer 없음 |
| `ros2_bridge.sensor_graph.build_sensor_graph` | `rover.ros2.graph_path`, `rover.ros2.topics.*`, `rover.ros2.rates.*`, `rover.ros2.publish_*`, `rover.ros2.sensor_qos`, `rover.ros2.tf_qos`, `rover.sensors.camera.depth_sensor.*` | Camera/IMU/3D LiDAR graph만 retained |
| `ros2_bridge.rclpy_integration.init_rclpy_side` | `rover.ros2.namespace`, `rover.ros2.topics.*`, `rover.ros2.odom_publisher.*`, `rover.ros2.cmd_vel_queue_size`, `rover.ros2.cmd_vel_qos`, `rover.ros2.odom_qos`, `rover.ros2.sensor_qos`, `rover.ros2.tf_qos`, `rover.urdf_source_path` | ROS node/publisher 입력 |
| `main._build_wheel_odom_params`, `runtime.main_loop._publish_wheel_odometry` | `rover.wheel_odometry.*`, `rover.control.wheel_radius`, `rover.ros2.topics.odom`, `wheel_odom.publish_tf` | Wheel Odom 수치/topic/TF authority |
| GT odometry publisher | `rover.ros2.topics.gt_trajectory`, `rover.ros2.odom_publisher.{gt_frame_id,gt_child_frame_id}` | `map`/`base_link_gt`, topic-only; Wheel과 topic 분리 |

따라서 표의 현재 consumer에는 미매핑 설정이 없다. `--scenario`,
`--rover-yaml`, `--z-offset`, `--sun-azimuth-deg`, `--sun-elevation-deg`,
`--headless`, `--no-ros2`, `--no-atmosphere`와 기존 두 YAML의 분리/중복
default는 최종 계약에서 제거하며 우선순위 overlay를 만들지 않는다. `scan`/2D
LiDAR, RunPlan, runtime USD content validation, `marslab.validation`,
`/World/odom_anchor`, `/tf_raw`, `isaac:nameOverride`, root rename, parent-anchor
및 외부/legacy TF bypass도 모두 제외한다. GT는 TF를 발행하지 않고,
`wheel_odom.publish_tf=false`일 때 MarsLab은 `odom→base_link` TF를 발행하지
않는다.

### Task 2 실행·검증 기록

- 라우팅: **LOW/Luna** (`lazycodex-worker-low`); 이 문서만 수정했다. Isaac/ROS
  runtime PASS는 주장하지 않으며 사용자 검증 상태는 `PENDING USER`다.
- 보고서 line delta: 기준선 178 lines → 현재 324 lines, 정확히 `+146/-0`이다.
  report가 기준선부터 untracked 문서라 `git diff --numstat` 자체는 빈 결과이며,
  이 수치는 pin의 line count와 post-append `wc -l`을 직접 뺀 값이다.
- Failing-first pin은 `.omo/evidence/marslab-runtime-refactor-v2/task-2/pin-before-edit.txt`에
  HEAD, report checksum/line count, exact RED command, live consumer inventory,
  YAML leaf inventory를 기록했다. RED 검색은 기존 Task 1 문구 때문에 exit 0이나
  `## Task 2`와 `scene.usdz_path`가 없어 **INCOMPLETE**임을 함께 고정했다.

## Task 3 — 설정 스키마에서 2D LiDAR/LaserScan 제거

- 라우팅: **LOW/Luna** (`lazycodex-worker-low`). 범위는 아래 네 스키마 파일뿐이며,
  YAML·loader·tests·plan·Boulder·ledger는 수정하지 않았다. Isaac Sim/ROS 2
  runtime은 실행하지 않았고 사용자 QA 상태는 **PENDING USER**다.
- 사전 pin: report SHA-256
  `9004680d6435f9e8c049dbac29629ca5e6d8d04482656d4c64b88946d2c69847`,
  `324` lines. `rg -n '^## Task 3' MARSLAB_REFACTORING_CHANGE_REPORT.md`
  는 exit `1`/무출력이었다. 원문은
  `.omo/evidence/marslab-runtime-refactor-v2/task-3/report/pre-edit-pin.txt`다.

| 파일 | 삭제된 심볼/필드/exports | 추가·보존된 심볼과 계약 | `+/-` (`git diff --numstat`) |
|---|---|---|---:|
| `marslab/config/schema/rover_sensors.py` | `EnabledLidar2DConfig`, `Lidar2DConfig`, `SensorsConfig.lidar_2d`, 두 2D `__all__` entries | `EnabledLidar3DConfig`가 직접 보유하는 `vertical_fov_deg`와 `check_range_and_profile`, Camera/IMU/3D LiDAR models | `+3/-13` |
| `marslab/config/schema/rover_ros2.py` | `RosTopicsConfig.scan`, `RosRatesConfig.scan` | `model_validator` import 및 `Ros2BridgeConfig.check_distinct_odom_topics`; `namespace`, `topics.odom`, `topics.gt_trajectory`, GT frame defaults와 Wheel `publish_odom_tf` 계약 보존 | `+12/-3` |
| `marslab/config/schema/__init__.py` | `Lidar2DConfig` import와 `__all__` export | 다른 public schema exports 보존 | `+0/-2` |
| `marslab/config/schema/robot.py` | 잔여 `Lidar2DConfig` import와 `__all__` export | 다른 robot exports 보존 | `+0/-2` |

Task 3의 정확한 schema `git diff --numstat` 합계는 **`+15/-20`**이다. Task 1–2는
report-only 변경이므로 제품 source 기준 Task 1–3 누적도 **`+15/-20`**이며, report
자체는 untracked 문서라 `git diff --numstat`에 포함되지 않는다. `git diff
--unified=0` 원문과 행별 reconciliation은
`.omo/evidence/marslab-runtime-refactor-v2/task-3/report/verification.txt`에
고정했다.

### 좁은 수리와 검증

- 좁은 수리 cycle 1: production package import gate에서 발견된 stale
  `Lidar2DConfig` import/export를 `schema/__init__.py`에서만 제거했다.
- 좁은 수리 cycle 2: 독립 verifier가 `schema/robot.py`의 같은 residue를 찾아,
  해당 파일에서 삭제 2줄만 추가했다. 두 cycle 모두 compatibility alias나 새
  abstraction을 만들지 않았다.
- 독립 확인 artifact는
  `.omo/evidence/marslab-runtime-refactor-v2/task-3/adversarial-verify/AdversarialVerify.md`
  이며 verdict는 **`confirmed`** (high confidence)다. 독립 확인은 schema-wide
  2D/LaserScan·삭제 symbol residue 부재, retained fields, malformed retired-key
  rejection, namespace-resolved GT/Wheel topic collision rejection을 직접
  관찰했다.
- Agent checks: production schema 전체 import exit `0`; `compileall` exit `0`;
  Ruff exit `0`; Black `--check` exit `0`; mypy exit `0`; source four-file
  `git diff --check` exit `0`; schema-wide retired-surface `rg` exit `1` (무매치);
  malformed `lidar_2d`/`scan` 및 resolved odom/GT collision probe exit `0`
  (각각 reject 확인). exact commands와 출력은
  `.omo/evidence/marslab-runtime-refactor-v2/task-3/report/verification.txt`에
  있다.
- Manual QA의 exact invocation은
  `sed -n '/^## Task 3/,/^## /p' MARSLAB_REFACTORING_CHANGE_REPORT.md`이며,
  파일·symbol·delta·checks·evidence·residual risk가 보이는지 확인했다. 이
  문서 QA는 PASS이고 Isaac/ROS runtime PASS는 주장하지 않는다.
- UltraQA: `dirty_worktree`, `stale_state`, `misleading_success_output`는
  각각 PASS (보호 dirty 경로 보존, bound HEAD/SHA 확인, exit·parsed fields·독립
  verdict 대조), `malformed_input`은 PASS; `concurrency/race`, `hung/long
  command`, `flaky_tests`, `repeated_interruptions`, `cancel_resume`,
  `prompt_injection`, `security/permissions`는 정적 문서·schema import 범위에
  해당 surface가 없어 N/A다. 상세는
  `.omo/evidence/marslab-runtime-refactor-v2/task-3/report/ultraqa.md`다.
- Cleanup: schema `__pycache__`/`.pyc`를 제거했고 최종 cache scan은 empty였다.
  임시 script·process·port는 없었으며 이번 시도에서 바뀐 경로는 이 report와
  `task-3/report/` evidence뿐이다.

### 잔여 위험

`configs/rover_m2020.yaml` legacy YAML에는 `sensors.lidar_2d`와 ROS `scan` keys가
아직 남아 있다. 이는 의도된 후속 작업이며 Tasks **5/29**에서 YAML·consumer/ROS
surface를 정리하기 전까지의 residual risk다; Task 3에서는 YAML을 수정하지 않았다.

## Task 4 — immutable integrated root configuration model (repair cycle 1)

- 라우팅: **MEDIUM/Terra** (`lazycodex-worker-medium`). Task 5의 canonical-tree
  RED가 Task 4의 첫 완료 주장을 재개방했다. 이번 수리는 `runtime.py`, `root.py`,
  `rover.py`, `rover_sensors.py`, `rover_ros2.py`, `schema/__init__.py`의 여섯
  production schema 파일만 다뤘으며 YAML, loader, CLI, tests, plan/ledger는
  수정하지 않았다. 이 단계는 offline Pydantic 경계만 검증하며 Isaac Sim/ROS 2
  runtime PASS는 주장하지 않는다.

| 파일 | Task 4 심볼/계약 및 repair | Task 4 `+/-` LOC |
|---|---|---:|
| `marslab/config/schema/runtime.py` | strict/frozen `RuntimeConfig`의 세 boolean과 신규 strict/frozen `WheelOdomConfig.publish_tf` | `+14/-0` |
| `marslab/config/schema/root.py` | `SceneConfig.usdz_path`; 여섯 필드 root `MarsLabConfig`: `scene`, `runtime`, `mars_env`, `rendering`, `rover`, `wheel_odom` | `+20/-3` |
| `marslab/config/schema/rover.py` | `RoverConfig.declaring_path` 제거, 필수 `usd_path: Path`로 교체 | `+1/-1` |
| `marslab/config/schema/rover_sensors.py` | Camera/3D LiDAR/IMU를 canonical strict/frozen models로 단순화; acquisition `enabled`·`parent_link` 제거 | `+3/-32` (Task 4 repair) |
| `marslab/config/schema/rover_ros2.py` | `publish_odom_tf`, name-override/root-rename fields 제거; GT/Wheel collision validator 유지 | `+0/-3` (Task 4 repair) |
| `marslab/config/schema/__init__.py` | root/runtime imports와 `MarsLabConfig` alias 제거; `RuntimeConfig`, `SceneConfig`, `WheelOdomConfig` exports | **Task 4 `+5/-1`** |

현재 aggregate diff에서 `schema/__init__.py`는 `+5/-3`이며, Task 3 소유인
`Lidar2DConfig` import와 `__all__` 삭제 `-2`줄은 Task 4에 재할당하지 않았다.
마찬가지로 `rover_sensors.py`의 Task 3 선행 delta `+3/-13`, `rover_ros2.py`의
Task 3 선행 delta `+12/-3`, `robot.py`의 `-2`는 보존해 분리했다. 따라서
Task 4 repair를 포함한 source delta는 정확히 **`+43/-40`**
(`14+20+1+3+0+5` / `0+3+1+32+3+1`)이며, Task 1–3 독립 source 합계
`+15/-20`에 더한 Task 1–4 누적 source 합계는 **`+58/-60`**이다.
행별 reconciliation과 current `git diff --numstat`는
`.omo/evidence/marslab-runtime-refactor-v2/task-4/report/verification.md`,
Task 5 RED/GREEN 수리는
`.omo/evidence/marslab-runtime-refactor-v2/task-4/repair-cycle-1.md`,
최종 독립 확인은
`.omo/evidence/marslab-runtime-refactor-v2/task-4/adversarial-verify/AdversarialVerify.md`
(`verdict: confirmed`)에 고정했다.

### Task 4 실행·검증 기록

- Failing-first pin: 최초 report SHA-256
  `e99688c0d9a31ffd71573a5f8462e914c7f8788eb43e390fcf1fb49d740661bc`, `390` lines;
  `rg -n '^## Task 4' MARSLAB_REFACTORING_CHANGE_REPORT.md`는 exit `1`/무출력이었다.
  repair RED는 동일 approved mapping이 `rover.declaring_path`, sensor
  `enabled`/`parent_link`, legacy `publish_odom_tf`를 잘못 요구하고
  `wheel_odom.publish_tf`를 거부한 것을 exit `0`의 caught `ValidationError`로
  고정했다. 원문은 `repair-cycle-1.md`다.
- GREEN canonical mapping scenario는 exit `0`이다. root fields는
  `['mars_env', 'rendering', 'rover', 'runtime', 'scene', 'wheel_odom']`,
  Runtime은 `headless`, `ros2_enabled`, `atmosphere_enabled`, Wheel Odom은
  `publish_tf`만 노출하며, Scene/Runtime/Wheel Odom/root가 strict/frozen이다.
  `RoverConfig.usd_path`는 required `pathlib.Path`이고 `declaring_path`는 없다.
  retained scene/runtime/Mars atmosphere/rendering/rover/sensor/ROS values와
  distinct GT/Wheel topics도 보존됐다.
- Malformed/strict scenario는 exit `0`: root unknown,
  `rover.declaring_path`, Camera/LiDAR/IMU `enabled`·`parent_link`,
  `rover.ros2.publish_odom_tf`, Wheel unknown이 모두 `extra_forbidden`; integer
  `wheel_odom.publish_tf=1`은 `bool_type`; root·Scene·Runtime·Wheel Odom
  mutation은 `frozen_instance`로 거부됐다. 동일 resolved GT/Wheel topic과
  slash-normalized collision도 `value_error`로 거부됐다.
- Final checks on the six repaired files: `python3 -m compileall -q` exit `0`;
  Black `--check` exit `0` (6 unchanged); Ruff exit `0` (all checks passed);
  mypy exit `0` (no issues in 6 source files); `git diff --check` exit `0`;
  canonical forbidden scan for `RunPlan|validation|lidar_2d|scan|MarsLab-Utils|/home/|declaring_path|publish_odom_tf|parent_link`
  exit `1` with no matches. The final adversarial artifact is independently
  **`confirmed`** and explicitly supersedes the prior five-field-root verdict.
- Intermediate limitations are named, not hidden: `load_rover_config` still
  fails on legacy split YAML (`usd_path` missing and stale `scan`/
  `publish_odom_tf`) until **Tasks 6–7** migrate loader/public exports; `import
  marslab.main` still fails on retired `EnabledImuConfig` until **Task 15** rewrites
  that consumer against the canonical root. These are not Task 4 runtime claims.
- Manual QA exact invocation is
  `sed -n '/^## Task 4/,/^## /p' MARSLAB_REFACTORING_CHANGE_REPORT.md`; the rendered
  section must show the six-field root, repair removals, exact separated deltas,
  checks, confirmed artifact, named limitations, and no-Isaac claim. Result is
  PASS in `.omo/evidence/marslab-runtime-refactor-v2/task-4/report/manual-qa.md`;
  user Isaac/ROS QA remains **PENDING USER**.
- UltraQA: `malformed_input`, `dirty_worktree`, `stale_state`, and
  `misleading_success_output` are PASS; the superseded claim and invalid first
  collision/gate outputs were explicitly revoked. `concurrency/race`,
  `hung/long command`, `flaky tests`, `cancel/resume`, `repeated interruptions`,
  `prompt injection`, `security/permissions`, ports, and processes are N/A because
  this is an offline immutable-schema surface. Details are in
  `.omo/evidence/marslab-runtime-refactor-v2/task-4/report/ultraqa.md`.
- Cleanup: generated schema `__pycache__`/`.pyc` and temporary loader/main captures
  were removed; final cache scan is empty. No temporary script, test, YAML, loader,
  process, port, container, or browser context remains.

### 잔여 위험

Canonical `configs/config.yaml` and declaring-directory path anchoring through
`load_config` are still deferred to **Tasks 5–6**; public canonical exports are
deferred to **Task 7**, and `main.py` consumer migration is deferred to **Task 15**.
The legacy failures above are therefore named intermediate limitations, not hidden
success claims. This Task 4 record contains no Isaac Sim/ROS 2 execution or runtime
asset behavior claim.

## Task 5 — canonical `configs/config.yaml`

- 라우팅: **LOW/Luna** (`lazycodex-worker-low`). 제품 변경 파일은 정확히
  `configs/config.yaml` 하나이며, 기존 `configs/default.yaml`과
  `configs/rover_m2020.yaml`은 보존했다. 이 기록은 offline YAML/schema 경계만
  검증하며 Isaac Sim/ROS 2 runtime PASS를 주장하지 않는다.
- 정본 root는 `scene`, `runtime`, `mars_env`, `rendering`, `rover`,
  `wheel_odom` 여섯 개다. `MarsLabConfig`가 이를 조합하고,
  `SceneConfig.usdz_path`, `RuntimeConfig`의 세 boolean,
  `RoverConfig.usd_path`, `WheelOdomConfig.publish_tf`를 canonical 계약으로
  고정한다. Camera/IMU/3D LiDAR acquisition block은 필수이며 acquisition
  `enabled`/`parent_link`와 2D LiDAR/`scan`은 없다.
- 모든 상대 경로는 선언 파일 `configs/config.yaml`의 디렉터리 기준이다.
  `scene.usdz_path`, `rover.usd_path`, `rover.urdf_source_path`,
  `rendering.sky_dome_hdri_dir`는 각각 Scene USDZ, Rover USD, URDF 파일,
  Mars sky 디렉터리로 해석된다. 이 Task는 Python-mode `Path`/tuple 변환이나
  production `load_config` 성공을 주장하지 않으며, 단일 read·anchoring은
  **Task 6** 소유다.

| 선언 경로 | YAML 값 | `configs/` 기준 대상 |
|---|---|---|
| `scene.usdz_path` | `../assets/scene/jezero_plain/jezero_plain.usdz` | `assets/scene/jezero_plain/jezero_plain.usdz` (file) |
| `rover.usd_path` | `../assets/robots/rover/m2020.usd` | `assets/robots/rover/m2020.usd` (file) |
| `rover.urdf_source_path` | `../assets/m2020-urdf-models/rover/m2020.urdf` | `assets/m2020-urdf-models/rover/m2020.urdf` (file) |
| `rendering.sky_dome_hdri_dir` | `../assets/mars_sky/` | `assets/mars_sky/` (directory) |

| 파일 | Task 5 심볼/계약 | `+/-` LOC |
|---|---|---:|
| `configs/config.yaml` | 여섯 canonical roots, retained Mars/rendering/Rover/ROS/sensor/control/wheel values, Scene/Rover paths, `wheel_odom.publish_tf` | **`+181/-0`** |

Task 1–4 product source 누적 `+58/-60`에 이 파일을 더한 Task 1–5 누적은
**`+239/-60`**이다. `configs/config.yaml`은 현재 untracked 파일이므로
`git diff --no-index --numstat /dev/null configs/config.yaml`이
`181  0  /dev/null => configs/config.yaml`을 출력하고 exit `1`을 반환한
것은 예상된 상태다. 정확한 identity/numstat와 현행 SHA는
`.omo/evidence/marslab-runtime-refactor-v2/task-5/report/verification.md`에
고정했다.

### Task 5 실행·검증 기록

- `sha256sum configs/config.yaml`은
  `c6ac6ac169f11caf9ca7b28d7e2da8dd9747ef8d227d6a0aa8f44170dc5c90ff`,
  `wc -l`은 `181`이다. `git diff --check -- configs/config.yaml`은 exit `0`이다.
- `yaml.safe_load` 후 `MarsLabConfig.model_validate_json`은 exit `0`이며,
  여섯 root, `camera`/`imu`/`lidar_3d`/`seed` sensor keys와
  `wheel_odom.publish_tf=True`를 출력했다. Scene/Rover/URDF/HDRI 네 경로의
  declaring-directory 해석은 모두 의도한 file/file/file/directory로 존재하며
  path probe exit은 `0`이다.
- 정확한 forbidden-key scan은 exit `1`/무출력이다(`lidar_2d`, `scan:`,
  `MarsLab-Utils`, `terrain:`, `/home/`, `declaring_path`, `parent_link`,
  `publish_odom_tf` 미검출). unknown root 및 retired `lidar_2d`/`scan` 변형은
  strict schema에서 `extra_forbidden`으로 거부됐고 probe exit은 `0`이다.
- 독립 recursive legacy reconciliation은 허용된 퇴역 surface 제거와
  `ros2.publish_odom_tf` → `wheel_odom.publish_tf` 단일 mapping을 적용한 뒤
  **`mismatch_count 0`** 및 `wheel_tf_mapping True`를 출력하고 exit `0`이었다.
  worker/verifier grouping이 달라진 leaf 총계는 이 보고서에 인용하지 않는다.
- 독립 확인 artifact는
  `.omo/evidence/marslab-runtime-refactor-v2/task-5/adversarial-verify/AdversarialVerify.md`
  (`verdict: confirmed`, high confidence)다. Manual QA exact invocation은
  `sed -n '/^## Task 5/,/^## /p' MARSLAB_REFACTORING_CHANGE_REPORT.md`이며
  PASS로 기록했다. 사용자 Isaac/ROS QA 상태는 **PENDING USER**다.
- UltraQA: `dirty_worktree`, `stale_state`, `misleading_success_output`,
  `malformed_input`은 PASS; prompt injection, cancellation/resume,
  hung/long, flaky/repeated interruption, concurrency, permissions/network,
  process/port surface는 이 offline 문서/YAML 범위에 없어 N/A다.
- Cleanup: `marslab/config` cache scan은 `cache_count=0`이다. 임시 script,
  test, mock, process, port, 외부 runtime을 생성하지 않았으며, 이 Task 기록은
  report와 `task-5/report/` evidence 외 경로를 수정하지 않았다.

## Task 6 — canonical `load_config`와 declaring-file 경로 anchoring

- 라우팅: **LOW/Luna** (`lazycodex-worker-low`). 제품 변경은
  `marslab/config/yaml_loader.py`의 `load_config(path: str | Path) -> MarsLabConfig`
  추가 40줄뿐이며, 현재 `git diff --numstat -- marslab/config/yaml_loader.py`는
  `40  0`이다. Task 5 누적 `+239/-60`에 더해 제품 source 누적은 정확히
  **`+279/-60`**이다. 이 단계도 offline YAML/schema 경계만 검증하며 Isaac Sim/
  ROS 2 runtime PASS를 주장하지 않는다.
- `load_config`는 declaring config path를 `resolve(strict=True)`로 고정하고,
  파일을 한 번 열어 `yaml.safe_load`를 한 번 실행한 뒤 mapping을
  `deepcopy`한다. AST 범위 검사는 file `.open` 1회, `safe_load` 1회,
  `MarsLabConfig.model_validate_json` 1회, `load_scenario_config`/
  `load_rover_config` 호출 0회를 확인했다 (`source-scan.txt`, exit `0`).
  검증은 한 번의 canonical model validation으로 끝나며 legacy loader를
  경유하지 않는다.
- 다음 네 선언 경로는 declaring file인 `configs/config.yaml` 기준으로
  절대 경로가 된다. 실제 production invocation은 정확한 값을 출력하고
  exit `0`이었다.

| 선언 경로 | 검증된 절대 경로 |
|---|---|
| `scene.usdz_path` | `/home/hoyunkim/MarsLab/assets/scene/jezero_plain/jezero_plain.usdz` |
| `rover.usd_path` | `/home/hoyunkim/MarsLab/assets/robots/rover/m2020.usd` |
| `rover.urdf_source_path` | `/home/hoyunkim/MarsLab/assets/m2020-urdf-models/rover/m2020.urdf` |
| `rendering.sky_dome_hdri_dir` | `/home/hoyunkim/MarsLab/assets/mars_sky` |

  `rover.sensors.lidar_3d.profile_json_path`는 canonical YAML의 `null`을
  보존해 검증 결과 `None`이며, 문자열일 때만 동일 declaring-file anchor
  branch를 탄다. 독립 확인 artifact는
  `.omo/evidence/marslab-runtime-refactor-v2/task-6/adversarial-verify/AdversarialVerify.md`
  (`verdict: confirmed`, high confidence)다.
- Strict/frozen/extra-forbid metadata는 `MarsLabConfig`에서
  `strict=True`, `frozen=True`, `extra="forbid"`로 확인됐다. malformed
  scenarios는 missing path와 `/dev/null` non-mapping을 nonzero로 거부하고,
  direct unknown-root 입력은 `extra_forbidden`을 포함해 거부했다. 이 결과와
  production 출력은 각각 `malformed-missing.txt`, `malformed-dev-null.txt`,
  `malformed-unknown-root.txt`, `manual-qa-production.txt`에 고정했다.
  offline import 후 `omni`/`isaacsim`/`pxr`/`rclpy` 모듈은 로드되지 않았다
  (`offline-import.txt`, exit `0`).
- Manual QA exact invocation은
  `sed -n '/^## Task 6/,/^## /p' MARSLAB_REFACTORING_CHANGE_REPORT.md`이며,
  이 section의 exact file/delta, one-read/one-validation/zero-legacy-call,
  네 absolute anchors, optional `None`, strict/malformed checks, confirmed
  artifact와 **no runtime claim**을 모두 표시하는지 확인한다. 사용자 Isaac/
  ROS 2 QA 상태는 **PENDING USER**다.
- Scope reconciliation note: implementation worker가 Task 6 범위를 벗어나
  plan/ledger를 조기에 변경했으며 parent executor가 이를 재조정했다. 이
  report append에서는 plan/ledger를 수정하지 않았고, 현재 scoped diff에도
  해당 경로가 없다. 이 기록은 그 조정 사실을 남길 뿐이며 runtime 성공을
  의미하지 않는다.
- UltraQA: `dirty_worktree`, `stale_state`, `misleading_success_output`,
  `malformed_input`은 각각 PASS로 독립 재검증했다. `prompt_injection`,
  `cancel_resume`, `hung/long command`, `flaky_tests`, `repeated_interruptions`,
  `concurrency/race`, `security/permissions`, network, process, port는
  bounded offline loader/report surface가 없어 N/A다. 상세는
  `.omo/evidence/marslab-runtime-refactor-v2/task-6/report/ultraqa.md`다.
- Cleanup: compileall이 만든 `marslab/config` `__pycache__`/`.pyc`는 제거했고
  cache scan은 empty다. 임시 script, test, fixture, process, port, container,
  browser context와 asset-content inspection은 없었다. report와
  `task-6/report/` evidence 외 product/plan/ledger 변경은 이번 append에서
  만들지 않았다.

### 잔여 위험

Task 7에서 canonical schema의 public export surface를 마무리해야 하며,
Task 15에서 `main.py`의 퇴역 `EnabledImuConfig` import를 canonical root
consumer로 교체해야 한다. 이 두 intermediate limitation은 Task 6 loader의
offline 성공과 별개이며, 이 Task 6 record는 Isaac Sim/ROS 2 runtime 실행을
포함하지 않는다.

## Task 7 — canonical config public facade와 migration-internal 경계

- 라우팅: **LOW/Luna** (`lazycodex-worker-low`). 제품 변경은 정확히 두 파일,
  `marslab/config/__init__.py`와 `marslab/config/loader.py`다. schema export
  lists는 확인만 하고 변경하지 않았다. 이 Task는 offline import/config facade만
  검증하며 Isaac Sim/ROS 2 runtime PASS를 주장하지 않는다.
- `marslab/config/__init__.py`: package-root `MarsLabConfig`를
  `marslab.config.schema.root`에서, `load_config`를
  `marslab.config.yaml_loader`에서 가져오며 exact `__all__`은
  **`["MarsLabConfig", "load_config"]`**다. 기존 root의
  `RoverConfig`, `ScenarioConfig`, `load_rover_config`,
  `load_scenario_config`는 import되지 않고 `hasattr(marslab.config, name)`도
  모두 false다.
- `marslab/config/loader.py`: migration wrapper의 exact `__all__`은
  **`["load_config"]`**이며 split loader 이름을 재광고하지 않는다. legacy
  구현 함수 `load_scenario_config`와 `load_rover_config`는
  `marslab.config.yaml_loader` 안에만 의도적으로 남아 직접 import할 수 있다.
  호환 alias, deprecation shim, registry, eager Isaac/ROS import, legacy loader
  호출은 추가하지 않았다.

| 파일 | Task 7 심볼/계약 | `+LOC` | `-LOC` |
|---|---|---:|---:|
| `marslab/config/__init__.py` | canonical root imports와 exact package `__all__` | 3 | 9 |
| `marslab/config/loader.py` | canonical-only migration wrapper와 exact `__all__` | 2 | 2 |
| **Task 7 합계** | 두 파일, public facade 경계 | **5** | **11** |

Task 6까지 독립적으로 재conciliate한 제품 누적 `+279/-60`에 Task 7
`+5/-11`을 더해 G1 Tasks 1–7 제품 누적은 정확히 **`+284/-71`**이다.
보고서와 `.omo/evidence/`는 stage 기록이며 이 제품 numstat에 포함하지 않았다.
Task 7 파일별 수치는 `git diff --numstat -- marslab/config/__init__.py
marslab/config/loader.py`에서 각각 `3 9`와 `2 2`로 재확인했다.

### Task 7 실행·검증 기록

- Public import invocation:
  `PYTHONDONTWRITEBYTECODE=1 python3 -c 'from marslab.config import MarsLabConfig, load_config; import marslab.config as c; print(c.__all__)'`
  는 exit `0`이며 `['MarsLabConfig', 'load_config']`를 출력했다.
  Canonical load invocation은 `configs/config.yaml`을 한 번의 public
  `load_config` 경계로 읽어 `MarsLabConfig`를 반환하고
  `scene.usdz_path`를 `/home/hoyunkim/MarsLab/assets/scene/jezero_plain/jezero_plain.usdz`로
  출력했다. exact root absence와 internal retention probe도 exit `0`이다:
  package root의 split four names는 absent, `loader.__all__`은
  `['load_config']`, `yaml_loader`의 두 legacy functions는 present다.
  원문은 `.omo/evidence/marslab-runtime-refactor-v2/task-7/public-api-qa.txt`다.
- Python 3.11 QA는
  `/home/hoyunkim/GeometricFoundationModelForSpaceRobotics/.tools/bin/uv run --no-project --python 3.11 --with 'pydantic>=2.0' --with 'pyyaml>=6.0' --with 'numpy>=1.24' python -c 'from marslab.config import MarsLabConfig, load_config; import marslab.config as c; cfg=load_config("configs/config.yaml"); print(c.__all__); print(type(cfg).__name__); print(cfg.scene.usdz_path)'`
  로 실행했고 exit `0`이다. 출력은 exact canonical `__all__`, `MarsLabConfig`,
  절대 Scene 경로였다. system `python3.11`의 의존성 부재는 repository를
  수정하지 않은 isolated environment로 보완했다. 원문은
  `.omo/evidence/marslab-runtime-refactor-v2/task-7/python311-qa.txt`다.
- Missing config와 `/dev/null` non-mapping은 모두 exit `0`의 rejection
  probe로 각각 `FileNotFoundError`, `ValueError`를 관찰했다. compileall,
  Ruff, Black `--check`, mypy, `git diff --check`는 모두 exit `0`이다.
  정적 원문은 `malformed-input.txt`와 `static-checks.txt`에 있다.
- Manual QA exact invocation은
  `sed -n '/^## Task 7/,$p' MARSLAB_REFACTORING_CHANGE_REPORT.md`다. 이
  명령으로 Task 7의 두 파일/심볼/`+5/-11`, exact exports, canonical load,
  root absence/internal retention, Python 3.11, checks, cleanup, limitations,
  G1 gate와 no-runtime claim을 확인하는 결과는 PASS다.
- UltraQA: dirty/stale/misleading-success/malformed는 PASS로 확인했다.
  network, ports, Isaac/ROS runtime, temporary tests/scripts, long-running
  process, user-only simulator behavior는 이 offline facade 범위에서 N/A다.
  compileall cache와 `.pyc`는 제거했고 최종 cache scan은 empty다. 임시
  script/test/process/port/container/browser context는 남기지 않았다.
- Worker DoneClaim가 언급한 `task-7/source-scan.txt`와
  `task-7/dirty-worktree.txt`는 현재 filesystem에 존재하지 않는다. 이를
  성공 증거로 사용하지 않으며, live 재실행 결과와
  `.omo/evidence/marslab-runtime-refactor-v2/task-7/report/independent-verification.md`
  및 `report/adversarial-verify/AdversarialVerify.md`가 해당 검증을 대체한다.

### Task 7 잔여 위험

후속 runtime consumer가 아직 package-root split names 또는
`EnabledImuConfig`를 참조할 수 있다. 이는 planned Tasks 8–15 migration의
책임이며, `yaml_loader` 내부 legacy functions는 planned Task 29까지 보존한다.
현재 `import marslab.main`도 이 legacy split import 경계 때문에 실패할 수
있으며, 이는 Task 15 consumer migration에서 해소할 명시적 intermediate
limitation이다.
이 Task 7 기록은 public import/loader 경계만 다루고 Isaac Sim boot, physics,
sensor, ROS topic/TF/QoS, cleanup 또는 기타 runtime 성공을 주장하지 않는다.

## G1 승인 — Tasks 1–7 통합 config/schema

- **승인 원문:** 사용자 입력 `좋아 Approve G1`.
- **정규화 토큰:** **`APPROVE G1`**.
- **승인 시각:** `2026-08-17 18:25:11 KST (+09:00)` (Asia/Seoul).
- **사용자 관찰:** **`G1 config facade PASS`**.
- **검증 누적:** Tasks 1–7 product delta **`+284/-71`**.
- **G1 stage commit:** **`8e25e38e4937ce4cdc1a3a8fb7b591448bad0168`** —
  `refactor(config): add canonical runtime configuration`; **12 committed paths**.
- **G1 변경/생성 파일:**
  `MARSLAB_REFACTORING_CHANGE_REPORT.md` (stage report),
  `configs/config.yaml` (canonical YAML, 신규),
  `marslab/config/__init__.py`, `marslab/config/loader.py`,
  `marslab/config/yaml_loader.py`, `marslab/config/schema/__init__.py`,
  `marslab/config/schema/robot.py`, `marslab/config/schema/root.py`,
  `marslab/config/schema/runtime.py` (신규),
  `marslab/config/schema/rover.py`,
  `marslab/config/schema/rover_ros2.py`,
  `marslab/config/schema/rover_sensors.py`. G1에서 삭제된 제품 파일은 없다.
  보호된 사용자 dirty 경로 `.gitignore`, `MARSLAB_STALE_RESIDUE_AUDIT.md`,
  `MarsLab.pdf`, `MarsLab_refactoring.md`, `package-lock.json`은 보존했다.
- **누적 product delta:** Task 1 report-only를 제외한 Tasks 1–7 제품 누적은
  **`+284/-71`** (`+` 284, `-` 71)다. 구성 요소는 Task 3 `+15/-20`,
  Task 4 `+43/-40`, Task 5 `+181/-0`, Task 6 `+40/-0`, Task 7 `+5/-11`이며,
  Task 1–2는 product delta `+0/-0`이다. Task 7 exact numstat은 위 표와
  `git diff --numstat` 명령 결과로 재확인했다.
- **에이전트 검증:** Tasks 1–7의 각 evidence에서 선언된 LOW/Luna 또는
  Task 4 MEDIUM/Terra route, static import/YAML/schema checks, compile/format/
  lint/type checks, malformed rejection, canonical path anchoring, public API
  probes를 확인했다. 최신 Task 7 artifact는
  `.omo/evidence/marslab-runtime-refactor-v2/task-7/report/DoneClaim.md`이며,
  Task별 독립 확인 artifact는 각 `task-{1..7}` evidence 아래에 있다.
- **사용자 inspection/commands 및 기대 결과:**
  `sed -n '/^## Task 7/,$p' MARSLAB_REFACTORING_CHANGE_REPORT.md` → Task 7
  record와 이 G1 gate가 모두 보이면 PASS; 누락/잘못된 delta·runtime claim이면
  FAIL. `git diff --numstat -- marslab/config/__init__.py marslab/config/loader.py`
  → `3 9` 및 `2 2`면 PASS. `PYTHONDONTWRITEBYTECODE=1 python3 -c 'from marslab.config import MarsLabConfig, load_config; import marslab.config as c; assert c.__all__ == ["MarsLabConfig", "load_config"]; assert load_config("configs/config.yaml").scene.usdz_path.is_absolute(); assert not any(hasattr(c, n) for n in ("ScenarioConfig", "RoverConfig", "load_scenario_config", "load_rover_config")); print("G1 config facade PASS")'` → exact PASS line이면 PASS; import, root exports, path, or absence assertion failure이면 FAIL. Isaac/ROS runtime QA is outside this config-facade approval and has not been run here.
- **남은 위험:** `main.py`와 later runtime consumers의 migration, Isaac Sim/ROS
  boot·physics·sensor·OmniGraph·topic/TF/QoS·AtmospherePanel·cleanup은 아직
  후속 Tasks/Gates 또는 사용자 전용 QA다. Legacy split functions remain only
  in `yaml_loader` by design; no runtime claim is made here.
- **다음 unlock:** **Task8 (G2 Tasks 8–10)** — **unlocked**.

## Task 8 — config-only CLI argument parser

- **라우팅:** **LOW/Luna** (`lazycodex-worker-low`). 이 단계의 제품 변경은
  `marslab/main.py`의 `main()` parser block(lines 409–414) 하나로 한정했다.
  `ArgumentParser`는 `allow_abbrev=False`를 사용하고, 정확히
  `parser.add_argument("--config", required=True, help="Path to the integrated config YAML.")`
  하나만 선언한 뒤 `parser.parse_args()`를 호출한다. parser는 경로를
  반환하기만 하며 YAML을 읽지 않는다.
- **제품 delta:** `git diff --numstat -- marslab/main.py`의 live 결과는
  `3 77 marslab/main.py`, 즉 **`+3/-77`**이다. G1 Tasks 1–7의 승인된
  **`+284/-71`**에 더하면 G1+Task8 제품 누적은 정확히
  **`+287/-148`**이다. 보고서와 evidence는 이 제품 수치에 포함하지 않는다.
- **정확한 parser semantics:** AST scan은 `add_argument` 한 건
  `[(413, ['--config'], True)]`, `parse_args` line `414`를 확인했다. parser
  region(lines 409–414)에는 11개 문서화된 legacy flags
  (`--usda`, `--scene`, `--rover-usd`, `--scenario`, `--rover-yaml`,
  `--headless`, `--no-ros2`, `--no-atmosphere`, `--z-offset`,
  `--sun-azimuth-deg`, `--sun-elevation-deg`)와 파일 read token이 없다.
  `--config configs/config.yaml`은 exit `0`으로 path string을 그대로
  반환하고 파일을 열지 않으며, 누락 `--config`, legacy `--usda`, extra
  positional, `run` subcommand, abbreviated `--con`은 각각 argparse exit
  `2`로 거부된다.
- **검증 명령/증거:** AST manual-QA invocation은 다음이며 출력은
  `[['--config']]`이다.

  ```bash
  python3 -c 'import ast, pathlib; t=ast.parse(pathlib.Path("marslab/main.py").read_text()); calls=[n for n in ast.walk(t) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr=="add_argument"]; print([[a.value for a in c.args if isinstance(a, ast.Constant) and isinstance(a.value,str)] for c in calls])'
  ```

  `python3 -m compileall -q marslab/main.py`, `ruff check marslab/main.py`,
  `black --check marslab/main.py`, and `git diff --check` all exited `0`.
  Independent verifier artifact는
  `.omo/evidence/marslab-runtime-refactor-v2/task-8/adversarial-verify/AdversarialVerify.md`
  (`verdict: confirmed`)이며 worker 기록은
  `.omo/evidence/marslab-runtime-refactor-v2/task-8/DoneClaim.md`와
  `.omo/evidence/marslab-runtime-refactor-v2/task-8/post-checks.txt`다.
- **Manual QA:** `sed -n '/^## Task 8/,$p' MARSLAB_REFACTORING_CHANGE_REPORT.md`
  실행 결과 이 section의 exact `main.py` parser symbols, `+3/-77`, cumulative
  `+287/-148`, parser semantics/checks, Task 15 limitation, cleanup, and
  no-runtime statement가 모두 보이면 **PASS**다. Append 전 pin은
  `.omo/evidence/marslab-runtime-refactor-v2/task-8/report/pre-edit-pin.md`에
  기록했으며, 당시 report checksum은
  `562a29b4e0142ee32dc5093328378439be4a4671880b6c25d98b4db990f4e660`,
  745 lines, `^## Task 8` scan exit `1`/empty였다.
- **Task 15 limitation:** parser만 전환했으므로 `main()` downstream은 아직
  `args.usda`, `args.rover_yaml`, `args.scenario`, `args.sun_*`,
  `args.z_offset`, `args.headless`, `args.no_atmosphere` 등을 참조한다.
  이 legacy consumer migration은 Task 15의 책임이며 Task 8에서 우회·호환
  alias를 추가하지 않았다.
- **UltraQA:** `malformed_input`, `dirty_worktree`, `stale_state`,
  `misleading_success_output`는 각각 PASS로 독립 재검증했다. 해당 parser
  시나리오는 bounded offline 검사이며 prompt injection, cancellation,
  hung/long, flaky/repeated interruption은 N/A다. **Isaac Sim, Kit, ROS 2,
  physics, sensors, OmniGraph, topics/TF/QoS, cleanup runtime은 실행하지
  않았고 성공을 주장하지 않는다.**
- **Cleanup:** Task 8 checks가 생성한 `marslab` cache를 explicit safe
  commands로 삭제했다. Task 7 종료 evidence의 `cache_count=0` 이후 이번
  Task 8 checks가 만든 현재 residue만 대상으로 했다: `find marslab -type f -name '*.pyc' -delete` 및
  `find marslab -depth -type d -name '__pycache__' -empty -delete`.
  최종 `.pyc`와 empty `__pycache__` count는 모두 `0`이며, tests/scripts/
  processes/ports를 만들지 않았다. G2 approval is recorded below; Isaac/Kit
  runtime remains user-only.

## Task 9 — Isaac launcher 위생과 Python 3.11 실행 메타데이터

- **라우팅:** **MEDIUM/Terra** (`lazycodex-worker-medium`). 제품 변경은 정확히
  `marslab/isaac_python.sh`와 `pyproject.toml` 두 파일에 한정됐다. 실제 Isaac
  Sim/Kit/ROS 2 실행은 사용자 검증 범위이며 이 기록에서 실행하거나 성공을
  주장하지 않는다.
- **제품 delta:** live `git diff --numstat -- marslab/isaac_python.sh pyproject.toml`
  결과는 각각 `16 22`와 `4 4`다. 따라서 Task 9는 **`+20/-26`**이다. Task 8까지
  누적 **`+287/-148`**에 더하면 G2 누적은 정확히 **`+307/-174`**다. 보고서와
  evidence는 이 product 수치에 포함하지 않는다.

| 파일 | Task 9 계약 | `+LOC` | `-LOC` |
|---|---|---:|---:|
| `marslab/isaac_python.sh` | wrapper 위치 기반 repository-root, ROS/ament/colcon 위생, root-only `PYTHONPATH`, Isaac `exec "$@"` | 16 | 22 |
| `pyproject.toml` | Python 3.11 package/Black/Ruff/mypy metadata, no project script | 4 | 4 |
| **Task 9 합계** | 두 파일, launcher/process 경계와 Python 3.11 계약 | **20** | **26** |

### Task 9 실행·검증 기록

- `marslab/isaac_python.sh`는 `BASH_SOURCE[0]`로 wrapper directory와 repository
  root를 계산해 caller cwd에 의존하지 않는다. 상속된 `PYTHONPATH`를 버리고
  repository root만 `export PYTHONPATH="$_REPOSITORY_ROOT"`로 전달하며,
  `/opt/ros` 경로를 `LD_LIBRARY_PATH`, `PYTHONPATH`, `CMAKE_PREFIX_PATH`,
  `PKG_CONFIG_PATH`, `PATH`에서 제거하고 ROS/ament/colcon 상태 변수를 unset한다.
  Isaac `python.sh`가 실행 가능하지 않으면 nonzero로 종료하고, 실행 경계는
  literal `exec "$ISAAC_PY" "$@"`로 caller 인자를 변경 없이 전달한다.
- `ISAAC_SIM_PATH=/definitely/missing/marslab-isaac marslab/isaac_python.sh marslab/main.py --config configs/config.yaml`와
  동일한 빈 인자 invocation은 모두 exit `1`, stdout empty, concise한 두 줄
  missing-`python.sh`/설치 안내 stderr만 관찰했다. `/tmp`에서 절대 경로 wrapper의
  root 계산과 `$@` 전달 토큰도 재확인했다. 어느 시나리오도 Isaac을 boot하지 않았다.
- `pyproject.toml` metadata probe는 `requires-python == ">=3.11"`, Black
  `['py311']`, Ruff `py311`, mypy `3.11`을 확인했고 `project.scripts`와
  `marslab.cli`는 존재하지 않는다. Python 3.12 전용 syntax/API나 host-Python
  re-exec 경로는 추가되지 않았다.
- `bash -n marslab/isaac_python.sh`, exact TOML assertions, launcher static
  sanitation/root/exec scan, missing-path normal/empty-args probes, other-cwd
  scan, `black --check --config pyproject.toml marslab/__init__.py`,
  `ruff check --config pyproject.toml marslab/__init__.py`, 그리고
  `git diff --check -- marslab/isaac_python.sh pyproject.toml`가 모두 exit `0`
  (missing-path probes만 의도된 exit `1`)였다. 원문 worker artifact는
  `.omo/evidence/marslab-runtime-refactor-v2/task-9-marslab-runtime-refactor-v2.txt`,
  독립 확인은
  `.omo/evidence/marslab-runtime-refactor-v2/task-9/adversarial-verify/AdversarialVerify.md`
  (`verdict: confirmed`)다.
- Root verifier는 현재 product source/delta와 모든 적용 가능한 launcher/
  metadata 조건을 **confirmed**로 판정했다. 다만 worker가 independent root
  verification 전에 orchestrator-owned plan의 Task 9 checkbox와 ledger의
  `task-completed` record를 조기에 변경했다. 따라서 이 report append는
  plan/ledger를 수정하지 않았다. 이후 parent executor가
  `.omo/evidence/marslab-runtime-refactor-v2/task-9/root-adversarial-verify/AdversarialVerify.md`,
  `task-9/adversarial-verify/AdversarialVerify.md`,
  `task-9/report/adversarial-verify/AdversarialVerify.md`를 함께 확인하고
  ledger의 `task-completion-reconciled` record를 기록했으므로 parent
  reconciliation은 **COMPLETED**다. 조기 mutation은 여전히 orchestration
  scope violation으로 보존하지만, 현재 completion binding은 독립
  product/root/report evidence에 의해 유효하다.
- Manual QA exact invocation은
  `sed -n '/^## Task 9/,$p' MARSLAB_REFACTORING_CHANGE_REPORT.md`다. 이
  명령에서 Task 9 heading, 두 파일의 `+16/-22`·`+4/-4`, 합계 `+20/-26`,
  누적 `+307/-174`, MEDIUM/Terra attribution, launcher sanitation/root/
  `exec "$@"`/missing-path behavior, Python 3.11 metadata, evidence 경로,
  premature plan/ledger note와 no-runtime claim이 모두 보이면 **PASS**다.

### Task 9 UltraQA와 cleanup

- `malformed_input`: nonexistent Isaac root normal/empty-args가 exit `1`로
  pre-exec reject되고 stderr/stdout observables가 정확히 일치해 **PASS**.
- `dirty_worktree`: live owned-file diff가 launcher와 `pyproject.toml` 두 경로만
  가리키고 unrelated dirty paths는 보존되어 **PASS**.
- `stale_state`: source를 재독해 SHA-256와 static predicates를 현재
  worktree에서 재생성해 **PASS**.
- `misleading_success_output`: missing-path에서 stdout/성공 문구/env dump가
  없고 concise error만 남아 **PASS**. `prompt_injection`, cancel/resume,
  hung/long, flaky/repeated interruption은 bounded offline launcher surface에
  해당하지 않아 **N/A**다.
- 검증 중 Isaac/ROS process, port, temporary script, fake launcher/shim,
  test, cache 또는 browser context를 만들지 않았다. `marslab/` product tree의
  scoped cache scan은 `pyc=0`, `__pycache__ dir=0`이다. Repo-wide scan은
  기존 unrelated `tests/refactor/__pycache__` 아래 `pyc=9`, dir=1을
  관찰했으며 이를 Task 9 residue로 귀속하지 않는다. 이 append에서 수정한
  것은 report와 `task-9/report/` evidence뿐이다.
  G2 approval is recorded below; this Task 9 record does not claim runtime
  Kit/physics/sensors/ROS topic·TF/QoS success.

## Task 10 — typed runtime preparation phase

- **변경/목적:** 새 모듈 `marslab/runtime/prepare.py`의
  `prepare_config(config_path)`가 config·Scene USDZ·Rover USD의 regular-file
  조건을 부팅 전에 값싸게 확인하고 typed immutable `MarsLabConfig`를
  반환한다. 유효 입력에서 공개 `marslab.config.load_config`는 정확히 한 번
  호출된다. USD 내용·joint·prim 검사는 없으며 Isaac/Omni/pxr/rclpy import와
  `SimulationApp` boot도 없다.
- **제품 LOC:** 모듈 전체는 **`+23/-0` physical lines**(nonblank/noncomment
  `15`)이다. Task 9 누적 `+307/-174`에 더한 제품 누적은 정확히
  **`+330/-174`**다. 제품 LOC이며 이 보고서/evidence 문서 LOC는 제외한다.
- **검증 방법/결과:**
  `.omo/evidence/marslab-runtime-refactor-v2/task-10/task-10-marslab-runtime-refactor-v2.txt`
  의 canonical invocation은 exit `0`으로 `MarsLabConfig`와 두 절대 regular
  file 경로를 출력했고 missing/non-regular config·Scene·Rover는
  `FileNotFoundError`로 거부했다. 독립
  `.omo/evidence/marslab-runtime-refactor-v2/task-10/adversarial-verify/AdversarialVerify.md`
  (`verdict: confirmed`)가 loader 호출 수 `1`, frozen 반환값, 금지 import와
  content validation 부재를 정적·동적 probe로 재확인했다. compileall(3.11
  포함), Ruff, Black, mypy, `git diff --check`는 모두 exit `0`이다.
- **범위/제외 및 G2:** product test·YAML fixture·runtime process는 만들거나
  실행하지 않았다. `dirty_worktree`, `stale_state`,
  `misleading_success_output`는 scoped diff/hash와 독립 재실행으로 확인했고,
  malformed YAML은 public loader 책임으로 두었다. G2에서는 non-Isaac
  preparation/launcher contract check만 요청한다. 실제 Isaac Sim/Kit
  runtime 검증은 Task 10 범위가 아니며 후속 gate의 사용자 소유다.

## G2 승인 — Tasks 8–10 CLI/Python 3.11 launcher

- **승인 원문:** `좋아 이해했어. Approve G2`.
- **정규화 토큰:** **`APPROVE G2`**.
- **승인된 implementation commit:**
  **`c0d3e09584469085a795d9941c4624a2082224c6`** —
  `refactor(runtime): simplify config-driven startup`.
- **정확한 committed paths (5):**
  `MARSLAB_REFACTORING_CHANGE_REPORT.md`, `marslab/isaac_python.sh`,
  `marslab/main.py`, `marslab/runtime/prepare.py`, `pyproject.toml`.
- **제품 delta (report/evidence 제외):** **`+46/-103`**, net **`-57`**.
- **다음 unlock:** **Task11 (G3 Tasks 11–15) — unlocked**. Isaac/Kit runtime
  관찰은 계속 사용자 전용이다.
