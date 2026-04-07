# PLAN.md -- MarsLab 아키텍처 및 구현 계획

**버전:** 2.0 (최종 -- 13-Agent 적대적 합성)
**날짜:** 2026-04-07
**목표:** ICRA 2027 Seoul (마감 ~2026년 9월 15일)
**기간:** 22주 (4월 7일 -- 9월 15일, 2026)
**라이선스:** Apache 2.0

**방법론:** 본 계획은 13-agent 적대적 토론 시스템을 통해 생성되었다. Agent 1과 6이
아키텍처 중심 및 학습 경로 중심 초안을 독립적으로 작성하였고, Agent 2-4 및 7-9가
교차 리뷰를 수행하여 19건의 핵심 이슈를 발견하였다. Agent 5 및 10-12가 수정사항을
통합 명세로 합성하였으며, Agent 13이 이 최종 문서를 생성하였다. 19건의 핵심
수정사항이 모두 반영되었다 (100% 방어율).

**선행 문서:**
- `plan/marslab_plan_v2.pdf` -- 연구 계획 v2.0
- `plan/marslab_weekly_schedule_en.pdf` -- 22주 스케줄
- `dev/architecture_blueprint_en.md` -- 아키텍처 청사진 (적대적 검증 완료)
- `dev/mars_first_requirements_en.md` -- Mars-First 요구사항 도출
- `dev/rlroverlab_analysis_en.md` -- RLRoverLab API 실현성 분석
- `dev/omnilrs_analysis_plan.md` -- OmniLRS 분석 계획

---

## 1. 목적

본 문서는 MarsLab 개발의 단일 진실 원천(single source of truth)이다. 다음을 정의한다:

1. **무엇을** -- 코드베이스 아키텍처 (디렉토리 트리, 모듈, 인터페이스).
2. **어떻게** -- 각 모듈을 구축 (가장 작은 단위부터, 점진적 확장).
3. **언제** -- 각 부분의 구현 시점 (22주 Phase 1 스케줄).
4. **어떻게 검증** -- 정확성 확인 (단위 테스트, 통합 테스트, 시각 검수).
5. **어떻게 추적** -- 진행 이력 (작업 이력 로그 형식).

프로젝트 중간에 합류하는 제3자를 포함한 모든 개발자가 이 문서를 읽고 전체 프로젝트
상태, 아키텍처 근거, 다음 단계를 파악할 수 있어야 한다.

---

## 2. 기본 원칙

다음 13가지 가이드라인이 모든 아키텍처 및 구현 결정을 지배한다. 각 섹션은 구현하는
가이드라인을 번호로 참조한다 (예: [G1]).

**[G1] 인지 로보틱스 중심.**
MarsLab은 인지 태스크를 위한 사실적 화성 로봇 시뮬레이터이다: 객체 탐지, 의미론적
분할, SLAM, 내비게이션, 탐사. Phase 1 범위 = OD + Seg + 센서 데이터 생성. SLAM/Nav
= Phase 2. RL은 엄격하게 향후 작업(Phase 2+).

**[G2] RL은 향후 작업.**
Phase 1에 RL 환경, 보상 함수, 학습 루프 없음. Isaac Lab의 Gym API wrapper는
Phase 2로 이월. Phase 1 코드는 인지와 데이터 생성만 담당.

**[G3] 참조 코드베이스에서 코드 재사용 금지.**
OmniLRS, RLRoverLab 또는 어떤 참조에서도 코드 복사 금지. 알고리즘/흐름도 영감만
허용. 패턴을 연구하고 알고리즘을 이해한 후, `omni.isaac.lab` API로 처음부터 재구현.
MarsLab 소스에 `OmniLRS`나 `RLRoverLab` 유래 명명 금지. 참고: `omni.*`는 NVIDIA
네임스페이스이며 이 규칙에서 면제.

**[G4] 사실적 렌더링이 최우선.**
RTX path-tracing 렌더링 품질이 핵심 차별점. 고충실도 물리(terramechanics)는
부차적이며 Phase 2로 이월. Phase 1 물리 = 강체 + 화성 보정 마찰 파라미터.

**[G5] YAML 기반 설정.**
모든 환경 파라미터가 YAML 설정 파일에 존재. Python 소스에 하드코딩된 물리 상수 제로.
YAML 파라미터(중력, 먼지 불투명도, 알베도, 암석 밀도) 변경만으로 시뮬레이션 환경이
코드 수정 없이 변경되어야 함.

**[G6] 극단적 모듈성.**
가능한 가장 작은 단위에서 시작: 단일 함수, 단일 클래스, 단일 파일. 복잡도가 요구할
때만 점진적으로 확장. 사용자가 흐름을 따라가며 단계별로 학습할 수 있어야 함. 조기
추상화, 만능 객체, 단일체 모듈 금지.

**[G7] 모든 것에 단위 테스트.**
모든 모듈에 단위 테스트. 순수 연산 모듈(화성 물리, 설정 검증, 암석 SFD 샘플링)은
Isaac Sim 없이 오프라인 테스트. Isaac Sim 의존 모듈은 통합 테스트. 자동화 테스트가
불가능한 경우, 문서화된 GUI 시각 검수 프로토콜 제공.

**[G8] 작업 이력 로그.**
완료된 모든 태스크는 구조화된 로그 항목으로 요약. 프로젝트에 새로 합류하는 제3자가
작업 로그를 읽고 전체 개발 이력을 추적 가능.

**[G9] 아키텍처 우선 계획.**
본 문서가 코드베이스 아키텍처와 상세 구현 계획 모두 포함. 마스터 참조 문서.

**[G10] 사용자 검토 게이트.**
본 계획은 사용자 검토용 초안. 사용자가 검토, 수정, 승인 후 구현 진행. Week 8 및
Week 16에 체크포인트.

**[G11] Ultrathink 전반 적용.**
모든 설계 결정에 깊은 추론 적용. 얕은 패턴 매칭 배제.

**[G12] 13-Agent 적대적 토론.**
본 계획은 다중 agent 적대적 리뷰를 통해 생성. 단일 패스 생성이 아님.
최종 확정 전 모든 핵심 이슈 식별 및 해결.

**[G13] 4개 산출물 파일.**
PLAN.md (EN), PLAN_kor.md (KR), CLAUDE.md (EN), CLAUDE_kor.md (KR) -- 완전하고,
일관되며, 상호 참조됨.

---

## 3. 코드베이스 아키텍처

