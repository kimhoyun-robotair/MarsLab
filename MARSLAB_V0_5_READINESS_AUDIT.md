# MarsLab Version 0.5 배포 준비도 감사

> 기준 커밋: `04f4346146900983c0eb7b02d4fad298046f3a92`  
> 감사 방식: 제품 파일 무수정, 정적·읽기 전용 조사  
> 최종 판정: **NOT_READY**

## 1. Executive snapshot

MarsLab의 핵심 구조는 명확하고 CPU 단위 테스트 표면도 크지만, 현재 상태는 Version 0.5로
배포할 수 없다. 14개 필수 gate 중 7개가 `FAIL`, 5개가 `NOT_RUN_ENV`, 2개만 `PASS`다.
특히 메타데이터가 `0.1.0`이고, 설치 산출물에 런타임 asset/config가 포함된다는 계약이
없으며, lint CI가 존재하지 않는 `scripts/`를 참조한다. Isaac/ROS 환경 검증도 이번
읽기 전용 감사에서는 실행하지 않았다.

실행에는 사용자가 제공하는 외부 terrain USDA가 매번 필요하다. 저장소에는 terrain
USDA가 없으며 이는 누락된 repository asset이 아니라 명시된 외부 입력 계약이다. 로버
USD 5개, URDF와 20개 GLTF 참조, 현재 소비되는 sky PNG 3개는 로컬에 있다. 다만 Isaac
없이 USD composition 의미론을 `PASS`로 판정하지 않았다.

기능 유지형 순감축은 보수적으로 **363 LOC**, 런타임 확인 후 누적 **401 LOC**다.
레거시 호환성 폐기 **583 LOC**와 기타 정책 의존 **52 LOC**는 별도 조건부 수치이며 앞의
합계에 더해서는 안 된다.

## 핵심 결과: 무엇을 지우고, 무엇을 바꾸고, 어떻게 0.5로 갈 것인가

이 절이 본 감사의 실제 결론이다. 뒤의 장들은 이 결론을 뒷받침하는 상세 원장이다.

### 요청 1 — 실행에 필요한 USD와 현재 보유 여부

| 구분 | 필요한 것 | 현재 상태 | Version 0.5 조치 |
|---|---|---|---|
| Terrain | 사용자가 `--usda`로 넘기는 Mars terrain USDA. `/World/Terrain`에 visible mesh와 collision contract가 필요 | **저장소에 없음**. 외부 MarsLab-Utils 산출물로 설계된 입력 | 최소 한 개의 배포 검증용 terrain USDA 경로와 생성·획득 절차를 release 문서에 고정하고 Isaac smoke에 사용 |
| Rover root | `assets/robots/rover/m2020.usd` | 있음 | 유지 |
| Rover layers | `m2020_base.usd`, `m2020_physics.usd`, `m2020_robot.usd`, `m2020_sensor.usd` | 모두 있음 | Isaac에서 composition을 실제 검증하기 전에는 의미론 PASS 금지 |
| Rover source | submodule의 `m2020.urdf`와 GLTF mesh | URDF 및 20/20 직접 GLTF 참조 있음 | submodule SHA 고정 및 clean-clone 검증 |
| Sky | clear/moderate/dusty PNG | 현재 runtime consumer 3개 모두 있음 | 유지 |
| LiDAR | `OS1`, `Example_Rotary_2D` profile | Isaac bundle 의존, 저장소 파일 아님 | 지원 Isaac 버전에서 profile resolution 확인 |

결론적으로 **현재 저장소만으로는 실행할 수 없다. 외부 terrain USDA가 반드시 필요하다.**
반면 rover USD/URDF/mesh가 없어서 실행하지 못하는 상태는 아니다.

### 요청 2 — 불필요한 파일의 최종 분류

#### A. 즉시 제거해도 되는 생성물

다음은 source가 아니며 도구가 재생성한다. Version 0.5 source tree 또는 배포물에 포함할
이유가 없다.

| 대상 | 현재 확인량 | 판단 | 복구 |
|---|---:|---|---|
| `.mypy_cache/**` | 4 files / 22,479,072 B | 제거 | mypy가 재생성 |
| `.pytest_cache/**` | 6 files / 158,388 B | 제거 | pytest가 재생성 |
| `.ruff_cache/**` | 90 files / 94,924 B | 제거 | Ruff가 재생성 |
| `**/__pycache__/**` | 236 files / 3,621,662 B | 제거 | Python이 재생성 |
| `build/**` | 2 files | 제거 | colcon/build가 재생성 |
| `install/**` | 12 files / 49,520 B | 제거 | colcon/install이 재생성 |
| `log/**` | 3 files / 82,774 B | 제거 | 실행 로그 |
| `tmp.txt` | 87,832 B | **내용 백업 필요 여부만 확인 후 제거** | 원본이 없으므로 삭제 전 owner 확인 |

#### B. 리팩토링과 함께 Git에서 제거할 tracked test

| 파일 | 조치 | 순감축 | 기능 유지 조건 |
|---|---|---:|---|
| `tests/unit/test_robot_config.py` | 전체 제거 | 44 | 동일 계약이 `test_robot_schema.py`와 `test_config_schema.py`에 존재함을 수정 시 다시 확인 |
| `tests/unit/test_rover_control.py` | 전체 제거하고 누락된 `track_middle=0` case 하나를 `test_ackermann.py`로 이동 | 60 | `test_ackermann.py`가 직진·회전·dtype·geometry를 모두 유지 |
| `tests/unit/test_materials.py` | 전체 삭제 금지. 자기검증·중복 구간 `1-11,21-32`만 제거 | 23 | 고유한 기본 `surface_albedo_range` 계약인 `12-20` 유지 |
| `tests/unit/test_runtime_shutdown_exit_code.py` | 현재 source-text test를 삭제하고 실제 cleanup/exit seam test로 교체 | likely 12 | replacement test가 실제 반환·예외 observable을 검증한 뒤에만 기존 파일 제거 |

#### C. 삭제가 아니라 owner 결정이 필요한 항목

| 대상 | 기본 권고 | 결정이 필요한 이유 |
|---|---|---|
| `MarsLab.html` | 생성 방법과 소비자가 없다면 Git에서 제거 | 4.7 MB 생성형 dossier로 보이나 배포 문서인지 확정할 owner 정보가 없음 |
| `figure/**` 252개 | 저장소 외 archive로 이동 권고 | 연구·논문 증거일 수 있어 자동 삭제 금지 |
| `docs/**` 7개 | 사용 문서만 source 관리 대상으로 승격하고 나머지는 archive | 현재 ignored 상태인데 README와 코드가 일부를 참조함 |
| `.claude/**`, `AGENTS.md`, `.omo/**` | 제품 배포물에서는 제외, 개발 환경에서는 유지 가능 | agent 운영 메타데이터이며 제품 runtime 파일이 아님 |
| `mars_sky_clear.hdr.png` | 실제 소비자를 만들거나 제거 | 존재하지만 현재 runtime consumer가 확인되지 않음 |
| `tests/unit/test_loader.py`와 seed path | 유지 | seed propagation은 실제 동작이며, 호환성 폐기 결정 없이는 dead code가 아님 |

#### D. 제거하면 안 되는 과거 개발 도구

`marslab/convert_urdf_to_usd.py`와 `marslab/fix_urdf_inertia.py`는 runtime code가 아니지만
rover source asset을 재생성하는 공식 one-shot preparation 경로다. “runtime에서 호출하지
않는다”와 “불필요하다”는 같은 뜻이 아니므로 유지한다. 이미 Git history에서 삭제된 과거
terrain/scenario/dev 파일은 현재 cleanup 대상에 다시 포함하지 않는다.

### 요청 3 — 7원칙에 따른 기능 유지형 리팩토링

다음 **A 작업 묶음은 public compatibility 폐기 없이 363 LOC 순감축**을 목표로 한다.
각 행의 검증을 같은 변경에 포함한다.

| 작업 | 수정 대상 | 순감축 | 기능 유지 검증 |
|---|---|---:|---|
| test-only QoS reset hook 제거 | `ros2_bridge/qos.py`, `test_ros2_qos_config.py` | 4 | 기존 QoS 변환·경고 test 유지 |
| 틀린 TF 설명 축약 | `tf_broadcaster.py` | 12 | runtime code diff 없음, canonical YAML/frame 문서와 일치 확인 |
| 로컬 Isaac 절대경로 주석 제거 | `tf_nameoverrides.py` | 11 | 함수·상수 diff 없음 |
| 1-call mass wrapper inline | `robots/rover.py`, `test_rover_module.py` | 20 | `apply_mass_properties` observable과 spawn orchestration test |
| quaternion 구현 재사용 | `sensors/sensor_spawner.py`, `marslab/quaternion.py` | 27 | 같은 RPY 입력의 quaternion 수치 비교 및 sensor spawn test |
| 사용하지 않는 GDAL CI 설치 제거 | security/unit workflows | 16 | clean CI에서 install·unit·mypy·audit가 GDAL 없이 동작 |
| 중복 diffuse test 제거 | `test_diffuse_fraction.py` | 20 | 더 강한 monotonic/floor/boundary test 유지 |
| materials test 중복 제거 | `test_materials.py` | 23 | 기본 albedo contract `12-20` 유지 |
| quaternion 중복 test 제거 | `test_odometry_math.py` | 61 | `test_quaternion.py`와 odometry 고유 test 모두 통과 |
| 중복 robot config test 제거 | `test_robot_config.py` | 44 | schema/config 대표 suite 통과 |
| QoS test latch 처리 단순화 | `test_ros2_qos_config.py` | 10 | 경고 1회 및 adapter contract 유지 |
| 중복 rover control test 통합 | `test_rover_control.py`, `test_ackermann.py` | 60 | 누락 validation case 이동 후 canonical suite 통과 |
| rover quaternion test 중복 제거 | `test_rover_module.py` | 31 | canonical quaternion suite와 rover spawn test 통과 |
| main-loop quaternion test 중복 제거 | `test_main_loop_structure.py` | 24 | canonical quaternion 및 main-loop structure test 통과 |
| **합계** |  | **363** | 변경 후 CPU suite·Ruff·Black·mypy 필수 |

