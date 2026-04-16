# Scene Generation Work Log (Stage 2)

---

## [2026-04-16] Stage 2: DEM Terrain + Atmosphere Scene

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** marslab/terrain/, marslab/rendering/, scripts/phase1/
**Type:** Feature (Scene pipeline)

---

### Plan

Stage 2는 DEM 기반 terrain mesh + Mars 대기 렌더링 뷰어를 구현한다.
로버/ROS2/Rock은 제외하고 순수 씬만 렌더링.

원래 계획 (plan file: `~/.claude/plans/parallel-popping-shell.md`):
- Step 2.1: `marslab/terrain/mesh_builder.py` 작성 (Layer1 offline + Layer2 USD)
- Step 2.2: `tests/unit/test_mesh_builder.py` 작성 + pytest PASS
- Step 2.3: `scripts/phase1/run_stage2.py` 작성 (terrain + atmosphere viewer)
- Step 2.4: Isaac Sim 시각 검증

---

### Step 2.1 -- mesh_builder.py 작성

**파일:** `marslab/terrain/mesh_builder.py` (~288 lines)

P3 Offline-First 원칙에 따라 두 레이어로 분리:

**Layer 1: `compute_mesh_arrays(elevation, resolution, uv_scale)` -- pure numpy**
- 고도 정규화: `elev -= np.nanmin(elev)` (절대 Mars datum -2518m 제거)
- NaN -> 0.0 대체
- Vertex: `(col * res, row * res, elev[row, col])`
- CCW winding: `[i00, i01, i10]` / `[i01, i11, i10]` -> +Z face normal 보장
- UV 좌표 + vertex normals (np.gradient 기반)
- 반환: dict with points, normals, face_indices, face_counts, uvs, normalized_elevation

**Layer 2: `build_terrain_mesh(elevation, resolution, stage, prim_path, uv_scale)`**
- Layer 1 호출 후 UsdGeom.Mesh prim 생성
- UsdPhysics.CollisionAPI + MeshCollisionAPI (approximation="none")
- Semantic label "soil"
- 반환: normalized elevation array

**Layer 1 보조: `terrain_z_at(elevation, resolution, x, y)`**
- Bilinear interpolation으로 world (x,y)에서 DEM 고도 샘플링
- 로버 spawn z 계산 + rock height sampling용

**Winding 수학적 보장:**
```
Triangle [i00, i01, i10]:
  edge1 = p01 - p00 = (+res, 0, dz)
  edge2 = p10 - p00 = (0, +res, dz)
  cross = (*, *, +res^2)  -> +Z normal
```

**Key Decision:** 이전 세션에서 winding 버그 (PhysX collision normal -Z -> rover 관통)와
절대 고도 문제로 전면 리셋된 교훈을 반영. 정규화와 winding을 수학적으로 보장.

---

### Step 2.2 -- test_mesh_builder.py 작성

**파일:** `tests/unit/test_mesh_builder.py` (25 tests)

| 카테고리 | 테스트 수 | 핵심 테스트 |
|----------|----------|------------|
| Winding/Normal | 4 | `test_all_face_normals_positive_z_flat` (THE critical test) |
| Elevation normalization | 3 | `test_elevation_absolute_mars_datum_normalized` |
| Geometry shape | 4 | `test_face_count_matches_grid`, `test_minimal_2x2_grid` |
| Normals/UVs | 3 | `test_normals_unit_length`, `test_flat_terrain_normals_all_up` |
| Dtypes/Keys | 2 | `test_output_dtypes_float32` |
| Error cases | 4 | `test_1x1_grid_raises`, `test_zero_resolution_raises` |
| terrain_z_at | 5 | `test_terrain_z_at_midpoint`, `test_terrain_z_at_clamp_outside` |

**결과:** 25 passed, 0 failed.

---

### Step 2.3 -- run_stage2.py 간소화

**파일:** `scripts/phase1/run_stage2.py`

사용자 피드백: "Rover와 ROS2는 상관없어. DEM 기반 scene만 렌더링. Rock도 전부 제거."

**변경 전:** 576줄 (rover spawn, OmniGraph ROS2, 센서, cmd_vel, rclpy 포함)
**변경 후:** 266줄 (terrain + atmosphere viewer only)

제거 항목:
- `from run_stage1 import (clamp_twist, resolve_joint_indices, skid_steer_targets)`
- `import omni.graph.core as og`
- `from isaacsim.core.prims import Articulation`
- `enable_extension("isaacsim.ros2.bridge")`
- `import rclpy`, `from geometry_msgs.msg import Twist`
- 로버 spawn 전체 (센서, OmniGraph, Articulation, cmd_vel 루프)
- `terrain_z_at` import (로버 없으므로 불필요)

유지 항목:
- `load_stage2_config()`, `load_terrain_elevation()`, `parse_args()`
- Terrain pipeline: elevation -> build_terrain_mesh -> apply_terrain_material
- Atmosphere pipeline: sun/sky/fog
- 무한 렌더 루프: `while simulation_app.is_running(): world.step(render=True)`

---

### Step 2.4 -- Isaac Sim 실행 및 버그 수정

**실행 1: UV primvar API 오류**
```
AttributeError: type object 'Vec2f' has no attribute 'GetArrayType'
```
- 원인: `Gf.Vec2f.GetArrayType()`는 Isaac Sim 5.x pxr에 존재하지 않음
- 수정: `Sdf.ValueTypeNames.TexCoord2fArray` 로 교체 (`mesh_builder.py` line 271)
- `from pxr import Sdf`를 기존 import 줄에 통합

**실행 2: 씬 렌더링 성공, 그러나 화면이 너무 어두움**

로그:
```
[run_stage2] Terrain: (256, 256) @ 1.0 m/px, z=[-2521.0, -2489.5] m
[run_stage2] Atmosphere: tau=0.3, direct=385.4 W/m2, diffuse_frac=0.33
[run_stage2] Terrain mesh: /World/Terrain, normalized z=[0.00, 31.53]
[run_stage2] Terrain material applied.
[run_stage2] Atmosphere configured (sun + sky + fog).
[run_stage2] Scene ready. Explore in GUI. Ctrl+C to exit.
```

---

### 어두움 원인 분석

**질문:** DEM 자체가 어두운가, 아니면 변환 과정에서 어두워진 것인가?

**결론: DEM/mesh 변환은 정상. 렌더러 보정 계수가 path-tracing 모드에 비해 너무 낮음.**

#### 물리 계산 검증 (모두 정확)

| 물리량 | 계산 | 참조 | 정확성 |
|--------|------|------|--------|
| Solar constant | 589 W/m^2 at 1.52 AU | IAU standard | 정확 |
| Beer's Law | 589 * exp(-0.3/cos(45deg)) = 385.4 W/m^2 | Appelbaum & Flood (1990) | 5% 이내 |
| Diffuse fraction | 0.33 at tau=0.3 | Vicente-Retortillo et al. (2015) Fig.4 | 논문값 일치 |
| Sky color | butterscotch (0.77, 0.59, 0.37) | Bell et al. (2006) | Pancam 데이터 기반 |

#### 문제: 렌더러 변환 계수

`sun_intensity_scale`과 `dome_brightness_scale`는 **물리 상수가 아니라 렌더러 보정값**이다.
물리적 W/m^2를 Isaac Sim 내부 단위로 변환하는 계수.

| 광원 | 물리값 | x scale | Isaac Sim 값 | 문제 |
|------|--------|---------|-------------|------|
| 태양 | 385.4 W/m^2 | x 5.0 | 1,927 | Path-tracing에서 너무 낮음 |
| 하늘 | 0.97 brightness | x 1000 x 0.33 | 320 | Path-tracing에서 너무 낮음 |

Path-tracing 모드에서 Isaac Sim DistantLight는 일반적으로 5,000~50,000 범위 필요.

#### 수정

`configs/mars_env.yaml` rendering 섹션:
- `sun_intensity_scale`: 5.0 -> 30.0 (x6 증가)
- `dome_brightness_scale`: 1000.0 -> 5000.0 (x5 증가)

**과학적 근거:** scale factor는 물리 모델이 아닌 렌더러 보정값이므로,
Beer's Law / COMIMART / sky color 등 물리 계산에 영향 없음.
조정은 최종 렌더링을 실제 화성 밝기에 맞추는 calibration.

---

### 수정 파일 목록

| 파일 | 변경 | 사유 |
|------|------|------|
| `marslab/terrain/mesh_builder.py` | 신규 작성 + UV primvar 타입 수정 | DEM -> mesh 변환 핵심 |
| `tests/unit/test_mesh_builder.py` | 신규 작성 | 25 unit tests |
| `scripts/phase1/run_stage2.py` | 576줄 -> 266줄 간소화 | terrain+atmosphere viewer only |
| `configs/mars_env.yaml` | sun_intensity_scale, dome_brightness_scale 조정 | 렌더러 보정 |

### 테스트 결과

```
black --check: passed
ruff check: passed
pytest tests/unit/ -v: 180 passed, 0 failed
```

---

## [2026-04-16] Stage 2.5: HiRISE DEM 분석 + Scenario YAML 생성

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/, configs/scenarios/
**Type:** Feature (DEM region analysis + scenario configs)

---

### Plan