### 3.1 아키텍처 원칙

**P1: 평면 P0 아키텍처.**
조기 추상화 금지. 평면 절차적 코드로 시작. 경험적 복잡도가 요구할 때만 클래스/패턴
추출. Phase 1에 플러그인 시스템, 만능 객체, 등록 메커니즘 금지.

**P2: 단방향 데이터 흐름.**
Config -> 순수 연산 모듈 -> Isaac Sim 씬 구성 -> 네이티브 시뮬레이션 루프.
어떤 모듈도 시뮬레이션 루프를 수정하지 않음. 순환 의존성 금지. Config만이 모듈 간
공유 의존성.

**P3: 오프라인 우선 테스트.**
모든 순수 연산 모듈(환경 물리, 설정 검증, 암석 SFD, 레이블 변환)은 Isaac Sim이나
GPU 없이 테스트 가능해야 함. Isaac Sim 의존 코드는 통합 전용으로 명확히 표시된
별도 함수/파일에 격리.

### 3.2 디렉토리 트리

모든 파일에 (1) 생성 주차, (2) 구현하는 가이드라인, (3) 예상 라인 수 표기.
패키지 하위 디렉토리별 그룹화. [G6]

```
MarsLab/                                    # 저장소 루트
|-- PLAN.md                                 # Wk 0 | G9       | ~800줄
|-- CLAUDE.md                               # Wk 0 | G9       | ~250줄
|-- README.md                               # Wk 8 | --       | ~100
|-- LICENSE                                 # Wk 0 | --       | Apache 2.0
|-- pyproject.toml                          # Wk 1 | G6       | ~50
|-- .gitignore                              # Wk 1 | --       | ~30
|
|-- .github/                                # CI/CD
|   `-- workflows/
|       |-- unit_tests.yaml                 # Wk 1 | G7       | ~40
|       `-- lint.yaml                       # Wk 1 | G7       | ~25
|
|-- configs/                                # 모든 설정 [G5]
|   |-- mars_env.yaml                       # Wk 1 | G5       | ~60
|   |-- terrain/
|   |   |-- jezero_crater.yaml              # Wk 2 | G5       | ~25
|   |   |-- procedural_flat.yaml            # Wk 5 | G5       | ~20
|   |   |-- procedural_crater.yaml          # Wk 5 | G5       | ~25
|   |   `-- procedural_hills.yaml           # Wk 5 | G5       | ~25
|   |-- robots/
|   |   |-- rover.yaml                      # Wk 4 | G5       | ~30
|   |   |-- rotorcraft.yaml                 # Wk 7 | G5       | ~25
|   |   |-- quadruped.yaml                  # Wk 7 | G5       | ~20
|   |   `-- humanoid.yaml                   # Wk 10 | G5      | ~20
|   |-- sensors/
|   |   |-- stereo_rgb.yaml                 # Wk 11 | G5      | ~20
|   |   |-- depth_camera.yaml               # Wk 11 | G5      | ~15
|   |   |-- lidar_3d.yaml                   # Wk 11 | G5      | ~20
|   |   `-- imu.yaml                        # Wk 11 | G5      | ~15
|   |-- benchmark/
|   |   |-- terrain_seg.yaml                # Wk 13 | G5      | ~30
|   |   `-- domain_randomization.yaml       # Wk 13 | G5      | ~40
|   `-- rendering/
|       `-- path_tracing.yaml               # Wk 6 | G4,G5   | ~20
|
|-- marslab/                                # 메인 Python 패키지
|   |-- __init__.py                         # Wk 1 | G6       | ~5
|   |
|   |-- config/                             # 설정 로딩 [G5][G6]
|   |   |-- __init__.py                     # Wk 1 |          | ~3
|   |   |-- schema.py                       # Wk 1 | G5       | ~150
|   |   `-- loader.py                       # Wk 1 | G5       | ~70
|   |
|   |-- environment/                        # 순수 Python 화성 물리 [G6]
|   |   |-- __init__.py                     # Wk 3 |          | ~3
|   |   |-- sun_position.py                 # Wk 3 | G5,G6    | ~60
|   |   |-- light_intensity.py              # Wk 3 | G5,G6    | ~40
|   |   |-- diffuse_fraction.py             # Wk 3 | G5,G6    | ~50
|   |   `-- sky_dome.py                     # Wk 3 | G4,G6    | ~50
|   |
|   |-- terrain/                            # 지형 생성 + 어노테이션 [G6]
|   |   |-- __init__.py                     # Wk 2 |          | ~3
|   |   |-- dem_loader.py                   # Wk 2 | G5,G6    | ~70
|   |   |-- mesh_builder.py                 # Wk 4 | G6       | ~120
|   |   |-- rock_placer.py                  # Wk 2 | G5,G6    | ~90
|   |   |-- procedural_generator.py         # Wk 5 | G5,G6    | ~120
|   |   |-- material_applicator.py          # Wk 4 | G4,G6    | ~60
|   |   `-- semantic_labeler.py             # Wk 12 | G1,G6   | ~60
|   |
|   |-- rendering/                          # 화성 렌더링 설정 [G4][G6]
|   |   |-- __init__.py                     # Wk 6 |          | ~3
|   |   |-- sky_renderer.py                 # Wk 6 | G4,G6    | ~60
|   |   |-- sun_renderer.py                 # Wk 6 | G4,G6    | ~70
|   |   |-- atmosphere_fog.py               # Wk 6 | G4,G6    | ~50
|   |   `-- render_settings.py              # Wk 6 | G4,G6    | ~40
|   |
|   |-- robots/                             # 로봇 스폰 [G6]
|   |   |-- __init__.py                     # Wk 4 |          | ~3
|   |   |-- rover.py                        # Wk 4 | G6       | ~70
|   |   |-- rotorcraft.py                   # Wk 7 | G6       | ~80
|   |   |-- quadruped.py                    # Wk 7 | G6       | ~50
|   |   `-- humanoid.py                     # Wk 10 | G6      | ~50
|   |
|   |-- sensors/                            # 센서 부착 [G6]
|   |   |-- __init__.py                     # Wk 11 |         | ~3
|   |   |-- camera.py                       # Wk 11 | G5,G6   | ~80
|   |   |-- lidar.py                        # Wk 11 | G5,G6   | ~60
|   |   `-- imu.py                          # Wk 11 | G5,G6   | ~50
|   |
|   |-- ros2_bridge/                        # ROS2 퍼블리싱 [G6]
|   |   |-- __init__.py                     # Wk 9 |          | ~3
|   |   |-- publisher.py                    # Wk 9 | G6       | ~90
|   |   `-- topic_config.py                 # Wk 9 | G6       | ~30
|   |
|   |-- annotation/                         # 합성 데이터 어노테이션 [G6]
|   |   |-- __init__.py                     # Wk 12 |         | ~3
|   |   |-- replicator_setup.py             # Wk 12 | G6      | ~70
|   |   |-- label_converter.py              # Wk 12 | G1,G6   | ~60
|   |   `-- dataset_writer.py               # Wk 12 | G6      | ~70
|   |
|   |-- benchmark/                          # AI4Mars 벤치마크 [G1][G6]
|   |   |-- __init__.py                     # Wk 13 |         | ~3
|   |   |-- data_generator.py               # Wk 13 | G1,G5   | ~110
|   |   |-- domain_randomizer.py            # Wk 13 | G5,G6   | ~90
|   |   `-- evaluator.py                    # Wk 16 | G1      | ~110
|   |
|   `-- utils/                              # 공용 유틸리티 [G6]
|       |-- __init__.py                     # Wk 1 |          | ~3
|       |-- seed.py                         # Wk 1 | G5       | ~25
|       `-- usd_helpers.py                  # Wk 4 | G6       | ~40
|
|-- tests/                                  # 모든 테스트 [G7]
|   |-- __init__.py                         # Wk 1 |          | ~1
|   |-- unit/                               # Isaac Sim 불필요
|   |   |-- __init__.py                     # Wk 1 |          | ~1
|   |   |-- test_config_schema.py           # Wk 1 | G7       | ~80
|   |   |-- test_config_loader.py           # Wk 1 | G7       | ~50
|   |   |-- test_sun_position.py            # Wk 3 | G7       | ~40
|   |   |-- test_light_intensity.py         # Wk 3 | G7       | ~50
|   |   |-- test_diffuse_fraction.py        # Wk 3 | G7       | ~40
|   |   |-- test_sky_dome.py                # Wk 3 | G7       | ~35
|   |   |-- test_dem_loader.py              # Wk 2 | G7       | ~50
|   |   |-- test_rock_placer.py             # Wk 2 | G7       | ~80
|   |   |-- test_seed.py                    # Wk 1 | G7       | ~30
|   |   |-- test_label_converter.py         # Wk 12 | G7      | ~40
|   |   |-- test_robot_config.py            # Wk 4 | G7       | ~40
|   |   |-- test_domain_randomizer.py       # Wk 13 | G7      | ~50
|   |   `-- test_materials.py               # Wk 4 | G7       | ~35
|   |-- integration/                        # Isaac Sim 필요
|   |   |-- __init__.py                     # Wk 6 |          | ~1
|   |   |-- test_terrain_render.py          # Wk 6 | G7       | ~60
|   |   |-- test_robot_spawn.py             # Wk 4 | G7       | ~60
|   |   |-- test_sensor_output.py           # Wk 11 | G7      | ~80
|   |   |-- test_full_scene.py              # Wk 6 | G7       | ~60
|   |   |-- test_annotation.py              # Wk 12 | G7      | ~50
|   |   |-- test_atmosphere_fog.py          # Wk 6 | G7       | ~40
|   |   |-- test_ros2_bridge.py             # Wk 9 | G7       | ~50
|   |   `-- test_multi_robot.py             # Wk 10 | G7      | ~50
|   `-- visual_inspection/
|       `-- checklist.md                    # Wk 6 | G7       | ~50
|
|-- scripts/                                # 진입점
|   |-- hello_isaac.py                      # Wk 1 | G6       | ~40
|   |-- run_scene.py                        # Wk 6 | G6       | ~80
|   |-- generate_dataset.py                 # Wk 13 | G1      | ~60
|   |-- run_benchmark.py                    # Wk 16 | G1      | ~60
|   `-- convert_urdf.py                     # Wk 4 | G6       | ~40
|
|-- assets/                                 # 프로젝트 전용 (Isaac Sim 내장 아님)
|   |-- terrain/
|   |   `-- dem/                            # 다운로드된 HiRISE GeoTIFF
|   |-- sky/
|   |   `-- hdri/                           # 화성 하늘 HDR 이미지
|   |-- materials/
|   |   `-- mars_pbr/                       # 화성 PBR 재질 MDL
|   `-- robots/
|       |-- rover/                          # 커스텀 로버 URDF + 메시
|       `-- rotorcraft/                     # 커스텀 로터크래프트 URDF + 메시
|
|-- docker/                                 # Docker 설정
|   |-- Dockerfile                          # Wk 15 |         | ~60
|   `-- docker-compose.yaml                 # Wk 15 |         | ~30
|
|-- work_log/                               # 작업 이력 [G8]
|   `-- LOG.md                              # Wk 1+ | G8      | append-only
|
`-- dev/                                    # 선행 분석 문서 (기존)
    |-- architecture_blueprint_en.md
    |-- mars_first_requirements_en.md
    |-- rlroverlab_analysis_en.md
    `-- omnilrs_analysis_plan.md
