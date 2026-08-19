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
| G3 | Tasks 11–15, lifecycle/main loop | `APPROVE G3` | Tasks 11–15 product subtotal **`+921/-871` (net `+50`)**; Task15 final **`+199/-842` (net `-643`)** | static/offline checks PASS; user runtime PASS evidence below | **runtime PASS; 사용자 승인 기록 완료**; exact token **`APPROVE G3`** | **Task16 (G4) unlocked** |
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
| 16 | G4 | LOW/Luna (`lazycodex-worker-low`) | 신규 product file 없음; `marslab/config/schema/rover_sensors.py`, `configs/config.yaml`, `marslab/sensors/sensor_spawner.py` 현재 상태 재검증 | retained Camera/IMU/Lidar3D schema와 chassis parent contract (기존 `8e25e38` 상태) | `0` | `0` | canonical loader/model/source probe · `0`; compile/Ruff/basedpyright/diff checks · `0` | `.omo/evidence/marslab-runtime-refactor-v2/task-16/` 및 `adversarial-verify/final.md` | PENDING USER; G4 미승인 |
| 18 | G4 | LOW/Luna (`lazycodex-worker-low`) | `marslab/sensors/camera_spawner.py` 신규, `marslab/sensors/sensor_spawner.py` 추출 위임 | typed `CameraConfig`, Camera prim/RP/annotator acquisition, legacy `SensorHandles` projection | `132` | `40` | source/diff/AST/import/trace·quality gates · `0` (basedpyright는 외부 stub 진단만) | `.omo/evidence/marslab-runtime-refactor-v2/task-18/` 및 `adversarial-verify/final.md` | PENDING USER; G4 미승인 |
| 20 | G4 | LOW/Luna (`lazycodex-worker-low`) | `marslab/sensors/imu_spawner.py` 신규, `marslab/sensors/sensor_spawner.py` coordinator 축소 | typed `IMUConfig`·deferred Isaac 5.1 `IMUSensor`; Camera/3D/IMU 단일 위임; 2D surface 제거 | `196` | `587` | live numstat·source/AST/import/fake-trace·quality gates · `0` (basedpyright/pytest는 분류된 비녹색) | `.omo/evidence/marslab-runtime-refactor-v2/task-20/` 및 `adversarial-verify/final.md` | PENDING USER; G4 미승인 |
| 21 | G4 | MEDIUM/Terra (heavy; `lazycodex-worker-medium`) | `marslab/ros2_bridge/sensor_graph.py`, `sensor_graph_builder.py`, `marslab/runtime/assembly.py`, `marslab/sensors/sensor_spawner.py` | ROS-on retained Camera RGB/depth/depth-PCL/CameraInfo, IMU, 3-D LiDAR graph; existing acquisition identity/path reuse; 2-D branch deferred to Task22 | `59` | `193` | fake PIN→RED→GREEN graph/assembly probes, deferred import, compile/Ruff/Black/diff checks · `0`; basedpyright external stubs 분류 | `.omo/evidence/marslab-runtime-refactor-v2/task-21/` 및 `adversarial-verify/AdversarialVerify.md` | PENDING USER; G4 미승인 |
| 22 | G4 | MEDIUM/Terra (heavy; `lazycodex-worker-medium`) | `marslab/ros2_bridge/sensor_graph.py`, `sensor_graph_builder.py` | 2-D LiDAR ROS API/switch/node/edge/scan-value surface atomically removed; Task21 retained six publishers and acquisition identities preserved; canonical raw ROS strict-schema subset filter present; Task22-only `+/-` delta is not independently recoverable from the shared worktree | `—` | `—` | process-local fake public invocation, residue/preimage scan, Python 3.11 compile, Ruff/Black/diff checks · `0`; basedpyright external stubs 분류 | `.omo/evidence/marslab-runtime-refactor-v2/task-22/report/DoneClaim.md`, `adversarial-verify/AdversarialVerify.md` | PENDING USER; G4 미승인 |

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
| G3 | `APPROVE G3` | 2026-08-19 14:01:03 KST (+09:00) | canonical full ROS Isaac command sustained normally, no automatic shutdown | `f23986e4fc7c76d50eb205cbe1866338595c0bb5` — `refactor(runtime): coordinate retained assembly` | **Task16 (G4) unlocked** |
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

## Task 11 — typed Isaac boot boundary

- **라우팅:** **LOW/Luna** (`lazycodex-worker-low`). 제품 변경은
  `marslab/sim/boot.py` 한 파일뿐이다. `boot_simulation_app()`는 typed
  `RuntimeConfig`를 받아 `runtime.headless`를 `SimulationApp` 설정에
  소비하고, `runtime.ros2_enabled`일 때만 지연 import한
  `isaacsim.ros2.bridge`를 정확히 한 번 enable한다. Isaac import는 호출
  시점까지 지연되며, 첫 `update()` 뒤 동일한 live handle을 반환한다.
  Scene/Rover/sensor/world assembly, lifecycle, RunPlan은 추가하지 않았다.
- **제품 delta:** `marslab/sim/boot.py`의 live diff는 **`+26/-29`**, net
  **`-3`** (29 pure LOC)이다. 제품 LOC이며 report/evidence LOC는 제외한다.
  직전 누적 **`+330/-174`**에서 **`+356/-203`**이 됐다.
- **검증:** inline fake-module QA의 exact observable은
  `{'pure_import_did_not_load_isaacsim': True, 'headless': [True, False], 'renderer': ['RaytracedLighting', 'RaytracedLighting'], 'bridge_calls': ['isaacsim.ros2.bridge'], 'updates': [1, 1], 'identity': [True, True]}`이다. 따라서 ROS-off는 bridge call 0회, ROS-on은 1회, 각 handle은
  1회 update되고 반환 identity가 보존된다. 오프라인 import/AST deferred-
  import·RuntimeConfig/read/update 정적 확인, Python 3.11 compileall,
  Ruff, Black, mypy, `git diff --check`가 모두 PASS했다.
- **범위 제한:** 실제 Isaac boot/physics는 **G3 사용자 소유**이며 여기서
  성공을 주장하지 않는다. 현재 `main.py`의 구 호출은 의도적으로 남겨 두고
  **Task 15에서 prepare→boot rewiring**한다. ULTRAQA는
  `dirty_worktree`, `stale_state`, `misleading_success_output` PASS이며,
  malformed input·concurrency/auth/network/ports/process lifetime은 이
  순수 boot boundary에 해당하지 않아 N/A다. `prompt_injection`은 untrusted
  instruction ingestion이 없고, `cancel_resume`은 resumable flow가 없으며,
  `hung_or_long_commands`는 bounded command만, `flaky_tests`는 tests를
  실행·변경하지 않았고, `repeated_interruptions`는 interrupt/retry 동작이
  없어 각각 N/A다.

## Task 12 — pre-reset assembly 추출

- **작업 난이도/모델:** **MEDIUM / Terra** (`lazycodex-worker-medium`).
- **재설계 및 범위:** 초기 reverse-dependency 검증은
  `PreResetDependencies`/project-callback injection을 발견해 **REJECT**됐다.
  사용자 승인으로 해당 주입과 250 pure-LOC 절대 gate를 제거하고,
  `marslab/runtime/assembly.py`가 concrete MarsLab 호출과 지연 Isaac import를
  직접 소유하도록 수리해 최종 verifier **confirmed/APPROVE**를 받았다. 최종
  소스에는 `marslab.main` 참조가 0건이다.
- **내부 상수 경계:** public `terrain_prim_path`, `cli_z_offset`,
  `parent_anchor_prim_path` 인자를 제거하고 `/World/Terrain`, legacy `0.0`
  z-fallback, `/World/odom_anchor`를 assembly 내부가 소유한다. `tf_nameoverrides`
  참조도 없으며, stale caller/import 제거는 **Task 15**에서 수행한다.
- **보존한 동작:** Scene → atmosphere/render 또는 fallback → 세 spawn 모드
  (`dem_center`, `dem_relative`, `absolute`) → Rover → 필수 Camera·IMU·3D LiDAR
  → ROS-조건부 graph → DriveAPI → `Articulation(prim_paths_expr=...)` → 단일
  `world.reset` 순서와 unsupported-mode 오류를 유지했다. 2D LiDAR 토큰/전달은 없다.
