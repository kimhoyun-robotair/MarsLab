# MarsLab Code Health Report — 2026-04-24

> **Scope:** 일회성 건강 진단(Q2) + 리팩토링 우선순위 식별(Q3).
> **Deliverable:** 본 리포트 1건 + HTML coverage 스냅샷.
> **CI / pre-commit / pyproject / 소스 코드 변경 — 없음.**

---

## Part 0 — Scope & Methodology

| 항목 | 값 |
|---|---|
| 측정 대상 | `marslab/` (79 files, ~10K LOC) + `scripts/` (22 files, ~4.5K LOC) |
| 측정 제외 | `tests/`, `delete_later/`, `refactoring/`, USD/URDF/YAML, 타 언어 |
| 측정 도구 | radon 6.0.1, lizard, pylint 4.0.5, pytest-cov |
| 실행 일자 | 2026-04-24 |
| 원시 출력 | `work_log/measurements_2026-04-24/{radon_raw,cc,mi,hal,lizard,coverage,pylint_dup}.txt` |
| Coverage HTML | `work_log/coverage_snapshot_2026-04-24/index.html` |
| 측정되지 않은 축 | DORA 4 (프로세스), SPACE (팀), CK metrics (OO), 보안 스캔, mutation score, profiling |

**임계값 출처**
- CC: McCabe (1976); SonarSource 기본 ≤10 warn, Microsoft VS ≤15 block
- MI: Oman & Hagemeister (1992); 두 스케일 병기 — radon (A≥20/B≥10/C<10) vs Microsoft VS (A≥85/B≥65/C<65)
- Coverage: Myers (2011) — 숫자 자체는 품질 아님 (Fowler 2012 경고)
- Code smells: Fowler, *Refactoring* 2nd ed. (2018) Ch.3

**Fowler 경고 재명시:** 이 리포트의 등급은 "리팩토링 우선순위"에 대한 것이며 "코드 완성도"가 아니다. "done"은 존재하지 않는다.

---

## Part A — Health Snapshot (Q2 답)

### A1. Scale

| 항목 | 값 |
|---|---|
| 총 LOC | 14,492 |
| 유효 SLOC | 8,345 |
| 코멘트 비율 | 26% (C+M%L) |
| Python 파일 | 162 (marslab 79 + scripts 22 + tests 61) |
| 분석 대상 함수/클래스 블록 | 270 |
| Unit test 수 | 735 pass / 0 fail (10.09s) |

연구 코드 규모 (≈10K LOC marslab/) 에서 **comment 비율 26%** 는 과학 상수 출처 인용이 많은 탓으로 합리적 수준.

### A2. Cyclomatic Complexity 분포 (McCabe)

```
A (1-5)   : 217  ████████████████████████████████ 80.4%
B (6-10)  :  38  █████                           14.1%
C (11-20) :  13  ██                               4.8%
D (21-30) :   1                                   0.4%
E (31-40) :   0
F (41+)   :   1                                   0.4%
```

- **평균 CC = 4.02 (grade A)** — 업계 양호 범위 (SonarSource 기본 ≤10).
- **SonarSource 임계값(>10) 초과 함수 15개** (5.6%). Microsoft VS 기준(>15)은 4개.
- **F-grade 단 1개** = `scripts/phase1/run_stage3_monolithic.py::main` (CC=112). **의도된 Oracle twin** 이라 제외.
- lizard 교차 검증 평균 CCN=4.2로 radon 값과 일치.

**판정:** 복잡도 분포는 Python 연구 코드 업계 평균과 같거나 약간 양호.

### A3. Maintainability Index 분포

두 스케일 병기 — radon 은 느슨하고 Microsoft 는 엄격:

| Grade | radon (20/10/0) | Microsoft VS (85/65/0) |
|-------|-----------------|------------------------|
| A (highly maintainable) | **100 / 101** | 37 / 101 |
| B (moderate) | 1 | 46 |
| C (difficult) | 0 | **18** |

