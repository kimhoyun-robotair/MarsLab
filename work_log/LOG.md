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
- Unit tests: **140 passed**, 0 failed (시스템 Python 3.12.3)
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
- ~~HiRISE DEM이 Isaac Sim에서 렌더링 불가 (GDAL 미설치)~~ → 아래 [2026-04-10] 엔트리에서 해결

---

## [2026-04-10] HiRISE DEM → Isaac Sim 렌더링 파이프라인 (GDAL 우회)

**Module:** marslab/terrain/, marslab/config/, scripts/
**Type:** Feature (아키텍처 개선)

### 문제 정의

Isaac Sim Python 3.11.13에 GDAL 설치가 불가능하여, `dem_loader.py`의 `from osgeo import gdal` 모듈 레벨 import가 실패. 이로 인해 `source: "hirise"` 설정 시 Isaac Sim 런타임에서 HiRISE GeoTIFF DEM을 로드할 수 없었음. Week 2에서 `dem_loader.py`와 `rock_placer.py`를 구현하고, 실제 Jezero Crater HiRISE DTM으로 전체 파이프라인을 검증했지만, Isaac Sim 렌더링에서는 procedural 모드만 사용 가능했음.

### OmniLRS 레퍼런스 분석

해결 방안 설계 전 OmniLRS(가장 핵심적인 레퍼런스 코드베이스)의 DEM 처리 방식을 조사함.

**OmniLRS의 2단계 아키텍처:**

| 단계 | 환경 | 도구 | 파일 |
|------|------|------|------|
| Stage 1 (오프라인) | 시스템 Python + GDAL | `gdal.Open()` → `np.save()` | `scripts/preprocess_dem.py` |
| Stage 2 (런타임) | Isaac Sim Python (GDAL 없음) | `np.load()` + YAML 메타데이터 | `src/terrain_management/` |

**OmniLRS의 핵심 설계 원칙:**
- `scripts/preprocess_dem.py`: GDAL로 GeoTIFF → `.npy` 변환 (약 30줄)
- `scripts/process_info.py`: `gdalinfo` 출력 파싱 → `dem.yaml` 메타데이터 생성 (154줄)
- `scripts/extract_dems.sh`: 전체 파이프라인 오케스트레이션 (bash 스크립트)
- **런타임 코드(`src/` 디렉토리)에는 GDAL import가 단 한 줄도 없음**
- `pyproject.toml`에 GDAL 의존성이 있지만, `scripts/`에서만 사용
- 디렉토리 구조: `assets/Terrains/SouthPole/DEM_NAME/dem.npy` + `dem.yaml`

**결론:** OmniLRS는 MarsLab과 동일한 문제(Isaac Sim Python에서 GDAL 사용 불가)를 동일한 방법론(오프라인 사전 변환)으로 해결. 이 패턴이 production-grade로 검증되어 있으므로 MarsLab도 동일 접근법을 채택.

### 해결: 사전 변환 파이프라인

**아키텍처 (OmniLRS 패턴 참고, MarsLab 통합 구현):**

```
[Stage 1: 시스템 Python + GDAL — 1회 실행]
  python scripts/convert_dem.py --config configs/terrain/jezero_crater.yaml
  └─ load_hirise_dem()     →  GDAL로 GeoTIFF 파싱
  └─ save_converted_dem()  →  elevation.npy + metadata.json 저장

[Stage 2: Isaac Sim Python — GDAL 불필요, 매번 실행]
  ~/isaacsim/python.sh scripts/run_scene.py --config configs/terrain/jezero_crater.yaml
  └─ load_converted_dem()  →  np.load() + json.load() 로드
  └─ mesh_builder, rock_instancer 등  →  기존 파이프라인 그대로
```

**OmniLRS와의 차이점:**
- OmniLRS는 3개 스크립트로 분리 (bash + 2 Python) → MarsLab은 `convert_dem.py` 1개로 통합 (더 단순)
- OmniLRS는 메타데이터를 YAML → MarsLab은 JSON (Python stdlib, 추가 의존성 없음)
- OmniLRS는 `gdalinfo` CLI 출력을 파싱 → MarsLab은 GDAL Python API에서 직접 추출 (더 정확)

### What Was Done

**1. `marslab/terrain/dem_loader.py` 수정:**
- GDAL import를 모듈 레벨에서 `load_hirise_dem()` 함수 내부로 이동 (lazy import)
- `save_converted_dem(elevation, metadata, output_dir)` 추가 — `np.save()` + `json.dump()`
- `load_converted_dem(converted_dir)` 추가 — `np.load()` + `json.load()`, GDAL 완전 불필요
- 두 함수 모두 `load_hirise_dem()`과 동일한 `(elevation, metadata)` 튜플 반환

**2. `marslab/config/schema.py` 수정:**
- `TerrainConfig`에 `converted_dem_dir: str | None` 필드 추가
- Validator 완화: `source == "hirise"`일 때 `dem_path` 또는 `converted_dem_dir` 중 하나만 있으면 유효

**3. `scripts/convert_dem.py` 신규 생성:**
- 시스템 Python으로 실행하는 사전 변환 CLI 스크립트
- YAML config → `load_hirise_dem()` → `save_converted_dem()` → round-trip 검증
- 출력 디렉토리: config의 `converted_dem_dir` 또는 DEM 경로에서 자동 유도

**4. `scripts/run_scene.py` 수정:**
- hirise 분기에 `converted_dem_dir` 우선 체크 → GDAL fallback → 에러 순서 추가
- procedural 분기는 변경 없음

**5. YAML 업데이트:**
- `configs/mars_env.yaml`: `converted_dem_dir` 주석으로 추가
- `configs/terrain/jezero_crater.yaml`: `converted_dem_dir` + `texture_dir` 활성화

**6. Unit Tests 추가:**
- `tests/unit/test_dem_converter.py` 신규 (8 tests): round-trip, 디렉토리 생성, 에러 케이스, NaN 보존, dtype 검증
- `tests/unit/test_config_schema.py` 수정/추가 (3 tests): converted_dir only, both paths, neither path

**7. `.gitignore` 업데이트:**
- `assets/terrain/dem/*_converted/` 패턴 추가

### Key Decisions

- **OmniLRS 패턴 채택 근거**: OmniLRS가 동일 문제를 동일 방법으로 해결하고 있으며, production에서 검증된 패턴. MarsLab은 이를 단순화하여 적용.
- **JSON vs YAML (메타데이터)**: OmniLRS는 `dem.yaml`을 사용하지만, MarsLab은 `metadata.json`을 선택. Python stdlib의 `json` 모듈만 필요하므로 Isaac Sim Python에서 추가 설치 없이 로드 가능.
- **통합 스크립트**: OmniLRS의 3파일(bash+2Python)을 1개 Python 스크립트로 통합. 사용자 입장에서 `python scripts/convert_dem.py --config ...` 한 줄로 완료.
- **Lazy import 패턴**: `dem_loader.py` 모듈 자체는 GDAL 없이 import 가능하도록 변경. `load_converted_dem`만 쓸 때는 GDAL 불필요.
- **기존 파이프라인 무변경**: `mesh_builder.py`, `rock_placer.py`, `rock_instancer.py`, `material_applicator.py`, `procedural_generator.py` 전부 그대로. 파이프라인이 DEM 로드 이후 100% source-agnostic이므로 downstream 코드 변경 불필요.

### Test Results

- Unit tests: **140 passed**, 0 failed (기존 130 → 140, +10 신규)
  - `test_dem_converter.py`: 8/8 passed
  - `test_config_schema.py`: 기존 테스트 통과 + 신규 3개 통과
- 변환 스크립트 실행:
  - 입력: `assets/terrain/dem/jezero_crater.tif` (500x500, 979KB)
  - 출력: `assets/terrain/dem/jezero_crater_converted/elevation.npy` (976KB) + `metadata.json`
  - Round-trip 검증: PASSED (shape, dtype, elevation 값 일치)
- Isaac Sim 렌더링 (사용자 실행): HiRISE DEM 기반 장면 렌더링 **성공**
- Lint: black + ruff 모두 통과

