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