```

**총 예상 소스 라인:** ~3,400 (marslab/ 패키지 + 테스트 + 스크립트)

### 3.3 모듈 설명 및 인터페이스

각 모듈은 단일 책임을 가짐. 의존성은 엄격하게 하향식. [G6]

#### 3.3.1 `marslab/config/` -- 설정 관리

**책임:** YAML 설정 파일 로드, 물리적으로 의미 있는 범위에 대해 모든 파라미터 검증,
모든 랜덤 모듈에 시드 전파. [G5]

**의존성:** 없음 (독립, 순수 Python + pydantic).

**주요 인터페이스:**

```python
# schema.py
class MarsEnvConfig(BaseModel):
    gravity: float = Field(ge=3.0, le=4.0, description="m/s^2")
    atmo_pressure: float = Field(ge=400, le=1200, description="Pa")
    dust_optical_depth: float = Field(ge=0.05, le=6.0, description="tau")
    solar_constant_mean: float = Field(ge=480, le=730, description="W/m^2")
    surface_albedo_range: tuple[float, float]
    seed: int

class MarsLabConfig(BaseModel):
    mars_env: MarsEnvConfig
    terrain: TerrainConfig
    robots: list[RobotConfig]
    rendering: RenderingConfig
    benchmark: BenchmarkConfig | None = None

