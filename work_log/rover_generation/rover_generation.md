# Rover Generation Work Log

---

## [2026-04-16] Phase 1 Stage 1: Perseverance Rover Spawn + ROS2 Round-Trip

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/, configs/, tests/unit/
**Type:** Feature + Bug Fix (iterative)

### Original Plan (주차별 개요)

Phase 1 Stage 1 목표: 평면 위에 Perseverance 로버를 URDF→USD 변환 후 스폰하고,
Isaac Sim ROS2 브리지를 통해 센서 토픽 퍼블리시 + cmd_vel 수신을 구현한다.
Earth gravity (9.81) 하에서 검증 후 Mars gravity (3.72) 전환은 Stage 2로 미룬다.

### Implementation Plan (세부 계획)

1. **오프라인 URDF→USD 컨버터** (`scripts/phase1/convert_urdf_to_usd.py`)
   - NASA JPL m2020 URDF 위생처리 (DBL_MAX 제한값, floating 관절, ground 링크 제거)
   - Isaac Sim `URDFParseAndImportFile` 호출 + import_config 설정
   - 출력 USD 무결성 검증 (wrapper + base USD 크기 검사)
   - `kit.close()` heap corruption 회피 → `os._exit(0)`

2. **Stage 1 런타임** (`scripts/phase1/run_stage1.py`)
   - Pure helper 레이어 (Isaac Sim 없이 import 가능): `load_config`, `clamp`, `clamp_twist`, `skid_steer_targets`, `resolve_joint_indices`, `rpy_to_quat`
   - Isaac Sim lazy import inside `main()`
   - Ground plane + physics context (gravity, solver) 설정
   - USD reference 로딩 + xform (translate + orient)
   - 센서 부착 (Camera, LiDAR, IMU)
   - OmniGraph ROS2 파이프라인 (Clock, Odom, TF, IMU, RGB, Depth, LiDAR)
   - rclpy cmd_vel subscriber → 6-wheel skid-steer joint velocity 매핑

3. **설정 파일** (`configs/phase1.yaml`)
   - G5 준수: 모든 물리/로봇/센서/제어 파라미터 YAML 관리
   - physics, rover, ros2, sensors, control 5개 섹션

4. **단위 테스트** (`tests/unit/test_run_stage1_helpers.py`)
   - 23개 테스트: clamp(4), clamp_twist(1), skid_steer(6), resolve_joint_indices(3), load_config(6), rpy_to_quat(3)

### What Was Done

#### 컨버터 (`convert_urdf_to_usd.py`)
- NASA JPL m2020 URDF 위생처리기 구현:
  - 102개 DBL_MAX 토큰 → 안전한 값으로 치환
  - `JointRoot` (floating) 제거, `ground` 링크 제거
  - `Joint_MHS_DebrisShield` floating → fixed 변환
  - Root link 유일성 검증
- Import config 최적화 (3차 반복):
  - 초기: 기본값 → 로버 무한 낙하 (mass=0, collision=0)
  - 수정: `merge_fixed_joints=True`, `collision_from_visuals=True`, `density=500.0`, `import_inertia_tensor=False`
  - 결과: 69개 고정 관절 병합, 21MB base USD 생성 성공

#### 런타임 (`run_stage1.py`) — 5차 반복 수정
- **v1**: 기본 구현 (spawn + sensors + OmniGraph + cmd_vel)
- **v2** (Bug Fix — 무한 낙하): 컨버터 import_config 수정으로 해결
- **v3** (Bug Fix — 상하 반전):
  - 스폰 높이 z=1.0 → z=3.0 (지면 관통 방지)
  - `rpy_to_quat` 헬퍼 추가 + orient op 적용
  - IMU 부모를 RigidBodyAPI 프림으로 자동 탐색
  - ComputeOdom 프림을 ArticulationRootAPI 프림으로 변경
- **v4** (Bug Fix — GfQuatd/GfQuatf 타입 불일치): `Gf.Quatd` → `Gf.Quatf`
- **v5** (Bug Fix — 여전히 거꾸로):
  - USD geometry가 반전 상태로 베이크됨 확인 (glTF Y-up → USD Z-up 변환 문제)
  - `spawn_orientation_rpy: [3.14159, 0.0, 0.0]` (180° X-roll)로 해결
  - ComputeOdom: `Usd.PrimRange`로 ArticulationRootAPI 프림 동적 탐색
- **v6** (튜닝 — 스폰 높이 + 무게중심 + 댐핑):
  - `spawn_position` z: 3.0 → 0.8 → 0.0 (사용자 조정)
  - `com_offset: [0.4, 0.0, 0.0]` → `[0.2, 0.0, 0.0]` (CoM 전방 보정, 사용자 조정)
  - `angular_damping: 5.0` → `12.0` (차체 회전 진동 감쇠, 사용자 조정)
  - `suspension_damping: 50.0` → `85.0` (서스펜션 관절 댐핑, 사용자 조정)
  - `physxRigidBody:angularDamping` → `Sdf.CreateAttribute` 패턴 (속성 미존재 시 생성)
  - `UsdPhysics.DriveAPI.Apply` + `CreateAttribute`로 서스펜션 관절 댐핑 적용

#### YAML 설정 (`configs/phase1.yaml`) 최종 상태
- `spawn_position: [0.0, 0.0, 0.0]`
- `spawn_orientation_rpy: [3.14159, 0.0, 0.0]`
- `com_offset: [0.2, 0.0, 0.0]`
- `angular_damping: 12.0`
- `suspension_damping: 85.0`
- 5개 drive joints, 4개 steer joints, 5개 suspension joints 명시

### Key Decisions

| 결정 | 근거 |
|------|------|
| 오프라인 1회 USD 변환, 런타임 URDF import 금지 | Isaac Sim URDF importer가 비결정적 + 느림. USD는 asset으로 관리 |
| `merge_fixed_joints=True` | 83개 Frame_* 고정 관절 제거 → physics 안정성 향상 |
| `collision_from_visuals=True` + `density=500.0` | NASA URDF에 collision/mass 정보 없음. visual mesh 기반 자동 생성 |
| `import_inertia_tensor=False` | URDF 관성 텐서 전부 0 → 임포터 자동 계산이 더 안정적 |
| 180° X-roll spawn orientation | USD geometry가 glTF Y-up 변환으로 상하 반전 상태 베이크 |
| CoM 런타임 오버라이드 | density 균일 적용으로 인한 무게중심 편향 보정. YAML 튜닝 가능 |
| 서스펜션 댐핑 + angular damping | 착지 후 rocker-bogie 자유 진동 억제 |
| `Sdf.CreateAttribute` 패턴 | PhysX 확장 속성이 USD에 없을 때 `GetAttribute`는 실패. `CreateAttribute`로 타입 지정 생성 필요 |
| Pure helper + lazy Isaac import | 단위 테스트를 GPU/Isaac Sim 없이 실행 가능하게 분리 |

### USD Prim Hierarchy (최종)

```
/World/Rover (Xform, reference root)
  /World/Rover/Body_Chassis (Xform, variantSets)
    /World/Rover/Body_Chassis/Body_Chassis (Xform, ArticulationRootAPI + RigidBodyAPI)
    /World/Rover/Body_Chassis/Body_Differential (RigidBody)
    /World/Rover/Body_Chassis/Body_WheelLeft* (RigidBody) ×3
    /World/Rover/Body_Chassis/Body_WheelRight* (RigidBody) ×3
    /World/Rover/Body_Chassis/Body_RockerLeft/Right (RigidBody)
    /World/Rover/Body_Chassis/Body_BogieLeft/Right (RigidBody)
    /World/Rover/Body_Chassis/Body_RSM_*, Body_HGA_*, Body_RA_* (RigidBody)
    /World/Rover/Body_Chassis/joints/ (PhysicsRevoluteJoint prims)
    /World/Rover/Body_Chassis/stage1_camera (Camera)
    /World/Rover/Body_Chassis/stage1_lidar (LidarRtx)
    /World/Rover/Body_Chassis/Body_Chassis/stage1_imu (IMUSensor)
```

### Bug Fix Timeline

