# MarsLab S01/S03 변경 보고서

## 목적과 범위

이 문서는 기준 커밋 `22fe45f9146e63e929ceb7163da9458aa0c98f7a`부터 S03 후보
커밋 `91abd42dda5712711ee0f0b711316c94c7185e6f`까지의 실제 Git 변경을
S01/S02/S03별로 기록한다. 범위는 S01(외부 MarsLab-Utils 의존성 제거),
S02(공급된 Scene USDZ/Rover 입력을 기준으로 한 문서·설정·주석 정리),
S03(Scenario/Rover 생산 스키마의 단일 strict 경계와 런타임 소비자 전환)이다.
S04 이후 작업이나 `.omo` 내부 구현은 제품 변경으로 세지 않는다. 기준·후보와
단계 부모는 `git`으로 재확인했으며, S03은 S04로 진행하지 않는다.

## 커밋 목록과 단계 경계

| 단계 | 커밋(시간순) | 내용 |
|---|---|---|
| S01 | `8f08606f78a43128ef14d3b78dc63f7d133291a4` | MarsLab-Utils/GT/trajectory 런타임 의존성 제거, 사전검사·검증 도구와 테스트 추가 |
| S01 | `360226dbbf169937b9f33e31e28da1b0f52840b3` | S01 Python 범위 포맷 정리(`marslab/main.py`) |
| S02 | `a48868a0f02a74b3e643e1d9ebc93a9705819739` | 공급 Scene USDZ/Rover 입력에 맞춘 문서·설정·공개 API 주석 정리 |
| S02 | `01e1e0e27596c213b44a919288adf25f43b09425` | README 로컬 링크가 추적 파일인지 검증하는 테스트 강화 |
| S02 | `f4053621844b212372f8c72f17a844e22b404a07` | 문서 명령의 입력 파일이 실제로 공급되는지 구별하는 테스트 보강 |
| S02 | `0358d0a6d12041483b3d2cb3dcc96c9b2093bdd7` | S01/S02 보고서 검증 범위와 Git 근거 정리 |
| S03 | `91abd42dda5712711ee0f0b711316c94c7185e6f` | 생산 Scenario/Rover strict Pydantic 스키마, 독립 YAML 로더, 런타임 소비자 전환 및 거부 테스트 |

S03 후보의 부모는 `0358d0a6d12041483b3d2cb3dcc96c9b2093bdd7`이며, 후보의
제목은 `refactor(config): enforce production scenario and rover schemas`이다.
S01/S02의 승인된 내용은 그대로 상속하고, S03 후보 이후 이 문서의 rename/content
커밋만 추가한다.

## S01 변경(코드, 도구, 테스트)

### 코드·런타임

