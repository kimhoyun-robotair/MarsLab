# MarsLab 우려사항 및 후속 조치 대장

마지막 소스/로그 점검일: 2026-08-24

이 문서는 개발 세션이 바뀌면 잊기 쉬운 알려진 결함, 조건부 위험,
성능 한계, 해결된 조사 결과를 기록한다. 런타임에 관한 판단은 사용자가
제공한 `log.txt`만을 근거로 하며, 소스 검사만으로 도출한 항목은 그 사실을
명시한다.

## 상태 및 우선순위

- **OPEN**: 확인된 문제이거나 오해를 일으키는 계약으로, 수정이 필요하다.
- **WATCH**: 조건부 위험으로, 변경 여부를 결정하기 전에 검증해야 한다.
- **ACCEPTED**: 사용자가 이해하고 현재 수용한 한계다.
- **RESOLVED**: 수정되었거나 실증적으로 문제가 없다고 확인된 항목으로, 회귀 방지를 위해 남겨 둔다.
- **P0**: 에셋 또는 데이터의 정확성이 훼손될 수 있다.
- **P1**: 설정이 이름과 다른 의미로 조용히 적용될 수 있다.
- **P2**: 조건부 정확성, 재현성 또는 유지보수성에 관한 우려다.
- **P3**: 현재 시뮬레이터 실행을 막지는 않는 도구 또는 로그 노이즈 문제다.

## `tests/` 삭제 결정 및 Git 추적 LOC

2026-08-24에 사용자 런타임 검증이 완료되었다는 판단에 따라 미추적 상태의
`tests/` 디렉터리를 삭제했다. 제거된 3개 파일에는 wheel link와 drive joint
소유 분리, 미사용 YAML 필드 제거, 여러 줄 physics override 로그를 확인하는
테스트 4개가 있었으며 삭제 직전에는 모두 통과했다. 사용자는 이 자동 회귀
검사를 계속 유지하지 않고 런타임 검증 결과를 최종 기준으로 삼기로 했다.

해당 디렉터리는 처음부터 Git 미추적 상태였으므로 삭제해도 Git이 추적하는
LOC와 checkout 결과는 변하지 않는다. `tmp/preserved_tests`는 별도의 오래된
자료로 남아 있으며 활성 테스트 suite로 간주하지 않는다.

모든 우려사항을 종결한 시점의 `git ls-files`를 기준으로 `tests/`,
`MARSLAB_CONCERNS.md`, `MARSLAB_CONCERNS_KO.md`를 제외해 계산한 LOC는
다음과 같다. 두 우려사항 문서는 원래 Git 미추적 상태이지만 제외 조건을
명시적으로 적용했다. 바이너리 USD/이미지와 submodule 포인터는 코드 LOC에
포함하지 않았다.

| 구분 | 파일 수 | 물리적 줄 수 | 공백 제외 줄 수 |
| --- | ---: | ---: | ---: |
| Python (`.py`) | 64 | 6,733 | 5,575 |
| Shell (`.sh`) | 1 | 74 | 64 |
| YAML (`.yaml`) | 1 | 181 | 176 |
| TOML (`.toml`) | 1 | 64 | 55 |
| 코드 및 설정 합계 | 67 | 7,052 | 5,870 |
| Python과 Shell만 | 65 | 6,807 | 5,639 |

참고로 `.gitignore`, `.gitmodules`, `README.md`까지 포함한 Git 추적 UTF-8
텍스트 전체는 70개 파일, 7,358줄이다. 최초 기록된 코드 및 설정 합계와
비교하면 물리적 127줄, 공백 제외 96줄이 감소했다. 마지막 context wrapper
정리만 비교하면 Python 물리적 75줄, 공백 제외 63줄이 감소했다.

## 미해결 우려사항

현재 `OPEN` 또는 `WATCH` 상태인 우려사항은 없다.

## 수용된 한계 및 관찰 항목

### ACCEPTED: 활성 자동 테스트를 유지하지 않음