**Microsoft 스케일 기준 하위 10개 (C-grade, <65):**

| MI | 파일 |
|---|---|
| 19.89 | `scripts/phase1/run_stage3_monolithic.py` (Oracle, 제외) |
| 43.24 | `marslab/runtime/main_loop.py` |
| 47.29 | `scripts/tools/generate_instruction_index.py` |
| 49.73 | `marslab/config/schema/terrain.py` |
| 50.55 | `marslab/terrain/procedural_generator.py` |
| 52.84 | `scripts/visualize_cave.py` |
| 54.35 | `scripts/visualize_scenario.py` |
| 56.04 | `scripts/analyze_dem_regions.py` |
| 56.42 | `marslab/math/quaternion.py` |
| 56.53 | `marslab/terrain/rock_instancer.py` |

**해석:** radon 기준으로는 "전부 건강" 이지만, Microsoft 스케일로 보면 `scripts/` 유틸과 `runtime/` 은 정비가 필요하다는 신호. 단, 상당 부분은 **docstring/과학 문헌 인용 밀도**와 **Isaac Sim 모듈 import 순서 제약**이라는 도메인 요인에서 온다 (Part B 진단 참고).

### A4. Halstead — 상위 effort 파일

| Effort | 파일 |
|---|---|
| 최고 | `marslab/runtime/main_loop.py` (573줄, 30+ 필드 LoopContext) |
| 다음 | `scripts/phase1/run_stage4.py` |
| 다음 | `marslab/config/schema/terrain.py` |

Halstead volume 기준 "이해 비용 큰 파일" 순위는 MI 하위 순위와 거의 일치 → 독립 축으로서 추가 정보 없음 (MI 안에 이미 반영).

### A5. Coverage Snapshot (참고용, 게이트 아님)

- **총 line coverage: 65%** (3,126 executable, 1,084 uncovered)
- **735 unit tests, 10.09s** — 빠른 피드백 루프 유지 중.

**Offline 모듈 (CLAUDE.md P3 범주) 커버리지:**

| 모듈 | 커버리지 |
|---|---|
| `marslab/config/` | **95%+** (yaml_loader 90%, config_loader 89%) |
| `marslab/environment/` | 100% (diffuse_fraction, sun_position 등 이미 테스트 완비) |
| `marslab/terrain/cave/` | **96–100%** |
| `marslab/terrain/dem_loader.py` | 89% |
| `marslab/terrain/rock_placer.py` | 96% |
| `marslab/math/quaternion.py` | 94% |
| `marslab/ros2_bridge/odometry_math.py` | 95% |
| `marslab/robots/drive_api_setup.py` | 92% |
| `marslab/robots/rover_control.py` | 96% |

→ **P3 원칙이 실제로 작동하고 있음.** offline 모듈은 거의 완비.

**Isaac Sim 통합 모듈 (P3상 0–35% 는 정상):**

| 모듈 | 커버리지 | 비고 |
|---|---|---|
| `rendering/*` | 0% | pxr/omni 동적 import 필요 |
| `runtime/precheck.py` | 0% | SimulationApp 전제 |
| `runtime/stage2_loop.py` | 12% | 통합 테스트 영역 |
| `runtime/stage2_scene.py` | 18% | 통합 테스트 영역 |
| `runtime/main_loop.py` | 35% | 일부 순수 로직은 커버됨 |
| `sensors/{imu,lidar,camera}.py` | 11–22% | Isaac Sim sensor API |
| `terrain/rock_instancer.py` | 0% | PointInstancer |
| `terrain/material_applicator.py` | 0% | pxr material |

**판정:** 65% 는 Python 연구 코드에서 **정상~양호** (업계 production 80%+, 연구 60–70%). offline/integration 분리가 CLAUDE.md P3 대로 명확하게 나온다는 점이 특히 긍정적.

### A6. Duplication (pylint duplicate-code)

