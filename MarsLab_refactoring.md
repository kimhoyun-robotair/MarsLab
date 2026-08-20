# MarsLab 단독 리팩터링 요약

전제가 다음처럼 확정되면 MarsLab 리팩터링 범위는 상당히 줄어듭니다.

- Scene과 모든 환경 Asset이 하나의 자기완결적 USDZ로 제공됨
- Rover spawn용 Rover USD가 별도로 제공됨
- 두 파일 모두 Isaac Sim 물리·렌더링 호환 검증 완료
- 외부 texture, sublayer, payload, 개인 로컬 경로 의존성 없음
- MarsLab-Utils는 설치하거나 실행하지 않음

즉, MarsLab은 이제 **“USD를 만드는 프로그램”이 아니라 “Scene USDZ와 Rover USD를 실행하는 시뮬레이터”**로 정리하면 됩니다.

## 1. 가장 먼저 정리할 제품 범위

- MarsLab의 공식 입력을 명확하게 제한

  - Scene USDZ
  - Rover USD
  - Scene·Rover·runtime·ROS 2 설정을 포함한 통합 YAML

- MarsLab의 책임

  - Scene USDZ 로드
  - Rover USD spawn
  - Rover 물리·관절 설정
  - 센서 생성
  - atmosphere·lighting 적용
  - ROS 2 연결
  - simulation loop
  - GUI와 안전한 종료

- MarsLab에서 제외할 책임

  - terrain 생성
  - rock 생성 및 배치
  - habitat 생성
  - URDF→USD 자동 변환
  - Scene composition 생성
  - trajectory 생성
  - SLAM/VPR benchmark
  - TUM 평가
  - MarsLab-Utils 실행 및 import

### 공통 코드·주석 원칙

- 장황하거나 역할이 불명확한 주석과 docstring을 작성하지 않음
- 함수·메서드에는 해당 코드의 역할을 명확히 설명하는 한 줄만 작성
- Python type annotation으로 이미 표현되는 입력·출력 타입을 주석에서 반복하지 않음
- 매개변수와 반환값을 기계적으로 나열하는 장문의 `Args`·`Returns` 설명을 작성하지 않음
- 코드 자체로 명확한 처리 과정은 주석으로 다시 서술하지 않음
- 코드 파일 최상단에는 파일 전체의 책임과 경계를 설명하는 3~6줄의 요약 주석 또는 module docstring을 허용
- 안전 제약, Isaac Sim·ROS 2의 비직관적인 동작, 외부 API 제약처럼 코드만으로 이유를 알 수 없는 경우에만 짧게 이유를 기록
- 오래된 구현 이력, 리뷰 대화, 임시 해결 과정은 코드 주석이 아니라 변경 기록이나 별도 문서에 남김

## 2. MarsLab-Utils 의존성 완전 제거

- `main.py`의 `gt_publisher` optional import 제거

  - 현재 존재하지 않는 `MarsLab-Utils/GT/gt_publisher`를 전제로 함
  - MarsLab 내부 GT publisher와 authority가 중복될 가능성도 있음

- 다음 형태의 의존성을 전부 제거

  - `~/MarsLab-Utils/...`
  - `/home/hoyunkim/MarsLab-Utils/...`
  - Utils trajectory 기본 경로
  - Utils Python package import
  - Utils가 없을 때 fallback하는 코드

- 최종 조건

  - MarsLab-Utils가 설치되지 않은 환경에서 MarsLab import·실행 가능
  - 실행 문서에서도 Utils를 필수 전제 조건으로 소개하지 않음

## 3. CLI 단순화

현재 여러 CLI 옵션과 두 YAML 파일에 분산된 실행 설정을 하나의 통합 YAML로 정리합니다.

- 권장 명령

  ```bash
  marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
  ```

- `main.py`는 오직 `--config` 하나만 받음

  - Scene USDZ 경로
  - Rover USD 경로
  - headless 여부
  - ROS 2 활성화 여부
  - atmosphere 활성화 여부
  - spawn 위치와 방향
  - 태양·환경·렌더링 설정
  - rover·sensor·control·odometry 설정

- 위 값은 모두 통합 YAML에서 읽음

  - `--usda`, `--scene`, `--rover-usd`, `--scenario`, `--rover-yaml` 제거
  - `--headless`, `--no-ros2`, `--no-atmosphere` 제거
  - `--z-offset`, `--sun-azimuth-deg`, `--sun-elevation-deg` 제거
  - legacy alias나 CLI override 우선순위를 만들지 않음

- `doctor`는 이번 리팩터링에서 구현하지 않음

  - 필요성이 확인되면 사용자와 별도로 범위를 협의한 뒤 추후 구현

