# MarsLab 잔존 기록·주석 전수조사 보고서

> 기준 시점: `main` / `22fe45f9146e63e929ceb7163da9458aa0c98f7a`  
> 조사 방식: 읽기 전용 정적 대조  
> 이 보고서는 정리 대상을 **목록화만** 했으며, 제품 코드·설정·문서·workflow를 정리하거나 삭제하지 않았다.

## 1. 결론

MarsLab에는 현재 동작과 다른 실행 예제, 이미 끝난 개발 단계의 명칭, 해결된 장애의
상세 기록, 삭제된 테스트와 문서를 여전히 현재 자료처럼 가리키는 설명이 남아 있다.
가장 먼저 고쳐야 할 것은 다음 네 부류다.

1. 그대로 복사하면 실패하는 실행 명령과 존재하지 않는 설정 파일 참조
2. 현재 ROS/센서 graph와 정반대로 설명된 모듈 개요
3. 실제 패키지 버전 `0.1.0`과 충돌하는 README의 “현재 v1.0” 표현
4. 이미 삭제된 `tests/unit/`과 존재하지 않는 문서·라이선스 파일을 가리키는 안내

확정된 정리 항목은 16개다. 이 중 14개는 사용자가 현재 자료를 믿고 실행하거나
설치할 때 직접 혼란을 일으킬 수 있어 P0 또는 P1로 분류했다. 반면, 상세한 이유가
적혀 있다는 이유만으로 지우면 안 되는 기록도 있다. Isaac ABI 우회, 단일 camera
render product, TF 단일 소유권, camera X-roll 제거 이유처럼 지금도 구현 결정을
설명하는 주석은 유지해야 한다.

ignored 영역의 문서 7개와 `tmp/preserved_tests`는 Git에 추적되지 않지만 사용자가
의도적으로 보관한 자료다. 내용에 충돌이 있더라도 자동 삭제 대상으로 보지 않았다.
캐시와 bytecode만 명확한 생성물 정리 대상으로 판정했다.

## 2. 즉시 처리 우선순위

| 우선순위 | 조치 | 구체적인 파일과 위치 | 근거 ID | 이유 |
|---|---|---|---|---|
| P0 | 실행 예제 갱신 | `marslab/isaac_python.sh:43-44`<br>`marslab/config/yaml_loader.py:149-151`<br>`configs/default.yaml:6`<br>`README.md:130-136` | SR-001, SR-002, SR-008 | 존재하지 않는 scenario/config를 가리켜 명령이 실패한다. |
| P0 | ROS graph 설명 갱신 | `marslab/ros2_bridge/sensor_graph.py:7-15` | SR-006 | 기본 TF 경로와 camera render product 설명이 현재 구현과 반대다. |
| P0 | 버전·배포 설명 정합화 | `README.md:417,435-460,478,529-531`<br>`pyproject.toml:3` | SR-009, SR-011 | 깨진 법적/문서 링크와 실제 버전 충돌이 있다. |
| P0 | 삭제된 테스트 안내 제거 | `README.md:511-513`<br>`AGENTS.md`<br>`marslab/config/AGENTS.md`<br>`marslab/robots/AGENTS.md`<br>`marslab/ros2_bridge/AGENTS.md`<br>`marslab/runtime/AGENTS.md`<br>`marslab/sensors/AGENTS.md`<br>`marslab/sim/AGENTS.md` | SR-012 | README와 모든 AGENTS 안내가 존재하지 않는 테스트를 실행시킨다. |
| P1 | 현재 코드에서 개발 연대기 제거 | `marslab/config/loader.py:3-6`<br>`marslab/runtime/main_loop.py:1,15,439,597-608`<br>`marslab/runtime/precheck.py:37,51` | SR-003, SR-005, SR-007 | 현재 계약보다 과거 pipeline·장애·단계명이 앞에 나온다. |
| P1 | portable 경로로 갱신 | `README.md:152-153`<br>`configs/rover_m2020.yaml:3-4,40,49,144`<br>`launch/rover_state_publisher.launch.py:193` | SR-010, SR-013, SR-014 | clean clone 또는 다른 checkout 경로에서 그대로 재현되지 않는다. |
| P1 | 옛 감사 보고서에 역사 자료 표시 | `MARSLAB_V0_5_READINESS_AUDIT.md` | SR-015 | 과거 저장소 규모와 현재 상태를 혼동할 수 있다. |
| P2 | 생성 캐시 정리 | `.ruff_cache/`<br>`**/__pycache__/*.pyc` | SR-016 | 재생성 가능하며 제품 자료가 아니다. |