삭제 직전의 4개 테스트를 기준으로 `coverage --source=marslab`를 실행했을 때
statement coverage는 16%였다. config import로 실행되는 스키마를 제외한
environment, control, lifecycle, ROS, sensor 모듈 대부분은 0%였다. 사용자는
이미 완료한 Isaac 런타임 검증을 근거로 이 낮은 범위의 미추적 테스트를
유지하지 않기로 결정했으며, 루트 `tests/`를 삭제했다.

따라서 현재 checkout과 CI에는 활성 자동 회귀 검사가 없다. 과거 테스트
9개가 있는 `tmp/preserved_tests`는 현재 API와 일치하지 않고 기본 pytest
수집도 깨뜨리므로 검증 근거로 사용하지 않는다. 향후 동작 변경에서 자동
회귀 검사가 다시 필요해지면 그 변경의 실제 경계에 맞는 새 테스트를 별도로
도입한다.

### PASS: 미사용 context wrapper 제거 및 대형 runtime 모듈 유지

실제 consumer가 없던 `VehicleGeometry`, `ControlLimits`,
`AtmosphereCallables`와 이를 매 접근마다 새로 만들던 `LoopContext` property를
제거했다. 정식 runtime은 기존 평탄 필드를 계속 사용하므로 실행 동작과 설정
전달은 바뀌지 않는다. `main_loop.py`, `rover.py`, `assembly.py`가 여러 책임을
포함하는 것은 현재 순차 실행 흐름을 한곳에서 추적하기 위한 설계로 수용한다.
활성 자동 회귀 검사가 없는 상태에서 파일 크기만 줄이기 위한 대규모 분리는
진행하지 않으며, 실제 기능 변경으로 책임 경계가 필요해질 때만 다시 검토한다.

### PASS: solver와 rendering timestep은 고정 실행 정책

`create_world()`는 `solver_type="TGS"`, position iteration 16, velocity
iteration 4를 Python 기본 인자로 보유하고, `rendering_dt`를 `physics_dt`와
항상 같게 만든다. 정식 시작 경로는 gravity와 physics dt만 전달하므로
사용자는 canonical YAML에서 solver 정확도나 render cadence를 조정할 수
없다. USD attribute `Set()` 결과도 확인하지 않는다.

근거: `marslab/sim/world_setup.py:14-68` 및 `marslab/main.py:66-69`.

현재 로버의 접촉·관절 거동이 안정적이고 depth 처리량은 해상도 조정으로
해소되었다. solver 반복 횟수와 render cadence를 실험별로 변경할 필요가
없으므로 재현 가능한 고정 실행 정책으로 유지하며 YAML에 노출하지 않는다.
접촉 불안정이나 렌더링 병목이 실제로 관찰될 때만 다시 검토한다.

### PASS: `_log_once`의 제한된 초기 오류 출력 정책

현재 `_log_once()`는 시작 후 120 step 동안 발생한 오류만 출력하고 이후
오류는 숨긴다. 장시간 실행 중 처음 발생한 publisher 또는 sensor 오류의
진단성이 낮아질 수 있지만, 현재 사용자 실행에서는 로버 제어와 유지 대상
ROS 토픽이 정상임을 확인했다. 오류별 상태 reporter와 종료 요약을 추가하는
복잡성보다 현재 동작 유지를 우선하므로 별도 수정 없이 수용한다. 실제로
토픽이 사라졌는데 관련 로그가 없는 문제가 관찰될 때만 다시 검토한다.

### PASS: `dynamic_atmosphere`는 dynamic sun과 수동 tau를 포괄함

현재 섹션은 시간 배율에 따라 자동으로 움직이는 sun과 GUI에서 수동 조작하는
tau를 함께 소유한다. dust tau가 자동 진행되지 않는 것은 설계 의도이므로
`dynamic_sun`으로 개명하거나 별도 dust profile을 추가하지 않는다.

### PASS: Git 추적 HDRI에는 별도 preflight를 두지 않음