## 4. Config와 Schema 정리

현재 `configs/default.yaml`과 `configs/rover_m2020.yaml`로 나뉜 설정을
`configs/config.yaml` 하나로 통합합니다.

- 통합 YAML 하나를 strict production schema에 연결

- 권장 최상위 구조

  - Scene USDZ와 runtime 설정
  - `mars_env`
  - `rendering`
  - Rover USD와 rover 설정
  - ROS 2
  - sensors
  - control
  - GT Pose와 Wheel Odom

- 다음 세 가지를 일치시킴

  - YAML에 선언된 필드
  - Pydantic schema가 허용하는 필드
  - runtime이 실제로 소비하는 필드

- runtime에서 읽지 않는 필드는 제거

  - 미래 기능용 field
  - documentation-only field
  - terrain 생성용 설정
  - MarsLab-Utils trajectory 경로
  - 더 이상 사용하지 않는 legacy config
  - Python 코드 내부 fallback과 중복되는 YAML default

- `parent_link` 처리

  - 실제 sensor spawner가 사용하도록 연결하거나
  - 현재 모든 센서를 chassis에 붙일 것이라면 필드 제거
  - 사용하지 않으면서 문서 계약으로만 유지하지 않음

- 설정을 실행 시작 시 한 번만 해석

  - 중간 단계에서 raw YAML을 다시 읽지 않음
  - 여러 함수가 서로 다른 기본값을 적용하지 않음
  - 별도의 RunPlan 객체를 만들지 않고 검증된 typed config를 runtime에 직접 전달

## 5. `main.py` 분리

현재 `main()`은 약 406줄로 역할이 너무 많습니다.

다음 정도로만 분리하면 충분합니다.

- `prepare_run()`

  - CLI parse
  - 경로 해석
  - YAML 로드

- `boot_simulation()`

  - SimulationApp
  - Isaac extension
  - timeline/world 초기화

- `assemble_runtime()`

  - Scene USDZ 로드
  - Rover USD spawn
  - sensors
  - ROS
  - AtmospherePanel

- `run_simulation()`

  - physics step
  - rover control
  - sensor publish
  - atmosphere update

- `cleanup_runtime()`

  - ROS
  - sensor/graph
  - world/timeline
  - SimulationApp 종료

`main.py` 자체는 위 단계를 순서대로 호출하는 짧은 orchestration 코드로 만듭니다.

- 이 작업은 동작 재설계가 아니라 현재 정상 실행 순서를 고정한 pin-point extraction으로 수행
- 함수 추출 전후의 정상 경로 호출 순서, reset 경계, warmup 횟수·위치, timeline 시작, 센서·ROS·AtmospherePanel 생성 시점을 변경하지 않음
- reset 이전 DriveAPI 설정과 reset 이후 articulation 초기화·PD gain 보강을 서로 이동하거나 합치지 않음
- 계산식, 기본값, 좌표계, topic, frame, 오류 우선순위를 변경하지 않음
- 허용되는 동작 변경은 흩어진 cleanup을 명시적인 생성 역순으로 정리하고 누락된 종료 처리를 보완하는 것뿐임
- 범용 lifecycle manager, registry, plugin, god object를 도입하지 않음
- G3 종료 즉시 사용자가 Isaac에서 boot, physics step, Rover control, 정상 종료를 검증한 뒤 승인

## 6. 센서 생성 코드 정리

현재 `spawn_sensors()`와 sensor graph builder가 지나치게 큽니다.

우선 지원하는 센서·관측 출력은 다음으로 한정합니다.

- Camera
  - RGB
  - Depth
  - CameraInfo
  - Camera 기반 PointCloud2
- IMU
- 3D LiDAR
- GT Pose
- 노이즈가 적용된 Wheel Odom

GT Pose와 Wheel Odom은 목적과 노이즈 특성이 다른 별개의 출력이므로 모두 유지합니다.

- GT Pose는 Isaac articulation의 실제 world pose를 SLAM·odometry 평가용 정답으로 제공

  - 기존 GT trajectory topic에 `nav_msgs/Odometry` 형식으로 publish
  - `frame_id: map`, `child_frame_id: base_link_gt`
  - TF를 절대 발행하지 않으며 운용 TF tree에 참여하지 않음
  - noise·wheel 적분 없이 simulation timestamp의 실제 pose를 제공
  - ROS `map`은 Isaac world와 원점·축·미터 단위가 동일한 평가 좌표계로 정의
  - reset이나 Rover spawn pose를 기준으로 GT 원점을 재설정하지 않고 Scene의 절대 world/map pose 유지

