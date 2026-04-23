---
title: MarsLab 알려진 이슈 / 리스크 / 기술부채 집약
last_updated: 2026-04-21
scope: wiki/**/*.md 에 이미 기록된 이슈의 재편성 (추측 금지) + T1~T4 감사 기반 추가
status: W6c v2 (T5 Wave 2 append)
---

# MarsLab 알려진 이슈 · 리스크 · 기술부채 — 메타 인덱스

> 본 문서는 W0~W5 위키 작성 과정에서 확인·기록된 이슈를 **카테고리별로 재정렬**한 단일 조회창이다.
> 각 항목은 출처(`wiki/**/*.md` 또는 소스 라인)를 링크로 달아 검증 가능하게 둔다. 새 이슈는
> 여기에 직접 적지 말고 해당 위키 md 에 먼저 기록한 뒤 링크를 옮겨온다(추측 금지 원칙).

---

## 1. Broken / 실행 불가 (3 건)

코드/테스트가 **현재 저장소 상태에서 import 또는 실행 자체가 실패**하는 케이스. 해결하지 않으면
"테스트 전부 초록" 이 원천적으로 불가능하다.

### 1.1 `tests/unit/test_seed.py` — `marslab.utils.seed` 모듈 삭제로 unit suite 전체 collection 중단
- `marslab/utils/__init__.py` 와 `marslab/utils/seed.py` 가 `git status D` (삭제됨) 인데
  `tests/unit/test_seed.py` 가 해당 모듈을 import → **pytest collection error → suite 전체 중단**.
- 출처: [`wiki/tests/unit/README.md`](tests/unit/README.md) §"현재 상태 알림" (L17-20) 및
  동일 문서 플래그 테이블 "BROKEN" 행(L115-116).
- 영향: `pytest tests/unit/` 명령이 다른 테스트까지 수집 전에 중단.
- 권고 조치: `pytest.mark.skip` 가드 또는 파일 삭제
  (`feedback_no_delete_comment` 는 2026-04-23 retired — 현재는 hard-delete 가 기본).
- **RESOLVED (2026-04-22, R1)**: `git rm` 으로 인덱스 포함 완전 제거 (3 파일 —
  `tests/unit/test_seed.py`, `marslab/utils/__init__.py`, `marslab/utils/seed.py`).
  소비자 0 (`grep -rn "marslab\.utils\|utils\.seed" marslab/ scripts/ tests/ configs/`
  결과 0 건). seed 재현성 단일 구현은 `marslab/config/loader.py:36-50`
  `propagate_seeds()` + `tests/unit/test_seed_reproducibility.py` (3 tests, passed).
  delete_later 격리 생략 — 소비자가 없고 재등장 가능성 0 이므로 git history
  복구 경로만 유지.

### 1.2 `tests/integration/test_robot_spawn.py` — stale `spawn_rover` 시그니처로 THE critical test 실행 불가
- 테스트 L55, L95 가 `spawn_rover(stage, config, gravity=3.72)` 형태로 호출하지만,
  현 API 는 `spawn_rover(stage, rover_cfg, usd_abs, spawn_xyz)` (`marslab/robots/rover.py:347`).
  → **3번째 positional 인자 누락 + 존재하지 않는 `gravity` 키워드 → `TypeError`**.
- 출처: [`wiki/tests/integration/test_robot_spawn.md`](tests/integration/test_robot_spawn.md)
  §8.1 "spawn_rover 시그니처 미스매치 (CRITICAL)" (L101-124).
- 영향: IMU z축 = 3.72 ± 0.05 m/s² 를 검증하는 **THE critical integration test** 실행 불가
  (CLAUDE.md "Integration Tests" §"Robot spawn").
- 권고 조치: 위 위키 §10 의 옵션 A (테스트를 새 API 에 맞춰 고침) 또는 옵션 C (skip + TODO)
  중 사용자 승인 후 택일.
- **RESOLVED (2026-04-22, R6)**: 파일이 R5 (2026-04-22) 에서
  `delete_later/tests/integration/test_robot_spawn.py` 로 격리. stale `spawn_rover`
  시그니처 (`gravity=3.72` 키워드) 는 `delete_later/` 내부에 보존되며 live 경로에서
  제거. THE critical IMU z=3.72±0.05 검증은 `scripts/phase1/run_stage3.py` 실행이
  커버 (`MEMORY feedback_isaac_sim_user_runs`). 완료 처리됨 (R1 정책, 2026-04-22 —
  retention 폐기). 근거: `delete_later/README.md` §R5 batch.

### 1.3 `scripts/run_ros2_test.py` — 존재하지 않는 `marslab.ros2_bridge.publisher` 6회 import, ImportError 확정
- `from marslab.ros2_bridge.publisher import ...` 가 L56, L65, L102, L155, L195, L274 6곳에서
  호출되지만, `marslab/ros2_bridge/` 에 `publisher.py` 파일이 **존재하지 않는다**. 패키지 `__init__.py`
  에서도 재노출되지 않음.
- 출처:
  - [`wiki/scripts/run_ros2_test.md`](scripts/run_ros2_test.md) §"⚠ 상태: BROKEN" (L3-5) 및
    §8 "BROKEN — 6 개 import 라인" (L74-80).
  - [`wiki/marslab/ros2_bridge/__init__.md`](marslab/ros2_bridge/__init__.md)
    §5 "주의" 블록 (L159) 및 §8.2 #1 "깨진 역의존성" (L197-201).
- 영향: TEST 1~5 (bridge-enable / clock / camera / IMU / LiDAR publisher 스모크) 전체 실행 불가.
- 권고 조치: 옵션 A(run_stage3 가 ROS2 검증 겸), 옵션 B(현 API 로 재작성) 중 사용자 결정 필요.
  해당 wiki §10 참조.
- **RESOLVED (2026-04-22, R4)**: `scripts/run_ros2_test.py` 를
  `delete_later/scripts/run_ros2_test.py` 로 격리하여 collection-time ImportError
  경로를 제거. publisher 계층은 `marslab/ros2_bridge/sensor_graph.py:build_sensor_graph()`
  가 canonical 대체물이며 `run_stage3.py` 실행이 통합 smoke 를 커버. 완료 처리됨
  (R1 정책, 2026-04-22 — retention 폐기). 근거: `delete_later/README.md`
  §scripts/run_ros2_test.py.

### 새 이슈 (T1~T4 감사 기반, 2026-04-21 추가)

