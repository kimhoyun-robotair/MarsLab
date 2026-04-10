# MarsLab Work History Log

---

## [2026-04-08] Dev Environment + Config + CI Foundation

**Week:** Wk 1 (Apr 7 -- Apr 13)
**Module:** marslab/config/, marslab/utils/, scripts/, .github/workflows/
**Type:** Feature

### What Was Done
- Created `pyproject.toml` with project definition, dependencies (pydantic, pyyaml, numpy), and tool config (black, ruff, pytest).
- Created `marslab/utils/seed.py` with `set_global_seed()` -- sets random/numpy/torch seeds with validation.
- Created `marslab/config/schema.py` with 6 pydantic v2 models:
  - `MarsEnvConfig` (gravity, atmosphere, dust, albedo, temperature, seed)
  - `TerrainConfig` (source, DEM path, Golombek SFD params, semantic classes)
  - `RobotConfig` (type, URDF/USD paths, spawn position, sensor configs)
  - `RenderingConfig` (mode, HDRI dir, resolution)
  - `BenchmarkConfig` (annotation format, DR axes, sample count)
  - `MarsLabConfig` (top-level aggregator)
- Created `marslab/config/loader.py` with `load_config()` and `propagate_seeds()`.
- Created `configs/mars_env.yaml` -- master configuration matching PLAN.md Section 3.5.
- Created 3 unit test files (32 tests total):
  - `tests/unit/test_seed.py` (5 tests: determinism, different seeds, zero, negative, large)
  - `tests/unit/test_config_schema.py` (19 tests: valid defaults, invalid ranges, boundary values)
  - `tests/unit/test_config_loader.py` (8 tests: valid load, missing file, invalid values, seed propagation)
- Created `.github/workflows/unit_tests.yaml` (pytest on push/PR).
- Created `.github/workflows/lint.yaml` (black + ruff on push/PR).
- Created `scripts/hello_isaac.py` -- minimal Isaac Sim 5.1.0 headless verification.

### Key Decisions
- Used `setuptools` as build backend for consistency with Isaac Sim environment.
- `from __future__ import annotations` NOT used in schema.py (pydantic v2 requires runtime type access).
- Seed propagation uses simple offsets (master, master+1, master+2) -- adequate for Phase 1 per P1.
- `yaml.safe_load()` returns `None` for empty files -- handled by converting to `{}`.
- Isaac Sim 5.x import pattern confirmed: `from isaacsim import SimulationApp` (not deprecated `omni.isaac.kit`).

### Environment
- System Python: 3.12.3 (unit tests, offline code)
- Isaac Sim Python: 3.11.13 at `~/isaacsim/python.sh` (integration code)
- Isaac Sim: 5.1.0 standalone at `~/isaacsim/`
- GPU: NVIDIA RTX 5070 Ti (16GB)
- Installed: black 26.3.1, ruff 0.15.9, pydantic 2.12.5

### Test Results
- Unit tests: 32 passed, 0 failed.
- Lint (black --check): passed.
- Lint (ruff check): passed.
- Isaac Sim hello_isaac.py: SimulationApp created, 10 steps run, clean shutdown (~8s).

### Blockers / Issues
- None.

### Next Steps
- Week 2: HiRISE DEM loader (`marslab/terrain/dem_loader.py`) + Golombek rock placer (`marslab/terrain/rock_placer.py`).

---

## [2026-04-08] HiRISE Terrain + Rock Placement (Offline)

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** marslab/terrain/, configs/terrain/, scripts/
**Type:** Feature

### Original Plan (PLAN.md Week 2)
- HiRISE DTM(Jezero Crater) 다운로드
- dem_loader.py: GDAL로 GeoTIFF → numpy 변환
- rock_placer.py: Golombek & Rapp (1997) SFD 모델로 암석 분포 생성
- jezero_crater.yaml: 지형별 설정 파일
- Unit tests: DEM elevation ±0.1m, CFA ±10% (VL1/VL2/MPF)
- 산출물: 오프라인 지형 + 암석 파이프라인, 전체 unit test 통과

### Implementation Plan (상세 계획안)
- GDAL 설치 (pip GDAL==3.8.4, 시스템 libgdal-dev 버전 매칭)
- rock_placer.py 먼저 구현 (numpy만 필요, GDAL 불필요)
- dem_loader.py 구현 (GDAL 필요)
- Synthetic GeoTIFF fixture로 CI 친화적 테스트
- CFA 통계 검증: 4개 화성 착륙지(VL1, VL2, MPF, InSight) 데이터와 10% 이내 일치
- 오프라인 시각화 스크립트로 개발책임자 검토 지원
- compute_q()는 수학적 범위 (0,1], sample_rocks_golombek()는 실용적 범위 (0,0.15]

### What Was Done
- Installed GDAL Python bindings 3.8.4 (matching system libgdal-dev).
- Created `marslab/terrain/rock_placer.py`:
  - `RockPlacement` dataclass (x, y, diameter, height)
  - `compute_q(k)`: q(k) = 1.79 + 0.152/k, range (0, 1]
  - `compute_cfa(k, diameter)`: F_k(D) = k * exp(-q(k) * D)
  - `sample_rocks_golombek()`: log-scale binning, Poisson sampling, seed reproducible
- Created `marslab/terrain/dem_loader.py`:
  - `load_hirise_dem(dem_path)`: GDAL GeoTIFF → float32 numpy + metadata dict
  - nodata → NaN, gdal.UseExceptions() for proper error handling
- Created `configs/terrain/jezero_crater.yaml` (Jezero Crater terrain preset).
- Created `tests/unit/test_rock_placer.py` (18 tests):
  - compute_q formula, CFA monotonic decrease, seed determinism
  - CFA statistical validation for k=0.02/0.04/0.06/0.08 (all within 10%)
  - Parameter validation (k=0, invalid range, negative area)