### 사용자 워크플로우

```bash
# 1회: 시스템 Python으로 변환 (GDAL 사용)
python3 scripts/convert_dem.py --config configs/terrain/jezero_crater.yaml

# 이후: Isaac Sim Python으로 렌더링 (GDAL 불필요)
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene.py \
  --config configs/terrain/jezero_crater.yaml
```

### 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `marslab/terrain/dem_loader.py` | GDAL lazy import + `save_converted_dem()` / `load_converted_dem()` 추가 |
| `marslab/config/schema.py` | `converted_dem_dir` 필드 + validator 완화 |
| `scripts/convert_dem.py` | **신규** — GeoTIFF→npy 변환 CLI |
| `scripts/run_scene.py` | hirise 분기에 converted_dem_dir 우선 체크 |
| `configs/mars_env.yaml` | `converted_dem_dir` 주석 추가 |
| `configs/terrain/jezero_crater.yaml` | `converted_dem_dir` + `texture_dir` 추가 |
| `tests/unit/test_dem_converter.py` | **신규** — GDAL-free 변환 테스트 8개 |
| `tests/unit/test_config_schema.py` | 기존 테스트 수정 + 신규 3개 |
| `.gitignore` | `*_converted/` 패턴 추가 |

### Blockers / Issues
- 없음. HiRISE DEM → Isaac Sim 렌더링 파이프라인이 완전히 동작.
- 후속 문제: 로봇/카메라 Z 좌표 불일치 발견 → 아래 엔트리에서 해결.

### Next Steps
- 로봇 spawn 위치 보정 + Bird's Eye View 추가. 아래 엔트리 참조.

---

## [2026-04-10] 로봇 Spawn 위치 + 카메라 보정 + Bird's Eye View

**Module:** scripts/run_scene.py, configs/terrain/jezero_crater.yaml
**Type:** Fix + Feature

### 문제 발견

Isaac Sim HiRISE DEM 렌더링 테스트 후 스크린샷 확인 결과, **로봇이 전혀 보이지 않았음**. `work_log/mars_scene_closeup.png`과 `mars_scene_overview.png` 모두 butterscotch 색 평면만 표시.

**근본 원인 분석:**
- HiRISE DEM elevation 범위: **-2584 ~ -2569m** (Jezero 분지의 실제 MOLA 고도)
- 로봇 spawn Z: **1.0m** (config의 `spawn_position: [0, 0, 1.0]`)
- 차이: **약 2570m** — 로봇이 지형 위 2.5km 상공에 배치됨
- 카메라도 로봇 기준(Z≈1m)으로 배치 → 지형 표면을 안개 너머로만 관찰
- procedural terrain (elevation ≈ -2500m)에서도 **동일한 문제**가 존재했으나 미발견

추가 문제: `jezero_crater.yaml`에 `robots:` 섹션이 없어서 로봇이 아예 spawn되지 않았음.

### What Was Done

**1. `scripts/run_scene.py` — 지형 표면 기준 자동 좌표 보정:**
- 지형 중심 좌표(`terrain_cx`, `terrain_cy`)와 중앙 elevation(`terrain_center_elev`) 자동 계산
- `_terrain_z_at(x, y)` 헬퍼 함수: 임의 XY 좌표에서 지형 elevation 쿼리
- 로봇 spawn 좌표를 **지형 중심 기준 상대 좌표**로 재해석:
  - config의 `[0, 0, 1]` → "지형 중심에서 X=0, Y=0 오프셋, 표면 위 1m"
  - 실제 spawn: `(terrain_cx + 0, terrain_cy + 0, surface_z + 1.0)`
- 카메라 위치도 실제 로봇/지형 elevation 기반으로 자동 설정
- 로봇 없는 config에서는 지형 중심을 카메라 기준점으로 사용

**2. Bird's Eye View 카메라 추가:**
- 지형 전체를 위에서 내려다보는 3번째 스크린샷 (`mars_scene_birdseye.png`)
- 높이: `terrain_center_elev + terrain_extent * 0.8` (지형 크기의 80% 고도에서 촬영)
- 지형 중심을 향해 수직 하방으로 촬영
- DEM 기반 렌더링 품질 확인용

**3. `configs/terrain/jezero_crater.yaml` 확장:**
- terrain-only config에서 **완전한 scene config**로 확장
- `mars_env`, `rendering`, `robots` 섹션 추가 (mars_env.yaml과 동일 값)
- 로봇 3대 (rover, rotorcraft, quadruped) 포함

### Key Decisions

- 로봇 spawn_position을 **지형 중심 기준 상대 좌표**로 해석: 절대 좌표로 해석하면 terrain source(hirise vs procedural)마다 spawn position을 바꿔야 하므로, 상대 좌표 방식이 config 재사용성이 높음.
- Bird's eye 높이를 `terrain_extent * 0.8`로 설정: 500m 지형이면 400m 상공에서 촬영. 전체 지형이 한 프레임에 들어옴.
- jezero_crater.yaml을 완전한 config로 확장: terrain-only config는 로봇 미생성 → 렌더링 테스트에 부적합.

### 스크린샷 출력 (3장)

| 파일 | 설명 |
|------|------|
| `work_log/mars_scene_closeup.png` | 로버 근접 촬영 (3m 거리) |
| `work_log/mars_scene_overview.png` | 중거리 조감 (15m 거리) |
| `work_log/mars_scene_birdseye.png` | **전체 지형 Bird's Eye View (신규)** |

### Test Results
- Unit tests: 140 passed, 0 failed (regression 없음)
- Isaac Sim 렌더링: **사용자 직접 실행 필요**

### Integration Test 실행 명령어
```bash
# HiRISE Jezero Crater (로봇 3대 + bird's eye)
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene.py \
  --config configs/terrain/jezero_crater.yaml

# Procedural terrain (기존, 좌표 보정 적용됨)
PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene.py
```

### 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `scripts/run_scene.py` | 지형 표면 기준 spawn/camera 자동 보정 + bird's eye view 추가 |
| `configs/terrain/jezero_crater.yaml` | 완전한 scene config로 확장 (mars_env + rendering + robots) |

### Blockers / Issues
- 없음.

### Next Steps
- Phase C1: 센서 부착. 아래 엔트리 참조.

---

## [2026-04-10] Phase C1: 센서 부착 (RGB, Depth, IMU, LiDAR)

**Module:** marslab/sensors/, configs/sensors/, scripts/
**Type:** Feature (PLAN.md Week 11, MUST)

### Original Plan (PLAN.md Week 11)
- imu.py: Mars-calibrated IMU (THE critical test: z=3.72±0.05)
- camera.py: stereo RGB + depth camera
- lidar.py: 3D LiDAR point cloud
- 4개 sensor config YAMLs
- Integration test: test_sensor_output.py

### Implementation Plan (상세 계획안)
- OmniLRS 센서 패턴 참고: Camera(`get_rgba()`/`get_depth()`), IMU(`_sensor.acquire_imu_sensor_interface()`)
- `RobotConfig.sensor_config_paths` 필드 활용 (schema.py에 이미 존재)
- 센서를 로봇 prim 하위 child prim으로 생성
- YAML `type` 필드 기반 디스패치 (`__init__.py`)
- 추상 클래스 없음 (P1: Flat P0 Architecture)
- Isaac Sim `World` 클래스 + `world.step(render=True)` 필수 (headless 모드 센서 데이터 수집)

### What Was Done

**1. Sensor Config YAMLs (4개 신규):**
- `configs/sensors/stereo_rgb.yaml`: RGB 카메라, 1280x720, enable_depth=false
- `configs/sensors/depth_camera.yaml`: Depth 카메라, 1280x720, enable_depth=true
- `configs/sensors/lidar_3d.yaml`: 3D LiDAR, 360° FOV, 100m range
- `configs/sensors/imu.yaml`: IMU, 200Hz update rate