| # | 증상 | 원인 | 해결 | 런타임 로그 |
|---|------|------|------|-------------|
| 1 | 무한 낙하 | mass=0, collision=0, 83 unmerged fixed joints | converter import_config 수정 | temp_run.txt → temp_convert.txt |
| 2 | 상하 반전 + 지면 관통 | spawn z=1.0 < geometry 최저점 z=-2.36 | z=3.0 + orient op + IMU/Odom prim 수정 | temp_run2.txt |
| 3 | GfQuatd/GfQuatf 타입 불일치 | USD xformOp이 float 정밀도 | `Gf.Quatd` → `Gf.Quatf` | temp_run3.txt |
| 4 | 여전히 거꾸로 | USD geometry 자체가 반전 베이크 | `spawn_orientation_rpy: [π, 0, 0]` | temp_run4.txt |
| 5 | 앞뒤 흔들림 | 서스펜션 damping=0, angular damping 없음 | joint damping + rigid body angular damping | temp_run5.txt |
| 6 | physxRigidBody 속성 미존재 | `GetAttribute` 실패 | `Sdf.CreateAttribute` 패턴 | temp_run5.txt (재실행) |

### Files Created/Modified

| 파일 | 상태 | 설명 |
|------|------|------|
| `scripts/phase1/convert_urdf_to_usd.py` | 신규 | URDF→USD 오프라인 컨버터 |
| `scripts/phase1/run_stage1.py` | 신규 | Stage 1 런타임 (spawn + ROS2) |
| `scripts/isaac_python.sh` | 신규 | Isaac Sim Python 래퍼 스크립트 |
| `configs/phase1.yaml` | 신규 | Stage 1 전체 설정 |
| `tests/unit/test_run_stage1_helpers.py` | 신규 | Pure helper 단위 테스트 (23개) |
| `assets/robots/rover/m2020.usd` | 생성됨 | 컨버터 출력 (wrapper USD) |
| `assets/robots/rover/configuration/m2020_base.usd` | 생성됨 | 컨버터 출력 (21MB mesh data) |

### Test Results

- Unit tests: **23 passed**, 0 failed (black, ruff, pytest 전체 통과)
- Integration (사용자 실행): 로버 정상 스폰, 센서 부착, OmniGraph 빌드, cmd_vel 구독 확인
- 시각 검증: 로버 정위 (바퀴 아래, 마스트 위), 진동 감쇠 확인

### Tuning Parameters (사용자 최종 조정값)

| 파라미터 | 초기값 | 최종값 | 비고 |
|---------|--------|--------|------|
| `spawn_position` z | 1.0 | 0.0 | 최소 낙하 거리 |
| `com_offset` x | 0.4 | 0.2 | 전방 CoM 보정 |
| `angular_damping` | 5.0 | 12.0 | 차체 회전 감쇠 |
| `suspension_damping` | 50.0 | 85.0 | 서스펜션 진동 감쇠 |

### Blockers / Issues

- `ComputeOdom` 여전히 `/World/Rover` 를 거부 (L493 temp_run4.txt). ArticulationRootAPI가 `/World/Rover/Body_Chassis/Body_Chassis`에 있어 동적 탐색으로 해결했으나, 향후 odom 데이터 정확성 검증 필요.
- IMU frequency > physics frequency 경고 (100Hz IMU vs 60Hz physics). Stage 2에서 정리.
- `kit.close()` heap corruption으로 `os._exit(0)` 사용 중. Isaac Sim 5.x 알려진 이슈.

### Next Steps

- ~~Stage 1 ROS2 라운드트립 검증~~ → 아래 Stage 1.5 참조
- Mars gravity (3.72) 전환 → IMU z축 검증 (3.72 ± 0.05 m/s²)
- Scenario 1 (Basic Mars): DEM 지형 + 암석 배치 위에 로버 스폰

---

## [2026-04-16] Phase 1 Stage 1.5: ROS2 라운드트립 검증 + Drive Joint 수정

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/, configs/
**Type:** Bug Fix

### Original Plan (주차별 개요)

Stage 1 스폰 완료 후 ROS2 전체 라운드트립 검증:
센서 토픽 발행 확인 + teleop cmd_vel → 로버 물리 이동 확인.

### Implementation Plan (세부 계획)

1. 터미널 A에서 `run_stage1.py` 실행, 터미널 B에서 시스템 ROS2로 토픽 검증
2. `ros2 topic list` → 8개 토픽 존재 확인
3. `ros2 topic echo` → IMU, odom, camera, lidar 데이터 수신 확인
4. `teleop_twist_keyboard` → cmd_vel 전송 → 로버 이동 확인
5. odom position 변화 확인

### What Was Done

#### ROS2 토픽 검증 결과

| 항목 | 결과 | 비고 |
|------|------|------|
| `/rover/cmd_vel` 토픽 존재 | PASS | |
| `/rover/odom` 토픽 존재 + 데이터 수신 | PASS | |
| `/rover/imu` 토픽 존재 + 데이터 수신 | PASS | 60Hz+ |
| `/rover/rgb/image_raw` 토픽 + 데이터 수신 | PASS | |
| `/rover/depth/image_raw` 토픽 + 데이터 수신 | PASS | |
| `/rover/lidar/points` 토픽 + 데이터 수신 | PASS | |
| `/tf` 토픽 존재 | PASS | |
| cmd_vel → 로버 물리 이동 | **FAIL** | 아래 참조 |

#### Bug Fix — Drive Joint DriveAPI 누락

**증상**: teleop_twist_keyboard → `/rover/cmd_vel` 전송 → rqt에서 sub/pub 파이프라인 확인됨 → 로버 바퀴 안 움직임

**근본 원인**: 6개 drive joints (LF_DRIVE 등)에 `UsdPhysics.DriveAPI`가 설정되지 않음. `articulation.set_joint_velocity_targets()` 호출은 성공하지만, PhysX 엔진이 토크를 가하려면 DriveAPI + damping이 필수. DriveAPI 없는 관절은 velocity target을 무시.

**해결**: suspension joints에서 이미 적용한 동일 패턴을 drive joints에도 적용:
- `configs/phase1.yaml`: `drive_damping: 1000.0` 추가 (velocity-mode: stiffness=0, damping=1000.0)
- `scripts/phase1/run_stage1.py`: steer lock 직후, suspension 블록 직전에 drive joints DriveAPI 설정 코드 삽입

```python
# Velocity control mode:
# stiffness = 0 → no position tracking
# damping > 0 → torque = damping * (target_vel - current_vel)
UsdPhysics.DriveAPI.Apply(joint_prim, "angular")
joint_prim.CreateAttribute("drive:angular:physics:damping", ...).Set(drive_damping)
joint_prim.CreateAttribute("drive:angular:physics:stiffness", ...).Set(0.0)
```

### Key Decisions

| 결정 | 근거 |
|------|------|
| `drive_damping: 1000.0` 초기값 | 차체 ~500kg, 바퀴 구동에 충분한 토크 필요. suspension_damping(85.0)은 진동 억제용이라 낮지만 drive는 10배+ |
| velocity mode (stiffness=0) | cmd_vel은 속도 명령. 위치 추종(stiffness>0)은 불필요 |
| YAML 파라미터화 | G5 준수: 사용자가 시뮬레이션 중 튜닝 가능 |

### Files Modified

| 파일 | 변경 | 설명 |
|------|------|------|
| `configs/phase1.yaml` | 수정 | `drive_damping: 1000.0` 추가 |
| `scripts/phase1/run_stage1.py` | 수정 | drive joints DriveAPI 설정 블록 삽입 (L491-510) |

### Test Results

- Unit tests: **23 passed**, 0 failed (black, ruff, pytest 전체 통과)
- Integration: **사용자 검증 대기** — teleop으로 cmd_vel 전송 → 바퀴 회전 + 로버 전진 확인 필요

### Sensor Q&A (사용자 질문 기록)

1. **LiDAR 종류**: RTX LiDAR (`isaacsim.sensors.rtx.LidarRtx`, profile="Example_Rotary")
2. **센서 위치**: 임의 오프셋 (YAML 지정). URDF의 83개 Frame_* 링크(NavCam, MastCam 등)는 `merge_fixed_joints=True`로 병합되어 소실. 실제 위치 복원은 Stage 2 이후.

### Blockers / Issues

- Drive damping 1000.0 초기값의 적정성은 사용자 통합 테스트 후 확인 필요
- 바퀴-지면 마찰이 부족하면 DriveAPI가 있어도 슬립 발생 가능 (friction material 추가 필요할 수 있음)

### Next Steps

- ~~사용자 통합 테스트: teleop → cmd_vel → 로버 이동 확인 + drive_damping 튜닝~~ → 아래 Stage 1.6 참조
- Mars gravity (3.72) 전환 → IMU z축 검증 (3.72 ± 0.05 m/s²)
- Scenario 1 (Basic Mars): DEM 지형 + 암석 배치 위에 로버 스폰