# loader.py
def load_config(config_path: str) -> MarsLabConfig: ...
def propagate_seeds(config: MarsLabConfig) -> MarsLabConfig: ...
```

#### 3.3.2 `marslab/environment/` -- 화성 환경 상태

**책임:** 설정값으로부터 화성 고유 환경 파라미터를 연산. 순수 연산 -- Isaac Sim
임포트 제로. 오프라인 테스트 가능. [G6]

**의존성:** `marslab/config/`만.

**주요 인터페이스:**

```python
# sun_position.py
def compute_sun_position(azimuth_deg: float, elevation_deg: float) -> SunPosition:
    """Phase 1: YAML에서 사용자 설정 값.
    Phase 2: Allison & McEwen (2000) Ls 기반 연산."""

# light_intensity.py
def compute_direct_intensity(
    solar_constant: float, tau: float, zenith_angle_rad: float
) -> float:
    """Beer 법칙: I = I_0 * exp(-tau / cos(theta_z))."""

# diffuse_fraction.py
def compute_diffuse_fraction(tau: float) -> float:
    """COMIMART 모델 조회. Vicente-Retortillo et al. (2015)."""
```

#### 3.3.3 `marslab/terrain/` -- 지형 생성 및 어노테이션

**책임:** HiRISE DEM 또는 절차적 방법으로 화성 지형 생성. Golombek SFD로 암석 배치.
AI4Mars 의미론적 레이블 할당. PBR 재질 적용. [G6]

**의존성:** `marslab/config/`. Isaac Sim은 `mesh_builder.py`에서만 필요.

```python
# dem_loader.py  (오프라인, Isaac Sim 불필요)
def load_hirise_dem(dem_path: str) -> tuple[np.ndarray, dict]: ...

# rock_placer.py  (오프라인, Isaac Sim 불필요)
def sample_rocks_golombek(
    area_m2: float, k: float, diameter_range: tuple[float, float], seed: int
) -> list[RockPlacement]:
    """Golombek & Rapp (1997): F_k(D) = k * exp[-q(k) * D]."""
```

#### 3.3.4 `marslab/rendering/` -- 화성 렌더링 설정

**책임:** 화성 정확 이미지를 위한 Isaac Sim 렌더링 파이프라인 설정. [G4][G6]

```python
def configure_sky_dome(stage, sky_params: SkyDomeParams) -> None: ...
def configure_sun_light(stage, sun_pos, intensity, diffuse_fraction) -> None: ...
def configure_atmosphere_fog(stage, tau: float) -> None: ...
def set_render_mode(mode: str) -> None:
    """path_tracing (데이터 생성 기본) 또는 ray_tracing (인터랙티브 기본)."""
```

#### 3.3.5 `marslab/robots/` -- 로봇 통합

**책임:** 로봇 로드 및 스폰. 내장 USD 에셋은 경로로 참조, 저장소에 복사하지 않음. [G6]

```python
def spawn_rover(stage, config: RobotConfig, gravity: float) -> None: ...
def spawn_rotorcraft(stage, config, gravity, atmo_density) -> None: ...
def spawn_quadruped(stage, config: RobotConfig, gravity: float) -> None:
    """Go2 내장 USD. 인지 전용."""
def spawn_humanoid(stage, config: RobotConfig, gravity: float) -> None:
    """G1 내장 USD. 인지 전용. 동역학 검증 주장 없음."""
```

#### 3.3.6-3.3.9 나머지 모듈

- **`sensors/`**: 인지 센서 부착 및 설정. 모든 파라미터 YAML에서 로드. [G5][G6]
- **`ros2_bridge/`**: 센서 데이터를 ROS2 Humble 토픽으로 퍼블리시. [G6]
- **`annotation/`**: Isaac Sim Replicator로 의미론적/인스턴스/깊이 어노테이션. [G6]
- **`benchmark/`**: 시드 고정 대량 데이터 생성 + domain randomization + AP/mIoU/F1. [G1][G6]

### 3.4 의존성 규칙

이 규칙은 불가침이다. [G6]

1. **순환 의존성 금지.** A가 B를 임포트하면, B는 절대 A를 임포트하지 않음.
2. **Config만 공유 의존성.** 모든 모듈이 `MarsLabConfig`에서 읽음.
3. **`environment/`는 Isaac Sim 임포트 제로.** 순수 Python. 오프라인 테스트 가능.
4. **`terrain/dem_loader.py`와 `terrain/rock_placer.py`는 Isaac Sim 임포트 제로.**
5. **`rendering/`은 `environment/`에 의존** (단방향).
6. **`robots/`는 `config/`에만 의존.** terrain이나 rendering을 임포트하지 않음.
7. **어떤 모듈도 Isaac Sim 시뮬레이션 루프를 수정하지 않음.**
8. **랜덤성을 사용하는 모든 함수는 `seed` 파라미터를 받음.** [G5]

### 3.5 설정 스키마

**마스터 설정:** `configs/mars_env.yaml` [G5]

```yaml
mars_env:
  gravity: 3.72                    # m/s^2 (IAU 표준)
  atmo_pressure: 610               # Pa (Viking/MSL 평균)
  atmo_density: 0.020              # kg/m^3
  dust_optical_depth: 0.3          # tau (맑은 날 기본값)
  solar_constant_mean: 589         # W/m^2 at 1.52 AU
  surface_albedo_range: [0.10, 0.40]
  surface_temp_mean: -60           # 섭씨
  sol_duration_seconds: 88642      # 24시간 37분 22초
  dust_opacity_range: [0.5, 2.0]   # DR용 tau 범위
  seed: 42

terrain:
  source: "hirise"
  dem_path: "assets/terrain/dem/jezero_crater.tif"
  rock_sfd_k: 0.05                # CFA = 5%
  rock_diameter_range: [0.05, 3.0]
  semantic_classes: ["soil", "bedrock", "sand", "big_rock"]
  seed: 42

rendering:
  mode: "path_tracing"
  sky_dome_hdri_dir: "assets/sky/hdri/"
  resolution: [1280, 720]

robots:
  - type: "rover"
    urdf_path: "assets/robots/rover/perseverance.urdf"
    spawn_position: [0.0, 0.0, 0.5]
    sensor_config_paths:
      - "configs/sensors/stereo_rgb.yaml"
      - "configs/sensors/depth_camera.yaml"
      - "configs/sensors/lidar_3d.yaml"
      - "configs/sensors/imu.yaml"