권장 순서는 “깨진 실행 예제 → 현재 동작과 모순된 설명 → 버전·배포 문서 →
개발 연대기 → 생성물”이다. 문서를 먼저 현재 진실에 맞추면 이후 코드 정리에서
활성 workaround를 실수로 제거할 위험도 줄어든다.

## 3. 조치별 목록

### 3.1 제거해도 되는 것

| 구체적인 파일과 위치 | 근거 ID | 대상과 권고 |
|---|---|---|
| `marslab/runtime/main_loop.py:597-608` | SR-005 | 해결된 odometry 장애 서술은 현재 계약만 남기고 장애 연대기를 제거 |
| `.ruff_cache/`<br>`**/__pycache__/*.pyc` | SR-016 | 재생성 가능한 생성물로 정리 |

### 3.2 다시 써야 하는 것

| 구체적인 파일과 위치 | 근거 ID | 대상과 권고 |
|---|---|---|
| `marslab/isaac_python.sh:43-44` | SR-001 | Isaac wrapper 예제를 실제 존재하는 입력을 쓰는 명령으로 교체 |
| `marslab/config/yaml_loader.py:149-151`<br>`configs/default.yaml:6` | SR-002 | `_base.yaml`을 현재 표준처럼 설명하는 주석에서 generic `base_config` 계약과 실제 파일 구성을 분리 |
| `marslab/config/loader.py:3-6` | SR-003 | typed config path 설명을 현재 schema와 raw-dict 경로의 역할에 맞게 수정 |
| `marslab/main.py:250` | SR-004 | 기본 `dem_center`의 “legacy” 표시를 지원되는 현재 기본값으로 표현 |
| `marslab/ros2_bridge/sensor_graph.py:7-15` | SR-006 | sensor graph 개요에 joint-state 기본 경로와 shared `RPCamera`를 반영 |
| `marslab/runtime/main_loop.py:1,15,439`<br>`marslab/runtime/precheck.py:37,51` | SR-007 | “Stage 3 monolithic” 표현을 현재 lifecycle/runtime 역할로 교체 |
| `README.md:130-136` | SR-008 | 존재하지 않는 dust/lidar 설정 예제를 실제 제공되는 예제로 교체하거나 제거 |
| `README.md:435,443,451,460,529-531` | SR-009 | 존재하지 않거나 ignored 상태인 문서 링크를 추적되는 실제 자료로 연결 |
| `README.md:152-153` | SR-010 | `tmp/run.log` 예제에 디렉터리 생성을 포함하거나 존재하는 경로 사용 |
| `README.md:417,478`<br>`pyproject.toml:3` | SR-011 | “현재 v1.0” 주장을 소유자가 정한 실제 release identity와 일치시킴 |
| `README.md:511-513`<br>`AGENTS.md`<br>`marslab/config/AGENTS.md`<br>`marslab/robots/AGENTS.md`<br>`marslab/ros2_bridge/AGENTS.md`<br>`marslab/runtime/AGENTS.md`<br>`marslab/sensors/AGENTS.md`<br>`marslab/sim/AGENTS.md` | SR-012 | 삭제된 tests와 이전 lint 명령을 현재 workflow와 개발 절차에 맞게 수정 |
| `configs/rover_m2020.yaml:3-4,40,49,144` | SR-013 | 삭제된 근거·절대 trajectory 경로를 portable 예시와 현재 근거로 교체 |
| `launch/rover_state_publisher.launch.py:193` | SR-014 | `~/MarsLab` 기본값을 설치/checkout 위치에 독립적인 해석 방식으로 수정 |

### 3.3 보관하되 역사 자료임을 표시할 것

| 구체적인 파일과 위치 | 근거 ID | 권고 |
|---|---|---|
| `MARSLAB_V0_5_READINESS_AUDIT.md` | SR-015 | 현재 상태 보고서가 아닌 과거 감사 결과로 명시 |