**§1-N1. T2 Critical 재확인 — `scripts/run_ros2_test.py` → `marslab.ros2_bridge.publisher` (교차참조)**
- T2 감사(`_reverse_deps_audit.md` §3.1, §4.3) 가 독립 grep 및 `ls marslab/ros2_bridge/` 로 `publisher.py` 부재를 재확인.
  6 사이트 (`run_ros2_test.py:{56, 65, 102, 155, 195, 274}`) 의 심볼(`enable_ros2_bridge`,
  `setup_clock_publisher`, `setup_camera_publisher`, `setup_imu_publisher`,
  `setup_lidar_publisher`, `setup_all_publishers`) 이 어디에서도 resolve 되지 않음을 확인.
- 기존 §1.3 과 **동일 이슈** 이며 RESOLVED 가 아님. T2 파이프라인 smoke test 의 통과 케이스로 기록만 갱신.
- 출처 추가: [`_reverse_deps_audit.md`](_reverse_deps_audit.md) §3.1 (L80-94), §4.3 (L187-196).
- 교차참조: §1.3, §2.1(중복 로직), §7.1 본 문서 §13-N1.
- **RESOLVED (2026-04-22, R4)**: §1.3 동반 해결. 동일 이슈 교차참조 종결.

---

## 2. 데드 코드 / 의심 데드 참조 (8 건)

**현재 저장소 어떤 호출자도 사용하지 않거나, 참조처가 존재하지 않는 파일·설정을 가리키는** 항목.
`feedback_no_delete_comment` 정책은 2026-04-23 retired — 현재는 hard-delete 가 기본이며 rollback 은 `git log -p` 로 수행.

### 2.1 `marslab/ros2_bridge/topic_config.py` — import 0 건의 48-LOC 모듈
- `grep -rn "from marslab.ros2_bridge.topic_config\|import.*topic_config" marslab scripts tests launch`
  결과 **1 건도 없음**. 동일 포맷 `f"/{ns}/{name}"` 가 `ros2_bridge/__init__.py:52-53` 과
  `sensor_graph.py:32-33` 에 **3 중 재구현**된 상태이고, 의도된 통합 지점이었던 `topic_config`
  만 남아 생성 후 방치.
- 출처: [`wiki/marslab/ros2_bridge/topic_config.md`](marslab/ros2_bridge/topic_config.md)
  §5 (L36-49), §8 "데드코드 가능성 HIGH" (L66-71).
- 권고: 사용자 승인 하에 파일 주석화 또는 살려서 `__init__`/`sensor_graph` 의 `_ns_topic` 을 흡수.

### 2.2 `marslab/utils/{__init__,seed}.py` — git status `D`, 삭제 상태
- 현 작업트리에서 삭제되었고, `tests/unit/test_seed.py` 만 의존처로 남아 broken (→ §1.1).
- 출처: [`wiki/tests/unit/README.md`](tests/unit/README.md) §"카테고리별 테이블 / seed" (L84-88),
  현재 대화 git status (`D marslab/utils/__init__.py`, `D marslab/utils/seed.py`).
- **RESOLVED (2026-04-22, R1)**: `git rm` 으로 3 파일 인덱스 제거 확정. §1.1 동반 해소.
  소비자 검증: `grep -rn "marslab\.utils" marslab/ scripts/ tests/` 결과 0 건.

### 2.3 `marslab/gui/__init__.py` — 빈 파일 (0 LOC)
- `marslab.gui` 패키지에 `atmosphere_panel.py` 만 있고 `__init__.py` 는 심볼 재노출 없는 빈 파일.
- 출처: [`wiki/marslab/gui/README.md`](marslab/gui/README.md),
  [`wiki/marslab/gui/atmosphere_panel.md`](marslab/gui/atmosphere_panel.md).

### 2.4 `assets/robots/rover/simple_rover.urdf` — 다수 참조 vs 디스크 부재 → `configs/robots/rover.yaml` 비기능
- `mars_env.yaml:74`, `robots/rover.yaml:6`, `terrain/jezero_crater.yaml:45` 가 참조하지만 실제
  파일은 `m2020.usd` 만 존재. 레거시 simple_rover 경로 전체가 데드 레퍼런스.
- 출처: [`wiki/configs/README.md`](configs/README.md) §6 이슈표 #2 (L86).
- **RESOLVED (2026-04-22, R5)**: `simple_rover.urdf` 경로를 참조하던
  `configs/mars_env.yaml:98` (사용자 직접 삭제, L94-157 robots 블록 제거),
  `configs/robots/rover.yaml:6` (delete_later),
  `configs/terrain/jezero_crater.yaml:45` (R5 범위 외 — robots 블록 사용자 판단 대기)
  세 지점을 동시 해소. 활성 rover 설정은 `configs/robots/rover_m2020.yaml`
  (`configs/scenarios/*.yaml` 의 `rover.base_config` 참조) 로 통일. 완료 처리됨
  (R1 정책, 2026-04-22 — retention 폐기). 근거: `delete_later/README.md` §R5 batch.

### 2.5 `configs/robots/{quadruped,rotorcraft}.yaml` — 소비자 0
- `mars_env.yaml:119-125` 에서 rotorcraft/quadruped 스폰이 주석 처리. 개별 robot YAML 은 살아
  있지만 아무도 로드하지 않음. 모순적으로 `configs/terrain/jezero_crater.yaml:47-52` 에는 여전히
  스폰 대상으로 열거되어 "dead URDF 참조" 를 트리거.
- 출처: [`wiki/configs/README.md`](configs/README.md) §6 이슈표 #3, #4 (L87-88).
- **RESOLVED (2026-04-22, R5)**: `configs/robots/rotorcraft.yaml`,
  `configs/robots/quadruped.yaml`, `marslab/robots/rotorcraft.py`,
  `marslab/robots/quadruped.py` 를 `delete_later/` 로 격리. 유일 소비자였던
  `scripts/run_multi_robot_test.py` 도 동반 격리. v1.0 스코프 (rover 단일) 와 부합.
  v3.0 (rotorcraft/quadruped 재도입) 시 `marslab/robots/rover.py` 의 현 API 패턴
  (`rover_cfg: Dict`, `usd_abs: str`, `spawn_xyz: Tuple`) 을 따라 재작성.
  근거: `delete_later/README.md` §R5 batch.

