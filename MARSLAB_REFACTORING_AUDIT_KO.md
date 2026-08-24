# MarsLab 전수 리팩터링 감사 보고서

감사일: 2026-08-24  
감사 범위: Git이 추적하는 MarsLab Python 64개 파일(6,733줄),
`configs/config.yaml`, `launch/`, `pyproject.toml`, README 및 하위 `AGENTS.md`  
감사 성격: **읽기 전용 조사**. 이 보고서 외 소스·설정·에셋은 수정하지 않았다.

## 결론

현재 정식 YAML의 필드가 완전히 미사용되는 사례나 즉시 실행을 막는 정적 오류는
새로 발견되지 않았다. Ruff 검사와 현재 mypy 범위는 통과했고, 설정 로딩 및
preflight도 정상이다.

다만 리팩터링 가치가 분명한 항목은 **5개** 남아 있다.

- P1 5개: 실패 시 자원 소유권, 지연 import 계약, 설정과 런타임 경로의 불일치

최초 감사에서 발견한 P2 2개는 2026-08-24에 해결했다. 센서 3곳의 중복
quaternion 변환은 공통 helper로 통합했고, sensor frame은 중간 dict 없이 typed
tuple을 직접 생성한다.

대형 파일 3개는 책임이 혼합되어 있지만, 이전에 사용자가 현재 구조를 설계상
수용했고 자동 회귀 테스트도 유지하지 않기로 했으므로 이번에는 수정 권고 목록에
포함하지 않았다. 파일 크기만을 이유로 분리하면 Isaac 런타임 회귀 위험이 얻는
이익보다 크다.

## 우선순위 요약

| ID | 우선순위 | 후보 | 판단 | 런타임 검증 필요 |
| --- | --- | --- | --- | --- |
| R1 | P1 | rclpy 부분 초기화 실패의 자원 정리 | 수정 권장 | ROS 2 필요 |
| R2 | P1 | renderer의 최상위 `pxr` import | 수정 권장 | Isaac atmosphere 필요 |
| R3 | P1 | GUI 모듈의 최상위 `omni.ui` import와 오래된 설명 | 수정 권장 | GUI 필요 |
| R4 | P1 | `spawn.z_offset`의 스키마/런타임 필수성 불일치 | 수정 권장 | 기본 설정은 offline 검증 가능 |
| R5 | P1 | LiDAR custom JSON 경로의 preflight 누락 | 수정 권장 | custom profile은 Isaac 필요 |
| R6 | P2 | 센서별 RPY degree→quaternion 구현 3중복 | **해결 완료** | 센서 pose 확인 필요 |
| R7 | P2 | sensor frame dict→tuple 즉시 재변환 | **해결 완료** | TF 확인 필요 |

남은 항목의 권장 처리 순서는 `R1 → R2/R3 → R4/R5`이다. R1은 실패 경로의
실제 자원 누수 가능성이고, R2~R5는 프로젝트가 선언한 경계 또는 입력 계약과
구현이 어긋난다.

## P1: 계약 및 실패 경로

### R1. rclpy 초기화가 트랜잭션처럼 정리되지 않음

근거:

- `marslab/ros2_bridge/rclpy_integration.py:36-56`에서 `rclpy.init()`, node 생성,
  subscriber/broadcaster/publisher 생성을 순서대로 수행한다.
- 중간 factory가 예외를 내면 `BridgeContext`가 반환되지 않는다.
- `marslab/runtime/post_reset.py:184-201`은 함수가 성공한 뒤에만 `bridge`를
  받는다.
- `marslab/main.py:93-97`도 반환된 bridge가 있어야 node와 rclpy shutdown을
  `CleanupResources`에 등록한다.

영향: ROS publisher 구성 도중 실패하면 이미 만들어진 node 또는 초기화된
rclpy가 정식 cleanup 소유자에게 전달되지 않는다. SimulationApp은 닫히지만 ROS
자원은 부분 초기화 상태로 남을 수 있다.

권장안: `init_rclpy_side()` 내부에서 자신이 생성한 node와 자신이 시작한 rclpy를
기록하고, 후속 factory 실패 시 역순으로 정리한 뒤 원래 예외를 다시 발생시킨다.
이미 외부에서 활성화한 rclpy는 이 함수가 shutdown하지 않아야 한다.