---

## [2026-04-16] Phase 1 Stage 1.6: Drive Damping 증가 + Ackermann Steering Controller

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/, configs/, tests/unit/
**Type:** Bug Fix + Feature

### Original Plan

Stage 1.5에서 DriveAPI 추가 후 사용자 통합 테스트 결과:
1. `drive_damping: 1000.0`으로는 뒤쪽 바퀴 1개만 아주 느리게 회전
2. damping 100배 증가(`100000.0`) + `drive_max_force: 1000000.0` 후 로버 이동 시작
3. 그러나 **직진 후 일정 거리에서 정지**, **회전 이상 동작** 발생
4. 사용자 진단: rocker-bogie 6륜 구조에 skid-steer 부적합 → Ackermann steering 필요

### What Was Done

#### Drive Damping 증가

| 파라미터 | 이전값 | 변경값 | 이유 |
|---------|--------|--------|------|
| `drive_damping` | 1,000.0 | 100,000.0 | density=500 collision mesh → 총 질량 수천 kg, 높은 토크 필요 |
| `drive_max_force` | (없음) | 1,000,000.0 | PhysX 토크 클램핑 방지 |

#### Ackermann Steering Controller 구현

**문제**: skid-steer (좌우 속도차)로는 rocker-bogie 6륜 로버의 회전 불가.
Lateral slip이 극히 제한적 → 직진 일정 거리 후 steer drift로 저항 누적 → 정지.

**해결**: Perseverance의 실제 구동 방식인 4-corner Ackermann steering을 별도 모듈로 구현.

1. **`scripts/phase1/ackermann.py`** (신규)
   - Pure Python + NumPy, Isaac Sim 의존 없음 (P3 준수)
   - 3가지 모드: Straight, Point turn, Ackermann curve
   - ICR 기반 per-wheel steer + velocity: `R = v/w`, `steer = atan(x_w / (R-y_w))`
   - 출력: `steer_angles[4]` (LF,LR,RF,RR) + `wheel_velocities[6]` (LF,LM,LR,RF,RM,RR)

2. **`configs/phase1.yaml`** 수정
   - `wheel_track: 2.9` (부정확) 제거 → URDF 실측 geometry:
     - `wheelbase: 2.26`, `track_steer: 2.125`, `track_middle: 2.369`
   - Steer DriveAPI 파라미터 추가: `steer_stiffness: 50000.0`, `steer_damping: 5000.0`, `steer_max_force: 100000.0`

3. **`scripts/phase1/run_stage1.py`** 수정
   - `ackermann_command()` import, `skid_steer_targets()` 주석 처리
   - Steer joints DriveAPI 블록 추가 (position mode)
   - Main loop: `ackermann_command()` → `set_joint_position_targets()` + `set_joint_velocity_targets()`

4. **`tests/unit/test_ackermann.py`** (신규, 15개 테스트)
   - Straight (3), Point turn (3), Curve (4), Shapes (2), Validation (3)

5. **`tests/unit/test_run_stage1_helpers.py`** 수정
   - skid_steer 테스트 주석 처리, config 키 업데이트

### URDF Geometry (kinematic chain 추적)

| 바퀴 | X (m) | Y (m) | Steer Joint | Drive Joint |
|------|-------|-------|-------------|-------------|
| LF | +1.185 | -1.063 | LF_STEER (Z-axis) | LF_DRIVE (-Y axis) |
| LM | 0.000 | -1.185 | (없음) | LM_DRIVE (-Y axis) |
| LR | -1.075 | -1.063 | LR_STEER (Z-axis) | LR_DRIVE (-Y axis) |
| RF | +1.185 | +1.063 | RF_STEER (Z-axis) | RF_DRIVE (-Y axis) |
| RM | 0.000 | +1.185 | (없음) | RM_DRIVE (-Y axis) |
| RR | -1.075 | +1.063 | RR_STEER (Z-axis) | RR_DRIVE (-Y axis) |

- Wheelbase: 2.26 m, Track (steer): 2.125 m, Track (middle): 2.369 m
- Wheel radius: 0.2667 m

### Key Decisions

| 결정 | 근거 |
|------|------|
| Ackermann을 별도 모듈 분리 | 사용자 요청 (코드 모듈화), P3 준수 (오프라인 테스트 가능) |
| ICR 통합 수식 | Straight는 `\|w\|<eps`로 분기, 나머지는 `R=v/w` 통합 수식으로 처리 |
| drive_damping=1e5, drive_max_force=1e6 | density=500 → 수천 kg, 높은 토크 필요 |
| `wheel_track: 2.9` 제거 → 3개 실측값 | URDF 킨레매틱 체인 추적: front/rear ≠ middle track |

### Test Results

- Unit tests: **222 passed**, 0 failed (black, ruff, pytest 전체 통과)

### Issues (사용자 통합 테스트 결과)

Ackermann 구현 후에도 **동일 증상 지속**: 직진 후 정지 + 회전 이상.
→ 아래 Stage 1.7에서 근본 원인 분석 및 해결.

---

## [2026-04-16] Phase 1 Stage 1.7: Ackermann Controller 고도화 (DriveAPI 타이밍 + 부호 규약 + 유클리드)

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/, configs/, tests/unit/
**Type:** Bug Fix (critical)

### Original Plan

Stage 1.6 Ackermann 구현 후에도 동일 문제 지속. 웹 리서치 + Isaac Sim 5.1.0 로컬
소스 분석 + URDF 관절 축 조사를 통해 **3가지 근본 원인** 식별.

### Root Cause Analysis

#### RC1: DriveAPI 타이밍 (정지 근본 원인)

```
실행 순서:
L473: articulation = Articulation(prim_paths_expr=prim_path)
L474: world.reset()           ← PhysX physics view 생성, USD → PhysX 캐시
L475: articulation.initialize()
L502+: USD DriveAPI 속성 설정   ← 이미 캐시된 PhysX에 반영 안 됨!
```

`world.reset()` 시점에 PhysX가 USD를 캐시하므로, 이후 USD `CreateAttribute`로
설정한 drive gains (stiffness, damping, maxForce)가 **실제 시뮬레이션에 반영되지 않음**.
결과적으로 drive joints는 기본값(stiffness=0, damping=0)으로 남아
`set_joint_velocity_targets()`가 아무 토크도 생성하지 않음 → 마찰로 정지.

**근거**: Isaac Sim 5.1.0 소스 (`isaacsim.core.prims/articulation.py:1057-1066`)에서
`set_joint_velocity_targets()`는 `_physics_view.set_dof_velocity_targets()`로 위임.
physics view는 `world.reset()` 시 생성되며, 이후 USD 변경을 다시 읽지 않음.
Isaac Lab Issue #2807, #344에서도 동일 패턴이 보고됨.

#### RC2: Steer 부호 반전 (회전 이상 원인)

URDF steer joints: axis `(0, 0, 1)` = Z-up.
`spawn_orientation_rpy: [π, 0, 0]` → local Z-up이 world Z-down으로 변환.
Positive steer angle (URDF 로컬 CCW) → world 공간에서 CW (오른쪽 회전).
Ackermann 모듈은 positive = 좌회전 가정 → 반대 방향으로 조향.

#### RC3: Wheel velocity 근사 오차

기존: `omega = w * (R - y_w) / r` (Y-성분만, 전후 바퀴 ~4% 오차).
NVIDIA 내장 AckermannController도 유클리드 거리 사용:
`dist = sqrt(x_w² + (R-y_w)²)`, `omega ∝ dist / r`.

### What Was Done

1. **DriveAPI → `set_gains()` API 전환** (`run_stage1.py`)
   - 기존 USD DriveAPI 블록 3개 (drive/steer/suspension) 전체 **주석 처리**
   - `articulation.set_gains(kps, kds)` — PhysX 텐서에 직접 기록
   - Physics handle warmup: `world.step()` 5회 → gains 설정
   - `set_effort_modes("acceleration")` — 질량 자동 보상
   - `set_max_efforts()` — 토크/가속도 제한
   - `get_gains()` readback으로 실제 적용값 출력 검증
   - Drive + steer + suspension 단일 `set_gains()` 호출로 통합

2. **`negate_steer: true` 플래그** (`run_stage1.py`, `phase1.yaml`)
   - Main loop에서 `steer_angles = -steer_angles` 적용
   - 180° X-roll로 인한 steer Z-axis 반전 보상