- **정리/LOC:** 최종 live delta는 **`+350/-0` physical lines, 294 pure LOC**이며
  누적은 **`+356/-203` → `+706/-203`**이다(report/evidence LOC 제외).
  294 pure LOC는 cohesive한 단일 pre-reset 책임으로 검토됐고, 길이는 warning이지
  pass/fail gate가 아니다. `_sample_dem_elevation`의 redundant guard는 제거됐다.
  `main.py`의 임시 중복은 Task 15에서 제거한다.
- **검증/인계:** 실제 `python3 -c` fake-consumer가 세 XYZ 모드, ROS on/off,
  fallback, Articulation identity/순서, 단일 reset, no-2D를 관찰했고 AST/offline
  import/compile/Ruff/Black/mypy/diff checks가 PASS했다(`task-12/internal-constants/DoneClaim.md`,
  `internal-constants/adversarial-verify/AdversarialVerify.md`). 실제 Isaac/Kit 실행은
  **G3 사용자 소유**다.

## Task 13 — post-reset initialization 추출

- **라우팅/승인:** **MEDIUM / Terra** (`lazycodex-worker-medium`). 사용자 승인으로
  `PostResetDependencies`·project callback 주입과 absolute 250-pure-LOC gate를 제거하고
  `post_reset.py` sibling split을 적용했다. `assembly.py`는 pre-reset 전용이며 길이는
  cohesive 책임에 대한 warning일 뿐 pass/fail gate가 아니다.
- **구현 경계:** concrete MarsLab calls를 모듈이 소유하고 Isaac/rclpy-only imports는
  deferred한다. 최종 소스에는 `PostResetDependencies`/project callback/`marslab.main`
  참조가 없으며, **Task13 당시** `assemble_post_reset` public API는 typed
  config/handles/results를 담은 정확히 여덟 keyword-only 입력 (`world`,
  `simulation_app`, `pre_reset`, `rover`, `atmosphere_init`, `headless`,
  `atmosphere_enabled`, `ros2_enabled`)을 받고 loop용 articulation·index·atmosphere·
  optional panel/bridge results만 반환했다. `wheel_odom_publish_tf` 입력은
  Task15 최종 rclpy 회귀 수리에서 추가됐다.
- **제품 LOC/누적:** Task delta는 **`+219/-0` physical lines, 188 pure LOC**이며 제품
  누적은 **`+706/-203` → `+925/-203`**이다. report/evidence LOC는 제품 수치에서 제외한다.
  `main.py`의 legacy post-reset block은 **Task 15 rewiring** 전까지 임시 중복으로 남는다.
- **보존한 순서/QA:** articulation initialize/root pin/DOF copy/drive-steer resolve·zero·initial
  positions → rendered **10**회 →
  stopped timeline play 시에만 **5**회 추가 → PD/atmosphere → eligible panel과 app update
  **5**회 → odom → ROS frames/seeds/wheel/noise/bridge 순서를 유지했다. A/B/C/D fake QA가
  ROS-off, stopped/running, seed child 0/1·seed-none, zero/nonzero noise, panel-constructor
  failure와 정확한 **10/5/5** 및 continuation을 PASS했다.
- **경계/검증:** no 2D-LiDAR, reset, loop, cleanup, publisher internals, lifecycle manager를
  추가하지 않았다. offline import·compileall·Ruff·Black·isolated mypy·AST/order/count/
  boundary scan·`git diff --check`가 PASS했고 full mypy의 기존 sibling diagnostics 3건 외
  `post_reset.py` 진단은 없다. 실제 Isaac/Kit/ROS 실행은 주장하지 않으며 **G3 사용자 소유**다.
- **ULTRAQA/cleanup:** dirty-worktree attribution, live hash rebinding/stale-state,
  misleading-success, generated-cache cleanup은 PASS; malformed typed config, prompt injection,
  auth/network/ports, concurrency, cancel/resume, hung/long, flaky/retry, repeated interruption,
  archive/symlink traversal은 이 동기 오프라인 seam에 surface가 없어 N/A이며 잔여 process/port/
  temp script/cache는 없다.

## Task 14 — concrete lifecycle cleanup boundary

- **라우팅/범위:** **MEDIUM / Terra**. 새 `marslab/runtime/lifecycle.py`만 추가했다.
  초기 검증에서 graph/sensor/annotator/render-product/panel/timeline/world cleanup은
  기존 concrete API가 없어 **REJECT**됐고, 사용자 승인으로 speculative callbacks와
  관련 기획/코드를 제거했다. 추측한 Isaac cleanup은 남기지 않았다.
- **동작:** `run_phase()`는 정확히 `return run_main_loop(ctx)`다. 정리 순서는
  `bridge.node.destroy_node()` → `rclpy.shutdown()` → `simulation_app.close()`이며,
  ordinary getter/invocation failures는 기록한 뒤 후속 정리를 계속한다. primary
  runtime error 또는 nonzero status가 권위이고 cleanup-only failure는 status `1`이다.
  `BaseException`은 삼키지 않고 전파한다.
- **LOC/경계:** 제품 delta는 **`+127/-0`, pure LOC 93**, 누적은
  **`+925/-203` → `+1052/-203`**이다(report/evidence 제외). `main.py`의 임시 중복은
  **Task 15 rewiring**에서 제거한다.
- **검증:** concrete fake QA와 최종 독립 verifier(`confirmed`)가 순서, getter/호출
  실패 연속성, primary/status authority, stale callback 제거를 확인했다. AST/import/
  compile/Ruff/Black/scoped mypy/diff/size/cache checks도 PASS이며 full mypy의 기존
  sibling diagnostics 3건 제한은 유지된다.
- **ULTRAQA/인계:** malformed/missing/getter/invocation/multiple failures, stale/dirty/
  misleading/repeated interruption은 PASS; prompt injection, cancel/resume, hung/long,
  flaky tests는 N/A다. 실제 Isaac/Kit cleanup과 Task 15 wiring은 **사용자 G3** 소유다.

## Task 15 — typed main/loop orchestration, rclpy 회귀 및 runtime observability repair

- **라우팅/소유:** **MEDIUM / Terra**. call-only `main.py`/`loop_context.py` wiring을
  유지하면서 최종 수리는 `main.py`, `runtime/post_reset.py`,
  `ros2_bridge/rclpy_integration.py`, `runtime/lifecycle.py`, `runtime/main_loop.py`에
  한정했다. Task13/14가 이미 계상한 `post_reset.py`/`lifecycle.py` 초기 추가분은
  Task15에서 중복 계산하지 않는다.
- **rclpy 회귀 원인/수리:** commit `8e25e38`이 canonical `Ros2BridgeConfig`에서
  `rename_root_to_base_link`와 `publish_odom_tf`를 제거했지만 `init_rclpy_side`가
  두 stale read를 남겨 `AttributeError`를 냈다(RED:
  `.omo/evidence/marslab-runtime-refactor-v2/task-15/rclpy-stale-config-fix/red-schema-access.txt`).
  최종 chain은 `main.py → assemble_post_reset → init_rclpy_side`이며 정책은
  root rename **false**, GT `publish_tf` **false**, `wheel_odom.publish_tf`만 전달이다.
- **관측성 수리:** `main.py`는 setup 예외를 traceback과 함께 기록·재전파하고,
  `lifecycle.py`는 run/각 cleanup 예외를 기록하며 status 권위를 보존한다.
  `main_loop.py`는 첫 step 전 정지/zero-iteration을 명시적으로 보고한다.
  로그의 `rosidl_generator_py`/`lark`는 known caught DEBUG일 뿐이며 dependency/shim을
  추가하거나 실패로 분류하지 않는다. 과거 자동종료 기록은 stale history로 남기고
  최종 사용자 관찰과 혼동하지 않는다.
- **현재 파일 LOC/numstat:** 아래 `+/-`는 tracked 파일의 현재
  `git diff --numstat`이며, untracked 파일은 동일한 `git diff --no-index --numstat
  /dev/null <file>`로 확인했다. physical line은 `wc -l` 결과다.

