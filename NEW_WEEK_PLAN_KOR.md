# MarsLab 품질 강화 계획 (Post-Week 11)

**버전:** 1.0 (5-Agent 적대적 토론 합성)
**작성일:** 2026-04-09
**대상:** Week 11 (센서 통합) 이후 ~ 논문 제출 (Sep 15, 2026)

---

## 1. 배경 및 목적

### 1.1 프로젝트 현황

MarsLab은 NVIDIA Isaac Sim 5.1.0 기반의 포토리얼리스틱 화성 시뮬레이션 플랫폼으로,
ICRA 2027 Seoul 논문 제출을 목표로 한다. 22주 개발 일정 중 Week 1-7이 **1일 만에 완료**되어
Phase 1a가 사실상 마무리 상태이다.

**완료 현황:** config(Wk1), terrain(Wk2), atmosphere(Wk3), rover+PBR(Wk4),
procedural terrain(Wk5), rendering 통합(Wk6), multi-robot(Wk7).
Unit test: 130개 통과. Integration test: 11개 통과.

### 1.2 핵심 문제

현재 렌더링 결과물(`work_log/mars_scene_*.png`)은 다음 문제를 가진다:

1. **지형이 단색 평면** — UV 좌표 없음, PBR 텍스처 없음
2. **바위 3D 객체 부재** — `rock_placer.py`가 좌표만 생성, scene에 미반영
3. **HDRI 스카이돔 없음** — `assets/sky/hdri/` 비어있음, 단색 fallback
4. **렌더링 매직 넘버** — `intensity * 5.0` 등 G5 위반
5. **SPP 32 클램핑** — 64 설정이 GPU 제한으로 32로 강제
6. **diffuse_fraction 미사용** — 계산만 하고 렌더링에 미반영

이 상태로는 ICRA 논문의 "photorealistic" 클레임이 성립하지 않는다.

### 1.3 본 보고서의 방법론

5개 에이전트의 적대적 토론을 통해 계획을 수립했다:
- **Agent 1** (렌더링 전문가): 85시간 계획 초안
- **Agent 2** (센서 전문가): 12.75일 계획 초안
- **Agent 3** (적대적 리뷰어 - 렌더링): 16개 구체적 반박
- **Agent 4** (적대적 리뷰어 - 센서): 16개 구체적 반박
- **Agent 5** (종합): 방어율 평가 + 최종 합성

---

## 2. 토론 결과 요약

### 2.1 방어율 표

| 에이전트 | 제안 | 비판 | 완전 방어 | 부분 방어 | 비방어 | 방어율 |
|----------|------|------|-----------|-----------|--------|--------|
| Agent 1 (렌더링) | 6개 (85h) | Agent 3 | 0 | 2 | 4 | 33% |
| Agent 2 (센서) | 6개 (12.75d) | Agent 4 | 0 | 2 | 4 | 33% |
| **종합** | **12개** | | **0** | **4** | **8** | **33%** |

### 2.2 핵심 합의 사항

**방어 성공 (최종 계획에 포함):**
- PBR 텍스처 적용 (UV + 4K 텍스처 1세트) — 범위 축소하여 8h
- 바위 3D PointInstancer — 범위 축소하여 10h
- 기본 센서 부착 (RGB + depth + IMU + LiDAR) — 원래 Wk 11 계획대로

**방어 실패 (Phase 2로 이관):**
- Post-Processing (렌즈 플레어, 색수차, 모션 블러) — OmniLRS도 기본 비활성화
- 물리 카메라 시스템 — Replicator 기본 카메라로 충분
- 센서 노이즈 모델 (Allan variance 등) — 세그멘테이션 벤치마크에 불필요
- 스테레오 카메라 — 모노큘러 세그멘테이션으로 충분
- Calibration 자동 내보내기 — nice-to-have

### 2.3 주요 반박에서 도출된 인사이트

1. **"논문 accept에 직결되는가?"가 유일한 기준** — 현재 문제는 "고급 기능 부족"이 아니라 "기초 품질 미달"
2. **Agent 1의 85h → 48h로 44% 감소** — Post-Processing(11h) + Camera(12h) + Lighting 과다(7h) + Sky 과다(10h) 제거
3. **Agent 2의 12.75d → 2.5d로 80% 감소** — 노이즈 모델 전체(3d) + 렌즈 효과(1.5d) + 캘리브레이션(1.75d) + 과다 설계 제거
4. **실제 개발 속도(5x)를 시간 추정에 반영** — 원래 5일 일정이 실제로 1일에 완료되는 패턴