benchmark:
  annotation_format: "ai4mars"
  dr_axes: ["dust_optical_depth", "surface_albedo", "rock_sfd_k",
            "sun_elevation", "camera_trajectory"]
  num_samples: 10000
  seed: 42
```

---

## 4. 우선순위 등급 [G10]

모든 태스크와 기능이 분류됨:

- **MUST:** ICRA 2027 MVP 제출에 필수. 실패 = 논문 없음.
  포함: config, 지형 (HiRISE + 절차적), 대기, 렌더링, 로버, 센서, 어노테이션,
  벤치마크 평가.
- **SHOULD:** 논문을 상당히 강화. 1주 이상 지연 시에만 삭감.
  포함: 로터크래프트, 사족보행, 다중 로봇, Docker, 절차적 지형 프리셋.
- **COULD:** 있으면 좋은 수준. 시간 압박 시 최우선 이월 대상.
  포함: 휴머노이드 (G1), arXiv 프리뷰, 고급 DR 축.

**MVP 정의:** 화성 환경 + 단일 로버 + 지형 분할 벤치마크.
논문은 로버만으로도 성립. 다중 로봇은 강화 요소이나 필수는 아님.

---

## 5. 구현 계획 (22주)

### 5.1 Phase 개요

| Phase | 주차 | 날짜 | 중점 |
|-------|------|------|------|
| Phase 1a | Wk 1-8 | 4/7 -- 5/31 | Config, 지형, 대기, 렌더링, 로버 |
| Phase 1b | Wk 9-16 | 6/2 -- 7/27 | ROS2, 다중 로봇, 센서, 벤치마크, 어노테이션 |
| Phase 1c | Wk 17-22 | 7/28 -- 9/15 | Sim2Real 실험, 논문, 제출 |

### 5.2 주차별 구현 (가장 작은 단위부터) [G6]

---

#### WEEK 1 (4/7-13): 개발 환경 + Config + CI

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | Isaac Sim 5.x 설치, GPU 확인 | MUST | -- | -- |
| 2 | 저장소 구조, pyproject.toml, .gitignore 생성 | MUST | pyproject.toml | G6 |
| 3 | GitHub Actions CI 설정 (단위 테스트 + lint) | MUST | .github/workflows/ | G7 |
| 4 | seed.py 작성 (set_global_seed) | MUST | marslab/utils/seed.py | G5 |
| 5 | config schema.py 작성 (pydantic 모델 전체) | MUST | marslab/config/schema.py | G5 |
| 6 | config loader.py 작성 | MUST | marslab/config/loader.py | G5 |
| 7 | mars_env.yaml 작성 (전체 설정) | MUST | configs/mars_env.yaml | G5 |
| 8 | hello_isaac.py 작성 (Isaac Sim 동작 확인) | MUST | scripts/hello_isaac.py | G6 |
| 9 | config + seed 단위 테스트 작성 | MUST | tests/unit/ | G7 |

**산출물:** Config 검증 완료, CI 그린, Isaac Sim이 hello_isaac.py 실행.

---

#### WEEK 2 (4/14-20): HiRISE 지형 + 암석 배치 (오프라인)

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | HiRISE DTM 다운로드 (Jezero) | MUST | assets/terrain/dem/ | -- |
| 2 | dem_loader.py 작성 (GDAL -> numpy) | MUST | marslab/terrain/dem_loader.py | G5,G6 |
| 3 | rock_placer.py 작성 (Golombek SFD) | MUST | marslab/terrain/rock_placer.py | G5,G6 |
| 4 | jezero_crater.yaml 작성 | MUST | configs/terrain/ | G5 |
| 5 | 단위 테스트 작성 | MUST | tests/unit/ | G7 |

**HiRISE DTM 출처:**
- AWS: `s3://nasa-usgs-mars-hirise-dtms/` (무료, 인증 불필요)
- 특정 제품: DTEEC_045994_1985_046060_1985 (Jezero Crater)
- USGS: `astrogeology.usgs.gov/search?pmi-target=mars`

**산출물:** 오프라인 지형 + 암석 파이프라인. 모든 단위 테스트 통과.

---

#### WEEK 3 (4/21-27): 화성 대기 + 조명 (오프라인)

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | sky_dome.py 작성 (tau -> 색상/밝기) | MUST | marslab/environment/ | G4,G6 |
| 2 | light_intensity.py 작성 (Beer 법칙) | MUST | marslab/environment/ | G5,G6 |
| 3 | diffuse_fraction.py 작성 (COMIMART) | MUST | marslab/environment/ | G5,G6 |
| 4 | sun_position.py 작성 (설정 가능) | MUST | marslab/environment/ | G5,G6 |
| 5 | 대기 단위 테스트 전체 작성 | MUST | tests/unit/ (4개 파일) | G7 |

**compute_sun_position Phase 1 vs Phase 2:**
- Phase 1: `compute_sun_position(azimuth_deg, elevation_deg) -> SunPosition`
  (YAML에서 사용자 설정, 궤도역학 없음)
- Phase 2: `compute_sun_position(ls, latitude, time_of_sol) -> SunPosition`
  (Allison & McEwen 2000 Ls 기반 연산)
- SunPosition dataclass는 Phase 간 변경 없음.

**산출물:** 모든 화성 물리 오프라인 테스트 가능. Isaac Sim 의존성 제로.

---

#### WEEK 4 (4/28 -- 5/4): 로버 (단순화 차체) + PBR 재질

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | material_applicator.py 작성 | MUST | marslab/terrain/ | G4,G6 |
| 2 | mesh_builder.py 작성 (고도 -> USD) | MUST | marslab/terrain/ | G6 |
| 3 | 단순화 로버 URDF 생성 (박스 차체 + 6바퀴) | MUST | assets/robots/rover/ | G6 |
| 4 | rover.py 작성 (spawn_rover) | MUST | marslab/robots/ | G6 |
| 5 | convert_urdf.py 스크립트 작성 | MUST | scripts/ | G6 |
| 6 | 단위 테스트 (로봇 설정, 재질) | MUST | tests/unit/ | G7 |
| 7 | test_robot_spawn.py 작성 (통합) | MUST | tests/integration/ | G7 |

**로버 URDF 출처:**
- Wk 4: 단순화 박스 차체 + 6개 원통형 바퀴. 로커보기 없음.
  목적: URDF->USD 파이프라인, 중력, 지형 상호작용 검증.