| 파일 | 심볼/책임 | 현재 diff `+LOC/-LOC` · Task15 incremental | 현재 physical LOC |
|---|---|---:|---:|
| `marslab/main.py` | typed entrypoint, setup error/status wiring | `+91/-697` | `116` |
| `marslab/runtime/loop_context.py` | concrete callback context | `+76/-124` | `112` |
| `marslab/runtime/post_reset.py` | `wheel_odom_publish_tf` typed forwarding (Task13 초기 `+219` 이후 수리 `+2/-0`) | `+221/-0` · **`+2/-0`** | `221` |
| `marslab/ros2_bridge/rclpy_integration.py` | stale field 제거, root/GT false, wheel TF 전달 | `+3/-17` | `257` |
| `marslab/runtime/lifecycle.py` | run/cleanup traceback/status observability (Task14 초기 `+127` 이후 수리 `+14/-0`) | `+141/-0` · **`+14/-0`** | `141` |
| `marslab/runtime/main_loop.py` | zero-iteration/first-step observability | `+13/-4` | `786` |
| **Task15 최종 합계** | 위 수리 포함, 기존 Task15 wiring 포함 | **`+199/-842`** | — |

단계별 additive churn 기준 누적은 기존 Task14 `+1052/-203`에 Task15
`+199/-842`를 더한 **`+1251/-1045` (net `+206`)**이다. 이는 one-shot
baseline `e6a1c580` → current worktree product diff **`+1250/-1044`
(net `+206`)**와 구별한다(단계 간 한 줄 교체가 add/delete churn에 중복 반영됨).
G3 Tasks11–15 subtotal은 **`+921/-871` (net `+50`)**이며, 모든 수치는
report/evidence LOC를 제외한다.
- **사용자 runtime 관찰(사용자 소유):** 공식 canonical command
  `marslab/isaac_python.sh marslab/main.py --config configs/config.yaml` 실행은
  자동 종료 없이 정상 지속됐다. 보존된 `/home/hoyunkim/MarsLab/log.txt`는 678 lines;
  `rclpy loaded` line 507, `Atmosphere control panel created` line 659,
  known caught `lark` DEBUG lines 660–668이며 setup/run/zero-iteration/`AttributeError`/
  shutdown marker가 없다. 이는 사용자가 본 real Isaac surface이며 agent가 Isaac을
  실행했다는 주장이 아니다.
- **에이전트 정적/경계 검증:** canonical RED/green fake-rclpy, Python 3.11 compile,
  Ruff, Black, isolated mypy, stale-read scan, lifecycle/main-loop fake failure matrix가
  PASS/confirmed다. 사용자 log read-only marker/hash 검사는
  `.omo/evidence/marslab-runtime-refactor-v2/task-15/user-runtime-final/adversarial-verify/inspection-transcript.md`,
  최종 verdict는
  `.omo/evidence/marslab-runtime-refactor-v2/task-15/user-runtime-final/adversarial-verify/final.md`에 있다.
- **cleanup/UltraQA:** probe·lark shim·split logs·temporary caches는 제거했고 user
  `log.txt`는 보존했다(영수증: `.omo/evidence/marslab-runtime-refactor-v2/task-15/ros-split-isolation/final-cleanup-receipt.md`).
  stale_state/dirty_worktree/misleading_success_output는 적용 PASS; malformed,
  prompt-injection, cancel/resume, hung/long, flaky/retry, repeated-interruption은
  이 보고서/정적 seam에 surface가 없어 N/A다. G3 승인 토큰은 정확히 **`APPROVE G3`**로
  기록했으며 다음 작업은 **Task16 (G4)**다.

## G3 승인 — Tasks 11–15 lifecycle/main loop

- **승인 원문:** 사용자 입력 `Approve G3`.
- **정규화 토큰:** **`APPROVE G3`**.
- **승인 시각:** `2026-08-19 14:01:03 KST (+09:00)` (Asia/Seoul; this turn).
- **사용자 관찰:** **canonical full ROS Isaac command sustained normally, no automatic shutdown**.
- **검토된 implementation commit:**
  **`f23986e4fc7c76d50eb205cbe1866338595c0bb5`** —
  `refactor(runtime): coordinate retained assembly`.
- **다음 unlock:** **Task16 (G4) unlocked**.

## Task 16 — 센서 schema parent link 제거의 현재 상태 충족 (no-op)

- **라우팅/소유:** **LOW/Luna** (`lazycodex-worker-low`). 이 기록은 Task16
  보고서와 evidence만 소유하며 product·plan·ledger는 수정하지 않았다.
- **no-op 판정:** Task16의 acceptance state는 기존 commit
  `8e25e38e4937ce4cdc1a3a8fb7b591448bad0168` (`refactor(config): add canonical
  runtime configuration`)에 이미 들어 있었다. 따라서 이번 작업은 삭제를
  새로 수행한 것이 아니라 현재 source/evidence를 재검증했으며 product delta는
  **`+0/-0`**이다.
- **현재 계약:** `CameraConfig`, `Lidar3DConfig`, `IMUConfig`는
  `local_translation`/`local_orientation_rpy_deg`를 유지하고 `parent_link`가
  없다. `SensorsConfig`와 canonical `configs/config.yaml`의 sensor keys는
  Camera·IMU·3D LiDAR·seed이며 canonical config에는 `parent_link`와
  `lidar_2d`가 없다. strict Pydantic injection은 `parent_link`를
  `extra_forbidden`으로 거부한다. Sensor spawner는 발견된
  chassis rigid body인 단일 `rigid_body_path: str`를 parent로 사용하고 retained
  sensor의 local transform을 유지한다.
- **잔여 분류:** 필수 전체 scan의 `sensor_spawner.py` 38 matches는 Task17이
  소유한 legacy 2D/scan 경로다. schema와 canonical config의 owned-file scan은
  exit `1`/empty output이며, 이 Task16 기록에서 해당 spawner 삭제를 주장하지
  않는다.

### Task 16 검증 및 수동 QA

| 시나리오 | invocation / binary observable | artifact |
|---|---|---|
| canonical loader와 retained field inventory | `python3` production `load_config('configs/config.yaml')` + four model field assertions · exit `0`, `FORBIDDEN_SCHEMA_FIELDS_ABSENT PASS` | `.omo/evidence/marslab-runtime-refactor-v2/task-16/canonical-loader.txt` |
| strict forbidden-input rejection | `CameraConfig.model_validate`에 `parent_link` 주입 · exit `0`, `MALFORMED_FORBIDDEN_FIELD_REJECTED PASS`, `extra_forbidden` at `('parent_link',)` | `.omo/evidence/marslab-runtime-refactor-v2/task-16/forbidden-input.txt` |
| residue classification | required `rg` scan · exit `0` with only out-of-scope spawner matches; owned-only scan · exit `1`/empty | `.omo/evidence/marslab-runtime-refactor-v2/task-16/residue-scan.txt` |
| sole chassis parent and retained transforms | direct source-contract probe · exit `0`, `SPAWNER_PARENT_CONTRACT PASS` | `.omo/evidence/marslab-runtime-refactor-v2/task-16/spawner-contract.txt` |
| touched-source quality | `py_compile`, Ruff, basedpyright, `git diff --check` · each exit `0` | `.omo/evidence/marslab-runtime-refactor-v2/task-16/quality-checks.txt` |

- **독립 확인:** `.omo/evidence/marslab-runtime-refactor-v2/task-16/adversarial-verify/final.md`
  의 direct loader/model/source probe가 exit `0`과
  `TASK16_ADVERSARIAL_VERIFY PASS`를 기록하고 verdict를 `confirmed`로
  고정했다. reviewed commit은 `c3d2cdff21de63a27c4b07aeff7064a590d5a0e0`이며,
  현재 reviewed source hash와 clean owned-path status도 같은 artifact에 있다.
- **ULTRAQA:** `malformed_input`, `dirty_worktree`, `stale_state`,
  `misleading_success_output`는 PASS. `prompt_injection`, `cancel_resume`,
  `hung_or_long_commands`, `flaky_tests`, `repeated_interruptions`는 이
  bounded offline/report surface에 해당 이벤트가 없어 N/A다. 기존 legacy
  pytest collection API ImportError는 `test-harness-note.txt`에 기록했으며
  no-op 범위를 넘어 수정하지 않았다.
- **수동 QA / gate:** `sed -n '/^## Task 16/,$p' MARSLAB_REFACTORING_CHANGE_REPORT.md`
  로 이 항목을 terminal-render해 exact criteria, **`+0/-0`**, LOW/Luna,
  evidence, no-new-deletion wording, 다음 **Task17**을 확인한다. **G4는
  여전히 PENDING USER**이며 `APPROVE G4` 또는 runtime PASS를 추론하지 않는다.

## Task 17 — legacy 2D LiDAR profile anchoring 제거 및 3D 경로 보존