추가 38 LOC는 다음 두 변경의 실제 동작 검증 후에만 적용한다.

- `launch/rover_state_publisher.launch.py`의 URDF sanitizer를 기존
  `robot_description_publisher.py` 경로와 공유: likely 26 LOC.
- source 문자열을 읽는 shutdown test를 실제 cleanup seam test로 교체: likely 12 LOC.

따라서 기능 유지 목표는 **검증 전 363 LOC, Isaac/ROS 관련 seam 검증 후 최대 401 LOC**다.
583 LOC의 legacy compatibility 제거와 52 LOC의 정책성 주석·fixture 정리는 이 수치에
포함하지 않는다.

### 요청 4 — Version 0.5로 가는 실제 실행 계획

아래 순서가 후속 구현자가 그대로 수행할 기본 계획이다. 각 단계는 별도 atomic commit으로
만들고 해당 단계의 검증이 통과하기 전 다음 단계로 넘어가지 않는다.

| 단계 | 구체적 변경 파일 | 완료 조건 |
|---:|---|---|
| 1. 즉시 위생 정리 | 생성 cache/build/install/log 제거, `.gitignore` 재확인, `tmp.txt` owner 판정 | source 외 생성물이 배포 후보 tree에 없고 필요한 연구 자료는 archive됨 |
| 2. CI의 명백한 결함 수정 | `.github/workflows/lint.yaml`, `security.yaml`, `unit_tests.yaml` | 존재하지 않는 `scripts/` 참조 제거; 불필요한 GDAL setup 제거; exact CI 명령이 clean checkout에서 0 |
| 3. 보수적 A 리팩토링 | 위 14개 A 작업의 production/test 파일 | 순감축 363 LOC 이상; CPU pytest, Black, Ruff, mypy 전부 0; 삭제된 test의 고유 계약이 canonical suite에 존재 |
| 4. Packaging·실행 계약 | `pyproject.toml`, `README.md`, config/asset 배포 방식, 선택한 CLI entry point | clean environment에서 설치 후 기본 config와 rover asset이 resolve되고 `--help` 실행 |
| 5. 문서·외부 asset 계약 | `README.md`, release 문서, terrain 생성/획득 절차, trajectory override | 누락 example/link 제거 또는 복구; 절대 trajectory 경로 제거; 검증용 external terrain 확정 |
| 6. CPU·security gate | 기존 unit suite, mypy, Black, Ruff, `pip-audit` | gate 4·5·6·10이 모두 PASS |
| 7. Isaac runtime gate | `isaac_python.sh main.py --usda <verified.usda>` headless와 GUI | terrain collision, rover spawn, USD composition, camera/IMU/LiDAR가 실제로 관측됨 |
| 8. ROS 2 gate | Jazzy companion launch, topics, TF, RViz, `cmd_vel` | 중복 TF publisher 없이 topic/TF tree와 rover drive가 관측됨 |
| 9. 0.5 release | `pyproject.toml`, changelog/release notes, tag/artifact | 모든 mandatory gate PASS 후에만 version을 `0.5.0`으로 설정하고 tag·artifact 발행 |

`MarsLab.html`, 연구 figure/docs, legacy compatibility C 항목은 위 기본 경로를 막지 않는다.
owner가 별도로 폐기 범위를 승인할 때만 후속 commit으로 처리한다.

## 2. Baseline and universes

| 항목 | 동결값 |
|---|---:|
| HEAD | `04f4346146900983c0eb7b02d4fad298046f3a92` |
| branch | `main` |
| submodule | `bc25f70c9abe6c34b8019ae5ec10d5b7f1c122c6` (clean) |
| tracked paths | 136 |
| frozen ordinary untracked | 14 (orchestration 6 + AGENTS guides 8) |
| code/config review universe | 118 paths, 23,353 physical LOC |
| privacy-safe ignored | 631 leaves, 356,843,049 bytes |
| unsafe root-only historical receipt | 635 leaves, 356,843,819 bytes (합계에서 제외) |
| private hidden delta | 4 leaves, 770 bytes (이름·내용 비공개) |
| report before audit | absent |

`.omo`의 이후 증가는 실행 제어 상태이며 product mutation이 아니다. 절대 경로는
`<repo>`와 `<external-root>`로 치환했고, private hidden leaf 이름과 내용은 열거나
기록하지 않았다.

## 3. Runtime asset matrix

| # | asset/consumer | 조건·source | 존재·정적 무결성 | 판정/불확실성 |
|---:|---|---|---|---|
| 1 | Terrain USDA; `main.py:479-490,558-560,639` | 모든 실행에 `--usda`; external MarsLab-Utils | repo terrain 없음; 예시 외부 경로는 감사 환경에서 미확인 | `NOT_RUN_ENV`, 공급 전 blocker. repository 누락으로 보지 않음 |
| 2 | rover root; `configs/rover_m2020.yaml:12` → `assets/robots/rover/m2020.usd` | repo, 필수 | 1,506 B, USD crate v0.9.0, sensor layer token 확인 | 존재 `PASS`, composition `REVIEW` |
| 3 | rover layers | repo, 필수 | sensor 652 B; physics 13,619 B; base 23,634,108 B; robot 4,787 B. 모두 존재, physics→base token | composition `REVIEW` |
| 4 | `rover/m2020.urdf` | submodule, ROS publication은 선택; 변환은 offline-only | clean SHA; unique GLTF 20/20 존재 | 존재 `PASS`; parser/ROS `NOT_RUN_ENV` |
| 5 | URDF mesh support | submodule | GLTF 20개 및 연관 지원 파일 존재 | 내부 buffer/texture 미파싱 `REVIEW` |
| 6 | sky images; `default.yaml:43`, renderers | repo | clear 3,304,309 B, moderate 3,129,219 B, dusty 2,847,303 B는 runtime consumer; clear.hdr 96,545 B는 supporting/unreferenced | 존재 `PASS`; decode는 `REVIEW` |
| 7 | LiDAR profiles OS1 / Example_Rotary_2D | Isaac-bundled; 3D 필수, 2D 선택 | repo path 없음, bundle version 미확인 | `NOT_RUN_ENV` |
| 8 | trajectory; `rover_m2020.yaml:40`, `main.py:255-294` | external; `trajectory_start`일 때만 사용, 기본은 `dem_center` | 로컬 4,038,239 B 존재; TUM 미파싱 | 존재 `PASS`; 절대 경로 portability `FAIL`, content `REVIEW` |
| 9 | omni/isaacsim/pxr/usdrt/rclpy | Isaac-bundled/system ROS | deferred import, repo asset 아님 | `NOT_RUN_ENV` |

## 4. Repository hygiene ledger

### 4.1 Tracked paths (136/136)

아래 각 행은 `path | verdict | 근거`다. 133개는 `RETAIN`, 세 문서만 provenance 및 최신성
확인이 필요한 `REVIEW`다. 확정적 `REMOVE-CANDIDATE`는 없다.