- Created `tests/unit/test_dem_loader.py` (10 tests):
  - Synthetic GeoTIFF fixture (64×64, GDAL API generated)
  - Shape, dtype, elevation range, metadata, nodata handling
  - Error cases: file not found, invalid file format
  - Real HiRISE test (skipped if DTM not downloaded)
- Created `scripts/visualize_terrain.py`:
  - DEM elevation heatmap, rock placement scatter, SFD curve comparison
  - Output: `work_log/terrain_visualization.png`
- Updated `pyproject.toml`: added GDAL>=3.8, matplotlib>=3.5.
- Updated `.gitignore`: added DEM file exclusion patterns.
- Updated `.github/workflows/unit_tests.yaml`: added GDAL system library install step.

### Key Decisions
- `compute_q` range (0,1] vs `sample_rocks_golombek` range (0,0.15]: 수학 함수는 넓은 범위, 실용 함수는 화성 관측 범위로 구분. 사용자 확인 후 결정.
- rock_placer.py를 dem_loader.py보다 먼저 구현: numpy만 필요하므로 GDAL 설치 전에 작성/테스트 가능.
- Synthetic GeoTIFF fixture 사용: CI에서 실제 DTM 다운로드 없이 테스트 가능.
- `gdal.UseExceptions()` 모듈 레벨 호출: GDAL 4.0 호환 + RuntimeError → ValueError 변환.
- `np.random.default_rng(seed)` 사용: 글로벌 state 변경 없이 재현성 보장.
- height_ratio를 함수 파라미터로 받음 (default 0.5): G5 준수하되 schema 변경 없이 유연성 확보.

### Test Results
- Unit tests: 63 passed, 1 skipped (real HiRISE DEM not downloaded), 0 failed.
- CFA validation: InSight(k=0.02) ✓, VL2(k=0.04) ✓, MPF(k=0.06) ✓, VL1(k=0.08) ✓ — all within 10%.
- Lint (black --check): passed.
- Lint (ruff check): passed.
- Visualization: 3 plots generated (DEM, rocks, SFD curve).

### Blockers / Issues
- (해결됨) HiRISE DTM 다운로드 및 실제 데이터 테스트 완료. 아래 후속 엔트리 참조.

### Next Steps
- Week 3: Mars Atmosphere + Lighting (Offline) — sun_position.py, light_intensity.py, diffuse_fraction.py, sky_dome.py

---

## [2026-04-09] HiRISE DTM 실측 테스트 + 바위 파라미터 조정

**Week:** Wk 2 (Apr 14 -- Apr 20) — 후속 작업
**Module:** marslab/terrain/, configs/, marslab/config/
**Type:** Fix + Feature

### Original Plan
- USGS S3에서 실제 HiRISE DTM(Jezero Crater) 다운로드
- 원본 전체 DEM과 크롭 DEM 양쪽에서 코드 테스트
- 바위 수가 비현실적으로 많은 문제 파악 및 파라미터 조정

### What Was Done
- USGS AWS S3에서 Jezero_C 타일 다운로드 (125MB, GeoTIFF, 1m/pixel).
  - 소스: `asc-pds-services.s3.us-west-2.amazonaws.com/mosaic/mars2020_trn/HiRISE/`
  - 원본 크기: 7061×14445 pixels (7km × 14km, 102km²)
  - 고도 범위: -2665.4m ~ -2396.0m (Jezero 분지)
- `gdal.Translate()`로 중앙 500×500 영역 크롭 → `jezero_crater.tif` (979KB).
- 실제 DEM으로 전체 파이프라인 검증 (config → DEM load → rock placement).
- `test_load_real_hirise_dem` 테스트가 PASSED (더 이상 skipped 아님).

#### 바위 수 과다 문제 발견 및 해결
- **문제:** `rock_diameter_range: [0.05, 3.0]`에서 d_min=5cm이 너무 작아서 바위 수 폭주.
  - 크롭 250,000m²: **808,350개** (68%가 5~10cm 바위)
  - 원본 102km²: **~3.3억 개** 예상 → 메모리/시간 비현실적
- **분석:** 직경별 분포 측정 결과 5~10cm 바위가 전체의 68%를 차지.
  실제 시뮬레이션에서 5cm 바위를 개별 배치하는 것은 비현실적이며,
  화성 시뮬레이터들도 일정 크기 이하는 텍스처로 처리.
- **해결:** `rock_diameter_range` 하한을 0.05m → **0.20m**으로 상향 조정.
  - 20cm 미만 바위는 Phase 1에서 지형 텍스처로 처리
  - Golombek 논문에서도 "resolvable rocks" 기준 하한으로 흔히 사용되는 값
- **결과:**
  - 크롭 250,000m²: 808,350 → **59,545** (93% 감소)
  - 원본 102km² (d_min=0.20): 24,461,804 (73s, 6.3GB)
  - 원본 102km² (d_min=0.50): 1,383,030 (4s, 실용적)

#### 수정한 파일
- `configs/mars_env.yaml`: rock_diameter_range [0.05, 3.0] → [0.20, 3.0]
- `configs/terrain/jezero_crater.yaml`: 동일 변경
- `marslab/config/schema.py`: TerrainConfig default (0.05, 3.0) → (0.20, 3.0)
- `scripts/visualize_terrain.py`: 실제 DEM 로드 지원 (fallback으로 synthetic 유지)

#### 시각화 생성
- `work_log/terrain_visualization.png` — 크롭 500×500, d>=0.20m, 59,545 rocks
- `work_log/terrain_visualization_full.png` — 원본 7061×14445, d>=0.50m, 1,383,030 rocks