**2. Sensor 모듈 (3 + init):**
- `marslab/sensors/camera.py`: `attach_camera()` — Camera prim 생성, RGB/depth 읽기 헬퍼
- `marslab/sensors/imu.py`: `attach_imu()` — `IsaacSensorCreateImuSensor` 커맨드, `read_imu()` 읽기 헬퍼
- `marslab/sensors/lidar.py`: `attach_lidar()` — `RangeSensorCreateLidar` 커맨드, `read_lidar_point_cloud()` 헬퍼
- `marslab/sensors/__init__.py`: `load_and_attach_sensor()` — YAML → type별 디스패치

**3. run_scene.py 통합:**
- 로봇 spawn 직후 `sensor_config_paths` 순회하며 `load_and_attach_sensor()` 호출
- 에러 시 경고 출력, fatal 아님 (일부 로봇은 센서 미설정)

**4. Integration Test (`scripts/run_sensor_test.py`):**
- 5개 테스트, `World` 클래스 기반, 각 테스트 독립 World 인스턴스
- `world.step(render=True)` 사용하여 렌더링/물리 파이프라인 활성화

### Key Decisions

- **`World` 클래스 필수**: 첫 번째 시도에서 `simulation_app.update()`만 사용 → 카메라 데이터 empty, IMU 전부 0. `World` + `world.step(render=True)`로 전환 후 5/5 통과. Isaac Sim headless 모드에서 센서 데이터 수집에는 `World`가 반드시 필요.
- **디스패치 패턴**: `__init__.py`에서 `type` 기반 단순 dict 디스패치. SensorBase 추상 클래스 등 불필요한 추상화 배제 (P1).
- **mount_link fallback**: URDF import 후 prim 구조가 예측과 다를 수 있으므로, `mount_link` prim이 없으면 robot root에 직접 부착.
- **IMU `read_gravity=True`**: OmniLRS에서 확인된 패턴. physics scene gravity(3.72)를 IMU가 자동으로 읽음.

### 첫 번째 시도 실패 및 수정

**1차 실행 (5/5 FAILED → 수정 → 5/5 PASSED):**

| 센서 | 1차 결과 | 원인 | 수정 |
|------|----------|------|------|
| RGB Camera | empty data | `simulation_app.update()`는 카메라 렌더 파이프라인 미트리거 | `World.step(render=True)` |
| Depth Camera | empty data | 동일 | 동일 |
| IMU | [0, 0, 0] | 물리 스텝 미실행으로 gravity 미반영 | `World.step()` + 120 스텝 settle |
| LiDAR | 0 points | 렌더 파이프라인 미활성 | `World.step(render=True)` |

**교훈:** Isaac Sim headless 모드에서 센서 데이터 수집은 반드시 `isaacsim.core.api.World`를 사용해야 함. `SimulationApp.update()`는 기본적인 시뮬레이션 루프만 실행하고, 센서 데이터 파이프라인(카메라 렌더, IMU 물리 읽기, LiDAR ray cast)은 `World.step(render=True)`에서만 트리거됨.

### Test Results

- Unit tests: **140 passed**, 0 failed (regression 없음)
- **Integration tests (사용자 실행): 5/5 PASSED**
  - TEST 1: RGB Camera — shape (720, 1280, 4) uint8 ✓
  - TEST 2: Depth Camera — shape (720, 1280), range [4.51, inf] ✓
  - **TEST 3: IMU Gravity — z = 3.7200 m/s² (THE critical test) ✓**
  - TEST 4: LiDAR — 2,400 points ✓
  - TEST 5: All Coexist — IMU z=3.7191, RGB OK ✓

### 생성 파일 요약

| 파일 | 내용 |
|------|------|
| `configs/sensors/stereo_rgb.yaml` | RGB 카메라 설정 |
| `configs/sensors/depth_camera.yaml` | Depth 카메라 설정 |
| `configs/sensors/lidar_3d.yaml` | 3D LiDAR 설정 |
| `configs/sensors/imu.yaml` | IMU 설정 |
| `marslab/sensors/__init__.py` | YAML→attach 디스패치 |
| `marslab/sensors/camera.py` | RGB/Depth 카메라 부착 + 읽기 |
| `marslab/sensors/imu.py` | IMU 부착 + 읽기 |
| `marslab/sensors/lidar.py` | LiDAR 부착 + point cloud 읽기 |
| `scripts/run_sensor_test.py` | 5개 integration test |
| `scripts/run_scene.py` (수정) | 센서 자동 부착 통합 (~10줄 추가) |

### Blockers / Issues

**미해결 경고/에러 (기능 영향 없으나 정리 필요):**
- `[Warning] verticalAperture inconsistent with pixel resolution aspect ratio` — 카메라 aperture 자동 보정
- `[Warning] IMU sensor frequency is higher than physics frequency` — IMU 200Hz > 물리 60Hz
- `[Warning] tensor view invalidated` — 테스트 간 `world.clear()` 시 발생
- `[Error] Simulation view object is invalidated` — 동일 원인

### Next Steps
- Week 9: ROS2 Bridge. 아래 엔트리 참조.

---

## [2026-04-10] Week 9: ROS2 Bridge (센서 데이터 Publish)

**Module:** marslab/ros2_bridge/, scripts/
**Type:** Feature (PLAN.md Week 9, MUST)

### Original Plan (PLAN.md Week 9)
- topic_config.py: 토픽 이름 관리
- publisher.py: 센서 데이터 ROS2 publish
- test_ros2_bridge.py: 토픽 존재 + 메시지 수신 검증

### Implementation Plan (상세 계획안)
- Isaac Sim 내장 `isaacsim.ros2.bridge` 확장 활용 (ROS2 Jazzy 내부 rclpy)
- OmniGraph 노드 기반 publish (C++ 파이프라인, 고성능)
- Camera: `ROS2CameraHelper` + Viewport/RenderProduct 파이프라인
- IMU: `IsaacReadIMU` → `ROS2PublishImu` OG 연결
- LiDAR: `RtxLidarROS2PublishPointCloud` Replicator writer
- Clock: `ROS2PublishClock` 시뮬레이션 시간 동기화
- 토픽 네이밍: `/{robot_name}/{sensor_name}/{sub_topic}` (CLAUDE.md 규칙)

### What Was Done

**1. `marslab/ros2_bridge/topic_config.py` (신규):**
- `build_topic_name()`: CLAUDE.md 규칙 준수 토픽명 생성
- `SENSOR_TOPICS`: 센서 타입별 기본 sub-topic 매핑

**2. `marslab/ros2_bridge/publisher.py` (신규, ~180줄):**
- `enable_ros2_bridge()`: `isaacsim.ros2.bridge` 확장 활성화
- `setup_camera_publisher()`: OmniGraph 동적 생성 (Viewport→RenderProduct→CameraHelper)
- `setup_imu_publisher()`: `IsaacReadIMU` → `ROS2PublishImu` OG 파이프라인
- `setup_lidar_publisher()`: `RtxLidarROS2PublishPointCloud` Replicator writer
- `setup_clock_publisher()`: `/clock` 토픽 publish
- `setup_all_publishers()`: 로봇별 센서 일괄 publisher 설정

**3. `scripts/run_scene.py` 수정:**
- 센서 부착 후 ROS2 bridge 자동 설정 (try/except로 graceful fallback)
- ROS2 미설치 환경에서도 기존 기능 정상 동작

**4. Sensor YAML 업데이트 (4개):**
- `ros2_topic`, `ros2_frame_id` 필드 추가

**5. `scripts/run_ros2_test.py` (신규, ~160줄):**
- 5개 integration test: bridge 활성화, clock, camera, IMU, LiDAR publisher

### Key Decisions

- **Isaac Sim 내장 ROS2 bridge 사용**: custom rclpy publisher 대신 OmniGraph 노드 활용. C++ 파이프라인으로 고성능, 센서 prim에서 직접 데이터 읽기.
- **Internal rclpy**: 시스템 ROS2의 rclpy가 아닌 Isaac Sim 내장 rclpy 사용. 로그: `Could not import system rclpy → Attempting to load internal rclpy for ROS Distro: jazzy → rclpy loaded`.
- **Graceful fallback**: run_scene.py에서 ROS2 bridge를 try/except로 래핑. ROS2 없어도 렌더링/스크린샷 정상 동작.
- **OmniGraph 패턴**: Isaac Sim standalone 예제(`camera_periodic.py`, `rtx_lidar.py`, `clock.py`)의 검증된 패턴 그대로 적용.