### 3.4 소유자 판단이 필요한 것

| 구체적인 파일과 위치 | 근거 ID | 판단 포인트 |
|---|---|---|
| `docs/odometry_ground_truth.md:16-43,51-67,90-122` | SR-017 | 현재 GT/wheel odom 분리로 갱신할지 역사 자료로 둘지 |
| `docs/frame_conventions.md:13-25,68-81,111-167` | SR-018 | REP-103 identity chain으로 갱신할지 역사 자료로 둘지 |
| `docs/colored_pointcloud.md:28,83-87` | SR-019 | 실제 배포 문서로 승격할지 설계 메모로 보관할지 |
| `pyproject.toml:33-53` | SR-020 | 설정 이유만 남기고 reviewer/ticket 연대기를 지울지 |
| `.github/workflows/security.yaml:19-26` | SR-021 | GDAL이 외부 배포 환경에서 필요한지 CI 소유자가 확인 |
| `marslab/ros2_bridge/sensor_graph_builder.py:91-92,361-364` | SR-023 | `/tf_raw` 기능은 유지하되 v0.7 버전 기반 표현을 바꿀지 |

### 3.5 그대로 유지할 것

[`GT_Trajectory.md`](GT_Trajectory.md)는 대체로 현재의 PhysX ground truth와 wheel
odometry 분리를 올바르게 설명한다(SR-022). 삭제된 테스트를 언급한 일부 역사 문장만
다듬으면 된다.

다음 가드레일은 정리 과정에서 삭제하면 안 된다.

| 구체적인 파일과 위치 | 근거 ID | 유지할 근거 |
|---|---|---|
| `marslab/ros2_bridge/sensor_graph_builder.py:118-123,195-224,385-393` | RG-001 | RGB, depth, point cloud, CameraInfo가 하나의 `RPCamera`를 공유하는 이유 |
| `marslab/ros2_bridge/sensor_graph_builder.py:82-113,340-380` | RG-002 | 기본 joint-state 경로와 선택 가능한 `/tf_raw` 경로의 상호 배타성 |
| `configs/rover_m2020.yaml:205-214` | RG-003 | 180° camera X-roll을 제거한 뒤 영상이 정상화된 active workaround 근거 |
| `marslab/ros2_bridge/robot_description_publisher.py`<br>`launch/rover_state_publisher.launch.py` | RG-004 | robot-description mesh URI sanitization이 필요한 이유 |
| `marslab/fix_urdf_inertia.py`<br>`marslab/convert_urdf_to_usd.py` | RG-005 | URDF inertia 수정과 USD 변환이 runtime이 아닌 일회성 준비 작업인 이유 |
| `marslab/sensors/sensor_spawner.py`<br>`marslab/config/schema/robot.py` | RG-006 | 현재 허용되는 LiDAR legacy alias |
| `marslab/rendering/`<br>`marslab/config/schema/rendering.py` | RG-007 | 현재 Isaac shader/API에 연결된 rendering migration 설명 |
| `marslab/isaac_python.sh:18-40` | RG-008 | Isaac/ROS ABI 충돌을 피하기 위한 wrapper의 동적 링커 환경 정리 |
| `marslab/environment/diffuse_fraction.py`<br>`marslab/environment/sun_position.py` | RG-009 | 사용 중인 diffuse zenith hook과 legacy sun API |
| `marslab/environment/light_intensity.py:7-12,63-64` | RG-010 | 현재 seasonal mode의 정확한 한계 |
| `tmp/preserved_tests/` | RG-011 | 사용자가 명시적으로 보존한 테스트 |
| `docs/` | RG-012 | ignored 문서는 사용자 소유 자료이므로 나이·크기만으로 삭제하지 않는 원칙 |
| `assets/m2020-urdf-models` | RG-013 | submodule 내부는 MarsLab 소유 residue로 분류하지 않는 원칙 |

## 4. 현재 구현을 읽는 기준

### Runtime과 CLI

지원되는 진입점은 `marslab/main.py`이며 Isaac 환경에서는
`marslab/isaac_python.sh`를 통해 실행한다. terrain USDA는 외부 입력이다.
기본 spawn mode는 `dem_center`이고 `dem_relative`, `absolute`,
`trajectory_start`도 지원된다. “Stage 3”은 현재 release identity가 아니다.