- Wk 14: NASA 3D Resources CAD에서 풀 로커보기 (nasa3d.arc.nasa.gov).

**산출물:** 화성 지형 위의 로버. 화성 중력 확인. PBR 재질 v1.

---

#### WEEK 5 (5/5-11): 절차적 지형 + 시드 재현성

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | procedural_generator.py 작성 (flat/crater/hills) | SHOULD | marslab/terrain/ | G5,G6 |
| 2 | 3개 지형 프리셋 YAML 작성 | SHOULD | configs/terrain/ | G5 |
| 3 | 병합 충돌 메시 구현 | SHOULD | marslab/terrain/ | G6 |
| 4 | 모든 모듈에서 시드 재현성 확인 | MUST | tests/ | G5 |

**산출물:** 3+ 지형 프리셋. 시드 재현성 단대단 검증.

---

#### WEEK 6 (5/12-18): 렌더링 통합 + 시각 검증

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | render_settings.py 작성 | MUST | marslab/rendering/ | G4 |
| 2 | sky_renderer.py 작성 (돔 라이트 + HDRI) | MUST | marslab/rendering/ | G4,G6 |
| 3 | sun_renderer.py 작성 (방향 광원) | MUST | marslab/rendering/ | G4,G6 |
| 4 | atmosphere_fog.py 작성 (tau -> 가시거리) | MUST | marslab/rendering/ | G4,G6 |
| 5 | run_scene.py 작성 (전체 씬 오케스트레이터) | MUST | scripts/ | G6 |
| 6 | 통합 테스트: 전체 씬, 대기 안개 | MUST | tests/integration/ | G7 |
| 7 | 시각 검수: 화성 vs 달, tau 비교 | MUST | -- | G7 |

**렌더링 모드:** 데이터 생성 기본: RTX Interactive (path-tracing).
인터랙티브 개발 기본: RTX Real-Time (ray-tracing). 양쪽 항상 지원.

**산출물:** 통합 화성 씬 v1. 실제 화성 사진과 스크린샷 비교.

---

#### WEEK 7 (5/19-25): 로터크래프트 + 사족보행 로봇

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | Ingenuity급 로터크래프트 URDF 생성 | SHOULD | assets/robots/rotorcraft/ | G6 |
| 2 | rotorcraft.py 작성 (단순화 운동학) | SHOULD | marslab/robots/ | G6 |
| 3 | quadruped.py 작성 (Go2 내장 USD) | SHOULD | marslab/robots/ | G6 |
| 4 | 로봇 설정 YAML 작성 | SHOULD | configs/robots/ | G5 |

**산출물:** 화성 씬에 3종 로봇 타입.

---

#### WEEK 8 (5/26 -- 6/1): 체크포인트 + 버퍼

**>>> 사용자 검토 게이트 1 <<<** [G10]

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | Phase 1a 체크포인트 보고서 | MUST | work_log/LOG.md | G8 |
| 2 | README.md v1 (설치 가이드 포함) | SHOULD | README.md | -- |
| 3 | 현재 역량 데모 영상 | SHOULD | -- | -- |
| 4 | 버퍼: 지연된 MUST 태스크 만회 | MUST | -- | -- |
| 5 | 스케줄 평가 + 재우선순위화 | MUST | -- | G10 |

**산출물:** 체크포인트 보고서. 사용자 검토. 필요 시 버퍼 소진.

---

#### WEEK 9 (6/2-8): ROS2 Bridge

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | topic_config.py 작성 | MUST | marslab/ros2_bridge/ | G6 |
| 2 | publisher.py 작성 | MUST | marslab/ros2_bridge/ | G6 |
| 3 | test_ros2_bridge.py 작성 | MUST | tests/integration/ | G7 |

**산출물:** `ros2 topic list/echo`로 ROS2 토픽 검증.

---

#### WEEK 10 (6/9-15): 다중 로봇 + 휴머노이드

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | humanoid.py 작성 (G1 내장 USD) | COULD | marslab/robots/ | G6 |
| 2 | 독립 네임스페이스 다중 로봇 스폰 | SHOULD | marslab/robots/ | G6 |
| 3 | FPS 벤치마크: 1/2/3/4 로봇 | SHOULD | -- | -- |
| 4 | test_multi_robot.py 작성 | SHOULD | tests/integration/ | G7 |

**산출물:** 다중 로봇 데모. G1 인지 전용 (동역학 주장 없음).

---

#### WEEK 11 (6/16-22): 전체 센서 스위트

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | imu.py 작성 (화성 보정 노이즈) | MUST | marslab/sensors/ | G5,G6 |
| 2 | camera.py 작성 (스테레오 RGB + 깊이) | MUST | marslab/sensors/ | G5,G6 |
| 3 | lidar.py 작성 | MUST | marslab/sensors/ | G5,G6 |
| 4 | 센서 설정 YAML 작성 | MUST | configs/sensors/ | G5 |
| 5 | test_sensor_output.py 작성 | MUST | tests/integration/ | G7 |
| 6 | **IMU 중력 테스트: z축 = 3.72 +/- 0.05** | MUST | tests/integration/ | G7 |

**산출물:** 4가지 센서 모달리티 ROS2 토픽 퍼블리시. IMU 중력 검증.

---

#### WEEK 12 (6/23-29): 어노테이션 파이프라인

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | semantic_labeler.py 작성 (AI4Mars 4클래스) | MUST | marslab/terrain/ | G1 |
| 2 | replicator_setup.py 작성 | MUST | marslab/annotation/ | G6 |
| 3 | label_converter.py 작성 | MUST | marslab/annotation/ | G1 |
| 4 | dataset_writer.py 작성 | MUST | marslab/annotation/ | G6 |
| 5 | 단위 + 통합 어노테이션 테스트 | MUST | tests/ | G7 |

**산출물:** 어노테이션 파이프라인 v1. RGB + 의미론적 레이블 쌍.

---

#### WEEK 13 (6/30 -- 7/6): 벤치마크 설계

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | domain_randomizer.py 작성 (5개 DR 축) | MUST | marslab/benchmark/ | G5 |
| 2 | data_generator.py 작성 (시드 고정 대량 생성) | MUST | marslab/benchmark/ | G1,G5 |
| 3 | 벤치마크 설정 YAML 작성 | MUST | configs/benchmark/ | G5 |
| 4 | test_domain_randomizer.py 작성 | MUST | tests/unit/ | G7 |

**산출물:** 벤치마크 프로토콜. 합성 데이터셋 v1 (10K+ 쌍).

