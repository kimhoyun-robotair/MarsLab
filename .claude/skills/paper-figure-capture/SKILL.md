---
name: paper-figure-capture
description: "MarsLab iSpaRo 2026 논문 figure 생성. 7개 scenario 스크린샷, SLAM 궤적 plot, Nav2 success heatmap, τ sweep 곡선, IEEE 형식 figure caption. Wk6 데이터를 paper/figures/ 로 정리. '논문 figure', 'paper screenshot', 'figure 다시', 'iSpaRo 그림', 'plot 정리', 'figure caption', 'figure 회귀' 요청 시 반드시 사용."
---

# paper-figure-capture — MarsLab iSpaRo 2026 논문 Figure 생성

Wk6의 벤치마크 데이터와 7개 scenario를 iSpaRo 2026 논문에 들어갈 figure로 변환하는 워크플로우. 8 page Regular Paper 분량을 고려하여 figure 수와 정보 밀도를 균형 있게 관리한다.

## Why this matters
논문에 들어갈 figure는 (a) 정확하고, (b) 재현 가능하고, (c) IEEE 양식에 맞아야 한다. 즉흥 스크린샷은 마감 직전 재캡처 비용이 크다. 이 스킬은 figure를 데이터 기반으로 자동 생성하고, Isaac Sim이 필요한 부분만 사용자 실행으로 분리한다.

## Figure 카탈로그 (제안)

| ID | 종류 | 데이터 소스 | 생성 방식 |
|----|------|-----------|----------|
| fig:overview | MarsLab 시스템 다이어그램 | 수동 | drawio/PowerPoint, png export |
| fig:scenarios | 7개 scenario 그리드 | Isaac Sim screenshot | 사용자 실행 |
| fig:terrain_pipeline | DEM→rocks→assets 흐름 | matplotlib + sample data | 오프라인 자동 |
| fig:atmosphere | sun sweep + τ 효과 비교 | sky_dome 산출물 | 오프라인 + Isaac Sim |
| fig:slam_traj | scenario별 SLAM 궤적 | `_workspace/{wk}_slam_bench.json` | matplotlib 자동 |
| fig:slam_ate | scenario × ATE bar plot | 동상 | matplotlib 자동 |
| fig:nav2_success | scenario × success rate heatmap | `_workspace/{wk}_nav2_bench.json` | matplotlib 자동 |
| fig:tau_sweep | τ vs ATE/success 곡선 | `_workspace/{wk}_tau_sweep.csv` | matplotlib 자동 |
| fig:rover | rover URDF + sensor mount | trimesh + screenshot | 오프라인 + Isaac Sim |

목표: 8 페이지에 ~6 figure, 표 ~3개. 위 9개 중 우선순위로 선택.

## 워크플로우

### Step 1: 데이터 수집
- `_workspace/wk6_*` 의 JSON/CSV 산출물 수집(slam-nav-benchmark 스킬의 출력)
- 누락된 데이터는 `slam-nav-integrator`에 SendMessage로 요청

### Step 2: 오프라인 figure 생성
matplotlib + numpy로:
- bar/line/heatmap plot 자동 생성
- IEEE 형식: figure 폭 3.5 inch (single col) 또는 7.16 inch (double col), 300 DPI, sans-serif, 글꼴 크기 8pt
- 출력 경로: `paper/figures/{fig_id}.png` 및 `.pdf` 두 포맷
- 캡션 초안: `paper/figures/{fig_id}.caption.txt`

### Step 3: Isaac Sim 필요 figure 준비
- 사용자에게 다음 요청:
  - 7개 scenario 각각 같은 시점·각도 스크린샷 (path-tracing, SPP 충분)
  - rover sensor mount close-up
  - 각 사진 명명: `paper/figures/raw/scenario_{name}.png`
- 후처리(crop, annotation 화살표 추가)는 `Pillow` + matplotlib로 자동

### Step 4: Figure caption 작성
각 figure에 IEEE 양식 캡션 초안:
```
Fig. 5: SLAM ATE across seven Mars mission scenarios at τ=1.0.
Bars show mean over 5 seeds; error bars represent standard deviation.
Cave scenario (rightmost) exhibits highest ATE due to feature-sparse walls.
```

### Step 5: 회귀 비교
- 이전 figure 버전이 `paper/figures/archive/` 에 있는지 확인
- 데이터가 변경되었는데 figure가 갱신 안 되면 alert
- 새 figure 생성 시 이전 버전을 `archive/{date}/` 로 이동(삭제 금지)

### Step 6: 최종 점검
- 모든 figure가 8 page 분량에 맞는 해상도·크기인지
- 캡션이 본문 텍스트와 일관된 표기(기호, 단위)
- 색맹 친화 색상 사용 (viridis, cividis 등)

## 안전 원칙
- 데이터에 없는 결과를 figure에 표시하지 않는다(조작 금지).
- IEEE 양식 폭·DPI 준수, vector(PDF) + raster(PNG) 둘 다 생성.
- raw screenshot은 `paper/figures/raw/`에 보관, 가공본만 `paper/figures/`.
- 이전 버전 archive 후 교체.
- v2.0 photorealism figure는 out-of-scope.

## 후속 작업 키워드
"figure 다시", "scenario 사진 재캡처", "ATE plot 다시", "tau sweep figure 갱신", "caption 수정", "IEEE 형식 다시" 후속 요청 시 사용. 이전 archive와 비교.

## 테스트 프롬프트
1. "Wk6 figure 6개 만들어줘 — SLAM ATE, Nav2 success, τ sweep 우선."
2. "Scenario screenshot 재캡처 후 그리드 figure 다시."
3. "fig:tau_sweep 캡션 영어로 다듬어줘."