### Config와 schema

YAML merge와 경로 해석은 `marslab/config/yaml_loader.py`가 담당한다.
`base_config` 기능 자체는 살아 있지만 추적되는 `configs/scenarios/_base.yaml`은 없다.
현재 추적되는 canonical config는 `configs/default.yaml`과
`configs/rover_m2020.yaml`뿐이다. Pydantic schema와 raw-dict seed propagation은
모두 현재 tree에 존재한다.

### ROS, odometry와 TF

현재 구조는 PhysX pose ground truth와 wheel dead-reckoning을 구분한다. 기본
articulation 경로는 `/rover/joint_states`를 발행하고 외부
`robot_state_publisher`가 link TF를 만든다. `/tf_raw` PubTF는
`publish_joint_states=False`일 때 사용하는 활성 호환 경로다. 같은 transform을
두 publisher가 동시에 소유하지 않는 규칙은 유지해야 한다.

### Frame과 sensor

rover, config, launch는 REP-103의 +X forward, +Y left, +Z up을 기준으로 하며
과거의 X-roll 보정은 적용하지 않는다. RGB, depth, point cloud와 CameraInfo는
하나의 `RPCamera` render product를 공유한다.

### CI와 tests

현재 추적 workflow는 lint와 security 두 개다. lint는 `marslab/`만 Black과
Ruff로 검사한다. `tests/`와 unit-test workflow는 없다. 따라서
`pytest tests/unit/`이나 `black ... tests/`를 현재 명령으로 제시하는 문서는
잘못됐다.

### Package, version과 distribution

`pyproject.toml`의 package version은 `0.1.0`, 요구 Python은 3.12 이상이다.
setuptools가 `marslab*` package를 찾도록 설정되어 있고 license expression은
Apache-2.0이다. 그러나 저장소에는 README가 연결하는 `LICENSE`와
third-party license 파일이 없고 console-script entry point도 없다.

## 5. 경계와 주의사항

- 오래됐다는 이유만으로 주석을 제거 대상으로 삼지 않았다.
- 현재 caller, config, schema 또는 workflow와 충돌하는 경우에만 확정했다.
- 호환 분기와 platform workaround는 장황하더라도 현재 동작 이유를 제공하면 보존했다.
- ignored 문서와 보존 테스트는 소유자 자료로 보아 자동 삭제를 권고하지 않았다.
- submodule 내부는 upstream 소유이므로 의미 감사를 수행하지 않았다.
- 이 조사는 runtime 정확성, 과학적 정확성 또는 release readiness를 검증하지 않는다.

## 6. 조사 방법

기준 commit과 Git 추적 상태를 고정한 뒤 세 영역을 나누어 조사했다.

1. `marslab/**/*.py`와 shell 파일의 comment/docstring을 현재 caller·default와 대조
2. README, AGENTS, config, launch, workflow, package metadata의 경로와 주장 대조
3. tracked, untracked, ignored universe의 소유권·생성 가능성·참조 여부 분류

이후 중복 후보를 합치고, HIGH 확신 항목과 “파일이 없다”는 주장은 현재 filesystem과
`HEAD:<path>` 양쪽에서 다시 확인했다. 전체 runtime, 테스트, lint, formatter,
Python import는 실행하지 않았다.

## 7. 상세 근거

아래 표는 요약부의 각 SR ID에 대응하는 단일 근거 행이다.