```text
.gitattributes | RETAIN | Git asset handling
.github/workflows/lint.yaml | RETAIN | CI source; command defect는 gate에서 수정
.github/workflows/security.yaml | RETAIN | security gate source
.github/workflows/unit_tests.yaml | RETAIN | test gate source
.gitignore | RETAIN | generated/private boundary
.gitmodules | RETAIN | required rover submodule
GT_Trajectory.md | REVIEW | 현재 trajectory 계약과 provenance 확인 필요
MarsLab.html | REVIEW | 생성된 과거 문서인지 owner 확인 필요
README.md | REVIEW | 배포 문서지만 stale/missing links 정리 필요
assets/m2020-urdf-models | RETAIN | required gitlink
assets/mars_sky/mars_sky_clear.hdr.png | RETAIN | supporting sky asset; 사용 여부 REVIEW
assets/mars_sky/mars_sky_clear.png | RETAIN | runtime sky
assets/mars_sky/mars_sky_dusty.png | RETAIN | runtime sky
assets/mars_sky/mars_sky_moderate.png | RETAIN | runtime sky
assets/robots/rover/configuration/m2020_base.usd | RETAIN | rover layer
assets/robots/rover/configuration/m2020_physics.usd | RETAIN | rover layer
assets/robots/rover/configuration/m2020_robot.usd | RETAIN | rover layer
assets/robots/rover/configuration/m2020_sensor.usd | RETAIN | rover layer
assets/robots/rover/configuration/materials/textures/M2020_Rover_Texture.jpg | RETAIN | rover texture
assets/robots/rover/m2020.usd | RETAIN | rover root
configs/default.yaml | RETAIN | canonical runtime config
configs/rover_m2020.yaml | RETAIN | canonical rover config
launch/rover_state_publisher.launch.py | RETAIN | ROS companion
marslab/__init__.py | RETAIN | package
marslab/config/__init__.py | RETAIN | package/API
marslab/config/loader.py | RETAIN | live seed behavior
marslab/config/schema/__init__.py | RETAIN | package/API
marslab/config/schema/mars_env.py | RETAIN | schema
marslab/config/schema/rendering.py | RETAIN | schema
marslab/config/schema/robot.py | RETAIN | schema
marslab/config/schema/root.py | RETAIN | schema
marslab/config/schema/ros2_bridge.py | RETAIN | schema
marslab/config/yaml_loader.py | RETAIN | loader
marslab/convert_urdf_to_usd.py | RETAIN | offline preparation
marslab/environment/__init__.py | RETAIN | package
marslab/environment/diffuse_fraction.py | RETAIN | computation
marslab/environment/light_intensity.py | RETAIN | computation
marslab/environment/sky_dome.py | RETAIN | computation
marslab/environment/sun_position.py | RETAIN | computation
marslab/fix_urdf_inertia.py | RETAIN | offline preparation
marslab/gui/__init__.py | RETAIN | package
marslab/gui/atmosphere_panel.py | RETAIN | optional GUI
marslab/isaac_python.sh | RETAIN | runtime boundary
marslab/main.py | RETAIN | entry source
marslab/quaternion.py | RETAIN | shared math
marslab/rendering/__init__.py | RETAIN | package
marslab/rendering/atmosphere_fog.py | RETAIN | renderer
marslab/rendering/render_settings.py | RETAIN | renderer
marslab/rendering/sky_renderer.py | RETAIN | renderer
marslab/rendering/sun_renderer.py | RETAIN | renderer
marslab/robots/__init__.py | RETAIN | package
marslab/robots/drive_api_setup.py | RETAIN | runtime
marslab/robots/rover.py | RETAIN | runtime
marslab/robots/rover_control.py | RETAIN | control
marslab/ros2_bridge/__init__.py | RETAIN | package/API
marslab/ros2_bridge/cmd_vel_subscriber.py | RETAIN | ROS
marslab/ros2_bridge/context.py | RETAIN | ROS
marslab/ros2_bridge/imu_noise_publisher.py | RETAIN | ROS
marslab/ros2_bridge/odometry_math.py | RETAIN | ROS math
marslab/ros2_bridge/odometry_publisher.py | RETAIN | ROS
marslab/ros2_bridge/qos.py | RETAIN | ROS QoS
marslab/ros2_bridge/rclpy_integration.py | RETAIN | ROS
marslab/ros2_bridge/robot_description_publisher.py | RETAIN | ROS
marslab/ros2_bridge/sensor_graph.py | RETAIN | graph
marslab/ros2_bridge/sensor_graph_builder.py | RETAIN | graph
marslab/ros2_bridge/tf_broadcaster.py | RETAIN | TF
marslab/ros2_bridge/tf_nameoverrides.py | RETAIN | TF
marslab/ros2_bridge/wheel_odometry_publisher.py | RETAIN | ROS
marslab/runtime/__init__.py | RETAIN | package
marslab/runtime/articulation_setup.py | RETAIN | runtime
marslab/runtime/atmosphere_boot.py | RETAIN | runtime
marslab/runtime/loop_context.py | RETAIN | runtime
marslab/runtime/main_loop.py | RETAIN | runtime
marslab/runtime/precheck.py | RETAIN | runtime
marslab/runtime/sensor_frames.py | RETAIN | runtime
marslab/sensors/__init__.py | RETAIN | package
marslab/sensors/sensor_spawner.py | RETAIN | runtime
marslab/sim/__init__.py | RETAIN | package
marslab/sim/boot.py | RETAIN | runtime boundary
marslab/sim/world_setup.py | RETAIN | runtime
pyproject.toml | RETAIN | packaging
tests/__init__.py | RETAIN | test package
tests/unit/__init__.py | RETAIN | test package
tests/unit/conftest.py | RETAIN | fixtures; obsolete exclusions REVIEW
tests/unit/test_ackermann.py | RETAIN | behavior contract
tests/unit/test_bridge_context.py | RETAIN | behavior contract
tests/unit/test_camera_info.py | RETAIN | behavior contract
tests/unit/test_camera_single_render_product.py | RETAIN | behavior contract
tests/unit/test_cmd_vel_subscriber.py | RETAIN | behavior contract
tests/unit/test_config_schema.py | RETAIN | schema contract; overlap SIMPLIFY
tests/unit/test_depth_sensor_schema.py | RETAIN | behavior contract
tests/unit/test_diffuse_fraction.py | RETAIN | behavior contract; duplicate cases SIMPLIFY
tests/unit/test_drive_api_setup.py | RETAIN | behavior contract
tests/unit/test_imu_gravity_assertion.py | RETAIN | behavior contract
tests/unit/test_lidar_runtime_override.py | RETAIN | behavior contract
tests/unit/test_light_intensity.py | RETAIN | behavior contract
tests/unit/test_loader.py | RETAIN | live legacy/seed contract; conditional retirement only
tests/unit/test_main_loop_log_once.py | RETAIN | behavior contract
tests/unit/test_main_loop_publish_odometry.py | RETAIN | behavior contract
tests/unit/test_main_loop_structure.py | RETAIN | structure checks partly reducible
tests/unit/test_mars_env_schema.py | RETAIN | schema contract
tests/unit/test_materials.py | RETAIN | 고유 surface_albedo_range 계약은 보존, 나머지는 SIMPLIFY
tests/unit/test_odometry_math.py | RETAIN | duplicate cases candidate
tests/unit/test_odometry_publisher.py | RETAIN | behavior contract
tests/unit/test_quaternion.py | RETAIN | behavior contract
tests/unit/test_rclpy_integration.py | RETAIN | behavior contract
tests/unit/test_rendering_schema.py | RETAIN | schema contract
tests/unit/test_rgbd_pointcloud2.py | RETAIN | behavior contract
tests/unit/test_robot_config.py | RETAIN | duplicate schema candidate
tests/unit/test_robot_description_url_rewrite.py | RETAIN | behavior contract
tests/unit/test_robot_drive_api_schema.py | RETAIN | behavior contract
tests/unit/test_robot_schema.py | RETAIN | behavior contract
tests/unit/test_ros2_bridge_lazy_import.py | RETAIN | import boundary
tests/unit/test_ros2_bridge_structure.py | RETAIN | structure contract
tests/unit/test_ros2_qos_config.py | RETAIN | contract; mapping overlap SIMPLIFY
tests/unit/test_rover_control.py | RETAIN | duplicate behavior candidate
tests/unit/test_rover_module.py | RETAIN | structure overlap SIMPLIFY
tests/unit/test_rover_physics_inject.py | RETAIN | behavior contract
tests/unit/test_runtime_articulation_setup.py | RETAIN | behavior contract
tests/unit/test_runtime_loop_context.py | RETAIN | behavior contract
tests/unit/test_runtime_sensor_frames.py | RETAIN | legacy alias REVIEW
tests/unit/test_runtime_shutdown_exit_code.py | RETAIN | test-for-test candidate
tests/unit/test_sensor_graph.py | RETAIN | behavior contract
tests/unit/test_sensor_graph_builder.py | RETAIN | behavior contract
tests/unit/test_sensor_graph_builder_schema.py | RETAIN | schema contract
tests/unit/test_sensor_seed.py | RETAIN | live seed contract
tests/unit/test_sensor_spawner.py | RETAIN | behavior contract
tests/unit/test_sensor_spawner_unified.py | RETAIN | behavior contract
tests/unit/test_sim_boot.py | RETAIN | behavior contract
tests/unit/test_sim_world_setup.py | RETAIN | behavior contract
tests/unit/test_sky_dome.py | RETAIN | behavior contract
tests/unit/test_sol_sun_position.py | RETAIN | behavior contract
tests/unit/test_sun_position.py | RETAIN | behavior contract
tests/unit/test_tf_broadcaster.py | RETAIN | behavior contract
tests/unit/test_tf_extrinsic_consistency.py | RETAIN | behavior contract
tests/unit/test_tf_nameoverrides.py | RETAIN | behavior contract
```

### 4.2 Frozen ordinary untracked paths (14/14)