검증:

- offline: factory 하나를 의도적으로 실패시키는 작은 주입형 driver로
  `destroy_node()`와 조건부 `shutdown()` 호출 여부 확인
- 사용자: ROS 활성 상태의 canonical launch와 Ctrl-C 종료 후 잔류 process 확인

### R2. rendering 모듈의 최상위 `pxr` import

근거:

- `marslab/rendering/sky_renderer.py:10`
- `marslab/rendering/sun_renderer.py:8`
- 두 모듈은 import 시점에 `pxr`를 로드한다.

이는 `pxr`/Isaac 계열 import를 SimulationApp 이후의 런타임 함수 경계로 미루라는
workspace 규칙과 다르다. 현재 환경에서는 `pxr`가 설치되어 있어 두 모듈의 단독
import가 성공했지만, 그것은 경계 준수를 보장하지 않는다. 정식 호출부가
`marslab/runtime/assembly.py:260-263`에서 SimulationApp 생성 이후 import하는
덕분에 현재 canonical launch는 이 문제를 가리고 있다.

권장안: `Gf`, `Sdf`, `UsdGeom`, `UsdLux` import를 실제 configure/update 함수의
런타임 경계로 옮긴다. 중복 local import가 싫다면 한 개의 private runtime loader를
사용하되, 모듈 import 시 `pxr`를 건드리지 않아야 한다.

검증:

- offline: `pxr`가 없어도 rendering 모듈 자체와 순수 설정 타입 import가 가능해야 함
- 사용자: atmosphere 활성 실행에서 sun/dome 생성과 GUI tau 변경 반영 확인

### R3. GUI 모듈의 최상위 `omni.ui` import와 문서 불일치

근거:

- `marslab/gui/atmosphere_panel.py:24`가 최상위에서 `omni.ui`를 import한다.
- 일반 Python에서 이 모듈을 import하면 현재 실제로
  `ModuleNotFoundError: No module named 'omni'`가 발생했다.
- 같은 파일 `:14-16`은 `marslab/main.py`의 import-time try/except가 보호한다고
  설명하지만, 실제 보호 경계는 `marslab/runtime/post_reset.py:156-164`의
  GUI 활성 조건과 try/except이다.

정식 headless 경로는 현재 보호되므로 즉시 실행 결함은 아니다. 그러나 standalone
import 가능성에 관한 workspace 계약과 설명이 실제 구현과 맞지 않는다.

권장안: UI 의존성을 panel 생성 시점으로 미루고, module docstring을 실제
`post_reset` 소유 관계에 맞춘다. UI 타입이 class 정의에 필요하다면 runtime 전용
구현 모듈과 CPU-safe facade를 분리하는 방안이 안전하다.

검증:

- offline: 일반 Python에서 GUI package import가 성공해야 함
- 사용자: GUI/atmosphere on에서 panel 생성, slider 조작, 종료 시 window cleanup 확인

### R4. `spawn.z_offset`은 스키마에서는 선택, 런타임에서는 필수

근거:

- `marslab/config/schema/rover.py:23-27`은 `z_offset`을 `None` 기본값을 가진
  선택 필드로 정의한다.
- `marslab/runtime/assembly.py:217-220`은 mode와 관계없이 `None`이면
  `RuntimeError`를 발생시킨다.
- 현재 canonical YAML은 `configs/config.yaml:55`에서 `0.1`을 명시하므로 정상이다.

영향: YAML/Pydantic 검증은 통과했는데 SimulationApp과 scene을 연 뒤에야 실패하는
입력을 만들 수 있다. preflight 우선 실패 계약과 맞지 않는다.

권장안: 모든 spawn mode에서 필요하므로 `z_offset: NonNegativeFloat`로 필수화한다.
호환해야 할 기존 문서가 없다면 임의 기본값을 두는 것보다 누락을 명확히 거부하는
편이 낫다.

검증: YAML 복사본에서 `z_offset`을 제거했을 때 `load_config()` 단계에서 명확한
validation error가 발생하고, 현재 YAML은 계속 통과해야 한다.

### R5. custom LiDAR JSON은 경로만 고정되고 파일 존재는 preflight하지 않음

근거:

- `marslab/config/yaml_loader.py:54-60`은 `profile_json_path`를 config 위치 기준으로
  anchor한다.