기본 sky-dome HDRI 세 파일은 모두 `assets/mars_sky` 아래 Git 추적 자산이다.
정상적인 clone에는 자동으로 포함되므로 별도 preflight와 실패 경로를 추가하지
않는다. 사용자가 경로나 파일명을 의도적으로 바꾼 경우 renderer의 color-dome
fallback을 허용한다.

### PASS: GUI tau는 현재 실행에만 적용되는 override

`mars_env.dust_optical_depth`는 재현 가능한 시작 tau를 소유하고, GUI slider는
현재 실행의 메모리 상태만 변경한다. 종료 후 다음 실행은 다시 YAML 값에서
시작한다. runtime이 canonical config를 자동 수정하지 않는 것이 설계 의도이며,
시험 중 slider 조작이 영구 설정이나 Git 변경으로 남지 않는다. 영구 변경이
필요하면 사용자가 YAML을 명시적으로 수정한다.

### PASS: Isaac 카메라 내부 파라미터 자동 보정

사용자 실행에서 RGB, depth, PointCloud2와 CameraInfo가 모두 정상임을
확인했다. Isaac은 render resolution의 square-pixel 계약에 맞춰 vertical
aperture를 조정하고 `fy`를 `fx`와 같게 하며, distortion model `None`은 기본
계수의 `plumb_bob`으로 발행한다. MarsLab은 정밀한 실물 카메라 calibration
재현보다 정상적인 합성 센서 출력을 우선하므로 이 동작을 수용한다. 별도
aperture 또는 distortion YAML 필드는 추가하지 않으며, 실제 카메라의 metric
calibration 재현이 요구사항이 될 때만 다시 검토한다.

### ACCEPTED: 고해상도 depth 처리량

Depth image와 point cloud 내용은 유효했다. 1280x960에서는 depth image와
point cloud 주기가 다른 토픽보다 훨씬 낮았고, 카메라를 640x480으로
낮추자 다른 stream과 비슷한 수준이 되었다. 이는 depth AOV 결함이 아니라
렌더링, 변환, 직렬화 처리량의 한계임을 확인한 결과다.

고해상도와 높은 관측 주기가 모두 요구사항이 될 때만 다시 검토한다.

### DEFERRED: ROSIDL generator의 `lark` 선택적 import 실패

Isaac 내부 ROSIDL generator의 DEBUG traceback은 `lark`가 없어 발생하지만,
현재 유지 대상인 표준 ROS 2 메시지 binding과 발행은 정상 동작한다. 사용자
정의 또는 동적 IDL 생성은 현재 MarsLab 범위가 아니므로 지금은 의존성을
추가하거나 내부 로그를 억제하지 않는다. 해당 기능이 요구사항이 될 때만
Isaac이 지원하는 설치 절차와 함께 다시 검토한다.

### ACCEPTED: ROS 토픽 발행 주기는 tick과 처리량에 종속됨

OmniGraph 출력은 playback tick, rclpy 출력은 메인 시뮬레이션 loop에 맞춰
발행되며 카메라와 LiDAR는 렌더링·변환·직렬화 처리량의 영향도 받는다.
센서 sampling frequency와 ROS에서 관측되는 wall-clock Hz를 분리하는 것이
현재 설계 의도다. MarsLab은 고정 ROS 발행률을 계약하지 않으며 별도 rate
limiter를 추가하지 않는다.

### PASS: RTX LiDAR Motion BVH 비활성 유지

`enable_motion_bvh=True`를 적용한 사용자 실행에서 renderer motion 설정과
scene acceleration structure 생성까지는 확인됐지만, RTX PSO 비동기 컴파일이
30초 이상 정체된 뒤 Isaac Python 프로세스가 강제 종료됐다. 정상적인 MarsLab
시작을 우선해 기본 활성화를 철회했다. 따라서 움직이는 장면의 LiDAR motion
effect 정확도 한계를 수용하며, 현재 런타임 환경이 바뀌기 전에는 다시
활성화하지 않는다. Motion BVH는 미해결 작업과 권장 구현 순서에서 제외한다.
향후 motion compensation이 필수 요구사항이 되거나 GPU·Isaac 버전이 바뀐
경우에만 최초 RTX shader cache 생성 시간을 충분히 허용하고 실행 중 VRAM을
측정하면서 다시 검토한다.