| path | verdict | note |
|---|---|---|
| `.omo/boulder.json` | REVIEW | orchestration state |
| `.omo/drafts/marslab-unification-refactor.md` | REVIEW | planning history |
| `.omo/drafts/marslab-v0-5-readonly-audit.md` | REVIEW | current planning state |
| `.omo/plans/marslab-unification-refactor.md` | REVIEW | planning history |
| `.omo/plans/marslab-v0-5-readonly-audit.md` | REVIEW | current plan |
| `.omo/start-work/ledger.jsonl` | REVIEW | orchestration ledger |
| `AGENTS.md` | REVIEW | local agent guide |
| `marslab/config/AGENTS.md` | REVIEW | local agent guide |
| `marslab/robots/AGENTS.md` | REVIEW | local agent guide |
| `marslab/ros2_bridge/AGENTS.md` | REVIEW | local agent guide |
| `marslab/runtime/AGENTS.md` | REVIEW | local agent guide |
| `marslab/sensors/AGENTS.md` | REVIEW | local agent guide |
| `marslab/sim/AGENTS.md` | REVIEW | local agent guide |
| `tests/AGENTS.md` | REVIEW | local agent guide |

### 4.3 Ignored groups

| non-overlapping group | leaves | bytes | verdict/recovery/risk |
|---|---:|---:|---|
| `.claude/**` | 16 | 93,742 | REVIEW; provenance owner 확인, private content 미열람 |
| `.mypy_cache/**` | 4 | 22,479,072 | REMOVE-CANDIDATE; mypy 재생성, 삭제 시 다음 실행 비용만 발생 |
| `.pytest_cache/**` | 6 | 158,388 | REMOVE-CANDIDATE; pytest 재생성 |
| `.ruff_cache/**` | 90 | 94,924 | REMOVE-CANDIDATE; Ruff 재생성 |
| `build/**` | 2 | 7 | REMOVE-CANDIDATE; colcon/generated |
| `docs/**` | 7 | 40,097,631 | REVIEW; 배포 문서 provenance 확인 |
| `figure/**` | 252 | 290,077,497 | REVIEW; 연구/논문 source provenance 확인 |
| `install/**` | 12 | 49,520 | REMOVE-CANDIDATE; colcon/generated |
| `log/**` | 3 | 82,774 | REMOVE-CANDIDATE; generated logs |
| `tmp.txt` | 1 | 87,832 | REMOVE-CANDIDATE; scratch, 필요한 내용 백업 여부 확인 |
| `**/__pycache__/**` | 236 | 3,621,662 | REMOVE-CANDIDATE; Python 재생성 |
| 기타 privacy-safe ignored leaves | 2 | 0 | ignore-rule 경계 leaf; 내용 미열람 |
| **합계** | **631** | **356,843,049** | private hidden 제외 |

Unsafe root-only receipt `635/356,843,819`는 private descendant를 잘못 포함할 수 있어 합계에서
명시적으로 제외했다. 정확한 차이는 4 leaves/770 bytes다. 과거 commit `87dc9be`,
`f4d53b1`에서 삭제된 경로는 현존 cleanup 항목이 아니다.

### 4.4 Ignored docs leaf appendix (7/7)

```text
docs/colored_pointcloud.md
docs/crater_distribution_procedural_flatland.pdf
docs/crater_distribution_procedural_flatland.png
docs/frame_conventions.md
docs/odometry_ground_truth.md
docs/rock_distribution_jezero_rocky.pdf
docs/rock_distribution_jezero_rocky.png
```

## 5. Seven principles

1. Does this need to exist? → no: skip it (YAGNI)
2. Already in this codebase? → reuse it, don't rewrite
3. Stdlib does it? → use it
4. Native platform feature? → use it
5. Installed dependency? → use it
6. One line? → one line
7. Only then: the minimum that works

## 6. Complete code/config ledger (118/118)

형식은 `path | LOC | verdict | principles | evidence/alternative/risk | gross/replacement/net`이다.
`0`은 감축 주장이 없다는 뜻이다. `C`는 compatibility-retirement conditional, `D`는 other
conditional, `B`는 runtime-confirm likely다.