- **31 duplicate clusters 발견, pylint 종합 9.94/10**.
- **대부분(24/31) 이 `scripts/phase1/run_stage3_monolithic.py` 와의 중복** — 의도된 Oracle twin 설계 (user memory `project_monolithic_new_oracle`). **리팩토링 대상 아님.**
- **실질적 중복 3건** (손볼 가치 있음):
  1. `marslab/math/quaternion.py` ↔ `marslab/runtime/main_loop.py:191–206` (quaternion 로컬 사본) — **Quick win**
  2. `marslab/terrain/material_applicator.py` ↔ `marslab/terrain/rock_instancer.py` — material USD 속성 설정 블록
  3. `marslab/sensors/imu.py:28–33` ↔ `marslab/sensors/lidar.py:31–36` — sensor mount parent_path 계산

SonarSource 3% 목표 대비 실질 중복 비율은 **<1%** 로 추정.

### A7. 종합 등급

| 축 | 등급 | 근거 |
|---|---|---|
| Complexity (McCabe) | **A** | 평균 4.02, C+ grade ≤ 6% |
| Maintainability (radon) | **A** | 100/101 A |
| Maintainability (Microsoft VS) | **B** | 37A / 46B / 18C |
| Coverage (offline) | **A–** | 90%+ |
| Coverage (integration) | N/A | 측정 불가 영역, P3상 정상 |
| Duplication (Oracle 제외) | **A** | <1% 실질 중복 |
| Test velocity | **A** | 735 tests / 10s |

**한 줄 판정:** MarsLab 은 **"현시점 리팩토링 우선순위 낮음"** 상태. Fowler 경고대로 "done" 은 아니며, 장기적으로 다룰 부채는 Part B 의 Quick win 3건과 Part B5 의 silent swallow 1건에 집중.

---

## Part B — Refactoring Priorities (Q3 답)

### B1. Top-10 Hotspot (4축 가중: CC/MI/Halstead/Coverage)

Oracle twin (`run_stage3_monolithic.py`) 제외 후:

| # | 파일 / 함수 | CC | MI(MS) | Cov | 줄수 |
|---|---|---|---|---|---|
| 1 | `scripts/phase1/run_stage4.py::main` | **28 (D)** | 59 | — | 356 |
| 2 | `marslab/runtime/main_loop.py` | 14/13/11 (C) | **43** | 35% | 573 |
| 3 | `marslab/runtime/stage2_loop.py::run_stage2_loop` | 12 (C) | 73 | 12% | 192 |
| 4 | `marslab/runtime/stage2_scene.py::setup_stage2_scene` | — | 64 | 18% | 242 |
| 5 | `scripts/tools/generate_instruction_index.py::main` | **19 (C)** | 47 | — | 210 |
| 6 | `marslab/terrain/procedural_generator.py` | — | 51 | 85% | 294 |
| 7 | `marslab/config/schema/terrain.py` | 8/7 (B) | 50 | — | 323 |
| 8 | `marslab/ros2_bridge/odometry_publisher.py::publish_odometry` | — | — | 100% | 147 |
| 9 | `marslab/terrain/elevation_loader.py::load_terrain_elevation` | 12 (C) | — | 100% | 120 |
| 10 | `marslab/math/quaternion.py` | — | 56 | 94% | — |

### B2. 정성 분석 (Fowler code smells)

`code-quality-reviewer` 에이전트 1-pass 요약:

| # | 주요 Smell | 진단 요약 | 권장 |
|---|---|---|---|
| 1 | long-method, data-clump | Isaac Sim import 순서 제약으로 선형 서사가 고정. 내부는 이미 facade 로 분해됨. | **Do-Not-Refactor** |
| 2 | long-parameter-list (LoopContext 30+) | MI=43 은 dataclass docstring 밀도의 착시. Oracle parity 요구로 필드 축소 위험. | **Do-Not-Refactor** |
| 3 | long-method, duplicate-code | atmosphere update 블록이 `main_loop._update_atmosphere`와 중복. | **Quick win (≤1일)** — `_step_atmosphere` 헬퍼 추출만 |
| 4 | none (이미 분해됨) | `_build_cave_scene`/`_build_heightmap_scene`/`_place_rocks_if_enabled` 이미 분해. coverage 18% 는 P3상 정상. | **Do-Not-Refactor** |
| 5 | long-method, primitive-obsession | markdown 문자열 append 템플릿 제너레이터. 단명 개발 도구. | **Deferred v2.0** (Jinja2 전환 고려) |
| 6 | long-method, duplicate-code (noise normalize 6회) | `_generate_canyon` 118줄. 동일 sigma/amplitude 정규화 패턴 반복. | **Quick win (≤1일)** — `_normalize_noise()` 헬퍼만 추출 |
| 7 | large-class (선언적) | pydantic schema 본성상 LOC=contract. 과학 문헌 1:1 매핑. | **Do-Not-Refactor** |
| 8 | none (현 파일) | ⚠ 정량지표가 main_loop 의 `_publish_odometry`를 여기로 오귀속했을 가능성. 현 파일은 건전. | **Do-Not-Refactor** |
| 9 | long-method, feature-envy | 3개 source(procedural/cave/hirise) dispatch + dict `.get()` 접근이 공존. | **Quick win (≤1일)** — `_load_*` 3개 분해. pydantic 전환은 별건. |
| 10 | duplicate-code (main_loop 중복) | quaternion 이 이미 single source of truth. main_loop L190–210 로컬 사본 잔존. | **Quick win (≤1일)** — 로컬 사본 삭제 + import 교체 |

### B3. 권장 작업 순서

**Quick wins (총 3–4일)** — 논문 deadline(2026-06-16) 전 여유 있음:

1. **#10 quaternion dedup** — main_loop.py L190–210 제거, `from marslab.math.quaternion import ...` 교체. 가장 먼저 해야 할 이유: 다른 hotspot 수정 시 drift 방지.
2. **#9 elevation_loader dispatch 분해** — `_load_procedural`/`_load_cave`/`_load_hirise`. 가독성 즉각 개선.
3. **#3 stage2_loop `_step_atmosphere` 헬퍼 추출** — `main_loop._update_atmosphere`와 중복 축이 명시적으로 드러남. **공용화는 아직 보류** (premature abstraction 리스크).
4. **#6 `_normalize_noise()` 헬퍼** — procedural_generator 6곳 정규화 패턴 통일.

**Medium (2–5일, 선택)**
- **#9 pydantic 전환** — elevation_loader 의 `terrain_cfg.get()` dict 접근을 `TerrainConfig` 사용으로. G5 정신 강화.

**Deferred v2.0+**
- **#5 Jinja2 템플릿화** — 개발 도구는 v2.0 청소 대상.
- **#4 stage2_scene** 은 이미 이상적이며, 추가 최적화 요구가 생길 때만.

### B4. 하지 말 것 (리팩토링 비용 > 효용)

| # | 이유 |
|---|---|
| 1 `run_stage4.py::main` | Oracle twin 동등성 + Isaac Sim import 순서 제약. 분해 시 diff noise 만 증가. |
| 2 `main_loop.py` LoopContext | Oracle parity + P3 callable injection 은 설계상 불가피. MI=43 은 착시. |
| 4 `stage2_scene.py` | 이미 이상적 분해. |
| 5 `generate_instruction_index.py` | 단명 개발 도구. v2.0 에서 Jinja2 전환 고려. |
| 7 `config/schema/terrain.py` | pydantic 선언적 특성상 LOC=contract. 분해 시 오히려 손해. |
| `run_stage3_monolithic.py` (목록 외) | **Oracle diff=0 twin, 절대 수정 금지** (user memory). |

### B5. 우선순위 재배치 — Critical 관찰

정량 지표가 놓친 **high-severity 2건**:

