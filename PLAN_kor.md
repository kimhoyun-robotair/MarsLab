# PLAN.md -- MarsLab 아키텍처 및 구현 계획

**버전:** 4.0 (iSpaRo 2026 — 시나리오 기반 로보틱스 플랫폼)
**날짜:** 2026-04-14
**목표:** 다양한 미션 시나리오를 지원하는 표준화된 화성 로보틱스 테스트 플랫폼
**기간:** 8주 (4/14 -- 6/16, 2026) v1.0 iSpaRo 제출
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

> **참고 (2026-04-14):** iSpaRo 2026 제출 기준으로 재구성 (6/16 마감).
> 버전 로드맵: v1.0 (시나리오+로보틱스) → v2.0 (Photorealism) → v3.0 (Terramechanics).

버전별 분류:

- **v1.0 MUST (iSpaRo 2026):** 7개 미션 시나리오, 로버 URDF 수정, 동적 대기,
  SLAM 통합, Nav2 통합, 실험 평가, 8페이지 논문.
- **v1.0 SHOULD:** 7개 시나리오 전부 완성. GitHub v1.0.0 릴리스.
- **v2.0 (iSpaRo 이후):** OmniLRS급 Photorealism (고폴리 암석, 4K HDRI, anti-tiling,
  pebble scatter).
- **v3.0 (향후):** Terramechanics, RL 환경, 다중 로봇 협조.

**MVP 정의:** 3+ 시나리오 + 로버 + SLAM + Nav2 + 논문.
최소 제출 가능: 시나리오 1-3 + 동적 대기 + SLAM/Nav2 실험.

---

## 5. 구현 계획

### 5.1 버전 로드맵

> **참고 (2026-04-14):** Photorealism-first에서 시나리오 기반 로보틱스 플랫폼으로
> 전환. 정체성: 렌더러 → 로보틱스 테스트베드. Wk 1-9 완료. v1.0은 iSpaRo 2026 대상.

| 버전 | 대상 | 중점 | 마감 |
|------|------|------|------|
| Foundation (Wk 1-9) | -- | Config, 지형, 대기, 렌더링, 로봇, 센서, ROS2 | **완료** |
| **v1.0** | **iSpaRo 2026** | 7개 미션 시나리오 + 로버 SLAM/Nav2 + 논문 (8p) | **6/16** |
| v2.0 | iSpaRo 이후 | OmniLRS급 Photorealism | 미정 |
| v3.0 | 향후 | Terramechanics, RL, 다중 로봇 협조 | 미정 |

### 5.2 Foundation (Wk 1-9, 완료)

Wk 1-9에서 핵심 인프라 구축 완료. git 이력 및 work_log/LOG.md 참조.
완료: config, HiRISE DEM, 절차적 지형, 대기, 렌더링, 로봇 3종,
센서 (RGB/depth/IMU/LiDAR), ROS2 bridge, 140 단위 테스트.

### 5.3 v1.0 일정 (8주, 4/14 -- 6/16) [G6]

---

#### WEEK 1 (4/14-20): 로버 URDF 수정 + 이동성 확보

**v1.0 MUST:** 로버 URDF 수정, 7개 미션 시나리오, 동적 대기,
SLAM + Nav2 통합, 실험 평가, 8페이지 iSpaRo 논문.

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | 로버 URDF 수정 (오픈소스 채택 또는 재설계) | MUST | assets/robots/rover/ | G4 |
| 2 | fix_base=False 설정, 지형 위 안착 검증 | MUST | marslab/robots/rover.py | G4 |
| 3 | run_scene.py 로봇 스폰 주석 해제 | MUST | scripts/run_scene.py | -- |
| 4 | mars_env.yaml 로봇 주석 해제 | MUST | configs/mars_env.yaml | G5 |

**산출물:** 로버가 fix_base=False로 화성 지형 위에서 주행.

---