### Key Decisions
- d_min=0.20m 선택 근거: Golombek의 "resolvable rocks" 기준 + 시뮬레이션 실용성.
  5cm 바위를 개별 3D 객체로 배치하는 것은 렌더링 성능 관점에서도 비효율적.
- 원본 전체 테스트 시 d_min=0.50m으로 시각화: 138만 개도 충분히 밀도감 있는 배치.
- 원본 DEM 파일(120MB)은 /tmp/로 이동. 크롭(979KB)만 assets/에 보관.
  .gitignore에 *.tif 패턴으로 제외되어 있으므로 둘 다 커밋되지 않음.

### Test Results
- Unit tests: 64 passed, 0 failed, 0 skipped (real HiRISE test 포함).
- CFA validation: 4개 착륙지 전부 10% 이내 통과 (변경 없음).
- Lint: black + ruff 모두 통과.
- 원본 전체 DEM 로드: 1.27s, Shape (14445, 7061) 정상.

### Blockers / Issues
- 없음.

### Next Steps
- (완료) Week 3: Mars Atmosphere + Lighting. 아래 엔트리 참조.

---

## [2026-04-09] Mars Atmosphere + Lighting (Offline)

**Week:** Wk 3 (Apr 21 -- Apr 27)
**Module:** marslab/environment/, marslab/config/
**Type:** Feature

### Original Plan (PLAN.md Week 3)
- sun_position.py: Phase 1은 YAML에서 방위각/고도 직접 지정
- light_intensity.py: Beer's Law `I = I₀ × exp(-τ / cos(θz))`
- diffuse_fraction.py: COMIMART 모델 (Vicente-Retortillo et al. 2015)
- sky_dome.py: τ → 하늘 색상/밝기 계산
- Unit tests 4개 파일
- 산출물: 모든 화성 물리 오프라인 테스트 가능. Isaac Sim 의존성 zero.

### Implementation Plan (상세 계획안)
- Config schema 확장 필요: MarsEnvConfig에 sun_azimuth_deg, sun_elevation_deg 추가
- 구현 순서: config 확장 → sun_position → light_intensity → diffuse_fraction → sky_dome
- COMIMART: 논문의 lookup table을 numpy 선형보간으로 근사
- sky_dome: Bell et al. (2006) 기반 butterscotch 색상 모델, τ에 따라 선형보간
- 오프라인 시각화: Beer's Law 곡선, COMIMART 곡선, 하늘 색상 swatch, 복사 분해 차트

### What Was Done
- Extended `marslab/config/schema.py`: MarsEnvConfig에 `sun_azimuth_deg` (0-360, default 180), `sun_elevation_deg` (0-90, default 45) 추가.
- Updated `configs/mars_env.yaml` with sun position fields.
- Created `marslab/environment/sun_position.py`:
  - `SunPosition` dataclass (azimuth_deg, elevation_deg, zenith_angle_rad)
  - `compute_sun_position()`: Phase 1은 YAML 값 직접 사용, dataclass는 Phase 2와 동일
- Created `marslab/environment/light_intensity.py`:
  - `compute_direct_intensity()`: Beer's Law 구현
  - cos(θz) ≤ 0이면 0 반환 (태양 수평선 아래)
- Created `marslab/environment/diffuse_fraction.py`:
  - `compute_diffuse_fraction()`: COMIMART lookup table + np.interp 선형보간
  - 14개 데이터 포인트 (τ=0.0 ~ 6.0)
- Created `marslab/environment/sky_dome.py`:
  - `SkyDomeParams` dataclass (base_color_rgb, brightness, hdri_texture_path)
  - `compute_sky_dome_params()`: τ에 따른 butterscotch → dusty 색상 보간
  - HDRI 파일명 τ 범위별 선택 (실제 에셋은 Week 6)
- Created 4 unit test files (30 tests):
  - `test_sun_position.py` (7 tests): zenith 공식, 경계값, 범위 검증
  - `test_light_intensity.py` (8 tests): Beer's Law, Appelbaum 5%, 단조감소
  - `test_diffuse_fraction.py` (7 tests): COMIMART τ=0.3/1.0 범위, 단조증가
  - `test_sky_dome.py` (8 tests): butterscotch RGB, brightness, HDRI 선택
- Created `scripts/visualize_atmosphere.py`: 4개 subplot 시각화

### Key Decisions
- COMIMART를 다항식이 아닌 lookup + np.interp로 구현: 논문 데이터에 충실, 데이터 포인트 추가 용이.
- sky_dome 색상에 _CLEAR_SKY_RGB, _DUSTY_SKY_RGB 모듈 상수 사용: 과학적 참조값이라 하드코딩 적절. 추후 필요 시 config로 이동.
- sun_position Phase 1은 단순 변환만 수행: Phase 2(Ls 기반)에서 함수 시그니처가 바뀌지만 SunPosition dataclass는 동일.

### Test Results
- Unit tests: 94 passed, 0 failed.
- Beer's Law: Appelbaum & Flood (1990) 참고값과 5% 이내 ✓
- COMIMART: τ=0.3 → 0.33 [0.29, 0.38] ✓, τ=1.0 → 0.51 [0.50, 0.53] ✓
- Sky dome: butterscotch RGB (R=0.77 > G=0.59 > B=0.38, R > 0.6) ✓
- Lint: black + ruff 모두 통과.
- Visualization: `work_log/atmosphere_visualization.png` 4개 subplot 생성.

### Blockers / Issues
- 없음.

### Next Steps
- Week 4: Rover (Simplified Chassis) + PBR Materials — mesh_builder.py, material_applicator.py, rover.py

---

## [2026-04-09] Week 4 계획: Rover (Simplified Chassis) + PBR Materials

**Week:** Wk 4 (Apr 28 -- May 4)
**Module:** marslab/terrain/mesh_builder, marslab/terrain/material_applicator, marslab/robots/rover
**Type:** Feature

