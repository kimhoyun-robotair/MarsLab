---
name: slam-nav-benchmark
description: "MarsLab SLAM·Nav2 벤치마크 실행 및 통계. ATE/RPE 측정(SLAM), success rate/path length(Nav2), tau ∈ {0.3,1.0,2.0,4.0} sweep 실험, 7개 scenario 전수 비교, 결과 JSON/CSV 저장, 회귀 비교. 'SLAM 벤치마크', 'Nav2 벤치마크', 'tau sweep 돌려', 'ATE 측정', 'RPE 다시', '논문 데이터 생성', '벤치마크 회귀', 'success rate 측정' 요청에 반드시 사용."
---

# slam-nav-benchmark — MarsLab SLAM·Nav2 벤치마크

MarsLab v1.0 Wk6의 핵심 산출물: 7개 scenario × 2개 알고리즘(SLAM, Nav2) × 4개 τ 조건의 정량 데이터를 생성하여 iSpaRo 2026 논문 figures/tables를 만든다.

## Why this matters
v1.0의 차별점은 **dynamic atmosphere 환경에서 SLAM·Nav 견고성 평가**다(PLAN.md §1, §5.3 Wk6). 단순 동작 시연이 아닌, 정량적 비교 데이터가 있어야 paper가 성립한다. 이 스킬은 결과 데이터의 형식·재현성·통계 처리를 표준화한다.

## 벤치마크 매트릭스

| Scenario | SLAM ATE/RPE | Nav2 success rate | Nav2 path length | τ sweep |
|---------|--------------|-------------------|------------------|---------|
| basic_mars | ✓ | ✓ | ✓ | ✓ |
| rock_dense | ✓ | ✓ | ✓ | ✓ |
| crater_slopes | ✓ | ✓ | ✓ | ✓ |
| canyon | ✓ | ✓ | ✓ | (선택) |
| cave | ✓ | ✓ | ✓ | (cave는 외부 sky 무관) |
| spacecraft | ✓ | ✓ | ✓ | (선택) |
| mars_base | ✓ | ✓ | ✓ | (선택) |

τ sweep: τ ∈ {0.3, 1.0, 2.0, 4.0}, scenario 1~3에 적용(7×4 = 12 run + 7×4 = 12 run = 24 base experiment).

각 실험 seed=42 고정.

## 데이터 형식

### `_workspace/{wk}_slam_bench.json`
```json
{
  "scenario": "basic_mars",
  "tau": 1.0,
  "seed": 42,
  "duration_s": 600,
  "metrics": {
    "ate_m": {"mean": 0.18, "std": 0.05, "max": 0.42},
    "rpe_m": {"mean": 0.04, "std": 0.01},
    "map_complete": true
  },
  "ros2_bag": "_workspace/bags/basic_mars_tau1.0.bag"
}
```

### `_workspace/{wk}_nav2_bench.json`
```json
{
  "scenario": "basic_mars",
  "waypoints": [...],
  "metrics": {
    "success_rate": 0.95,
    "path_length_m": 187.3,
    "time_to_goal_s": 124.5,
    "n_replanning": 3
  }
}
```

### `_workspace/{wk}_tau_sweep.csv`
```
scenario,tau,ate_mean,ate_std,success_rate
basic_mars,0.3,0.15,0.04,0.98
basic_mars,1.0,0.18,0.05,0.95
basic_mars,2.0,0.27,0.08,0.88
basic_mars,4.0,0.45,0.15,0.65
...
```

## 워크플로우

### Step 1: 사전 조건 점검
- `ros2-bridge-verification` 스킬 통과 (토픽 sanity)
- `urdf-physics-tuning` 통과 (IMU 중력 OK)
- `dem-scenario-builder`로 7개 scenario YAML 모두 작성 완료
- `dynamic-atmosphere-update` 통과 (τ sweep 가능)

### Step 2: 벤치마크 스크립트 작성
- `scripts/benchmark/slam_ate.py` — ATE/RPE 계산 (ground truth는 sim의 정답 trajectory)
- `scripts/benchmark/nav2_success.py` — waypoint 도달률
- `scripts/benchmark/tau_sweep.py` — τ 변경하며 SLAM 반복 실행
- 모든 스크립트는 seed 인수 받음, 결과를 위 JSON/CSV 형식으로 출력

### Step 3: 단위 테스트(파서·통계만 오프라인)
- `tests/unit/test_benchmark_parsers.py` — JSON/CSV 파싱, 통계 함수(mean·std·max) 단위 검증
- 실제 SLAM 실행은 사용자 직접

### Step 4: 사용자 실행 요청
- 사용자에게 Isaac Sim + ROS2 + scripts/benchmark 실행 요청
- 단계별: scenario 1만 먼저 → 결과 확인 → 7개 전수 → τ sweep
- 각 실행 후 결과 JSON을 받아 `_workspace/`에 저장

### Step 5: 회귀 비교
- 이전 주차 결과(`_workspace/{prev_wk}_*.json`)와 비교
- 회귀 발견 시 (ATE 증가, success rate 감소) 즉시 `qa-validator`에 alert
- 회귀 원인 후보: URDF 변경, scenario YAML 변경, atmosphere 코드 변경, seed 의도 변경

### Step 6: 시각화
- `_workspace/{wk}_slam_ate_per_scenario.png` — bar plot
- `_workspace/{wk}_tau_vs_ate.png` — line plot per scenario
- `_workspace/{wk}_nav2_success_grid.png` — heatmap (scenario × τ)
- 이 plot들이 `paper-figure-capture` 스킬의 입력이 됨

### Step 7: 최종 데이터 export
- `paper/data/slam_results.csv`, `nav2_results.csv` 로 정리
- 각 row에 모든 메타데이터(scenario, τ, seed, duration, commit hash) 포함

## 안전 원칙
- 모든 실행은 seed 고정. 비결정적 결과 금지.
- 외부 ROS2 패키지(slam_toolbox, nav2_*) 코드 복사 금지(G3).
- 실패한 실행도 로그 보존 — 누락 표기 후 다음으로 진행.
- 벤치마크 스크립트 자체에는 Mars 파라미터 하드코딩 금지(G5).
- 이전 결과 archive(삭제 금지).

## 후속 작업 키워드
"τ sweep 다시", "벤치마크 일부만 다시", "ATE 재계산", "Nav2 success 재측정", "회귀 점검", "결과 시각화 다시" 후속 요청에 사용. 이전 JSON/CSV Read로 비교.

## 테스트 프롬프트
1. "Wk6 벤치마크 시작 — 일단 basic_mars부터."
2. "τ sweep 결과 plot 다시 그려줘."
3. "Nav2 success rate가 회귀했는지 확인."