| 파일(현재 위치) | 현재 심볼/구간 | 변경 내용(삭제된 구 동작 포함) |
|---|---|---|
| `configs/rover_m2020.yaml` | `spawn` 주석·블록, 현재 22–33행 | `trajectory_start`, `trajectory_path`, `use_yaw_from_trajectory` 예시와 절대 Utils 경로를 삭제했다. `dem_center`, `dem_relative`, `absolute`만 문서화한다. URDF 변환 플래그 4개(구 110행 부근)는 삭제했고, S05 전환 때문에 `usd_path` 12행은 아직 유지한다. |
| `marslab/main.py` | `_REMOVED_SPAWN_MODE`, `_load_rover_cfg` 92–116행 | 제거된 `trajectory_start` 요청을 Kit 부팅 전에 명시적인 `RuntimeError`로 거부한다. |
| `marslab/main.py` | `_resolve_spawn_rpy` 119–125행, `_resolve_spawn` 212–275행 | TUM 첫 pose 파서 `_parse_tum_first_pose`와 `math` import, 궤적 기반 좌표·yaw 오버라이드를 삭제했다. 세 가지 spawn 모드만 허용하고 오류 메시지도 갱신했다. |
| `marslab/main.py` | `_reference_user_usda` 319–327행, `main` 427–447행·594행·619행 | USDA 외부 terrain 표현을 공급 Scene 입력 표현으로 바꾸고, `--usda` 호환 플래그로 Scene USDZ를 받는 설명을 반영했다. 중첩 `PhysicsScene` 비활성화 동작은 유지한다. |
| `marslab/main.py` | `main`의 ROS 초기화·LoopContext 구간 700–745행 | `MarsLab-Utils/GT/gt_publisher` 선택 import/fallback과 `attach_to_bridge`/`register_physics_callback`를 삭제했다. 현재 735–745행의 bridge/LoopContext 경계 주변에는 MarsLab 소유 GT 경로만 남긴다. |
| `marslab/main.py` | `_nearest_k_median_z` 159–187행, `main` 427행 이후 | S01 포맷 커밋에서 행 길이와 다중 인자 호출을 Black 형식으로 정리했다(행동 변화 없음). |
| `marslab/runtime/precheck.py` | `check_rover_usd` 14–26행 | 누락 Rover USD 오류에서 변환 스크립트를 실행하라는 Utils 안내를 삭제하고 파일 경로만 보고한다. |
| `marslab/runtime/atmosphere_boot.py` | 모듈 설명 5–11행, `boot_atmosphere` 104–113행 | 외부 USDA/Utils 설명을 공급 Scene USDZ 설명으로 교체했다. 순수 atmosphere 계산과 terrain 미로드 정책은 유지한다. |
| `marslab/config/schema/root.py` | `MarsLabConfig` docstring 36–47행 | terrain/scene authoring이 내부에서 수행되지 않고 공급 Scene을 소비한다는 설명으로 갱신했다. 모델 필드/`extra="forbid"` 동작은 그대로다. |
| `marslab/ros2_bridge/tf_nameoverrides.py` | 모듈 주석 14–26행, `apply_nameoverride` docstring 70–78행 | `<Isaac-Sim-install>` 파일 인용을 제거하고 공개 Isaac Sim robot schema/API 설명으로 대체했다. 함수 동작(커스텀 `isaac:nameOverride`)은 유지했다. |

### 새 도구·테스트

| 파일(현재 위치) | 현재 심볼/구간 | 역할 |
|---|---|---|
| `scripts/verify_refactor_ledger.py` | `ValidationReport` 38–48행, `validate` 88–164행, CLI 167–185행 | 계획 단계 수, manifest/ledger 순서, SHA-256 증거, 승인 문자열과 다음 단계 자격을 검증하고 `APPROVE`/`REJECT`와 JSON을 출력한다. |
| `tests/refactor/test_no_utils_dependencies.py` | 24–100행의 5개 테스트 | S01 CLI 세 플래그, Rover USD 경로, 제거된 trajectory의 사전-Kit 실패, 금지 문자열 및 변환 모듈 import 부재를 검증한다. 테스트 안의 문자열은 제거 동작을 고정하기 위한 fixture이며 제품 의존성이 아니다. |
| `tests/refactor/test_verify_refactor_ledger.py` | `_write_fixture` 13–36행, 두 테스트 63–88행 | 유효한 승인 ledger는 통과하고 변조된 증거 hash는 거부되는지 검증한다. |

## S02 변경(문서·주석·테스트)

S02는 기존 파일을 삭제하지 않고 stale truth를 정리했다. S01과 겹치는 파일은
아래에 `S01 연속`으로 표시한다.