---

## 3. 최종 계획

### Phase A: 즉시 수정 (4h) — Wk 8 Review Gate 전

| # | 작업 | 파일 | 공수 |
|---|------|------|------|
| A1 | 렌더링 매직 넘버 YAML 이동 | sun_renderer, sky_renderer, atmosphere_fog, schema.py | 2h |
| A2 | SPP 클램핑 대응 (기본값 32, totalSpp 256) | render_settings.py, path_tracing.yaml | 1h |
| A3 | diffuse_fraction DomeLight 적용 | sky_renderer.py | 1h |

**검증:** 기존 130개 unit test 전체 통과, G5 위반 0개.

### Phase B: 핵심 품질 강화 (28h) — Wk 9-10

| # | 작업 | 파일 | 공수 | 우선순위 |
|---|------|------|------|----------|
| B1 | Mars PBR 텍스처 (UV + 4K albedo/normal/roughness) | mesh_builder, material_applicator | 8h | **P0** |
| B2 | 바위 3D PointInstancer | rock_instancer.py (신규), run_scene.py | 10h | **P0** |
| B3 | HDRI 스카이돔 1개 적용 | assets/sky/hdri/, sky_renderer.py | 4h | **P1** |
| B4 | 지형 기하학 개선 (요철 + normal + rocky_plain) | procedural_generator, mesh_builder | 6h | **P1** |

**검증 기준:**
- V-B1: 지형에 PBR 질감 시각 확인 (단색 아님)
- V-B2: 지형 위 바위 50개+ 분포 시각 확인
- V-B3: HDRI 하늘 렌더링 (butterscotch, 단색 아님)
- V-B4: 카메라 근접 시 지형 요철 인지
- tau 0.3 vs 2.0 side-by-side 차이 명확

### Phase C: 확장 강화 (16h) — Wk 11