- `marslab/runtime/prepare.py:18-26`과 `precheck.py:18-21`은 scene, rover USD,
  URDF만 검사한다.
- `marslab/sensors/lidar_3d_spawner.py:77-85`는 JSON 경로를 문자열로 Isaac에
  전달하며, 그 전에 파일 존재 여부를 확인하지 않는다.
- 현재 YAML은 `profile_name: OS1`, `profile_json_path: null`이므로 영향받지 않는다.

영향: custom JSON profile을 선택한 사용자는 잘못된 경로를 SimulationApp 생성
전에 발견하지 못한다.

권장안: `profile_json_path`가 설정된 경우 `prepare_config()`에서 regular file인지
검사한다. 내장 `profile_name`의 유효성은 Isaac registry에 의존하므로 offline
preflight 대상에서 제외한다.

검증: 존재/부재 JSON 경로를 가진 임시 config로 `prepare_config()` 성공/실패를
각각 확인하고, custom profile의 실제 로딩은 사용자 Isaac 실행에서 확인한다.

## 해결 완료: 동작 보존형 정리

### R6. 센서 orientation quaternion 변환 중복 제거

동일한 ZYX degree RPY → WXYZ quaternion 구현이 다음 위치에 각각 존재한다.

- `marslab/sensors/camera_spawner.py:42-58`
- `marslab/sensors/imu_spawner.py:43-59`
- `marslab/sensors/lidar_3d_spawner.py:187-203`

한편 `marslab/quaternion.py:147-171`에는 같은 convention의 radians 기반
`rpy_to_quat()`가 이미 있다. 세 복사본은 향후 validation, convention 또는 반환
타입이 바뀔 때 서로 달라질 위험이 있다.

조치: `marslab/quaternion.py`의 `rpy_deg_to_quat()`가 길이 3 검증과
degree→radian 변환을 담당하고, 세 sensor spawner가 이를 공유하도록 변경했다.
기존 private helper 3개는 제거했다.

검증: canonical config의 Camera/IMU/LiDAR WXYZ 결과를 변경 전 기준선과 비교해
`1e-15` 절대오차 안에서 같음을 확인했다. 실제 prim pose와 TF는 사용자가
Isaac/ROS 실행에서 확인한다.

### R7. sensor frame 중간 dict 제거

근거:

- `marslab/runtime/sensor_frames.py:23-43`이 sensor config dict에서 다시
  `list[dict[str, Any]]`를 만든다.
- 같은 파일 `:46-57`이 이를 다시 broadcaster용 tuple로 변환한다.
- 유일한 정식 호출부 `marslab/runtime/post_reset.py:168-171`은 두 함수를
  바로 연속 호출한다.

조치: `build_sensor_frames()`가 검증된 `SensorsConfig`를 직접 받아 typed sensor
frame tuple을 반환하도록 변경했다. `sensor_frames_to_tuples()`와 중간 dict
형식은 제거했다.

검증: 변경 전후 세 frame의 child name, translation, RPY가 완전히 같음을 offline
출력으로 확인했다. 실제 `/tf_static` transform은 사용자가 확인한다.

## 이번 감사에서 수정 대상으로 올리지 않은 항목

### 대형 파일 분리

다음 파일은 물리적 크기와 책임 수가 크다.

- `marslab/runtime/main_loop.py`: 459줄
- `marslab/robots/rover.py`: 367줄
- `marslab/runtime/assembly.py`: 342줄

그러나 `main_loop`는 tick 순서를, `assembly`는 pre-reset 순서를, `rover`는 rover
USD/physics 설정 순서를 한곳에서 추적하려는 현재 설계다. 사용자는 이전 감사에서
이 대형 파일 자체를 수용했고, 현재 활성 자동 회귀 suite도 없다. 따라서 실제 기능
변경이 해당 경계를 요구하기 전에는 분리하지 않는 것이 권장된다.

### `_log_once`와 broad exception 정책

main loop의 제한된 오류 관측은 이미 사용자가 수용한 정책이다. 이번 감사에서
새로운 실제 토픽 소실이나 무로그 실패 근거가 없으므로 재개하지 않는다.

### wheel odometry 설정 위치와 고정 sensor frame 이름