### ROS2 토픽 구조

| 토픽 | 메시지 타입 | 소스 |
|------|-------------|------|
| `/rover_0/stereo_rgb/image_raw` | sensor_msgs/Image | ROS2CameraHelper (rgb) |
| `/rover_0/depth_camera/image_raw` | sensor_msgs/Image | ROS2CameraHelper (depth) |
| `/rover_0/imu_sensor/data` | sensor_msgs/Imu | IsaacReadIMU → ROS2PublishImu |
| `/rover_0/lidar_3d/points` | sensor_msgs/PointCloud2 | RtxLidarROS2PublishPointCloud |
| `/clock` | rosgraph_msgs/Clock | ROS2PublishClock |

### Test Results

- Unit tests: **140 passed**, 0 failed (regression 없음)
- **ROS2 Integration tests: 5/5 PASSED**
  - TEST 1: ROS2 Bridge Enable — `isaacsim.ros2.bridge-4.12.4` ✓
  - TEST 2: Clock Publisher — `/ROS2_Clock` graph 생성 ✓
  - TEST 3: Camera Publisher — viewport + render product 파이프라인 ✓
  - TEST 4: IMU Publisher — `IsaacReadIMU → ROS2PublishImu` OG ✓
  - TEST 5: LiDAR Publisher — `RtxLidarROS2PublishPointCloud` writer ✓

### 생성 파일 요약

| 파일 | 내용 |
|------|------|
| `marslab/ros2_bridge/__init__.py` | 모듈 init |
| `marslab/ros2_bridge/topic_config.py` | 토픽 네이밍 + 센서 매핑 |
| `marslab/ros2_bridge/publisher.py` | OmniGraph 기반 ROS2 publisher |
| `scripts/run_ros2_test.py` | 5개 integration test |

### Blockers / Issues

**[해결됨] 별도 터미널에서 `ros2 topic list` 실행 시 토픽 미표시:**
- **원인:** 테스트 스크립트가 ~14초 만에 종료 → publisher가 즉시 파괴되어 외부 ROS2 노드에서 발견 불가
- **해결:** `MARSLAB_PUBLISH=1` 환경 변수 기반 장시간 실행 모드 추가. 시뮬레이션이 무한 루프로 실행되며, 별도 터미널에서 `ros2 topic list/echo` 검증 가능. Ctrl+C로 종료.
- **결과:** `ros2 topic list` 및 `ros2 topic echo` 모두 **성공** 확인.

**[해결됨] `--publish` CLI 인자 → Isaac Sim Segmentation Fault:**
- **증상:** `~/isaacsim/python.sh scripts/run_ros2_test.py --publish` 실행 시 `--publish takes a parameter` → `Segmentation fault (core dumped)`.
- **원인:** Isaac Sim의 `python.sh`가 모든 CLI 인자를 Kit 애플리케이션(`isaacsim.exp.base.python.kit`)에 전달. `--publish`가 Kit의 인자 파서에서 유효하지 않은 옵션으로 인식되어 파싱 실패 → segfault.
- **해결:** CLI 인자(`--publish`) 대신 환경 변수(`MARSLAB_PUBLISH=1`)로 전환. `os.environ.get("MARSLAB_PUBLISH")` 방식은 Isaac Sim의 인자 파서와 충돌하지 않음.
- **교훈:** Isaac Sim `python.sh`로 실행하는 스크립트에서는 `argparse` 또는 custom CLI 플래그 사용에 주의. 환경 변수 방식이 안전.

### 장시간 실행 모드 사용법
```bash
# 장시간 publish (토픽 검증용, Ctrl+C로 종료)
MARSLAB_PUBLISH=1 PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_ros2_test.py

# 별도 터미널에서:
ros2 topic list
ros2 topic echo /rover_0/imu_sensor/data --once
```

### Next Steps
- ROS2 카메라 토픽에 화성 지형 미표시 문제 해결. 아래 엔트리 참조.

---

## [2026-04-10] ROS2 카메라 토픽 화성 지형 미표시 수정

**Module:** scripts/run_scene.py
**Type:** Fix

### 문제 발견

`MARSLAB_PUBLISH=1`로 `run_ros2_test.py` 실행 후 `ros2 topic echo`로 stereo camera 토픽을 수신 → **Isaac Sim 기본 격자 바닥**이 찍힘. 화성 지형, 바위, 대기, 하늘 없음.

**근본 원인 2가지:**

1. **`run_ros2_test.py`의 publish 모드가 기본 ground plane만 로드:** `world.scene.add_default_ground_plane()`만 사용. 전체 Mars scene 파이프라인(terrain, rocks, atmosphere, rendering) 미로드.

2. **`run_scene.py`의 sensor prim path 잘못 구성:** ROS2 bridge 코드에서 `f"{robot_config.type}_{i}_prim/{mount}/{sname}"` 패턴 사용 → 실제 spawn 함수가 반환한 prim path(예: `/simple_rover`)와 불일치.

### What Was Done

**`scripts/run_scene.py` 수정 (2건):**

**수정 A: sensor prim path를 실제 spawn 반환값 기반으로 변경**
- robot spawn 루프에서 `robot_prim_paths` dict에 `robot_name → actual prim path` 누적
- ROS2 bridge 코드에서 이 dict 참조 + `stage.GetPrimAtPath()`로 prim 존재 확인 후 경로 결정
- 이전: `f"{robot_config.type}_{i}_prim/{mount}/{sname}"` (존재하지 않는 경로)
- 이후: `f"{actual_robot_path}/{mount}/{sname}"` (실제 USD stage의 prim 경로)

**수정 B: `MARSLAB_PUBLISH=1` 장시간 실행 모드 추가**
- 스크린샷 완료 후, `MARSLAB_PUBLISH=1`이면 `simulation_app.close()` 대신 무한 루프
- 전체 Mars scene(terrain + rocks + atmosphere + sky + robots + sensors)이 로드된 상태에서 ROS2 계속 publish
- 300 프레임마다 상태 출력, Ctrl+C로 종료

### 사용법
```bash
# 전체 Mars scene + ROS2 장시간 publish
MARSLAB_PUBLISH=1 PYTHONPATH=/home/hoyunkim/MarsLab ~/isaacsim/python.sh scripts/run_scene.py

# 별도 터미널:
ros2 topic list
ros2 topic echo /rover_0/stereo_rgb/image_raw --once  # 화성 지형 이미지
```

### Test Results
- Unit tests: 140 passed, 0 failed (regression 없음)
- Isaac Sim 렌더링: **사용자 직접 실행 필요**

### Blockers / Issues
- 없음.

### Next Steps
- 시각적 품질 강화 (재시도 필요). 아래 엔트리 참조.

---

## [2026-04-10] 시각적 품질 강화 시도 → 실패 → 롤백

**Module:** marslab/terrain/, marslab/config/, configs/, assets/
**Type:** Feature (시도) → Revert

### 무엇을 시도했는가

OmniLRS/RLRoverLab 분석 결과, photorealism의 핵심은 **실제 사진 기반 PBR 텍스처**(4K-8K)와 **실제 3D 바위 메시**라는 것을 확인. 이를 바탕으로 4단계 품질 강화를 시도:

**Step 1: CC0 PBR 텍스처 에셋 확보 + 지형 적용**
- ambientCG에서 Ground037 (2K-PNG, 70MB) + Rock049 (2K-PNG, 66MB) 다운로드
- `material_applicator.py`에서 OmniPBR 셰이더에 `normalmap_texture`, `reflectionroughness_texture` 직접 연결 (UsdShade API)
- `assets/materials/mars_terrain/`, `assets/materials/mars_rock/` 디렉토리에 배치

**Step 2: 바위 재질 + 형상 개선**
- `rock_instancer.py`: 프로토타입 3→6개 확장, pitch/roll 랜덤 회전 추가
- Mars rock PBR 재질 적용 (적갈색 + roughness 0.92 + 텍스처)
- `schema.py`에 `rock_color`, `rock_roughness`, `rock_texture_dir` 필드 추가