| 파일(현재 위치) | 현재 심볼/섹션(라인) | 변경 내용 및 분류 |
|---|---|---|
| `AGENTS.md` | Conventions 58–66행, Commands 82–94행 | **프로젝트 문서**: 외부 terrain USDA를 공급 Scene USDZ 입력으로 바꾸고 현재 `--usda` 호환 실행 예를 추가했다. |
| `README.md` | 서문 6–24행, Quick Start 31–57행, CLI/예제 71–128행 | **제품 문서**: MarsLab-Utils 생성 절차·변환 명령·개인 checkout 경로·궤적 spawn 예를 제거하고 Scene USDZ, scenario YAML, Rover USD/URDF 입력과 실행 명령을 명시했다. |
| `README.md` | Scene/Rover Inputs 152–168행 | **제품 문서**: 네 개 참조 Scene, Rover bundle, companion URDF와 중첩 PhysicsScene 정책을 설명했다. |
| `README.md` | Architecture 367–387행, License/Assets 391–403행, Roadmap 419–425행, Tests 448–474행 | **제품 문서**: authoring/변환이 런타임 밖임을 명시하고 자산 권리 주장을 유보했으며 공급 Scene 기준 테스트 명령과 `AGENTS.md` 링크만 남겼다. 기존 `docs/colored_pointcloud.md`, `CLAUDE*`, `work_log` 링크는 삭제했다(파일 삭제가 아니라 README 링크 삭제). |
| `configs/default.yaml` | 파일 주석 4–12행 | **설정 주석**: terrain/scene 블록 부재 사유와 공급 Scene USDZ `--usda` 예를 갱신했다. |
| `configs/rover_m2020.yaml` | `spawn` 22–33행 및 S01 연속 | **설정 주석**: trajectory/절대 Utils 경로와 변환 플래그를 제거했다. 실제 `usd_path`는 S05 전까지 유지한다. |
| `marslab/config/loader.py` | `propagate_seeds_in_dict` docstring 10–30행 | **코드 주석**: “USDA-external passthrough”를 “supplied-scene passthrough”로 바꿨다. |
| `marslab/config/schema/robot.py` | `DepthSensorConfig` docstring 524–542행 | **코드 주석**: Isaac 설치 내부 파일 경로 인용을 공개 single-view depth schema/API 설명으로 대체했다. |
| `marslab/config/schema/root.py` | `MarsLabConfig` docstring 36–47행, S01 연속 | **코드 주석**: 공급 Scene USDZ 표현을 반영했다. |
| `marslab/config/schema/ros2_bridge.py` | `Ros2BridgeConfig` 설명 172–250행 | **코드 주석**: ROS2 camera helper의 개인 Isaac 설치 경로·라인 인용을 공개 API 설명으로 바꿨다. QoS/필드 동작은 바꾸지 않았다. |
| `marslab/isaac_python.sh` | 배경 설명 22–29행, Usage 42–47행 | **런처 주석**: `<Isaac-Sim-install>` 인용을 `$ISAAC_SIM_PATH`로 바꾸고 실제 Scene USDZ·scenario·rover 실행 예를 적었다. 셸 동작은 변경하지 않았다. |
| `marslab/main.py` | 모듈/CLI 설명 1–30행·427–447행, S01 연속 구간 | **코드+주석**: USDA terrain 문구를 Scene USDZ로 정리하고 S01 포맷 변경을 포함했다. |
| `marslab/ros2_bridge/sensor_graph.py` | `build_sensor_graph` 설명 138–145행, `_DEPTH_SENSOR_SCHEMA_ATTRS` 224–233행 | **코드 주석**: depth sensor의 개인 schema 경로 인용을 공개 API/속성명 설명으로 바꿨다. graph wiring은 유지했다. |
| `marslab/ros2_bridge/sensor_graph_builder.py` | 모듈 설명 1–16행, `_build_create_nodes` 47–79행, `_build_set_values` 228–369행 | **코드 주석**: 개인 Isaac 설치 경로·OGN 내부 파일 인용과 `resetSimulationTimeOnStop` 근거 주석을 제거하고 공개 ROS2 helper 설명을 남겼다. 노드/값 연결은 유지했다. |
| `marslab/ros2_bridge/tf_nameoverrides.py` | 모듈/`apply_nameoverride` 설명 14–26·70–78행, S01 연속 | **코드 주석**: 공개 API 근거로 정리했다. |
| `marslab/runtime/atmosphere_boot.py` | 모듈 설명 5–11행, `boot_atmosphere` 104–113행, 계산부 177–179행 | **코드 주석+포맷**: 공급 Scene USDZ 표현으로 갱신하고 한 줄 `os.path.join`을 포맷했다. 계산 결과는 동일하다. |
| `marslab/runtime/precheck.py` | `check_rover_usd` 14–26행, S01 연속 | **코드 주석/메시지**: 변환 명령 안내 없는 간결한 오류로 정리했다. |
| `marslab/sim/AGENTS.md` | Notes 30–33행 | **중첩 가이드 문서**: 상위 startup이 공급 Scene USDZ를 참조한다는 설명으로 바꿨다. |
| `tests/refactor/test_documented_commands.py` | 상수 10–28행, 테스트 36–123행 | **새 테스트**: README/설정 대상 존재, 세 외부 runtime 입력 문자열, 추적된 Markdown 링크, `--usda` allowlist, 개인/Utils 경로 부재 및 음성 missing-target fixture를 검증한다. `01e1e0e`에서 링크 추적 검사를 강화했고 `f405362`에서 외부 입력을 명시적으로 구분했다. |