---

#### WEEK 14 (7/7-13): 로봇 마무리 + 데이터셋 확정

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | 로버 URDF 업그레이드: 풀 로커보기 | SHOULD | assets/robots/rover/ | -- |
| 2 | 로봇 모델 QA (충돌, 관성, 관절) | MUST | -- | -- |
| 3 | 합성 데이터셋 완료, train/val/test 분할 | MUST | -- | G5 |

**산출물:** 최종 로봇 모델. 완전한 합성 데이터셋.

---

#### WEEK 15 (7/14-20): Docker + 버퍼

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | Dockerfile + docker-compose 작성 | SHOULD | docker/ | -- |
| 2 | 전체 DR 다양성으로 최종 데이터 생성 | MUST | -- | G5 |
| 3 | 버퍼: SHOULD 태스크 만회 | -- | -- | -- |

**산출물:** Docker 이미지 v1. 최종 데이터셋.

---

#### WEEK 16 (7/21-27): ML 파이프라인 + 평가

**>>> 사용자 검토 게이트 2 <<<** [G10]

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | evaluator.py 작성 (AP, mIoU, F1) | MUST | marslab/benchmark/ | G1 |
| 2 | run_benchmark.py 스크립트 작성 | MUST | scripts/ | G1 |
| 3 | 전체 시스템 사용자 검토 | MUST | -- | G10 |

**산출물:** 평가 파이프라인 준비 완료. Phase 1c 사용자 승인.

---

#### WEEKS 17-22: 실험 + 논문

| 주차 | 중점 | 우선순위 |
|------|------|----------|
| 17 | SegFormer 학습, zero-shot + fine-tune (AI4Mars) | MUST |
| 18 | 절삭 연구, 다중 로봇 데모, 실패 분석 | MUST/SHOULD |
| 19 | 논문 초안 v1 (ICRA 6+2 형식) | MUST |
| 20 | 논문 v2, 3분 영상, 코드 정리 | MUST |
| 21 | 내부 리뷰, IEEE 형식, 최종 마무리 | MUST |
| 22 | ICRA 2027 제출 + GitHub v1.0.0 릴리스 | MUST |

---

## 6. 테스트 전략 [G7]

### 6.1 단위 테스트 (Isaac Sim 불필요)

실행: `pytest tests/unit/ -v` (GPU 불필요, CI에서 실행)

| 모듈 | 테스트 파일 | 통과 기준 |
|------|------------|----------|
| config | test_config_schema.py | 부적절한 파라미터가 ValidationError 발생 |
| config | test_config_loader.py | Config 정상 로드, 시드 상속 |
| environment | test_light_intensity.py | Appelbaum & Flood (1990) 대비 5% 이내 |
| environment | test_diffuse_fraction.py | tau=0.3: [0.29, 0.38]; tau=1.0: [0.50, 0.53] |
| environment | test_sun_position.py | 물리적으로 합리적인 천정각 |
| environment | test_sky_dome.py | 낮은 tau에서 버터스카치 RGB 범위 |
| terrain | test_dem_loader.py | 고도 범위가 GeoTIFF 헤더와 +/- 0.1m 일치 |
| terrain | test_rock_placer.py | CFA가 VL1/VL2/MPF 데이터 대비 10% 이내 |
| terrain | test_materials.py | 알베도가 화성 범위 [0.10, 0.40] 이내 |
| annotation | test_label_converter.py | AI4Mars 4클래스 레이블 유효 |
| benchmark | test_domain_randomizer.py | 시드 재현성, 파라미터 범위 |
| robots | test_robot_config.py | URDF 경로 유효, 스폰 위치 유효 |
| utils | test_seed.py | 동일 시드 = 동일 시퀀스 |

### 6.2 통합 테스트 (Isaac Sim 필요)

실행: `pytest tests/integration/ -v`

| 테스트 파일 | 통과 기준 |
|------------|----------|
| test_terrain_render.py | 지형 로드 및 렌더링 에러 없음 |
| test_robot_spawn.py | IMU z축 = 3.72 +/- 0.05 m/s^2 |
| test_sensor_output.py | 모든 센서가 설정 Hz +/- 10%로 퍼블리시 |
| test_full_scene.py | 화성 유사 렌더링 (달도 지구도 아님) |
| test_annotation.py | AI4Mars 레이블이 RGB와 픽셀 정렬 |
| test_atmosphere_fog.py | tau에 따라 가시거리 변화 |
| test_ros2_bridge.py | 토픽 표시, 5초 이내 메시지 수신 |
| test_multi_robot.py | 2+ 로봇이 독립 네임스페이스로 동작 |

### 6.3 시각 검수 프로토콜 [G7]

**파일:** `tests/visual_inspection/checklist.md`

| 체크포인트 | 검수 항목 | 비교 대상 |
|-----------|----------|----------|
| V1 | 하늘이 버터스카치색 (파란색/검은색 아님) | MSL Mastcam 하늘 이미지 |
| V2 | 지형이 실제 화성 지형과 유사 | 동일 지점 HiRISE 이미지 |
| V3 | 암석 분포가 자연스러움 | 화성 표면 사진 |
| V4 | tau=0.3 vs tau=2.0 시각적 차이 | 나란히 비교 스크린샷 |
| V5 | 화성 렌더링 vs 달 파라미터 | 구별 가능해야 함 |
| V6 | 지형 위 로버, 서스펜션 보임 | 시각 확인 |
| V7 | 3대 로봇 동시 보임 | 시각 확인 |
| V8 | 의미론적 레이블 오버레이 정렬 | RGB 위 레이블 맵 |

### 6.4 CI 파이프라인

- `.github/workflows/unit_tests.yaml`: 모든 push/PR에서 실행. GPU 불필요.
- `.github/workflows/lint.yaml`: black + ruff 모든 push/PR에서 실행.
- 통합 테스트: 수동 실행 또는 GPU 지원 CI (가용 시).

---

## 7. 작업 이력 로그 [G8]

### 7.1 위치

**파일:** `work_log/LOG.md` (추가 전용)

프로젝트 중간에 합류하는 제3자가 이 파일을 읽고 전체 개발 이력을 파악.

### 7.2 항목 템플릿