**Step 3: 로봇 URDF 색상**
- Rover chassis: 회색 → sand/khaki, Wheels: 회색 → 먼지 갈색
- Rotorcraft rotors: 반투명 → 불투명

**Step 4: 하늘/안개**
- HDRI 재생성 (2048x1024, 수평선 그라디언트 + sun glow)
- fog_density_scale 0.002 → 0.005, fog_color warmer

### 발생한 문제

**Isaac Sim 렌더링 결과: 지형이 풀밭처럼 보임**
- Ground037 텍스처가 **잔디/풀밭 계열** (Sandy Ground이라고 했지만 실제로는 녹색 포함된 지구 토양)
- 화성 지형이 아니라 **지구 잔디밭**처럼 렌더링됨
- 텍스처 선택이 근본적으로 잘못됨 — ambientCG에서 "Mars-like"를 검색하는 것만으로는 부족

### 왜 롤백했는가

1. **텍스처 선택 실패**: CC0 소스에서 Mars regolith에 적합한 텍스처를 아직 찾지 못함. 적합한 텍스처 없이 코드만 변경하면 오히려 품질이 저하됨.
2. **검증 없이 진행**: 텍스처를 Isaac Sim에서 미리 확인하지 않고 코드까지 전부 변경함. 텍스처 선정 → 시각 확인 → 코드 변경 순서가 맞음.
3. **변경 범위가 너무 넓음**: 7개 파일을 동시에 수정하여 문제 발생 시 원인 특정이 어려움.

### 롤백한 항목 (전부 원래대로 복원)

| 파일 | 복원 내용 |
|------|-----------|
| `marslab/terrain/material_applicator.py` | normal/roughness 셰이더 연결 제거, `from pxr import Sdf` 제거 |
| `marslab/terrain/rock_instancer.py` | 원래 3 프로토타입 + yaw only + 재질 없음으로 복원 |
| `marslab/config/schema.py` | `rock_color`, `rock_roughness`, `rock_texture_dir` 필드 제거 |
| `configs/mars_env.yaml` | `texture_dir` 원래 경로 복원, rock 필드 제거, fog 파라미터 복원 |
| `configs/terrain/jezero_crater.yaml` | `texture_dir` 원래 경로 복원 |
| `assets/robots/rover/simple_rover.urdf` | chassis/wheel 색상 원래대로 |
| `assets/robots/rotorcraft/simple_rotorcraft.urdf` | rotor 색상 원래대로 |
| `scripts/run_scene.py` | rock config 전달 제거 (원래 호출 방식) |

### 교훈

1. **텍스처 선정이 먼저**: 코드 변경 전에 적합한 텍스처를 확보하고 시각적으로 확인해야 함
2. **Mars 전용 PBR 텍스처 필요**: 범용 CC0 소스에서 "ground rocky"로 검색하면 지구 토양이 나옴. NASA HiRISE ortho 이미지 기반 커스텀 텍스처 생성이 더 적합할 수 있음
3. **단계별 검증**: 한 번에 7개 파일을 변경하지 말고, 텍스처 1개 → 확인 → 다음 단계 순서로 진행
4. **OmniPBR normal/roughness 연결 코드는 유효**: `normalmap_texture`, `reflectionroughness_texture` 셰이더 입력 이름은 MDL에서 확인됨. 적절한 텍스처만 있으면 재적용 가능

### 보존된 발견 (재활용 가능)

- OmniPBR MDL 셰이더 입력 이름: `normalmap_texture`, `reflectionroughness_texture`, `reflection_roughness_texture_influence`
- UsdShade 직접 연결 코드 패턴은 검증됨 (Isaac Sim 5.1 호환)
- ambientCG API 사용법 확인 (`https://ambientcg.com/get?file={ID}_{format}.zip`)

### Next Steps
- 시각적 품질 강화를 위한 올바른 Mars 텍스처 소싱 전략 수립 필요
- 로봇 공중 부유/사라짐 문제 해결. 아래 엔트리 참조.

---

## [2026-04-10] 로봇 공중 부유 → World.reset() 적용 → 로봇 사라짐

**Module:** scripts/run_scene.py
**Type:** Bug Fix (진행 중)

### 문제 이력

1. **최초 문제 (공중 부유):** spawn_position Z=1.0m → 로봇이 지면 위 ~0.7m에 떠 있음. `simulation_app.update()` 60 step으로는 물리 시뮬레이션이 불안정하여 낙하 미발생.

2. **1차 수정 시도:** Z offset 1.0→0.3 감소 + `simulation_app.update()` → `World.step(render=True)` 120 step 전환.

3. **1차 수정 결과: 로봇 완전 사라짐.** Closeup 스크린샷에서 뒤집어진 삼각형 형태의 잔해만 보임. Rover/Quadruped 모두 사라짐. 반면 Bird's eye에서 크레이터 지형이 처음으로 선명하게 보임 (렌더링 자체는 개선).

### 근본 원인 분석 (Isaac Sim 소스 코드 확인)

**`World.reset()` 내부 동작 (world.py line 356-398):**
```
reset() → stop() → play() → _scene._finalize() → scene.post_reset()
```

1. `self.stop()` (simulation_context.py:977): `self._timeline.stop()` — **모든 물리 상태 초기화**
2. `self.play()` (simulation_context.py:900): timeline 재시작
3. `self.scene.post_reset()`: **`World.scene`에 등록된 객체만** default state 복원

**문제의 핵심:**
- MarsLab의 terrain/robot은 `World.scene.add()`가 아니라 **USD API(pxr)로 직접 생성**
- `World`는 이 객체들을 인식하지 못함 → `post_reset()`에서 위치 복원 안 됨
- `stop()`→`play()` cycle에서 물리 상태가 완전 초기화 → 로봇이 예측 불가능한 위치로 이동/사라짐
- Isaac Sim 공식 예제는 `World.scene.add()`로 객체를 추가하므로 `reset()`이 정상 작동

**해결 방향:** `World` 대신 `SimulationContext` 사용. scene 관리 없이 물리+렌더링만 구동. 기존 USD prim 위치를 건드리지 않음.

### Next Steps
- `World` → `SimulationContext` 전환 (시도 완료, 아래 참조)
- 선행연구 분석 기반 photorealism 전략 수립

---

## [2026-04-11] 선행연구 Photorealism 방법론 분석 보고서

**Type:** Research / Analysis
**대상:** reference_paper/ 내 13편 planetary robotics simulation 논문

### 1. 엔진별 분류

| 엔진 | 논문 | Photorealism 수준 |
|------|------|-------------------|
| **Isaac Sim** | OmniLRS, ISMRS, RLRoverLab | **높음** (RTX path tracing) |
| **Unreal Engine 5** | MarsDrone | **높음** (Nanite/Lumen) |
| **Unity** | LunarSim | **중상** (post-processing) |
| **Blender** | Mars Multi-terrain | **중간** (오프라인 렌더링) |
| **Chrono + OptiX** | Physics-based Lunar Sensor | **높음** (ray tracing + Hapke BRDF) |
| **Gazebo** | MarsSim, Simulation Framework, SEELO | **낮음** (rasterization) |
| **AGX Dynamics** | Lindmark et al., Linde et al. | **없음** (물리 전용) |
| **PyBullet** | Lunar Rover RL | **매우 낮음** |

### 2. Photorealism 핵심 방법론

#### 2a. 텍스처/재질 소싱

| 논문 | 방법 | 소스 |
|------|------|------|
| **OmniLRS** | CC0 PBR 라이브러리 | **Polyhaven** (gravel, sand) + **NVIDIA Base Materials** |
| **ISMRS** | 동일 | **Polyhaven** + **NVIDIA Thinner Gravel Material** |
| **MarsDrone** | AI 생성 PBR | 실제 Mars 사진 → MGNN(신경망) → PBR 6채널 자동 생성 |
| **Mars Multi-terrain** | Voronoi 랜덤화 | Mars 텍스처 라이브러리 + Voronoi 좌표 변환으로 tiling 반복 제거 |
| **Chrono Lunar** | 물리 기반 BRDF | **Hapke BRDF** (regolith 반사율 물리 모델) |