## 삭제 파일과 새 파일(S01/S02)

삭제 여부는 추측하지 않고 다음 명령의 Git 결과로 판단했다.

```bash
git diff --diff-filter=D --name-only \
  22fe45f9146e63e929ceb7163da9458aa0c98f7a \
  0358d0a6d12041483b3d2cb3dcc96c9b2093bdd7
```

출력은 **없음(0개)** 이다. 따라서 S01/S02에서 삭제된 파일은 없다. README에서
링크나 코드 블록이 없어진 것과 파일 삭제는 구별한다.

후보 범위에서 새로 추가된 파일은 다음 네 개이며 모두 현재 추적 파일이다.

| 파일 | 단계 | 종류 |
|---|---|---|
| `scripts/verify_refactor_ledger.py` | S01 | 검증 도구(코드) |
| `tests/refactor/test_no_utils_dependencies.py` | S01 | 회귀/의존성 테스트 |
| `tests/refactor/test_verify_refactor_ledger.py` | S01 | ledger 무결성 테스트 |
| `tests/refactor/test_documented_commands.py` | S02 | 문서·입력 경로 테스트 |

## S01/S02 테스트와 증거(상속 보존)

S02 후보에서 실행한 검증은 다음과 같다.

```text
python3 -m pytest tests/refactor/test_no_utils_dependencies.py \
  tests/refactor/test_documented_commands.py \
  tests/refactor/test_verify_refactor_ledger.py -q
결과: 14 passed in 0.59s, exit 0
```

실행 원문은
`.omo/evidence/marslab-reference-runtime-refactor/agent/task-2/change-report/refactor-tests.txt`
에 기록했다. 보고서 생성 전 필수 경로 부재 확인은
`baseline-absent.txt`에 있으며 `test -e ... && test -s ...`의 반환 코드는 1이다.
S03 후보의 경로/라인·Git 표 검증과 수동 출력은 이 문서 rename 작업의
`agent/task-3/change-report/` 증거에 저장한다. `.omo` 파일은 제품 변경이 아니라
증거 메모다.

Isaac Sim/ROS2가 필요한 실제 GUI·physics·topic 실행은 S01/S02 CPU 검증에서
수행하지 않았다. 이는 코드 변경의 성공을 주장하는 항목이 아니라 런타임 확인이
남아 있던 검증 한계다. S01/S02 ledger에는 사용자 명령과 승인 `APPROVE S01`,
`APPROVE S02`가 별도로 기록되어 있다.

## S01/S02 작업 트리와 변경 영향(상속 보존)

보고서 생성 전부터 다음 사용자 소유 dirty/untracked 파일이 있었고 건드리지
않았다: `.gitignore`(수정), `MARSLAB_STALE_RESIDUE_AUDIT.md`, `MarsLab.pdf`,
`MarsLab_refactoring.md`, `package-lock.json`(미추적). 이 파일들은
`22fe45f..0358d0a` 제품 diff에 포함되지 않는다.

S01/S02 행동 영향은 (1) runtime이 MarsLab-Utils/외부 `gt_publisher`/TUM
trajectory에 의존하지 않음, (2) S01에서 제거된 `trajectory_start`가 Kit 전에
실패함, (3) Scene은 공급 USDZ를 사용하고 terrain authoring은 수행하지 않음,
(4) S02 당시 Rover YAML의 `usd_path`는 S05 전환까지 유지하도록 의도되었다는
것이다. S03에서 schema 경계가 이 필드를 제거했지만, S05 전환 전 실제 asset은
아래 `_PRE_S05_ROVER_USD_PATH` bounded adapter로만 보존한다. ROS TF, sensor
graph, QoS 및 atmosphere 계산의 실행 로직은 S02에서 바꾸지 않고 근거 주석만
공개 API 기준으로 정리했다.

### 레거시 `--usda` 상태(상속 보존)

`--usda`는 **삭제되지 않았다**. 현재 `marslab/main.py`의 parser,
`marslab/isaac_python.sh` 및 README/config 문서에서 pre-S06 호환 alias로
유지한다. 의미는 구 USDA terrain이 아니라 공급 Scene USDZ 경로이며, S06에서
canonical `--scene`이 추가될 때까지 이 호환 상태를 유지한다.

### S01/S02 선행·환경 검증 이슈(상속 보존)