기존 DEM → mesh 파이프라인 검증 완료 후, 실제 HiRISE DEM에서 두 종류의 지역을 추출:
1. **평지 (Flat):** 고도 차이 최소, 경사 완만 → Basic Mars scene용
2. **크레이터 (Crater):** 소규모 오목 지형 → Crater+Slopes scene용

원래 계획 (plan file: `~/.claude/plans/parallel-popping-shell.md`):
- Step A: `work_log/scene_generation/` 디렉토리 생성 + 기존 로그 이동
- Step B: DEM 분석 스크립트 작성 + 후보 추출 + 통합 시각화
- Step C: Scenario YAML 2개 생성 + 사용자 Isaac Sim GUI 검증

---

### Step A -- 작업 디렉토리 정리

`work_log/scene_generation/` 디렉토리 생성, `work_log/scene_generation.md`를 이동.
이후 scene generation 관련 기록/이미지는 모두 이 디렉토리에 저장.

---

### Step B -- HiRISE DEM 분석 + 후보 추출

**스크립트:** `scripts/analyze_dem_regions.py` (~310 lines)

**입력:** `assets/terrain/dem/jezero_crater_converted/` (500x500, 1.0 m/px)
- 고도 범위: -2584.46 ~ -2569.00 m (total dz = 15.46 m)
- NaN: 없음 (전체 유효)

**분석 방법:**
1. 전체 DEM 로드 (`load_converted_dem()` 재사용)
2. 200x200 슬라이딩 윈도우, stride=20으로 후보 스캔
3. 각 윈도우별 통계: dz (max-min), std, mean_slope, concavity (border - center mean)
4. **평지 후보:** `flat_score = dz + mean_slope * 2.0` 오름차순 상위 3개
5. **급경사 후보 (v2):** `mean_slope` 내림차순 상위 3개 (로버 경사 체감 우선)

> **v1 → v2 변경 사유:** 초기 concavity 기반 크레이터 후보(row=160,col=280)는
> mean_slope=2.93도로 로버가 경사를 거의 체감 못 함.
> 사용자 GUI 검증 후 mean_slope 기준으로 교체 결정 (2026-04-16).

**분석 결과:**

#### 평지 후보 (Flat Candidates) -- DEM 서쪽

| 순위 | row | col | size | dz (m) | std (m) | mean_slope (deg) |
|------|-----|-----|------|--------|---------|-----------------|
| #1 | 180 | 0 | 200 | 3.00 | 0.68 | 1.97 |
| #2 | 140 | 0 | 200 | 3.07 | 0.69 | 1.93 |
| #3 | 160 | 0 | 200 | 3.00 | 0.68 | 1.97 |

특징: DEM 서쪽(col=0) 영역이 전반적으로 평탄. 고도차 ~3m, 경사 ~2도.

#### 급경사 후보 (Steep Candidates) -- DEM 북동쪽

| 순위 | row | col | size | dz (m) | std (m) | mean_slope (deg) | max_slope (deg) | >5deg 비율 |
|------|-----|-----|------|--------|---------|-----------------|----------------|-----------|
| #1 | 0 | 300 | 200 | 12.57 | 2.91 | 5.08 | 29.9 | 44.8% |
| #2 | 0 | 280 | 200 | 11.50 | 2.54 | 4.80 | 29.9 | 40.8% |
| #3 | 20 | 300 | 200 | 11.89 | 2.79 | 4.66 | 29.9 | 38.8% |

특징: DEM 북동쪽(row=0, col=280~300) 영역이 가장 급경사.
면적의 45%가 5도 이상, 최대 30도 급경사 포함.
로버 경사 체감 가능, SLAM/Nav2 경로 계획에 차이 유발.

