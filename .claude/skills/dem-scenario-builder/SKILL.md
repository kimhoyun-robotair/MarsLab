---
name: dem-scenario-builder
description: "MarsLab HiRISE DEM crop → rock placement → scenario YAML 생성 파이프라인. Jezero plain/rim/delta crop, Golombek SFD 기반 암석 배치(10% 오차), Blender mesh 통합, structure_loader로 OBJ/USD 에셋 배치, scenario별 YAML 작성. 'scenario 추가', 'scenario {N} 만들어줘', 'DEM 교체', 'rock 밀도 조정', 'cave 배치', 'spacecraft 배치', 'mars base 추가', 'crater 시나리오 다시', 'canyon scenario' 등의 요청에 반드시 사용."
---

# dem-scenario-builder — MarsLab Scenario YAML 생성 파이프라인

MarsLab의 7개 mission scenario(Basic Mars, Rock-Dense, Crater+Slopes, Canyon, Cave, Spacecraft Landing, Mars Base) YAML을 일관되게 생성·검증·시각화하는 워크플로우.

## Why this matters
각 scenario는 DEM 크롭, 암석 SFD, 조명, 에셋 배치, 로버 스폰을 일관된 YAML로 표현해야 한다. Python에 하드코딩하면 G5 위반이고, scenario 간 비교·재현이 어려워진다. 이 스킬은 7개 scenario를 동일한 패턴으로 빠르게 생성하고 오프라인 시각화로 검증한다.

## Scenario YAML 표준 구조

```yaml
# configs/scenarios/{name}.yaml
scenario:
  name: "basic_mars"
  description: "Jezero plain crop, baseline Mars surface"
  seed: 42

terrain:
  source: "dem"            # dem | procedural | hybrid
  dem:
    file: "assets/terrain/dem/jezero_plain_5m.tif"
    crop_extent_m: [0, 0, 200, 200]
    resolution_m: 0.5
  rock_placement:
    enabled: true
    sfd:
      model: "golombek_2008"
      k: 0.05               # SFD intensity (Wk2 rock_dense uses 0.10)
      diameter_range_m: [0.05, 1.5]
    seed: 1234

assets:
  structures: []           # canyon/cave/spacecraft/mars_base scenarios에서 사용
  rocks_mesh_lod: 2

lighting:
  sun:
    azimuth_deg: 135
    elevation_deg: 45
    sweep: false
  sky:
    tau: 1.0
    sweep: false
  domelight:
    enabled: true           # cave scenario에서는 false

robot:
  spawn:
    x: 100.0
    y: 100.0
    z: null                 # null = 지형 위 자동 안착
    yaw_deg: 0
```

## 워크플로우

### Step 1: 입력 수집
1. PLAN.md §5.3에서 해당 scenario의 요구사항 확인 (어느 주차, 어떤 특성)
2. 기존 scenario YAML이 있으면 Read해서 패턴 차용
3. 사용자에게 필요한 입력 확인:
   - DEM 경로(또는 procedural)
   - 특수 에셋(Blender mesh) 경로
   - rock SFD intensity 의도

### Step 2: DEM crop 및 검증 (오프라인)
- `marslab/terrain/dem_loader.py`로 DEM 로딩, 메타데이터(해상도·범위) 확인
- crop 영역이 DEM 경계 내부인지 검증
- `_workspace/{wk}_terrain_{scenario}_dem.png`에 heightmap 시각화
- 평탄도(slope distribution) 통계 산출 → 로버 스폰 위치 추천

### Step 3: Rock placement (오프라인)
- `marslab/terrain/rock_placer.py`로 Golombek SFD 기반 무작위 배치 (seed 고정)
- 결과를 matplotlib scatter plot으로 `_workspace/{wk}_terrain_{scenario}_rocks.png` 저장
- 통계 검증: 직경 분포가 Golombek 식 ±10% 이내인가
- 실패 시 SFD 파라미터 조정

### Step 4: 구조물 배치 (Canyon/Cave/Spacecraft/Mars Base만)
- `marslab/terrain/structure_loader.py`(Wk4 신규)로 OBJ/USD 메시 메타데이터 로드
- 배치 좌표·회전 계산은 순수 파이썬에서, Isaac Sim 의존 부분만 별도 함수
- `trimesh`로 scene 합성 → `_workspace/{wk}_terrain_{scenario}_assets.png`

### Step 5: YAML 작성 및 스키마 검증
- 표준 구조 따라 `configs/scenarios/{name}.yaml` 작성
- pydantic 스키마로 검증 (`marslab/config/schema.py` 의 ScenarioConfig 모델)
- `tests/unit/test_scenario_{name}.py` 추가 — YAML 로딩·필드 존재·범위 검증

### Step 6: 사용자 시각 확인
- 위 PNG 3종(heightmap, rocks, assets)을 사용자에 공유
- "이대로 진행할까요?" 확인 후 진행 (user review gate G10)

### Step 7: Isaac Sim 통합 검증 (사용자 직접 실행)
- 사용자에게 `scripts/run_scene.py --scenario {name}` 실행 요청
- 확인 항목: 로딩 성공, 시각적 오류 없음, IMU 중력 3.72±0.05
- 결과를 `_workspace/{wk}_terrain_{scenario}_isaac_log.md`에 기록

## 7개 Scenario 작성 순서 (PLAN.md §5.3 매핑)

| Scenario | 주차 | 핵심 특성 |
|---------|------|---------|
| basic_mars | Wk2 | Jezero plain, 평탄, baseline |
| rock_dense | Wk2 | rock_sfd_k=0.10 |
| crater_slopes | Wk2 | Jezero rim/delta, 슬로프 |
| canyon | Wk4 | structure_loader + Blender mesh |
| cave | Wk5 | DomeLight off, PointLight 모드 |
| spacecraft | Wk5 | 착륙선 3D 모델 |
| mars_base | Wk5 | 거주지/태양광 패널 |

## 안전 원칙
- DEM·메시 파일은 `assets/terrain/`에 두고, 교체 시 archive/로 이동(삭제 금지).
- 모든 무작위 함수에 `seed` 명시(G7 reproducibility).
- OmniLRS의 함수명·변수명 차용 금지(G3). 알고리즘만 참조.
- Isaac Sim integration은 사용자 직접 실행. 오프라인 PNG로 먼저 검증.

## 후속 작업 키워드
"scenario X 다시", "DEM 교체", "rock 밀도 조정", "암석 재배치", "scenario YAML 수정", "에셋 배치 수정" 후속 요청에도 사용. 이전 `_workspace/{wk}_terrain_*` 결과를 Read로 비교.

## 테스트 프롬프트
1. "Scenario rock_dense 만들어줘. SFD k=0.10."
2. "Canyon scenario에 새 Blender mesh 적용."
3. "Cave scenario lighting 다시 — DomeLight 꺼지고 PointLight 켜지는지 확인."