- **라우팅/소유:** **LOW / Luna** (`lazycodex-worker-low`). 변경된 product
  파일은 `marslab/config/yaml_loader.py` 하나이며, report/evidence 외의
  unrelated worktree 변경은 건드리지 않았다.
- **정확한 product delta:** 현재 `git diff --numstat --
  marslab/config/yaml_loader.py marslab/config configs/config.yaml`는
  `5 6 marslab/config/yaml_loader.py`로 **`+5/-6` (net `-1` LOC)**이다.
  기존 `load_rover_config`의 `("lidar_3d", "lidar_2d")` 순회에서 retired
  `lidar_2d` profile anchoring만 제거했고, 지원되는
  `lidar_3d.profile_json_path`는 declaring YAML 기준 anchoring을 유지했다.
  schema export와 `configs/config.yaml`에는 product delta가 없다.
- **계약/잔여:** 현재 `rg -n -i 'lidar_2d|lidar2d|scan' marslab/config
  configs/config.yaml`는 exit `1`/빈 출력으로 owned config/schema residue가
  0이다. strict `MarsLabConfig.model_validate`는 주입된
  `rover.sensors.lidar_2d`와 `rover.ros2.topics.scan`을 각각 정확한 위치에서
  `extra_forbidden`으로 거부한다. 계획의 `profile_path` 표기는 오기이며
  production field는 `profile_json_path`다. 호환 alias는 추가하지 않았다.

### Task 17 검증 및 수동 QA

| 시나리오 | invocation / binary observable | artifact |
|---|---|---|
| legacy 2D traversal RED/green | in-memory mapping을 production `load_rover_config`에 전달 · preimage는 2D/3D 모두 anchor, 현재는 2D 값 `profiles/lidar2d.json` 유지·3D는 absolute | `.omo/evidence/marslab-runtime-refactor-v2/task-17/red_2d_traversal.txt`, `.omo/evidence/marslab-runtime-refactor-v2/task-17/post_traversal_scope.txt` |
| retained 3D path | relative `lidar_3d.profile_json_path`를 선언 YAML 기준으로 로드 · `absolute=True`, `exists=True`, expected file | `.omo/evidence/marslab-runtime-refactor-v2/task-17/post_3d_anchor.txt` |
| canonical load / corrected manual QA | `marslab/isaac_python.sh` Python 3.11 `load_config('configs/config.yaml')` · exit `0`, `None OS1`; corrected `profile_json_path` probe `True OS1` | `.omo/evidence/marslab-runtime-refactor-v2/task-17/baseline_canonical_load.txt`, `.omo/evidence/marslab-runtime-refactor-v2/task-17/manual_qa_corrected.txt` |
| strict retired-input rejection | `MarsLabConfig.model_validate` with injected 2D/scan keys · both rejected at `rover.sensors.lidar_2d` and `rover.ros2.topics.scan` | `.omo/evidence/marslab-runtime-refactor-v2/task-17/malformed_input_rejection.txt` |
| residue/export/static gates | required `rg` scan exit `1`/empty; imports, Python 3.11 compile, Ruff, Black, mypy, `git diff --check` exit `0` | `.omo/evidence/marslab-runtime-refactor-v2/task-17/residue_post.txt`, `.omo/evidence/marslab-runtime-refactor-v2/task-17/schema_export_import.txt`, `.omo/evidence/marslab-runtime-refactor-v2/task-17/py_compile.result`, `.omo/evidence/marslab-runtime-refactor-v2/task-17/ruff.result`, `.omo/evidence/marslab-runtime-refactor-v2/task-17/black.result`, `.omo/evidence/marslab-runtime-refactor-v2/task-17/mypy.result`, `.omo/evidence/marslab-runtime-refactor-v2/task-17/diff_check.result` |

- **독립 확인:** `.omo/evidence/marslab-runtime-refactor-v2/task-17/adversarial-verify/final.md`
  는 direct source/loader/schema probe를 재실행해 **`confirmed` / APPROVE**로
  판정했다. 같은 확인에서 authoritative numstat `+5/-6`, current residue 0,
  strict rejection, 3D anchoring 보존을 고정했다. 독립 code review도
  `CLEAR`/`APPROVE`이며 blocker가 없다.
- **증거 정정:** executor DoneClaim의 `+5/-5`/net-zero 표기는 실제
  `git diff --numstat`와 불일치한다. 이 보고서는 authoritative **`+5/-6`**만
  기록한다. task snippet의 `profile_path` 실패는 production schema에 없는
  이름 때문이며, 실제 `profile_json_path` corrected probe는 PASS다.
- **ULTRAQA/cleanup:** stale state, dirty scope, misleading success output은
  적용 PASS(오류 표기는 위와 같이 명시); malformed input과 generated/cache
  cleanup도 PASS다. prompt injection, cancel/resume, flaky, hung/long,
  repeated interruption, network/auth/server lifecycle은 이 결정적 offline
  loader task에 surface가 없어 N/A다. cleanup receipt는
  `.omo/evidence/marslab-runtime-refactor-v2/task-17/cleanup_receipt.txt`다.
- **수동 QA / gate:** `sed -n '/^## Task 17/,$p' MARSLAB_REFACTORING_CHANGE_REPORT.md`
  로 terminal render해 exact criteria, **`+5/-6`**, LOW/Luna, evidence,
  typo/alias 및 stale·dirty·misleading 적용 결과를 확인한다(PASS). **G4는
  여전히 PENDING USER**이며 다음 작업은 **Task18**이다.

## Task 18 — Camera spawner 추출 및 ROS-independent acquisition 경계

- **라우팅/소유:** **LOW/Luna** (`lazycodex-worker-low`). 새
  `marslab/sensors/camera_spawner.py`가 typed `CameraConfig` 경계로 Camera
  생성을 소유하고, `marslab/sensors/sensor_spawner.py`는 한 번 위임한 뒤
  기존 `camera`와 `camera_prim_path`만 `SensorHandles`에 투영한다. IMU,
  LiDAR, ROS, config, graph 및 enable/disabled 분기는 이 Task18 범위에서
  수정하지 않았다.
- **정확한 product delta:** live authoritative numstat은 신규 파일에
  `git diff --no-index --numstat /dev/null marslab/sensors/camera_spawner.py`
  를 적용해 `+124/-0` (명령의 no-index 차이 exit `1`은 신규 파일 신호)로
  확인했고, tracked coordinator는 `git diff --numstat --
  marslab/sensors/sensor_spawner.py`의 `+8/-40`이다. 따라서 Task18 합계는
  **`+132/-40` (net `+92`)**이며 report/evidence LOC는 제외한다.
- **Camera 계약:** 기존 constructor → `initialize()` → focal-length →
  clipping 순서를 zero-orientation trace와 직접 비교해 보존했다. 비영(非零)
  orientation은 기존 parent-Xform 패턴을 유지한다. 새 경계는 Camera prim
  정확히 하나, ROS와 독립된 acquisition render product 정확히 하나를 만들고
  같은 render product에 `rgb`와 `distance_to_image_plane` annotator를 각각
  한 번 attach한다. 반환 `CameraSpawnHandles`는 frozen/slotted typed handle로
  고정되며 기존 경로 필드는 그대로 소비된다.
- **경계/잔여 위험:** Isaac/Omni/pxr import는 `spawn_camera()` 호출 시점으로
  지연되어 offline import가 가능하다. 새 모듈 AST에는 IMU/LiDAR/ROS/enable
  로직이 없다. 기존 ROS OmniGraph의 `RPCamera` render-product 노드는 같은
  Camera prim에 대한 별도 pipeline으로 남아 있으며, RP 통합은 **Task22의
  bounded risk**이지 Task18 실패가 아니다.
- **LOC/정적 품질:** `camera_spawner.py`는 **95 pure LOC / 124 physical
  LOC**다. Ruff, Black, Python 3.11 `py_compile`, AST 및 `git diff --check`는
  PASS했다. basedpyright의 진단은 offline 환경에서 제공되지 않는
  Isaac/Omni/pxr import·stub에 한정되며 새 public handle API에 `Any`를
  추가하지 않았다.

### Task 18 검증 및 수동 QA