**산출물:** `work_log/scene_generation/dem_regions_overview.png`
- 전체 500x500 DEM elevation heatmap
- 평지 후보: 초록색 사각형 3개 (서쪽)
- 급경사 후보: 빨간색 사각형 3개 (북동쪽)
- 최적 후보(#1)는 실선, 나머지는 점선

---

### Step C -- Scenario YAML 생성

**파일 1:** `configs/scenarios/jezero_flat.yaml`
- source: hirise
- dem_crop: row=180, col=0, height=200, width=200
- Flat #1 후보 사용 (dz=3.00m, slope=1.97 deg)

**파일 2:** `configs/scenarios/jezero_crater.yaml`
- source: hirise
- dem_crop: row=0, col=300, height=200, width=200
- Steep #1 후보 사용 (dz=12.57m, mean_slope=5.08 deg, max_slope=29.9 deg)
- (v2) 초기 concavity 기반 후보(row=160,col=280)에서 교체

두 YAML 모두 mars_env + terrain + rendering 3 섹션 완비.
`run_stage2.py` 코드 변경 없이 `--config` 인자만 교체하면 동작.

**Isaac Sim 실행 명령:**
```bash
# 평지 scene
scripts/isaac_python.sh scripts/phase1/run_stage2.py \
    --config configs/scenarios/jezero_flat.yaml 2>&1 | tee temp_scene.txt

# 크레이터+경사 scene
scripts/isaac_python.sh scripts/phase1/run_stage2.py \
    --config configs/scenarios/jezero_crater.yaml 2>&1 | tee temp_scene.txt
```

---

### 수정 파일 목록

| 파일 | 작업 | 설명 |
|------|------|------|
| `work_log/scene_generation/` | 디렉토리 생성 | scene_generation.md 이동 |
| `scripts/analyze_dem_regions.py` | 신규 (v2: steep 기준) | DEM 분석 + 후보 추출 + 시각화 |
| `work_log/scene_generation/dem_regions_overview.png` | 산출물 (v2) | 전체 DEM + 후보 영역 표시 |
| `configs/scenarios/jezero_flat.yaml` | 신규 | 평지 HiRISE crop scenario |
| `configs/scenarios/jezero_crater.yaml` | 신규 (v2: steep crop) | 급경사 HiRISE crop scenario |

### 검증

- [x] `scripts/analyze_dem_regions.py` 실행 성공
- [x] `dem_regions_overview.png` 생성 + 시각 확인 (v2)
- [x] `jezero_flat.yaml` YAML 파싱 정상
- [x] `jezero_crater.yaml` YAML 파싱 정상 (v2: row=0, col=300)
- [x] Isaac Sim 평지 scene 렌더링 (사용자 GUI 검증 완료)
- [x] Isaac Sim 크레이터 scene 렌더링 (사용자 GUI 검증 완료, v1 — 경사 부족으로 교체)
- [x] Isaac Sim 급경사 scene 렌더링 (사용자 GUI 검증 완료, v2)

---

## Stage 2 완료 요약

**완료일:** 2026-04-16
**상태:** 전체 terrain + atmosphere 파이프라인 검증 완료

### 구현된 파이프라인

```
Config YAML → terrain elevation (offline) → atmosphere params (offline)
→ Isaac Sim → build_terrain_mesh (USD) → apply_material (PBR)
→ sun/sky/fog → infinite render loop
```

### 핵심 모듈

| 모듈 | 파일 | 역할 | Isaac Sim 필요? |
|------|------|------|-----------------|
| DEM 로더 | `marslab/terrain/dem_loader.py` | HiRISE GeoTIFF 로드 + crop | No |
| Mesh 빌더 | `marslab/terrain/mesh_builder.py` | elevation → USD mesh + collision | Partial |
| Material | `marslab/terrain/material_applicator.py` | PBR material 적용 | Yes |
| Rock 배치 | `marslab/terrain/rock_placer.py` | Golombek SFD 기반 (미사용) | No |
| 절차적 지형 | `marslab/terrain/procedural_generator.py` | flat/crater preset | No |
| 대기 | `marslab/environment/*.py` | Beer's Law, COMIMART, sky dome | No |
| 렌더링 | `marslab/rendering/*.py` | sun, sky dome, fog | Yes |

### 검증된 Scenario

| Scenario | Config | DEM Crop | 특징 |
|----------|--------|----------|------|
| 평지 | `configs/scenarios/jezero_flat.yaml` | row=180, col=0, 200x200 | dz=3m, slope=2deg |
| 급경사 | `configs/scenarios/jezero_crater.yaml` | row=0, col=300, 200x200 | dz=12.6m, slope=5deg, max 30deg |
| 절차적 크레이터 | `configs/mars_env.yaml` (procedural) | - | 256x256, crater preset |

### 테스트 결과

- Unit tests: 180 passed, 0 failed
- black/ruff: all passed
- Isaac Sim GUI: 3개 scene 모두 시각 검증 완료
  - 평지: 평탄한 HiRISE 지형, 대기/하늘/fog 정상
  - 급경사: 눈에 띄는 경사, 로버 테스트에 적합
  - 절차적 크레이터: procedural 대조군으로 유지

### 확장성

DEM 교체 시 코드 변경 없이 `converted_dem_dir` + `dem_crop` 좌표만 수정하면 됨.
Gale Crater, Syrtis Major 등 다른 HiRISE DEM도 동일 파이프라인으로 지원 가능.

---

## [2026-04-16] Stage 3: Rock Placement + Dynamic Atmosphere

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** marslab/terrain/, marslab/environment/, marslab/rendering/, scripts/phase1/
**Type:** Feature (Rock placement + dynamic atmosphere integration)

---

### Plan

Stage 2 terrain+atmosphere 파이프라인 위에 두 가지 주요 기능을 추가:
(A) Golombek SFD 기반 바위 배치 통합 + Rock-Dense 전용 맵
(B) 과학 기반 동적 대기 환경 (sun sweep + tau variation)

로버 통합은 별도 세션에서 진행 중이므로 범위 밖.

원래 계획 (plan file: `~/.claude/plans/parallel-popping-shell.md`):
- Phase A: Rock placement 통합 (run_stage2.py + jezero_rocks.yaml)
- Phase B: Offline atmosphere 함수 (sol sun position + tau profiles + unit tests)
- Phase C: Renderer update 함수 (update_sun_light, update_sky_dome)
- Phase D: Dynamic loop 통합 (YAML config + render loop 교체)
- Phase E: Offline 시각화 (4-panel matplotlib)

핵심 요구사항 (사용자):
1. Rock은 정규화된 고도(z_min=0) 기반으로 지형 표면에 정확히 배치
2. Rock-Dense 맵은 별도 YAML -> 총 3개 맵 (flat, rocks, crater)
3. Rock-Dense는 시각 확인 용이하도록 대형 바위 위주 (k=0.08, diameter 0.5-5m)
4. 동적 대기(sun sweep + tau variation)는 과학적 근거 기반
5. 동적 대기는 3개 맵 모두에 적용

---

### Phase A -- Rock Placement 통합

**재사용 모듈 (이전 세션에서 구현 완료, 코드 변경 없음):**

| 모듈 | 파일 | 상태 |
|------|------|------|
| Golombek SFD 샘플링 | `marslab/terrain/rock_placer.py` (156줄) | 17 unit tests passed |
| 3D PointInstancer 배치 | `marslab/terrain/rock_instancer.py` (224줄) | 구현 완료 |
| Rock OBJ meshes | `assets/rocks/rock_blender_{0-7}.obj` | 8개 생성 완료 |

**A1: run_stage2.py에 rock 배치 코드 추가**

`scripts/phase1/run_stage2.py` (terrain material 적용 직후, line ~229):
```python
rock_k = float(terrain_cfg.get("rock_sfd_k", 0))
if rock_k > 0:
    rocks = sample_rocks_golombek(area_m2, rock_k, d_range, seed=...)
    place_rocks_on_terrain(stage, rocks, norm_elevation, resolution, ...)
```
핵심: `norm_elevation` (z_min=0 정규화된 배열)을 전달하여 지형 표면에 정확히 배치.
`rock_k == 0` 이면 스킵 (jezero_flat은 바위 없음).

**A2: Rock-Dense Scenario YAML 생성**

`configs/scenarios/jezero_rocks.yaml` (신규):
- 평지 crop 재사용 (row=180, col=0, 200x200)
- `rock_sfd_k: 0.08` (CFA 8%, VL1급 고밀도 -- 기존 0.012의 ~7배)
- `rock_diameter_range: [0.50, 5.0]` (최소 50cm, 최대 5m -- 대형 바위 위주)

기존 맵 수정:
- `jezero_flat.yaml`: `rock_sfd_k: 0.012 -> 0` (바위 없는 순수 평지)
- `jezero_crater.yaml`: `rock_sfd_k: 0.012` 유지 (적당한 바위 밀도)

`marslab/config/schema.py` 수정: `rock_sfd_k` 하한 `ge=0.001 -> ge=0` (0 허용)

**A3: 3개 맵 Isaac Sim GUI 검증 -- 사용자 확인 완료**

---

### Phase B -- Dynamic Atmosphere: Offline 함수 (과학적 근거)

**B1: `compute_sol_sun_position()` 추가**

`marslab/environment/sun_position.py` 에 함수 추가:
```python
def compute_sol_sun_position(
    time_of_sol_fraction: float,  # [0, 1] where 0=sunrise, 1=sunset
    start_azimuth_deg: float = 90.0,   # sunrise (east)
    end_azimuth_deg: float = 270.0,    # sunset (west)
    max_elevation_deg: float = 60.0,   # noon peak
) -> SunPosition:
```

과학적 근거:
- 화성 sol = 88,642초 (24h 37m 22s) -- IAU 표준
- 방위각: 일출 90deg(E) -> 정오 180deg(S) -> 일몰 270deg(W), 선형 보간
  - Jezero crater 위도 18.4 deg N에서 선형 근사 유효 (Allison & McEwen 2000)
- 고도: `max_elevation * sin(pi * t)` -- 반구 기하학적 아크
  - Jezero에서 max ~60-70deg (Ls 의존, v2.0에서 정밀화)

**B2: `marslab/environment/tau_profile.py` 신규 작성 (~60줄)**

3가지 tau 시간 프로파일:
- `compute_tau_constant(base_tau, t)`: 일정 (맑은 날)
- `compute_tau_ramp(start_tau, end_tau, t)`: 선형 증가 (먼지 폭풍 onset)
- `compute_tau_sine(base_tau, amplitude, period_fraction, t)`: 주기적 변동
- `compute_tau(profile, t, **kwargs)`: 디스패처

과학적 근거:
- tau 관측 범위: ~0.2 (clear) ~ 6+ (2018 global dust storm)
- Ref: Lemmon et al. (2015) Icarus, Smith et al. (2019) JGR Planets
- tau -> Beer's Law (직사광) + COMIMART (산란광) -- 기존 모듈 재사용

**B3: Unit tests**

- `tests/unit/test_sol_sun_position.py`: 12 tests (boundary, zenith, validation)
- `tests/unit/test_tau_profile.py`: 21 tests (constant, ramp, sine, dispatch, validation)

---

### Phase C -- Renderer Update 함수 (Flicker-Free)

**C1: `update_sun_light()` -- `marslab/rendering/sun_renderer.py`**

기존 `configure_sun_light()`는 prim 삭제 -> 재생성 (init용).
새 `update_sun_light()`는 기존 prim의 attribute만 in-place 업데이트:
- intensity, color: `UsdLux.DistantLight` attribute
- rotation: `UsdGeom.Xformable.GetOrderedXformOps()[0].Set(...)`
- prim 없으면 fallback -> `configure_sun_light()`

**C2: `update_sky_dome()` -- `marslab/rendering/sky_renderer.py`**

동일 패턴: 기존 DomeLight의 color + intensity attribute만 업데이트.

**C3: Fog -- 변경 불필요**

`configure_atmosphere_fog()`는 `carb.settings.set()` 호출만 하므로 이미 re-entrant.

---

### Phase D -- Dynamic Loop 통합

**D1: YAML config 구조**

`mars_env` 하위에 `dynamic_atmosphere` 섹션 추가 (optional):
```yaml
mars_env:
  dynamic_atmosphere:
    enabled: true
    time_scale: 200.0          # 실시간 대비 가속 배율
    sun_sweep:
      start_azimuth_deg: 90    # sunrise (east)
      end_azimuth_deg: 270     # sunset (west)
      max_elevation_deg: 60    # noon peak
    tau_profile: "constant"    # "constant" | "ramp" | "sine"
    tau_constant:
      base_tau: 0.3
    update_interval_frames: 10
```

**D2: run_stage2.py render loop 교체**

```python
while simulation_app.is_running():
    world.step(render=True)
    frame += 1
    if dynamic_enabled and frame % update_interval == 0:
        elapsed += physics_dt * update_interval * time_scale
        t = (elapsed % sol_duration) / sol_duration
        # Recompute: sun_pos -> tau -> intensity -> diffuse -> sky
        # Update: update_sun_light, update_sky_dome, configure_atmosphere_fog
```

`dynamic_enabled=False` 시 기존 static 동작 보존.

**D3: 3개 Scenario YAML 모두 `dynamic_atmosphere.enabled: true` 추가**

- `configs/scenarios/jezero_flat.yaml`
- `configs/scenarios/jezero_rocks.yaml`
- `configs/scenarios/jezero_crater.yaml`
- `configs/mars_env.yaml`: `dynamic_atmosphere.enabled: false` (기본값)

---

### Phase E -- Offline 시각화

`scripts/visualize_dynamic_atmosphere.py` (신규):

Isaac Sim 없이 matplotlib 4-panel:
1. **Sun trajectory**: azimuth + elevation vs time-of-sol (0~24.66h)
2. **Tau profiles**: constant / ramp / sine 비교
3. **Direct irradiance**: Beer's Law over sol (constant vs ramp tau)
4. **Sky color swatches**: sky dome color at 6 time points

산출물: `work_log/scene_generation/dynamic_atmosphere_visualization.png`

---

### 수정 파일 목록

| 파일 | 작업 | Phase |
|------|------|-------|
| `scripts/phase1/run_stage2.py` | 수정: rock block + dynamic loop | A, D |
| `configs/scenarios/jezero_rocks.yaml` | **신규**: Rock-Dense scenario | A |
| `configs/scenarios/jezero_flat.yaml` | 수정: rock_sfd_k -> 0, dynamic_atmosphere 추가 | A, D |
| `configs/scenarios/jezero_crater.yaml` | 수정: dynamic_atmosphere 추가 | D |
| `configs/mars_env.yaml` | 수정: dynamic_atmosphere 섹션 (disabled) | D |
| `marslab/config/schema.py` | 수정: rock_sfd_k ge=0 허용 | A |
| `marslab/environment/sun_position.py` | 수정: `compute_sol_sun_position()` 추가 | B |
| `marslab/environment/tau_profile.py` | **신규** (~60줄) | B |
| `marslab/rendering/sun_renderer.py` | 수정: `update_sun_light()` 추가 | C |
| `marslab/rendering/sky_renderer.py` | 수정: `update_sky_dome()` 추가 | C |
| `tests/unit/test_sol_sun_position.py` | **신규** (12 tests) | B |
| `tests/unit/test_tau_profile.py` | **신규** (21 tests) | B |
| `scripts/visualize_dynamic_atmosphere.py` | **신규** | E |

### 테스트 결과

```
black --check: passed (75 files)
ruff check: passed
pytest tests/unit/ -v: 213 passed, 0 failed (180 기존 + 33 신규)
```

### 시각 검증

- [x] **jezero_flat**: 바위 없는 평탄 지형, dynamic sun sweep 정상
- [x] **jezero_rocks**: 대형 바위가 지형 표면에 자연스럽게 배치됨
- [x] **jezero_crater**: 급경사 지형 위 바위가 경사면 따라 배치됨
- [x] 3개 맵 모두: 태양 동->서 이동 (그림자 방향 변화 확인)
- [x] dynamic_atmosphere.enabled: false 시 기존 static 동작 보존

---

## [2026-04-16] Stage 3.5: Interactive Atmosphere Control Panel

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** marslab/gui/, scripts/phase1/
**Type:** Feature (omni.ui interactive GUI panel)

---

### Plan

Stage 3 dynamic atmosphere가 YAML 기반 자동 제어만 지원했으므로,
사용자가 시뮬레이션 중 실시간으로 대기 파라미터를 조정할 수 있는
omni.ui 기반 interactive panel을 추가.

사용자 요구사항:
1. Tau (먼지 광학 깊이)를 슬라이더로 실시간 조정 -> fog/sky/irradiance 즉시 반영
2. 태양 제어 모드 선택: Auto Sweep (동->서 자동) vs Manual (사용자 직접 위치 제어)
3. Manual 모드에서 azimuth/elevation 슬라이더로 태양 위치 조정

---

### 설계: Shared State Dict + omni.ui Callback

핵심 아키텍처:
- `atmosphere_state` dict: render loop과 GUI panel이 공유하는 mutable state
- GUI 슬라이더 callback: dict 값 대입만 수행 (~1ns, non-blocking)
- render loop: 매 N프레임마다 dict 값을 읽어 renderer 업데이트
- headless 모드: panel 생성 스킵, 기존 YAML 기반 동작 유지
- omni.ui 불가 시: try/except graceful fallback

---

### 구현

**신규 파일: `marslab/gui/__init__.py`** (빈 패키지)

**신규 파일: `marslab/gui/atmosphere_panel.py`** (~176줄)

`AtmospherePanel` 클래스 (`omni.ui.Window` 기반):

| UI 요소 | 타입 | 범위 | 동작 |
|---------|------|------|------|
| Tau slider | `ui.FloatSlider` | 0.1 -- 6.0 | fog 밀도 + sky color + irradiance 즉시 변경 |
| Mode buttons | `ui.Button` x2 | Auto / Manual | sun_mode 전환, Manual 슬라이더 활성/비활성 |
| Azimuth slider | `ui.FloatSlider` | 0 -- 360 | Manual 모드에서만 활성 |
| Elevation slider | `ui.FloatSlider` | 0.5 -- 89.5 | Manual 모드에서만 활성 |
| Status labels | `ui.Label` x3 | 읽기 전용 | tau, irradiance, diffuse fraction, sol time 표시 |

Auto 모드에서 Manual 전환 시 azimuth/elevation 슬라이더가 현재 auto 위치를 반영
(위치 점프 방지).

**수정 파일: `scripts/phase1/run_stage2.py`**

변경 내용:
1. `atmosphere_state` dict 생성 (tau, sun_mode, sun_azimuth_deg, sun_elevation_deg 등)
2. `if not args.headless:` 가드 내에서 `AtmospherePanel(atmosphere_state)` 생성
3. render loop 리팩토링:
   - tau는 항상 `atmosphere_state["tau"]`에서 읽음 (GUI 슬라이더 or 초기값)
   - `sun_mode == "auto"`: 기존 `compute_sol_sun_position()` 시간 기반 sweep
   - `sun_mode == "manual"`: `compute_sun_position(azimuth, elevation)` 슬라이더 값 사용
   - 매 업데이트 후 `atmo_panel.update_display()` 호출로 status label 갱신

---

### 수정 파일 목록

| 파일 | 작업 | 설명 |
|------|------|------|
| `marslab/gui/__init__.py` | **신규** | 빈 패키지 init |
| `marslab/gui/atmosphere_panel.py` | **신규** (176줄) | omni.ui atmosphere control panel |
| `scripts/phase1/run_stage2.py` | 수정 | atmosphere_state + panel 연동 + render loop 리팩토링 |

### 테스트 결과

```
black --check: passed (79 files)
ruff check: passed
pytest tests/unit/ -v: 222 passed, 0 failed
```

### 시각 검증

- [x] Panel 윈도우가 Isaac Sim 내에 정상 표시
- [x] Tau 슬라이더 드래그 -> fog 밀도 + 하늘색 실시간 변경
- [x] Sun mode "Auto Sweep" -> 태양 자동 동->서 이동
- [x] Sun mode "Manual" -> 슬라이더로 azimuth/elevation 직접 제어
- [x] 3개 맵 모두 정상 동작 확인

---

## Stage 3 + 3.5 완료 요약

**완료일:** 2026-04-16
**상태:** Rock placement + Dynamic atmosphere + Interactive GUI 전체 검증 완료

### 구현된 파이프라인 (Stage 2 대비 추가)

```
Config YAML → terrain → atmosphere → Isaac Sim → mesh → material
→ rock placement (Golombek SFD, PointInstancer)
→ sun/sky/fog (static init)
→ dynamic atmosphere loop (auto sun sweep + GUI tau/sun control)
→ interactive panel (omni.ui sliders + status readout)
```

### 검증된 3개 Scenario

| Scenario | Config | 특징 |
|----------|--------|------|
| 평지 | `configs/scenarios/jezero_flat.yaml` | 바위 없음, dz=3m, slope=2deg |
| Rock-Dense | `configs/scenarios/jezero_rocks.yaml` | k=0.08, 0.5-5m 대형 바위, 평지 crop |
| 급경사+바위 | `configs/scenarios/jezero_crater.yaml` | k=0.012, dz=12.6m, max slope 30deg |

### 테스트 결과 누적

- Unit tests: 222 passed (180 Stage 2 + 33 Stage 3 + 9 기타)
- black/ruff: all passed
- Isaac Sim GUI: 3개 scene + interactive panel 시각 검증 완료

---

## [2026-04-16] Stage 4 준비: Cerberus Fossae HiRISE DTM 취득 및 DEM 변환

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** assets/terrain/dem/
**Type:** Data acquisition (Scenario 4 Canyon 지형 데이터)

---

### 목적

Scenario 4 (Canyon)는 화성 협곡 지형에서의 SLAM/Nav2 성능을 평가하는 시나리오.
Jezero crater DEM (500x500, 15m 고도차)으로는 협곡 지형을 표현할 수 없으므로,
실제 화성 균열 지형인 **Cerberus Fossae** HiRISE DTM을 별도로 취득.

**지형 선정 근거** (참조: `work_log/scenario_asset_strategy.md`):
- Cerberus Fossae = 화성 Elysium Planitia의 대규모 균열(graben) 지형
- 폭 ~1-2 km, 깊이 수백 m의 협곡이 로버 자율주행 시나리오에 적합
- HiRISE DTM이 공개되어 있어 즉시 사용 가능
- InSight 착륙지 인근으로 과학적 관심도 높음

---

### 데이터 소스

| 항목 | 값 |
|------|-----|
| **소스** | University of Arizona HiRISE (Mars Reconnaissance Orbiter) |
| **검색 URL** | `https://www.uahirise.org/results.php?keyword=cerberus+fossae` |
| **제품 페이지** | `https://www.uahirise.org/dtm/DTEEC_017719_1890_017218_1890_A01` |
| **Product ID** | DTEEC_017719_1890_017218_1890_A01 |
| **원본 포맷** | PDS3 .IMG (NASA Planetary Data System) |
| **다운로드 파일** | `DTEEC_017719_1890_017218_1890_A01.IMG` (352 MB) |
| **저장 위치** | `assets/terrain/dem/cerberus_fossae.IMG` |

---

### 변환 파이프라인

```
PDS3 .IMG (352 MB)
  → [Python GDAL: gdal.Open() + driver.CreateCopy()]
  → GeoTIFF cerberus_fossae.tif
  → [marslab/terrain/dem_loader.py: load_hirise_dem() + save_converted_dem()]
  → cerberus_fossae_converted/
      ├── elevation.npy (336 MB, float32)
      └── metadata.json
```

**Step 1: PDS3 → GeoTIFF**
- `gdal_translate` CLI가 시스템에 없어 Python GDAL 사용
- `from osgeo import gdal` → `gdal.Open()` → `GetDriverByName("GTiff").CreateCopy()`
- 출력: `assets/terrain/dem/cerberus_fossae.tif`

**Step 2: GeoTIFF → numpy**
- 기존 `load_hirise_dem()` 함수로 GeoTIFF 로드 (GDAL 의존)
- `save_converted_dem()`으로 GDAL 없이 로드 가능한 numpy 포맷 저장
- 출력: `assets/terrain/dem/cerberus_fossae_converted/`
- Isaac Sim Python (GDAL 미탑재)에서 `load_converted_dem()` 으로 로드

---

### DEM 특성

| 항목 | 값 |
|------|-----|
| **크기 (pixels)** | 6,301 x 13,955 (width x height) |
| **해상도** | 1.0114 m/px |
| **공간 범위** | 6.4 km x 14.1 km |
| **좌표계** | Equirectangular Mars (central meridian 162.84°) |
| **고도 범위** | -3,334.3 m ~ -1,761.6 m |
| **고도차 (relief)** | **1,572.7 m** |
| **NaN 비율** | 29% (가장자리 stereo coverage 부족 영역) |

#### Jezero DEM과 비교

| 항목 | Jezero | Cerberus Fossae |
|------|--------|-----------------|
| 크기 | 500 x 500 px | 6,301 x 13,955 px |
| 해상도 | 1.0 m/px | 1.01 m/px |
| 공간 범위 | 0.5 x 0.5 km | 6.4 x 14.1 km |
| 고도차 | 15.5 m | **1,572.7 m** |
| 최대 경사 | ~30° | **40-60°** (협곡 벽면) |
| NaN | 0% | 29% |

Cerberus Fossae는 Jezero 대비 **면적 360배, 고도차 100배**.
협곡 벽면에서 40-60도 급경사가 형성되어 로버 자율주행 챌린지로 적합.

#### 지형 분포 특성 (histogram 분석)

- **평원 (대다수 픽셀)**: 고도 -2,900 ~ -2,800 m 집중, 경사 5° 미만
- **협곡 바닥**: 고도 -3,300 m 부근 소규모 peak
- **협곡 벽면**: 경사 40-60°, slope map에서 inferno 밝은 색으로 표시
- 평균 고도: -2,807 m, 중위값: -2,862 m

---

### 산출물

| 파일 | 설명 | 크기 |
|------|------|------|
| `assets/terrain/dem/cerberus_fossae.IMG` | 원본 PDS3 (변환 완료 후 삭제 가능) | 352 MB |
| `assets/terrain/dem/cerberus_fossae.tif` | 중간 GeoTIFF | ~336 MB |
| `assets/terrain/dem/cerberus_fossae_converted/elevation.npy` | 최종 numpy 고도 배열 | 336 MB |
| `assets/terrain/dem/cerberus_fossae_converted/metadata.json` | 메타데이터 (해상도, CRS 등) | 788 B |
| `work_log/scene_generation/cerberus_fossae_dem_overview.png` | 4-panel 시각화 | - |

### 시각화 (4-panel)

`work_log/scene_generation/cerberus_fossae_dem_overview.png`:
1. **Full Elevation Map**: terrain colormap, 협곡이 중앙~하단에 뚜렷
2. **Hillshade**: 경사면 음영, 협곡 벽면 지형 상세 확인
3. **Elevation Distribution**: 히스토그램, 평원(-2900m)과 협곡 바닥(-3300m) 이봉 분포
4. **Slope Map**: inferno colormap, 협곡 가장자리 40-60° 급경사

---

### 다음 단계

- ~~협곡 중심부에서 NaN이 없는 crop 영역 선정~~ → 완료
- ~~`configs/scenarios/cerberus_canyon.yaml` Scenario YAML 생성~~ → 완료
- ~~Isaac Sim에서 Canyon scene 렌더링 + 시각 검증~~ → 완료

---

## [2026-04-16] Stage 4: Canyon Scenario 구현

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** marslab/terrain/, configs/scenarios/, scripts/phase1/
**Type:** Feature (Canyon scenario — HiRISE crop + procedural corridor)

---

### Plan

Scenario 4 (Canyon)는 협곡 지형에서의 로버 perceptual robotics 시나리오.
목표: traversability 연구, 장애물 회피, SLAM, Navigation 테스트.

3단계로 진행:
1. Cerberus Fossae DEM에서 최적 Canyon crop 영역 선정
2. HiRISE 기반 Canyon scene 2개 (Challenge + Easy)
3. "양벽+중앙통로" corridor는 procedural 생성으로 해결

---

### Phase A — Canyon Crop 분석

Cerberus Fossae DEM (13955x6301 px, 1.01 m/px)에서 10개 후보를 수작업으로 선정하여 분석.

**분석 기준:**
- NaN-free (mesh builder 요구사항)
- 고도차 (dz), traversable 비율 (<15°), impassable 비율 (>30°)
- 로버가 실제로 주행 가능한 경로 존재 여부

**분석 결과 (10개 → 2개 선정):**

| 선정 | row | col | size | dz | trav% | imp% | 특징 |
|------|-----|-----|------|----|-------|------|------|
| **C (1순위)** | 8000 | 2800 | 500x500 | 460m | 43% | 28% | Rim-to-floor, 경로 탐색 필수 |
| **G (2순위)** | 8500 | 3200 | 400x400 | 110m | 82% | 8% | 대부분 주행 가능, 입문 난이도 |

**제외 사유:**
- B, H, J, F, I: traversable <10% (절벽, 로버 불가)
- D, E: dz <70m (고도차 부족, 협곡 느낌 없음)

산출물: `work_log/scene_generation/cerberus_canyon_candidates.png`

---

### Phase B — HiRISE Canyon Scenario YAML

**`configs/scenarios/cerberus_canyon.yaml`** (신규):
- HiRISE crop: row=8000, col=2800, 500x500 (~505x505m)
- dz=460m, traversable 43%, 경로 탐색이 핵심 과제
- `rock_sfd_k: 0.008` (소량), `rock_diameter_range: [0.15, 2.0]`

**`configs/scenarios/cerberus_canyon_easy.yaml`** (신규):
- HiRISE crop: row=8500, col=3200, 400x400 (~405x405m)
- dz=110m, traversable 82%, 중앙에 원형 crater 포함
- SLAM 기본 검증, 장애물 회피 초기 테스트

두 scene 모두 Isaac Sim 시각 검증 완료: 텍스처, 동적 대기, GUI 패널 정상 동작.

---

### Phase C — Corridor Topology 분석 및 Procedural Canyon

**문제:** 사용자 요구 "양옆에 절벽 + 중앙 통로" 구조.
Cerberus Fossae 메인 graben은 폭 5-6km로 500m crop에 양벽을 담을 수 없음.

**분석 과정:**
1. East-west 단면 프로파일 (row 6000~10500): 모든 구간에서 rim-to-rim = 5000-6000 px
2. 보조 지형 탐색 (wall-floor-wall 패턴): 22개 raw → 4개 후보, 최대 벽 높이 18m (불충분)
3. **결론: Cerberus Fossae는 corridor 시나리오에 부적합**

**해결: Procedural canyon generator 구현**

`marslab/terrain/procedural_generator.py`에 `_generate_canyon()` 함수 추가 (~100줄):

알고리즘:
1. 기저 평원 생성 (flat base + low-freq noise)
2. 구불구불한 중심선 정의 (2개 sinusoid 합성, `canyon_curvature` 파라미터)
3. 중심선 거리 기반 단면 프로필 적용:
   - `d < floor_half_width`: 바닥 (평탄, ~0° slope)
   - `floor_half ~ rim_half`: smoothstep(3t²-2t³) 전환 (벽면, 50-75°)
   - `d > rim_half`: 원래 평원 유지
4. 소규모 크레이터 삽입 (canyon 바닥, parabolic + rim)
5. Micro detail (기존 `_add_micro_detail()` 재사용)

**YAML 파라미터 (G5 준수):**

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `canyon_depth` | 40.0 | 바닥→rim 높이차 (m) |
| `canyon_floor_width` | 30.0 | 바닥 평탄부 폭 (m) |
| `canyon_total_width` | 80.0 | rim-to-rim 전체 폭 (m) |
| `canyon_curvature` | 0.3 | 중심선 굴곡 강도 |
| `canyon_craters` | 2 | 바닥 크레이터 수 |
| `canyon_crater_radius_range` | [5, 15] | 크레이터 반경 (m) |
| `canyon_crater_depth_range` | [2, 6] | 크레이터 깊이 (m) |

**`configs/scenarios/procedural_canyon.yaml`** (신규):
- source: procedural, preset: canyon, 300x300 @ 1m/px
- 결과: 양쪽 절벽(>30°, 16%) + 중앙 통로(<5°, 71%) + 크레이터 2개
- dz=50m, max slope 75°

**파이프라인 통합:**
- `generate_terrain("canyon", ...)` → 기존 `build_terrain_mesh()` → `apply_terrain_material()`
- 동일한 Mars regolith 텍스처, 동일한 대기/GUI → HiRISE scene과 시각적 일관성 보장
- `run_stage2.py`에서 `canyon_*` prefix params를 자동 수집하여 전달

산출물: `work_log/scene_generation/procedural_canyon_preview.png`

---

### 수정 파일 목록

| 파일 | 작업 | Phase |
|------|------|-------|
| `configs/scenarios/cerberus_canyon.yaml` | **신규** | B |
| `configs/scenarios/cerberus_canyon_easy.yaml` | **신규** | B |
| `configs/scenarios/procedural_canyon.yaml` | **신규** | C |
| `marslab/terrain/procedural_generator.py` | 수정: `_generate_canyon()` + preset 등록 | C |
| `scripts/phase1/run_stage2.py` | 수정: canyon params 전달 로직 | C |
| `tests/unit/test_procedural_generator.py` | 수정: canyon tests 8개 추가 | C |

### 테스트 결과

```
black --check: passed
ruff check: passed
pytest tests/unit/ -v: 233 passed, 0 failed (222 기존 + 8 canyon + 3 기타)
```

### 시각 검증

- [x] **cerberus_canyon**: 460m 고도차, 협곡 rim에서 바닥까지 극적 지형, 동적 대기 정상
- [x] **cerberus_canyon_easy**: 110m 고도차, 중앙 crater, 대부분 주행 가능
- [x] **procedural_canyon**: 양쪽 절벽 + 중앙 통로 구조, 크레이터 장애물, 텍스처 일치
- [x] 3개 scene 모두: GUI 패널 (tau/sun) 정상, dynamic atmosphere 정상

---

## Stage 4 완료 요약

**완료일:** 2026-04-16
**상태:** Canyon 시나리오 3종 구현 및 검증 완료

### 검증된 전체 Scenario (7개)

| # | Scenario | Config | 소스 | 특징 |
|---|----------|--------|------|------|
| 1 | Basic Mars (Flat) | `jezero_flat.yaml` | HiRISE Jezero | dz=3m, 바위 없음 |
| 2 | Rock-Dense | `jezero_rocks.yaml` | HiRISE Jezero | k=0.08, 대형 바위 |
| 3 | Crater+Slopes | `jezero_crater.yaml` | HiRISE Jezero | dz=12.6m, max slope 30° |
| 4a | Canyon Challenge | `cerberus_canyon.yaml` | HiRISE Cerberus | dz=460m, trav 43% |
| 4b | Canyon Easy | `cerberus_canyon_easy.yaml` | HiRISE Cerberus | dz=110m, trav 82% |
| 4c | Canyon Corridor | `procedural_canyon.yaml` | Procedural | 양벽+통로, dz=50m |
| - | Procedural Crater | `mars_env.yaml` | Procedural | 256x256, crater preset |

### 테스트 결과 누적

- Unit tests: 233 passed
- black/ruff: all passed
- Isaac Sim GUI: 7개 scene + interactive panel 시각 검증 완료

---

## [2026-04-16] Scenario 5: Mars Cave (Lava Tube) 절차적 생성

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** marslab/terrain/, marslab/config/, scripts/phase1/
**Type:** Feature (Scenario 5 -- 3D cave mesh generation)

---

### 과학적 근거

`work_log/scene_generation/mars_cave.md` (536줄, 30+ peer-reviewed 출처) 기반.
핵심 파라미터:

| 파라미터 | 값 | 출처 |
|---------|-----|------|
| 통로 폭 | 80--300 m (mode 200 m) | Sauro 2020 |
| 높이 비율 | W:H = 2:1 ~ 3:1 (half-ellipse) | Blair 2017, Theinat 2020 |
| 천장 두께 | 30--80 m | Sauro 2018, Theinat 2020 |
| Skylight 직경 | 30--250 m (mode 100 m) | Cushing 2007/2012 |
| Breakdown 블록 | LogNormal(mean=0.5m, sigma=0.3) | Blank 2024 (BRAILLE) |
| 벽 albedo | 0.05--0.15 (매우 어두운 현무암) | Rodriguez 2021 |

### 기술적 결정: Cross-Section Sweep

동굴은 같은 (x,y)에 z값이 2개 필요 (바닥 + 천장) -> **2D heightmap 불가** -> 3D 메시 필요.

접근법 비교:
- **A. Cross-section sweep (채택)**: 기존 의존성만 사용, UV 자연 생성
- B. Dual heightmap: 수직/오버행 벽 불가 -> 불가
- C. SDF + marching cubes: scikit-image 의존, 128M voxel 메모리, UV 어려움 -> 과잉

### 계획 (plan: `~/.claude/plans/parallel-popping-shell.md`)

1. CaveConfig 스키마 추가 (schema.py)
2. cave_generator.py Layer 1 (offline mesh generation)
3. test_cave_generator.py 단위 테스트
4. visualize_cave.py 오프라인 시각화
5. cave_mesh_builder.py Layer 2 (USD 변환)
6. material_applicator.py 확장 + run_stage2.py 통합 + YAML

---

### Step 1 -- CaveConfig 스키마

**파일:** `marslab/config/schema.py`

`CaveConfig(BaseModel)` 추가 -- 20개 필드, 모두 과학적 근거 기반 제약:
- `tube_width_m` (80--300), `tube_height_ratio` (0.25--0.6)
- `cross_section_noise` (0--0.4), `ceiling_thickness_m` (20--100)
- `skylight_count` (0--2), `skylight_diameter_m` (30--250)
- `breakdown_coverage_pct` (0--80), `wall_albedo_range`
- `ring_resolution`, `path_resolution` (mesh density)

`TerrainConfig`에 `cave: CaveConfig | None = None` 필드 추가.

### Step 2 -- cave_generator.py (Layer 1, offline)

**파일:** `marslab/terrain/cave_generator.py` (~550줄)

P3 원칙: Isaac Sim 의존 없음. 순수 numpy + scipy + trimesh.

핵심 함수:
- `_generate_centerline()`: sinusoidal 경로 (canyon centerline 패턴 재사용)
- `_generate_cross_sections()`: half-ellipse + Gaussian-filtered noise
- `_tangent_frames()`: Frenet-like frame (tangent, normal, binormal)
- `_build_tube_shell()`: ring stacking, **역방향 winding** (내향 노멀)
- `_build_tube_floor()`: 하단 vertex strip, CCW winding (상향 노멀)
- `_build_skylight_shaft()`: 수직/오버행 원통, overhang angle 지원
- `_build_debris_cone()`: 안식각 30도 원뿔, skylight 하단 배치
- `_build_surface_cap()`: flat terrain + skylight 구멍 (centroid filtering)
- `_generate_breakdown_positions()`: LogNormal 분포, rejection sampling
- `generate_cave_mesh()`: 공개 API, dict 반환

Z 정규화: tube floor = z=0, surface = z=(ceiling_thickness + tube_height).

### Step 3 -- 단위 테스트

**파일:** `tests/unit/test_cave_generator.py` (33 tests)

카테고리:
- 출력 구조 (return_keys, mesh_types, surface_elevation_shape)
- 데이터 무결성 (no_nan x3, face_indices_valid x3)
- 치수 검증 (bounding_box_width, tube_height, surface_z, floor_z)
- 법선 방향 (floor_normals_upward, tube_normals_inward)
- Skylight (count, shaft_depth, surface_hole, no_skylight_variant)
- Debris/Breakdown (cone_exists, cone_apex, positions, keys, zero_coverage)
- Seed (determinism, different_seeds_differ)
- 파라미터 변형 (narrow_tube, wide_tube, two_skylights, high_breakdown, no_debris)
- 메타데이터 (keys, values)

### Step 4 -- 오프라인 시각화

**파일:** `scripts/visualize_cave.py`

4-panel matplotlib:
1. Plan view (XY) -- tube footprint, skylight 원, breakdown 위치
2. Cross-section (mid-tube) -- 천장/바닥 프로파일
3. Longitudinal section -- tube 축 방향 종단면
4. 3D wireframe -- subsampled point cloud

결과: `work_log/scene_generation/cave_preview.png` 생성 완료.
OBJ export도 지원 (`--export-obj` 플래그).

### Step 5 -- cave_mesh_builder.py (Layer 2, USD)

**파일:** `marslab/terrain/cave_mesh_builder.py`

- `_trimesh_to_usd_prim()`: trimesh -> UsdGeom.Mesh 변환 (collision, UV, semantic label)
- `build_cave_scene()`: /World/Cave/{Surface, Tube, Floor, Skylight_N, DebrisCone_N, Breakdown}
- `_build_breakdown_instancer()`: PointInstancer + icosphere prototype + dark basalt material

### Step 6 -- Material + run_stage2.py 통합 + YAML

**material_applicator.py 확장:**
- `apply_cave_material()`: 어두운 현무암 PBR (회흑색, roughness 0.85)
- 색상: `[albedo * 1.2, albedo * 1.0, albedo * 0.9]` (적갈색 아님 -- 산화 안 된 내부 현무암)

**run_stage2.py 통합:**
- `load_terrain_elevation()`: `preset == "cave"` 분기 -> `generate_cave_mesh()` 호출
- `main()`: cave 분기:
  - `build_cave_scene()` 대신 `build_terrain_mesh()` 호출
  - `apply_cave_material()` -> Tube, Floor, Skylight prims
  - `apply_terrain_material()` -> Surface prim (기존 Mars 텍스처)
  - Cave 조명: RectLight at skylight (butterscotch 색) + SphereLights inside tube (v1.0 임시)
  - 기존 Scenario 1-4 파이프라인 보존 (else 분기)

**시나리오 YAML:**
- `configs/scenarios/cave_lava_tube.yaml` (MARS-LT-B 변형)
  - terrain: procedural, preset=cave, 400x400, seed=42
  - cave: width=200, ceiling=50, 1 skylight, 25% breakdown
  - rendering: sun=0, dome=0, fog=0 (동굴 내부)

### 디버그 이슈 및 수정

1. **F841 unused `half_len`**: `cave_generator.py`에서 ruff 경고, 삭제
2. **`rng.uniform(lo, hi)` ValueError**: `left_x`가 음수일 때 `left_x * 0.8 > right_x * 0.8` 가능. `min/max` 적용으로 수정
3. **F841 unused `domain_center_x/y`**: test에서 ruff 경고, 삭제
4. **Unused import `Vt` + variable `proto_container`**: `cave_mesh_builder.py`에서 ruff 경고, 수정

---

### 파일 변경 목록

| 파일 | 작업 | 설명 |
|------|------|------|
| `marslab/config/schema.py` | 수정 | CaveConfig 추가, TerrainConfig에 cave 필드 |
| `marslab/terrain/cave_generator.py` | **신규** | Layer 1: 동굴 메시 생성 (~550줄, offline) |
| `marslab/terrain/cave_mesh_builder.py` | **신규** | Layer 2: trimesh -> USD prim 변환 |
| `marslab/terrain/material_applicator.py` | 수정 | apply_cave_material() 추가 |
| `scripts/phase1/run_stage2.py` | 수정 | cave 분기 (elevation + scene build + lighting) |
| `configs/scenarios/cave_lava_tube.yaml` | **신규** | Scenario 5 기본 설정 |
| `scripts/visualize_cave.py` | **신규** | 4-panel 오프라인 시각화 |
| `tests/unit/test_cave_generator.py` | **신규** | 33 단위 테스트 |

### 검증된 전체 Scenario (8개)

| # | Scenario | Config | 소스 | 특징 |
|---|----------|--------|------|------|
| 1 | Basic Mars (Flat) | `jezero_flat.yaml` | HiRISE Jezero | dz=3m, 바위 없음 |
| 2 | Rock-Dense | `jezero_rocks.yaml` | HiRISE Jezero | k=0.08, 대형 바위 |
| 3 | Crater+Slopes | `jezero_crater.yaml` | HiRISE Jezero | dz=12.6m, max slope 30° |
| 4a | Canyon Challenge | `cerberus_canyon.yaml` | HiRISE Cerberus | dz=460m, trav 43% |
| 4b | Canyon Easy | `cerberus_canyon_easy.yaml` | HiRISE Cerberus | dz=110m, trav 82% |
| 4c | Canyon Corridor | `procedural_canyon.yaml` | Procedural | 양벽+통로, dz=50m |
| **5** | **Cave (Lava Tube)** | **`cave_lava_tube.yaml`** | **Procedural** | **3D mesh, skylight, breakdown** |
| - | Procedural Crater | `mars_env.yaml` | Procedural | 256x256, crater preset |

### 테스트 결과 누적

- Unit tests: **266 passed** (233 + 33 cave tests)
- black/ruff: all passed
- Isaac Sim GUI: Scenario 5 사용자 시각 검증 대기

---

## [2026-04-16] Scenario 5 후속 수정 — Isaac Sim 런타임 버그 수정

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/, marslab/config/
**Type:** Bugfix (Scenario 5 초기 실행 시 런타임 오류 3건)

---

### 사용자 보고

Isaac Sim에서 `cave_lava_tube.yaml`로 첫 실행 시 3건의 런타임 오류 발생.

### 버그 1: wall_albedo_range TypeError

```
TypeError: generate_cave_mesh() got an unexpected keyword argument 'wall_albedo_range'
```

- **원인**: `run_stage2.py`에서 `**cave_cfg`로 모든 cave 파라미터를 언패킹할 때,
  `wall_albedo_range`는 material 전용 파라미터인데 mesh generator에도 전달됨
- **수정**: `geom_cfg = {k: v for k, v in cave_cfg.items() if k != "wall_albedo_range"}`
  로 필터링 후 `generate_cave_mesh(**geom_cfg)` 호출
- **파일**: `scripts/phase1/run_stage2.py`

### 버그 2: SdfPath 마이너스 부호 오류

```
Ill-formed SdfPath </World/Cave/InteriorLight_0_-60>
```

- **원인**: 동굴 내부 조명 prim 이름에 음수 elevation 값 `-60`이 포함되어
  USD SdfPath 규칙 위반 (경로 세그먼트에 `-` 불가)
- **수정**: 순차 인덱스 (`InteriorLight_0`, `InteriorLight_1`, ...) 로 교체
- **파일**: `scripts/phase1/run_stage2.py`

### 버그 3: Pydantic ValidationError (sun=0, dome=0)

```
pydantic.ValidationError: sun_intensity_scale=0 (ge=0.1 위반)
pydantic.ValidationError: dome_brightness_scale=0 (ge=1.0 위반)
```

- **원인**: 초기 설계에서 동굴 내부 조명을 sun=0, dome=0으로 설정했으나,
  `schema.py`의 `RenderingConfig`에 `ge=0.1`, `ge=1.0` 제약이 있음
- **수정 (임시)**: ge 제약을 ge=0.0으로 완화
- **후속**: 자연광 전환 (아래 섹션) 후 ge 제약 원복
- **파일**: `marslab/config/schema.py`

---

### 수정 파일 목록

| 파일 | 변경 | 사유 |
|------|------|------|
| `scripts/phase1/run_stage2.py` | wall_albedo_range 필터 + SdfPath 인덱싱 | 런타임 오류 2건 |
| `marslab/config/schema.py` | sun/dome ge 제약 임시 완화 | Pydantic 검증 오류 |

---

## [2026-04-16] Scenario 5 후속 수정 — 자연광 전환

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** scripts/phase1/, marslab/config/, configs/scenarios/
**Type:** Refactor (동굴 조명 방식 변경)

---

### 사용자 요청

> "태양은 다른 scene들과 마찬가지로 떠있고, 동굴만 벽면으로 가려지고 중간중간
> 일부 구멍을 뚫어서 햇빛 일부만 들어오게 만드는 식으로 구현해."

### 기존 방식의 문제

- sun=0, dome=0, fog=0으로 모든 자연광 비활성화
- RectLight (skylight 입구) + SphereLight (동굴 내부) 인공 조명으로 대체
- **결과**: 씬 전체가 너무 어두워 시각적 확인 불가

### 변경 방향

- sun/sky/fog를 다른 scenario와 **동일하게** 유지 (sun=30, dome=5000, fog=0.002)
- **동굴 geometry가 물리적으로 빛을 차단** -- path tracing에서 자연스러운 차광
- skylight 구멍으로만 자연광이 동굴 내부에 도달
- 모든 인공 조명 (RectLight, SphereLight) 완전 제거

### 변경 내용

**`scripts/phase1/run_stage2.py`:**
- RectLight 생성 코드 (~20줄) 제거
- SphereLight 생성 코드 (~15줄) 제거
- "# Natural light from sun/sky enters through skylight holes" 주석으로 대체
- 동적 대기 (sun sweep + tau) 활성화 -- cave도 다른 scenario와 동일 물리

**`marslab/config/schema.py`:**
- `sun_intensity_scale` ge 제약: ge=0.0 → ge=0.1 (원복)
- `dome_brightness_scale` ge 제약: ge=0.0 → ge=1.0 (원복)

**`configs/scenarios/cave_lava_tube.yaml`:**
- rendering 섹션: sun=30.0, dome=5000.0, fog=0.002 (기존 scenario와 동일)
- dynamic_atmosphere: enabled=true, tau_profile="constant", base_tau=0.3

### 수정 파일 목록

| 파일 | 변경 | 사유 |
|------|------|------|
| `scripts/phase1/run_stage2.py` | 인공 조명 제거, dynamic atmosphere 적용 | 자연광 전환 |
| `marslab/config/schema.py` | ge 제약 원복 | 자연광으로 sun>0 필요 |
| `configs/scenarios/cave_lava_tube.yaml` | rendering 값 변경 | 다른 scenario와 일치 |

### 시각 검증

- [x] 동굴 외부 지표면: 일반 Mars scene과 동일한 밝기
- [x] 동굴 내부: geometry 차단으로 어두움, skylight 구멍에서 빛줄기 진입
- [x] 동적 대기: 태양 위치 변화에 따라 skylight 빛줄기 방향 변화

---

## [2026-04-16] Scenario 5 후속 수정 — Skylight 소형화 (1×100m → 10×20m)

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** marslab/config/, marslab/terrain/, configs/scenarios/, tests/unit/
**Type:** Enhancement (skylight 개수/크기 재조정)

---

### 사용자 요청

> "큰 구멍 하나에서 한번에 빛이 들어오는 것은 시각적으로 별로.
> 차라리 작은 구멍을 10개 정도 뚫어서 빛이 들어오게 하는게 현실적."

### 과학적 근거

실제 화성 lava tube에는 ceiling collapse로 인한 다수의 소규모 개구부 존재.
Cushing (2007/2012): skylight 직경 30-250m 분포, 하나의 tube에 여러 개 발생 가능.

### 변경 내용

**`marslab/config/schema.py` — CaveConfig 제약 완화:**
- `skylight_count`: default=1 le=2 → **default=10 le=20**
- `skylight_diameter_m`: default=100 ge=30 → **default=20 ge=5**

**`marslab/terrain/cave_generator.py` — 겹침 방지 로직:**
- `_compute_skylight_positions()`: 기존 `count+1` 등분 배치는 유지
- **신규**: 인접 skylight 간 최소 거리 = `diameter * 1.5` 체크
- 400m domain에 20m diameter × 10개 → 간격 ~36m, 겹침 없음

**`configs/scenarios/cave_lava_tube.yaml`:**
- `skylight_count: 10`
- `skylight_diameter_m: 20.0`

**`tests/unit/test_cave_generator.py`:**
- `test_two_skylights` → `test_many_skylights` (count=10, large domain)
- `test_skylight_no_overlap` 신규 추가 (모든 skylight 쌍 간 거리 검증)
- `test_skylight_count_default`: 기대값 1 → `>= 1` (small domain에서 10개 미만 가능)

### 수정 파일 목록

| 파일 | 변경 | 사유 |
|------|------|------|
| `marslab/config/schema.py` | skylight 제약 완화 | 10개 소형 허용 |
| `marslab/terrain/cave_generator.py` | 겹침 방지 로직 추가 | 다수 skylight 안전 배치 |
| `configs/scenarios/cave_lava_tube.yaml` | count=10, diameter=20 | YAML 업데이트 |
| `tests/unit/test_cave_generator.py` | 테스트 업데이트 + 신규 | 겹침 검증 |

### 시각 검증

- [x] 10개 소형 skylight이 centerline을 따라 분산 배치
- [x] 각 skylight에서 가느다란 빛줄기가 동굴 내부로 진입
- [x] 시각적으로 자연스러운 조명 패턴 (큰 구멍 1개 대비 개선)

---

## [2026-04-16] Scenario 5 후속 수정 — Cave 내부 장식물 조정

**Week:** Wk 2 (Apr 14 -- Apr 20)
**Module:** marslab/config/, marslab/terrain/, configs/scenarios/, tests/unit/, scripts/
**Type:** Enhancement (debris cone 독립 배치 + rock 감소 + 로버 통행 보장)

---

### 사용자 요청

> "원뿔 형상 구조물은 5개로 줄이고 동굴 내부 랜덤 배치.
> 빨간 점(rock)도 대폭 줄이고 크기 키워. 로버 통행 길은 보장."

### 기존 문제

1. **Debris cone 10개**: 각 skylight 하단에 1:1 종속 → 부자연스러움
2. **Rock 2719개**: `rock_sfd_k=0.005`, diameter [0.10, 1.0]m → 과다, 적갈색 점
3. **로버 통행 경로**: centerline 근처에도 장애물 무차별 배치

### 변경 내용

**1. Debris cone skylight 분리 (`cave_generator.py`):**
- `generate_cave_mesh()` 시그니처: `debris_cone_count: int = 5` 파라미터 추가
- Section 7 (debris cones) 전면 재작성:
  - 기존: `for sx, sy in skylight_positions: _build_debris_cone(sx, sy, ...)`
  - 변경: centerline station 랜덤 선택 → perpendicular offset → cone 배치
- cone 크기: `tube_width_m * 0.15` 고정 (skylight diameter 연동 제거)
- 각 cone center: centerline에서 tube_width의 20-35% offset (centerline 자체 비워둠)

**2. Rock 감소 (`cave_lava_tube.yaml`):**
- `rock_sfd_k`: 0.005 → **0.001** (바위 수 대폭 감소)
- `rock_diameter_range`: [0.10, 1.0] → **[0.5, 3.0]** (소수 대형 바위)

**3. Centerline exclusion zone (`cave_generator.py`):**
- tube_width의 10% 양쪽 = 클리어 존 (200m tube → 좌우 20m = 40m 통로)
- Debris cone: `offset >= exclusion_half` 보장
- `_generate_breakdown_positions()`: `if abs(local_x) < widths[station_idx] * 0.1: continue`

**4. Schema (`schema.py`):**
- `debris_cone_count: int = Field(default=5, ge=0, le=20)` 필드 추가
- `debris_cone_present: bool` 유지 (False면 count 무시)

**5. 테스트 (`test_cave_generator.py`):**
- `test_no_skylight_variant`: debris cone이 skylight과 독립 → `len >= 1`로 변경
- `test_debris_cone_avoids_centerline` 신규 추가 (large domain에서 cone ≥ 1 확인)

**6. 시각화 (`visualize_cave.py`):**
- `--skylight-diameter`, `--debris-cone-count` CLI 인자 추가
- 기본값: skylight-count=10, skylight-diameter=20, debris-cone-count=5
- Plan view에 debris cone 위치를 darkorange 삼각형 마커로 표시

### 수정 파일 목록

| 파일 | 변경 | 사유 |
|------|------|------|
| `marslab/config/schema.py` | `debris_cone_count` 필드 추가 | 개수 분리 제어 |
| `marslab/terrain/cave_generator.py` | debris cone 배치 분리 + exclusion zone | skylight 독립 + 통행 보장 |
| `configs/scenarios/cave_lava_tube.yaml` | cone=5, k=0.001, diameter=[0.5,3.0] | 파라미터 조정 |
| `tests/unit/test_cave_generator.py` | 테스트 수정 + 신규 | 독립 cone + exclusion 검증 |
| `scripts/visualize_cave.py` | CLI 인자 + cone 마커 | 시각화 최신화 |

### 테스트 결과

```
black --check: passed (83 files)
ruff check: passed
pytest tests/unit/ -v: 268 passed, 0 failed (266 + 2 신규/수정)
```

### 시각 검증 (오프라인)

산출물: `work_log/scene_generation/cave_preview_v3.png`
- [x] 10개 소형 skylight (gold 원) centerline 따라 분산
- [x] 5개 debris cone (orange 삼각형) centerline 회피하여 tube 내부 랜덤
- [x] breakdown blocks centerline 클리어 존 유지
- [x] Isaac Sim 시각 검증 완료 (사용자 확인, 2026-04-17)

---

## Scenario 5 최종 완료 요약

**완료일:** 2026-04-17
**상태:** 초기 구현 + 4차 반복 수정 + Isaac Sim 시각 검증 **완료**

### 최종 파라미터

| 카테고리 | 파라미터 | 값 |
|----------|---------|-----|
| Tube | width, height, direction, ceiling | 200m, 100m, 45°, 50m |
| Skylights | count, diameter, depth, overhang | 10개, 20m, 90m, 5° |
| Debris cones | count, 배치 방식 | 5개, centerline 회피 랜덤 |
| Rocks | k, diameter range | 0.001, [0.5, 3.0]m |
| Breakdown | coverage, block mean, sigma | 25%, 0.5m, 0.3 |
| Lighting | 방식 | 자연광 (geometry 차단), dynamic_atmosphere |
| Rover passage | exclusion zone | centerline ±10% tube_width |

### 반복 수정 이력

| 차수 | 변경 | 트리거 |
|------|------|--------|
| 초기 | 3D cave mesh (cross-section sweep) | 계획 |
| 1차 | 런타임 버그 3건 수정 | Isaac Sim 실행 오류 |
| 2차 | 인공 조명 → 자연광 전환 | 씬 너무 어두움 |
| 3차 | Skylight 1×100m → 10×20m | 큰 구멍 부자연스러움 |
| 4차 | Debris cone 독립 + rock 감소 + exclusion | 과다 장식물 + 통행 |

### 검증된 전체 Scenario (8개)

| # | Scenario | Config | 소스 | 특징 |
|---|----------|--------|------|------|
| 1 | Basic Mars (Flat) | `jezero_flat.yaml` | HiRISE Jezero | dz=3m, 바위 없음 |
| 2 | Rock-Dense | `jezero_rocks.yaml` | HiRISE Jezero | k=0.08, 대형 바위 |
| 3 | Crater+Slopes | `jezero_crater.yaml` | HiRISE Jezero | dz=12.6m, max slope 30° |
| 4a | Canyon Challenge | `cerberus_canyon.yaml` | HiRISE Cerberus | dz=460m, trav 43% |
| 4b | Canyon Easy | `cerberus_canyon_easy.yaml` | HiRISE Cerberus | dz=110m, trav 82% |
| 4c | Canyon Corridor | `procedural_canyon.yaml` | Procedural | 양벽+통로, dz=50m |
| **5** | **Cave (Lava Tube)** | **`cave_lava_tube.yaml`** | **Procedural** | **10 skylights, 5 cones, exclusion** |
| - | Procedural Crater | `mars_env.yaml` | Procedural | 256x256, crater preset |

### 테스트 결과 누적

- Unit tests: **268 passed** (233 기존 + 35 cave tests)
- black/ruff: all passed
- Isaac Sim GUI: Scenario 5 사용자 시각 검증 **완료** (2026-04-17)

---

## Scene Generation 전체 완료 선언

**완료일:** 2026-04-17

Scenario 1-5 (Cave 포함) 전체 scene 파이프라인 구현 및 시각 검증 완료.
다음 단계: 로버 + scene 통합 (별도 세션에서 진행).

Scenario 6 (Spacecraft), 7 (Mars Base)은 사실적 3D 에셋 소싱 후 별도 진행.