### Original Plan (PLAN.md Week 4)
- material_applicator.py: 지형에 Mars PBR 재질 적용
- mesh_builder.py: elevation numpy → USD 메시 변환
- 간소화 로버 URDF (box chassis + 6 wheels, rocker-bogie 없음)
- rover.py: spawn_rover — URDF→USD 변환 후 spawn
- convert_urdf.py: URDF→USD 변환 스크립트
- Unit tests: robot config, materials / Integration test: IMU z=3.72±0.05

### Implementation Plan (상세 계획안)

**핵심 변화: 첫 Isaac Sim 연동.** Week 1-3은 전부 오프라인이었으나, Week 4부터 Isaac Sim 의존 코드 등장.

**Isaac Sim 5.1.0 API 패턴 (조사 결과):**
- URDF 변환: `omni.kit.commands.execute("URDFParseAndImportFile", ...)`
- 메시 생성: `pxr.UsdGeom.Mesh.Define(stage, prim_path)`
- PBR 재질: `isaacsim.core.api.materials.omni_pbr.OmniPBR`
- 중력 설정: `physics_ctx.set_gravity(-3.72)`
- 로봇: `isaacsim.core.api.robots.Robot`

**구현 순서:**
1. 간소화 로버 URDF (box + 6 wheels, ~80줄 XML) — Isaac Sim 불필요
2. mesh_builder.py — elevation → USD 메시 (UsdGeom.Mesh + collision)
3. material_applicator.py — OmniPBR로 Mars regolith 재질 적용
4. rover.py + convert_urdf.py — URDF→USD 변환 및 spawn
5. Unit tests (offline) — test_robot_config.py, test_materials.py
6. Integration test (Isaac Sim) — test_robot_spawn.py, IMU z=3.72±0.05

**실행 환경 구분:**
- 시스템 Python: unit tests (robot config, materials 범위 검증)
- Isaac Sim Python (`~/isaacsim/python.sh`): mesh_builder, material_applicator, rover, integration tests

**생성 예정 파일 (11개):**
- `assets/robots/rover/simple_rover.urdf`
- `configs/robots/rover.yaml`
- `marslab/robots/__init__.py`, `marslab/robots/rover.py`
- `marslab/terrain/mesh_builder.py`, `marslab/terrain/material_applicator.py`
- `scripts/convert_urdf.py`
- `tests/unit/test_robot_config.py`, `tests/unit/test_materials.py`
- `tests/integration/__init__.py`, `tests/integration/test_robot_spawn.py`

**주의사항:**
- `omni.isaac.orbit` 절대 사용 금지 → `isaacsim.core.api` 사용
- URDF에 collision/inertial 빠지면 물리 시뮬레이션 실패
- 큰 DEM은 크롭(500x500) 기준으로 테스트

### What Was Done
- Created `assets/robots/rover/simple_rover.urdf`: box chassis (1.0×0.6×0.3m, 50kg) + 6 cylindrical wheels (r=0.15, 2kg each), continuous joints, collision + inertial 포함.
- Created `configs/robots/rover.yaml`: 로버 전용 프리셋.
- Updated `configs/mars_env.yaml`: urdf_path → simple_rover.urdf.
- Created `marslab/terrain/mesh_builder.py`: elevation numpy → USD 메시 (UsdGeom.Mesh + UsdPhysics.CollisionAPI). Grid cell당 2개 삼각형.
- Created `marslab/terrain/material_applicator.py`: OmniPBR 재질 (albedo 기반 Mars regolith 색상, roughness=0.8, metallic=0.0).
- Created `marslab/robots/rover.py`: `spawn_rover()` — URDF import + gravity 설정 + spawn position.
- Created `scripts/convert_urdf.py`: URDF→USD CLI 변환 유틸리티.
- Created `scripts/run_integration_test.py`: Isaac Sim headless integration test runner.
- Created `tests/unit/test_robot_config.py` (7 tests): RobotConfig 유효성 검증.
- Created `tests/unit/test_materials.py` (5 tests): albedo 범위, regolith 색상 검증.
- Created `tests/integration/test_robot_spawn.py`: pytest용 (ROS2 플러그인 충돌로 직접 실행 방식 병행).

### Key Decisions
- Isaac Sim 5.1.0 API: `isaacsim.core.api` 네임스페이스 사용 (`omni.isaac.orbit` 아님).
- URDF import: `omni.kit.commands.execute("URDFParseAndImportFile")` 패턴.
- Gravity: `UsdPhysics.Scene`에서 직접 설정 (magnitude=3.72, direction=(0,0,-1)).
- Integration test를 `scripts/run_integration_test.py`로 분리: ROS2 pytest 플러그인(`launch_testing_ros`)이 Isaac Sim Python 환경과 충돌하여 `pytest` 직접 호출이 불안정. 독립 스크립트로 3개 테스트를 실행하는 방식 채택.
- Claude Bash에서 Isaac Sim 실행이 환경 문제로 불안정 → 사용자가 직접 터미널에서 실행.

### Test Results
- Unit tests: 106 passed, 0 failed (시스템 Python).
- Integration test (사용자 직접 실행):
  - TEST 1: URDF→USD import → PASSED (`/simple_rover`)
  - TEST 2: Mars gravity = 3.72 m/s² → PASSED (THE critical test)
  - TEST 3: 120 step simulation, robot z=1.000 → PASSED
- URDF→USD 변환: `convert_urdf.py` → PASSED
- Lint: black + ruff 모두 통과.

### Blockers / Issues
- ROS2 pytest 플러그인(`launch_testing_ros`)이 Isaac Sim Python 3.11 환경과 충돌 (`pluggy.PluginValidationError`). Integration test를 독립 스크립트로 분리하여 해결.
- Isaac Sim Python에 marslab을 pip install 할 수 없음 (GDAL 의존성). PYTHONPATH 방식으로 대체.

