---
name: code-quality-audit
description: "MarsLab 코드 품질 감사. black/ruff가 잡지 못하는 가독성, 함수 복잡도, dead code, 중복, docstring 정확성, 타입 힌트 일관성, MarsLab 특화 anti-pattern(Mars 파라미터 하드코딩 G5, OmniLRS/RLRoverLab 네이밍 G3, omni.isaac.orbit 폐기 API, bare except, silent swallow, seed 누락, 코드 삭제) 감사. 심각도별 (critical/high/medium/low) 리포트. '코드 리뷰', '코드 품질 점검', 'anti-pattern 감사', 'dead code', '복잡도 점검', '리뷰 다시', 'PR 점검' 요청 시 반드시 사용."
---

# code-quality-audit — MarsLab 코드 품질 감사 체크리스트

`code-quality-reviewer` 에이전트가 black/ruff 같은 정적 도구가 잡지 못하는 코드 품질·anti-pattern 이슈를 LLM이 직접 소스를 읽어 감사하는 워크플로우.

## Why this matters
black은 포매팅, ruff는 스타일/linting을 잡지만, **설계 결함·의도·도메인 anti-pattern**은 잡지 못한다. MarsLab의 G3/G5/P1/P3 같은 원칙은 LLM이 맥락을 이해해야 검출 가능하다. 이 스킬은 그 검출을 체계화한다.

## 체크리스트

### A. 코드 품질
- [ ] **함수 길이**: 50줄 초과 함수가 있는가? (리팩터 후보)
- [ ] **순환 복잡도**: 분기·반복 깊이 4단 이상 함수가 있는가?
- [ ] **명확한 네이밍**: `data`, `result`, `tmp`, `x` 같은 모호한 이름이 있는가?
- [ ] **Dead code**: 호출되지 않는 함수, unreachable branch, 미사용 import (ruff가 못 잡는 동적 호출 포함)
- [ ] **3회 이상 중복**: 동일 로직이 3곳 이상 반복되는가? (P1 상 섣부른 추상화 금지하나, 3+회는 신호)
- [ ] **docstring 일관성**: 파라미터·반환·예외가 실제 시그니처와 일치하는가?
- [ ] **타입 힌트**: 공개 함수에 일관되게 적용되었는가? `Any` 남용?

### B. MarsLab 특화 Anti-Pattern (CLAUDE.md, PLAN.md §9)

#### B1. G5 위반: Mars 파라미터 하드코딩
다음 값들이 Python 소스에 박혀 있는지 grep:
- `3.72` (gravity), `610` (atmo pressure), `0.020` (atmo density), `88642` (sol duration)
- `-60` (surface temp), `0.5`, `2.0`, `4.0` (tau sweep)

발견 시: severity=high, 권고="`configs/mars_env.yaml` 의 mars 섹션에서 로드"

#### B2. G3 위반: 외부 codebase 네이밍 차용
다음 키워드가 함수·클래스·변수에 등장하는지:
- `omnilrs`, `lunar_lab`, `rl_rover_lab`, `omnilrs_*`, `rover_lab_*`
- 도메인 일반 용어("rocker_bogie", "wheel_odom")는 OK, 코드베이스명이 박힌 것은 NG

발견 시: severity=high, 권고="MarsLab 컨벤션으로 재네이밍"

#### B3. 폐기 Isaac Sim API
- `omni.isaac.orbit` import → `omni.isaac.lab` 으로 교체 권고
- deprecated 표시 함수(`add_reference_to_stage_old`, 등) 사용

발견 시: severity=high

#### B4. P3 위반: Isaac Sim import in offline 모듈
다음 파일에 `import omni`, `import pxr` 있는지:
- `marslab/environment/*.py` (전부)
- `marslab/terrain/dem_loader.py`
- `marslab/terrain/rock_placer.py`
- `marslab/config/*.py`

발견 시: severity=critical, 권고="Isaac Sim 의존부를 별도 파일로 분리"