| 시나리오 | invocation / binary observable | artifact |
|---|---|---|
| legacy Camera 의미/순서 pin | fake Isaac trace에서 constructor, `initialize`, focal, clipping prefix가 기존과 동일 · oriented branch도 parent Xform 유지 | `.omo/evidence/marslab-runtime-refactor-v2/task-18/PIN-RED.md`, `post-camera-only.log`, `trace-compare.log`, `adversarial-verify/final.md` |
| 단일 Camera/RP와 annotator 공유 | dynamic count `Camera=1`, `render_product=1`, `rgb.attach=1`, `distance_to_image_plane.attach=1`; 두 attach가 동일 RP | `.omo/evidence/marslab-runtime-refactor-v2/task-18/post-camera-only.log`, `post-trace.log`, `trace-compare.log` |
| typed/frozen handle와 coordinator projection | `CameraConfig.model_validate`, 단일 `spawn_camera(stage, camera_cfg, rigid_body_path)` 호출, mutation은 `FrozenInstanceError` · 기존 path fields 유지 | `.omo/evidence/marslab-runtime-refactor-v2/task-18/ast-scan.log`, `adversarial-verify/final.md` |
| offline import/deferred runtime imports | `env PYTHONDONTWRITEBYTECODE=1 marslab/isaac_python.sh -c 'import marslab.sensors.camera_spawner as m; print(m.__all__)'` · exit `0`, `['CameraSpawnHandles', 'spawn_camera']`; Isaac/Omni/pxr modules 미로드 | `.omo/evidence/marslab-runtime-refactor-v2/task-18/manual-import.log`, `adversarial-verify/final.md` |
| source/tool gates | AST, Ruff, Black, Python 3.11 `py_compile`, `git diff --check` · 각 exit `0`; basedpyright는 외부 runtime stub 진단으로 분류 | `.omo/evidence/marslab-runtime-refactor-v2/task-18/ast-scan.log`, `ruff.log`, `black.log`, `py_compile.log`, `diff-check.log`, `basedpyright.log` |

- **독립 확인:** `.omo/evidence/marslab-runtime-refactor-v2/task-18/adversarial-verify/final.md`
  는 `APPROVE — AdversarialVerify PASS`/`confirmed`로 고정했으며, exact
  criteria C1–C10과 `95 pure / 124 physical LOC`를 재확인했다. 실제 GPU/Isaac
  생성은 실행하지 않았고 사용자 runtime QA로 추론하지 않는다.
- **ULTRAQA/cleanup:** stale/dirty/misleading/generated 상태 검토를 적용했다.
  compile/import 중 생긴 변경 모듈 bytecode는 임시 경로에서 정리했고, 저장소
  cache·test·script·YAML·source, SimulationApp/process/port는 추가·기동하지
  않았다. 별도 runtime/auth/network/cancel/hung surface는 이 offline
  extraction 검증 범위가 아니므로 결과를 발명하지 않는다.
- **수동 QA / gate:**
  `sed -n '/^## Task 18/,$p' MARSLAB_REFACTORING_CHANGE_REPORT.md`로 이
  항목을 terminal-render하고 `git diff --check --
  MARSLAB_REFACTORING_CHANGE_REPORT.md marslab/sensors/sensor_spawner.py`
  를 재실행해 PASS를 확인한다. **G4는 여전히 PENDING USER**이며 다음 unlock은
  **Task19**다.

## Task 19 — typed RTX 3D LiDAR spawner 추출 및 ROS-independent point-cloud 경계

- **라우팅/소유:** **LOW/Luna** (`lazycodex-worker-low`). 새
  `marslab/sensors/lidar_3d_spawner.py`가 typed `Lidar3DConfig` 경계에서 RTX
  3D LiDAR 생성·초기화·point-cloud acquisition을 소유하고,
  `marslab/sensors/sensor_spawner.py`는 한 번 위임한 뒤 coordinator가 읽기
  handle을 투영한다. Camera, IMU, 2D LiDAR, ROS graph, schema, YAML,
  enable/experimental 경계는 이 Task19에서 확장하지 않았다.
- **정확한 authoritative product delta:** live untracked-aware numstat은 새
  파일 `git diff --no-index --numstat /dev/null
  marslab/sensors/lidar_3d_spawner.py`의 **`192 0`** (no-index exit `1`은
  신규 파일 차이의 정상 신호)과 tracked coordinator
  `git diff --numstat -- marslab/sensors/sensor_spawner.py`의
  **`18 74`**를 기록했다. 따라서 Task19 합계는 **`+210/-74` (net +136)**다.
  새 모듈은 **192 physical / 148 pure LOC**이며 report/evidence와 unrelated
  dirty paths는 product delta에서 제외했다.
- **보존된 Isaac 계약:** `LidarRtx` profile name/JSON path는
  `config_file_name`으로 그대로 전달되고, float32 translation 및 non-zero
  orientation, optional USD profile/variant, near/far/rate/FOV/elevation
  overrides, prim resolution → override → `initialize()` 순서를 보존한다.
  runtime에는 LiDAR sensor 하나, render-product handle 하나, point-cloud
  annotator 하나만 연결하며 spawn 시 eager `get_data()`/copy를 수행하지 않고
  `read_point_cloud()` 호출 때만 읽는다.
- **coordinator/오프라인 경계:** `SensorHandles.read_lidar_3d_point_cloud()`는
  새 acquisition handle을 사용하고 수동으로 만든 legacy handle에는 기존
  fallback을 유지한다. `omni`/`isaacsim`/`pxr` import는 호출 내부로 지연되어
  Python 3.11 wrapper offline import가 가능하며 public API는
  `['Lidar3DSpawnHandles', 'spawn_lidar_3d']`다. 새 모듈에는 Camera/IMU/2D
  LiDAR/ROS/experimental/enable branch가 없다.

### Task 19 검증 및 수동 QA

| 시나리오 | invocation / binary observable | artifact |
|---|---|---|
| live product numstat (untracked 포함) | `git diff --numstat -- marslab/sensors/sensor_spawner.py` → `18 74`; `git diff --no-index --numstat /dev/null marslab/sensors/lidar_3d_spawner.py` → `192 0`, expected exit `1`; derived `+210/-74` | `.omo/evidence/marslab-runtime-refactor-v2/task-19/report/live-numstat.log` |
| profile/transform/override/order 보존 | fake Isaac trace에서 supplied profile name/JSON, float32 translation·WXYZ orientation, USD profile/variant, six override writes, `initialize` order가 확인됨 | `.omo/evidence/marslab-runtime-refactor-v2/task-19/profile-overrides-trace.log`, `post-fake-trace.log`, `adversarial-verify/final.md` |
| 단일 runtime sensor/RP/annotator 및 on-demand read | counts가 constructor/initialize/render-product/annotator/read 각각 `1`; read 전 eager `get_data()` `0`, 명시적 read 후 `1`, point-cloud shape `(1, 3)` | `.omo/evidence/marslab-runtime-refactor-v2/task-19/counts.log`, `post-fake-trace.log`, `adversarial-verify/final.md` |
| typed coordinator compatibility | `Lidar3DConfig.model_validate`와 단일 `spawn_lidar_3d(...)` call, coordinator read binary assertion 및 legacy fallback 확인 | `.omo/evidence/marslab-runtime-refactor-v2/task-19/post-coordinator-fake-trace.log`, `adversarial-verify/final.md` |
| offline deferred import / forbidden scope | `env PYTHONDONTWRITEBYTECODE=1 marslab/isaac_python.sh -c 'import marslab.sensors.lidar_3d_spawner as m; print(m.__all__)'` → exit `0`, exact API; AST/text scan에서 eager Isaac import·Camera/IMU/2D/ROS/experimental/enable 없음 | `.omo/evidence/marslab-runtime-refactor-v2/task-19/manual-import.log`, `ast-scan.log`, `adversarial-verify/final.md` |
| source/tool gates | Python 3.11 `py_compile`, Ruff, Black, `git diff --check` 모두 PASS; basedpyright는 외부 Isaac SDK/stub 및 pre-existing coordinator 진단으로 분류 | `.omo/evidence/marslab-runtime-refactor-v2/task-19/py_compile.log`, `ruff.log`, `black.log`, `diff-check.log`, `basedpyright.log` |
| malformed profile boundary | invalid typed profile configuration이 Pydantic 경계에서 거부됨 | `.omo/evidence/marslab-runtime-refactor-v2/task-19/malformed-config.log` |