### 2.6 `configs/sensors/*.yaml` — `mount_link: base_link` 가 m2020 현실(Body_Chassis 루트) 과 불일치
- NASA m2020 URDF 에는 `base_link` 이 **없고** articulation 루트는 `Body_Chassis`
  (configs/README.md §7 용어집, [`wiki/configs/README.md`](configs/README.md) L100).
- Sensor YAML 이 `mount_link: base_link` 로 지정되면 m2020 환경에서는 실질 attach 실패 후보.
- 출처: [`wiki/configs/README.md`](configs/README.md) §7 용어집 (L100), 그리고 관련 센서
  부착 문서 [`wiki/marslab/sensors/rover_rig.md`](marslab/sensors/rover_rig.md).

### 2.7 `configs/terrain/procedural_*.yaml` 3 개 — Python 소비자 0
- `configs/terrain/` 의 procedural YAML 3 개가 "단독 사용은 사실상 없음 (scenarios 블록에서 인라인)"
  으로 명시됨.
- 출처: [`wiki/configs/README.md`](configs/README.md) §2 매트릭스 `terrain/*.yaml` 행 (L34).

### 2.8 `scripts/tools/generate_instruction_index.py:187` — 존재하지 않는 `generate_instruction_skeleton.py` 안내
- 재실행 가이드 줄이 `python3 scripts/tools/generate_instruction_skeleton.py` 를 안내하지만
  `scripts/tools/` 에는 `generate_instruction_index.py` 1 개만 존재 → **깨진 링크**.
- 출처: [`wiki/scripts/tools/generate_instruction_index.md`](scripts/tools/generate_instruction_index.md)
  §8 "의심 1 — Dead reference" (L74).

---

## 3. G5 (하드코딩) 위반 (8 건)

CLAUDE.md "G5: All Configs in YAML. Zero hardcoded constants in Python source." 에 대한 위반.
엄격/관대 해석에 따라 판단이 갈리는 케이스는 비고로 명시.

### 3.1 `marslab/rendering/render_settings.py:45-46` — RTX AA/DLSS 매직 넘버
- L45 `/rtx/post/aa/op = 3`, L46 `/rtx/post/dlss/execMode = 1`. 또한 L33·L43-44 의
  denoiser `True` 고정도 YAML 무경유.
- 출처: [`wiki/marslab/rendering/render_settings.md`](marslab/rendering/render_settings.md)
  §8 "하드코딩(G5 위반)" (L95).
- **RESOLVED (2026-04-22, R6)**: R3 (2026-04-22) 시점에 `RenderingConfig` 에
  `antialiasing_op`, `dlss_exec_mode`, `denoiser_indirect_diffuse`, `denoiser_reflections`,
  `denoiser_optix_pathtracing` 5 필드 추가 + `render_settings.py:54-55` consumer
  migration 완료. `scripts/phase1/run_stage3.py:240` 및 Oracle
  `scripts/phase1/run_stage3_monolithic.py:537-538` 에서 `set_render_mode(render_config)`
  호출로 YAML 기반 전환. 문서 태깅 누락만 R6 에서 해소.

### 3.2 `marslab/rendering/atmosphere_fog.py` — 고도 폴오프/밀도/색 계수 5 종 리터럴
- L37 `fogEnabled=True`, L43 `HeightDensity = density * 0.5`, L45 `ColorAmount=1.0`,
  L46 `StartHeight=0.0`, L47 `HeightFalloff=0.01`.
- 출처: [`wiki/marslab/rendering/atmosphere_fog.md`](marslab/rendering/atmosphere_fog.md)
  §3 "G5 관점" (L33), §8 하드코딩 행 (L92).
- **RESOLVED (2026-04-22, R6)**: R3 에서 `RenderingConfig.fog_enabled`,
  `fog_color_amount`, `fog_start_height`, `fog_height_falloff`, `fog_height_density_ratio`,
  `fog_density_scale` 6 필드 추가 + `atmosphere_fog.py:37-50` consumer migration 완료.
  `configure_atmosphere_fog(stage, tau, render_config)` 시그니처로 modular + monolithic
  모두 YAML 경로 수렴. 문서 태깅 누락만 R6 에서 해소.

### 3.3 `marslab/rendering/sun_renderer.py:32`, `sky_renderer.py:34` — prim path 리터럴
- `sun_renderer.py:32,L76` 의 `/World/SunLight`, `sky_renderer.py:34,L73` 의 `/World/DomeLight` 가
  Python 상수로 고정. 다중 라이트/scenario 별 분기 불가.
- 출처:
  - [`wiki/marslab/rendering/sun_renderer.md`](marslab/rendering/sun_renderer.md) §8
    "경로 하드코딩" (L97).
  - [`wiki/marslab/rendering/sky_renderer.md`](marslab/rendering/sky_renderer.md) §8
    "경로 하드코딩" (L96).
- **RESOLVED (2026-04-22, R6)**: R3 에서 `RenderingConfig.sun_prim_path` (default
  "/World/SunLight"), `dome_prim_path` (default "/World/DomeLight") 필드 추가 +
  `sun_renderer.py:32,76` / `sky_renderer.py:34,73` consumer migration 완료. 4개
  엔트리 함수 (`configure_sun_light`, `update_sun_light`, `configure_sky_dome`,
  `update_sky_dome`) 모두 `rendering_config: RenderingConfig` 수신. 문서 태깅 누락만
  R6 에서 해소.

### 3.4 `marslab/robots/quadruped.py:47` — prim path `/World/quadruped` 하드코딩
- 단일 인스턴스 전용. `config.name` 기반 파생 필요.
- 출처: [`wiki/marslab/robots/quadruped.md`](marslab/robots/quadruped.md) §8.2 #2-3
  (L170-171).
- **RESOLVED (2026-04-22, R6)**: `marslab/robots/quadruped.py` 파일 자체가 R5
  (2026-04-22) 에서 `delete_later/marslab/robots/quadruped.py` 로 격리 (§2.5 RESOLVED
  참조). v1.0 스코프 (rover 단일) 에서 quadruped 가 제외되어 `/World/quadruped` prim
  path 하드코딩 이슈는 자동 해소. v3.0 재도입 시 `rover.py` 의 현 API 패턴을 따라
  `config.name` 기반 파생 규칙으로 재작성 예정. 근거: `delete_later/README.md`
  §R5 batch.