1. **🔴 high — `marslab/runtime/main_loop.py::_publish_odometry` silent swallow (L513-518)**
   ```python
   except Exception as odom_exc:
       ...
       if step_count < 120:
           print(...)
   ```
   **step 120 이후 모든 odometry 실패가 완전히 묵살된다.** CLAUDE.md "Never silently swallow exceptions. Never use bare except." 위반. 논문 실험 중 silent data loss 위험.
   → **최소 `logging.error` + 주기적 warn 패턴 필요.** 본 리포트의 여타 항목보다 **우선순위 가장 높음.**

2. **🟠 high — quaternion ↔ main_loop 중복 (B2 #10)**
   pylint 이 명시 경고. quaternion 버그 수정 시 drift 위험.
   → B3 순서 1번으로 이미 반영.

---

## Part C — Reference Mapping

사용자가 제시한 출처 중 **이 리포트에 실제로 적용된 것 vs 적용 안 된 이유**:

| 출처 | 적용 여부 | 비고 |
|---|---|---|
| McCabe (1976) CC | ✅ 적용 | radon cc + lizard 교차검증 |
| Halstead (1977) | ✅ 적용 | radon hal, effort 상위 확인 |
| Oman & Hagemeister (1992) MI | ✅ 적용 | radon mi + Microsoft VS 스케일 병기 |
| Campbell (2018) Cognitive Complexity | ⬜ 미측정 | radon 미지원. ruff 플러그인 필요. 비용 대비 효용 판단. |
| Chidamber & Kemerer (1994) CK metrics | ❌ 미적용 | MarsLab 은 dataclass+pure function 중심. OO 전제 부적합. |
| Fowler (2018) *Refactoring* Ch.3 | ✅ 적용 | Part B2 정성 smell 태깅 |
| Myers (2011) Coverage | ✅ 적용 | line coverage 스냅샷 |
| Fowler (2012) "TestCoverage" 경고 | ✅ 반영 | 숫자 게이트 아님, 참고용만 |
| Letouzey (2012) SQALE | ❌ 미적용 | SonarCloud 연동 필요. 이번은 1회 측정 범위 아님. |
| Jia & Harman (2011) Mutation Testing | ❌ 미적용 | 일회성 측정 범위 아님 (Tier C). |
| Williams et al. (2009) Roofline | ❌ 미적용 | 성능 프로파일링 범위 아님. |
| Knuth (1974) | ✅ 정신적으로 반영 | Do-Not-Refactor 근거. |
| Forsgren et al. (2018) DORA | ❌ 미적용 | 1인 팀 + 일회성 측정 범위 아님. |
| Forsgren et al. (2021) SPACE | ❌ 미적용 | 동일. |
| Ford et al. (2017) Fitness Functions | ❌ 미적용 | CI 게이트 도입 시만 의미. 이번 범위 아님. |
| Martin (2002, 2008) SOLID / Clean Code | ✅ 에이전트 heuristic | Part B 정성 리뷰에 암묵 반영. |
| AUTOSAR C++14 / MISRA C++ | ❌ 해당 없음 | Python 프로젝트. |

**결론:** 사용자가 가져온 16개 레퍼런스 중 **7개만** 본 1회 측정에 의미 있게 적용됐다. 나머지 9개는 부적합(언어/패러다임), 또는 "지속 게이트 도입 시에만 의미" 인 지표들이다. 이는 **"레퍼런스 카탈로그 ≠ 체크리스트"** 라는 초반 논의와 일치한다.

---

## 다음 단계 (이 리포트 범위 밖)

- **즉시:** B5 silent swallow 패치 여부 결정 (논문 실험 신뢰성 영향).
- **논문 deadline 전:** B3 Quick wins 3–4건 처리 여부 결정 (예상 총 3–4일).
- **논문 이후:** Tier A/B 게이트 CI 도입 여부 재검토. 본 리포트가 baseline 으로 기능.
- **v2.0:** 개발 도구 (#5 generate_instruction_index) Jinja2 전환.

---

*본 리포트는 측정 데이터 기반이며, 수치가 아닌 Part B2/B5 의 정성 관찰이 실제 리팩토링 의사결정의 근거가 된다. — Fowler*
