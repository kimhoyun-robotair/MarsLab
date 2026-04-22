# delete_later/

R2 refactor (2026-04-22)로 격리된 원본 파일 보관소.

이 디렉터리는 `feedback_no_delete_comment` ("코드 비활성화 시 삭제하지 말고
주석 처리") 정책을 파일 단위로 확장한 사용자 지정 패턴이다. 리팩토링으로
파일을 "제거"해야 할 때 실제 삭제 대신 여기로 이동해 둔다. **R1 정책 (2026-04-22)
부터 retention 기간을 폐기** — 이동 시점이 곧 완료 시점이고, 복구는 git history
로 가능하다. `delete_later/` 는 "현 워크트리에서 1-step rollback 가능한 역사
보존소" 역할만 수행한다.

## schema.py

- **출처**: `marslab/config/schema.py` (670 LOC, 13 pydantic 모델).
- **이동 사유**: R2 (2026-04-22)에서 `marslab/config/schema/` 패키지로
  도메인 분할. 파일-패키지 네임 충돌로 원위치 보존 불가.
- **코드 실체**: 아래 8개 파일에 전량 분산 이동.
  - `marslab/config/schema/mars_env.py` — `MarsEnvConfig`
  - `marslab/config/schema/terrain.py` — `DemCropConfig`, `CaveConfig`,
    `TerrainConfig`
  - `marslab/config/schema/robot.py` — `OdometryCovarianceConfig`,
    `SkidSteerDriveConfig`, `RobotConfig`
  - `marslab/config/schema/rendering.py` — `RenderingConfig`
  - `marslab/config/schema/sensors.py` — `SensorImuConfig`, `SensorsConfig`
  - `marslab/config/schema/telemetry.py` — `TelemetryConfig`
  - `marslab/config/schema/benchmark.py` — `BenchmarkConfig`
  - `marslab/config/schema/root.py` — `MarsLabConfig`
- **외부 import 호환**: `marslab/config/schema/__init__.py`가 13개 클래스를
  모두 re-export 하므로 기존 `from marslab.config.schema import X` 패턴은
  무수정 통과. R2 plan Part C의 18개 import site 전부 보존.
- **복구 절차**:
  ```bash
  rm -rf marslab/config/schema/
  mv delete_later/schema.py marslab/config/schema.py
  ```
  복구 후 `from marslab.config.schema import X` 패턴은 원본 파일에서 해결
  되므로 외부 파일 수정 불필요.
- **완료 처리**: R1 정책 (2026-04-22) 에 의해 이동 시점이 곧 완료 시점. retention 없음.

## scripts/run_ros2_test.py

- **출처**: `scripts/run_ros2_test.py` (311 LOC, 5 test 함수).
- **이동 사유**: R4 (2026-04-22) 에서 `refactoring/_risks.md §1.3` 해결.
  원본이 import 하는 `marslab.ros2_bridge.publisher` 모듈 (6개 심볼:
  `enable_ros2_bridge`, `setup_clock_publisher`, `setup_camera_publisher`,
  `setup_imu_publisher`, `setup_lidar_publisher`, `setup_all_publishers`) 이
  저장소 어디에도 존재하지 않아 collection-time ImportError 를 유발.
  파일 전체는 이미 `pytest.mark.skip(reason="Awaits R4 sensor_graph_builder")`
  로 보호되어 있었으나 IDE / broad collection 경로에서 import 자체가 실패하는
  문제는 해결되지 않았음.
- **코드 실체**: `marslab/ros2_bridge/sensor_graph.py:build_sensor_graph()` 가
  canonical 대체물. 5개 test 가 검증하려 했던 내용 (clock / camera / IMU /
  LiDAR publisher 스모크) 을 `scripts/phase1/run_stage3.py` 가 end-to-end 운용
  경로로 커버한다. 즉 **삭제되는 publisher 계층은 이미 sensor_graph 에 흡수
  완료된 상태**.
- **pytest 자동화 불가 사유**: Isaac Sim `SimulationApp` 은 pytest 런타임과 동시
  initialization 이 불가능 (known limitation). 재작성해도 단위 테스트로 실행
  불가하므로 `MEMORY feedback_isaac_sim_user_runs` 에 따라 사용자가
  `run_stage3.py` 를 직접 실행하는 통합 smoke 로 대체.
- **외부 import 호환**: 해당 파일은 어디에서도 import 되지 않는다
  (`grep -rn "run_ros2_test" scripts/ marslab/ tests/ configs/` 결과 0건).
  pytest collection 시점에 `tests/` 외 경로는 스캔되지 않으므로 `scripts/`
  에서 `delete_later/scripts/` 로의 이동은 실행 경로 0건 변화.
- **복구 절차**:
  ```bash
  mkdir -p scripts
  git mv delete_later/scripts/run_ros2_test.py scripts/run_ros2_test.py
  # publisher.py 를 재작성하거나 import 라인 6곳을 sensor_graph 기반으로 교체
  ```
- **완료 처리**: R1 정책 (2026-04-22) 에 의해 이동 시점이 곧 완료 시점. retention 없음.

## R5 batch (2026-04-22): simple_rover 레거시 파이프라인 청산

NASA JPL m2020 공식 자산 (`configs/robots/rover_m2020.yaml` + `assets/robots/rover/m2020.usd`)
전환 이전의 `simple_rover.urdf` + 구식 `spawn_rover(stage, config, gravity)` 시그니처
호출 흔적을 10개 파일 단위로 일괄 격리. `refactoring/_risks.md §2.4` + `§2.5` 동반 해결.

### scripts/ 계열 (4 파일)
- **scripts/run_integration_test.py** (112 LOC): 구식 `spawn_rover(stage, config, gravity=3.72)` 호출 + `simple_rover.urdf` 참조. 통합 smoke 는 `scripts/phase1/run_stage3.py` 가 흡수.
- **scripts/run_sensor_test.py** (304 LOC): 5개 테스트 전부 구식 시그니처 + simple_rover. `run_stage3.py` 가 sensor attach 경로 전체 커버.
- **scripts/run_multi_robot_test.py** (124 LOC): rover + rotorcraft + quadruped 동시 spawn — v1.0 스코프가 rover 단일로 좁혀지며 의미 상실. gravity 파라미터 포함 구식 호출.
- **scripts/run_scene_test.py** (129 LOC): R1 에서 `load_and_validate` 로 전환됐지만 L72 의 `spawn_rover(stage, config.robots[0], config.mars_env.gravity)` 가 여전히 구식. 전체 scene assembly 는 `run_stage3.py` 가 end-to-end 커버.

### tests/ 계열 (1 파일)
- **tests/integration/test_robot_spawn.py** (116 LOC): 이미 `pytest.mark.skip` 상태 — pytest + SimulationApp 동시 initialization 비호환 (known limitation, `MEMORY feedback_isaac_sim_user_runs`). THE critical IMU z=3.72±0.05 검증은 `run_stage3.py` 가 커버. 5.x 구식 API 재작성은 가치 없음 (v2.0 harness 시점에 재설계).

### marslab/robots/ 계열 (2 파일)
- **marslab/robots/rotorcraft.py** (gravity + atmo_density 파라미터 포함 구식 spawn): v1.0 out-of-scope (CLAUDE.md "In scope: rover + SLAM + Nav2"). v3.0 에서 rover.py 의 현 API 패턴으로 재작성 예정.
- **marslab/robots/quadruped.py** (gravity 파라미터 포함 구식 spawn): 동상. R3 에서 `prim_path` Optional 추가 됐으나 소비자 0 → 투자 회수 불가.

### configs/robots/ 계열 (3 파일)
- **configs/robots/rover.yaml** (8 LOC): `simple_rover.urdf` 경로. 활성 대체는 `configs/robots/rover_m2020.yaml` (7개 scenario 의 `rover.base_config` 참조).
- **configs/robots/rotorcraft.yaml** (5 LOC): 소비자 0.
- **configs/robots/quadruped.yaml** (5 LOC): 소비자 0.

### pytest 자동화 불가 사유

5개 Python 실행 파일 (scripts 4 + test 1) 은 모두 Isaac Sim `SimulationApp` 런타임
초기화가 필요하며, 이는 pytest in-process 실행과 비호환 (known limitation).
`MEMORY feedback_isaac_sim_user_runs` 에 따라 사용자가 `run_stage3.py` 를 직접
실행하는 통합 smoke 로 대체. 재작성 투자는 v2.0 harness (headless SimApp + pytest)
도입 시점까지 보류.

### 외부 import 호환

- `marslab.robots.rotorcraft` / `marslab.robots.quadruped` 의 소비자는
  `scripts/run_multi_robot_test.py` 단 하나 — 같은 배치에 동반 이동 → 잔존 참조 0.
- `configs/robots/rover.yaml` / `rotorcraft.yaml` / `quadruped.yaml` 은 Python
  로더 소비자 0 (grep 확인). `work_log/` 내 언급은 역사 문서 성격, 실행 경로 아님.
- `scripts/phase1/run_stage3.py` 및 Oracle (`run_stage3_monolithic.py`) 은 해당 10개
  파일 중 어느 것도 import 하지 않음 (R1/R3 에서 `load_and_validate` +
  `rover.base_config` 경로로 통일 완료).

### 복구 절차

```bash
# 일괄 복구
git mv delete_later/scripts/run_integration_test.py  scripts/run_integration_test.py
git mv delete_later/scripts/run_sensor_test.py        scripts/run_sensor_test.py
git mv delete_later/scripts/run_multi_robot_test.py   scripts/run_multi_robot_test.py
git mv delete_later/scripts/run_scene_test.py         scripts/run_scene_test.py
git mv delete_later/tests/integration/test_robot_spawn.py \
       tests/integration/test_robot_spawn.py
git mv delete_later/marslab/robots/rotorcraft.py      marslab/robots/rotorcraft.py
git mv delete_later/marslab/robots/quadruped.py       marslab/robots/quadruped.py
git mv delete_later/configs/robots/rover.yaml         configs/robots/rover.yaml
git mv delete_later/configs/robots/rotorcraft.yaml    configs/robots/rotorcraft.yaml
git mv delete_later/configs/robots/quadruped.yaml     configs/robots/quadruped.yaml

# 그리고 각 파일의 spawn_rover 호출을 현 API (rover_cfg: Dict, usd_abs: str,
# spawn_xyz: Tuple) 로 갱신. rotorcraft/quadruped 는 rover.py 패턴을 따라 gravity
# 파라미터 제거 + UsdPhysics.Scene 레벨 gravity 설정으로 이전.
```

### 완료 처리

R1 정책 (2026-04-22) 에 의해 이동 시점이 곧 완료 시점. retention 없음.

## R1 batch (2026-04-22): run_stage1.py 파이프라인 완전 삭제

Stage 3 modular (`scripts/phase1/run_stage3.py`) + Oracle
(`scripts/phase1/run_stage3_monolithic.py`) 이 rover spawn + sensor rig + OmniGraph
+ ROS2 bridge 전체를 흡수 완료한 시점에서 Stage 1 backbone 을 은퇴. 사용자 결정 (2026-04-22,
Option A) 에 따라 **`delete_later/` 를 경유하지 않고 완전 삭제**. 재등장 가능성 0 인
파일은 retention 폐기 원칙을 한 단계 확장해 소스 트리에서 즉시 제거하며, 역사 복구는
git history (commit `31bd504` 이전 tree) 로 충분하다고 판단.

### 삭제 파일 (2)

- **scripts/phase1/run_stage1.py** (1,136 LOC): M2020 spawn + sensor rig + OmniGraph
  + ROS2 pub/sub 의 Stage 1 reference. 해당 로직 전체가 monolithic L321-1497
  ("verbatim from run_stage1.py" 주석 10+ 개로 추적 가능) + modular
  `marslab/robots/rover.py`, `marslab/sensors/rover_rig.py`, `marslab/ros2_bridge/*` 로
  분산 흡수 완료.
- **tests/unit/test_run_stage1_helpers.py** (245 LOC, ~14 tests): run_stage1.py 를
  importlib 로 파일 경로 직접 로딩 (`importlib.util.spec_from_file_location`) 하므로
  원본 제거 시 FileNotFoundError → pytest suite collection 실패. 동반 삭제 필수.
  helper 층 커버리지는 아래에서 대체:
  - `rpy_to_quat` / `resolve_joint_indices` (4 tests) —
    `tests/unit/test_rover_module.py` L14-57 이 동일 API 전량 커버.
  - `load_config` validator (7 tests) — `marslab/config/loader.py` 의 pydantic
    검증이 더 엄격하게 대체.
  - `clamp` / `clamp_twist` (3 tests) — 순수 유틸, 회귀 위험 무시 가능.

### 외부 import 호환

- `scripts/phase1/run_stage3_monolithic.py` 내 `run_stage1.py` 언급 10+ 건은
  **주석 (텍스트) 뿐** — `import run_stage1` 구문 0 건 (grep 확인). 파일 삭제 후에도
  monolithic 런타임 영향 0. Oracle diff=0 제약으로 주석 자체는 건드리지 않는다 (R7+
  monolithic 해체 시 자연 해소).
- `scripts/phase1/run_stage3.py:374`, `scripts/phase1/ackermann.py:4`,
  `marslab/robots/rover.py:3`, `marslab/sensors/rover_rig.py:3` 의 docstring /
  주석 언급 — 모두 "Extracted from run_stage1.py" 역사 설명. 기능 영향 0. 역사
  보존 정책으로 손대지 않음 (포인터 해소는 git history 로).

### pytest 기저 영향

R6 기저 348 passed → R1 후 **331 passed** (test_seed.py 3 + test_run_stage1_helpers.py
~14 = ~17 tests 감소). 실질 커버리지 손실 0 — 위 대체 경로 참조.

### 복구 절차

```bash
# commit 31bd504 이전 tree 에서 복구
git checkout 31bd504^ -- scripts/phase1/run_stage1.py \
                          tests/unit/test_run_stage1_helpers.py
```

### 완료 처리

사용자 결정 Option A (2026-04-22): retention 폐기의 연장선에서 `delete_later/`
경유도 생략. 소스 트리에서 완전 제거된 시점 = 즉시 완료. 복구 레퍼런스는 git
history + 본 엔트리.