### Next Steps
- Week 5: Procedural Terrain + Seed Reproducibility

---

## [2026-04-09] Procedural Terrain + Seed Reproducibility

**Week:** Wk 5 (May 5 -- May 11)
**Module:** marslab/terrain/procedural_generator, marslab/config/, configs/terrain/
**Type:** Feature

### Original Plan (PLAN.md Week 5)
- procedural_generator.py (flat/crater/hills) [SHOULD]
- 3개 terrain preset YAML [SHOULD]
- Seed reproducibility 전체 검증 [MUST]

### Implementation Plan (상세 계획안)
- Config schema 확장: TerrainConfig에 terrain_size, terrain_resolution, procedural_preset 추가
- 3개 프리셋: flat(평탄+노이즈), crater(포물선+림), hills(가우시안 bump)
- scipy.ndimage.gaussian_filter로 자연스러운 저주파 노이즈
- Seed e2e 검증: config→terrain→rocks→environment 전체 파이프라인

### What Was Done
- Extended `marslab/config/schema.py`: TerrainConfig에 `terrain_size`, `terrain_resolution`, `procedural_preset` 추가. validator: procedural이면 preset 필수.
- Created `marslab/terrain/procedural_generator.py`:
  - `generate_terrain(preset, size, resolution, seed)` → (elevation, metadata)
  - flat: base -2500m + gaussian smoothed noise (~2m std)
  - crater: flat + 포물선 bowl(depth 20m) + sinusoidal rim(5m)
  - hills: base + 대진폭 noise(30m) + 5개 gaussian bumps
  - metadata: dem_loader.py와 동일 포맷
- Created 3 preset YAMLs: procedural_flat, procedural_crater, procedural_hills
- Created `tests/unit/test_procedural_generator.py` (14 tests):
  - shape, dtype, elevation range, metadata 검증
  - flat 낮은 분산, crater 중앙 최저점, hills > flat 분산
  - seed 결정론, 다른 seed 다른 출력, 잘못된 preset ValueError
- Created `tests/unit/test_seed_reproducibility.py` (3 tests) [MUST]:
  - **전체 파이프라인 seed 결정론**: config→propagate→terrain→rocks→sun→light→diffuse→sky 동일 출력
  - 다른 master seed → 다른 출력
  - seed propagation offset 검증
- Created `scripts/visualize_procedural.py`: 3 프리셋 × 2 (elevation + rocks) 시각화
- Updated `pyproject.toml`: scipy>=1.10 추가
- Updated 기존 tests: procedural source에 preset 필수 반영

### Key Decisions
- gaussian_filter를 Perlin noise 대신 사용: scipy 내장이라 추가 의존성 불필요, seed 재현성 보장.
- metadata를 dem_loader.py와 동일 포맷으로 반환: 다운스트림(mesh_builder 등)이 소스 구분 없이 동일하게 처리 가능.
- crater 프로파일: `z = -depth * (1 - (r/R)^2)` 포물선. 실제 Mars crater morphology의 간소화.

### Test Results
- Unit tests: 130 passed, 0 failed.
- **Seed e2e [MUST]: PASSED** — 동일 master seed → 전체 파이프라인 byte-identical 출력.
- Lint: black + ruff 모두 통과.
- Visualization: `work_log/procedural_terrain_visualization.png` (flat 7,531 / crater 19,890 / hills 11,563 rocks)

### Blockers / Issues
- 없음.

### Next Steps
- Week 6: Rendering Integration + Visual Validation (Isaac Sim)

---

## [2026-04-09] Rendering Integration + Visual Validation

**Week:** Wk 6 (May 12 -- May 18)
**Module:** marslab/rendering/, scripts/run_scene.py
**Type:** Feature

### Original Plan (PLAN.md Week 6)
- render_settings.py: RTX path-tracing / ray-tracing 모드 전환
- sky_renderer.py: 돔 라이트 + HDRI
- sun_renderer.py: 방향광 (태양)
- atmosphere_fog.py: τ → 가시거리/안개
- run_scene.py: 전체 장면 오케스트레이터
- Integration tests + visual inspection
- 산출물: 통합 Mars scene v1

### Implementation Plan (상세 계획안)
- Isaac Sim 5.1.0 rendering API: UsdLux.DomeLight, UsdLux.DistantLight, carb.settings `/rtx/fog/*`
- rendering/ 모듈 4개 → run_scene.py에서 통합
- run_scene.py: Week 1-6 전체 모듈을 하나의 장면으로 조립
- Integration test를 독립 스크립트로 (run_scene_test.py)

### What Was Done
- Created `marslab/rendering/render_settings.py`: `set_render_mode()` — path_tracing/ray_tracing 전환, carb.settings API.
- Created `marslab/rendering/sky_renderer.py`: `configure_sky_dome()` — UsdLux.DomeLight + SkyDomeParams 연동.
- Created `marslab/rendering/sun_renderer.py`: `configure_sun_light()` — UsdLux.DistantLight + XformOp rotation (azimuth/elevation).
- Created `marslab/rendering/atmosphere_fog.py`: `configure_atmosphere_fog()` — τ → fog density/color via `/rtx/fog/*`.
- Created `scripts/run_scene.py`: 전체 통합 오케스트레이터 (config→terrain→environment→rendering→rover→simulate).
- Created `scripts/run_scene_test.py`: 3개 integration test (scene assembly, prim verification, tau fog variation).
- Created `configs/rendering/path_tracing.yaml`: 렌더링 프리셋.
- Created `tests/visual_inspection/checklist.md`: V1-V8 시각 검사 항목.