| ID | 위치와 남은 설명 | 현재 진실 근거 | 조치·확신·영향 | 주의 |
|---|---|---|---|---|
| SR-001 | `marslab/isaac_python.sh:43-44`가 `configs/scenarios/jezero_flat.yaml`을 사용 | 대상은 tree와 HEAD 모두 없음 | 갱신 / HIGH / 실행 실패 | ABI wrapper 설명은 유지 |
| SR-002 | `marslab/config/yaml_loader.py:149-151`, `configs/default.yaml:6`이 `_base.yaml`을 현재 공통 파일처럼 설명 | `base_config` merge는 live지만 `configs/scenarios/_base.yaml`은 tree/HEAD에 없음 | 갱신 / HIGH / config 작성 혼란 | generic merge 계약은 유지 |
| SR-003 | `marslab/config/loader.py:3-6`이 typed path 전체를 퇴역한 pipeline처럼 설명 | `marslab/config/schema/**`와 seed helper가 현재 존재 | 갱신 / HIGH / 구조 오해 | live seed invariant 유지 |
| SR-004 | `marslab/main.py:250`의 “default, legacy” | 같은 함수와 rover config가 `dem_center`를 현재 기본값으로 사용 | 갱신 / MEDIUM / 지원 상태 오해 | 동작 변경 없음 |
| SR-005 | `marslab/runtime/main_loop.py:597-608`의 이전 inline 구현과 `NoneType.sendTransform` 장애 기록 | 현재 `_publish_odometry`는 canonical context/publisher gate에 위임 | 제거 / HIGH / API 문서 노이즈 | 단일 TF 소유권은 유지 |
| SR-006 | `marslab/ros2_bridge/sensor_graph.py:7-15`의 기본 `/tf_raw`, 독립 RGB/depth RP 주장 | builder 기본은 joint states이며 `sensor_graph_builder.py:118-224,385-393`은 shared `RPCamera`를 연결 | 갱신 / HIGH / 현재 graph와 반대 | `/tf_raw` 선택 분기는 유지 |
| SR-007 | `runtime/main_loop.py:1,15,439`, `runtime/precheck.py:37,51`의 “Stage 3 monolithic” | runtime은 이미 sim/runtime/bridge 계층으로 분리되어 main이 orchestrate | 제거·갱신 / HIGH / 역사 단계를 현재 구조처럼 표현 | import-order·소유권 계약 유지 |
| SR-008 | `README.md:130-136`의 dust/lidar config 예제 | 두 대상 config 모두 tree와 HEAD에 없음 | 갱신 / HIGH / 복사한 명령 실패 | 파일을 새로 만들라는 판정은 아님 |
| SR-009 | `README.md:435,443,451,460,529-531`의 삭제/누락/ignored 파일 링크 | `delete_later`, CLAUDE, LICENSE, third-party 파일은 HEAD에 없고 docs는 ignored라 clean clone에 없음 | 갱신 / HIGH / 배포·법적 안내 손상 | ignored docs는 삭제 금지 |
| SR-010 | `README.md:152-153`이 `~/MarsLab/tmp/run.log`에 바로 tee | `tmp/`는 ignored이며 clean clone에 생성되지 않음 | 갱신 / HIGH / 명령 실패 가능 | 현재 로컬 tmp 존재는 보존 테스트 때문 |
| SR-011 | `README.md:417,478`의 post/current v1.0 표현 | `pyproject.toml:3`은 `0.1.0` | 갱신 / HIGH / release identity 충돌 | 최종 버전은 소유자가 결정 |
| SR-012 | `README.md:511-513`, root/nested AGENTS의 `tests/unit` 명령 | tests와 unit workflow는 없고 lint workflow는 `marslab/`만 검사 | 갱신 / HIGH / 개발 명령 실패 | 역사 보고서는 명시하면 보존 가능 |
| SR-013 | `configs/rover_m2020.yaml:3-4,40,49,144`의 없는 scenario/delete_later와 사용자 절대 경로 | 추적 config는 두 개뿐이고 trajectory mode에서만 해당 path 사용 | 갱신 / HIGH / portable 실행 저해 | `dem_center`에서는 경로가 사용되지 않음 |
| SR-014 | `launch/rover_state_publisher.launch.py:193`의 `~/MarsLab` 기본 URDF | checkout/install 위치는 고정되지 않음 | 갱신 / HIGH / 다른 위치에서 launch 실패 | 사용자 override는 가능 |
| SR-015 | `MARSLAB_V0_5_READINESS_AUDIT.md`의 136 tracked path, 23,353 LOC 등 | 현재 baseline은 87 tracked path이며 tests가 제거됨 | archive/label / HIGH / 현재 감사로 오인 | 역사 기록 가치는 있음 |
| SR-016 | ignored `.ruff_cache` 3개와 pyc 126개 | 재생성 가능한 lint/Python cache | 생성물 정리 / HIGH / 로컬 clutter | Git 삭제 대상이 아님 |
| SR-017 | ignored `docs/odometry_ground_truth.md`의 odometry 설명 | 현재 context/config는 wheel `/odom`과 PhysX `GT_Trajectory`를 분리 | owner decision / MEDIUM / 사용자 문서 혼란 | ignored 사용자 자료 |
| SR-018 | ignored `docs/frame_conventions.md`의 X-roll 설명 | `configs/rover_m2020.yaml:16-17`과 launch는 REP-103 identity chain | owner decision / MEDIUM / frame 오해 | ignored 사용자 자료 |
| SR-019 | ignored `docs/colored_pointcloud.md`의 사용자 launch와 v1.5 backlog | 해당 launch는 추적 tree에 없음 | owner decision / MEDIUM / 실행성 불명 | 설계 메모일 수 있음 |
| SR-020 | `pyproject.toml:33-53`의 reviewer 번호·날짜·v2.0 연대기 | Ruff/Mypy scope 자체는 현재 설정으로 유효 | 제거·갱신 / MEDIUM / config 노이즈 | 의도적 scope 이유는 유지 |
| SR-021 | `.github/workflows/security.yaml:19-26`의 GDAL 설치·검증 | 선언 dependency와 MarsLab source에서 직접 GDAL 필요를 확인하지 못함 | owner decision / MEDIUM / CI 비용·실패면 | 외부 환경 요구일 수 있음 |
| SR-022 | `GT_Trajectory.md`의 GT와 wheel odometry 설명 | 현재 context/config의 두 publisher 역할과 대체로 일치 | 유지·부분 갱신 / HIGH / 유용한 운영 문서 | 삭제된 test 언급만 역사 표시 |
| SR-023 | `sensor_graph_builder.py:91-92,361-364`가 `/tf_raw`를 v0.7 scenario용이라 설명 | `publish_joint_states=False`이면 현재도 분기가 실행되나 tracked v0.7 scenario는 없음 | owner decision / MEDIUM / 호환 대상 불명 | 분기 자체는 삭제 금지 |

