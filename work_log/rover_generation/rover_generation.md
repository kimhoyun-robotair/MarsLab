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

- 사용자 통합 테스트: teleop → cmd_vel → 로버 이동 확인 + drive_damping 튜닝
- Mars gravity (3.72) 전환 → IMU z축 검증 (3.72 ± 0.05 m/s²)
- Scenario 1 (Basic Mars): DEM 지형 + 암석 배치 위에 로버 스폰