```text
marslab/config/__init__.py | 1 | KEEP | P7 | package marker/API | 0
marslab/config/loader.py | 53 | REVIEW | P1,P7 | live seed propagation; policy risk | 53/0/53 C
marslab/config/schema/__init__.py | 71 | KEEP | P2,P7 | public reexports | 0
marslab/config/schema/mars_env.py | 260 | KEEP | P7 | typed Pydantic boundary | 0
marslab/config/schema/rendering.py | 315 | SIMPLIFY | P1,P7 | flat→nested migrator required by current YAML; compatibility risk | 53/0/53 C
marslab/config/schema/robot.py | 1120 | SIMPLIFY | P1,P2,P7 | duplicate legacy profile validators | 25/0/25 C
marslab/config/schema/root.py | 82 | REVIEW | P1,P7 | base_config shim; external risk | 14/0/14 C
marslab/config/schema/ros2_bridge.py | 412 | KEEP | P7 | typed QoS/TF boundary | 0
marslab/config/yaml_loader.py | 188 | REVIEW | P1,P3,P7 | include/legacy normalization; external risk | 40/0/40 C
marslab/environment/__init__.py | 1 | KEEP | P7 | package marker | 0
marslab/environment/diffuse_fraction.py | 100 | SIMPLIFY | P1,P5,P7 | zenith hook public risk | 12/2/10 C
marslab/environment/light_intensity.py | 91 | KEEP | P7 | live formula | 0
marslab/environment/sky_dome.py | 93 | KEEP | P7 | live physics | 0
marslab/environment/sun_position.py | 279 | KEEP | P7 | live solar model | 0
marslab/rendering/__init__.py | 1 | KEEP | P7 | package marker | 0
marslab/rendering/atmosphere_fog.py | 51 | KEEP | P4,P7 | native Kit feature | 0
marslab/rendering/render_settings.py | 58 | KEEP | P4,P7 | native Kit feature | 0
marslab/rendering/sky_renderer.py | 86 | KEEP | P4,P7 | USD live consumer | 0
marslab/rendering/sun_renderer.py | 123 | KEEP | P2,P4,P7 | shared clamp/USD | 0
marslab/robots/__init__.py | 1 | KEEP | P7 | marker | 0
marslab/robots/drive_api_setup.py | 193 | KEEP | P2,P4,P7 | native DriveAPI lifecycle | 0
marslab/robots/rover.py | 620 | SIMPLIFY | P1,P2,P6,P7 | mass wrapper safe; spawn fallback compatibility | 21/1/20 A + 4/2/2 C
marslab/robots/rover_control.py | 144 | KEEP | P5,P7 | live Ackermann | 0
marslab/ros2_bridge/__init__.py | 59 | REVIEW | P1,P2,P7 | broad public reexports | 0
marslab/ros2_bridge/cmd_vel_subscriber.py | 82 | KEEP | P4,P7 | native rclpy callback | 0
marslab/ros2_bridge/context.py | 43 | KEEP | P7 | minimum context | 0
marslab/ros2_bridge/imu_noise_publisher.py | 123 | KEEP | P2,P5,P7 | live seeded publisher | 0
marslab/ros2_bridge/odometry_math.py | 91 | KEEP | P2,P5,P7 | shared live math | 0
marslab/ros2_bridge/odometry_publisher.py | 205 | KEEP | P2,P4,P7 | publisher/TF | 0
marslab/ros2_bridge/qos.py | 183 | SIMPLIFY | P1,P7 | test-only reset hook | 4/0/4 A
marslab/ros2_bridge/rclpy_integration.py | 311 | KEEP | P2,P4,P7 | bridge composition | 0
marslab/ros2_bridge/robot_description_publisher.py | 316 | REVIEW | P1,P3,P4,P7 | regex/legacy rename external risk | 0
marslab/ros2_bridge/sensor_graph.py | 320 | REVIEW | P1,P2,P4,P7 | legacy reexports public risk | 0
marslab/ros2_bridge/sensor_graph_builder.py | 496 | KEEP | P2,P4,P7 | distinct builders | 0
marslab/ros2_bridge/tf_broadcaster.py | 215 | SIMPLIFY | P1,P2,P7 | stale duplicated docs | 16/4/12 A
marslab/ros2_bridge/tf_nameoverrides.py | 162 | SIMPLIFY | P1,P7 | machine-specific prose | 15/4/11 A
marslab/ros2_bridge/wheel_odometry_publisher.py | 172 | KEEP | P2,P5,P7 | live publisher | 0
marslab/runtime/__init__.py | 7 | KEEP | P7 | exports | 0
marslab/runtime/articulation_setup.py | 175 | KEEP | P2,P4,P7 | ordered lifecycle | 0
marslab/runtime/atmosphere_boot.py | 224 | REVIEW | P1,P2,P7 | seed call live | 6/0/6 C
marslab/runtime/loop_context.py | 160 | KEEP | P2,P7 | live factory | 0
marslab/runtime/main_loop.py | 777 | REVIEW | P1,P2,P7 | composition views test-only but public risk | 116/0/116 C
marslab/runtime/precheck.py | 74 | KEEP | P2,P7 | bounded prechecks | 0
marslab/runtime/sensor_frames.py | 120 | REVIEW | P1,P7 | legacy lidar alias | 6/1/5 C
marslab/sensors/__init__.py | 17 | KEEP | P2,P7 | unified facade | 0
marslab/sensors/sensor_spawner.py | 657 | SIMPLIFY | P1,P2,P7 | duplicate quaternion; legacy profile/alias | 30/3/27 A + 26/5/21 C
marslab/sim/__init__.py | 13 | KEEP | P2,P7 | exports | 0
marslab/sim/boot.py | 46 | KEEP | P4,P7 | sole SimulationApp boundary | 0
marslab/sim/world_setup.py | 73 | KEEP | P4,P7 | native world/gravity | 0
launch/rover_state_publisher.launch.py | 224 | MERGE | P2,P3,P7 | sanitizer duplicates publisher converter; runtime confirm | 46/20/26 B
marslab/__init__.py | 1 | KEEP | P7 | marker | 0
marslab/convert_urdf_to_usd.py | 325 | KEEP | P3,P4,P7 | one-shot preparation | 0
marslab/fix_urdf_inertia.py | 229 | KEEP | P3,P7 | one-shot preparation | 0
marslab/gui/__init__.py | 1 | KEEP | P7 | marker | 0
marslab/gui/atmosphere_panel.py | 228 | KEEP | P4,P7 | optional GUI | 0
marslab/isaac_python.sh | 138 | KEEP | P3,P4,P7 | ABI boundary | 0
marslab/main.py | 879 | KEEP | P2,P4,P7 | sole orchestrator | 0
marslab/quaternion.py | 229 | KEEP | P2,P5,P7 | shared numerical helpers | 0
.github/workflows/lint.yaml | 26 | SIMPLIFY | P1,P7 | missing scripts path; correctness fix, no net claim | 2/2/0
.github/workflows/security.yaml | 27 | SIMPLIFY | P1,P5,P7 | unnecessary GDAL setup | 8/0/8 A
.github/workflows/unit_tests.yaml | 41 | SIMPLIFY | P1,P5,P7 | duplicate GDAL setup | 8/0/8 A
configs/default.yaml | 53 | SIMPLIFY | P1,P7 | flat keys force migration shim | 3/5/-2 C
configs/rover_m2020.yaml | 349 | SIMPLIFY | P1,P6,P7 | stale/nonportable prose/defaults | 42/11/31 D
tests/__init__.py | 1 | KEEP | P7 | test package | 0
tests/unit/__init__.py | 1 | KEEP | P7 | test package | 0
tests/unit/conftest.py | 207 | REVIEW | P1,P7 | obsolete exclusions policy | 21/0/21 D
tests/unit/test_ackermann.py | 261 | KEEP | P7 | distinct control contract | 0
tests/unit/test_bridge_context.py | 46 | KEEP | P7 | context contract | 0
tests/unit/test_camera_info.py | 440 | KEEP | P7 | camera contract | 0
tests/unit/test_camera_single_render_product.py | 232 | KEEP | P7 | render-product contract | 0
tests/unit/test_cmd_vel_subscriber.py | 147 | KEEP | P7 | subscriber behavior | 0
tests/unit/test_config_schema.py | 538 | SIMPLIFY | P1,P2,P7 | legacy rendering overlap | 59/0/59 C
tests/unit/test_depth_sensor_schema.py | 183 | KEEP | P7 | depth schema | 0
tests/unit/test_diffuse_fraction.py | 111 | SIMPLIFY | P1,P2,P7 | duplicate cases plus conditional hook | 20/0/20 A + 10/0/10 C
tests/unit/test_drive_api_setup.py | 280 | KEEP | P7 | DriveAPI behavior | 0
tests/unit/test_imu_gravity_assertion.py | 474 | KEEP | P7 | gravity contract | 0
tests/unit/test_lidar_runtime_override.py | 202 | KEEP | P7 | override behavior | 0
tests/unit/test_light_intensity.py | 155 | KEEP | P7 | formula behavior | 0
tests/unit/test_loader.py | 62 | REMOVE-CANDIDATE | P1,P7 | only if live seed compatibility retired | 62/0/62 C
tests/unit/test_main_loop_log_once.py | 101 | KEEP | P7 | log-once behavior | 0
tests/unit/test_main_loop_publish_odometry.py | 189 | KEEP | P7 | publish behavior | 0
tests/unit/test_main_loop_structure.py | 311 | SIMPLIFY | P1,P2,P7 | brittle/duplicate structure checks | 24/0/24 A + 70/0/70 C
tests/unit/test_mars_env_schema.py | 110 | KEEP | P7 | schema behavior | 0
tests/unit/test_materials.py | 32 | SIMPLIFY | P1,P2,P7 | lines 12-20의 고유 MarsEnvConfig default surface_albedo_range 계약은 보존 | 23/0/23 A
tests/unit/test_odometry_math.py | 170 | SIMPLIFY | P1,P2,P7 | duplicate cases | 61/0/61 A
tests/unit/test_odometry_publisher.py | 277 | KEEP | P7 | publisher behavior | 0
tests/unit/test_quaternion.py | 342 | KEEP | P7 | numeric behavior | 0
tests/unit/test_rclpy_integration.py | 365 | KEEP | P7 | integration seams | 0
tests/unit/test_rendering_schema.py | 107 | KEEP | P7 | schema behavior | 0
tests/unit/test_rgbd_pointcloud2.py | 460 | KEEP | P7 | data conversion | 0
tests/unit/test_robot_config.py | 44 | REMOVE-CANDIDATE | P1,P2,P7 | duplicate schema assertions | 44/0/44 A
tests/unit/test_robot_description_url_rewrite.py | 299 | KEEP | P7 | rewrite behavior | 0
tests/unit/test_robot_drive_api_schema.py | 128 | KEEP | P7 | schema behavior | 0
tests/unit/test_robot_schema.py | 132 | KEEP | P7 | schema behavior | 0
tests/unit/test_ros2_bridge_lazy_import.py | 47 | KEEP | P7 | import boundary | 0
tests/unit/test_ros2_bridge_structure.py | 154 | KEEP | P7 | structure contract | 0
tests/unit/test_ros2_qos_config.py | 455 | SIMPLIFY | P1,P2,P7 | duplicate mapping cases | 12/2/10 A
tests/unit/test_rover_control.py | 61 | REMOVE-CANDIDATE | P1,P2,P7 | redundant smoke; retain one assertion | 61/1/60 A
tests/unit/test_rover_module.py | 226 | SIMPLIFY | P1,P2,P7 | structure overlap and legacy fallback | 31/0/31 A + 22/0/22 C
tests/unit/test_rover_physics_inject.py | 532 | KEEP | P7 | physics contract | 0
tests/unit/test_runtime_articulation_setup.py | 148 | KEEP | P7 | runtime setup | 0
tests/unit/test_runtime_loop_context.py | 189 | KEEP | P7 | context behavior | 0
tests/unit/test_runtime_sensor_frames.py | 135 | REVIEW | P1,P7 | legacy lidar alias contract | 17/0/17 C
tests/unit/test_runtime_shutdown_exit_code.py | 37 | REMOVE-CANDIDATE | P1,P2,P7 | test-for-test; replace behavior assertion | 37/25/12 B
tests/unit/test_sensor_graph.py | 199 | KEEP | P7 | graph contract | 0
tests/unit/test_sensor_graph_builder.py | 202 | KEEP | P7 | builder contract | 0
tests/unit/test_sensor_graph_builder_schema.py | 148 | KEEP | P7 | schema contract | 0
tests/unit/test_sensor_seed.py | 177 | KEEP | P7 | live seed behavior | 0
tests/unit/test_sensor_spawner.py | 305 | KEEP | P7 | spawner behavior | 0
tests/unit/test_sensor_spawner_unified.py | 231 | KEEP | P7 | unified path contract | 0
tests/unit/test_sim_boot.py | 94 | KEEP | P7 | boot boundary | 0
tests/unit/test_sim_world_setup.py | 162 | KEEP | P7 | world setup | 0
tests/unit/test_sky_dome.py | 86 | KEEP | P7 | sky computation | 0
tests/unit/test_sol_sun_position.py | 188 | KEEP | P7 | sol behavior | 0
tests/unit/test_sun_position.py | 51 | KEEP | P7 | solar behavior | 0
tests/unit/test_tf_broadcaster.py | 312 | KEEP | P7 | TF behavior | 0
tests/unit/test_tf_extrinsic_consistency.py | 452 | KEEP | P7 | frame consistency | 0
tests/unit/test_tf_nameoverrides.py | 141 | KEEP | P7 | override behavior | 0
```

구성별 reconciliation은 `9+5+5+4+14+7+2+3+9+55+3+2=118`, LOC는
`2502+564+319+958+2778+1537+674+132+2254+11139+94+402=23,353`이다.

## 7. Disjoint LOC interval ledger