### 3.5 `marslab/ros2_bridge/odometry_publisher.py:45-47` — `frame_id="odom"`, `child_frame_id="base_link"`, `queue_size=10`
- 함수 인자 default 로 존재하고 `init_rclpy_side` 가 override 없이 default 를 쓴다. SLAM YAML
  (`configs/slam/slam_toolbox_async.yaml`) 과 Nav2 YAML(`configs/nav2/nav2_params.yaml`) 이 독립적으로
  같은 프레임 이름을 하드코드 → drift 리스크.
- 출처: [`wiki/marslab/ros2_bridge/odometry_publisher.md`](marslab/ros2_bridge/odometry_publisher.md)
  §3.4 표 (L52-57) 및 §3.4 "의심" 단락 (L58).
- **PARTIAL RESOLVED (2026-04-22, R6)**: R3 에서 `SkidSteerDriveConfig.odom_publisher`
  submodel 추가 + `marslab/ros2_bridge/__init__.py:105-120` `init_rclpy_side()` 에서
  YAML override 전달 경로 확립. modular `scripts/phase1/run_stage3.py:438-443` 는 이
  경로를 경유 → YAML 기반 완료. 함수 default (`queue_size=10`, `frame_id="odom"`,
  `child_frame_id="base_link"`) 는 호환성 안전장치로 보존. **Oracle
  `run_stage3_monolithic.py:1212-1214` 는 `create_odometry_publisher()` 를 호출하지
  않고 `node.create_publisher(Odometry, ..., 10)` 로 수동 구현**. Oracle diff=0 제약
  으로 monolithic 내 하드코딩 제거는 R6 범위 외 (R7+ 또는 v2.0 harness 도입 시점
  재검토).

### 3.6 통합 테스트 스크립트 전반 — URDF 경로/스폰 위치 하드코딩
- `scripts/run_ros2_test.py` 가 sensor yaml 경로, topic 문자열, step count(10/30/60),
  tolerance(0.10) 모두 인라인. 같은 지적이 run_sensor_test.py / run_integration_test.py 에도
  확산될 가능성.
- 출처: [`wiki/scripts/run_ros2_test.md`](scripts/run_ros2_test.md) §8 "🟡 G5 위반 다수" (L78).
- **RESOLVED (2026-04-22, R6)**: `scripts/run_ros2_test.py` 는 R4 (2026-04-22) 에서
  `delete_later/scripts/run_test.py` 로 격리. 확산 우려됐던 `run_sensor_test.py`,
  `run_integration_test.py` 등 4 스크립트도 R5 (2026-04-22) 에서 `delete_later/scripts/`
  일괄 이동. 해당 파일들의 sensor yaml 경로 / topic 문자열 / step count / tolerance
  리터럴은 `delete_later/` 내부에 보존되며 live 경로에서 제거. 통합 smoke 는
  `scripts/phase1/run_stage3.py` end-to-end 실행이 흡수. 근거: `delete_later/README.md`
  §scripts/run_ros2_test.py 및 §R5 batch.

### 3.7 `scripts/visualize_atmosphere.py` — `solar_constant=589`, `zenith=45°`, τ 범위 리터럴
- L27 `solar_constant=589.0`, L28 `zenith=45°`, L29 `np.linspace(0.05, 4.0, 100)`, L97 출력 경로,
  DPI 150 등 전부 인라인.
- 출처: [`wiki/scripts/visualize_atmosphere.md`](scripts/visualize_atmosphere.md) §8 "G5" (L48).
- **RESOLVED (2026-04-22, R6)**: R1 (2026-04-22) 에서 `load_and_validate` 단일
  진입점 전환 후, R3 의 소비자 migration 일환으로 `visualize_atmosphere.py:35` 가
  `load_and_validate("configs/mars_env.yaml")` 로 `solar_constant_mean=589`,
  `sun_elevation_deg=45`, `dust_opacity_range=[0.5, 2.0]` 3개 physics 상수 모두
  YAML 경유. `_PLOT_TAU_MIN=0.05`, `_PLOT_TAU_SAMPLES=100`, DPI=150 은 plotting
  anchor (physics 아님 — 파일 L25-27 주석에 명시) 로 G5 범위 외. 문서 태깅 누락만
  R6 에서 해소.

### 3.8 `scripts/visualize_dynamic_atmosphere.py:87` — sol 길이 24.66h 리터럴, `mars_env.yaml:sol_duration=88642` 과 0.04h 편차
- `hours = t * 24.66` 리터럴. `sol_duration / 3600 ≈ 24.623 h` 와 수식적으로 불일치.
- 출처: [`wiki/scripts/visualize_dynamic_atmosphere.md`](scripts/visualize_dynamic_atmosphere.md)
  §3 Panel 1 주석(L13), §8 "24.66h vs 24.623h" (L57).
- **RESOLVED (2026-04-22, R6)**: `visualize_dynamic_atmosphere.py:44` 는 R3 동반
  수정에서 `sol_hours = cfg.mars_env.sol_duration_seconds / 3600.0` 로 리터럴
  제거 완료 (파일 L38-41 이력 주석 참조). 남아있던 같은 주제의 잔재
  `marslab/gui/atmosphere_panel.py:149` 의 `hours = t * 24.66` 는 R6 Part A 에서
  `hours = t * (sol_duration_seconds / 3600.0)` + `atmosphere_state` dict fallback
  88642.0 으로 교체 (GUI 전용, 24 sol 누적 시 ~16분 drift 제거). modular 호출자
  `scripts/phase1/run_stage2.py:400-408` 의 `atmosphere_state` 에 `sol_duration_seconds`
  키 추가로 YAML 경유 경로 확립 (monolithic 은 Oracle 제약으로 fallback 88642.0 사용).

---

## 4. 스키마 / 검증 공백 (3 건)

pydantic 스키마에 블록이 존재하지 않거나 존재하지만 소비자가 없는 상태. 런타임에서 `dict.get()` 으로
우회 파싱되어 오타 검증이 불가한 "깜깜이" 설정.

### 4.1 `mars_env.yaml.dynamic_atmosphere` — 스키마 미존재, `run_stage3_monolithic.py:545` dict 직접 파싱
- `mars_env.yaml:18-35` 및 7 개 scenario YAML 에 공통으로 존재하지만 `MarsEnvConfig`
  (`schema.py:12-61`) 에 필드 없음 → extra=ignore 로 조용히 버려짐.
- 출처: [`wiki/configs/README.md`](configs/README.md) §4 "우회 사례" 첫 항목 (L68),
  §6 이슈표 #1 (L85).