#### B5. P1 위반: premature abstraction (Phase 1)
- 플러그인 시스템, 레지스트리, god object, 추상 base class 남용
- 단일 구현체에 대한 abstract interface
- 사용처 없는 ABC

발견 시: severity=medium, 권고="현재 사용처가 0~1개라면 인라인"

#### B6. Bare except / silent swallow
- `except:` (bare)
- `except Exception: pass`
- `except ...: return None` (컨텍스트 없이)
- `try: ... except ...:` 안에서 로그·재발생 없음

발견 시: severity=critical (실패를 감추므로)

#### B7. Seed 파라미터 누락
- `random`, `np.random`, `torch.manual_seed`, `random.choice` 사용 함수
- 함수 시그니처에 `seed: int` 또는 `rng: np.random.Generator` 가 없으면 NG

발견 시: severity=high

#### B8. 코드 삭제 (사용자 원칙 위반)
- git diff에서 large block 삭제 발견
- 비활성화된 코드는 `# DISABLED (reason): ...` 주석 처리만 허용

발견 시: severity=high (삭제 대신 주석 처리하라)

### C. 의도 검증
- [ ] 함수 이름과 실제 동작이 일치하는가?
- [ ] 주석이 코드와 모순되지 않는가?
- [ ] TODO/FIXME 가 방치되었는가? (issue로 등록 권고)

## 워크플로우

### Step 1: 범위 결정
- 입력: 변경된 파일 목록(git diff) 또는 특정 모듈
- 사용자 요청이 "전수"라면 `marslab/` 전체

### Step 2: 자동 grep 패스 (B1~B8)
- 정규식·grep으로 빠른 후보 추출
- 후보 라인을 LLM이 직접 읽고 false positive 제거 (예: `3.72`가 주석에 든 경우)

### Step 3: LLM read 패스 (A, C)
- 각 파일을 읽고 함수 단위로 품질·의도 검토
- 큰 함수는 부분 단위로 분석

### Step 4: 리포트 작성
경로: `_workspace/reviews/{wk}_{agent}_{module}.md`

포맷:
```
## File: marslab/{module}/{file}.py

### Issue (severity: high, category: G5 hardcoded)
- Line 42: `gravity = 3.72`
- **Why:** G5 violation — Mars constants must come from configs/mars_env.yaml.
- **Recommendation:** Load via pydantic schema: `config.mars.gravity`.

### Issue (severity: medium, category: dead code)
- Lines 88-105: function `_legacy_normalize` not called anywhere (grep confirmed).
- **Why:** Carry-over from refactor on 2026-04-12.
- **Recommendation:** Comment out with `# DISABLED (legacy_normalize, replaced 2026-04-12): ...`. Do not delete.

...

### Summary
- critical: 0
- high: 3
- medium: 2
- low: 1
```

### Step 5: critical alert
- critical 이슈가 있으면 즉시 SendMessage로 해당 에이전트 + 오케스트레이터에 통지
- "blocked" 플래그로 작업 진행 차단 요청

### Step 6: 회귀 비교
- 이전 리뷰(`_workspace/reviews/`)를 Read하여 같은 issue 재발 여부 확인
- 재발 시 severity 한 단계 상승 + "regression" 마킹

## 안전 원칙
- 자동 수정 금지. 권고만 한다. 수정은 해당 에이전트 책임.
- false positive를 LLM read 단계에서 정직하게 제거.
- P1과의 균형: 단발 중복(2회)은 issue 아님. 3회+ 만 신호로.
- 사용자 반박 시 해당 issue를 `_workspace/reviews/resolved/` 로 이동 + 사유 기록.

## 후속 작업 키워드
"코드 리뷰 다시", "anti-pattern 다시 점검", "보안 점검 별도", "회귀 리뷰" 후속 요청 시 사용. 보안 전용은 `security-static-scan` 스킬과 분리.

## 테스트 프롬프트
1. "Wk1 변경분 전체 코드 리뷰."
2. "anti-pattern 감사 — G5 G3 P1 P3 위주로."
3. "지난 주 리뷰에서 지적한 dead code 회귀 점검."