| # | 작업 | 파일 | 공수 |
|---|------|------|------|
| C1 | 센서 부착 (RGB, depth, IMU, LiDAR) | sensors/*.py (3개 신규) | 8h |
| C2 | 추가 HDRI 또는 tau 연동 색온도 조정 | sky_dome.py, sky_renderer.py | 4h |
| C3 | 도메인 랜덤화 시각 검증 스크립트 | visualize_dr_variations.py | 4h |

**핵심 검증:** IMU z-axis = 3.72 ± 0.05 m/s² (THE critical test)

### Phase D: Phase 2 이관 (현재 범위 밖)

| 항목 | 근거 |
|------|------|
| 센서 노이즈 모델 (Allan variance IMU, Gaussian/Poisson 카메라) | 세그멘테이션 벤치마크에 불필요 |
| 렌즈 효과 (플레어, 색수차, 모션 블러) | OmniLRS도 기본 비활성화 |
| 스테레오 카메라 | 모노큘러 세그멘테이션으로 충분 |
| 물리 카메라 시스템 (f-stop, DOF) | Replicator 기본 카메라 충분 |
| CameraInfo ROS2 calibration | Phase 2 SLAM용 |
| HiRISE DEM Isaac Sim 직접 렌더링 | GDAL 환경 문제 미해결, 위험 높음 |
| 다중 해상도/다중 포맷 출력 | 1280x720 고정이면 논문 충분 |

---

## 4. 일정 매핑

| 주차 | Phase | 핵심 작업 | 산출물 |
|------|-------|-----------|--------|
| **Wk 8** | A | 하드코딩 제거, SPP 수정, Review Gate 1 | 클린 렌더링 설정 |
| **Wk 9** | B1+B3 | PBR 텍스처 + HDRI 적용 | 텍스처 있는 지형 + 하늘 |
| **Wk 10** | B2+B4 | 바위 인스턴싱 + 지형 개선 | 바위가 보이는 Mars scene |
| **Wk 11** | C1 | 센서 부착 (RGB, depth, IMU, LiDAR) | 센서 데이터 출력 |
| **Wk 12** | C2+C3+원래 일정 | DR 검증 + Annotation pipeline | 라벨링 파이프라인 |
| **Wk 13-16** | 원래 일정 | Benchmark + ROS2 + Evaluation | 데이터셋 + 평가 |
| **Wk 17-22** | 원래 일정 | 실험 + 논문 | ICRA 2027 제출 |

**변경점:**
- Wk 9: 원래 ROS2 → **PBR 텍스처** (렌더링 품질 선행, G4 존중)
- Wk 10: 원래 Multi-Robot+Humanoid → **바위 + 지형** (다중 로봇은 Wk 7에서 완료)
- ROS2: Wk 12-13으로 이동 (센서/어노테이션과 통합)

---

## 5. 총 공수 비교

| 계획 | 공수 | 항목 수 | 비고 |
|------|------|---------|------|
| Agent 1 원안 | 85h | 6 | 과대 설계 |
| Agent 3 대안 | 40h | 7 | 핵심 집중 |
| Agent 2 원안 | 12.75d (~100h) | 6 | Phase 2 작업 혼재 |
| Agent 4 대안 | 2.5d (~20h) | 5 | 최소 MVP |
| **최종 합성** | **48h** | **10** | **Phase A(4h) + B(28h) + C(16h)** |

Agent 1 대비 44% 감소, Agent 2 대비 52% 감소. ICRA 논문 accept에 직결되는 항목만 포함.

---

## 6. 위험 요소 및 완화 방안

| 위험 | 심각도 | 완화 |
|------|--------|------|
| PBR 텍스처 소싱 실패 | 높음 | CC0 rock/sand 텍스처 → Mars 색조 보정. Fallback: 절차적 생성 |
| PointInstancer 성능 저하 (수만 개 바위) | 중간 | d_min=0.5m으로 제한, camera frustum culling |
| Isaac Sim 5.1.0 API 비호환 | 중간 | 각 API 사용 전 prototype 스크립트로 검증 |
| SPP 32 클램핑 해결 불가 | 낮음 | totalSpp 누적 + Denoiser로 우회 |
| HDRI 색조 보정 품질 | 낮음 | 다수 CC0 후보 비교, 최적 선택 |

---

## 7. 검증 기준 체크리스트

### Phase A 완료
- [ ] 매직 넘버 0개 (G5 완전 준수)
- [ ] SPP = YAML 설정값
- [ ] diffuse_fraction → DomeLight 강도 반영
- [ ] 기존 130개 unit test 전체 통과

### Phase B 완료 (논문 최소 품질)
- [ ] **V1**: 하늘이 butterscotch HDRI (파란색/검은색 아님)
- [ ] **V2**: 지형에 PBR 텍스처 (단색 아님)
- [ ] **V3**: 바위가 지형 위에 분포 (최소 50개 시각 확인)
- [ ] **V4**: tau=0.3 vs tau=2.0 side-by-side 차이 명확
- [ ] **V5**: Mars 렌더링이 달(lunar) 파라미터와 구분 가능
- [ ] "이것은 화성 표면이다"라고 인지 가능

### Phase C 완료
- [ ] IMU z-axis = 3.72 ± 0.05 m/s² (**THE critical test**)
- [ ] RGB 카메라 1280x720 이미지 출력
- [ ] Depth 맵 출력
- [ ] LiDAR point cloud 출력

---

## 부록: 발견된 코드 버그 (즉시 수정 필요)

1. `sun_renderer.py:37` — `sun.GetIntensityAttr().Set(intensity * 5.0)` → G5 위반 (매직 넘버)
2. `sun_renderer.py:39` — `Gf.Vec3f(1.0, 0.95, 0.85)` → G5 위반 (하드코딩 색상)
3. `sky_renderer.py:33` — `dome.GetIntensityAttr().Set(sky_params.brightness * 1000.0)` → G5 위반
4. `atmosphere_fog.py:33` — `fog_density = tau * 0.002` → G5 위반 (스케일 팩터)
5. `atmosphere_fog.py:36` — `fog_color = [0.78, 0.62, 0.42]` → G5 위반 (하드코딩 색상)
6. `sun_renderer.py` — `diffuse_fraction` 파라미터를 받지만 **미사용**
7. `run_scene.py` — `rock_placer.py` 호출 코드 **부재** (바위 미배치)