- Wheel Odom은 wheel encoder 적분과 slip/noise를 포함하는 운용 추정값

  - odom topic에 publish
  - `frame_id: odom`, `child_frame_id: base_link`
  - MarsLab 내부에서 `odom -> base_link` 동적 TF를 발행할 수 있는 유일한 publisher
  - 외부 odometry가 같은 TF를 소유하는 구성에서는 중복 발행을 금지
  - 통합 YAML의 `wheel_odom.publish_tf`로 authority를 명시적으로 선택
  - `true`: Wheel Odom이 `odom -> base_link` 소유, SLAM은 `map -> odom`만 발행
  - `false`: 외부 Visual Odom/SLAM이 `odom -> base_link` 소유, Wheel Odom은 topic만 발행

- ROS 표준 이동 기준 프레임 `base_link`와 실제 URDF/USD 루트 `Body_Chassis`를 모두 유지

  - Wheel Odom 또는 외부 odometry 중 하나만 `odom -> base_link`를 소유
  - companion launch의 단일 identity static TF만 `base_link -> Body_Chassis`를 소유
  - 외부 `robot_state_publisher`는 `Body_Chassis` 아래 articulation link chain만 소유하고 odom TF를 발행하지 않음
  - MarsLab static sensor TF broadcaster는 `Body_Chassis` 아래 Camera·IMU·3D LiDAR 프레임만 소유
  - URDF/USD 루트를 `base_link`로 바꾸지 않고, 두 프레임을 잇는 publisher를 중복 생성하지 않음

- 과거의 TF 우회 경로는 호환 계층으로 남기지 않고 전량 삭제

  - `isaac:nameOverride`, `/World/odom_anchor`, OmniGraph `/tf_raw`
  - `rename_root_to_base_link`, `enable_isaac_nameoverride`, `parent_anchor_prim_path`
  - 관련 helper, schema/YAML 필드, 호출 인자, 문서와 생성 cache

- `spawn_sensors()`를 센서별로 분리

  - `spawn_camera()`
  - `spawn_lidar_3d()`
  - `spawn_imu()`

- 2D LiDAR 기능은 deprecated 상태로 남기지 않고 전량 삭제

  - schema와 YAML 필드
  - sensor prim과 handle
  - render product와 OmniGraph node/edge
  - ROS 2 `LaserScan` topic과 publish rate
  - `scan_frame`과 관련 TF
  - README와 기타 문서

- 위 지원 목록에 포함되지 않은 센서용 코드·설정·문서도 삭제

  - Camera의 Depth·CameraInfo·PointCloud2는 별도 센서가 아니라 Camera 출력이므로 유지
  - 향후 센서는 실제 필요성이 확인된 뒤 사용자와 협의하여 추가

- 공통 처리

  - parent prim
  - translation/orientation
  - topic/frame
  - 오류 메시지

- 센서 설정은 YAML에서 한 번 검증된 typed config만 사용

- Isaac Sim 5.1에서 현재 정상 동작하는 센서 API를 그대로 유지

  - Camera의 기존 `Camera` API 유지
  - IMU의 `isaacsim.sensors.physics.IMUSensor` 유지
  - 3D LiDAR의 `isaacsim.sensors.rtx.LidarRtx` 유지
  - 최신 `isaacsim.sensors.experimental.*` API로 migration하지 않음
  - annotator 이름, sensor profile 적용, render-product 의미를 임의로 변경하지 않음
  - ROS graph가 소유하던 획득 구성요소를 sensor 계층으로 옮길 수는 있지만 API 교체나 센서 중복 생성은 금지

- 지원하지 않는 설정은 조용히 무시하지 않고 오류 처리

- Camera, IMU, 3D LiDAR는 선택 기능이 아니라 항상 생성되는 필수 센서로 취급

  - 센서별 `enabled` 설정과 비활성 분기 제거
  - Camera는 prim, render product, RGB/Depth annotator를 항상 생성
  - IMU는 prim과 runtime handle을 항상 생성하고 physics 측정을 유지
  - 3D LiDAR는 prim, runtime sensor, render product, point-cloud annotator를 항상 생성
  - Python 데이터 복사·3D point 후처리·메시지 변환은 실제 소비자가 있을 때만 수행
  - ROS 2 활성 시 기존 sensor handle/render product에 publisher를 연결하며 센서를 중복 생성하지 않음
  - ROS 2 비활성 시 sensor runtime과 annotator는 유지하고 ROS bridge·OmniGraph·publisher만 생성하지 않음

## 7. ROS 2 코드 정리