3. **진단 로깅 모드** (`run_stage1.py`, `phase1.yaml`)
   - `debug_logging: false` → true 시 매 1초(60 step)마다:
     twist (v,w), steer_cmd, steer_actual, drive_cmd, drive_actual 출력

4. **유클리드 거리 기반 wheel velocity** (`ackermann.py`)
   - 기존: `omega = w * (R - y_w) / r`
   - 변경: `dist = sqrt(x_w² + dy²)`, `omega = copysign(1, w*dy) * |w| * dist / r`
   - 중간 바퀴(x_w=0) = 기존과 동일, 전후 바퀴 = ICR까지 실제 거리

5. **Config 추가** (`phase1.yaml`)
   - `drive_type: "acceleration"`, `negate_steer: true`, `debug_logging: false`

6. **테스트 추가** (`test_ackermann.py`)
   - `TestAckermannEuclidean` 클래스 3개 테스트:
     - `test_front_rear_faster_than_middle_on_curve`
     - `test_middle_wheels_same_as_linear_approx`
     - `test_point_turn_front_faster_than_middle`

### Key Decisions

| 결정 | 근거 |
|------|------|
| USD DriveAPI → `set_gains()` | PhysX physics view가 `world.reset()` 시점에 USD 캐시 → 이후 변경 무효. `set_gains()`는 PhysX 텐서 직접 기록 |
| `drive_type: "acceleration"` | density=500 → 수천 kg. acceleration 모드는 질량/관성 자동 보상 |
| `negate_steer: true` (YAML) | 180° X-roll 후 steer Z-axis 반전. 플래그로 실험적 전환 가능 |
| 유클리드 거리 | NVIDIA AckermannController 동일 접근. 전후 바퀴 정확도 향상 |

### Files Modified

| 파일 | 변경 | 설명 |
|------|------|------|
| `scripts/phase1/run_stage1.py` | 수정 | USD DriveAPI → `set_gains()`, negate_steer, debug_logging |
| `scripts/phase1/ackermann.py` | 수정 | 유클리드 거리 기반 wheel velocity |
| `configs/phase1.yaml` | 수정 | drive_type, negate_steer, debug_logging 추가 |
| `tests/unit/test_ackermann.py` | 수정 | TestAckermannEuclidean 3개 추가 (총 18개) |
| `tests/unit/test_run_stage1_helpers.py` | 수정 | VALID_CONFIG 업데이트 |

### Test Results

- Unit tests: **225 passed**, 0 failed (black, ruff, pytest 전체 통과)
  - test_ackermann.py: 18 passed (기존 15 + 신규 3)
  - test_run_stage1_helpers.py: 17 passed

### User Integration Test Guide

**1단계: 진단 모드로 부호 확인**
```yaml
# phase1.yaml:
debug_logging: true
```
```bash
# Terminal A:
scripts/isaac_python.sh scripts/phase1/run_stage1.py --config configs/phase1.yaml
# Terminal B:
ros2 topic pub --once /rover/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.1}, angular: {z: 0.0}}"
```
→ Gain readback에서 kd > 0 확인
→ `[DIAG]` 출력에서 drive_act 양수 확인

**2단계: teleop 주행 테스트**
```bash
ros2 run teleop_twist_keyboard teleop_twist_keyboard \
  --ros-args --remap cmd_vel:=/rover/cmd_vel
```
- `i`: 지속적 전진, `j`/`l`: 좌/우 선회, `k`: 즉시 정지

**튜닝 가이드:**

| 증상 | 원인 | 조치 |
|------|------|------|
| 여전히 정지 | kd=0 (gains 미적용) | warmup step 증가 또는 USD fallback |
| 직진 방향 반대 | drive axis 부호 | `wheel_vels = -wheel_vels` 추가 |
| 조향 방향 반대 | negate_steer 값 | `negate_steer: false`로 전환 |
| 조향 떨림 | steer_damping 부족 | `steer_damping` 2배 증가 |
| 속도 너무 느림 | force mode 토크 부족 | `drive_type: "acceleration"` 확인 |

---

### Stage 1.8: 런타임 크래시 수정 — 변수 충돌 + set_gains() fallback

**날짜:** 2026-04-16
**이전 상태:** Stage 1.7 코드 구현 완료, 2회 연속 Isaac Sim segfault 크래시

**진단 (temp_run5.txt 분석):**

1. **Bug 1 — `ns` 변수 충돌 (크래시 직접 원인)**
   - `set_max_efforts` shape 수정 시 `ns = len(steer_indices)` (= 4)가
     `ns = ros2_cfg["namespace"]` (= "rover")를 덮어씀
   - ROS2 노드 이름 `"4_stage1_runtime"` → 숫자로 시작 → InvalidNodeNameException → segfault
   - 수정: `ns` → `n_steer`, `nd` → `n_drive`로 변수명 변경

2. **Bug 2 — `set_gains()` PhysX 미반영**
   - readback: 모든 joint kp=35809.9, kd=0.0 (USD 기본값)
   - Isaac Sim 5.1.0 소스 분석: `set_gains()` 내부에서 `timeline.is_stopped()` 또는
     `physics_sim_view is None`이면 USD fallback 경로를 탐
   - 수정: warmup 10 steps + `timeline.play()` 명시 호출 + readback 검증 +
     실패 시 USD DriveAPI fallback + `world.reset()` 재동기화

3. **Bug 3 — `set_max_efforts` shape mismatch (이전 세션에서 수정 완료)**
   - `(1, 29)` → `(1, 15)` shape 오류. `(1, num_controlled)`로 수정 완료.

**수정 파일:**
- `scripts/phase1/run_stage1.py`:
  - `n_drive`/`n_steer` 변수명 변경 (Bug 1)
  - `_apply_drive_gains_via_usd()` 내부 함수 추출 (기존 주석 블록 로직 재활용)
  - warmup 5→10 steps, `timeline.play()` 명시 호출
  - `set_gains()` → readback 검증 → 실패 시 USD fallback + `world.reset()` 재호출

**검증:** black OK, ruff OK, pytest 225 passed.

---

### Stage 1.9: DriveAPI effort mode — USD pre-reset 전략으로 전환

**날짜:** 2026-04-16
**이전 상태:** 크래시 해결, gain readback OK, 그러나 cmd_vel 인가 시 바퀴 미회전

**진단 (temp_run5.txt DIAG 분석):**
- drive_cmd=0.375 rad/s 인가 → drive_act ≈ 0 (바퀴 미회전)
- steer_cmd=0 인가 → steer_act가 -0.5 rad까지 drift (position control 미작동)
- `set_gains()` readback은 정확 (kd=100000, kp=50000)

**근본 원인:** Isaac Sim 5.1.0 `set_effort_modes()` API 소스 분석 결과:
- `set_effort_modes()`는 **USD DriveAPI 속성만 변경**, PhysX 텐서 경로 없음
- `set_gains()`와 달리 timeline/physics_view 체크 없이 항상 USD만 수정
- `world.reset()` 후 호출 → PhysX가 이미 캐시한 기본 effort type으로 작동
- PhysX가 force mode에서 acceleration 값을 받으면 사실상 무시됨

**수정:**
- USD DriveAPI 속성(gains + effort type + maxForce) 전부를 `world.reset()` **이전**에 설정
- `world.reset()`이 USD→PhysX 캐시 동기화 시 effort type도 함께 반영
- `set_gains()`는 reset 후 PhysX 텐서에 gains를 강화(reinforce)
- effort mode readback 추가 (검증)
- `set_effort_modes()` 후처리 호출 제거

**수정 파일:** `scripts/phase1/run_stage1.py`

**검증:** black OK, ruff OK, pytest 225 passed.

### Next Steps (Stage 1.7 기준)

- 사용자 통합 테스트: cmd_vel 인가 시 바퀴 회전 확인 (drive_act > 0)
- Mars gravity (3.72) 전환 → IMU z축 검증 (3.72 ± 0.05 m/s²)
- Scenario 1 (Basic Mars): DEM 지형 + 암석 배치 위에 로버 스폰

---

## [2026-04-16] Stage 1.8~1.11: 로버 주행 정지 디버깅 및 해결

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/, configs/phase1.yaml
**Type:** Critical Bug Fix (multi-session iterative debugging)

### 문제 현상