| ID | unique interval | gross | repl | net | class |
|---|---|---:|---:|---:|---|
| A1 | `qos.py:68-71` | 4 | 0 | 4 | conservative |
| A2 | `tf_broadcaster.py:13-20,35-42` | 16 | 4 | 12 | conservative |
| A3 | `tf_nameoverrides.py:15-29` | 15 | 4 | 11 | conservative |
| A4 | `rover.py:466-485,606` | 21 | 1 | 20 | conservative |
| A5 | `sensor_spawner.py:309-336,513,620` + replacement import | 30 | 3 | 27 | conservative |
| A6 | `security.yaml:19-26`; `unit_tests.yaml:19-22,35-38` | 16 | 0 | 16 | conservative |
| A7 | `test_diffuse_fraction.py:36-41,44-47,78-87` | 20 | 0 | 20 | conservative |
| A8 | `test_materials.py:1-11,21-32` | 23 | 0 | 23 | conservative; lines 12-20 보존 |
| A9 | `test_odometry_math.py:18-78` | 61 | 0 | 61 | conservative |
| A10 | `test_robot_config.py:1-44` | 44 | 0 | 44 | conservative |
| A11 | `test_ros2_qos_config.py:232-243` | 12 | 2 | 10 | conservative |
| A12 | `test_rover_control.py:1-61` | 61 | 1 | 60 | conservative |
| A13 | `test_rover_module.py:14-44` | 31 | 0 | 31 | conservative |
| A14 | `test_main_loop_structure.py:159-182` | 24 | 0 | 24 | conservative |
| **A** | **합계** | **378** | **15** | **363** | behavior-preserving |
| B1 | `launch/rover_state_publisher.launch.py:45-90` | 46 | 20 | 26 | runtime confirm |
| B2 | `test_runtime_shutdown_exit_code.py:1-37` | 37 | 25 | 12 | runtime confirm |
| **B** | **추가/누적** | **83** | **45** | **38 / 401** | likely |
| C1 | `loader.py:1-53`; `atmosphere_boot.py:29,145-149`; `test_loader.py:1-62` | 121 | 0 | 121 | live seed policy REVIEW |
| C2 | `rendering.py:256-308`; `default.yaml:51-53`; `test_config_schema.py:293-351` | 115 | 5 | 110 | legacy |
| C3 | `robot.py:902-918,959-962,976-979`; `sensor_spawner.py:152-172` | 46 | 4 | 42 | legacy |
| C4 | `sensor_spawner.py:497-501`; `sensor_frames.py:43-48`; test `45-61` | 28 | 2 | 26 | legacy |
| C5 | `root.py:69-82`; `yaml_loader.py:148-188` | 54 | 0 | 54 | legacy |
| C6 | `main_loop.py:154-234,312-350`; structure test `242-311` | 186 | 0 | 186 | legacy |
| C7 | diffuse hook + test | 21 | 1 | 20 | legacy |
| C8 | rover fallback + test | 26 | 2 | 24 | legacy |
| **C** | **합계** | **597** | **14** | **583** | compatibility conditional |
| D1 | `conftest.py:14-34` | 21 | 0 | 21 | policy |
| D2 | `rover_m2020.yaml:1-9,44-54,143-147,197-213` | 42 | 11 | 31 | policy |
| **D** | **합계** | **63** | **11** | **52** | other conditional |

모든 interval은 서로 겹치지 않는다. A만 보수적 기능 유지 합계이고, B는 실제 runtime 확인
후 더한다. C와 D는 정책/호환성 결정 전에는 감축 약속으로 사용하지 않는다.

## 8. Version 0.5 gate matrix

| # | gate | status | evidence/blocker | future completion |
|---:|---|---|---|---|
| 1 | metadata/version | FAIL | `pyproject` 0.1.0 | 0.5 metadata/tag/release |
| 2 | installation contract | FAIL | repo-root assets/config package-data/checkout contract 및 CLI 없음 | clean build/install 후 asset·entry inspection |
| 3 | dependency declarations | FAIL | Isaac/ROS/GDAL external contract 불완전 | dependency/prerequisite reconciliation |
| 4 | CI lint | FAIL | absent `scripts/` 참조 | path 수정 후 exact Black/Ruff |
| 5 | CI unit/type | NOT_RUN_ENV | 전체 실행 금지 | clean env에서 `pytest tests/unit -q && mypy` |
| 6 | security | NOT_RUN_ENV | audit 실행 금지 | `pip-audit --desc` |
| 7 | docs/examples/links | FAIL | 두 example YAML, LICENSE, THIRD_PARTY, CLAUDE 문서들, work log 누락; v1.0 서술 | 링크/버전 전수 정합 |
| 8 | submodule setup | PASS | clean pinned SHA와 recursive clone 안내 | 계속 고정 |
| 9 | external terrain contract | PASS | CLI/README가 외부 USDA 계약 설명 | 실제 runtime은 gate 11 |
| 10 | CPU test surface | NOT_RUN_ENV | 52 test modules, suite 미실행 | CPU suite receipt |
| 11 | Isaac/GPU QA | NOT_RUN_ENV | Isaac 5.x/RTX/terrain 필요 | headless와 GUI smoke |
| 12 | ROS2/RViz QA | NOT_RUN_ENV | Jazzy/bridge 필요 | topic/TF/RViz scenario |
| 13 | release notes/changelog | FAIL | 없음 | 0.5 notes/changelog |
| 14 | distribution entry point | FAIL | `project.scripts` 없음 | installed CLI smoke |

따라서 overall은 **NOT_READY**다. mandatory gate 하나라도 `FAIL` 또는 `NOT_RUN_ENV`면
`READY`가 될 수 없다.

## 9. Dependency-ordered remediation roadmap

문서 앞의 **“요청 4 — Version 0.5로 가는 실제 실행 계획”**이 authoritative roadmap이다.
의존성 관계는 다음과 같다.

```text
generated-file cleanup
        │
        ├── CI path/GDAL fixes ──┐
        └── conservative A refactor ─┤
                                    ▼
                         packaging + CLI contract
                                    │
                         docs + external USDA contract
                                    │
                   CPU/type/lint/security gates PASS
                                    │
                         Isaac headless + GUI PASS
                                    │
                           ROS2/TF/RViz PASS
                                    │
                    version 0.5.0 + notes + tag/artifact
```

기본 0.5 범위에는 A의 363 LOC 감축만 넣는다. B의 추가 38 LOC는 실제 runtime seam을
검증하면서 포함하고, C의 583 LOC와 D의 52 LOC는 public config compatibility 및 연구
자료 보존 정책이 별도로 승인되기 전에는 release scope에 넣지 않는다.

## 10. Uncertainties and blockers

- 외부 terrain USDA가 제공되지 않아 stage/mesh/collision 의미론을 확인하지 못했다.
- USD crate/layer는 존재하지만 Isaac/USD composition을 실행하지 않아 PASS가 아니다.
- LiDAR profile의 정확한 Isaac bundle/version을 실행 환경에서 확인해야 한다.
- trajectory는 로컬에 있으나 절대 경로이고 TUM 내용은 파싱하지 않았다.
- ignored docs/figure/.claude 자료는 owner provenance 없이는 삭제할 수 없다.
- seed propagation은 실제 동작이다. 제거 후보가 아니라 명시적 compatibility 정책에
  종속된 `REVIEW`다.

## 11. Bounded command receipts

모든 command의 cwd는 `<repo>`다. 아래 version은 executor가 실제 receipt에 남긴 값만
기록했다. version을 별도로 캡처하지 않은 POSIX/coreutils 및 Python 명령은 임의의
version을 만들지 않고 `not captured`로 명시한다.