### Key Decisions
- rendering/ 모듈은 environment/ 출력(SkyDomeParams, SunPosition, intensity, diffuse)을 직접 소비. 의존성 방향: environment → rendering (단방향).
- Fog: `/rtx/fog/*` 설정 사용. τ → density 선형 매핑 (density = τ × 0.002).
- Sun direction: XformOp RotateXYZ로 azimuth/elevation 적용. 기본 방향 -Z.
- HDRI 파일 미존재 시 색상 기반 돔 라이트로 fallback (실제 HDRI 에셋은 추후 추가).

### Test Results
- Unit tests: 130 passed, 0 failed (regression 없음).
- Lint: black + ruff 모두 통과.
- Integration tests: **사용자 직접 실행 필요** (아래 명령어 참조).

### Integration Test 실행 명령어
```bash
# 전체 장면 오케스트레이터
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene.py

# Integration tests (3개)
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene_test.py
```

### Blockers / Issues

**[해결됨] GDAL import 에러 (Isaac Sim Python에서 run_scene.py 실행 시)**

- **증상:** `PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene.py` 실행 시 `ModuleNotFoundError: No module named 'osgeo'` 에러.
- **원인:** `run_scene.py`가 파일 상단에서 `from marslab.terrain.dem_loader import load_hirise_dem`을 무조건 import. `dem_loader.py`는 모듈 레벨에서 `from osgeo import gdal`을 실행. Isaac Sim Python(3.11)에는 GDAL이 설치되어 있지 않으므로, procedural terrain을 사용하더라도 import 시점에 에러 발생.
- **해결:** `dem_loader` import를 조건부(lazy)로 변경. `config.terrain.source == "hirise"`일 때만 함수 내부에서 import하도록 수정.
  ```python
  # 변경 전 (파일 상단):
  from marslab.terrain.dem_loader import load_hirise_dem  # 항상 import → GDAL 필요

  # 변경 후 (분기 내부):
  if config.terrain.source == "hirise":
      from marslab.terrain.dem_loader import load_hirise_dem
      elevation, meta = load_hirise_dem(config.terrain.dem_path)
  ```
- **교훈:** Isaac Sim Python 환경에서 실행되는 스크립트는 시스템 Python 전용 라이브러리(GDAL 등)를 top-level import하면 안 됨. 조건부 import 또는 lazy import 패턴 사용 필요.

**[해결됨] mars_env.yaml의 기본 terrain source가 hirise여서 여전히 GDAL import 에러**

- **증상:** lazy import 적용 후에도 동일 에러 발생. `config.terrain.source == "hirise"` 분기를 타기 때문.
- **원인:** `configs/mars_env.yaml`의 기본 terrain이 `source: "hirise"`로 설정되어 있었음. Isaac Sim Python에서는 GDAL이 없으므로 hirise 분기 자체를 탈 수 없음.
- **해결:** `mars_env.yaml`의 hirise 설정을 주석 처리하고 procedural로 변경. 기존 hirise 설정은 주석으로 보존.
  ```yaml
  # source: "hirise"
  # dem_path: "assets/terrain/dem/jezero_crater.tif"
  source: "procedural"
  procedural_preset: "crater"
  ```
- `test_config_loader.py`의 `test_load_config_valid`에서 `source == "hirise"` assertion도 주석 처리 후 `"procedural"` 검증으로 변경.

### Integration Test Results (사용자 실행)

**run_scene.py:**
- Config 로드 → procedural crater terrain (256×256) → atmosphere (intensity=385.4 W/m², diffuse=0.33) → rendering (path-tracing) → rover spawn → 60 step 시뮬레이션 → 정상 종료.
- Warning: spp clamped to 32 (기능 영향 없음), wheel mesh fabric 동기화 (무시 가능).

**run_scene_test.py (3/3 passed):**
- TEST 1: 전체 scene assembly → PASSED
- TEST 2: Prim 검증 (Terrain, DomeLight, SunLight) → PASSED
- TEST 3: Tau fog variation (τ=0.3 fog=0.0006, τ=2.0 fog=0.0040) → PASSED

### Next Steps
- Week 7: Rotorcraft + Quadruped

---

## [2026-04-09] Rotorcraft + Quadruped

**Week:** Wk 7 (May 19 -- May 25)
**Module:** marslab/robots/, configs/robots/, assets/robots/rotorcraft/
**Type:** Feature

### Original Plan (PLAN.md Week 7)
- Ingenuity 급 rotorcraft URDF + rotorcraft.py (simplified kinematic) [SHOULD]
- Go2 quadruped (built-in USD) + quadruped.py [SHOULD]
- Robot config YAMLs [SHOULD]
- 산출물: 3 robot types in Mars scene

### Implementation Plan (상세 계획안)
- Rotorcraft: URDF (box body + 4 rotor disks, 1.8kg) + spawn_rotorcraft() — kinematic only, fix_base=True
- Quadruped: Go2 built-in USD (`Isaac/Robots/Unitree/Go2/go2.usd`) + spawn_quadruped() via prim reference
- Go2 에셋 경로: `get_assets_root_path()` + relative path
- run_scene.py를 robot type별 분기로 확장
- Integration test: 5개 (rover/rotorcraft/go2 개별 + 공존 + gravity)