- **독립 확인:** `.omo/evidence/marslab-runtime-refactor-v2/task-19/adversarial-verify/final.md`는
  `APPROVE`/`confirmed`로 고정되었고, profile·transform·override 순서,
  정확히 한 개의 sensor/RP/annotator, on-demand read, coordinator projection,
  offline import, 금지 범위를 독립 source/AST/import/fake-runtime probe로
  재실행했다. 새 source의 pure LOC는 148로 250 LOC 상한 아래다.
- **검증 한계/분류:** `tests/refactor`는 이미 제거된
  `marslab.config.load_rover_config`를 가져오는 out-of-scope 테스트 때문에
  collection 단계에서 중단되며 Task19가 tests/fixture를 추가하거나 이 API를
  복원하지 않았다. basedpyright의 missing Isaac runtime import/stub 진단과
  legacy coordinator diagnostics도 pre-existing/external로 분류한다. 실제
  GPU/SimulationApp/Isaac runtime은 실행하지 않았고 사용자 G4 표면으로 남긴다.
- **ULTRAQA/cleanup:** stale state, dirty-worktree attribution,
  misleading-success output, generated bytecode/cache cleanup을 적용해 PASS했다.
  이 bounded offline extraction에는 prompt injection, auth/network/ports,
  cancel/resume, hung/long, flaky/retry, repeated interruption surface가 없어
  결과를 발명하지 않고 N/A로 분류했다. 임시 bytecode와 probe process는
  정리했으며 SimulationApp/Isaac process는 시작하지 않았다
  (`cleanup.log`).
- **수동 QA / gate:** `sed -n '/^## Task 19/,$p'
  MARSLAB_REFACTORING_CHANGE_REPORT.md`의 terminal render와 report/source
  `git diff --check`가 PASS인지 확인했다. **G4는 여전히 PENDING USER**이고,
  Task20 IMU 추출이 다음 작업이다. `APPROVE G4` 또는 사용자 Isaac runtime
  PASS를 추론하지 않는다.

## Task 20 — IMU spawner 추출 및 sensor coordinator 축소

- **라우팅/소유:** **LOW/Luna** (`lazycodex-worker-low`). 새
  `marslab/sensors/imu_spawner.py`가 typed `IMUConfig` 경계에서 Isaac Sim 5.1
  `isaacsim.sensors.physics.IMUSensor` 생성·초기화를 소유하고,
  `marslab/sensors/sensor_spawner.py`는 Camera·3D LiDAR·IMU를 각각 한 번씩
  위임하는 좁은 coordinator로 축소했다. 이 report-only 기록은 product source를
  추가로 수정하지 않았다.
- **정확한 authoritative product delta:** live untracked-aware numstat은 새
  `imu_spawner.py`의 `git diff --no-index --numstat /dev/null ...`에서
  **`+137/-0`** (no-index exit `1`은 신규 파일 차이의 정상 신호), tracked
  coordinator에서 **`+59/-587`**이다. 따라서 Task20 합계는 **`+196/-587`
  (net `-391`)**이다. 새 모듈은 **137 physical / 109 pure LOC**,
  coordinator는 **117 physical / 99 pure LOC**이며 report/evidence와 unrelated
  dirty paths는 product delta에서 제외했다.
- **보존된 IMU 계약:** `IMUConfig`를 typed 입력으로 받고 Isaac import는
  `spawn_imu()` 호출 내부로 지연한다. 기존 Mars gravity assertion(3.72 ± 0.05),
  parent-Xform orientation 및 local translation, frequency의 `int(...)` 변환,
  정확히 한 번의 `IMUSensor` constructor와 `initialize()` 호출을 보존한다.
  `SensorHandles.read_imu()`의 on-demand read, 동일 prim path,
  `use_latest_data=True`/`read_gravity=True`, 여섯 acceleration/angular-velocity
  필드와 read-time gravity warning도 유지된다.
- **coordinator surface:** 모든 retained sensor는 enable/disabled 분기 없이
  Camera·3D LiDAR·IMU spawner를 한 번씩 호출한다. coordinator와 새 IMU 모듈에서
  2D LiDAR constants/handles/prim·profile creation/branches/helpers를 제거했고,
  experimental/deprecated/duplicate/eager/ROS sensor creation surface는 없다.
  `imu.py` 신규 deprecated module도 만들지 않았다.

### Task 20 검증 및 수동 QA

| 시나리오 | invocation / binary observable | artifact |
|---|---|---|
| live product numstat (untracked 포함) | `git diff --numstat -- marslab/sensors/sensor_spawner.py` → `59 587`; `git diff --no-index --numstat /dev/null marslab/sensors/imu_spawner.py` → `137 0`, expected exit `1`; derived `+196/-587` | `.omo/evidence/marslab-runtime-refactor-v2/task-20/report/live-numstat.log` |
| source/evidence availability 및 LOC | `wc -l`/nonblank count → IMU `137/109`, coordinator `117/99`; authoritative implementation/adversarial logs non-empty | `.omo/evidence/marslab-runtime-refactor-v2/task-20/report/source-evidence-check.log` |
| typed/deferred IMU API와 금지 surface | AST/signature scan → `__all__ == ['IMUSpawnHandles', 'spawn_imu']`, one constructor/initialize, no module-scope Isaac import, coordinator delegates Camera/3D/IMU once, zero 2D/experimental/enable | `.omo/evidence/marslab-runtime-refactor-v2/task-20/ast-api-scan.log` |
| IMU behavior boundary | fake Isaac orientation/config trace → parent Xform ordering, configured translation/orientation, float32 zero translation, frequency `30.9 → 30`, one constructor/initialize; malformed/unknown `IMUConfig` rejected | `.omo/evidence/marslab-runtime-refactor-v2/task-20/orientation-and-config.log`, `fake-trace.log` |
| offline import | `env PYTHONDONTWRITEBYTECODE=1 marslab/isaac_python.sh -c 'import marslab.sensors.imu_spawner as m; print(m.__all__)'` → exit `0`, Isaac/Omni/pxr/rclpy not loaded | `.omo/evidence/marslab-runtime-refactor-v2/task-20/manual-import.log` |
| quality gates | Python compile, Ruff, Black, `git diff --check` → exit `0`; basedpyright exit `1` only for external Isaac/pxr stubs and existing coordinator diagnostics; pytest exit `2` at out-of-scope legacy collection import | `.omo/evidence/marslab-runtime-refactor-v2/task-20/py_compile.log`, `ruff.log`, `black.log`, `diff-check.log`, `basedpyright.log`, `pytest-refactor.log` |
| independent implementation verdict | adversarial recheck directly compared live source/hashes and fake probes; verdict `confirmed` with all Task20 criteria satisfied | `.omo/evidence/marslab-runtime-refactor-v2/task-20/adversarial-verify/final.md` |

- **독립 확인:** `adversarial-verify/final.md`는 live hash, AST/text, Python 3.11
  offline import, typed boundary, fake Isaac/coordinator/read trace, gravity source
  semantics, LOC/numstat, quality gates를 재실행해 **`confirmed`**로 고정했다.
  이는 실제 GPU/SimulationApp/ROS runtime 실행이나 사용자 표면 PASS를 의미하지
  않는다.
- **진단 분류:** basedpyright의 exit 1은 CPU-only 환경의 외부 Isaac/Omni/pxr
  import·attribute/stub 진단과 기존 coordinator typing 경고로 분류했다.
  `pytest-refactor.log`의 exit 2는 이미 제거된
  `marslab.config.load_rover_config`를 가져오는 out-of-scope legacy test의
  collection 실패이며 Task20 source/test를 추가하거나 API를 복원하지 않았다.
- **ULTRAQA/cleanup:** `malformed_input`, `stale_state`, `dirty_worktree`,
  `misleading_success_output`, `generated_artifacts`는 PASS다. prompt injection,
  cancel/resume, hung/long, flaky, repeated interruption은 이 bounded
  offline/report surface에 이벤트가 없어 N/A로 분류했다. 임시 probe·bytecode·
  venv를 정리했고 Isaac/ROS process·port·SimulationApp은 시작하지 않았다
  (`cleanup.log`).
- **수동 QA / gate:** `sed -n '/^## Task 20/,$p'
  MARSLAB_REFACTORING_CHANGE_REPORT.md`로 이 항목을 terminal-render하고
  report/source `git diff --check`를 재실행했다. **G4는 여전히 PENDING USER**이며
  다음 작업은 **Task21**이다. `APPROVE G4` 또는 사용자 Isaac runtime PASS를
  추론하지 않는다.