## 8. 추적 텍스트 76개 coverage ledger

각 파일은 아래 한 그룹에만 포함된다. “이상 없음”은 관련 prose를 조사했으나 현재
구현과 충돌하거나 불필요한 개발 기록으로 확정할 근거가 없다는 뜻이다.

| 그룹 | 파일 | 결과 |
|---|---|---|
| C1 metadata/workflow (5) | `.gitattributes`, `.gitignore`, `.gitmodules`, `.github/workflows/lint.yaml`, `.github/workflows/security.yaml` | security는 SR-021; 나머지는 현재 정책 또는 관련 prose 없음 |
| C2 root 문서 (4) | `AGENTS.md`, `GT_Trajectory.md`, `MARSLAB_V0_5_READINESS_AUDIT.md`, `README.md` | SR-008~SR-012, SR-015, SR-022 |
| C3 config/launch/package (4) | `configs/default.yaml`, `configs/rover_m2020.yaml`, `launch/rover_state_publisher.launch.py`, `pyproject.toml` | SR-002, SR-011, SR-013, SR-014, SR-020, RG-003 |
| C4 package root (1) | `marslab/__init__.py` | 관련 prose 없음 |
| C5 config package (10) | `marslab/config/AGENTS.md`, `__init__.py`, `loader.py`, `yaml_loader.py`, `schema/__init__.py`, `schema/mars_env.py`, `schema/rendering.py`, `schema/robot.py`, `schema/root.py`, `schema/ros2_bridge.py` | SR-002, SR-003, SR-012; 나머지는 현재 schema 근거 또는 이상 없음 |
| C6 준비 도구 (2) | `marslab/convert_urdf_to_usd.py`, `marslab/fix_urdf_inertia.py` | RG-005, 유지 |
| C7 environment (5) | `marslab/environment/__init__.py`, `diffuse_fraction.py`, `light_intensity.py`, `sky_dome.py`, `sun_position.py` | RG-009, RG-010; 나머지 이상 없음 |
| C8 GUI (2) | `marslab/gui/__init__.py`, `marslab/gui/atmosphere_panel.py` | 관련 prose 없음 |
| C9 top-level runtime (3) | `marslab/isaac_python.sh`, `marslab/main.py`, `marslab/quaternion.py` | SR-001, SR-004, RG-008; quaternion 이상 없음 |
| C10 rendering (5) | `marslab/rendering/__init__.py`, `atmosphere_fog.py`, `render_settings.py`, `sky_renderer.py`, `sun_renderer.py` | RG-007; 관련 migration 외 이상 없음 |
| C11 robots (5) | `marslab/robots/AGENTS.md`, `__init__.py`, `drive_api_setup.py`, `rover.py`, `rover_control.py` | AGENTS는 SR-012; 나머지 이상 없음 |
| C12 ROS bridge (15) | `marslab/ros2_bridge/AGENTS.md`, `__init__.py`, `cmd_vel_subscriber.py`, `context.py`, `imu_noise_publisher.py`, `odometry_math.py`, `odometry_publisher.py`, `qos.py`, `rclpy_integration.py`, `robot_description_publisher.py`, `sensor_graph.py`, `sensor_graph_builder.py`, `tf_broadcaster.py`, `tf_nameoverrides.py`, `wheel_odometry_publisher.py` | SR-006, SR-012, SR-023, RG-001, RG-002, RG-004; 나머지는 current-truth 근거 또는 이상 없음 |
| C13 runtime package (8) | `marslab/runtime/AGENTS.md`, `__init__.py`, `articulation_setup.py`, `atmosphere_boot.py`, `loop_context.py`, `main_loop.py`, `precheck.py`, `sensor_frames.py` | SR-005, SR-007, SR-012; 나머지 이상 없음 |
| C14 sensors (3) | `marslab/sensors/AGENTS.md`, `__init__.py`, `sensor_spawner.py` | AGENTS는 SR-012; active parent-Xform 설명은 유지 |
| C15 sim (4) | `marslab/sim/AGENTS.md`, `__init__.py`, `boot.py`, `world_setup.py` | AGENTS는 SR-012; 나머지 이상 없음 |