### PASS: 선택적 depth-sensor 모델이 비활성화되어 있음

`camera.depth_sensor.enabled: false`는 선택적 stereo/noise 스키마를
비활성화할 뿐, 유지 대상인 raw `DistanceToImagePlane` depth image나
depth point cloud를 끄지 않는다. 이 스위치가 false일 때 하위 파라미터가
비활성 상태인 것은 의도된 동작이다.

### PASS: path-tracing 설정은 렌더링 모드에 따라 적용됨

`rendering.mode`가 `ray_tracing`인 동안 `path_tracing.*`가 비활성인 것은
의도된 동작이다. path tracing을 선택하면 해당 값들이 사용된다.

### PASS: 내장 및 커스텀 LiDAR profile 입력은 서로 배타적임

정식 YAML에서는 `profile_name`이 활성 상태다. `profile_json_path`와
`usd_profile`은 죽은 필드가 아니라 null로 둔 대체 입력이며, `variant`도
사용되고 있다. `profile_name`과 `profile_json_path` 중 정확히 하나를
선택하도록 검증하므로 Isaac 내장 profile과 커스텀 JSON profile을 모두
수용하면서 모호한 동시 입력은 시작 전에 거부한다.

## 해결된 조사 결과

### RESOLVED: companion 기본 URDF 경로의 checkout 독립성

companion launch의 `~/MarsLab` 하드코딩을 제거했다. 기본 URDF는 launch 파일의
위치를 기준으로 `../assets/m2020-urdf-models/rover/m2020.urdf`를 해석하므로
저장소를 어느 디렉터리에 clone해도 같은 checkout의 submodule을 사용한다.
명시적인 `urdf_path:=...` override와 별도 ROS 환경 실행 계약은 유지한다.

### RESOLVED: 제거된 `initial_joint_positions` no-op 경로

`ControlConfig`에 존재하지 않아 항상 빈 값이던 `initial_joint_positions`
조회와 post-reset 호출, target 변환 helper 및 export를 제거했다. steering
joint의 명시적 0 초기화는 별도 기능이므로 그대로 유지한다.

### RESOLVED: 사용되지 않는 이전 경로와 중복 atmosphere 부트 경로

atmosphere snapshot 조립은 정식 `main.py` 경로만 남겼다. 런타임 단계가
공유하는 `AtmosphereInit` 타입은 유지하고, 호출자가 없던
`boot_atmosphere()`, `AtmosphereBootResult`, `REPO_ROOT`를 제거했다. 함께
확인된 미사용 `check_lidar_cfg()`와 `compute_odom_delta()`도 제거했으며,
sun spherical API 문서는 존재하지 않는 YAML 필드를 언급하지 않도록 현재
계약에 맞췄다.

### RESOLVED: OmniGraph QoS는 transient-local에 의존하지 않음

OmniGraph의 Camera, IMU와 LiDAR는 기존 `sensor_qos`의 best-effort/volatile을
유지한다. 반복 발행되는 joint states는 rclpy TF용 `tf_qos`를 재사용하지 않고
별도의 reliable/volatile `joint_state_qos`를 사용한다. OmniGraph QoS 변환기는
transient-local 입력을 거부하므로 검증되지 않은 late-joiner 동작에 조용히
의존할 수 없다. transient-local은 rclpy가 소유하는 정적 TF 등에서만 사용한다.
사용자 런타임 검증에서 `/rover/joint_states`가 정상 발행됐고, 새 `log.txt`에는
기존 OmniGraph transient-local 경고가 나타나지 않았다. SimulationApp startup,
post-reset gain 검사와 physics override도 정상 완료됐다.

### RESOLVED: sky-dome 하위 설정 전달

기본 YAML에 `rendering.sky_dome` 값을 명시하고, 검증된 `SkyDomeConfig`를
최초 atmosphere snapshot과 동적 tau 업데이트의 `compute_sky_dome_params()`에
전달한다. 색상 endpoint, tau saturation, 밝기 계수와 HDRI 파일명 override가
동일한 설정 소유자를 사용한다.

