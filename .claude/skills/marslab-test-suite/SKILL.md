---
name: marslab-test-suite
description: "MarsLab 통합 테스트 스위트 운영. black + ruff + pytest 3종 자동 실행, visual inspection checklist 진행, IMU 중력 검증(z=3.72±0.05) 점검, Beer's law 5%·Golombek SFD 10% 정합성 확인, work_log/LOG.md 엔트리 자동 생성. 'pytest 돌려', 'lint 돌려', '테스트 다시', 'LOG 갱신', 'visual inspection', 'QA 회귀', '주차 마무리 검증', '테스트 회귀' 요청 시 반드시 사용."
---

# marslab-test-suite — MarsLab 통합 테스트 스위트

MarsLab 모든 모듈에 대해 black/ruff/pytest 3종을 일관되게 실행하고, 핵심 수용 기준을 점검하며, work_log/LOG.md를 PLAN.md §7.2 템플릿에 맞게 작성하는 워크플로우.

## Why this matters
CLAUDE.md "Coding Standards"는 **모든 변경 전에 black + ruff + pytest 3종 통과**를 명시한다. 사용자 메모리는 LOG.md 엔트리에 plan + 결정안을 포함하라고 한다. 이 스킬은 이 두 요구사항을 매 작업 종료 시 자동으로 적용한다.

## 워크플로우

### Step 1: 정적 검사 3종
```bash
black --check marslab/ scripts/ tests/
ruff check marslab/ scripts/ tests/
python3 -m pytest tests/unit/ -v
```

- 실패하면 자동 수정 가능한 부분만 적용:
  ```bash
  black marslab/ scripts/ tests/
  ruff check --fix marslab/ scripts/ tests/
  ```
- 자동 수정 후 다시 3종 실행하여 **모두 0 에러**가 나야 통과.
- 통과/실패 결과를 `_workspace/{wk}_test_3suite.txt`에 저장.

### Step 2: 핵심 수용 기준 점검 (오프라인)

다음 unit test가 PASS인지 확인:
- `test_config_loader.py` — pydantic schema validation
- `test_robot_config.py` — URDF 경로·spawn 위치
- `test_beers_law.py` — NASA TM-102299 5% 이내
- `test_diffuse_fraction.py` — COMIMART 식
- `test_sky_dome_rgb.py` — butterscotch 범위
- `test_rock_placer.py` — Golombek SFD 10% 이내
- `test_seed_determinism.py` — 동일 seed = 동일 출력

각 테스트의 PASS/FAIL을 표로 정리해 `_workspace/{wk}_acceptance_criteria.md`에 기록.

### Step 3: Visual inspection checklist 진행
- `tests/visual_inspection/checklist.md` 읽기
- 해당 주차의 신규 항목 추가 (예: Wk1 → "rover settles on terrain stably")
- 사용자에게 항목별 시각 확인 요청 (Isaac Sim 실행 후 스크린샷 또는 동영상)
- 결과를 체크리스트에 ✅/❌로 마킹 + 비고

### Step 4: Integration test (사용자 실행 요청)
- 사용자에게 다음 요청:
  ```
  cd /home/hoyunkim/MarsLab
  pytest tests/integration/ -v --no-header
  ```
- **THE critical test**: `test_imu_gravity` — IMU z축 = 3.72 ± 0.05 m/s²
- 결과를 `_workspace/{wk}_integration_test_log.md`에 저장

### Step 5: PLAN/LOG drift 점검
- PLAN.md §5.3에서 해당 주차 작업 목록 Read
- 각 작업이 실제 commit/파일에 반영되었는지 확인
- 미반영(drift) 발견 시 사용자에 보고, **PLAN.md 임의 수정 금지** (사용자 동적 우선순위 원칙).

### Step 6: LOG.md 엔트리 작성

PLAN.md §7.2 템플릿 기반, 사용자 메모리(plan + 결정안 포함) 적용:

```markdown
## [YYYY-MM-DD] Wk{N}: {Phase Title}

### 원래 계획 (PLAN.md §5.3 기준)
- {Wk N 작업 목록 인용}

### Plan Mode 결정안 (있다면)
- {plan mode에서 사용자가 승인한 설계 결정}

### What Was Done
- {파일별 변경 요약, 코드 스니펫 일부 인용 가능}

### Key Decisions
- {선택지 → 채택안 + 근거}

### Test Results
- 3-suite (black/ruff/pytest unit): {n}/{n} pass
- 수용 기준: Beer's law {%}, SFD {%}, IMU z = {value} m/s²
- Integration test: {pass/fail/사용자 실행 결과}
- Visual inspection: {n}/{n} ✅

### Blockers / Issues
- {open issue, 다음 주차로 carry-over}

### Next Steps
- {Wk{N+1} 시작 시 우선 작업}
```

엔트리는 `work_log/LOG.md` 에 **append-only** (기존 내용 수정 금지, 끝에 추가).

### Step 7: 사용자 보고
- 3종 결과 + 수용 기준 + drift 요약을 한 화면 리포트로 사용자에게 출력
- "다음 주차 진행할까요?" 질문으로 G10 user review gate

## 안전 원칙
- 테스트 실패를 임의로 skip 하거나 xfail 표기 금지. 실패는 기록.
- LOG.md는 append-only. 과거 엔트리 수정 금지.
- pytest 인수에 `--ignore=` 같은 우회 옵션 사용 금지(원인 모를 때).
- pip 사용 시 `--break-system-packages` 플래그.
- venv 생성 금지.

## 후속 작업 키워드
"테스트 다시", "lint 다시", "LOG 갱신", "주차 마감 검증", "회귀 점검", "수용 기준 다시 확인" 후속 요청에 사용. 매 호출 시 이전 `_workspace/{prev_wk}_*` 결과와 비교.

## 테스트 프롬프트
1. "Wk1 마무리 — 3종 테스트 + LOG 갱신해줘."
2. "Beer's law test 회귀 점검."
3. "지난 주 LOG에 추가할 항목 정리."