| exact command | tool/version | exit | bounded relevant output | interpretation |
|---|---|---:|---|---|
| `git rev-parse HEAD` | Git 2.43.0 | 0 | `04f4346146900983c0eb7b02d4fad298046f3a92` | 감사 기준 HEAD |
| `git diff --no-ext-diff` | Git 2.43.0 | 0 | empty | tracked product diff 없음 |
| `git diff --cached --no-ext-diff` | Git 2.43.0 | 0 | empty | staged diff 없음 |
| `git status --short --untracked-files=all` | Git 2.43.0 | 0 | frozen 14 paths; 최종에는 report 1개만 추가 | dirty baseline 보존 |
| `git submodule status` | Git 2.43.0 | 0 | ` bc25f70c9abe6c34b8019ae5ec10d5b7f1c122c6 assets/m2020-urdf-models` | pinned submodule clean |
| `git ls-files` | Git 2.43.0 | 0 | 136 paths | tracked universe |
| `git ls-files -o --exclude-standard` | Git 2.43.0 | 0 | baseline 14 paths | ordinary-untracked universe |
| `git ls-files -o -i --exclude-standard \| wc -l` | Git 2.43.0 + wc, wc version not captured | 0 | `661` | privacy filtering 전 raw ignored entries |
| `git ls-files -o -i --exclude-standard -z \| while IFS= read -r -d '' p; do case "/$p/" in */.omc/*\|*/.codex/*\|*/.codegraph/*) continue;; esac; printf '%s\0' "$p"; done \| xargs -0 -r stat -c '%s %n' \| awk '{sum+=$1; n++} END{print n, sum}'` | Git 2.43.0 + shell/xargs/stat/awk, ancillary versions not captured | 0 | `631 356843049` | private path segments 제외 privacy-safe ignored universe |
| `find assets -type f \( -name '*.usd' -o -name '*.usda' -o -name '*.usdc' \) -print` | find, version not captured | 0 | rover USD 5개, terrain USDA 0개 | local USD extension inventory |
| `file assets/robots/rover/m2020.usd` | file 5.45 | 0 | USD crate v0.9.0 | container 존재만 확인 |
| `strings assets/robots/rover/m2020.usd` | strings, version not captured | 0 | `configuration/m2020_sensor.usd` | root→sensor token; composition 증명 아님 |
| `strings assets/robots/rover/configuration/m2020_physics.usd` | strings, version not captured | 0 | `m2020_base.usd` | physics→base token; composition 증명 아님 |
| `python3 -B -c 'import pathlib,xml.etree.ElementTree as ET; p=pathlib.Path("assets/m2020-urdf-models/rover/m2020.urdf"); root=ET.parse(p).getroot(); refs=sorted({e.attrib["filename"] for e in root.iter() if "filename" in e.attrib and e.attrib["filename"].lower().endswith(".gltf")}); missing=[r for r in refs if not (p.parent / r).resolve().is_file()]; print(f"{len(refs)-len(missing)}/{len(refs)} PRESENT")'` | Python, version not captured | 0 | `20/20 PRESENT` | 재현 가능한 URDF unique GLTF 존재 검사; GLTF 내부는 미검증 |
| `ls -l assets/mars_sky` | ls, version not captured | 0 | clear 3,304,309 B; moderate 3,129,219 B; dusty 2,847,303 B; clear.hdr 96,545 B | sky asset 네 개 존재 |
| `test -f <external-root>/TrajectoryComposer/out/jezero_habitat_ellipse_orbit/trajectory.tum` | shell builtin | 0 | no stdout | configured trajectory 현재 존재 |
| `stat -c '%s' <external-root>/TrajectoryComposer/out/jezero_habitat_ellipse_orbit/trajectory.tum` | stat, version not captured | 0 | `4038239` | trajectory 크기; TUM 내용은 미파싱 |

실행하지 않은 것: tests, build/install, `pip-audit`, URDF conversion, Isaac, ROS, RViz.

## 12. Coverage reconciliation

- tracked hygiene: 133 RETAIN + 3 REVIEW = 136.
- frozen ordinary untracked: 6 `.omo` + 8 AGENTS guides = 14.
- ignored: 631 leaves/356,843,049 bytes; unsafe receipt와 delta 산술
  `635-4=631`, `356,843,819-770=356,843,049`.
- runtime matrix: 9 exhaustive rows.
- code/config: 118 rows/23,353 LOC.
- LOC: A `378-15=363`; B `83-45=38`, cumulative `401`; C `597-14=583`;
  D `63-11=52`.
- release: 7 FAIL + 5 NOT_RUN_ENV + 2 PASS = 14, overall NOT_READY.

## 13. Final mutation proof

보고서 작성 직후의 bounded Git 비교에서 tracked diff와 staged diff는 비어 있었다.
동결 시점의 ordinary-untracked는 `.omo` 6개와 AGENTS guide 8개, 합계 14개였으며 최종
시점에도 이 14개가 동일하게 남아 있다. post-baseline `.omo` 추가는 없다. 현재 ordinary
untracked는 **frozen 14 + 이 보고서 1개**뿐이다. 따라서 허용된 실행 산출물은 이
`MARSLAB_V0_5_READINESS_AUDIT.md` 하나다. 독립 bounded 재계산으로 privacy-safe ignored
합계가 **631 leaves/356,843,049 bytes**로 유지됨을 확인했다.

## Appendix A. Privacy-safe figure leaf ledger (252/252)

모든 행의 verdict는 `REVIEW`다. 논문/연구 자료 provenance와 재생성 가능성을 owner가
확인하기 전에는 삭제하지 않는다.