#### WEEK 2 (4/21-27): 시나리오 1-3 (HiRISE Crop) + ROS2 제어

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | 시나리오 1 config: Basic Mars (Jezero 평원 crop) | MUST | configs/scenarios/basic_mars.yaml | G5 |
| 2 | 시나리오 2 config: Rock-Dense Zone (rock_sfd_k=0.10) | MUST | configs/scenarios/rock_dense.yaml | G5 |
| 3 | 시나리오 3 config: Crater + Slopes (Jezero rim/delta crop) | MUST | configs/scenarios/crater_slopes.yaml | G5 |
| 4 | cmd_vel 서브스크라이버: /cmd_vel → 바퀴 제어 | MUST | marslab/ros2_bridge/cmd_vel_subscriber.py (신규) | G6 |
| 5 | TF 브로드캐스터: odom → base_link → sensor_frames | MUST | marslab/ros2_bridge/tf_broadcaster.py (신규) | G6 |
| 6 | Odometry 퍼블리셔: 바퀴 인코더 → /odom | MUST | marslab/ros2_bridge/odometry.py (신규) | G6 |
| 7 | 센서 ROS2 퍼블리셔 재활성화 | MUST | marslab/ros2_bridge/publisher.py | G6 |

**산출물:** 3개 시나리오 config + /cmd_vel로 로버 원격 제어 가능.

---

#### WEEK 3 (4/28 -- 5/4): 동적 대기 + SLAM 통합

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | 동적 태양 위치: sol 내 방위각 sweep | MUST | marslab/environment/sun_position.py | G5 |
| 2 | 런타임 tau 변화: scene 수준 tau 변경 | MUST | marslab/environment/sky_dome.py | G5 |
| 3 | tau 변경 시 fog 자동 업데이트 | MUST | marslab/rendering/atmosphere_fog.py | G5 |
| 4 | SLAM 통합: slam_toolbox (2D LiDAR) | MUST | ROS2 launch 파일, configs/ | G1 |
| 5 | 시나리오 1-3에서 SLAM 맵 생성 | MUST | -- | G7 |

**산출물:** 동적 대기 + 3개 시나리오 SLAM 맵.

---

#### WEEK 4 (5/5-11): Nav2 통합 + 시나리오 4 (협곡)
| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | Nav2 스택: costmap + planner + controller | MUST | configs/nav2/, launch 파일 | G1 |
| 2 | Nav2 waypoint following 테스트 | MUST | 테스트 스크립트 | G7 |
| 3 | structure_loader.py: OBJ/USD 에셋 로드 + scene 배치 | MUST | marslab/terrain/structure_loader.py (신규) | G6 |
| 4 | 시나리오 4: 협곡 (과학 논문 기반 Blender 메시 + 배치) | SHOULD | configs/scenarios/canyon.yaml, assets/ | G4 |

**산출물:** Nav2 자율 주행 + 협곡 scene.

---

#### WEEK 5 (5/12-18): 시나리오 5-7 (동굴, 우주선, 기지)

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | 시나리오 5: 화성 동굴 (Blender 메시 + PointLight 조명) | SHOULD | configs/scenarios/cave.yaml, assets/ | G4 |
| 2 | 시나리오 6: 우주선 착륙지 (3D 모델 배치) | SHOULD | configs/scenarios/spacecraft.yaml, assets/ | G4 |
| 3 | 시나리오 7: 화성 기지 (habitat/solar panel 모델) | SHOULD | configs/scenarios/mars_base.yaml, assets/ | G4 |
| 4 | 동굴 조명 모드: DomeLight 끄기 + PointLight/SpotLight | SHOULD | marslab/rendering/sky_renderer.py | G5 |

**산출물:** 7개 시나리오 scene 전체 완성.

---

#### WEEK 6 (5/19-25): 실험 + 데이터 수집

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | SLAM 벤치마크: 전체 시나리오 ATE/RPE 측정 | MUST | 평가 스크립트 | G7 |
| 2 | Nav2 벤치마크: 성공률, 경로 길이 측정 | MUST | 평가 스크립트 | G7 |
| 3 | tau 영향 실험: tau 0.3/1.0/2.0/4.0에서 SLAM 정확도 | MUST | -- | G7 |
| 4 | 논문 figure 생성: 시나리오 스크린샷, 그래프 | MUST | scripts/ | G4 |