cmd_vel=0.1 m/s 또는 0.5 m/s를 ROS2로 전송하면 로버가 **일정 시간 정상 주행 후 갑자기 모든 바퀴가 정지**하여 영구적으로 회복 불가 상태에 빠짐. cmd_vel은 계속 전송되고 있었음.

**시각적 관찰:** 로버가 띄워지거나 뒤집히는 현상은 없음 — 지면에 있지만 바퀴가 구동력 상실.

### 디버깅 과정 (시도 → 결과)

| Stage | 시도 | 가설 | 결과 |
|-------|------|------|------|
| 1.7 | `drive_damping` 100000→10000 | 과도한 모터 토크가 wheelie 유발 | **실패** — 동일 패턴 |
| 1.8 | velocity ramp 도입 (`max_wheel_accel_rate=0.5`) | 즉각적 속도 점프가 임펄스 유발 | **실패** — ramp은 정상 동작하나 정지 패턴 동일 |
| 1.9 | `suspension_damping` 85→500, `linear_damping=10` 추가 | spawn 후 흔들림이 주행 불안정 유발 | **idle 안정화 성공**, 그러나 주행 정지 동일 |
| 1.10 | 종합 분석: linear_damping/suspension/drive 감쇠 조정 | PhysX velocity damping 공식이 과도한 속도 감쇠 유발 | **부분 성공** — 원래 7초에서 1~2초로 단축 (새 실패 모드 발견) |
| **1.11** | **drive joint limit ±pi 발견 및 제거** | **URDF sanitizer가 ±DBL_MAX를 ±pi로 교체** | **성공 — 30초+ 연속 주행 달성** |

### 근본 원인 1: URDF Joint Limit 클램핑 (CRITICAL)

**파일:** `scripts/phase1/convert_urdf_to_usd.py` line 39-40

```python
# 문제 코드:
(re.compile(rf'lower="{_DBL_MAX_RE}"'), 'lower="-3.14159"'),
(re.compile(rf'upper="{_DBL_MAX_RE}"'), 'upper="3.14159"'),
```

NASA JPL m2020 URDF는 모든 관절에 `±1.79769e+308` (DBL_MAX)를 limit으로 사용.
Isaac Sim의 URDF importer가 DBL_MAX를 float32로 파싱 시 오버플로우하므로,
sanitizer가 이를 `±3.14159` (±pi)로 교체. 이것은 steer/suspension에는 적절하나,
**drive wheel(구동 바퀴)은 연속 회전이 필요**하므로 ±180° 회전 후 PhysX joint limit에
도달하여 잠김.

**증거 (drive_pos 로그):**
```
Step 2100: drive_pos = [1.91, 1.81, 1.79, 1.81, 1.84, 1.78]  ← pi 접근
Step 2160: drive_pos = [3.1416, 3.1416, 3.1416, 3.1416, 3.1416, 3.1416]  ← 정확히 pi에서 잠김!
```

**이전 테스트에서 7초 후 실패한 것도 동일 원인:** cmd_vel=0.1에서 wheel_vel=0.375 rad/s
→ pi까지 도달 시간 = pi / 0.375 ≈ **8.4초** (실측 7~8초와 일치).

**수정:**
1. **런타임 override** (`run_stage1.py`): drive joint의 USD `physics:lowerLimit`/`upperLimit`을
   `±1e6`으로 덮어쓰기 (USD 재변환 없이 즉시 적용)
2. **sanitizer 수정** (`convert_urdf_to_usd.py`): global ±pi pass 후 drive joint 6개에 대해
   `±1e6`으로 재확장하는 second pass 추가

### 근본 원인 2: 과도한 Body Linear Damping (HIGH)

**파일:** `configs/phase1.yaml` — `linear_damping: 10.0`

PhysX `physxRigidBody:linearDamping` 공식: `velocity *= max(0, 1 - damping * dt)`

dt=1/60, damping=10.0일 때 **매 스텝 16.7% 속도 감소** → 1초 후 잔여 속도 0.002%.
바퀴가 마찰력으로 본체를 밀어도 본체가 매 스텝 속도를 급격히 잃어, 바퀴-지면 마찰원추
(friction cone) 포화 → 슬립 → 진동 고착.

**수정:** `linear_damping: 10.0` → `0.5` (매 스텝 0.83% 감소, 1초 후 61% 잔여)

### 근본 원인 3: 과도한 Suspension/Drive Damping (HIGH)

- `suspension_damping: 500.0` (acceleration mode) → rocker-bogie 사실상 강체로 고정.
  하중 재분배 불가 → RSM 마스트(좌측 편향)로 인한 질량 비대칭이 LF 바퀴 과부하 유발.
- `drive_damping: 10000.0` → 미세 속도 오차에 3750 rad/s² 교정 가속도.
  마찰원추 초과 가능성 높음.

**수정:** `suspension_damping: 500.0` → `50.0`, `drive_damping: 10000.0` → `1000.0`

### 추가 수정사항

- **PhysX solver iterations** 증가 시도: `set_solver_position_iteration_count(16)` →
  Isaac Sim 5.x `PhysicsContext`에 해당 메서드 없음 (`AttributeError`).
  USD `physxScene` 속성으로 대체 시도했으나, `add_default_ground_plane()` 생성 시점에서
  PhysicsScene prim을 찾지 못함. 현재 기본값(4 pos / 1 vel) 사용 중 — 추후 해결 필요.
- **drive_pos DIAG 로깅** 추가: 관절 누적 위치를 로깅하여 joint limit 잠김 감지 가능.
- **Ackermann 제어기 검증**: 직진(w=0)시 ICR 미사용, 6바퀴 균일 속도 반환 확인.
  URDF 구동 축 6개 모두 `<axis xyz="0 -1 0"/>`, 좌/우 부호 차이 없음.
  180° X-roll 후 구동 방향 반전 불필요 (PhysX joint는 local frame 기준). **문제 없음.**

### 최종 파라미터 (Stage 1.11)

```yaml
# configs/phase1.yaml
rover:
  angular_damping: 12.0
  linear_damping: 0.5         # was 10.0 (Stage 1.9)
control:
  drive_damping: 1000.0       # was 10000.0 (Stage 1.7) / 100000.0 (원래)
  suspension_damping: 50.0    # was 500.0 (Stage 1.9) / 85.0 (원래)
  max_wheel_accel_rate: 0.5   # Stage 1.8에서 추가
  drive_type: "acceleration"
  negate_steer: true
```

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `configs/phase1.yaml` | linear_damping 10→0.5, suspension_damping 500→50, drive_damping 10000→1000 |
| `scripts/phase1/run_stage1.py` | drive joint limit ±1e6 override, drive_pos DIAG, solver iteration 시도(실패→fallback) |
| `scripts/phase1/convert_urdf_to_usd.py` | sanitizer에 drive joint limit ±1e6 second pass 추가 |

### 검증 결과 (사용자 통합 테스트)

**테스트 명령:**
```bash
scripts/isaac_python.sh scripts/phase1/run_stage1.py --config configs/phase1.yaml
ros2 topic pub /rover/cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.5}, angular: {z: 0.0}}" -r 10
```

| 항목 | 결과 | 비고 |
|------|------|------|
| drive_act 안정 유지 | **PASS** | 1.87 ± 0.1, 30초+ 지속, 붕괴 없음 |
| body_vel.x 양수 유지 | **PASS** | 0.35~0.65 m/s (cmd_vel=0.5) |
| rover_pos.x 전진 | **PASS** | 0.1 → 8.96m (28초간) |
| rover_pos.z 안정 | **PASS** | ±0.05m 이내, 들림 없음 |
| drive_pos > pi | **PASS** | 36.4 rad (5.8회전), 잠김 없음 |
| idle body_vel 진동 | ±0.29 → ±0.003 | linear_damping 감소로 더 안정 |
| 사용자 시각 확인 | **PASS** | 정상 주행, 정지/급브레이크 없음 |

**오프라인 검증:** black OK, ruff OK, pytest 266 passed.

### 교훈

1. **URDF sanitizer의 global 치환은 위험.** 관절 종류(continuous vs revolute)에 따라 다른
   limit이 필요. DBL_MAX→±pi는 steer에 적절하나 drive에 치명적.
2. **drive_pos 로깅이 핵심 진단 도구.** velocity/position만으로는 joint limit 잠김을 감지 불가.
   drive_pos가 pi에 수렴하는 패턴이 결정적 증거.
3. **PhysX linear damping은 velocity multiplier.** Newtonian force가 아닌 `vel *= (1-d*dt)`.
   d=10은 매 스텝 16.7% 감소로 실질적 속도 제로. 로보틱스에서는 0.1~1.0이 적절.