* S02 당시 `python` 명령 자체가 없어 `python -m pytest`는 exit 127이었고,
  동일 명령을 `python3`로 재실행해 14개 테스트가 통과했다.
* Isaac Sim 5.x, GPU, ROS2 daemon이 필요한 GUI/physics/topic 검증은 S01/S02에서
  재현하지 않았다. 이는 파일 삭제나 테스트 실패가 아니다.
* README의 요구사항에는 Python 3.12+가 남아 있다(패키지 런타임 floor를 3.11로
  맞추는 S07 범위). S02에서 이를 임의로 바꾸지 않았다.

## S03 변경(런타임/스키마, 설정, 테스트)

S03 후보 `91abd42`는 부모 `0358d0a` 대비 **30개 경로(새 8, 수정 22, 삭제 0)**를
변경했다. 아래 라인 범위는 후보 현재 파일의 `nl -ba`로 확인한 범위이며, 표의
구분은 Git `--diff-filter` 결과와 일치한다. 스키마/로더와 런타임 소비자 변경을
테스트·증거·문서 변경과 분리한다.

### S03 새 파일 — Git `A` 8개

| 파일 | 현재 심볼/정확한 라인 범위 | 성격과 결과 |
|---|---|---|
| `marslab/config/schema/common.py` | `StrictConfigModel` 6–13; scalar/vector aliases 15–22 | `extra="forbid"`, `frozen=True`, `strict=True`, finite 숫자·벡터 공통 기반을 단일화한다. |
| `marslab/config/schema/rover.py` | `SpawnConfig` 19–24; `ChassisConfig` 26–31; `WheelsConfig` 33–46; `SuspensionConfig` 48–51; `ControlConfig` 53–76; `WheelOdometryConfig` 78–114; `RoverConfig` 116–131; exports 133–141 | Rover 루트와 물리·제어·spawn·odometry를 strict typed 모델로 정의하며 cross-field validator가 마찰/휠 뱅크를 확인한다. |
| `marslab/config/schema/rover_ros2.py` | `RosTopicsConfig` 13–27; `RosRatesConfig` 29–39; `OdomPublisherConfig` 41–47; `QoSProfileConfig` 49–54; `Ros2BridgeConfig` 56–83; exports 85 | ROS topic/rate/odom/QoS 설정의 생산 모델이다. |
| `marslab/config/schema/rover_sensors.py` | `DisabledSensorConfig` 17–19; `DepthSensorConfig` 21–36; enabled camera/LiDAR/IMU 38–89; discriminated aliases 91–106; `SensorsConfig` 109–115; exports 117–129 | enabled 센서는 부모·범위·profile을 요구하고 disabled variant는 acquisition 필드를 생략할 수 있다. |
| `marslab/config/schema/scenario.py` | atmosphere leaves 16–46; `MarsEnvConfig` 48–57; fog/path/sky/rendering 59–108; `RenderingConfig.check_colors` 110–114; `ScenarioConfig` 116–120; exports 122–127 | Scenario 환경·렌더링·동적 atmosphere를 strict immutable 모델로 만든다. |
| `tests/refactor/test_config_rejections.py` | helpers 10–30; rejection tests 32–108; typed/frozen tests 111–149 | NaN/Inf, unknown key, 벡터/물리 범위, 제거 필드, enabled parent, raw dict 누수, disabled variant, frozen 모델을 15개 테스트로 고정한다. |
| `tests/refactor/test_rover_schema.py` | `test_canonical_rover_is_typed_and_paths_anchor_to_declaring_yaml` 9–25 | canonical Rover typed 값과 선언 YAML 기준 절대 URDF 경로를 확인한다. |
| `tests/refactor/test_scenario_schema.py` | `test_canonical_scenario_is_typed_and_paths_anchor_to_declaring_yaml` 8–21 | canonical Scenario typed 값과 선언 YAML 기준 절대 HDRI 경로를 확인한다. |

### S03 수정 파일 — Git `M` 22개