- `init_rclpy_side()`를 역할별로 분리

  - node 생성
  - cmd_vel subscriber
  - camera publisher
  - lidar publisher
  - IMU publisher
  - odometry publisher
  - GT publisher
  - cleanup 등록

- GT Pose publisher는 MarsLab 내부 하나만 사용하고 topic message만 발행

- topic, frame, QoS의 출처를 통합 YAML의 Rover·ROS 2 설정으로 단일화

- 중복 TF publisher 방지

- 통합 YAML에서 ROS 2가 비활성화되었을 때

  - rclpy import 최소화
  - ROS node/publisher 미생성
  - 센서 자체는 필요에 따라 유지

- ROS 지원을 주장한다면 실제 runtime에서 확인

  - topic 수신
  - QoS 호환
  - TF tree
  - timestamp clock
  - 종료 시 node cleanup

## 8. Rover spawn과 control 정리

- Rover USD 경로는 통합 YAML 한 곳에서만 받음

- 다음 값을 통합 YAML의 Rover 설정 한 곳으로 정리

  - wheel joint 이름
  - steer joint 이름
  - wheel radius
  - wheelbase
  - track width
  - control limit
  - damping/stiffness
  - mass/inertia override
  - spawn orientation

- 하드코딩된 prim/joint 이름은 최소화

- 통합 YAML의 Rover 설정과 실제 Rover USD의 joint 목록을 spawn 전에 비교

- Ackermann 계산은 순수 계산 함수로 유지

- 잘못된 joint index나 0 wheel radius가 simulation 중간에서 터지지 않도록 사전 검증

## 9. Python·패키징 정리

- Python 기준을 Isaac Sim 5.1 내장 Python 3.11로 통일

  - `requires-python`: Python 3.11 이상
  - Black target: `py311`
  - Ruff target: `py311`
  - mypy `python_version`: `3.11`
  - 개발 환경에서 Python 3.12를 사용할 수는 있지만 3.12 전용 문법·API는 사용하지 않음

- 별도 `project.scripts` console CLI나 `marslab run` 명령은 만들지 않음

- `marslab/isaac_python.sh`가 유일한 공식 launcher이며 system ROS 환경 제거 후 Isaac Python 3.11로 `marslab/main.py`를 직접 실행

- wrapper가 자신의 위치에서 저장소 루트를 계산하고 깨끗한 `PYTHONPATH`를 구성하여 `main.py`의 repo root `sys.path.insert()` 제거

- Python package와 대형 USD 자산을 분리 가능

  - MarsLab Python runtime package
  - 별도의 versioned Scene/Rover asset bundle

- Scene USDZ를 wheel에 무조건 포함할 필요는 없음

## 10. 종료와 오류 처리 정리

- 예상치 못한 runtime 오류는 성공처럼 처리하지 않음

- `simulation_app.close()` 실패를 성공 코드로 숨기지 않음

- cleanup은 생성 역순으로 실행

  - ROS
  - publishers/graph
  - sensors
  - world/timeline
  - SimulationApp

- 한 cleanup이 실패해도 나머지 cleanup은 계속 시도

- broad `except Exception`은 다음 위치에만 허용

  - 최상위 오류 기록 경계
  - best-effort cleanup
  - optional GUI/telemetry

## 11. 파일과 주석 정리

- 제거 또는 통합 대상

  - stale `MARSLAB_V0_5_READINESS_AUDIT.md`
  - 중복·오래된 nested `AGENTS.md`
  - 현재 코드와 맞지 않는 `GT_Trajectory.md`
  - 존재하지 않는 문서를 가리키는 README 링크
  - 개인 Isaac 설치 경로 주석
  - 제거된 CLI 사용법과 분리된 두 YAML 실행 예시
  - 존재하지 않는 DEM 경로의 `.gitattributes`
  - 중복·과도하게 넓은 `.gitignore`
  - MarsLab-Utils 경로와 설명

- 자산 reference 확인 없이 삭제하면 안 되는 것

  - sky/texture 이미지
  - Rover USD layer
  - Rover mesh
  - submodule
  - Scene USDZ 내부에서 참조될 가능성이 있는 파일

- `convert_urdf_to_usd.py`, `fix_urdf_inertia.py`

  - runtime에서는 제외
  - Rover USD를 다시 생성할 계획이 있으면 `tools/`의 개발 도구로 유지
  - 재생성 계획이 전혀 없다면 별도 archive 또는 삭제 검토

## 12. Test와 GitHub Actions 처리

- 현존하는 테스트를 우선 전량 삭제

  - `tests/` 아래의 현재 테스트 파일 전체
  - pytest dependency와 pytest 전용 설정
  - 존재하지 않는 `tests/unit/`을 가리키는 문서와 주석