### 4.2 `telemetry` / `benchmark` 블록 — 스키마에는 있으나 소비자 0 건 (데드 스키마)
- `schema.py:627` 의 `TelemetryConfig` / `json_sink_path` 는 `grep telemetry marslab/` 결과
  schema 자체 외 0 건.
- 출처: [`wiki/configs/README.md`](configs/README.md) §6 이슈표 #7 (L91).

### 4.3 `configs/robots/rover_m2020.yaml:81-85` `lidar_2d` 블록 — Stage 3 전용 잔재, 스키마 미검증
- `phase1.yaml` 에는 존재하지 않는 블록이 rover_m2020 에만 남아있음. W4 보고대로 rollback 잔재.
- 출처: [`wiki/configs/README.md`](configs/README.md) §6 이슈표 #5 (L89).

---

## 5. Seed / 재현성 (2 건)

G7 ("seed-based reproducibility") 위반 후보. 동일 seed → 동일 출력 보장이 깨질 경로.

### 5.1 `run_stage1.py` / `run_stage3_monolithic.py` — 자체 `load_config` 재정의, `propagate_seeds` 미호출
- `scripts/phase1/run_stage1.py:L39-L87` 가 `load_config` 를 **자체 재정의**하고,
  `run_stage3_monolithic.py` 는 `marslab.config.loader` 를 아예 import 하지 않음 →
  `terrain.seed = master + 1` 파생 규칙이 두 스크립트에서 적용되지 않음. `terrain.seed ==
  mars_env.seed` 가 되어 독립성 보장 깨짐.
- 출처:
  - [`wiki/marslab/config/loader.md`](marslab/config/loader.md) §5 "결정적 비사용처" (L100-104),
    §8 이슈 1 (L128-135).
  - [`wiki/scripts/phase1/run_stage1.md`](scripts/phase1/run_stage1.md) §2 `load_config` 행
    (L9), Note: `Instruction/고치거나구현해야하는.md` #1 과 연결.
- **PARTIAL RESOLVED (2026-04-22, R1, Option A)**: `run_stage1.py` +
  `tests/unit/test_run_stage1_helpers.py` 를 **완전 삭제** (delete_later 미경유 —
  재등장 가능성 0 인 파일은 retention 폐기의 연장선에서 소스 트리에서 즉시 제거).
  자체 `load_config` 재정의 + `propagate_seeds` 미호출 경로는 git history (commit
  `31bd504` 이전 tree) 로만 참조 가능. `run_stage3_monolithic.py` 분
  (`marslab.config.loader` 미사용 + `propagate_seeds` 미호출) 은 Oracle diff=0 제약으로
  보존 (R7+ 또는 v2.0 harness 도입 시 재검토). 근거: `delete_later/README.md` §R1 batch.

### 5.2 `mars_env.yaml` 의 `seed: 42` 3 중 중복 선언
- `schema.py:L46/280/652` 가 각기 `Field(default=42, ge=0)` 로 선언 → `mars_env.seed`,
  `terrain.seed`, `benchmark.seed` 가 파일에서 동일값 42 로 표시될 수 있음. `loader.py` 의
  `propagate_seeds` 가 덮어쓰지만 **propagate 를 호출하지 않는 경로** (§5.1) 에서는 그대로 노출.
- 출처: [`wiki/marslab/config/loader.md`](marslab/config/loader.md) §3.2 (L47-59) 및
  §8 "G5 하드코딩 스캔" 반주 (L150-154).

---

## 6. Lidar2D 롤백 잔재 (3 건)

LOG 2026-04-17 에서 2D LaserScan 지원을 추가했다 즉시 롤백. `marslab/sensors/lidar_2d.py` 는
삭제되었으나 참조가 몇 군데 남아있음.

### 6.1 `scripts/phase1/run_stage3_monolithic.py:777-791, 885-903, 1183-1184` — 잔재 경로
- lidar_2d 관련 분기/토픽/publisher 코드가 monolithic 스크립트에 남아있음.
- 출처: [`wiki/scripts/phase1/run_stage3_monolithic.md`](scripts/phase1/run_stage3_monolithic.md)
  (해당 라인 섹션), 그리고 [`wiki/configs/README.md`](configs/README.md) §6 이슈표 #5 (L89).

### 6.2 `configs/robots/rover_m2020.yaml:81-85` — `lidar_2d` 블록 잔재
- §4.3 과 동일 항목. 여기서는 "Lidar2D 롤백" 맥락에서 재기재.
- 출처: [`wiki/configs/README.md`](configs/README.md) §6 이슈표 #5 (L89).

### 6.3 `marslab/ros2_bridge/sensor_graph.py` 일부 — 흔적 가능성 (확인 필요)
- 현재 위키 `sensor_graph.md` 에서 lidar_3d 노드는 명시되어 있지만 2D 관련 OmniGraph 잔재 여부는
  **확인 필요** (wiki/CLAUDE.md 원칙에 따라 추측하지 않고 flag 만 남김).
- 출처: [`wiki/marslab/ros2_bridge/sensor_graph.md`](marslab/ros2_bridge/sensor_graph.md) —
  소비자 쪽 확인 필요.

---

## 7. 문서-코드 불일치 (3 건)

`PLAN.md` / `wiki/PLAN.md` / 각 모듈 docstring 과 **실제 구현 간 드리프트**.

### 7.1 `PLAN.md:439` `spawn_quadruped -> None` vs 실제 구현 `-> str`
- 설계 시점에 반환값이 `None` 이었으나 `marslab/robots/quadruped.py:17-61` 가 `/World/quadruped`
  문자열을 반환하도록 구현됨.
- 출처: [`wiki/marslab/robots/quadruped.md`](marslab/robots/quadruped.md) §5 역의존성 표의
  `PLAN.md L439` 행 (L105), §8.2 #1 "PLAN.md vs 구현 시그니처 불일치" (L169).

### 7.2 `wiki/PLAN.md` "terrain=11 파일" vs 실측 10 — 카운트 드리프트
- `wiki/marslab/terrain/` 글롭 실측 파일 수는 `wiki/tests/unit/README.md` 카테고리 표(terrain 7개 테스트 대상) 및
  `wiki/marslab/terrain/README.md` 파일 목록으로 산출된 10 에 수렴. LOC 집계는 W1c 검증치 사용.