## Task 21 — retained ROS sensor graph와 acquisition identity 연결

- **라우팅/소유:** **MEDIUM / Terra (heavy)** (`lazycodex-worker-medium`). 보고서와
  report evidence만 갱신했으며 product source 및 기존 Task21 evidence는 수정하지
  않았다. 초기 call-graph RED에서 `spawn_sensors()`가 Task18 Camera와 Task20
  IMU acquisition handle을 버려 assembly가 graph에 identity를 전달할 수 없음을
  확인했다. 사용자 승인 최소 범위 확장으로 `SensorHandles`에
  `camera_acquisition`, `lidar_3d_acquisition`, `imu_acquisition`을 보존하고,
  ROS-on assembly가 이 세 객체를 그대로 한 번 전달하도록 연결했다.
- **정확한 Task21 delta:** clean-at-start에서 검토한 hunk 기준으로
  `sensor_graph.py +22/-40`, `sensor_graph_builder.py +27/-145`,
  `assembly.py +3/-4`, coordinator projection `sensor_spawner.py +7/-4`이다.
  합계는 **`+59/-193` (net `-134`)**이며, Task20과 공유하는 coordinator의
  전체 dirty `numstat`를 Task21 delta로 재사용하지 않았다.
- **Graph 계약:** ROS graph가 만들어질 때 Camera RGB, depth, depth PointCloud2,
  CameraInfo, IMU, 3-D LiDAR publisher를 enable flag 없이 유지한다. Camera의
  네 publisher는 Camera spawner가 이미 만든 **동일한 render-product path**를
  받고, LiDAR helper는 기존 LiDAR acquisition의 path를, IMU publisher는 기존
  IMU acquisition의 prim identity를 사용한다. retained Camera/LiDAR render
  product 재생성은 없다. ROS disabled assembly는 graph-builder 호출 **0회**,
  enabled assembly는 **1회**이며 세 acquisition 객체 identity가 모두 보존된다.
- **2-D 경계 및 LOC:** `RPLidar2D` temporary branch만 Task22까지 남긴다. 현재
  pure LOC는 `sensor_graph.py=235`, `sensor_graph_builder.py=265`,
  `sensor_spawner.py=103`, `assembly.py=293`이며, 모듈 250 pure-LOC 수치는
  이 Task에서 절대 gate로 적용하지 않는 사용자 승인 정책을 따른다.

### Task 21 검증 및 수동 QA

| 시나리오 | invocation / binary observable | artifact |
|---|---|---|
| retained graph PIN→RED→GREEN | process-local fake `build_sensor_graph`에서 필수 노드·endpoint를 검증; CamInfo 제거 RED는 `exit 1`, GREEN은 missing/unresolved 모두 빈 집합 | `.omo/evidence/marslab-runtime-refactor-v2/task-21/DoneClaim.md`, `adversarial-verify/AdversarialVerify.md` |
| path/identity와 ROS gate | fake `assemble_pre_reset`를 `ros2_enabled=False/True`로 각각 호출; graph build `0/1`, Camera/LiDAR/IMU identity `True` | `.omo/evidence/marslab-runtime-refactor-v2/task-21/adversarial-verify/AdversarialVerify.md` |
| retained publisher surface | source/fake payload에서 `CamRGB`, `CamDepth`, `CamPCL`, `CamInfo`, `PubIMU`, `Lidar3DHelper` 존재; retained `IsaacCreateRenderProduct` 0, 임시 `RPLidar2D`만 보존 | `.omo/evidence/marslab-runtime-refactor-v2/task-21/DoneClaim.md` |
| offline/static gates | deferred import exit `0`; Python 3.11 compile, Ruff, Black, `git diff --check` exit `0`; basedpyright exit `1`은 외부 Isaac/Omni/pxr/usdrt stub 진단으로 분류 | `.omo/evidence/marslab-runtime-refactor-v2/task-21/DoneClaim.md`, `adversarial-verify/AdversarialVerify.md` |
| reviewed arithmetic/source binding | clean-start hunk arithmetic `22+27+3+7=59`, `40+145+4+4=193`, net `-134`; source/evidence non-empty 및 report render/diff-check 확인 | `.omo/evidence/marslab-runtime-refactor-v2/task-21/report/DoneClaim.md`, `live-numstat.log`, `manual-render.log`, `diff-check.log` |

- **독립 확인:** `.omo/evidence/marslab-runtime-refactor-v2/task-21/adversarial-verify/AdversarialVerify.md`는
  `verdict: confirmed`, `recommendation: APPROVE`, blockers 없음으로 고정했고,
  malformed endpoint RED, public builder GREEN, Task22 임시 2-D branch, assembly
  identity/gate, deferred import 및 정적 검사를 직접 재실행했다.
- **진단·실행 한계:** basedpyright의 비녹색은 `omni.graph.core`,
  `isaacsim.core.utils.prims`, `usdrt`, `isaacsim.sensors.physics`,
  `omni.isaac.sensor` 외부 runtime stub 부재다. 실제 Isaac Sim/ROS/OmniGraph
  runtime은 시작하지 않았으므로 사용자 G4 표면 PASS를 추론하지 않는다.
- **ULTRAQA/cleanup:** malformed/stale topology, dirty scope,
  misleading-success, generated cache cleanup은 PASS로 기록되어 있다. 이
  bounded offline/report 검증에는 prompt injection, cancel/resume, hung/long,
  flaky, repeated interruption surface가 없어 N/A다. 기존 unrelated dirty path는
  보존했고, Task21 report 검증은 product process·port·임시 파일을 만들지 않았다.
- **수동 QA / gate:** `sed -n '/^## Task 21/,$p'
  MARSLAB_REFACTORING_CHANGE_REPORT.md`로 terminal render와 exact
  **`+59/-193` (net `-134`)**, MEDIUM/Terra heavy, path/identity/gate,
  adversarial verdict를 확인한다. **G4는 여전히 PENDING USER**이며 다음은
  **Task22**다. `APPROVE G4` 또는 사용자 Isaac runtime PASS를 추론하지 않는다.

## Task 22 — 2-D LiDAR ROS graph surface 원자적 제거

- **라우팅/소유:** **MEDIUM / Terra (heavy)** (`lazycodex-worker-medium`). 이번
  Task의 product 범위는 `marslab/ros2_bridge/sensor_graph.py`와
  `marslab/ros2_bridge/sensor_graph_builder.py` 두 파일뿐이다. Task21이 보존한
  Camera RGB/depth/depth-PCL/CameraInfo, IMU, 3-D LiDAR의 여섯 publisher와
  acquisition product/identity/endpoint를 그대로 유지하고, graph 내부에서
  render product를 새로 만들지 않는다.
- **원자적 삭제:** public `lidar_2d_prim_path` 인자와 `include_2d` 선택,
  builder의 `include_lidar_2d` switch/인자, `RPLidar2D`·`Lidar2DHelper` node,
  tick/exec/render-product edges, camera prim·`/rover/scan`·`scan_frame`·
  `laser_scan`·sensor QoS·reset 값이 두 graph 파일에서 함께 사라졌다. 현재
  두 파일의 2-D residue 검색은 빈 출력이며, retained camera 네 helper는 동일한
  caller render-product path, 3-D helper는 기존 3-D path, IMU는 기존 prim identity를
  받는다. `IsaacCreateRenderProduct` 재생성은 없다.
- **canonical raw ROS 경계:** canonical YAML의 legacy free-form `topics`/`rates`
  키를 strict `Ros2BridgeConfig` subset으로 먼저 필터링하는 경계가 현재 source에
  존재한다. 이 경계 필터 덕분에 raw `configs/rover_m2020.yaml` public invocation이
  graph edit까지 도달하며, 2-D dispatch나 compatibility shim은 남기지 않는다.
- **LOC 보고 한계:** 현재 두 owned graph 파일은 `wc -l` 기준 **620 physical LOC**
  (`sensor_graph.py=299`, `sensor_graph_builder.py=321`)이다. HEAD 대비 현재
  shared-worktree scoped diff는 **`+71/-236` (net `-165`)**이나 이는 Task21과
  Task22의 누적 변경을 함께 포함하므로 Task22 단독 delta로 귀속하지 않는다.
  Task22 전용 pre-edit snapshot/patch가 durable하게 남아 있지 않아 Task22-only
  `+/-` 또는 net LOC를 권위 수치로 제시하지 않는다.