4. **acceleration mode에서 damping 값은 관성 자동보상됨.** kd=10000은 raw Nm이 아니라
   10000 rad/s² 가속도. 마찰원추 대비 과도한 값.
5. **실패가 항상 좌측(LF)부터 시작한 이유:** RSM 마스트(y=+0.559m, 좌측)로 인한 질량
   비대칭 + 고정된 서스펜션(damping=500)이 하중 재분배 차단.

### Next Steps (Stage 1.11 시점)

- ~~Mars gravity (3.72 m/s²) 전환 → IMU z축 검증~~ → Stage 1.12에서 완료
- ~~PhysX solver iterations 정상 설정~~ → Stage 1.12에서 완료
- ~~Ackermann 곡선 주행 테스트~~ → Stage 1.12에서 테스트 + 문제 발견 + 수정
- Scenario 1 (Basic Mars): DEM 지형 + 암석 배치 위에 로버 스폰
- URDF 재변환 (`convert_urdf_to_usd.py` 수정 반영): 런타임 override 제거 가능

---

## [2026-04-16] Stage 1.12: Mars Gravity + Solver Fix + Ackermann Stability

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/run_stage1.py, configs/phase1.yaml
**Type:** Enhancement + Bug Fix

### 원래 계획

Stage 1.11에서 직진 주행이 해결된 후 4가지 후속 작업:
1. Mars gravity (3.72) 전환 + IMU z축 검증
2. PhysX solver iterations `/physicsScene` 직접 경로 수정
3. Ackermann 곡선 주행 검증 (angular velocity ≠ 0)
4. URDF 재변환 → 런타임 limit override 제거

Plan file: `~/.claude/plans/swift-puzzling-manatee.md`

### 세부 계획 및 구현

#### Task 1: Mars Gravity 전환 (완료)

- `configs/phase1.yaml` — `gravity: 9.81` → `3.72`
- `scripts/phase1/run_stage1.py` — DIAG 블록에 IMU acceleration 로깅 추가
- **검증 결과 (사용자 통합 테스트):**
  - `imu_acc.z ≈ -3.71` at idle (180° X-roll로 인해 음수)
  - |imu_acc.z| = 3.71 ± 0.02 → 3.72 ± 0.05 기준 통과

#### Task 2: Solver Iterations 수정 (완료)

- **이전:** `Usd.PrimRange` + `HasAPI(UsdPhysics.Scene)` 검색 → 항상 실패 (WARNING)
- **수정:** `stage.GetPrimAtPath("/physicsScene")` 직접 접근
  - Isaac Sim's World + `add_default_ground_plane()`이 `/physicsScene`에 생성
  - 프로젝트 내 다른 스크립트들도 모두 동일 경로 사용
- **검증:** `Solver iterations: pos=16, vel=4 on /physicsScene` 로그 확인

#### Task 3: Ackermann 곡선 주행 — 문제 발견 + 수정

**테스트 결과 (teleop_keyboard로 검증):**
- 직진 (v=0.5, w=0): 완벽하게 작동. 5m+ 연속 전진.
- 완만한 곡선: 정상 작동.
- 급격한 정지/높은 각속도: **로커-보기 다리 꼬임 → 로버 주저앉음**

**근본 원인 분석:**

| 문제 | 원인 | DIAG 증거 |
|------|------|-----------|
| 과도한 조향각 | v=0.5, w=0.5일 때 R=1.0m < wheelbase/2=1.13m → 내측 바퀴 87°+ | steer_cmd에 ±1.52 rad |
| 급격한 조향 복귀 | cmd_vel=0 시 steer 즉시 0으로 스냅, drive는 느리게 감속 | DIAG 3540: steer=0, drive=±2.67 |
| 느린 제동 | 0.5 rad/s² 감속률 → 최대 속도에서 6초 소요 | DIAG 3540~3720 |

Ackermann 기하학에서 R < track/2이면 내측 바퀴가 90° 이상 회전해야 하며,
이는 물리적으로 불가능. 실제 로버는 기계적 정지장치(mechanical stop)로 제한.

**3가지 수정 적용:**

1. **조향각 클램핑** (`max_steer_angle: 0.7` = 40°)
   - `np.clip(steer_angles, -max_steer_angle, max_steer_angle)`
   - 87°→40°로 제한. Ackermann 기하 정확도는 다소 저하되지만 물리적 안정 확보.

2. **조향 램프** (`steer_ramp_rate: 2.0` rad/s)
   - 기존: steer angles는 즉시 적용 (ramping 없음)
   - 수정: 드라이브 속도 램프와 동일한 방식으로 per-step 변화량 제한
   - cmd_vel=0 시 조향이 부드럽게 0으로 복귀 (0.7/2.0 = 0.35초)

3. **비대칭 감속** (`decel_multiplier: 3.0`)
   - 기존: 가속/감속 동일 속도 (0.5 rad/s², 정지에 6초)
   - 수정: 감속 시 3배 빠른 ramp (1.5 rad/s², 정지에 2초)
   - 판별: `|target| < |current|` → 감속 모드

### 수정 파일

| 파일 | 변경 |
|------|------|
| `configs/phase1.yaml` | gravity 9.81→3.72, max_steer_angle, steer_ramp_rate, decel_multiplier 추가 |
| `scripts/phase1/run_stage1.py` | solver path 수정, IMU DIAG, steer clamp+ramp, asymmetric decel |

### 오프라인 검증

```
black --check: All 83 files unchanged
ruff check: All checks passed
pytest tests/unit/: 268 passed, 1 warning
```

### Task 3 수정 후 통합 테스트 (완료)

teleop_keyboard로 재검증:
- 급정지 시 부드러운 감속 확인 (decel_multiplier=3.0 동작)
- 높은 각속도에서 조향각 ±0.7 rad(40°) 클램핑 확인
- 로커-보기 안정성 확인 — 다리 꼬임 현상 해소

#### Task 4: URDF 재변환 + 런타임 Override 제거 (완료)

**Step 4a: URDF 재변환 (사용자 실행)**
```
scripts/isaac_python.sh scripts/phase1/convert_urdf_to_usd.py
```
- 결과: `Imported root prim: /Perseverance/Body_Chassis`
- base USD 크기: 21,234,792 bytes (21MB) — 메시 데이터 정상 직렬화
- sanitizer의 drive joint limit widening pass(±1e6)가 USD에 bake됨

**Step 4b: 런타임 override 코드 주석 처리**
- `scripts/phase1/run_stage1.py`에서 제거한 코드:
  - `drive_limit = 1e6`
  - `rev_api.GetLowerLimitAttr().Set(-drive_limit)` / `.Set(drive_limit)`
  - `print(f"Drive joint limits overridden...")`

**Step 4c: 재검증 (사용자 통합 테스트)**
- `Drive joint limits overridden` 로그 미출력 확인 — override 완전 제거
- drive_pos 최대 25.9 rad 도달 (pi=3.14의 8배 이상) — 잠김 없음
- 좌우 비대칭 drive_pos (회전 중): 좌측 -4.16 rad, 우측 +6.49 rad — Ackermann 정상
- 직진/곡선/제자리 회전/급정지 모두 시각적으로 안정 확인

### Stage 1.12 전체 결과 요약

| Task | 상태 | 핵심 결과 |
|------|------|-----------|
| 1. Mars gravity | ✅ 완료 | imu_acc.z ≈ -3.71 (3.72 ± 0.05 통과) |
| 2. Solver iterations | ✅ 완료 | pos=16, vel=4 on /physicsScene (WARNING 해소) |
| 3. Ackermann 안정성 | ✅ 완료 | steer clamp 40° + ramp 2.0 rad/s + 3x decel |
| 4. URDF 재변환 | ✅ 완료 | base USD 21MB, override 제거, drive_pos > 25 rad |

### 최종 파라미터 (Stage 1.12 완료 시점)

```yaml
# configs/phase1.yaml 핵심 값
physics:
  gravity: 3.72           # Mars gravity
  time_step: 0.01667      # 60 Hz
rover:
  angular_damping: 12.0
  linear_damping: 0.5
  com_offset: [0.2, 0.0, 0.0]
control:
  drive_damping: 1000.0
  drive_type: "acceleration"
  suspension_damping: 50.0
  max_steer_angle: 0.7    # 40° mechanical stop
  steer_ramp_rate: 2.0    # rad/s
  decel_multiplier: 3.0   # 3x faster braking
  max_wheel_accel_rate: 0.5
  negate_steer: true
```

