# MarsLab S01/S02 변경 보고서

## 목적과 범위

이 문서는 기준 커밋 `22fe45f9146e63e929ceb7163da9458aa0c98f7a`부터 후보
커밋 `f4053621844b212372f8c72f17a844e22b404a07`까지의 실제 Git 변경만을
S01/S02별로 기록한다. 범위는 S01(외부 MarsLab-Utils 의존성 제거)과 S02(공급된
Scene USDZ/Rover 입력을 기준으로 한 문서·주석 정리)이다. S03 이후의 작업이나
`.omo` 내부 구현은 제품 변경으로 세지 않았으며, 이 보고서를 만들기 전 파일이
없었다는 실패 우선 증거도 함께 보관했다.

## 커밋 목록과 단계 경계

| 단계 | 커밋(시간순) | 내용 |
|---|---|---|
| S01 | `8f08606f78a43128ef14d3b78dc63f7d133291a4` | MarsLab-Utils/GT/trajectory 런타임 의존성 제거, 사전검사·검증 도구와 테스트 추가 |
| S01 | `360226dbbf169937b9f33e31e28da1b0f52840b3` | S01 Python 범위 포맷 정리(`marslab/main.py`) |
| S02 | `a48868a0f02a74b3e643e1d9ebc93a9705819739` | 공급 Scene USDZ/Rover 입력에 맞춘 문서·설정·공개 API 주석 정리 |
| S02 | `01e1e0e27596c213b44a919288adf25f43b09425` | README 로컬 링크가 추적 파일인지 검증하는 테스트 강화 |
| S02 | `f4053621844b212372f8c72f17a844e22b404a07` | 문서 명령의 입력 파일이 실제로 공급되는지 구별하는 테스트 보강 |

후보 커밋의 부모는 `01e1e0e27596c213b44a919288adf25f43b09425`이고, 보고서 자체는
후보 이후 새 커밋으로만 추가된다. 위 목록은 `git log --oneline --stat
22fe45f..f405362`로 확인했다.

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

## 삭제 파일과 새 파일

삭제 여부는 추측하지 않고 다음 명령의 Git 결과로 판단했다.

```bash
git diff --diff-filter=D --name-only \
  22fe45f9146e63e929ceb7163da9458aa0c98f7a \
  f4053621844b212372f8c72f17a844e22b404a07
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

## 테스트와 증거

현재 후보에서 실행한 검증은 다음과 같다.

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
이 보고서 자체의 경로/라인 및 Git 표 검증 결과는 최종 검증 시 같은 디렉터리의
`report-validation.txt`와 수동 출력 `manual-qa.txt`에 저장한다. `.omo` 파일은
제품 변경이 아니라 증거 메모다.

Isaac Sim/ROS2가 필요한 실제 GUI·physics·topic 실행은 이 CPU 환경에서 수행하지
않았다. 이는 S01/S02 코드 변경의 성공을 주장하는 항목이 아니라, 런타임 확인이
아직 남아 있는 알려진 검증 한계다. S01 ledger에는 별도로 사용자 명령과 승인
`APPROVE S01`이 기록되어 있다.

## 작업 트리와 변경 영향

보고서 생성 전부터 다음 사용자 소유 dirty/untracked 파일이 있었고 건드리지
않았다: `.gitignore`(수정), `MARSLAB_STALE_RESIDUE_AUDIT.md`, `MarsLab.pdf`,
`MarsLab_refactoring.md`, `package-lock.json`(미추적). 이 파일들은
`22fe45f..f405362` 제품 diff에 포함되지 않는다.

행동 영향은 (1) runtime이 MarsLab-Utils/외부 `gt_publisher`/TUM trajectory에
의존하지 않음, (2) 제거된 `trajectory_start`가 Kit 전에 실패함, (3) Scene은
공급 USDZ를 사용하고 terrain authoring은 수행하지 않음, (4) 현재 단계에서는
Rover YAML의 `usd_path`가 여전히 해석됨(S05에서 CLI 소유권으로 바뀔 예정)이다.
ROS TF, sensor graph, QoS 및 atmosphere 계산의 실행 로직은 S02에서 바꾸지 않고
근거 주석만 공개 API 기준으로 정리했다.

### 레거시 `--usda` 상태

`--usda`는 **삭제되지 않았다**. 현재 `marslab/main.py` 427–447행의 parser,
`marslab/isaac_python.sh` 42–47행, `README.md` 43–49·78행 및
`configs/default.yaml` 10–12행에서 pre-S06 호환 alias로 유지한다. 의미는 구
USDA terrain이 아니라 공급 Scene USDZ 경로이며, S06에서 canonical `--scene`이
추가될 때까지 이 호환 상태를 유지한다.

### 알려진 선행/환경 검증 이슈

* `python` 명령 자체가 이 셸에 없어 `python -m pytest`는 exit 127이었고,
  동일 명령을 `python3`로 재실행해 14개 테스트가 통과했다.
* Isaac Sim 5.x, GPU, ROS2 daemon이 필요한 GUI/physics/topic 검증은 이 단계에서
  재현하지 않았다. 이는 파일 삭제나 테스트 실패가 아니다.
* README의 요구사항에는 여전히 Python 3.12+가 남아 있다(패키지 런타임 floor를
  3.11로 맞추는 S07 범위). S02에서 이를 임의로 바꾸지 않았다.

## Git 재현 명령

정확한 기준·후보를 다시 확인하고 변경 목록/삭제 목록/통계를 보는 명령은 다음과
같다.

```bash
BASE=22fe45f9146e63e929ceb7163da9458aa0c98f7a
CANDIDATE=f4053621844b212372f8c72f17a844e22b404a07
git rev-parse "$BASE" "$CANDIDATE"
git log --oneline --decorate --stat "$BASE..$CANDIDATE"
git diff --name-status "$BASE" "$CANDIDATE"
git diff --diff-filter=D --name-only "$BASE" "$CANDIDATE"
git diff --check "$BASE..$CANDIDATE"
git show --stat --oneline 8f08606 360226d a48868a 01e1e0e f405362
```

현재 파일의 모든 인용 라인은 `nl -ba <file>`로 확인할 수 있다. 이 보고서의
검증 스크립트는 표의 파일 경로가 위 Git 출력에 존재하는지, 삭제 표가 빈 결과와
일치하는지, 표에 기록한 `파일:시작–끝` 라인이 현재 파일 범위인지 검사한다.