```text
figure/0_최초terrain구현.png
figure/1_화성조명및대기구현.png
figure/2_테스트용로버올리기.png
figure/3_로버_카메라_rqt.png
figure/fig03_jezero1.png
figure/fig03_jezero2.png
figure/fig03_main_crater1.png
figure/fig03_main_crater2.png
figure/fig03_marsbase1.png
figure/fig03_marsbase2.png
figure/fig03_marscanyon02.png
figure/fig03_marscanyon1.png
figure/fig04_rockyscene.png
figure/fig05_procedural_crater.png
figure/fig06_azimuth360_elevation13.png
figure/fig06_azimuth70_elevation13.png
figure/fig1_depth.png
figure/fig1_goal.png
figure/fig1_lidar.png
figure/fig1_rgb.png
figure/figure/fig01/base.png
figure/figure/fig01/base_matching.png
figure/figure/fig01/fig1_depth.png
figure/figure/fig01/fig1_goal.png
figure/figure/fig01/fig1_lidar.png
figure/figure/fig01/fig1_lidar_slam.png
figure/figure/fig01/fig1_rgb.png
figure/figure/fig02/fig02_depth.png
figure/figure/fig02/fig02_lidar.png
figure/figure/fig02/fig02_main_scene.png
figure/figure/fig02/fig02_rgb.png
figure/figure/fig02/fig2_rover.png
figure/figure/fig02/isaac.jpeg
figure/figure/fig02/isaac_upscaled.png
figure/figure/fig02/ros2.png
figure/figure/fig02/ros2.webp
figure/figure/fig02/ros2_upscaled.png
figure/figure/fig03/fig03_jezero1.png
figure/figure/fig03/fig03_jezero2.png
figure/figure/fig03/fig03_main_crater1.png
figure/figure/fig03/fig03_main_crater2.png
figure/figure/fig03/fig03_marsbase1.png
figure/figure/fig03/fig03_marsbase2.png
figure/figure/fig03/fig03_marscanyon02.png
figure/figure/fig03/fig03_marscanyon1.png
figure/figure/fig04/fig04_rockyscene.png
figure/figure/fig04/jezero_rock_map.png
figure/figure/fig05/fig05_procedural_crater.png
figure/figure/fig05/jezero_crater_map.png
figure/figure/fig06/fig06_azimuth360_elevation13.png
figure/figure/fig06/fig06_azimuth70_elevation13.png
figure/figure/fig07/fig07_tau03.png
figure/figure/fig07/fig07_tau03_view.png
figure/figure/fig07/fig07_tau10.png
figure/figure/fig07/fig07_tau10_view.png
figure/figure/fig07/fig07_tau20.png
figure/figure/fig07/fig07_tau20_view.png
figure/figure/fig07/fig07_tau30.png
figure/figure/fig07/fig07_tau30_view.png
figure/figure/fig07/fig07_tau45.png
figure/figure/fig07/fig07_tau45_view.png
figure/figure/fig07/fig07_tau60.png
figure/figure/fig07/fig07_tau60_view.png
figure/figure/fig08/gt_gc.png
figure/figure/fig08/gt_habitat.png
figure/figure/fig08/gt_mc.png
figure/figure/fig08/mola_gc_clean.png
figure/figure/fig08/mola_habitat_clean.png
figure/figure/fig08/mola_mc_clean.png
figure/figure/fig08/orb_habitat_tau05_clean.png
figure/figure/fig08/orb_habitat_tau60_clean.png
figure/figure/fig08/orb_mc_tau05_clean.png
figure/figure/fig08/rtab_gc_tau05_clean.png
figure/figure/fig08/rtab_gc_tau60_clean.png
figure/figure/fig08/rtab_habitat_tau05_clean.png
figure/figure/fig08/rtab_habitat_tau60_clean.png
figure/figure/fig08/rtab_mc_tau05_clean.png
figure/figure/fig08/rtab_mc_tau60_clean.png
figure/figure/fig11/base.png
figure/figure/fig11/base_matching.png
figure/figure/fig11/footprint_overview.png
figure/figure/fig11/starship.png
figure/figure/fig11/starship_matching.png
figure/figure/fig11/vpr_traj_clean.png
figure/figure/fig8_new/mola_base.png
figure/figure/fig8_new/mola_base_clean.png
figure/figure/fig8_new/mola_canyon.png
figure/figure/fig8_new/mola_canyon_clean.png
figure/figure/fig8_new/mola_crater.png
figure/figure/fig8_new/mola_crater_clean.png
figure/figure/fig8_new/orb_base.png
figure/figure/fig8_new/orb_base_clean.png
figure/figure/fig8_new/rtab_canyon.png
figure/figure/fig8_new/rtab_canyon_clean.png
figure/figure/fig8_new/rtab_crater.png
figure/figure/fig8_new/rtab_crater_clean.png
figure/figure/fig_dust.tex
figure/figure/fig_environment_group.tex
figure/figure/fig_overview.tex
figure/figure/fig_pipeline.tex
figure/figure/fig_pipeline.tex.bak-1781557612
figure/figure/fig_rock.tex
figure/figure/fig_ros2_topics.tex
figure/figure/fig_runtime_slam_page.tex
figure/figure/fig_scenes.tex
figure/figure/fig_slam_gt.tex
figure/figure/fig_slam_maps.tex
figure/figure/fig_slam_traj.tex
figure/figure/fig_sun.tex
figure/figure/fig_vpr.tex
figure/mola_base.png
figure/mola_canyon.png
figure/mola_crater.png
figure/orb_base.png
figure/rtab_canyon.png
figure/rtab_crater.png
figure/스크린샷 2026-04-23 22-57-56.png
figure/스크린샷 2026-04-23 22-58-24.png
figure/스크린샷 2026-04-26 03-05-49.png
figure/스크린샷 2026-04-26 16-52-28.png
figure/스크린샷 2026-04-26 18-24-18.png
figure/스크린샷 2026-04-26 18-24-33.png
figure/스크린샷 2026-04-26 18-24-39.png
figure/스크린샷 2026-04-26 20-45-58.png
figure/스크린샷 2026-04-26 20-46-42.png
figure/스크린샷 2026-04-26 20-47-00.png
figure/스크린샷 2026-04-26 21-33-54.png
figure/스크린샷 2026-04-27 11-00-36.png
figure/스크린샷 2026-04-27 12-56-47.png
figure/스크린샷 2026-04-27 13-20-40.png
figure/스크린샷 2026-04-27 14-02-50.png
figure/스크린샷 2026-04-27 14-03-18.png
figure/스크린샷 2026-04-27 14-28-42.png
figure/스크린샷 2026-04-27 16-29-36.png
figure/스크린샷 2026-04-27 16-40-16.png
figure/스크린샷 2026-04-27 18-09-54.png
figure/스크린샷 2026-04-27 20-04-00.png
figure/스크린샷 2026-04-27 22-11-21.png
figure/스크린샷 2026-04-27 22-11-30.png
figure/스크린샷 2026-04-27 22-43-04.png
figure/스크린샷 2026-04-27 22-46-23.png
figure/스크린샷 2026-04-27 23-16-26.png
figure/스크린샷 2026-04-27 23-17-02.png
figure/스크린샷 2026-04-27 23-17-04.png
figure/스크린샷 2026-04-28 14-12-13.png
figure/스크린샷 2026-04-28 15-15-49.png
figure/스크린샷 2026-04-28 15-36-13.png
figure/스크린샷 2026-04-28 15-56-12.png
figure/스크린샷 2026-04-28 19-17-10.png
figure/스크린샷 2026-04-28 19-17-45.png
figure/스크린샷 2026-04-28 19-42-11.png
figure/스크린샷 2026-04-29 15-30-37.png
figure/스크린샷 2026-04-29 16-13-17.png
figure/스크린샷 2026-04-30 02-40-29.png
figure/스크린샷 2026-04-30 08-46-48.png
figure/스크린샷 2026-04-30 08-46-59.png
figure/스크린샷 2026-04-30 08-47-38.png
figure/스크린샷 2026-04-30 08-56-40.png
figure/스크린샷 2026-05-04 01-25-38.png
figure/스크린샷 2026-05-04 01-25-46.png
figure/스크린샷 2026-05-04 01-34-29.png
figure/스크린샷 2026-05-05 22-26-38.png
figure/스크린샷 2026-05-05 22-26-44.png
figure/스크린샷 2026-05-05 22-35-12.png
figure/스크린샷 2026-05-05 22-35-18.png
figure/스크린샷 2026-05-05 22-51-37.png
figure/스크린샷 2026-05-05 22-52-06.png
figure/스크린샷 2026-05-06 20-50-43.png
figure/스크린샷 2026-05-06 21-24-25.png
figure/스크린샷 2026-05-06 21-44-26.png
figure/스크린샷 2026-05-06 21-53-18.png
figure/스크린샷 2026-05-06 21-55-44.png
figure/스크린샷 2026-05-06 22-01-33.png
figure/스크린샷 2026-05-06 22-46-07.png
figure/스크린샷 2026-05-06 22-47-23.png
figure/스크린샷 2026-05-06 22-53-58.png
figure/스크린샷 2026-05-06 22-54-18.png
figure/스크린샷 2026-05-07 08-53-08.png
figure/스크린샷 2026-05-07 08-55-55.png
figure/스크린샷 2026-05-09 17-25-31.png
figure/스크린샷 2026-05-09 18-04-29.png
figure/스크린샷 2026-05-09 23-54-21.png
figure/스크린샷 2026-05-13 00-35-57.png
figure/스크린샷 2026-05-13 06-05-14.png
figure/스크린샷 2026-05-14 08-49-15.png
figure/스크린샷 2026-05-14 08-49-39.png
figure/스크린샷 2026-05-14 09-11-59.png
figure/스크린샷 2026-05-14 11-01-33.png
figure/스크린샷 2026-05-15 15-01-41.png
figure/스크린샷 2026-05-15 15-02-49.png
figure/스크린샷 2026-05-15 15-27-41.png
figure/스크린샷 2026-05-20 19-54-52.png
figure/스크린샷 2026-05-20 19-56-14.png
figure/스크린샷 2026-05-20 19-57-21.png
figure/스크린샷 2026-05-20 23-42-07.png
figure/스크린샷 2026-05-21 23-40-38.png
figure/스크린샷 2026-05-22 00-02-24.png
figure/스크린샷 2026-05-22 03-58-47.png
figure/스크린샷 2026-05-22 08-00-02.png
figure/스크린샷 2026-05-22 19-33-11.png
figure/스크린샷 2026-05-22 19-43-53.png
figure/스크린샷 2026-05-22 19-47-42.png
figure/스크린샷 2026-05-22 19-58-50.png
figure/스크린샷 2026-05-23 17-09-50.png
figure/스크린샷 2026-05-24 14-04-33.png
figure/스크린샷 2026-05-24 14-08-11.png
figure/스크린샷 2026-05-24 14-11-00.png
figure/스크린샷 2026-05-24 15-20-48.png
figure/스크린샷 2026-05-24 16-41-22.png
figure/스크린샷 2026-05-24 20-49-27.png
figure/스크린샷 2026-05-26 18-19-38.png
figure/스크린샷 2026-05-26 18-19-51.png
figure/스크린샷 2026-05-26 18-20-01.png
figure/스크린샷 2026-05-26 18-34-40.png
figure/스크린샷 2026-05-27 16-58-37.png
figure/스크린샷 2026-05-29 19-29-05.png
figure/스크린샷 2026-06-07 23-49-08.png
figure/스크린샷 2026-06-09 01-35-46.png
figure/스크린샷 2026-06-11 13-48-31.png
figure/스크린샷 2026-06-12 16-48-31.png
figure/스크린샷 2026-06-12 17-32-32.png
figure/스크린샷 2026-06-12 17-32-42.png
figure/스크린샷 2026-06-12 21-26-52.png
figure/스크린샷 2026-06-12 21-27-05.png
figure/스크린샷 2026-06-12 21-27-35.png
figure/스크린샷 2026-06-13 00-13-04.png
figure/스크린샷 2026-06-13 00-14-07.png
figure/스크린샷 2026-06-13 00-14-13.png
figure/스크린샷 2026-06-13 00-14-22.png
figure/스크린샷 2026-06-13 16-50-27.png
figure/스크린샷 2026-06-14 17-09-48.png
figure/스크린샷 2026-06-14 23-57-39.png
figure/스크린샷 2026-06-15 00-00-11.png
figure/스크린샷 2026-06-15 01-40-33.png
figure/스크린샷 2026-06-15 01-43-36.png
figure/스크린샷 2026-06-15 01-47-10.png
figure/스크린샷 2026-06-15 01-47-42.png
figure/스크린샷 2026-06-15 01-47-52.png
figure/스크린샷 2026-06-15 05-36-27.png
figure/스크린샷 2026-06-15 14-56-17.png
figure/스크린샷 2026-06-15 16-38-11.png
figure/스크린샷 2026-06-15 21-32-14.png
figure/스크린샷 2026-06-15 21-59-15.png
figure/스크린샷 2026-06-15 23-37-44.png
figure/스크린샷 2026-06-16 00-30-39.png
figure/스크린샷 2026-06-16 00-42-06.png
figure/스크린샷 2026-06-16 02-00-37.png
figure/스크린샷 2026-06-16 03-10-39.png
figure/스크린샷 2026-06-16 04-09-53.png
figure/스크린샷 2026-06-16 05-27-15.png
figure/스크린샷 2026-06-16 05-35-35.png
figure/스크린샷 2026-06-16 06-10-40.png
```

### Historical F1 receipt — presentation revision으로 superseded

이 receipt는 기준 커밋 `04f4346146900983c0eb7b02d4fad298046f3a92`의 상세 감사 원장에
대해 수행된 독립 검증 기록이다. 이후 사용자 요청에 따라 문서 앞부분에 삭제 결론,
파일별 리팩토링 표, 기능 유지 조건, Version 0.5 실행 계획을 추가하고 roadmap을
재작성했으므로, 이를 현재 presentation revision 전체에 대한 새 독립 승인으로 해석하면
안 된다. 기존 검증에서 확정된 coverage와 산술은 그대로 유지한다: tracked 136,
frozen untracked 14, code/config 118개와 23,353 LOC, privacy-safe ignored
631개/356,843,049 B, figure 252개, asset 9행, release gate 14개, A `378−15=363`,
A+B `401`, C `583`, D `52`.