- 출처: [`wiki/marslab/terrain/README.md`](marslab/terrain/README.md) 파일 표(실측),
  [`wiki/PLAN.md`](PLAN.md).

### 7.3 `marslab/sensors/__init__.py` docstring vs 실제 dispatcher 로직 미세 차이
- docstring 은 `type` 필드만 언급하지만 실제로는 `data.get("sensor", data)` 로 두 YAML 스키마
  (sensor 블록 O/X) 를 모두 허용하는 폴백이 존재. docstring 에 이 fallback 이 명시돼 있지 않음.
- 출처: [`wiki/marslab/sensors/__init__.md`](marslab/sensors/__init__.md) §3 "line 47" 설명
  (L43-45).

### 새 이슈 (T1~T4 감사 기반, 2026-04-21 추가)

**§7-N1. T1 orphan — `wiki/tests/unit/test_sun_position.py.md` 확장자 중복 오류 (고아 md)**
- `tests/unit/test_sun_position.py` 를 이중으로 참조하는 md 가 2개 (`test_sun_position.md` 1006 B
  정상, `test_sun_position.py.md` 378 B 중복). 후자는 확장자 명명 규칙(`foo.py` → `foo.md`,
  `.py.md` 금지) 위반으로 고아. 다른 subagent 가 파일명 규칙을 혼동해 생성한 것으로 추정.
- 출처: [`_structure_audit.md`](_structure_audit.md) §3 (L66-71), §5.5 (L165-171), §6.2 (L186-190).
- 권고: `_delete_ok.md` (T6) 에 삭제 후보로 기재됨. 본 문서에서는 드리프트로 플래그만 유지.

**§7-N2. T2 Medium — `terrain/dem_loader.md §5` 역의존성 2건 누락 (lazy import 미기재)**
- `scripts/phase1/run_stage2.py:120` 및 `scripts/phase1/run_stage3_monolithic.py:198` 이
  `from marslab.terrain.dem_loader import crop_dem, load_converted_dem` 를 지연 import 하지만
  wiki 역의존성 표에 누락. 독자는 Stage2/3 이 elevation_loader 경유 간접 호출이라 오인 가능
  (실제로는 dem_loader 직접 소비, elevation_loader 는 `run_stage3.py` 전용).
- 출처: [`_reverse_deps_audit.md`](_reverse_deps_audit.md) §3.2 #1 (L98-109), §4.1 (L129-158),
  §5.2 M1 (L210-216).
- 권고: [`marslab/terrain/dem_loader.md`](marslab/terrain/dem_loader.md) §5 테이블에 두 줄 추가 +
  §3 에 "Stage2/Stage3_monolithic 이 elevation_loader 미경유로 dem_loader 직접 소비" 한 문장 보강.

**§7-N3. T2 Medium — `config/schema.md §5` 역의존성 1건 누락 (`visualize_scenario.py:34`)**
- `scripts/visualize_scenario.py:34` 가 `from marslab.config.schema import MarsLabConfig, TerrainConfig`
  를 직접 import 하지만 `config/schema.md §5` "스크립트" 블록에 미기재. 인근 파일은 모두 열거.
- 출처: [`_reverse_deps_audit.md`](_reverse_deps_audit.md) §3.2 #2 (L111-119), §4.2 (L160-186),
  §5.2 M2 (L218-223).
- 권고: [`marslab/config/schema.md`](marslab/config/schema.md) §5 스크립트 블록에 한 줄 추가.

**§7-N4. T4 고빈도 드리프트 후보 — `scripts/phase1/run_stage3.md` (4 건 "확인 필요")**
- 2.1-#10 (scene-only `/clock` 지원 부재), 2.1-#11 (propagate_seeds 계약),
  2.1-#19 (`rover_m2020.yaml` lidar_2d 잔재), 2.3-#10 (`_cave_data` mutation) 가 한 파일에 집중.
  런타임 계약·잔재·외부 로봇 지원 모두에 걸쳐 불확실성이 누적.
- 출처: [`_open_question.md`](_open_question.md) §3 상위 10개 (L397), §2.1 #10~#11/#19,
  §2.3 #10 (L67-105).
- 권고: Stage3 파이프라인 전체 재검토 다음 웨이브 지정 권고.

**§7-N5. T4 고빈도 드리프트 후보 — `scripts/blender_generate_rocks.md` (4 건 "확인 필요")**
- 2.2-#9 (Blender ≥ 2.9x 정확 버전), 2.2-#10 (rock_instancer 소비 확인),
  2.3-#15 (bpy seed 재현성), 2.5-#13 (`os.remove` feedback_no_delete_comment 정책 충돌).
- 출처: [`_open_question.md`](_open_question.md) §3 (L398), §2.2/§2.3/§2.5 관련 항목.
- 권고: Blender 파이프라인 1회 실행 + 결과 재측정 후 md 보강.

**§7-N6. T4 고빈도 드리프트 후보 — `scripts/phase1/run_stage3_monolithic.md` (3 건 "확인 필요")**
- 2.1-#12 (propagate_seeds), 2.3-#11 (resolve_spawn_pose 좌표 기준 모호),
  2.4-#23 (`rover_m2020.yaml` lidar_2d 섹션 잔존). §8.1 monolithic 1500-LOC 이슈와 연동.
- 출처: [`_open_question.md`](_open_question.md) §3 (L401).

**§7-N7. T4 고빈도 드리프트 후보 — `scripts/phase1/run_stage2.md` (3 건 "확인 필요")**
- 2.1-#8 (유닛 테스트 유무), 2.1-#9 (`tau_profile_name` 매핑 dict 부재),
  2.3-#9 (`atmosphere_state` 스레드 안전성). τ 동적 변동 로직 소재지 불명이 핵심.
- 출처: [`_open_question.md`](_open_question.md) §3 (L402).

**§7-N8. T4 고빈도 드리프트 후보 — `marslab/gui/atmosphere_panel.md` (3 건 "확인 필요")**
- 2.3-#1 (omni.ui 스레딩 모델), 2.4-#1 (`hours = t * 24.66` 리터럴 하드코딩; §3.8 과 동일 주제),
  2.4-#2 (`atmosphere_state` 스키마 암묵화).
- 출처: [`_open_question.md`](_open_question.md) §3 (L404).

**§7-N9. T4 고빈도 드리프트 후보 — `scripts/visualize_atmosphere.md` (3 건 "확인 필요")**
- 2.4-#20, 2.4-#21 (`total = direct / (1 - diffuse_frac)` 수식 COMIMART 출처 미확인),
  2.5-#12 (HDRI 디렉터리 fallback 분기 동작 불명).