### Next Steps

- Rover + Scene 통합: DEM 지형 위에 로버 스폰 (별도 세션에서 scene 개발 완료됨)
- Scenario 1 (Basic Mars) 완성

---

## [2026-04-17] Phase 1 Stage 1.13~1.14: 센서 TF · Depth · Odom 문제 해결

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/run_stage1.py, configs/phase1.yaml
**Type:** Bug Fix (다단계 반복)

### Original Plan (세션 시작 시점)

Stage 1.12 완료 상태 기준으로 rover + scene 통합 준비 단계. 그러나 rviz2에서 TF/센서 검증
중 다수의 문제 발견 → 통합 전에 센서 파이프라인 안정화 필요.

### Implementation Plan (발견된 문제들)

1. 센서가 로버와 함께 이동하지 않고 world 원점에 고정
2. TF 프레임 이름 불일치로 TF tree 분리 (`/rover/base_link` vs `base_link`)
3. Depth 카메라 이미지에 심한 수직 줄무늬 노이즈
4. odom → base_link TF가 로버와 함께 이동 (분리 안됨)
5. Isaac Sim segfault 반복 발생
6. TF_OLD_DATA 경고로 LiDAR pointcloud 미출력
7. rviz2에서 base_link가 두 위치로 순간이동 (TF 이중 발행)

### What Was Done — 7가지 문제 해결 과정

---

#### Issue 1: 센서 world 고정 문제

**증상**: 로버가 전진해도 camera/lidar/imu의 world 좌표가 변하지 않음. rviz2 pointcloud가
로버를 따라가지 않고 원점에 머무름.

**원인 분석**: URDF→USD 변환 후 prim tree 구조를 조사한 결과:
```
/World/Rover/Body_Chassis              ← Xform + ArticulationRootAPI (STATIC, 움직이지 않음)
/World/Rover/Body_Chassis/Body_Chassis ← RigidBodyAPI (물리 엔진이 업데이트, MOVES)
```
기존 코드는 `chassis_path` (외부 Xform) 하위에 센서를 부착하고 있었음. 이 Xform은
articulation root로 정적 위치. 내부 RigidBodyAPI prim만 physics 업데이트를 받음.

**해결**: `chassis_prim.GetChildren()`을 순회해서 `UsdPhysics.RigidBodyAPI`를 가진 child를
찾아 `rigid_body_path`로 사용. 모든 센서(Camera, LiDAR, IMU)를 이 경로 하위에 부착.

```python
rigid_body_path = chassis_path  # fallback
for child in chassis_prim.GetChildren():
    if child.HasAPI(UsdPhysics.RigidBodyAPI):
        rigid_body_path = str(child.GetPath())
        break
```

**결과**: 센서가 로버와 함께 이동 확인.

---

#### Issue 2: TF 프레임 이름 불일치

**증상**: rqt_tf_tree에서 `odom → base_link`와 `/rover/base_link → sensor frames` 두 개의
분리된 tree가 존재. `/rover/odom`은 존재하지 않음.

**원인**: OmniGraph PubOdom은 `base_link` (prefix 없음)을 발행, 반면 StaticTransformBroadcaster
는 `rover/base_link → rover/camera_link` 등 prefix 붙은 이름을 사용.

**해결**: 모든 TF frame 이름에서 `rover/` prefix 제거:
- `odom`, `base_link`, `camera_link`, `lidar_link`, `imu_link`
- Static broadcaster의 parent_frame을 `"base_link"`로 통일

**결과**: TF tree가 단일 체인으로 연결됨.

---

#### Issue 3: Depth 카메라 수직 줄무늬 노이즈 (3차 반복)

**증상**: `work_log/rover_generation/depth_noise.png` — depth 이미지에 심한 수직 줄무늬
패턴. RGB 이미지는 정상.

**시도 1 — Camera constructor에 orientation 제거**:
- 가설: constructor의 orientation 파라미터가 depth render pipeline 손상
- 시도: `translation`만 전달, orientation은 `set_local_pose`로 후처리
- 결과: **실패** — 줄무늬 여전

**시도 2 — AddOrientOp()로 orientation 적용**:
- 가설: set_local_pose가 내부 캐시를 갱신 안함
- 시도: `xform.AddOrientOp().Set(Gf.Quatf(...))`
- 결과: **segfault** — `pxr.Tf.ErrorException: Camera already has xformOps`

**시도 3 — set_local_pose() 재시도**:
- 결과: **실패** — 줄무늬 여전

**시도 4 — 별도 Render Product (RPDepth)**:
- 가설: RGB와 Depth가 동일 render product 공유 → buffer conflict
- 시도: OmniGraph에 `RPDepth` 추가, `RPCamera`는 RGB 전용
- 결과: **실패** — 줄무늬 여전

**최종 해결 — 부모 Xform 패턴 (확정된 근거 기반)**:

확인된 사실: Camera prim의 xformOps를 수정하는 **모든 방법**이 depth pipeline을 손상시킴.
→ Camera prim 자체는 건드리지 않고, 중간 Xform prim에 translation + orientation을 적용.

```
rigid_body_path/
  stage1_camera_xform   ← UsdGeom.Xform (translate + orient here)
    stage1_camera       ← Camera (xformOps 없음, 부모에서 상속)
```

```python
if has_cam_orient:
    camera_xform_path = f"{rigid_body_path}/stage1_camera_xform"
    camera_xform = UsdGeom.Xform.Define(stage, camera_xform_path)
    camera_xform.ClearXformOpOrder()
    cx_translate = camera_xform.AddTranslateOp()
    cx_translate.Set(Gf.Vec3d(*camera_cfg["local_translation"]))
    cx_orient = camera_xform.AddOrientOp()
    cx_orient.Set(Gf.Quatf(cam_qw, cam_qx, cam_qy, cam_qz))
    camera_prim_path = f"{camera_xform_path}/stage1_camera"

camera = Camera(
    prim_path=camera_prim_path,
    resolution=tuple(camera_cfg["resolution"]),
    translation=None if has_cam_orient else np.asarray(...),
)
```

**결과**: rqt_image_view에서 depth 이미지 정상 확인. rviz2 Image display는 여전히 노이즈로
보이나, 이는 rviz2의 depth 시각화 설정 문제이며 data 자체는 정상.

---

#### Issue 4: odom → base_link 분리 실패 (3차 반복)

**증상**: 로버가 전진해도 odom과 base_link가 서로 붙어서 함께 이동. REP-105 위반.

**시도 1 — ComputeOdom chassisPrim = ArticulationRootAPI prim**:
- 시도: `/World/Rover/Body_Chassis` (외부 Xform) 지정
- 결과: **실패** — odom이 원점 고정

**시도 2 — chassisPrim = RigidBodyAPI prim**:
- 시도: `/World/Rover/Body_Chassis/Body_Chassis` 지정
- 결과: **실패** — 여전히 붙어서 이동

**시도 3 — chassisPrim = 최상위 prim**:
- 시도: `/World/Rover` 지정
- 결과: **실패** — 여전히 붙어서 이동

**최종 해결 — OmniGraph ComputeOdom/PubOdom 완전 제거 + 수동 rclpy publisher**:

OmniGraph `IsaacComputeOdometry` 노드의 chassisPrim 입력이 3가지 경로로 모두 실패.
노드 내부 동작이 불확실하므로 우회 → 직접 `articulation.get_world_poses()`로 계산.

```python
# world.reset() 이후 초기 포즈 캡처
init_poses = articulation.get_world_poses()
odom_init_pos = init_poses[0].copy()
odom_init_quat = init_poses[1].copy()

# 메인 루프: 매 틱마다 delta 계산 후 발행
cur_pos, cur_quat = articulation.get_world_poses()
delta_pos_world = cur_pos - odom_init_pos
delta_pos_odom = quat_rotate_vec(odom_init_quat_inv, delta_pos_world)
delta_quat = quat_multiply(odom_init_quat_inv, cur_quat)

odom_tf_broadcaster.sendTransform(...)  # odom → base_link TF
odom_pub.publish(Odometry(...))          # /rover/odom
```

Helper 함수 추가: `quat_inverse`, `quat_multiply`, `quat_rotate_vec`.

**결과**: odom → base_link 분리 성공. 로버가 전진할 때 base_link만 이동, odom은 고정.

---

#### Issue 5: 반복된 segfault