### RESOLVED: LiDAR 실수 회전율과 override 검증

`rotation_rate_hz`를 정수로 자르지 않고 float 그대로
`scanRateBaseHz`에 저작한다. range, 회전율, 수평 FOV 및 적용 가능한 수직 FOV
attribute는 `Set()` 결과와 readback 값을 검사하며 불일치 시 시작을 실패시킨다.
성공하면 실제 range, 회전율, azimuth를 여러 줄 INFO 로그로 출력한다.

### RESOLVED: ROS namespace와 상대 topic 계약

namespace는 입력 경계에서 바깥 slash를 제거해 정규화하고 topic은 leading 및
trailing slash가 없는 상대 이름만 허용한다. 빈 segment, `.`/`..`, 공백을
거부하며 rclpy와 OmniGraph producer가 공통 resolver로 정확히 하나의 선행
slash를 가진 절대 topic을 만든다.

### RESOLVED: 카메라 focal length 단위

YAML과 스키마 필드를 `focal_length_mm`로 개명했다. 값은 물리 카메라의 mm
단위이며 camera spawner 한 곳에서 Isaac Camera 표현으로 `/10` 변환한다.
기존 단위 없는 `focal_length` 입력은 strict schema가 거부한다.

### RESOLVED: IMU 중력 검사의 설정 소유 관계

IMU 생성 전 PhysicsScene 검사와 보조 `read_imu()` 진단에 있던 `3.72`
하드코딩을 제거했다. 검증된 `mars_env.gravity`가 atmosphere snapshot과 sensor
assembly를 거쳐 두 검사에 전달되므로 실제 PhysX world와 IMU가 같은 YAML
값을 기준으로 삼는다. 기본값뿐 아니라 스키마가 허용하는 다른 Mars 중력값도
별도의 고정 범위와 충돌하지 않는다.

### RESOLVED: 필수 ROS 출력에 붙어 있던 무효 발행 스위치

PointCloud2와 CameraInfo는 유지가 보장되는 필수 출력이므로 실제 그래프를
끄지 못하던 `publish_pointcloud2`, `publish_camera_info` 필드를 ROS 스키마에서
제거했다. 이제 입력 가능한 설정과 런타임 출력 계약이 일치한다.

### RESOLVED: 로버 USD의 빈 visual reference 65개

`m2020_base.usd`에는 visual geometry가 없는 frame에도 `/visuals/...` 내부
reference가 작성되어 있었다. 실제 visual을 가진 URDF link와 유효한 visual
target은 각각 20개로 일치했으며, 6개 wheel mesh도 모두 정상적으로
합성되었다. 따라서 기존 경고는 실제 로버 geometry 누락이 아니라 빈 frame
reference를 잘못 생성한 에셋 저작 잔여물이었다.

기존 layer 구조를 유지하는 targeted rebake로 target이 없는 reference
65개만 제거했다. 정적 OpenUSD composition 결과는 다음과 같다.

- `Unresolved reference prim path`: 65개에서 0개
- 유효한 visual reference: 20개 유지, 모든 target 존재
- mesh reference: 40개 유지
- 6개 wheel visual: 각각 Mesh 1개 유지
- composed stage prim: 343개 유지
- articulation, drive joint, `Frame_WHEEL_*`, default prim 경로 유지
- 파일 형식: USD crate 0.9.0 유지

전체 URDF 재변환이나 runtime 변환은 수행하지 않았으며,
`configuration/m2020_base.usd`만 정리했다. 최종 Isaac 렌더링 외관은 사용자
런타임 검증 경계에 남는다.

### RESOLVED: IMU 샘플링 주기의 설정 소유 관계

ROS 설정 아래 있던 `rover.ros2.rates.imu`를 제거하고 실제 센서 소유 위치인
`rover.sensors.imu.sampling_frequency_hz`로 이동했다. 필드는 Isaac
`IMUSensor.frequency` 계약에 맞는 양의 정수이며, sensor spawner는 더 이상
IMU 생성 때문에 ROS 설정을 받지 않는다. ROS bridge의 죽은 `rates` 모델과
재검증 경로도 함께 제거했다.

