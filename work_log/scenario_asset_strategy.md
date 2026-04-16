# Scenario 4-7 Asset Sourcing Strategy

**Date:** 2026-04-16
**Purpose:** Scenario 4-7 (Canyon, Cave, Spacecraft, Mars Base)의 과학적 근거 및 에셋 확보 전략
**Status:** Research complete, implementation pending

---

## Scenario 4: Canyon (협곡)

### 과학적 근거

화성 협곡은 크게 세 유형:
- **Valles Marineris** — 길이 4,000km, 깊이 7km, 폭 200km. 로버 스케일에 너무 거대하나, 내부 소규모 구간 crop 가능
- **Grabens (Fossae)** — 좁은 지구조 균열. 폭 1-2km, 깊이 100-200m. 로버 시나리오에 최적
- **Outflow channel margins** — Kasei Valles, Ares Vallis. 침식된 협곡 벽 50-200m

### 접근법: 실제 HiRISE DEM 사용

기존 Jezero DEM과 동일한 파이프라인 (`dem_loader.py` -> `crop_dem()` -> `mesh_builder.py`)으로 처리.

### HiRISE DTM 후보

| 순위 | 지역 | Product ID (근사) | 위치 | 폭 | 깊이 | 적합성 |
|------|------|-------------------|------|-----|------|--------|
| **1** | **Cerberus Fossae** | DTEEC_023957_1845_* | ~4.5N, 160.5E | 1-2 km | 100-200 m | **최적** — 512x512 crop으로 양쪽 벽+바닥 동시 캡처 |
| 2 | Coprates Chasma | DTEEC_006747_1665_* | ~13.0S, 295.7E | ~60 km | ~7 km | 좋음 — 측면 지류 crop 시 로버 스케일 가능 |
| 3 | Juventae Chasma | DTEEC_003179_1755_* | ~4.2S, 297.5E | ~30 km | ~5 km | 좋음 — 내부 퇴적층 마운드가 지형 다양성 제공 |

**Cerberus Fossae를 1순위로 추천하는 이유:**
- 폭 1-2km → 1m/px 해상도에서 512x512 crop이 자연스럽게 양쪽 벽 포함
- 화산 용암류 위의 graben → 바닥이 비교적 평탄하여 로버 통행 가능
- 잘 연구된 지역 (Vaucher et al. 2009, Berman & Hartmann 2002)

### 다운로드 절차

1. `https://www.uahirise.org/dtm/` 에서 "Cerberus Fossae" 검색
2. GeoTIFF DTM 다운로드 (또는 PDS ODE: `https://ode.rsl.wustl.edu/mars/`)
3. `assets/terrain/dem/cerberus_fossae.tif` 에 저장
4. `scripts/convert_dem.py` 로 변환 → `assets/terrain/dem/cerberus_fossae_converted/`

### 사용자 확인 필요사항

- [ ] Product ID가 실제 PDS에서 유효한지 웹 확인 (`uahirise.org/dtm/`)
- [ ] DEM 파일 크기 확인 (수 GB 가능, crop만 필요)
- [ ] Cerberus Fossae vs Coprates Chasma 최종 선택

### 참고 논문

- Andrews-Hanna (2012): Valles Marineris 형성 메커니즘
- Mege & Masson (1996): Mars tectonic grabens 치수
- Okubo et al. (2009): HiRISE canyon wall 노출 층리 관측
- Vaucher et al. (2009): Cerberus 지역 화산 지형 형태학

---

## Scenario 5: Cave (동굴 / 용암 터널)

### 과학적 근거

**핵심 논문: Sauro et al. (2020), Earth-Science Reviews, 209, 103288**

화성 용암 터널은 저중력(0.38g)으로 지구보다 2-3배 큰 규모 가능. 중력 스케일링: `W_mars = W_earth x (g_earth / g_mars) = W_earth x 2.64`

#### 치수 범위