`rover.wheel_odometry`와 top-level `wheel_odom.publish_tf`의 분리는 dynamic TF
소유권을 별도로 두려는 명시적 계약이다. `imu_link`, `camera_optical_frame`,
`lidar_link`도 현재 MarsLab이 소유하는 고정 frame 계약이다. 이름을 더 유연하게
만들 수 있다는 이유만으로 YAML 필드를 늘리는 것은 권장하지 않는다.

### `sensors.seed`

현재 canonical YAML은 `seed: 42`이며 이전 사용자 결정에 따라 seed 관련 우려는
종결했다. 이번 보고서에서는 `null` 사용을 전제로 한 wheel odometry seed 의미를
새 리팩터링 항목으로 다시 제기하지 않는다.

### 정식 동작에는 영향이 없는 소규모 정리

- `marslab/ros2_bridge/sensor_graph.py:20`의 `GRAPH_PATH`는 실제 graph 생성에
  쓰이지 않고 schema의 `graph_path`가 사용된다. 다만 package facade에서
  re-export되므로 API 의도를 확인하기 전에는 삭제 이득이 작다.
- `marslab/runtime/precheck.py:12-15`의 `check_rover_usd()`는 현재 한 호출자만
  있지만 역할이 명확하고 독립적인 pure preflight 함수이므로 유지 가능하다.
- `marslab/sensors/camera_spawner.py:21-23`의 빈 stage Protocol은 타입 계약을
  제공하지 못하지만 runtime handle typing 전체를 정리하지 않는 한 단독 수정
  효과가 작다.
- cleanup idempotence는 일반적으로 유용하지만, 현재 `main.py`는 성공 경로와
  setup 실패 경로 중 한 곳에서만 cleanup을 호출한다. 실제 이중 cleanup 호출
  근거가 없으므로 R1의 부분 초기화 정리보다 우선하지 않는다.

## 문서 정합성 참고 사항

코드 리팩터링과 별개로 하위 workspace 문서에 오래된 경로가 남아 있다.

- `marslab/config/AGENTS.md`는 존재하지 않는 `loader.py`를 언급한다. 현재 구현은
  `yaml_loader.py`다.
- `marslab/ros2_bridge/AGENTS.md`는 존재하지 않는
  `launch/companion_urdf.py`를 언급한다. 현재 companion 구현은
  `launch/rover_state_publisher.launch.py` 한 파일이다.
- `marslab/gui/atmosphere_panel.py:14-16`의 보호 위치 설명은 `main.py`가 아니라
  `runtime/post_reset.py`로 고쳐야 한다.

이 문서 수정은 승인 후 R3과 함께 또는 별도 P3 문서 정리로 처리할 수 있다.

## 확인된 정상 항목

- canonical YAML의 **완전 미사용 필드는 발견되지 않았다**.
- config root는 unknown field를 거부하고, 주요 상대 경로는 config 파일 위치를
  기준으로 anchor한다.
- Camera RGB/depth/PointCloud2/CameraInfo는 한 render product를 공유한다.
- IMU sampling frequency, LiDAR range/FOV/rotation rate, rover physics override,
  ROS topic/QoS 및 wheel odometry 설정은 각각 소비 경로가 존재한다.
- 대부분의 `isaacsim`, `omni`, `pxr`, live `rclpy` import는 runtime 함수 내부로
  지연되어 있다.
- 뚜렷한 순환 import는 발견되지 않았다.
- Ruff의 `E/F/W/I/B/SIM` 검사에서 오류가 없었다.
- mypy는 설정된 범위인 `marslab/config`, `marslab/environment` 15개 파일을
  오류 없이 통과했다. 이는 전체 runtime 타입 검사를 의미하지 않는다.

## 승인 후 작업 단위 제안

각 항목은 별도 작업으로 적용하고 검증하는 것이 안전하다.

1. R1: ROS 부분 초기화 cleanup
2. R2 + R3 + 문서 정합성: runtime import 경계
3. R4 + R5: preflight 입력 계약

사용자의 명시적 승인 전에는 위 항목을 구현하지 않는다. 특히 Isaac GUI, physics,
sensor, ROS, TF, AtmospherePanel 및 cleanup의 실제 동작은 agent가 정적으로 확인했다고
주장하지 않으며, 각 변경 후 canonical command와 별도 ROS companion 환경에서
사용자가 검증해야 한다.