IMU 초기화 후 실제 sensor period를 읽어 요청값과 허용 오차 안에서
일치하는지 검사한다. 성공하면 요청 frequency, 실제 frequency, sensor
period를 그룹화된 여러 줄 INFO 로그로 출력하고, 불일치하면 시작을
실패시킨다. 이 값은 PhysX 샘플 생성 주기이며 raw/noisy ROS topic Hz를
보장하지 않는다는 계약을 README에 명시했다.

### RESOLVED: reset 후 PD gain의 DOF 소유 범위

Isaac 5.1의 인덱스 기반 `set_gains()`를 사용해 drive, steer, rocker, bogie로
명시된 DOF만 갱신하도록 변경했다. 갱신 전후에 비소유 DOF gain을 읽어
동일한지 검사하고, 소유 DOF에는 요청한 gain이 실제 적용됐는지 검사한다.
두 검증 중 하나라도 실패하면 시작을 중단한다. 성공 시 소유 DOF 갱신 수와
비소유 DOF 보존 수를 여러 줄 INFO 로그로 출력한다.

### RESOLVED: rigid-body damping 0과 대상 식별 계약

`angular_damping`과 `linear_damping`은 0을 포함해 항상 USD에 저작되므로
사용자가 기존 damping을 명시적으로 비활성화할 수 있다. chassis 설정에는
`rigid_body_prim_name`을 추가했고, 기본 에셋의 실제 합성 대상인
`Body_Chassis/Body_Chassis`를 명시한다. 해당 direct child가 없거나
`RigidBodyAPI`가 없으면 질량, 관성, CoM, damping 또는 센서를 다른 prim에
조용히 적용하지 않고 시작을 실패시킨다.

### RESOLVED: rocker와 bogie damping의 소유 관계

공통 `control.suspension_damping` 필드를 제거했다. rocker와 bogie damping은
이제 `rover.suspension`에서만 가져오며, reset 전에 저작되고 reset 후에는
각각 별도로 재적용된다.

### RESOLVED: wheel link 이름과 drive joint 이름의 혼동

wheel physics는 이제 `rover.wheels.link_names`의 명시적인
`Frame_WHEEL_*` prim을 대상으로 한다. `*_DRIVE`는 articulation joint의
소유 대상으로 유지된다. 대상이 누락되면 reset 전에 실패한다.

### RESOLVED: physics override 적용 여부의 가시성

필수 대상과 USD `Set`/binding 결과를 검사한다. 시작에 성공하면 YAML이
소유하는 실제 물리값을 그룹화된 여러 줄의 요약 로그로 출력한다.

### RESOLVED: 완전히 사용되지 않던 YAML 필드 10개

제거한 항목:

- 사용되지 않던 ROS 발행 주기 필드 7개
- `rendering.resolution`
- `dynamic_atmosphere.tau_profile`
- `dynamic_atmosphere.tau_constant.base_tau`

죽은 tau profile 스키마 타입과 export도 함께 제거했다. 남겨 둔
`dust_optical_depth`는 실제 tau 초기값의 출처로 계속 사용된다.

### RESOLVED: 최초 depth render-variable 경고

Depth image와 카메라에서 생성된 PointCloud2는 모두 유효했다. 카메라
해상도를 낮추자 처리량이 회복되었으므로, 한 번만 발생한
`DistanceToImagePlaneSDhost` 경고는 반복되거나 데이터가 무효해지지 않는
한 초기 그래프 연결 노이즈로 본다.

## 권장 구현 순서

현재 등록된 `OPEN` 또는 `WATCH` 구현 항목은 없다.

## 검증 경계

소스/설정 테스트로 소유 관계, 필드 전달, 실패 동작을 검증할 수 있다.
Isaac GUI, 물리, 센서 정확도, ROS 주기, TF, 시각적 완전성, 정리 동작은
다음 명령으로 사용자가 직접 실행해 검증해야 한다.

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```