| 파라미터 | 지구 (실측) | 화성 (추정) | 출처 |
|----------|------------|------------|------|
| 터널 폭 | 5-30m | 15-80m (최대 ~250m 이론) | Sauro et al. 2020 |
| 터널 높이 | 3-15m | 8-40m (최대 ~100m) | Sauro et al. 2020 |
| 폭:높이 비 | 2:1 ~ 3:1 | 2:1 ~ 3:1 (보존) | Sauro et al. 2020 |
| 터널 길이 | 100m ~ 65km | 수십-수백 km 가능 | Sauro et al. 2020 |
| Skylight 직경 | N/A | 50-250m (관측) | Cushing 2007, 2012 |
| Skylight 깊이 | N/A | 70-130m (관측) | Cushing et al. 2007 |

#### 알려진 화성 동굴 후보

| 지역 | 후보 수 | Skylight 직경 | 비고 |
|------|---------|-------------|------|
| **Arsia Mons** | 7 확인 + 30+ 후보 | 100-252m | 가장 잘 연구됨 |
| Olympus Mons | 10-15 후보 | 50-200m | 측면 용암 채널 가시 |
| Elysium Planitia | 5-10 후보 | 50-150m | Cerberus Fossae 인근 |
| Pavonis Mons | 수 개 | 80-200m | 중앙 Tharsis |

#### 동굴 내부 환경

| 조건 | 값 | 비고 |
|------|-----|------|
| 조명 | 완전 암흑 (skylight 구역 제외) | DomeLight OFF, 로버 헤드라이트만 |
| 온도 | 안정적 -20 ~ -30 C | 주야 변동 차단 (Wynne et al. 2008) |
| 대기 | 지표와 동일 (CO2 95.3%, 610 Pa) | 밀봉되지 않음 |
| 바람 | 0 m/s | 풍성 운반 없음 |
| 바닥 암석 | Skylight 근처 CFA 30-60%, 중간부 CFA 5-15% | 붕락 잔해 vs 용암류 바닥 |
| GPS | 불가 | LiDAR SLAM 필수 |

#### 단면 형태

- **천장:** 포물선 아치형 (parabolic arch) — 가장 보편적
- **바닥:** 평탄 (고화된 용암류) + 약간의 undulation
- **벽:** 수평 용암 흐름 자국 (bathtub ring), 용암 선반(ledge)

### 에셋 전략: Blender 제작

동굴은 2D heightmap으로 표현 불가 (천장 존재) → 3D 메시 필수.

#### v1.0 Blender 제작 사양

| 파라미터 | 값 | 근거 |
|----------|-----|------|
| **터널 폭** | 40m (28-52m 변동) | 화성 추정 중간값 |
| **터널 높이** | 20m (15-25m 변동) | 폭:높이 2:1 |
| **단면** | 포물선 아치 천장 + 평탄 바닥 | Sauro et al. canonical form |
| **길이** | 200-300m | SLAM/Nav2 테스트 충분 |
| **Skylight 직경** | 100-150m | Cushing 관측 중간값 |
| **Skylight 깊이** | 80m | 관측 범위 내 |
| **바닥 거칠기** | 10-30cm RMS | 로버 통행 가능하되 센서 특징 제공 |
| **벽 거칠기** | 5-15cm RMS | 수평 흐름선 ~1m 간격 |
| **폴리곤 수** | 2,000-5,000 faces | v1.0 충분 (G4) |

#### 에셋 파일 구조

```
assets/structures/cave/
  lava_tube.obj          # 터널 셸 (천장+벽)
  lava_tube_floor.obj    # 바닥 메시 (별도, 충돌용)
  collapse_rubble/       # skylight 아래 붕락 잔해 (선택)
```

#### 텍스처/재질