```markdown
## [YYYY-MM-DD] 태스크 제목

**주차:** Wk N (월 DD -- 월 DD)
**모듈:** marslab/module_name/
**유형:** [Feature | Fix | Test | Research | Documentation]

### 수행 내용
- 파일 참조가 포함된 간결한 글머리 기호.

### 핵심 결정
- 근거가 포함된 아키텍처/구현 결정.

### 테스트 결과
- 단위 테스트: N개 통과, M개 실패.
- 통합 테스트: 결과 요약.
- 시각 검수: 통과/실패 (스크린샷 경로 포함).

### 차단 요소 / 이슈
- 발생한 문제와 해결 방법.

### 다음 단계
- 계획에서 이 태스크 이후의 작업.
```

---

## 8. Phase 전환 기준

### 8.1 Phase 1a -> Phase 1b (Wk 8 -> Wk 9) [G10]

모두 충족되어야 함:

- [ ] `marslab/config/` 완전 동작, 검증된 YAML 로딩.
- [ ] `marslab/environment/` Beer 법칙, 확산 비율, 스카이돔 정상 연산.
- [ ] `marslab/terrain/` HiRISE DEM 로드, 절차적 지형, Golombek SFD 암석 배치.
- [ ] `marslab/rendering/` 화성 유사 씬 생성 (버터스카치 하늘, 올바른 그림자).
- [ ] 로버가 3.72 m/s^2 중력으로 화성 씬에 스폰.
- [ ] 모든 단위 테스트 통과. 통합 테스트 통과.
- [ ] 시각 검수 V1-V5 서명 완료.

### 8.2 Phase 1b -> Phase 1c (Wk 16 -> Wk 17) [G10]

모두 충족되어야 함:

- [ ] ROS2 bridge가 모든 센서 데이터를 올바른 토픽으로 퍼블리시.
- [ ] 다중 로봇 스폰 (3+ 타입) 동시 동작.
- [ ] 4가지 센서 모달리티 모두 검증.
- [ ] 어노테이션 파이프라인이 AI4Mars 호환 레이블 생성.
- [ ] 벤치마크 합성 데이터셋 생성 (10K+ 쌍, 시드 고정 DR).

### 8.3 Phase 1 -> Phase 2 (ICRA 이후) [G2]

모두 충족되어야 함:

- [ ] ICRA 2027 논문 제출.
- [ ] GitHub v1.0.0 공개 릴리스.
- [ ] AI4Mars 벤치마크: mIoU > 베이스라인.
- [ ] Gap 분석으로 부재한 P1/P2 현상 문서화.
- [ ] 22주 전체 작업 로그 완료. [G8]

**Phase 2 변경 사항:**
- RL 통합 (Isaac Lab Gym API wrapper). [G2]
- Terramechanics 플러그인 (데이터 기반). [G4]
- SLAM/Nav 모듈. [G1]
- Ls 파라미터화 시간 변동.

**변경되지 않는 사항:**
- Config 스키마 (확장, 파괴 아님). [G5]
- 모듈 경계. Isaac Sim 코어 엔진. AI4Mars 벤치마크 형식.

---

## 9. 안티패턴 [G3][G5][G6]

### 9.1 화성 파라미터 하드코딩 [G5]
**실수:** Python 소스에 `gravity = 3.72` 작성.
**규칙:** 모든 상수는 `configs/mars_env.yaml`에. `MarsLabConfig`로 로드.

### 9.2 참조 코드 복사 [G3]
**실수:** OmniLRS나 RLRoverLab에서 지형 코드 복사-붙여넣기.
**규칙:** 알고리즘 읽기. 이해. `omni.isaac.lab` API로 재작성.

### 9.3 폐기된 API 사용
**실수:** `omni.isaac.orbit`에서 임포트.
**규칙:** 항상 `omni.isaac.lab` 사용. `omni.isaac.orbit` 절대 불가.

### 9.4 프로토타입 전 추상화 구축 [G6]
**실수:** 1일차에 플러그인 시스템 설계.
**규칙:** 평면 절차적 코드 작성. 패턴이 나타날 때만 추상화 추출.

### 9.5 Phase 1 중 Phase 2 설계
**실수:** "향후 확장성"을 위한 terramechanics 인터페이스 구축.
**규칙:** Phase 1은 동작하는 MVP 전달. Phase 2 인터페이스는 Phase 1 학습에서 도출.

### 9.6 Isaac Sim 내장 에셋 복사
**실수:** G1/Go2 USD 파일을 `assets/`에 복사.
**규칙:** Isaac Sim 에셋 경로로 참조. 절대 복사 금지.

### 9.7 RL을 Phase 1 작업으로 취급 [G1][G2]
**실수:** 보상 함수나 학습 루프 추가.
**규칙:** Phase 1은 인지 전용. RL은 엄격하게 향후 작업.

---

## 10. 참고 문헌

### 행성 과학

1. NASA Mars Fact Sheet. https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html
2. Golombek & Rapp (1997). Rock SFD on Mars. JGR 102(E2).
3. Golombek et al. (2003). Rock size-frequency distributions. JGR 108(E12).
4. Golombek et al. (2021). InSight landing site assessment. Earth & Space Science.
5. Smith (2004). TES atmospheric observations. Icarus 167.
6. Vicente-Retortillo et al. (2015). COMIMART model. JSWSC.
7. Appelbaum & Flood (1990). Solar radiation on Mars. NASA TM-102299.
8. Swan et al. (2021). AI4Mars: Terrain-aware driving on Mars. CVPRW.
9. Allison & McEwen (2000). Areocentric solar coordinates. Planet. Space Sci. 48(2-3).

### 시뮬레이션 플랫폼 (연구용, 코드 재사용 아님) [G3]

10. Richard et al. (2023). OmniLRS. arXiv:2309.08997.
11. Mortensen & Boegh (2024). RLROVERLAB. iSpaRo 2024.
12. SRB (2025). arXiv:2509.23328.
13. Sim2Dust (2025). arXiv:2508.11503.
14. unitree_sim_isaaclab (2025). github.com/unitreerobotics/unitree_sim_isaaclab.

### 엔진 문서

15. Isaac Lab API Reference. isaac-sim.github.io/IsaacLab/.
16. Isaac Sim Robot Assets. docs.isaacsim.omniverse.nvidia.com/
17. NVIDIA Replicator Tutorials. docs.isaacsim.omniverse.nvidia.com/

---

*본 문서는 19/19 핵심 수정사항이 적용된 13-agent 적대적 토론 시스템을 통해
생성되었다. ICRA 2027 Seoul을 목표로 하는 MarsLab 개발의 단일 진실 원천으로
기능한다.*