### What Was Done
- Created `assets/robots/rotorcraft/simple_rotorcraft.urdf`: box body (0.3×0.3×0.15m, 1.8kg) + 4 rotor disks (r=0.3), fixed joints.
- Created `marslab/robots/rotorcraft.py`: `spawn_rotorcraft(stage, config, gravity, atmo_density)` — URDF import, fix_base=True (kinematic), atmo_density는 Phase 2 인터페이스 준비만.
- Created `marslab/robots/quadruped.py`: `spawn_quadruped(stage, config, gravity)` — `get_assets_root_path()` + USD reference. `_resolve_asset_path()` 헬퍼로 Isaac Sim 내장 에셋 경로 해석.
- Created `configs/robots/rotorcraft.yaml`, `configs/robots/quadruped.yaml`.
- Updated `configs/mars_env.yaml`: robots 리스트에 rotorcraft, quadruped 추가 (총 3개).
- Updated `scripts/run_scene.py`: robot type별 spawn 분기 (rover/rotorcraft/quadruped).
- Created `scripts/run_multi_robot_test.py`: 5개 integration test.
- Updated unit tests: `len(robots) == 1` → `== 3` 반영.

### Key Decisions
- Rotorcraft: `fix_base=True` — 공중에 고정. Phase 1은 perception object로만 사용. 비행 역학 구현 금지.
- Quadruped: USD prim reference 방식 (`stage.DefinePrim() + GetReferences().AddReference()`). URDF가 아닌 built-in USD 사용.
- Go2 에셋: `isaacsim.storage.native.get_assets_root_path()`로 Nucleus/로컬 캐시 경로 해석. 미연결 시 fallback 로깅.
- run_scene.py에서 rotorcraft/quadruped import를 조건부(lazy)로 처리 — GDAL 문제와 동일 패턴.

### Test Results
- Unit tests: 130 passed, 0 failed.
- Lint: black + ruff 모두 통과.
- Integration tests: **사용자 직접 실행 필요** (아래 명령어 참조).

### Integration Test 실행 명령어
```bash
# Multi-robot test (5개)
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_multi_robot_test.py

# 전체 장면 (3 robots)
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene.py
```

### Blockers / Issues
- Go2 USD 에셋은 Nucleus 서버 또는 로컬 캐시에서 로드. 네트워크 미연결 시 실패 가능.
- 결과 대기 중.

### Integration Test Results (사용자 실행)

**run_multi_robot_test.py (5/5 passed):**
- TEST 1: Rover → PASSED
- TEST 2: Rotorcraft → PASSED
- TEST 3: Quadruped (Go2) → PASSED
- TEST 4: 3개 공존 → PASSED
- TEST 5: Gravity 3.72 → PASSED

**run_scene.py (3 robots):** 정상 동작, 스크린샷 저장 성공.

### Next Steps
- Phase A (즉시 수정) → Phase B (핵심 품질 강화)

---

## [2026-04-09] Phase A: 즉시 수정 (G5 위반 해소)

**Week:** Wk 8 (May 26 -- Jun 1) — User Review Gate 1
**Module:** marslab/rendering/, marslab/config/
**Type:** Fix

### What Was Done

5-Agent 적대적 토론으로 도출된 품질 강화 계획(`NEW_WEEK_PLAN_KOR.md`)의 Phase A를 수행.

**A1. 렌더링 매직 넘버 YAML 이동:**
- `sun_renderer.py`: `intensity * 5.0` → `rendering_config.sun_intensity_scale`
- `sun_renderer.py`: `Gf.Vec3f(1.0, 0.95, 0.85)` → `rendering_config.sun_color`
- `sun_renderer.py`: `0.35` → `rendering_config.sun_angular_diameter_deg`
- `sky_renderer.py`: `brightness * 1000.0` → `rendering_config.dome_brightness_scale`
- `atmosphere_fog.py`: `tau * 0.002` → `rendering_config.fog_density_scale`
- `atmosphere_fog.py`: `[0.78, 0.62, 0.42]` → `rendering_config.fog_color`

**A2. SPP 클램핑 대응:**
- `render_settings.py`: 하드코딩 `spp=64` → `rendering_config.spp` (기본값 32)
- `totalSpp`, `maxBounces`도 YAML 설정으로 이동

**A3. diffuse_fraction DomeLight 적용:**
- `sky_renderer.py`: `configure_sky_dome()`에 `diffuse_fraction` 파라미터 추가
- DomeLight intensity = `brightness * dome_brightness_scale * diffuse_fraction`
- 이전에는 diffuse_fraction을 계산만 하고 사용하지 않았음

**함수 인터페이스 변경:**
- `set_render_mode(mode)` → `set_render_mode(rendering_config)`
- `configure_sky_dome(stage, sky_params)` → `configure_sky_dome(stage, sky_params, diffuse_fraction, rendering_config)`
- `configure_sun_light(stage, sun_pos, intensity, diffuse)` → `configure_sun_light(stage, sun_pos, intensity, diffuse, rendering_config)`
- `configure_atmosphere_fog(stage, tau)` → `configure_atmosphere_fog(stage, tau, rendering_config)`

**Schema 확장 (RenderingConfig):**
- 추가 필드: spp, total_spp, max_bounces, sun_intensity_scale, sun_color, sun_angular_diameter_deg, dome_brightness_scale, fog_density_scale, fog_color

### Test Results
- Unit tests: 130 passed, 0 failed (regression 없음).
- Lint: black + ruff 모두 통과.
- G5 위반: 렌더링 모듈 내 **0개** (전부 config로 이동).

### Next Steps
- Phase B: 핵심 품질 강화 (PBR 텍스처, 바위 3D, HDRI, 지형 개선)

---

## [2026-04-09] Phase B: 핵심 품질 강화

**Module:** marslab/terrain/, marslab/environment/, assets/
**Type:** Feature (품질 강화)

### What Was Done

**B1. Mars PBR 텍스처 (UV + 텍스처 바인딩):**
- `mesh_builder.py`: UV 좌표 생성 추가 (planar mapping, uv_scale 파라미터)
- `mesh_builder.py`: vertex normal 계산 추가 (`np.gradient` 기반)
- `material_applicator.py`: `texture_dir` 파라미터 추가 — PBR 텍스처 자동 바인딩
- `_apply_textures()`: albedo.png, normal.png, roughness.png 자동 탐색
- 1K 절차적 Mars regolith 텍스처 3종 생성 (albedo, normal, roughness)
- TerrainConfig에 `texture_dir` 필드 추가