**산출물:** 논문용 실험 테이블 + figure 전체 완성.
인터랙티브 개발 기본: RTX Real-Time (ray-tracing). 양쪽 항상 지원.

---

#### WEEK 7 (5/26 -- 6/1): 논문 작성 (Draft v1)

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | 논문 초안: 8개 섹션 (intro, related work, 아키텍처, 시나리오, 실험, 결론) | MUST | paper/ | G8 |
| 2 | 데모 영상 (선택, 제출 강화) | SHOULD | -- | -- |

**산출물:** 8페이지 논문 초안 완성.

---

#### WEEK 8 (6/2-16): 논문 수정 + 제출

| # | 태스크 | 우선순위 | 파일 | 가이드라인 |
|---|--------|----------|------|-----------|
| 1 | 자체 리뷰 기반 논문 수정 | MUST | paper/ | G10 |
| 2 | 최종 figure, IEEE 형식 준수 | MUST | paper/ | -- |
| 3 | iSpaRo 2026 제출 | MUST | -- | -- |
| 4 | GitHub v1.0.0 릴리스 | SHOULD | -- | -- |

**>>> v1.0 제출 <<<** [G10]

---

### 5.4 v2.0 / v3.0 (iSpaRo 이후, 향후 작업)

**v2.0: High Photorealism**
- OmniLRS급 PBR 텍스처 (4K+, anti-tiling, pebble scatter)
- Photogrammetry 암석 메시 (5K-40K faces)
- 4K HDRI 하늘 + smooth tau 보간
- Production 렌더 설정 (SPP 32+, bounces 6+)

**v3.0: High Physical Fidelity**
- Terramechanics 플러그인 (Bekker/Janosi)
- RL 환경 (Isaac Lab Gym API)
- 다중 로봇 협조
- Ls 파라미터화 계절 변동


---



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

## 8. 버전 릴리스 기준

> **참고 (2026-04-14):** 버전 기반 릴리스로 재구성.

### 8.0 Foundation (Wk 1-9) [G10]

**완료 (2026-04-11).** Config, 지형, 대기, 렌더링, 로봇, 센서, ROS2.

### 8.1 v1.0 릴리스 기준 (iSpaRo 2026, 6/16) [G10]

모두 충족되어야 함:

- [ ] 로버가 화성 지형 위에서 주행 (fix_base=False, 안정적 물리).
- [ ] /cmd_vel로 로버 이동 제어. TF 트리 + 오도메트리 퍼블리시.
- [ ] 3개+ 미션 시나리오 운영 (HiRISE crop 기반, config 구동).
- [ ] 동적 대기: tau 및 시간에 따라 scene 변화.
- [ ] SLAM이 최소 2개 시나리오에서 맵 생성 (ATE/RPE 측정).
- [ ] Nav2가 최소 1개 시나리오에서 waypoint 내비게이션.
- [ ] 실험 테이블 완성 (SLAM 정확도 vs 시나리오, SLAM vs tau).
- [ ] 8페이지 iSpaRo 논문 제출.

**SHOULD (논문 강화, 차단 아님):**
- [ ] 7개 시나리오 전부 완성 (협곡, 동굴, 우주선, 기지).
- [ ] 다수 시나리오에서 Nav2 벤치마크.
- [ ] GitHub v1.0.0 공개 릴리스.

### 8.2 v2.0 릴리스 기준 (iSpaRo 이후) [G4]

- [ ] OmniLRS급 Photorealism (고폴리 암석, 4K HDRI, anti-tiling).
- [ ] Production 렌더 설정 (SPP 32+, bounces 6+).
- [ ] Perception 벤치마크: AI4Mars sim2real 전이.

### 8.3 v3.0 릴리스 기준 (향후) [G4]

- [ ] Terramechanics 플러그인 (Bekker/Janosi).
- [ ] RL 환경 (Isaac Lab Gym API).
- [ ] 다중 로봇 협조.

**버전 간 변경되지 않는 사항:**
- Config 스키마 (확장, 파괴 아님). [G5]
- 모듈 경계. Isaac Sim 코어 엔진.
- 코딩 표준 및 테스트 요구사항.

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