- 현존하는 GitHub Actions를 우선 전량 삭제

  - `.github/workflows/` 아래의 현재 workflow 전체
  - workflow가 존재한다고 설명하는 문서와 badge

- 이번 리팩터링에서는 대체 테스트나 GitHub Actions를 자동으로 추가하지 않음

- 필요한 테스트의 범위와 형태는 사용자와 별도로 협의

  - 실제로 보호할 동작
  - CPU-only 테스트와 Isaac runtime 테스트의 경계
  - mock 허용 범위
  - CI 재도입 여부

- 리팩터링 도중 또는 G1-G7 사용자 검증에서 자동화 가치가 있는 구체적 회귀 경계가 발견되면 작업을 멈추고 사용자와 테스트 필요성·범위·형태를 협의

  - 사용자 승인 없이 테스트를 임의로 추가하지 않음
  - 단순 구현 확인용 일회성 테스트는 추가하지 않음

- 새 테스트가 합의되기 전까지 일회성 검증 코드로 완료를 주장하지 않음

- 검증은 다음 실제 표면과 정적 도구만 사용

  - 통합 YAML parse
  - CLI 오류 처리
  - 실제 Isaac Sim GUI/headless 실행
  - 실제 Camera·IMU·3D LiDAR 출력
  - GT Pose와 Wheel Odom의 별도 출력
  - 정상 종료와 cleanup

- 센서 상시 생성·획득의 GPU/CPU 비용은 승인된 설계 비용으로 간주하며 최적화를 이유로 센서를 비활성화하지 않음

- README 설치 단락은 submodule 확보 방법을 반드시 포함

  - 새 clone: `git clone --recursive <repository-url>`
  - 이미 clone한 저장소: `git submodule update --init --recursive`

- 최종 Isaac 검증에서는 `configs/config.yaml`을 수정하지 않음

  - canonical YAML을 `/tmp/marslab-runtime-v2-qa/` 아래 U1-U3 파일로 복사
  - GUI/headless, atmosphere, ROS 2 boolean은 복사본에서만 변경
  - 복사로 상대경로 기준이 달라지므로 asset 경로는 절대경로로 변환하거나 원래 `configs/` 기준을 보존
  - 검증 종료 후 임시 복사본 디렉터리 삭제

## 13. 권장 작업 순서

- 아래 세부 작업은 경량 모델용 내부 단위이며 사용자 승인·commit 경계가 아님
- 사용자 검증, 승인, 누적 보고, commit은 다음 7개 실행 가능한 단계에서만 수행

  1. 통합 config/schema
  2. CLI와 Python 3.11 launcher
  3. lifecycle과 `main.py`
  4. 센서 정리와 2D LiDAR 삭제
  5. ROS·TF·GT/Wheel Odom
  6. 저장소 청소와 문서
  7. 최종 정적 점검과 사용자 Isaac U1-U3 검증

- 각 단계 승인 전에는 다음 단계로 진행하지 않으며, 단계 내부의 불완전한 중간 상태는 commit하지 않음

1. MarsLab-Utils 및 개인 경로 의존성 제거
2. stale 파일·주석·README 정리
3. 통합 YAML schema와 단일 loader 작성
4. `marslab/isaac_python.sh marslab/main.py --config ...` 단일 실행 계약 작성
5. Python 3.11·패키징 계약 수정
6. `main.py` lifecycle 분리
7. 2D LiDAR와 미지원 센서 코드·설정·문서 삭제
8. Camera·IMU·3D LiDAR sensor spawner와 graph builder 정리
9. ROS·TF·GT Pose·Wheel Odom authority 정리
10. cleanup과 오류 상태 정리
11. 기존 테스트와 GitHub Actions 전량 삭제
12. 실제 GUI/headless Isaac smoke와 sensor·odometry 출력 확인
13. 문서·LICENSE·third-party notices 정리
14. 필요한 테스트와 CI 범위를 사용자와 별도로 협의

## 한 문장으로 요약

- **MarsLab-Utils와 asset 생성 기능을 제거한 뒤, 완성된 Scene USDZ·Rover USD와 설정을 받아 실행하는 runtime simulator로 MarsLab을 축소하는 것이 핵심입니다.**
- **가장 중요한 코드 작업은 `main.py`, config/schema, sensor spawner/graph, ROS integration, cleanup, CLI·패키징 정리입니다.**
- **현재 테스트와 GitHub Actions는 우선 삭제하고, 필요한 자동 검증은 사용자와 별도로 합의한 뒤 추가합니다.**