**핵심 발견: Polyhaven + NVIDIA Base Materials가 2편(OmniLRS, ISMRS)에서 검증됨.**

#### 2b. 바위 메시 소싱

| 논문 | 방법 | 상세 |
|------|------|------|
| **OmniLRS** | **Photogrammetry** | ~200개 lab 바위 촬영 → Reality Capture → Blender → 40K poly decimation → normal map bake → USD |
| **ISMRS** | **Photogrammetry** | ~150장/바위 → Reality Capture → Blender → 40K poly → normal bake → USD. 남극 운석도 SfM 처리 |
| **MarsDrone** | **AI 생성** | Mars 파노라마 이미지에서 바위 크롭 → Novel View Synthesis NN → Depth Estimation NN → 3D mesh. 57,186장 생성 |
| **Mars Multi-terrain** | 절차적 + scatter | Blender 모델 + terrain type별 분포 규칙 + weathering shader |
| **나머지** | 단순 primitive 또는 없음 | Sphere, Box, 또는 바위 없음 |

**핵심 발견: Photogrammetry (Reality Capture → Blender → USD)가 2편에서 동일 파이프라인으로 검증됨.**

#### 2c. 렌더링 방식

| 논문 | 렌더러 | 결과 |
|------|--------|------|
| **ISMRS** | RTX path tracing | **Path tracing이 ray tracing 대비 AP 39% 향상** (61.7 vs 30.1) |
| **OmniLRS** | RTX Real-Time + Interactive | 32 SPP, 6 bounces, 고품질 |
| **LunarSim** | Unity rasterization + **post-processing** | AO, contact shadow, color grading, SSR로 높은 시각 품질 달성 |

#### 2d. 대기/조명

| 논문 | 방법 |
|------|------|
| **MarsSim** | **가장 과학적.** Tau-dependent CIE chromaticity: `x = -0.0057τ² + 0.0358τ + 0.3781`. 5단계 dust opacity |
| **MarsDrone** | Mars-GRAM 대기 모델 (온도, 압력, 밀도 위치/고도별) |
| **MarsLab(현재)** | Beer's Law + COMIMART + butterscotch 보간 — **이미 대부분의 논문보다 과학적** |

### 3. 물리/충돌 처리

| 접근법 | 논문 | MarsLab Phase 1 적용 |
|--------|------|---------------------|
| **Rigid body only** | OmniLRS, ISMRS, RLRoverLab, LunarSim | **현재 MarsLab과 동일. 충분.** |
| **Terramechanics** (Bekker/Janosi) | MarsSim, PyBullet Lunar, Chrono | Phase 2 |
| **Deformable terrain** (DEM particles) | AGX Dynamics (2편), Chrono | Phase 2+ |

### 4. MarsLab에 대한 시사점

#### 즉시 적용 가능 (2+ 논문에서 검증)

| # | 방법론 | 출처 | MarsLab 적용 |
|---|--------|------|-------------|
| 1 | **Polyhaven + NVIDIA Base Materials** PBR | OmniLRS, ISMRS | 지형/바위 텍스처 소싱 |
| 2 | **Path tracing 기본값** | ISMRS (AP 39% 향상) | 이미 설정됨. 유지 |
| 3 | **Photogrammetry 바위 파이프라인** | OmniLRS, ISMRS | Reality Capture → Blender → USD (자원 필요) |
| 4 | **Replicator annotation** | OmniLRS, ISMRS | Week 12 annotation pipeline |
| 5 | **Golombek SFD 바위 분포** | MarsSim | 이미 구현됨 |
| 6 | **HiRISE DEM 지형** | ISMRS, Simulation Framework | 이미 구현됨 |

#### MarsLab 고유 차별점 (13편 모두에 없는 것)

