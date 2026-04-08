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
- Week 3: Mars Atmosphere + Lighting (Offline) — sun_position.py, light_intensity.py, diffuse_fraction.py, sky_dome.py