**B2. 바위 3D PointInstancer:**
- 새 파일 `marslab/terrain/rock_instancer.py` 생성
- `UsdGeom.PointInstancer` + 3개 Sphere prototype (크기 변형)
- terrain elevation z-보간 (bilinear nearest)
- 랜덤 yaw 회전 + diameter 기반 scale
- `run_scene.py`에 rock placement 단계 추가 — 이전에는 rock_placer 미사용
- semantic label `"big_rock"` 적용

**B3. HDRI 스카이돔:**
- 2048×1024 절차적 Mars sky PNG 생성 (butterscotch 그라디언트 + 먼지 노이즈 + sun glow)
- `assets/sky/hdri/mars_sky_clear.png`, `mars_sky_moderate.png`, `mars_sky_dusty.png`
- `sky_dome.py` 파일 확장자 `.hdr` → `.png` 변경

**B4. 지형 기하학 개선:**
- 모든 프리셋에 `_add_micro_detail()` 고주파 노이즈 레이어 추가 (0.15m amplitude)
- 새 프리셋 `rocky_plain` 추가: 3단계 주파수 노이즈 (low 5m + mid 1.5m + high 0.3m) + 15개 bedrock mound
- rocky_plain std=5.08m — 카메라 근접 시 지형 요철 인지 가능

### Test Results
- Unit tests: 130 passed, 0 failed.
- Lint: black + ruff 모두 통과.
- Isaac Sim integration: **사용자 직접 실행 필요** (아래 명령어).

### Integration Test 실행 명령어
```bash
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene.py
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene_test.py
```

### Blockers / Issues

**[해결됨] OmniPBR.set_texture() API 호환성 문제**

- **증상:** `material.set_texture(path, "normal")` 호출 시 `TypeError: OmniPBR.set_texture() takes 2 positional arguments but 3 were given`
- **원인:** Isaac Sim 5.1.0의 `OmniPBR.set_texture()` 메서드는 albedo/diffuse 텍스처 경로 1개만 인자로 받음. 두 번째 인자로 텍스처 채널("normal", "roughness")을 지정하는 기능이 없음. Normal map과 roughness map은 `OmniPBR` 래퍼의 범위 밖이며, `UsdShade` shader graph를 직접 조작해야 함.
- **해결:** MVP에서는 albedo 텍스처만 `set_texture()`로 적용. Normal/roughness는 상수값(roughness=0.8, metallic=0.0)으로 유지. Phase B+ 품질 정제 시 `UsdShade` 직접 조작으로 업그레이드 예정.
- **교훈:** Isaac Sim API를 사용하기 전에 반드시 prototype 스크립트로 메서드 시그니처를 검증할 것. 특히 `OmniPBR` 같은 편의 래퍼의 기능 범위는 제한적일 수 있음.

### Integration Test Results (사용자 실행)

**run_scene.py:** OmniPBR 에러 수정 후 재실행 — 정상 동작 확인.
- PBR albedo 텍스처 적용 성공
- PointInstancer 바위 배치 성공
- HDRI 스카이돔 로드 성공
- 스크린샷: `work_log/mars_scene_closeup.png`, `work_log/mars_scene_overview.png`

### Next Steps
- Phase C: 센서 부착 (RGB, depth, IMU, LiDAR) + DR 검증

---

## [2026-04-09] 세션 종료 상태 요약

### 하루 진행 요약

2026-04-09 하루 동안 Week 1 ~ Week 8 (Phase A + Phase B 포함) 전체를 구현 완료.

| 단계 | 내용 | 상태 |
|------|------|------|
| Wk 1 | Config + CI Foundation | ✅ 완료 |
| Wk 2 | HiRISE DEM + Rock SFD | ✅ 완료 |
| Wk 3 | Mars Atmosphere + Lighting | ✅ 완료 |
| Wk 4 | Rover + PBR Materials | ✅ 완료 |
| Wk 5 | Procedural Terrain + Seed | ✅ 완료 |
| Wk 6 | Rendering + Scene Integration | ✅ 완료 |
| Wk 7 | Rotorcraft + Quadruped | ✅ 완료 |
| Wk 8 | Phase A (매직 넘버 제거) | ✅ 완료 |
| Wk 8 | Phase B (PBR/Rock/HDRI/Terrain) | ✅ 완료 |

### 테스트 현황
- Unit tests: **130 passed**, 0 failed (시스템 Python 3.12.3)
- Integration tests: **11 passed** (사용자 Isaac Sim Python 직접 실행)
  - run_integration_test.py: 3/3
  - run_scene_test.py: 3/3
  - run_multi_robot_test.py: 5/5
- Lint: black + ruff 모두 통과

### 다음 작업 (미완료)
1. **Phase C** (16h): 센서 부착 (RGB, depth, IMU, LiDAR) + Domain Randomization 검증
2. **Week 9-11**: ROS2 bridge, annotation (AI4Mars), benchmark evaluation
3. **Phase D** (Phase 2 이관): noise models, lens effects, stereo camera, calibration
4. **품질 잔여**: Normal/roughness 텍스처 UsdShade 직접 적용, 바위 가시성 개선

### 알려진 제한사항
- OmniPBR 래퍼는 albedo 텍스처만 지원. Normal/roughness는 UsdShade 직접 조작 필요 (Phase B+ 이관)
- 카메라 거리에서 바위가 잘 보이지 않음 — 카메라 배치/스케일 조정 필요
- HDRI는 절차적 생성 PNG (실제 HDR 포맷 아님) — 충분한 품질이면 유지, 부족하면 CC0 소싱