- 출처: [`_open_question.md`](_open_question.md) §3 (L400).

> 나머지 T4 항목 (≤2 건 파일, 총 50+ 개 md) 은 본 §7 로 승격하지 않고
> [`_open_question.md`](_open_question.md) §2 에서 카테고리별로 추적. 해소 시 같은 위치에
> `RESOLVED (YYYY-MM-DD)` 태그 추가.

---

## 8. 아키텍처 관찰 / 리팩터 후보 (4 건)

즉시 "버그" 는 아니지만 P1 / P2 / P3 원칙 혹은 모듈러 성장 관점에서 주의할 구조적 부채.

### 8.1 monolithic 1500-LOC `main()` — P3 offline-first 불가능
- `scripts/phase1/run_stage3_monolithic.py` 의 `main()` 이 L259-L1497 (≈1240 LOC). Isaac Sim boot
  포함 전 구간이 한 함수 안에 있음 → 오프라인 테스트 불가.
- 출처: [`wiki/scripts/phase1/run_stage3_monolithic.md`](scripts/phase1/run_stage3_monolithic.md)
  §2 퍼블릭 인터페이스 (L15), §1 one-liner 에서 `monolithic_before_modular` 정책 참조.

### 8.2 Config loader 3 중화 — 통합 필요
- `scripts/phase1/run_stage1.py` 자체 `load_config`, `scripts/phase1/run_stage3_monolithic.py`
  `marslab.config.loader` 미사용, `scripts/phase1/run_stage2.py` 별도 로더. 공통 검증 파이프
  없음.
- 출처: [`wiki/marslab/config/loader.md`](marslab/config/loader.md) §5 "결정적 비사용처"
  (L100-104), §8 이슈 1 (L128-135).
- **PARTIAL RESOLVED (2026-04-22, R1, Option A)**: `run_stage1.py` 자체 `load_config`
  지분은 R1 완전 삭제 (delete_later 미경유) 로 해소. `run_stage3_monolithic.py` 분은
  Oracle 제약으로 보존. `run_stage2.py` 별도 로더는 R1 이후 재검토 대상 (R7+).
  근거: `delete_later/README.md` §R1 batch.

### 8.3 `_ns_topic` 3 중 재구현 — `__init__.py`, `sensor_graph.py`, `topic_config.py`
- §2.1 데드코드 항목과 동일 원인. 동일 공식 `f"/{ns}/{name}"` 가 세 군데.
- 출처: [`wiki/marslab/ros2_bridge/__init__.md`](marslab/ros2_bridge/__init__.md) §3.2
  "`_ns_topic` 의 역할과 중복" (L99-100), [`wiki/marslab/ros2_bridge/topic_config.md`](marslab/ros2_bridge/topic_config.md)
  §8 근거 2 (L68).

### 8.4 센서 attach 경로 2 중화
- `marslab/sensors/{camera,lidar,imu}.attach_*` 와 `marslab/sensors/rover_rig.attach_rover_sensor_rig`
  가 비슷한 책임을 가짐. 전자는 per-sensor 단독, 후자는 rover rig 번들. 소비자가 경로 선택을
  해야 해 의도 불명료.
- 출처: [`wiki/marslab/sensors/__init__.md`](marslab/sensors/__init__.md) §5 역의존성 (L72-80),
  [`wiki/marslab/sensors/rover_rig.md`](marslab/sensors/rover_rig.md).

---

## 9. 우선순위 권고

**이 섹션은 수정 주체가 아닌 우선순위만 제안한다.** 실제 수정은 각 담당 에이전트·사용자 승인이 필요.

| 시점 | 대상 | 근거 |
|-----|-----|-----|
| **즉시 (blocker)** | — (§1.1/§1.2 RESOLVED R1/R6) | CI/CD 및 THE critical test 복구 완료. |
| **Wk6 내** | §5.1 partial RESOLVED (R1) — monolithic 잔존분 R7+ | §1.3/§2.4/§2.5 RESOLVED R4/R5. v1.0 MUST 기능의 재현성·ROS2 스모크 정상화. |
| **Wk6 ~ 논문 작성 중** | §6.* (Lidar2D 잔재), §3.* (G5 하드코딩) 선택적 | 실험 재현성 / 코드 형상 청결도. 논문 제출 전 정리 권장. |
| **v2.0 이관** | §8.* (아키텍처 리팩터) | Phase 1 "flat P0" 원칙(P1) 존중. premature abstraction 금지. |

---

## 10. 유지 규약 (문서 관리)

1. **새 이슈 추가 절차**: 먼저 해당 wiki md (모듈 문서) 의 §8 "구현 상태 / 의심 영역" 에 기록한
   뒤 본 문서로 링크를 이동한다. 본 문서에 이슈의 "원본 정의" 를 두지 않는다.
2. **출처 없는 항목 금지**: 모든 항목은 `wiki/**/*.md` 의 해당 섹션 혹은 소스 파일 라인을 인용.
   추측(wiki/CLAUDE.md 원칙) 은 §"확인 필요" 서브불릿으로만 남긴다.
3. **해결 시 처리**: 이슈가 해결되면 항목을 삭제하지 말고 "RESOLVED" 태그 + 해결 커밋/리포트 링크를
   남긴다 (MEMORY `feedback_no_delete_comment` 와 동일 정신).
4. **재편성**: 분기별 1 회, W6 단위(메타 위키 주기) 로 카테고리 재정렬 검토.

---

## 11. 카테고리별 이슈 수 요약

| 카테고리 | 기존 (v1) | 신규 (T1~T4) | 합계 (v2) |
|---------|----------|--------------|----------|
| §1. Broken / 실행 불가 | 3 | 1 (교차참조) | 4 |
| §2. 데드 코드 / 의심 데드 참조 | 8 | 0 | 8 |
| §3. G5 (하드코딩) 위반 | 8 | 0 | 8 |
| §4. 스키마 / 검증 공백 | 3 | 0 | 3 |
| §5. Seed / 재현성 | 2 | 0 | 2 |
| §6. Lidar2D 롤백 잔재 | 3 | 0 | 3 |
| §7. 문서-코드 불일치 | 3 | 9 | 12 |
| §8. 아키텍처 관찰 / 리팩터 후보 | 4 | 0 | 4 |
| §12. 문서화 공백 (신설) | — | 3 | 3 |
| §13. 위키 내부 링크 무결성 (신설) | — | 2 | 2 |
| **합계** | **34** | **15** | **49** |