| 파일 | 현재 심볼/정확한 라인 범위 | 변경 성격 |
|---|---|---|
| `configs/default.yaml` | `mars_env` 15–32; `rendering` 34–47 | legacy atmosphere 중복 필드 제거, `rendering.path_tracing` 중첩, 선언 YAML 기준 HDRI 경로로 정리한다. |
| `configs/rover_m2020.yaml` | root/spawn 1–30; chassis/wheels/suspension 41–89; ros2 90–151; sensors 153–256; control 257–304; wheel odometry 305–315 | `usd_path`·중복 문서 필드·lidar 해상도/alias를 제거하고 enabled 센서와 canonical schema 필드를 명시한다. |
| `marslab/config/__init__.py` | public imports 1–10 | `RoverConfig`/`ScenarioConfig`와 두 독립 loader를 공개한다. |
| `marslab/config/loader.py` | exports 1–3 | raw seed propagation을 제거하고 loader compatibility export만 남긴다. |
| `marslab/config/schema/__init__.py` | imports 1–36; aliases 38–40; `__all__` 42–74 | 새 rover/scenario 모듈을 aggregate하고 `MarsLabConfig`/`RobotConfig`/`SkidSteerDriveConfig` API 별칭만 유지한다. |
| `marslab/config/schema/mars_env.py` | exports 1–17 | Scenario 모듈로 이동한 환경 모델의 import/export compatibility를 유지한다. |
| `marslab/config/schema/rendering.py` | exports 1–15 | Scenario 모듈로 이동한 렌더링 모델의 import/export compatibility를 유지한다. |
| `marslab/config/schema/robot.py` | compatibility aliases 1–34 | 대형 legacy Robot schema를 제거하고 Rover 모델 별칭만 제공한다. |
| `marslab/config/schema/root.py` | `MarsLabConfig` alias 1–5 | ScenarioConfig을 root legacy 이름으로 재수출한다. |
| `marslab/config/schema/ros2_bridge.py` | exports 1–3 | Rover ROS2 모델의 legacy import 경로를 유지한다. |
| `marslab/config/yaml_loader.py` | `_read_mapping` 12–18; path helpers 20–29; `load_scenario_config` 31–41; `load_rover_config` 43–59; exports 61 | YAML은 이 단일 경계에서만 읽고, 선언 파일 기준 경로를 anchor한 뒤 즉시 typed model로 parse한다. deep merge/base_config/raw dict 누수는 없다. |
| `marslab/main.py` | constants 88–91; `_load_rover_cfg` 99–101; `_resolve_spawn_rpy` 104–108; `_resolve_spawn` 194–257; `main` 407–796 | typed config를 받아 검증된 `model_dump` compatibility projection으로 기존 Isaac 소비자를 전환한다. `_PRE_S05_ROVER_USD_PATH` 90행은 S05까지의 단일 bounded adapter다. |
| `marslab/robots/drive_api_setup.py` | `resolve_joint_indices` 32–46; `configure_drives` 85–148; `reinforce_pd_gains` 150–193 | 제거된 raw/default lookup 대신 validated control projection을 사용한다. |
| `marslab/robots/rover.py` | `SpawnedRover` 38–50; spawn/physics helpers 53–550; `spawn_rover` 552–622 | Rover typed 물리·spawn 값을 소비하고 직접 접근/재검증 경계를 유지한다. |
| `marslab/ros2_bridge/qos.py` | `to_rclpy_qos` 74–121; `to_omnigraph_qos_json` 123–181 | QoS 모델을 검증된 값으로 변환하며 deferred rclpy import를 유지한다. |
| `marslab/ros2_bridge/rclpy_integration.py` | `init_rclpy_side` 32–241; `_resolve_qos_bundle` 243–269 | typed ROS2 설정을 호환 dict로 변환해 publisher 초기화에 공급한다. |
| `marslab/ros2_bridge/sensor_graph.py` | `SensorGraphHandle` 55–59; options 62–88; `build_sensor_graph` 90–218; depth attrs 220–286; QoS 288–301 | validated sensor/ROS options를 그래프에 연결하고 legacy lidar fallback을 제거한다. |
| `marslab/runtime/atmosphere_boot.py` | `AtmosphereInit` 39–75; `AtmosphereBootResult` 77–101; `boot_atmosphere` 103–196 | raw config 대신 `ScenarioConfig`/`MarsEnvConfig`/`RenderingConfig`를 사용하고 atmosphere를 한 번 계산한다. |
| `marslab/runtime/loop_context.py` | `build_loop_context` 33–158 | control 값의 `.get(default)`를 제거하고 validated projection의 필수 키를 사용한다. |
| `marslab/runtime/sensor_frames.py` | bindings 32–38; `_resolve_sensor_block` 40–45; frame builders 47–111 | `lidar` legacy alias fallback을 제거하고 canonical blocks만 사용한다. |
| `marslab/sensors/sensor_spawner.py` | profile resolver 142–165; `SensorHandles` 331–425; `spawn_sensors` 427–640 | `profile`/`lidar` aliases를 제거하고 `profile_name`/`lidar_3d` canonical config만 소비한다. |
| `tests/refactor/test_no_utils_dependencies.py` | constants 13–22; tests 25–102 | S01 compatibility test를 `RoverConfig`와 `_PRE_S05_ROVER_USD_PATH`에 맞추고 trajectory failure를 `ValidationError`로 고정한다. |