합계는 `5+4+4+1+10+2+5+2+3+5+5+15+8+3+4 = 76`이다.

## 9. Git universe와 ignored 산술

| 구분 | 수량 | 크기 | 판정 |
|---|---:|---:|---|
| tracked 전체 | 87 paths | - | 76 text + 10 binary + 1 gitlink |
| ordinary untracked | 0 | 0 | 별도 root residue 없음 |
| ignored 전체 | 153 leaves | 41,393,392 B | 아래 다섯 class의 합 |
| `.omo` | 8 | 129,484 B | orchestration state, 의미 감사 제외 |
| ignored docs | 7 | 40,097,631 B | 사용자 소유, SR-017~SR-019 포함 |
| `.ruff_cache` | 3 | 2,613 B | 생성물 정리 |
| `__pycache__/*.pyc` | 126 | 1,057,181 B | 생성물 정리 |
| `tmp/preserved_tests` | 9 | 106,483 B | 사용자 지정 보존 |

산술:

- leaves: `8 + 7 + 3 + 126 + 9 = 153`
- bytes: `129,484 + 40,097,631 + 2,613 + 1,057,181 + 106,483 = 41,393,392`

`assets/m2020-urdf-models`는 gitlink이며 기준 SHA는
`bc25f70c9abe6c34b8019ae5ec10d5b7f1c122c6`이다. 그 내부는 MarsLab 소유
파일처럼 조사하거나 정리 대상으로 분류하지 않았다.

## 10. 한계와 미수행 항목

- 정적 source/config/document 대조만 수행했다.
- Isaac Sim, ROS 2, GPU, USD composition을 실행하지 않았다.
- unit/E2E test, lint, formatter, type checker, build, import를 실행하지 않았다.
- ignored 문서의 의도를 작성자에게 확인하지 않았다.
- security workflow에서 GDAL이 외부 배포 환경에 필요한지는 확인하지 못했다.
- 실제 release version은 저장소 소유자가 결정해야 한다.

따라서 이 보고서는 “무엇을 정리해야 현재 자료와 구현이 일치하는가”에 대한
근거 목록이지, MarsLab의 runtime 또는 scientific fidelity가 검증되었다는 뜻이
아니다. 조사 중에는 어떤 정리도 수행하지 않았고, 이 Markdown 보고서 외의
제품·설정·문서·workflow 파일을 수정하거나 생성하지 않았다.