| 표면 | Albedo | PBR Roughness | 색상 |
|------|--------|---------------|------|
| 현무암 벽 | 0.10-0.15 | 0.7-0.9 | 어두운 회갈색 (#3A3530) |
| 현무암 바닥 | 0.12-0.18 | 0.6-0.8 | 어두운 회색 (#454040) |
| 붕락 잔해 | 0.10-0.20 | 0.8-0.95 | 혼합 회갈색 |

#### 조명 설정

| 광원 | 설정 |
|------|------|
| DomeLight (하늘) | **OFF** |
| DistantLight (태양) | **OFF** |
| Fog (대기) | **OFF** |
| Skylight 광원 | AreaLight/DistantLight, 하향 원뿔, Mars butterscotch 색온도 |
| 로버 헤드라이트 | SpotLight x2, 30도 원뿔, 5000K 백색 |
| Ambient | **0 lux** (skylight 원뿔 바깥 완전 암흑) |

### 참고 논문

- **Sauro et al. (2020):** "Lava tubes on Earth, Moon and Mars" — Earth-Science Reviews 209, 103288. DOI: 10.1016/j.earscirev.2020.103288
- **Cushing et al. (2007):** "THEMIS observes possible cave skylights on Mars" — GRL 34, L17203
- **Cushing (2012):** "Candidate cave entrances on Mars" — J. Cave Karst Studies 74(1), 33-47
- **Bleacher et al. (2017):** 화성 용암 터널 탐사 유사체 연구
- **Wynne et al. (2008):** "On determining the cave climate of Mars" — EPSL 272, 240-248

---

## Scenario 6: Spacecraft Landing Site (우주선 착륙지)

### 에셋 전략: NASA 3D Resources 우선

#### 1순위: InSight Lander

| 항목 | 내용 |
|------|------|
| **출처** | nasa3d.arc.nasa.gov/detail/insight |
| **형식** | glTF (.glb) |
| **라이선스** | NASA public domain (Apache 2.0 호환) |
| **치수** | 데크 직경 1.56m, 태양 패널 각 2.15m 스팬 (총 6m), 높이 0.83m |
| **후처리** | glTF → USD 변환 (Blender + NVIDIA USD plugin), decimation (5K faces 목표), 충돌 메시 추가 |

**선택 이유:** 단순한 기하학적 형태, 잘 문서화된 치수, 태양 패널이 시각적 다양성 제공.

#### 추가 착륙지 요소 (Blender 제작)

| 요소 | 치수 | 형태 |
|------|------|------|
| Heat Shield | 직경 4.5m, 깊이 ~0.7m | 원뿔형 |
| Backshell | 직경 4.5m, 높이 ~2m | 반구형 |
| Parachute (잔해) | 직경 ~12m, 지면에 구겨진 형태 | 천 시뮬레이션 또는 sculpt |

#### 착륙지 배치 규칙

- Lander: DEM 중앙부 배치
- Heat shield: Lander에서 ~500m downrange
- Backshell + parachute: Lander에서 ~800m uprange
- 역추진 블라스트 존: Lander 주변 반경 5-10m, 표면 변색 (선택)

#### 다른 NASA 3D 모델 (가용 확인 필요)

| 모델 | URL (확인 필요) | 용도 |
|------|-----------------|------|
| Perseverance | nasa3d.arc.nasa.gov/detail/mars-2020-rover | 착륙지 컨텍스트 |
| Viking Lander | nasa3d.arc.nasa.gov/detail/viking-lander | 대안 착륙선 |
| Ingenuity | nasa3d.arc.nasa.gov/detail/ingenuity | 착륙지 장식 |

### 사용자 확인 필요사항

- [ ] nasa3d.arc.nasa.gov에서 InSight 모델 실제 다운로드 가능 확인
- [ ] glTF 형식 확인 및 Blender import 테스트
- [ ] 폴리곤 수 확인 (decimation 필요 여부)

---

## Scenario 7: Mars Base (화성 기지)

### 과학적 참조: NASA Mars DRA 5.0 (SP-2009-566, 2009)

NASA에 화성 기지 3D 모델은 존재하지 않음. DRA 5.0 치수 기반으로 Blender 제작.

### 기지 구성 요소 및 치수

| 구성 요소 | 형태 | 치수 | 우선순위 |
|-----------|------|------|---------|
| **Habitat Module** | 수평 원통 + 구형 캡 | 직경 7.5m x 길이 11m, 지상 1m | MUST |
| **Solar Array (x4)** | 원형 UltraFlex | 직경 5.5m, 마스트 높이 2.5m | MUST |
| **EVA Airlock** | 소형 원통 | 직경 2.5m x 길이 3.5m | SHOULD |
| **Comm Antenna** | 포물선 디쉬 | 직경 2.5m, 마스트 4m | SHOULD |
| **ISRU Plant** | 직사각형 + 탱크 | 3m x 3m x 2m + 탱크 2m dia x 4m | NICE-TO-HAVE |
| **Pressurized Tunnel** | 원통 | 직경 2m, 모듈 연결 | NICE-TO-HAVE |

### Blender 제작 사양

#### Habitat Module

```
형태: 원통 + 양쪽 구형 캡
  Main body: 직경 7.5m, 길이 11.0m
  End caps: 반구 반경 3.75m, 깊이 1.5m
  다리: 4개, 직경 0.3m, 길이 1.2m
  EVA 해치: 측면 1.2m x 2.0m 직사각형
  창문: 4개 원형 포트, 직경 0.5m
  도킹 포트: 한쪽 캡에 원형 2.0m
  재질: 백색/연회색 열 코팅
```

#### Solar Array

```
형태: 원형 팬 (UltraFlex 스타일)
  직경: 5.5m (전개 시)
  마스트: 직경 0.15m, 높이 2.5m
  짐벌: 2축 관절
  패널: 12-16 방사형 세그먼트
  재질: 어두운 청/흑색 (앞면), 연회색 (뒷면)
  배치: 2x2 격자, 간격 8m, habitat에서 30m
```

### 기지 전체 레이아웃 (DRA 5.0 참조)

```
                  [Comm]
                    |
    [Solar] [Solar]   [Habitat]---[Airlock]
    [Solar] [Solar]   |
                    [ISRU] (50-100m 이격)
    
    [Landing Pad] (1-2km 이격)
    
전체 핵심 시설 풋프린트: ~200m x 200m
```

### 에셋 파일 구조

```
assets/structures/base/
  habitat.obj
  solar_panel.obj
  airlock.obj          (SHOULD)
  comm_antenna.obj     (SHOULD)
  isru_plant.obj       (NICE-TO-HAVE)
  tunnel_segment.obj   (NICE-TO-HAVE)
```

### v1.0 최소 품질 기준 (G4)

| 항목 | 기준 |
|------|------|
| 폴리곤 | 500-5,000 faces / 에셋 |
| 텍스처 | 1K (1024x1024) |
| PBR | Albedo + Normal + Roughness |
| 충돌 메시 | 단순 convex hull |
| 핵심 | 정확한 스케일 + PhysX 충돌 + Nav2 장애물 회피 테스트 가능 |

---

## 종합: 에셋 확보 로드맵

| Scenario | 에셋 유형 | 소싱 방법 | 예상 작업량 |
|----------|----------|----------|------------|
| 4 Canyon | HiRISE DEM | PDS 다운로드 (기존 파이프라인) | 2-4시간 (다운로드+변환+crop) |
| 5 Cave | 3D 터널 메시 | **Blender 제작** | 8-12시간 |
| 6 Spacecraft | 착륙선 모델 | **NASA 3D Resources** 다운로드 + 변환 | 2-4시간 (+ 추가 요소 Blender 4시간) |
| 7 Mars Base | 기지 구성 요소 | **전부 Blender 제작** | 12-16시간 |

### 라이선스 호환성

| 출처 | 라이선스 | Apache 2.0 호환 |
|------|---------|-----------------|
| HiRISE DEM (PDS) | Public domain | YES |
| NASA 3D Resources | NASA public domain | YES |
| Blender 자체 제작 | Apache 2.0 (프로젝트 소유) | YES |
| Sketchfab CC0 | CC0 | YES |
| Sketchfab CC-BY | CC-BY 4.0 | YES (attribution 필요) |

### 사용자 액션 아이템

1. [ ] `https://www.uahirise.org/dtm/` 에서 Cerberus Fossae DTM 검색 및 product ID 확인
2. [ ] `https://nasa3d.arc.nasa.gov` 에서 InSight 모델 다운로드 가능 여부 확인
3. [ ] NASA DRA 5.0 문서 (`ntrs.nasa.gov`에서 "NASA SP-2009-566" 검색) 다운로드
4. [ ] Canyon DEM 최종 선택 (Cerberus Fossae vs Coprates Chasma)
5. [ ] Blender 에셋 제작 일정 결정 (Cave, Base 우선순위)