**segfault 1 — `PubTF.inputs:targetPrims` 속성 미존재**:
- 시도: `[odom_chassis_path]`로 targetPrims 설정
- 오류: `OmniGraphError: Attribute named 'inputs:targetPrims' does not refer to a legal og.Attribute`
- 이후: `libomni.syntheticdata.plugin.so` segfault → shutdown 강제 종료
- 해결: Isaac Sim 5.1의 `ROS2PublishRawTransformTree`에는 `targetPrims` 입력이 없음.
  해당 라인 제거.
- 메모리 저장: `feedback_omnigraph_attribute_verify.md` — OmniGraph 노드 속성 추측 금지

**segfault 2 — `cam_xform.AddOrientOp()`**:
- 오류: `pxr.Tf.ErrorException: Camera already has xformOps`
- 원인: `camera.initialize()`가 이미 xformOps를 생성 → 중복 적용 충돌
- 해결: `set_local_pose()`로 전환 (이후 부모 Xform 패턴으로 재설계)

**사용자 피드백 (중요)**:
> "앞으로 확실한 근거가 없이 추측에 의존해서 함부로 수정하지마"

→ 메모리 저장: `feedback_no_speculative_fixes.md`
- 확실한 근거 없이 수정 금지
- OmniGraph 노드 동작 불확실 시 우회 구현
- 수정 전 "이 수정이 문제를 해결한다는 근거가 있는가?" 자문

---

#### Issue 6: TF_OLD_DATA 경고 → LiDAR pointcloud 미출력

**증상**:
```
[WARN] TF_OLD_DATA ignoring data from the past for frame base_link at time 79.389831
according to authority Authority undetectable
```
→ rviz2에서 LiDAR pointcloud가 전혀 표시되지 않음.

**원인 분석**:
- rclpy 노드는 **wall-clock 시간** 사용 (`node.get_clock().now()` → epoch 기준 ~1.7B 초)
- OmniGraph 노드들은 **simulation time** 사용 (`ReadSimTime.outputs:simulationTime` → 0~수백 초)
- `/clock`은 PubClock이 simulation time으로 발행
- rviz2/tf2는 `/clock` 기반으로 TF 평가 → wall-clock 타임스탬프의 odom→base_link TF를
  "먼 미래 데이터"로 판단하고 무시

**해결**: rclpy 노드 생성 시 `use_sim_time=True` 파라미터 추가:
```python
node = rclpy.create_node(
    f"{ns}_stage1_runtime",
    parameter_overrides=[
        rclpy.parameter.Parameter(
            "use_sim_time",
            rclpy.parameter.Parameter.Type.BOOL,
            True,
        )
    ],
)
```

**결과**: TF_OLD_DATA 경고 사라짐. LiDAR pointcloud 정상 출력.

---

#### Issue 7: base_link TF 이중 발행 (순간이동)

**증상**: rviz2에서 odom을 fixed frame으로 설정 시, base_link가 두 위치로 번갈아
순간이동하며 크게 흔들림.

**원인**: `/tf` 토픽에 두 개의 소스가 경쟁:
1. **수동 rclpy TransformBroadcaster** → `odom → base_link` (delta 기반, 정확히 이동)
2. **PubTF (ROS2PublishRawTransformTree)** → articulation 전체 prim tree 발행. Body_Chassis
   world transform이 별도 체인을 생성하여 base_link 위치에 간섭.

**해결**: PubTF의 topicName을 `/tf` → `/tf_raw`로 분리:
```python
("PubTF.inputs:topicName", "/tf_raw"),
```

- `/tf`: 수동 odom publisher + static broadcaster (SLAM/Nav2용)
- `/tf_raw`: PubTF articulation joints (디버깅/모니터링용)

**Trade-off**: rviz2 RobotModel 시각화 불가 (바퀴, 서스펜션 등 URDF link TF가 `/tf_raw`에만
있음). SLAM/Nav2에는 영향 없음. 향후 `/tf_raw` → `/tf` relay 또는 PubTF frame 이름
재설계로 통합 가능.

**결과**: base_link 순간이동 현상 해소. odom→base_link 분리가 정상 표시.

---

### Stage 1.13~1.14 최종 결과

| Issue | 상태 | 핵심 해결 |
|-------|------|----------|
| 1. 센서 world 고정 | ✅ 해결 | RigidBodyAPI prim 하위로 부모 변경 |
| 2. TF 이름 불일치 | ✅ 해결 | `rover/` prefix 제거, 통일 |
| 3. Depth 수직 줄무늬 | ✅ 해결 (rqt 기준) | 부모 Xform 패턴 (Camera prim xformOps 미변경) |
| 4. odom-base_link 붙음 | ✅ 해결 | OmniGraph ComputeOdom 폐기 → 수동 rclpy publisher |
| 5. segfault | ✅ 해결 | OmniGraph 속성 검증, 메모리 저장 |
| 6. TF_OLD_DATA | ✅ 해결 | `use_sim_time=True` 파라미터 |
| 7. base_link 순간이동 | ✅ 해결 | PubTF 토픽 `/tf` → `/tf_raw` 분리 |

### 사용자 확인 검증 (Isaac Sim 실행 결과)

1. **LiDAR**: pointcloud 정상 출력 확인
2. **Depth**:
   - rqt_image_view: 정상 (줄무늬 없음)
   - rviz2 Image display: 여전히 노이즈 표시 — rviz2 display 설정 문제로 판단 (데이터 정상)
3. **odom TF**:
   - odom 고정, base_link 전진 정상
   - 약간의 jitter 관찰됨 — PhysX 미세 진동 반영, SLAM 통합 시 `map → odom` 보정으로 흡수
4. **cmd_vel 제어**: 정상 동작 유지

### 주요 코드 변경 위치 (`scripts/phase1/run_stage1.py`)

- 신규 import (line 236-239): `rclpy.parameter`, `nav_msgs.msg.Odometry`,
  `tf2_ros.TransformBroadcaster`
- RigidBody 탐색 (line 357-368): `UsdPhysics.RigidBodyAPI` 기반 자동 탐색
- Camera 부모 Xform 패턴 (line 381-425): `UsdGeom.Xform.Define` 중간 레이어
- OmniGraph (line 440-510):
  - ComputeOdom/PubOdom 노드 제거
  - RPDepth 별도 render product 추가
  - PubTF 토픽 `/tf` → `/tf_raw`
- 초기 포즈 캡처 (line 734-747): `articulation.get_world_poses()` copy
- rclpy 노드 use_sim_time (line 750-760)
- Static TF (line 784-816): base_link → sensor frames
- 수동 odom publisher (line 818-854): TransformBroadcaster + Odometry publisher
- 메인 루프 odom 발행 (line 1007-1079): quat_inverse/multiply/rotate_vec 헬퍼 +
  매 틱 delta 계산

### 주요 설정 변경 (`configs/phase1.yaml`)

- 센서 local_translation 조정:
  - camera: `[0.3, 0.0, -2.1]` (마스트 상단 위)
  - lidar: `[0.3, 0.0, -1.0]` (차체 전방, 바닥 탐지 가능 높이)
  - imu: `[0.0, 0.0, 0.0]` (chassis 중앙)
- camera `local_orientation_rpy_deg: [180.0, 0.0, 0.0]` — 로버 180° X-roll spawn 상쇄

### 교훈 (메모리 저장됨)

- **No speculative fixes**: Isaac Sim OmniGraph 노드의 내부 동작이 불확실하면 우회 구현.
  추측 기반 수정 반복 금지.
- **OmniGraph attribute verify**: 노드 속성 추가 전 Isaac Sim 공식 문서나 Extension Graph
  Editor에서 실제 입력/출력 존재 여부 확인. 미존재 속성 → segfault 패턴.

### 기술 부채

- `run_stage1.py` ~1090줄: 센서 설정, OmniGraph, odom publisher, 제어 루프가 단일
  main()에 인라인. 향후 모듈화 필요 (사용자 요청, 2026-04-17).
- PubTF `/tf_raw` → `/tf` 통합: 충돌 원인(PubTF의 frame naming) 정확히 파악 후 병합 가능.
- rviz2 depth display 노이즈: 데이터는 정상이나 rviz2 시각화 설정 조정 필요.

### Next Steps

- 새 세션에서 rover + scene 통합 진행 (DEM + rocks + rover 스폰)
- 추후 `run_stage1.py` 리팩토링 (모듈화, 최적화)
- SLAM + Nav2 통합 (Wk3~4)