### Task 22 검증 및 수동 QA

| 시나리오 | invocation / binary observable | artifact |
|---|---|---|
| canonical raw ROS public build | process-local fake `omni.graph.core.Controller`/`usdrt`로 `configs/rover_m2020.yaml`의 raw `ros2` block을 public `build_sensor_graph`에 전달; retained six, endpoint, product identity를 assert | `.omo/evidence/marslab-runtime-refactor-v2/task-22/adversarial-verify/AdversarialVerify.md` (`manual-qa=PASS`, `unresolved=[]`) |
| atomic 2-D removal | `rg -n 'lidar_2d|lidar2d|Lidar2D|scan|RPLidar2D' marslab/ros2_bridge/sensor_graph.py marslab/ros2_bridge/sensor_graph_builder.py` | 빈 출력·exit `1`; 같은 artifact의 preimage RED/GREEN 기록 |
| retained topology / no RP recreation | fake payload reconciliation; camera products 4개가 동일 path, 3-D path/IMU identity 보존, `IsaacCreateRenderProduct` 생성 0 | `.omo/evidence/marslab-runtime-refactor-v2/task-22/adversarial-verify/AdversarialVerify.md` |
| offline/static quality | `python3.11 -m py_compile`·`black --check`·`ruff check`·`git diff --check` | 모두 exit `0`; basedpyright exit `1`은 `omni.graph.core`, `isaacsim.core.utils.prims`, `usdrt` 외부 import 진단으로 분류 |
| source/evidence accounting | current owned-file `wc -l` `620`; HEAD→current scoped cumulative diff `+71/-236` (Task21+22 combined, not Task22-only); report tail render and whitespace diff check | `.omo/evidence/marslab-runtime-refactor-v2/task-22/report/DoneClaim.md` |

- **독립 확인:** `.omo/evidence/marslab-runtime-refactor-v2/task-22/adversarial-verify/AdversarialVerify.md`는
  current source와 `git show HEAD:<owned-file>` preimage를 직접 대조해
  **CONFIRMED** verdict, retained endpoints/products/identities, malformed detector,
  residue scan, deferred import 및 정적 gate를 재실행했다. 실제 Isaac Sim/ROS/Kit
  runtime은 실행하지 않았고, 따라서 사용자 G4 surface PASS를 추론하지 않는다.
- **ULTRAQA/cleanup:** stale state, dirty worktree, malformed topology,
  misleading-success, generated artifacts/cleanup은 adversarial review에서 PASS다.
  `.venv`는 정확한 경로에 대해 `gio trash`로 recoverable move 되었고 원 inode와
  source path metadata는 `.omo/evidence/marslab-runtime-refactor-v2/task-22/cleanup-venv-receipt.md`와
  `cleanup-venv-independent-verification.md`에 고정되어 있다. 원 경로 부재,
  Trash inode 존재, status hash 보존, process prefix scan `none`을 재확인했다.
  임시 fake module/script/process/port는 남기지 않았다.
- **수동 QA / gate:**
  `sed -n '/^## Task 22/,$p' MARSLAB_REFACTORING_CHANGE_REPORT.md`와
  `git diff --check -- MARSLAB_REFACTORING_CHANGE_REPORT.md`를 재실행한다.
  **G4는 여전히 PENDING USER**이며 다음 작업은 **Task23**이다. `APPROVE G4`나
  실제 Isaac runtime PASS를 추론하지 않는다.

## Task 23 — 2-D TF 및 legacy base-link 우회 경로 제거

- **라우팅/소유:** **MEDIUM / Terra (heavy)** (`lazycodex-worker-medium`). Task23은
  `sensor_frames.py`, `tf_broadcaster.py`, `sensor_graph.py`,
  `sensor_graph_builder.py`, `runtime/assembly.py`, 관련 schema/YAML, rclpy/URDF
  경계, `launch/rover_state_publisher.launch.py`, `docs/frame_conventions.md`를
  함께 정리하고 `marslab/ros2_bridge/tf_nameoverrides.py`를 삭제했다. 현재
  report는 Task23 전용 pre-edit snapshot이 없으므로 Task23-only `+/-` LOC를
  발명하지 않는다.
- **최종 TF 계약:** 2-D `scan_frame`/`lidar_2d` frame map과
  `apply_nameoverride`, `create_odom_anchor`, `DEFAULT_ODOM_ANCHOR_PATH`,
  `isaac:nameOverride`, `/World/odom_anchor`, `/tf_raw`,
  `rename_root_to_base_link`, `enable_isaac_nameoverride`,
  `parent_anchor_prim_path` 및 관련 active documentation을 제거했다. 현재
  retained frame map은 `camera_link`, `lidar_link`, `imu_link` 세 개이며 모두
  `Body_Chassis` 아래에 있다. `base_link`와 실제 USD/URDF root `Body_Chassis`는
  유지되고, companion launch에는 all-zero identity `base_link → Body_Chassis`
  static connector가 정확히 하나, `robot_state_publisher`가 정확히 하나 남는다.
- **문서/경계 정합:** `docs/frame_conventions.md`와 센서 TF docstring은
  identity REP-103 `Body_Chassis` 계약으로 정정했다. 단, `docs/`는
  `.gitignore:55`에 의해 무시되므로 G4 stage commit에서
  `docs/frame_conventions.md`를 force-stage해야 한다. 실제 Isaac/ROS TF tree는
  실행하지 않았고 **PENDING USER (G5)**다.
- **재현 가능한 LOC/검사:** 현재 report에서 Task23 전용 LOC를 산출하지 않는다.
  broad Task23 static scope의 basedpyright는 **50 errors / 861 warnings**로
  비녹색이며, unavailable Isaac/Omni/ROS/usdrt imports와 inherited local generic
  annotation debt가 함께 있다. narrow graph core check의 3 missing-import
  진단도 green gate로 취급하지 않는다. Python compile, Ruff, Black,
  `git diff --check`, frame-map/launch topology probe는 PASS다.

### Task 23 검증 및 수동 QA

| 시나리오 | invocation / binary observable | artifact |
|---|---|---|
| stale report PIN/RED | `rg -n '^## Task 23|^\\| 23 \\|' MARSLAB_REFACTORING_CHANGE_REPORT.md` before edit | empty output; expected RED captured in report-update DoneClaim |
| frame-map and connector contract | process-local Python probe injects a `lidar_2d` block, parses launch AST, and counts identity connector | `frame-map has no scan/lidar_2d: True`; `base_link->Body_Chassis identity count == 1`; `legacy token scan == 0`; exit `0` — `.omo/evidence/marslab-runtime-refactor-v2/task-23/manual-qa.txt`, `post-fix-manual-qa.txt` |
| forbidden residue | exact-token `rg` across active `marslab`, `configs`, `launch`, `docs`, `tests`, `.github`, `pyproject.toml` | no active matches; `tf_nameoverrides.py` absent — `.omo/evidence/marslab-runtime-refactor-v2/task-23/adversarial-verify/AdversarialVerify.md` |
| static quality | in-memory Python compile, `ruff check`, `black --check`, `git diff --check` | exit `0`; basedpyright remains explicitly non-green as classified above — `.omo/evidence/marslab-runtime-refactor-v2/task-23/` |
| independent gate | read-only post-fix adversarial source/preimage/topology audit | verdict **`confirmed`**, no Task23 blocker — `.omo/evidence/marslab-runtime-refactor-v2/task-23/adversarial-verify/AdversarialVerify.md` |

- **ULTRAQA/cleanup:** stale state, dirty worktree, malformed input, misleading
  success, and generated-artifact cleanup were directly probed and recorded.
  Prompt injection, cancel/resume, hung/long, flaky, and repeated interruption
  surfaces are N/A for this bounded deterministic offline/report task. Temporary
  pre-edit scan, generated bytecode, process, port, fixture, and temp directory
  cleanup is recorded in `.omo/evidence/marslab-runtime-refactor-v2/task-23/cleanup-receipt.txt`.
- **수동 QA / gate:**
  `rg -n 'Task 23|base_link|Body_Chassis|tf_nameoverrides|PENDING USER' MARSLAB_REFACTORING_CHANGE_REPORT.md`
  must exit `0` and show this entry, the retained identity contract, deleted helper,
  and pending G5 runtime. **G4는 여전히 PENDING USER**이며 Task23의 실제 TF tree
  관찰이나 `APPROVE G4`를 추론하지 않는다.