### S03 삭제 파일 — Git `D` 0개

| Git 확인 명령 | 결과 |
|---|---|
| `git diff --diff-filter=D --name-only 0358d0a..91abd42` | 빈 출력, **삭제 파일 0개** |

스키마가 기존 파일에서 모델을 이동·축소한 것은 파일 삭제가 아니라 수정이며,
legacy import alias는 API 호환 이름일 뿐 YAML alias/raw contract가 아니다.

## S03 설정/YAML, 제거 필드와 엄격 제약

S03 canonical field matrix는 `.omo/evidence/marslab-reference-runtime-refactor/agent/task-3/field-matrix.md`에
기록되어 있으며 YAML leaf 150개와 runtime literal-key access 217개를 모두 분류하고
미분류 0개를 확인했다. `configs/default.yaml`과 `configs/rover_m2020.yaml`은
독립적으로 parse하며 `base_config`, recursive merge, `generation`/`terrain`/`scene`/
`trajectory` 블록을 생산 입력에서 제거했다. Scenario의 atmosphere pressure/density/
temperature/albedo/dust-range/seed 중복 필드와 Rover의 `usd_path`, root
`spawn_position`/`spawn_orientation_rpy`, chassis bbox, wheel radius/diameter_reference/
width, LiDAR 해상도, `sensors.lidar`와 `profile` alias를 제거했다. rendering의 root
`spp`/`total_spp`/`max_bounces`는 `rendering.path_tracing`으로 이동했다.

모든 생산 모델은 `extra="forbid"`, `frozen=True`, `strict=True`,
`allow_inf_nan=False`를 상속한다. fixed vector는 tuple이며 enabled camera/LiDAR는
non-empty `parent_link`와 acquisition fields를 요구하고, disabled variant는 이를
생략할 수 있다. 물리 범위(양수 질량/반지름), finite 수, 마찰 순서 및 wheel bank
cross-field 검증은 loader에서 Kit 전에 수행된다. raw YAML `safe_load`는
`marslab/config/yaml_loader.py` 한 곳뿐이고 곧바로 Pydantic으로 parse한다.

`_PRE_S05_ROVER_USD_PATH`는 `marslab/main.py:90`과 S01 compatibility test의 두
사용처에만 존재하는 임시 상수다. S03은 CLI asset ownership을 구현하지 않았으며,
S05에서 Rover USD 입력을 CLI/RunPlan으로 전환할 때 이 상수를 제거해야 한다는
bounded risk를 명시적으로 남긴다. 이는 S04 asset manifest/submodule 및 S05
RunPlan/CLI 작업을 앞당기지 않았다는 뜻이다.

## 테스트·수동·적대적 검증과 한계

| 성공 기준 | 정확한 시나리오/호출 | 관찰된 binary 결과 | 증거 |
|---|---|---|---|
| canonical Scenario/Rover | `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH= <fresh-venv>/bin/python -m pytest tests/refactor/test_scenario_schema.py tests/refactor/test_rover_schema.py -q` | exit 0, 2 passed | `agent/task-3/pytest.txt` |
| strict rejection | 동일 fresh venv에서 `-m pytest tests/refactor/test_config_rejections.py -q` | exit 0, 15 passed | `agent/task-3/config-rejections.txt` |
| available complete regression | `-m pytest tests/refactor -q` | exit 0, 31 passed | `agent/task-3/full-refactor.txt` |
| formatting/lint/types | changed-scope Black/Ruff, `mypy`, `compileall` | 모두 exit 0; Black 28 files, mypy 19 source | `agent/task-3/black-changed.txt`, `ruff-changed.txt`, `mypy.txt`, `compileall.txt` |
| canonical YAML/field accounting | PyYAML parse와 field/AST checker | exit 0; 150 leaves, 217 accesses, unclassified 0 | `agent/task-3/yaml-parse.txt`, `field-matrix-check.txt`, `runtime-dict-accesses.txt` |
| external consumer | `/tmp`에서 editable package로 두 YAML load | exit 0; typed classes, absolute paths, `ISAAC_IMPORT_MARKER=False` | `agent/task-3/manual-consumer.txt` |
| malformed pre-Isaac | `/tmp` malformed rover loader, expected nonzero wrapper | exit 7; 13 errors, unknown-field true, Isaac marker false | `agent/task-3/manual-malformed.txt` |