| # | 차별점 |
|---|--------|
| 1 | **물리 기반 대기 파이프라인** (Beer's Law + COMIMART + tau 하늘) — 어떤 Mars 시뮬레이터도 없음 |
| 2 | **다종 로봇 동시 장면** (rover + drone + quadruped) |
| 3 | **AI4Mars 호환 4-class 벤치마크** |
| 4 | **ROS2 Jazzy 통합** |

#### ISMRS와의 직접 비교 (가장 유사한 선행연구)

| 항목 | ISMRS | MarsLab |
|------|-------|---------|
| 바위 | 4종 photogrammetry → **AP 10.9 (Curiosity 전이 실패)** | Golombek SFD 분포 (아직 Sphere) |
| 대기 | **없음** (pitch-black shadows) | Beer's Law + COMIMART + butterscotch sky |
| 다종 로봇 | 단일 rover만 | rover + rotorcraft + quadruped |
| 텍스처 | Polyhaven + NVIDIA | 절차적 1K (개선 필요) |

**ISMRS 핵심 약점**: 바위 다양성 부족(4종)으로 sim2real 전이 실패(AP=10.9). MarsLab은 이를 논문에서 지적하고 해결책 제시 가능.

### 5. 추가 발견 (개별 논문에서 주목할 방법론)

- **Chrono Lunar Sensor**: 물리 기반 카메라 센서 파이프라인 (pinhole → distortion → defocus → vignetting → Poisson-Gaussian noise → CRF). Sim2real 갭 평가에서 13% real + 87% synthetic가 100% real과 동등 성능 (DER < 1.52%).
- **MarsDrone**: AI 기반 PBR 생성 (Mars 사진 → 신경망 → BaseColor/Normal/Roughness/Height/AO/Metallic 자동 생성)
- **Mars Multi-terrain**: Voronoi 좌표 변환으로 PBR 텍스처 tiling 반복 제거
- **MarsSim**: Tau-dependent CIE chromaticity 수식 (MarsLab sky_dome.py에 적용 가능)
- **LunarSim**: Post-processing (AO, contact shadow, color grading, SSR)만으로 높은 시각 품질 달성

### 6. 권장 다음 조치

#### 텍스처 문제 해결 (최우선)
- **Polyhaven에서 Mars-like 텍스처 소싱** (OmniLRS/ISMRS 검증): "gravel", "sand", "rock" 검색
- NVIDIA Base Material Collection도 확인
- OmniPBR 셰이더에 normal/roughness 연결 코드는 이미 검증됨 (Phase B+에서 확인)

#### 바위 문제 해결
- **단기**: Sphere + PBR 재질 + pitch/roll 변형
- **중기**: Polyhaven/Sketchfab에서 CC0 rock 3D mesh 소싱 → USD 변환
- **장기**: Photogrammetry (Reality Capture → Blender → USD) — 자원 필요

#### 로봇 안착 문제
- SimulationContext 전환 시도했으나 로봇 뒤집힘 발생
- spawn Z offset 미세 조정 + URDF collision/inertia 검증 필요

#### 논문 포지셔닝
- ISMRS 대비 차별점: 대기 모델 + 바위 다양성 + 다종 로봇
- 비교 테이블에 13편 선행연구 vs MarsLab 포함

### Next Steps
- 텍스처 적용 + 바위 개선 + 로봇 안착. 아래 엔트리 참조.

---

## [2026-04-11] 지형 텍스처 적용 (Polyhaven brown_mud_dry)

**Module:** marslab/terrain/material_applicator.py, configs/
**Type:** Feature (품질 개선)

### What Was Done

**텍스처 소싱 (선행연구 기반 의사결정):**
- OmniLRS/ISMRS 논문이 **Polyhaven**을 PBR 소스로 사용한 것을 확인
- Polyhaven에서 3개 후보 다운로드: brown_mud_dry, bicolour_gravel, coast_sand_01
- 사용자 육안 확인 후 **brown_mud_dry** 선택 (갈색 마른 흙 + 작은 자갈, Mars regolith에 가장 유사)
- 이전 ambientCG Ground037 (풀밭) 실패 교훈 반영: 텍스처를 먼저 확인 후 적용

**코드 변경:**
- `material_applicator.py`: `_apply_textures()`에 normal/roughness 셰이더 직접 연결 추가
  - `normalmap_texture`, `reflectionroughness_texture` (OmniPBR.mdl input, UsdShade API)
  - `from pxr import Sdf` 추가
- `mars_env.yaml`, `jezero_crater.yaml`: `texture_dir` → `"assets/materials/mars_terrain"`
- `assets/materials/mars_terrain/`: brown_mud_dry 2K PBR 3종 배치 (albedo 9.4MB, normal 9.2MB, roughness 7.5MB)

**텍스처 교체 용이성 (G5):** YAML에서 `texture_dir` 경로만 변경하면 텍스처 세트 전체 교체 가능.

### Test Results
- Unit tests: 140 passed (regression 없음)
- Isaac Sim 렌더링: 지형에 갈색 마른 흙 텍스처 적용 확인, normal map 디테일 보임

---

## [2026-04-11] 바위 품질 개선 + 로봇 안착 수정

**Module:** marslab/terrain/rock_instancer.py, scripts/, assets/, configs/
**Type:** Feature + Fix

### Phase A: 바위 품질 개선

**A1. 절차적 angular rock mesh 생성:**
- `scripts/generate_rock_meshes.py` 신규 — trimesh + numpy로 icosphere noise 변형
- 8개 프로토타입 생성 → `assets/rocks/rock_proto_{0-7}.obj` (각 162 verts, 320 faces)
- 비균등 scale + vertex noise displacement + random shear → 각진 자연석 형태
- seed 기반 재현성 (G5), 시스템 Python에서 실행 (P3)

**A2. rock_instancer.py 전면 수정:**
- OBJ mesh 파일 로드 → `UsdGeom.Mesh`로 프로토타입 생성 (Sphere fallback 유지)
- OmniPBR 재질: Mars rock 적갈색 (0.42, 0.28, 0.20) + roughness 0.92
- pitch/roll 랜덤 회전 추가 (이전: yaw만) → 구체감 크게 감소
- `_create_prototypes()`, `_apply_rock_material()`, `_euler_to_quath()` 헬퍼 함수
- `rock_mesh_dir=None`이면 기존 Sphere 6개 프로토타입으로 fallback

**A3. Config 확장:**
- `schema.py`: `rock_color`, `rock_roughness`, `rock_mesh_dir` 필드 추가
- `mars_env.yaml`: `rock_mesh_dir: "assets/rocks"` 설정
- `pyproject.toml`: `trimesh>=4.0` 의존성 추가

### Phase B: 로봇 안착 수정

**B1. URDF friction/damping:**
- `simple_rover.urdf`: 6개 wheel joint에 `<dynamics damping="0.5" friction="1.0"/>` 추가

**B2. spawn Z 미세 조정:**
- rover/quadruped Z offset: 0.3 → 0.16m (wheel_radius 0.15 + 0.01 여유)

**B3. SimulationContext 재적용:**
- `run_scene.py`: `simulation_app.update()` → `SimulationContext.step(render=True)` 200 step
- 이전 `World.reset()` 문제(로봇 사라짐) 회피: SimulationContext는 scene 관리 없이 물리만 구동

**B4 (fallback 대기):** 여전히 뒤집히면 `fix_base=True` 적용 예정.

### 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `scripts/generate_rock_meshes.py` | **신규** — 8개 rock OBJ 생성 |
| `marslab/terrain/rock_instancer.py` | OBJ 프로토타입 + PBR 재질 + pitch/roll |
| `marslab/config/schema.py` | `rock_color`, `rock_roughness`, `rock_mesh_dir` 추가 |
| `configs/mars_env.yaml` | rock config + spawn Z 0.16 |
| `configs/terrain/jezero_crater.yaml` | spawn Z 0.16 |
| `assets/robots/rover/simple_rover.urdf` | wheel joint friction/damping 추가 |
| `scripts/run_scene.py` | SimulationContext 200 step + rock config 전달 |
| `pyproject.toml` | `trimesh>=4.0` 의존성 추가 |

### Test Results
- Unit tests: 140 passed (regression 없음)
- Isaac Sim 렌더링: **사용자 직접 실행 필요**

### Next Steps
- 에셋 품질 강화. 아래 엔트리 참조.

---

## [2026-04-11] 에셋 품질 강화: Mars 색 보정 + Blender 바위 + 개발 최적화

**Module:** scripts/, assets/, configs/
**Type:** Feature (품질 개선) + Optimization

### What Was Done

**1. Mars 색 보정 스크립트 (`scripts/color_grade_mars.py` 신규):**
- Polyhaven brown_mud_dry (지구 흙) → Mars regolith 색감으로 변환
- Red 채널 1.3x 강화 + Green 0.85x + Blue 0.70x + 채도 0.6 + 밝기 0.8
- 결과: `assets/materials/mars_terrain_graded/` (albedo + normal + roughness)
- normal/roughness는 색 무관하므로 원본 그대로 복사
- YAML `texture_dir` 변경만으로 텍스처 세트 교체 가능 (G5)

**2. Blender 바위 고품질화 (`scripts/blender_generate_rocks.py` 신규):**
- `blender --background --python` headless 모드로 8개 프로토타입 자동 생성
- Icosphere subdivisions=4 → Cloud noise + Musgrave noise 2중 displacement → decimate
- 각 1280 faces (이전 trimesh 320 대비 4x 디테일)
- 비균등 scale + 2단계 noise → 자연석에 가까운 각진 형태
- 기존 trimesh rock_proto_{0-7}.obj 삭제, Blender rock_blender_{0-7}.obj로 교체

**3. 로봇 안착 — simulation_app.update()로 최종 롤백:**
- SimulationContext/World 물리 시 로봇 뒤집힘 3회 반복 → 물리 시뮬레이션 포기
- Phase 1은 perception-only이므로 `simulation_app.update()` 60 step으로 고정
- 로봇은 spawn 위치에 그대로 유지. 물리 시뮬레이션은 Phase 2에서 재시도

**4. 개발 모드 최적화:**
- 바위 수: 15,720 → 844개 (k=0.05 → 0.012)
- SPP: 32 → 8, total_spp: 256 → 64, max_bounces: 8 → 4
- 스크린샷: 3장 → 2장 (bird's eye 제거)
- Steps/shot: 10 → 5, subframes: 4 → 2
- UV scale: 4.0 → 16.0 (tiling 반복 감소)
- 프로덕션 복원: YAML 값만 원래대로 변경

**5. 코드 품질 (CLAUDE.md 규칙 추가):**
- CLAUDE.md에 "모든 코드 변경은 black + ruff + pytest 통과 필수" 규칙 추가
- 전체 코드베이스 black 포매팅 (13개 파일) + ruff 린팅 (15개 에러 수정)

### 렌더링 결과 평가

**Closeup:**
- 로버 지면 안착 ✓, Go2 quadruped 보임 ✓
- 적갈색 Mars 지형 색감 ✓
- 지형 normal map 디테일 ✓

**Overview:**
- 적갈색 Mars 지면 + 바위 분포 ✓
- 로버/그림자 확인 ✓

**남은 문제:**
- 텍스처 tiling 반복 (overview에서 격자 패턴) — 더 큰 텍스처 또는 Voronoi 블렌딩 필요
- 바위 PBR 텍스처 미적용 (단색 적갈색만) — Rock049 텍스처 적용 대기
- 로버 chassis 단색 회색 — MVP에서 수용 가능

### 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `scripts/color_grade_mars.py` | **신규** — Mars 색 보정 |
| `scripts/blender_generate_rocks.py` | **신규** — Blender headless 바위 생성 |
| `assets/materials/mars_terrain_graded/` | **신규** — Mars 색감 PBR 텍스처 |
| `assets/rocks/rock_blender_{0-7}.obj` | **신규** — Blender 바위 8개 (1280 faces/개) |
| `configs/mars_env.yaml` | texture_dir, rock_sfd_k, spp, bounces 등 변경 |
| `scripts/run_scene.py` | bird's eye 제거, render step 감소, simulation_app.update() 롤백 |
| `CLAUDE.md` | black + ruff + pytest 필수 규칙 추가 |
| `pyproject.toml` | trimesh 의존성 |

### Test Results
- black: 전부 통과
- ruff: 전부 통과
- pytest: 140 passed

### Next Steps
- 바위 PBR 텍스처 + HiRISE 1:1 매핑. 아래 엔트리 참조.

---

## [2026-04-11] 바위 PBR 텍스처 + HiRISE 1:1 매핑 + 물리 위치 조정

**Module:** scripts/, marslab/terrain/, configs/, assets/
**Type:** Feature (품질 개선)

### What Was Done

**1. 바위 PBR 텍스처 적용 (Phase 4):**
- Rock049(ambientCG) 텍스처에 Mars 색 보정 적용 → `assets/materials/mars_rock/`
- `rock_instancer.py`에 `rock_texture_dir` 파라미터 추가
- `_apply_rock_material()`에서 albedo + normalmap_texture + reflectionroughness_texture 셰이더 연결
- `schema.py`에 `rock_texture_dir` 필드, YAML에 `rock_texture_dir: "assets/materials/mars_rock"` 추가

**2. HiRISE Ortho → PBR 변환 (Phase 2):**
- NASA HiRISE ESP_045994_1985 Jezero Crater ortho (RED_C, 6673×14266 grayscale) 다운로드
- `scripts/generate_pbr_from_photo.py` 신규 — photo → albedo (Mars tint) + normal (Sobel) + roughness (luminance)
- DEM 500×500 대응 영역을 ortho에서 비율 환산 crop (472×472) → 4096×4096 upscale
- 4K PBR 텍스처 생성 → `assets/materials/mars_hirise/`

**3. Tiling 완전 제거:**
- `material_applicator.py`: `set_project_uvw(True)` → `set_project_uvw(False)` 변경
  - `project_uvw=True`가 mesh UV를 무시하고 월드 좌표 기반 자동 tiling → 원인
  - `project_uvw=False`로 mesh_builder의 UV 좌표 사용 → 1:1 매핑 성공
- `mars_env.yaml`: `uv_scale: 1.0` (텍스처 1장 = 지형 전체)

**4. 물리 위치 조정:**
- 바위: Z를 `rock.height * 0.3`만큼 낮춤 → 30% 지면 매립 (자연스러움)
- Rover spawn Z: 0.16 → 0.32m (wheel_joint_z 0.15 + wheel_radius 0.15 + 여유)
- Quadruped spawn Z: 0.16 → 0.35m (Go2 다리 높이 고려)

### 렌더링 결과

- **tiling 완전 제거** — 실제 Jezero Crater 표면이 1:1로 매핑됨
- 로버 지면 안착, Go2 서 있음
- 바위 지면에 묻힘
- Mars 적갈색 색감 유지

### 미해결 문제

**바위 공중 부유 + 로봇 지면 관통:**
- Overview에서 바위 일부가 여전히 공중에 떠 보임
- 로버 일부와 Go2 대부분이 지형 내부로 파묻힌 것처럼 보임
- 원인 분석 필요 — OmniLRS/RLRoverLab 패턴 참고 예정

### 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `scripts/generate_pbr_from_photo.py` | **신규** — Mars photo → PBR 변환 |
| `marslab/terrain/rock_instancer.py` | `rock_texture_dir` 파라미터 + 바위 Z 매립 |
| `marslab/terrain/material_applicator.py` | `set_project_uvw(False)` (tiling 제거) |
| `marslab/config/schema.py` | `rock_texture_dir` 필드 추가 |
| `configs/mars_env.yaml` | uv_scale 1.0, rock_texture_dir, spawn Z 조정 |
| `assets/materials/mars_hirise/` | **신규** — 4K HiRISE PBR |
| `assets/materials/mars_rock/` | **신규** — Rock049 Mars 색 보정 PBR |

### Test Results
- black + ruff + pytest: 전부 통과 (140 tests)

### Next Steps
- fix_base 정적 배치 + 바위/로봇 Z 보정. 아래 엔트리 참조.

---

## [2026-04-11] fix_base 정적 배치 + Phase 2 동적 물리 로드맵

**Module:** marslab/robots/, marslab/terrain/, configs/
**Type:** Fix + Architecture Decision

### 문제

- 바위: 일부가 공중에 부유 (30% 매립 보정이 역효과)
- 로버/Go2: 지형 내부로 관통 (spawn Z offset 부정확)
- `SimulationContext` 물리 사용 시 로봇 뒤집힘 (3회 시도 모두 실패)

### 원인 분석 (OmniLRS/RLRoverLab 비교)

| 항목 | OmniLRS | RLRoverLab | MarsLab (이전) |
|------|---------|------------|---------------|
| 로봇 배치 | config 위치 + **물리 settle** | heightmap max Z | elevation + offset |
| 바위 배치 | DEM bilinear, **매립 없음** | 전체 3D mesh, 매립 없음 | elevation - 30% height |
| 물리 방식 | PhysX rigid body | PhysX + raycaster | simulation_app.update() (물리 없음) |

**핵심 발견:**
- OmniLRS는 물리 엔진으로 로봇을 자연스럽게 안착시킴
- MarsLab은 물리를 실행하면 URDF가 불안정하여 로봇이 뒤집힘
- URDF 문제: box chassis + 6 wheels (proper inertia/friction 미설정), rocker-bogie 없음
- 이것은 URDF 자체의 물리 품질 문제이지, 코드 문제가 아님

### 아키텍처 결정: Phase 1 = 정적, Phase 2 = 동적

**CLAUDE.md 근거:**
- "Phase 1 physics = rigid body + Mars-calibrated friction" (G4)
- "Do NOT validate legged robot dynamics. G1/Go2 are perception-ready only" (What NOT To Do #2)
- "Do NOT claim terramechanics fidelity in Phase 1" (#1)
- "MVP definition: Mars environment + single rover + terrain seg benchmark"

**선행연구 근거:**
- ISMRS: "explicitly does NOT model geomechanics. Perception-focused" — rigid body only
- OmniLRS: 일부 로봇 fix_base=True 사용

**결론:** Phase 1에서 fix_base 정적 배치는 CLAUDE.md에 완전히 부합하며, 선행연구와 동일한 접근법.

### What Was Done

**1. Rover fix_base=True:**
- `marslab/robots/rover.py`: `import_config.fix_base = True`
- 물리 없이 spawn 위치에 고정. perception-only Phase 1에 적합.

**2. 바위 매립 제거:**
- `rock_instancer.py`: `z - rock.height * 0.3` → `z` 그대로
- mesh 원점이 중심이므로 Z=surface이면 자연스럽게 반 묻힘 (OmniLRS 패턴)

**3. Spawn Z 통일:**
- Rover: 0.32 → 0.30 (wheel_joint -0.15 + wheel_radius 0.15)
- Quadruped: 0.35 → 0.30
- Rotorcraft: 3.0 유지 (공중 고정)

### Phase 2 동적 물리 로드맵 (ICRA 제출 후)

| Phase | 작업 | CLAUDE.md 근거 |
|-------|------|---------------|
| 2a | Rocker-bogie URDF + proper inertia/friction | G4 (physics fidelity) |
| 2b | SimulationContext 물리 전환 + fix_base 제거 | config 변경 1줄 |
| 2c | Terramechanics plugin (Bekker/Janosi) | PLAN.md 8.3 |
| 2d | RL/SLAM 통합 (Isaac Lab Gym API) | G1, G2 |

**전환 비용 최소화 설계:**
- `simulation_app.update()` → `SimulationContext.step()`: 1줄 변경
- `fix_base: true` → `fix_base: false`: YAML 1줄 변경 (G5)
- Config schema extends, does not break (PLAN.md Section 8.3)

### Test Results
- black + ruff + pytest: 전부 통과 (140 tests)
- Isaac Sim 렌더링: **사용자 직접 실행**

### Next Steps
- Isaac Sim 렌더링 결과 확인 (로봇/바위 위치)
- 이후: Annotation Pipeline (Week 12) → Benchmark (Week 13-16)