> v1 블로커: 0 건. §1.1 RESOLVED (2026-04-22, R1, `git rm` 확정 — utils/seed.py +
> test_seed.py 3 파일 영구 제거), §1.2 RESOLVED (2026-04-22, R6 via R5 delete_later 격리).
> Wk6 내 조치 대상: §5.1 PARTIAL RESOLVED (2026-04-22, R1 Option A, run_stage1.py +
> test_run_stage1_helpers.py 완전 삭제 — monolithic 잔존분 R7+ 대기).
> §8.2 PARTIAL RESOLVED (R1 Option A). §1.3 RESOLVED R4.
> §2.4/§2.5 RESOLVED R5. §3.1/§3.2/§3.3/§3.4/§3.6/§3.7/§3.8 RESOLVED (2026-04-22, R6).
> §3.5 partial RESOLVED R6 (modular 완료, monolithic Oracle 제약으로 R7+ 대기).
> v2 추가 (T1~T4): 비차단 트래킹 대상 15건. 이 중 §7-N2/N3 Medium 과 §13-N1 (wiki 링크) 은
> 다음 Edit 웨이브에서 해소 가능.

---

## 12. 문서화 공백 (신설, T1 기반, 3 건)

T1 구조 감사(`_structure_audit.md`)에서 발견된, **소스는 존재하나 wiki README/__init__ 흡수 대체물이
없어 실질 누락** 인 항목. 미러링 원칙(wiki/CLAUDE.md "구조 1:1 미러") 대비 공백.

### 12.1 `wiki/marslab/README.md` 부재 — 패키지 전체 안내 없음
- `marslab/__init__.py` 가 1 LOC 이고 `wiki/marslab/` 하위에 `README.md` 또는 `__init__.md`
  어느 것도 없음. 9개 서브모듈(config, environment, gui, rendering, robots, ros2_bridge, sensors,
  terrain) 에 대한 패키지 레벨 안내가 상위 `wiki/README.md` 에만 존재.
- 출처: [`_structure_audit.md`](_structure_audit.md) §2 #1 (L50), §5.1 플래그 1행 (L116),
  §6.1 P1 권고 (L181).
- 권고: `wiki/marslab/README.md` 신규 작성 (9개 서브모듈 아키텍처 요약).

### 12.2 `wiki/tests/integration/README.md` 부재 — 통합 테스트 전략 안내 없음
- `tests/integration/__init__.py` 가 0 LOC 이고 `wiki/tests/integration/README.md` 도 없음.
  통합 테스트 전략(Isaac Sim 의존, 수동 실행 기준, MEMORY `feedback_isaac_sim_user_runs`) 을
  안내할 진입점 부재.
- 출처: [`_structure_audit.md`](_structure_audit.md) §2 #7 (L56), §5.1 플래그 3행 (L127),
  §6.1 P2 권고 (L182).
- 권고: `wiki/tests/integration/README.md` 신규 작성.

### 12.3 `wiki/marslab/sensors/README.md` 부재 — 다른 서브모듈과 패턴 불일치
- `marslab/sensors/__init__.py` 가 56 LOC 의 실 디스패치 로직을 보유 (`__init__.md` 는 존재).
  다만 같은 디렉터리에 README 가 없어 다른 marslab 서브디렉터리(config/env/rendering/terrain/
  ros2_bridge) 패턴과 불일치.
- 출처: [`_structure_audit.md`](_structure_audit.md) §5.1 플래그 2행 (L123),
  §6.1 P3 권고 (L183).
- 권고: 기능상 블로커 아님. 일관성 차원에서 후순위.

> 참고 — 본 §12 에 올리지 않은 T1 항목:
> `marslab/{config,environment,gui,robots,rendering,terrain}/__init__.py` 및
> `scripts/phase1/__init__.py`, `tests/__init__.py`, `tests/unit/__init__.py` 는 모두
> 대응 `README.md` 가 있어 **README 흡수로 허용**. T1 §2 테이블 판정 그대로 유지.

---

## 13. 위키 내부 링크 무결성 (신설, T3 기반, 2 건 / 10 링크)

T3 링크 감사(`_links_audit.md`)에서 발견된 **깨진 상대 링크 10건** (202 링크 중 5.0%).
모두 한 패턴 (`.py.md` 접미사 오기) 으로 수렴하고 `wiki/marslab/rendering/` 하위 2개 md 에 집중.

### 13.1 `wiki/marslab/rendering/README.md` — `.py.md` 접미사 9건
- L16-20 (표 형식 파일 목록 5건), L188-191 (본문 내 참조 4건) 에서 `render_settings.py.md`,
  `atmosphere_fog.py.md`, `sun_renderer.py.md`, `sky_renderer.py.md`, `__init__.py.md` 로 기재.
  실제 위키 파일은 `.md` 접미사만 사용 (wiki/CLAUDE.md 규칙: `foo.py` → `foo.md`, `.py.md` 금지).
- 출처: [`_links_audit.md`](_links_audit.md) §2 테이블 #1-9 (L25-33), §4 패턴 분석 (L53),
  §5.1 P1 (L60-67), §5.4 (L81).
- 권고: 정규식 치환 `./X.py.md` → `./X.md` 일괄 적용. 단, §3 에서 "의도된 미구현" 으로 분류된
  3 링크(`schema.py.md`, `sky_dome.py.md`, `sun_position.py.md`) 는 대상 md 미생성 상태이므로
  단순 치환만으로는 해결 불가 — W2a/W1a 착수 시 재정리.

### 13.2 `wiki/marslab/rendering/atmosphere_fog.md:99` — `.py.md` 접미사 1건
- L99 의 `./render_settings.py.md` 링크가 동일 패턴 오기.
- 출처: [`_links_audit.md`](_links_audit.md) §2 테이블 #10 (L34), §5.4 (L82).
- 권고: 위 §13.1 과 함께 일괄 치환.

**파생 권고 — 명명 규칙 문서화:**
- `wiki/CLAUDE.md` 또는 `wiki/README.md` 템플릿 섹션에 "소스 `foo.py` 의 위키는 `foo.md`
  (`.py.md` 금지)" 한 줄 명시.
- 출처: [`_links_audit.md`](_links_audit.md) §5.2 (L69-72).