S03 adversarial verifier는 fresh archive/venv와 plugin autoload 차단으로 결과를
독립 재현했고 verdict **CONFIRMED**를 남겼다. stale state, misleading exit code,
dirty worktree, generated/cache cleanup을 별도 점검했으며 `.omo/evidence/.../agent/task-3/adversarial-verify/AdversarialVerify.md`에
상세 결과가 있다. malformed/hostile input은 통과, prompt injection/cancel-resume/
hung/flaky/repeated interruptions는 이 CPU-only 결정적 단계에 해당하지 않아
N/A로 기록했다. Isaac GUI/ROS 실제 실행은 S03 지정 QA가 아니므로 주장하지 않는다.

`tests/unit/`는 현재 트리에 없어 `pytest tests/unit -q`가 exit 4(파일/디렉터리 없음)다.
전체 트리 Black도 변경과 무관한 선행 세 파일
`marslab/environment/diffuse_fraction.py`, `marslab/ros2_bridge/imu_noise_publisher.py`,
`marslab/ros2_bridge/wheel_odometry_publisher.py`에서 실패하며, 변경 범위 Black은
통과했다. 이 두 항목은 S03 실패가 아닌 inherited baseline limitation이다.

## 누적 변경 수와 작업 트리

Git `22fe45f..91abd42`의 누적 통계는 **41개 경로, 1,756 insertions, 2,974
deletions**이며 상태는 **추가 13, 수정 28, 삭제 0**이다. S03 자체는 **30개
경로, 추가 8, 수정 22, 삭제 0, +960/-2,655**다. S01/S02/S03 제품 변경은
`.omo` 증거·계획·ledger와 구별한다. 후보 시점 user-owned dirty는 `.gitignore`(수정),
`MARSLAB_STALE_RESIDUE_AUDIT.md`, `MarsLab.pdf`, `MarsLab_refactoring.md`,
`package-lock.json`(미추적)이며 모두 보존했고 커밋에 포함하지 않았다.

## 문서 유지보수와 rename 공개

기존 `MARSLAB_S01_S02_CHANGE_REPORT.md`는 S03 SHA/섹션을 담을 수 없는 stale
이름이므로 이 문서로 **rename**한다. Git 기준 old path는 삭제, new path는 추가로
보일 수 있으며 내용은 S01/S02 검증을 보존하고 S03을 누적한다. 이 rename/content
커밋은 사용자 요청 범위의 문서 유지보수이며 코드·테스트·계획·ledger·evidence는
수정하지 않는다.

## Git 재현 명령

```bash
BASE=22fe45f9146e63e929ceb7163da9458aa0c98f7a
S02_PARENT=0358d0a6d12041483b3d2cb3dcc96c9b2093bdd7
CANDIDATE=91abd42dda5712711ee0f0b711316c94c7185e6f
git rev-parse "$BASE" "$S02_PARENT" "$CANDIDATE"
git log --oneline --decorate --stat "$BASE..$CANDIDATE"
git diff --name-status "$BASE" "$CANDIDATE"
git diff --diff-filter=D --name-only "$BASE" "$CANDIDATE"
git diff --name-status "$S02_PARENT" "$CANDIDATE"
git diff --check "$BASE..$CANDIDATE"
git show --stat --oneline 8f08606 360226d a48868a 01e1e0e f405362 0358d0a 91abd42
```

현재 파일의 표 인용 라인은 `nl -ba <file>`로 확인한다. 보고서 경로/라인 자동
검증과 수동 `sed` 출력은 문서 rename 커밋 전후의 evidence 디렉터리에 저장한다.
