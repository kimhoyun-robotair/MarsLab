---
name: dynamic-atmosphere-update
description: "MarsLab 동적 대기 워크플로우. Sun azimuth sweep(time-of-sol), runtime tau variation, atmosphere fog 자동 재계산, sky dome butterscotch 색상 튜닝. Beer's law(NASA TM-102299, 5% 오차) + COMIMART diffuse fraction 검증. '동적 대기', 'sun sweep', 'tau 변화', 'fog 재계산', 'butterscotch 색', 'sky dome 튜닝', 'time of sol', 'tau sweep 다시', '대기 재구성' 요청 시 반드시 사용."
---

# dynamic-atmosphere-update — MarsLab 동적 대기 갱신

MarsLab v1.0의 dynamic atmosphere(Wk3·Wk5)를 구현·검증하는 워크플로우. Sun position·dust opacity τ·fog가 런타임에 일관되게 갱신되도록 한다.

## Why this matters
정적 sky·sun으로는 SLAM 견고성, 그림자 변화, τ 영향 평가가 불가능하다. v1.0의 차별점 중 하나가 "dynamic atmosphere + SLAM/Nav 평가"이므로(PLAN.md §1), τ ∈ {0.3, 1.0, 2.0, 4.0} 4단계와 time-of-sol sun 위치를 런타임에 안정적으로 변경할 수 있어야 한다. Beer's law·COMIMART 식은 NASA 참조값과 5% 이내 정확도를 유지해야 한다.

## 워크플로우

### Step 1: 모듈 현황 확인
1. `marslab/environment/sun_position.py`, `light_intensity.py`, `diffuse_fraction.py`, `sky_dome.py` Read
2. `marslab/rendering/sky_renderer.py`, `sun_renderer.py`, `atmosphere_fog.py`, `render_settings.py` Read
3. 현재 정적 vs 동적 분기 상태 정리, `_workspace/wk3_env_baseline.md`에 기록

### Step 2: Sun azimuth sweep (오프라인 검증)
- `sun_position(t_seconds, latitude, longitude, sol_number)` 함수가 time-of-sol 입력으로 azimuth/elevation 반환하는지 확인
- numpy로 24h sol(88642 s) sweep → matplotlib plot
- `_workspace/{wk}_env_sun_sweep.png` 저장(azimuth, elevation 곡선)
- 사용자 공유 → 시각적 합리성 확인

### Step 3: Runtime tau variation
- `sky_dome.py`에 `update_tau(new_tau)` 함수 존재 확인 또는 신설
- τ 변화 시 sky_dome 색상·intensity, fog 농도, 직사광/산란광 비율이 한 번에 갱신되도록 트리거
- 무한 루프·중복 갱신 없도록 호출 그래프 정리

### Step 4: Fog auto-update
- `atmosphere_fog.py` 가 τ 변화 이벤트를 구독(Observer or callback)
- Beer's law: I = I0 · exp(−τ · m), m = airmass
- `_workspace/{wk}_env_beerslaw_tau_curve.png` 에 τ ∈ [0, 5] 곡선 plot
- NASA TM-102299 참조값과 5% 이내 일치 확인

### Step 5: Sky color tuning (butterscotch)
- 낮은 τ(0.3~0.7)에서 butterscotch RGB 범위에 들어가는지 검증
- 단위 테스트: `tests/unit/test_sky_dome_rgb.py` — τ별 RGB 평균이 mars 일출/낮 색상 범위

### Step 6: COMIMART diffuse fraction
- `diffuse_fraction.py` 가 Vicente-Retortillo et al. (2015) 식을 따르는지 검증
- τ별 diffuse fraction 곡선 plot → `_workspace/{wk}_env_diffuse_curve.png`

### Step 7: Cave lighting 모드 (Wk5)
- DomeLight off + PointLight/SpotLight 분기를 `sky_renderer.py` 에 추가
- scenario YAML의 `lighting.domelight.enabled: false` 시 다른 광원 활성화
- Cave scenario 전용 검증: 외부광 차단되었는가, 내부 광원만 동작하는가

### Step 8: Isaac Sim 통합 검증 (사용자 실행)
- 사용자에게 다음 시나리오를 Isaac Sim에서 실행 요청:
  - τ=0.3 → τ=2.0 → τ=4.0 순차 변화, fog·sky 갱신 확인
  - sun azimuth 0° → 180° sweep, 그림자 회전 확인
- 결과를 `_workspace/{wk}_env_isaac_validation.md`에 기록

## 안전 원칙
- 모든 상수·범위는 `configs/mars_env.yaml`(G5).
- `environment/`는 Isaac Sim import 금지(P3, offline-first).
- `rendering/`만 Isaac Sim 의존, 그러나 파라미터 계산은 `environment/`에서 받는 단방향 의존(P2).
- Beer's law·COMIMART 식은 논문 참조 식만 사용, OmniLRS 코드 복사 금지(G3).
- 코드 비활성화는 주석 처리.
- v2.0 photorealism(4K HDRI, 안티타일링)은 out-of-scope.

## 후속 작업 키워드
"sun sweep 다시", "tau 재검증", "fog 재계산", "sky 색 다시", "Beer's law 5% 초과", "diffuse fraction 점검", "cave lighting 재구성" 등 후속 요청에 사용. 이전 `_workspace/{wk}_env_*` 산출물 Read.

## 테스트 프롬프트
1. "동적 대기 통합해줘. tau 0.3에서 4.0까지 sweep 가능하게."
2. "Beer's law 검증 다시 — 4% 초과인 것 같음."
3. "Cave scenario lighting 모드 점검."
