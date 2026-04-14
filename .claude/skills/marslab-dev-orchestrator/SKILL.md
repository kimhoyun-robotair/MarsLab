---
name: marslab-dev-orchestrator
description: "MarsLab iSpaRo 2026 v1.0 개발 오케스트레이터. 6명 에이전트 팀(robotics-mobility-lead, scenario-terrain-architect, atmosphere-rendering-specialist, slam-nav-integrator, qa-validator, code-quality-reviewer)을 구성하여 PLAN.md §5.3 8주 스케줄을 주차별로 실행. Wk1~Wk6의 Rover URDF, ROS2 브리지, 7개 mission scenario, 동적 대기, SLAM/Nav2 통합, 벤치마크, 논문 figure 작업을 자동 분배. 'Wk{N} 시작', 'Wk{N} 진행', '다음 주차', 'URDF 수정', 'rover 안정화', 'scenario 추가', 'cmd_vel 구현', 'TF 브리지', 'odometry', 'SLAM 통합', 'Nav2 튜닝', '동적 대기', 'tau sweep', '벤치마크 돌려', '논문 figure', 'paper screenshot' 같은 v1.0 개발 요청에 사용. 후속 작업: '다시 실행', '재실행', '부분 수정', '회귀 점검', '이전 결과 개선', 'Wk{N} 다시'에도 반드시 사용. 단순 질문, 문서 오타, Wk7~8 논문 작성, v2.0/v3.0 작업은 직접 응답."
---

# marslab-dev-orchestrator — MarsLab v1.0 개발팀 오케스트레이터

iSpaRo 2026 v1.0 (Apr 14 ~ Jun 16) 8주 개발을 6명 에이전트 팀으로 조율한다.

## 실행 모드: 에이전트 팀 (6명)

`TeamCreate` + `TaskCreate` + `SendMessage`로 자체 조율. 모든 Agent 호출에 `model: "opus"` 명시.

## 에이전트 구성

| 팀원 | 타입 | 역할 | 주 담당 주차 | 산출 경로 |
|------|------|------|------------|----------|
| `robotics-mobility-lead` | 커스텀 | URDF 동적 물리, ROS2 cmd_vel/TF/odom | Wk1, Wk2 | `marslab/robots/`, `marslab/ros2_bridge/` |
| `scenario-terrain-architect` | 커스텀 | DEM crop, rock, structure_loader, scenario YAML | Wk2, Wk4, Wk5 | `marslab/terrain/`, `configs/scenarios/` |
| `atmosphere-rendering-specialist` | 커스텀 | dynamic sun/τ/fog, cave lighting, paper figure | Wk3, Wk5, Wk6 | `marslab/environment/`, `marslab/rendering/`, `paper/figures/` |
| `slam-nav-integrator` | 커스텀 | slam_toolbox, Nav2, ATE/RPE 벤치마크 | Wk3, Wk4, Wk6 | `configs/slam/`, `configs/nav2/`, `scripts/benchmark/` |
| `qa-validator` | general-purpose | unit test, visual inspection, LOG.md | 전 주차 연속 | `tests/`, `work_log/LOG.md` |
| `code-quality-reviewer` | general-purpose | 코드 품질·보안·anti-pattern 감사 | 전 주차 연속 | `_workspace/reviews/` |

## 워크플로우

### Phase 0: 컨텍스트 확인 (후속 작업 지원)

`MarsLab/_workspace/` 디렉토리 존재 여부를 확인하여 실행 모드 결정:

1. **`_workspace/` 미존재** → 초기 실행. Phase 1로 진행, 디렉토리 생성.
2. **`_workspace/` 존재 + 사용자가 부분 수정 요청** → 부분 재실행. 해당 에이전트만 재호출, 기존 산출물 보존.
3. **`_workspace/` 존재 + 사용자가 새 주차 시작** → 신규 주차 진행. 이전 주차 산출물은 그대로 두고 새 파일 생성.
4. **`_workspace/` 존재 + 사용자가 처음부터 다시 요청** → 기존 `_workspace/` 를 `_workspace_{YYYYMMDD_HHMMSS}/` 로 이동 후 새로 시작.

부분 재실행 시 이전 산출물 경로를 에이전트 프롬프트에 명시하여, 에이전트가 Read로 컨텍스트 복원 후 증분 수정.

### Phase 1: 주차 파악 및 작업 등록

1. PLAN.md §5.3 을 Read하여 사용자가 진행하려는 주차(Wk1~Wk8) 식별.
2. 해당 주차의 작업 표(예: Wk1은 Rover URDF 4개 작업)를 추출.
3. `TaskCreate` 로 작업 등록. 필드:
   - `subject`: 작업 제목
   - `description`: PLAN.md 인용 + 파일 경로 + 가이드라인 G번호
   - `metadata.week`: "Wk1"
   - `metadata.guideline`: "G4" 등
4. `TaskUpdate` `addBlockedBy` 로 의존 관계 설정 (8주 DAG):
   ```
   Wk1 Rover URDF ─┬─▶ Wk2 cmd_vel/TF/odom ─┬─▶ Wk3 SLAM ─▶ Wk4 Nav2 ─▶ Wk6 benchmark
                   └─▶ Wk2 scenarios 1-3 ───┘                   │
                                              Wk4 structure_loader ─▶ Wk5 scenarios 4-7
                                                                       │
                                                                Wk6 figures ─▶ Wk7 paper
   ```

### Phase 2: 팀 구성

1. `TeamCreate`:
   ```
   team_name: "marslab-v1-dev"
   members:
     - { name: "robotics-mobility-lead", agent_type: "robotics-mobility-lead", model: "opus", prompt: "..." }
     - { name: "scenario-terrain-architect", agent_type: "scenario-terrain-architect", model: "opus", prompt: "..." }
     - { name: "atmosphere-rendering-specialist", agent_type: "atmosphere-rendering-specialist", model: "opus", prompt: "..." }
     - { name: "slam-nav-integrator", agent_type: "slam-nav-integrator", model: "opus", prompt: "..." }
     - { name: "qa-validator", agent_type: "general-purpose", model: "opus", prompt: "...에이전트 정의 .claude/agents/qa-validator.md 를 Read로 로드한 뒤 그 역할로 동작" }
     - { name: "code-quality-reviewer", agent_type: "general-purpose", model: "opus", prompt: "...에이전트 정의 .claude/agents/code-quality-reviewer.md 를 Read로 로드한 뒤 그 역할로 동작" }
   ```
   - 커스텀 타입(`robotics-mobility-lead` 등)은 `.claude/agents/{name}.md` 가 존재하면 자동 로드.
   - general-purpose 타입에는 프롬프트에 "에이전트 정의 .md 파일을 먼저 Read 후 그 역할로 동작" 명시.

2. 작업 할당: 각 작업에 `TaskUpdate(owner: "{teammate}")` 로 owner 지정.

### Phase 3: 주차 실행

**실행 방식: 팀원 자체 조율**

팀원들은 공유 작업 목록에서 자기 owner 작업을 진행하고, 다음 통신 규칙으로 협업:

- **robotics-mobility-lead ↔ slam-nav-integrator**: ROS2 토픽 스펙(`_workspace/ros2_topic_spec.md`) 공유
- **scenario-terrain-architect ↔ atmosphere-rendering-specialist**: scenario 별 lighting 조건 협의
- **qa-validator ↔ 전원**: 모듈 완료 직후 incremental QA, 결과를 SendMessage로 전달
- **code-quality-reviewer ↔ 전원**: 코드 변경 직후 review pass, 심각도별 issue를 SendMessage. critical 시 작업 blocked 요청.

**리더(오케스트레이터) 모니터링:**
- 팀원 idle 알림 수신 → 다음 작업 할당 또는 다른 팀원과 연결
- TaskGet으로 진행률 확인
- critical issue alert 수신 → 사용자에 보고

**주차 체크포인트** (G10 user review gate): Wk1, Wk2, Wk3, Wk4, Wk6, Wk8 종료 시 사용자 리뷰 요청.

### Phase 4: 주차 완료 처리

1. 모든 owner 작업이 completed 상태인지 TaskList 확인.
2. `qa-validator`에게 LOG.md 엔트리 작성 요청 — `marslab-test-suite` 스킬을 사용하도록 지시.
3. `code-quality-reviewer`에게 주차 종합 리뷰 요청 — `_workspace/reviews/{wk}_weekly_summary.md`.
4. 산출물 경로 정리:
   - 코드 변경: `marslab/`, `scripts/`, `configs/`, `tests/`
   - 중간 산출물: `_workspace/{wk}_*.md`, `_workspace/reviews/{wk}_*.md`
   - LOG: `work_log/LOG.md` append
5. 사용자에 주차 완료 보고 + 다음 주차 우선순위 확인 (PLAN.md 동적 원칙).

### Phase 5: 다음 주차 준비 또는 팀 정리

- **다음 주차 진행**: 동일 팀 유지, Phase 1로 돌아가 새 주차 작업 등록.
- **Wk6 완료 후**: 개발 팀 해체. `TeamDelete` 후 `qa-validator` + `code-quality-reviewer` 만 잔존시키고 Wk7~8 논문 작성을 사용자 직접 주도.
- **사용자 종료 요청**: `TeamDelete`, `_workspace/` 보존(삭제 금지).

## 데이터 흐름

```
[오케스트레이터]
  ↓ TeamCreate(6 members) + TaskCreate(주차 작업)
[팀]
  ├─ robotics-mobility-lead ─┐
  ├─ scenario-terrain-arch  ─┤
  ├─ atmosphere-rendering   ─┼─→ _workspace/{wk}_*.md
  ├─ slam-nav-integrator    ─┘                │
  │                                           ↓
  ├─ qa-validator ←───────────── incremental QA
  │     │
  │     └→ work_log/LOG.md (append)
  │
  └─ code-quality-reviewer ←──── code review pass
        │
        └→ _workspace/reviews/{wk}_*.md
              │
              └─ critical → SendMessage → 오케스트레이터 → 사용자 alert
```

## 에러 핸들링

| 상황 | 전략 |
|------|------|
| 팀원 1명 실패/중지 | SendMessage로 상태 확인 → 1회 재시작. 재실패 시 해당 작업 누락 표기 후 진행. |
| critical 보안/IMU 실패 | code-quality-reviewer 또는 qa-validator의 alert 즉시 사용자 보고. 작업 blocked 전환. |
| 팀원 간 데이터 충돌 | 출처 명시하여 양쪽 산출물 모두 `_workspace/` 보존. 사용자 결정 대기. |
| Isaac Sim integration test 실패 | 사용자 직접 실행 결과를 받아 LOG에 기록. 임의 fallback 금지. |
| 작업 의존성 순환 | TaskList 점검 후 사용자에 보고. 자동 해결 금지. |
| PLAN.md drift 감지 | qa-validator 가 사용자 보고. PLAN.md 임의 수정 금지. |
| 외부 ROS2 패키지 버전 불일치 | 사용자에게 환경 확인 요청. 임의 업그레이드 금지. |

## 데이터 전달 프로토콜

- **태스크 기반**: `TaskCreate`/`TaskUpdate`/`TaskList` 로 진행 추적
- **메시지 기반**: `SendMessage` 로 팀원 간 직접 통신 (실시간 협업)
- **파일 기반**: `_workspace/` 디렉토리 (중간 산출물 보존, 감사 추적)
  - 명명: `{wk}_{agent}_{artifact}.{ext}` 예: `wk1_robotics_urdf_baseline.md`
  - 코드 리뷰: `_workspace/reviews/{wk}_{agent}_{module}.md`

## 후속 작업 지원

이전 결과 기반 부분 재실행 시:
1. Phase 0에서 `_workspace/` 존재 확인
2. 사용자 요청에서 "어느 주차의 어느 작업"인지 파싱
3. 해당 작업만 `TaskUpdate(status: pending, owner: ...)` 로 재할당
4. 해당 에이전트 프롬프트에 "이전 산출물 `_workspace/{file}` Read 후 증분 수정" 지시

후속 키워드(description 에 포함됨):
- 다시 실행, 재실행, 업데이트, 수정, 보완, 부분 수정, 회귀 점검
- "Wk{N} 다시", "{작업명}만 다시"
- "이전 결과 기반으로", "결과 개선"

## 테스트 시나리오

### 정상 흐름 (Wk1 시작)
1. 사용자: "Wk1 시작해줘"
2. Phase 0: `_workspace/` 미존재 확인 → 디렉토리 생성
3. Phase 1: PLAN.md §5.3 Wk1 작업 4개 추출 → TaskCreate
4. Phase 2: TeamCreate(6 members) → robotics-mobility-lead 에 4개 작업 owner 지정
5. Phase 3: robotics-mobility-lead 가 `urdf-physics-tuning` 스킬 따라 작업 수행
   - code-quality-reviewer 가 code-quality-audit 으로 review pass
   - qa-validator 가 IMU 중력 검증 준비
6. Wk1 완료 → Phase 4: LOG.md 엔트리, 주간 리뷰 리포트
7. 사용자 체크포인트 → Wk2 진행 동의 → Phase 5

### 에러 흐름 (IMU 중력 검증 실패)
1. Phase 3에서 사용자가 IMU z축 = 4.5 m/s² 보고
2. qa-validator 가 critical alert → SendMessage to 오케스트레이터
3. 오케스트레이터: Wk1의 다음 작업을 blocked로 표시 + 사용자에 보고
4. robotics-mobility-lead 가 URDF spawn orientation 재검토 (urdf-physics-tuning Step 6)
5. 사용자 재실행 → 검증 통과 → blocked 해제, Phase 4로 진행
6. LOG.md 엔트리에 "IMU 중력 검증 1차 실패 → URDF orientation 수정 → 통과" 기록

### 부분 재실행 (scenario 한 개만 다시)
1. 사용자: "Scenario rock_dense YAML 만 다시 만들어줘"
2. Phase 0: `_workspace/` 존재 확인 → 부분 재실행 모드
3. Phase 1: scenario_rock_dense 작업만 pending으로 재등록
4. scenario-terrain-architect 만 호출, dem-scenario-builder 스킬 사용, 이전 `_workspace/wk2_terrain_rock_dense_*` 를 Read로 참조
5. 결과를 동일 경로에 덮어쓰기 + 이전 버전을 `_workspace/archive/{date}/` 로 이동
6. qa-validator 가 YAML 스키마 재검증
7. 사용자 보고

## 사용자 메모리·원칙 준수 (모든 에이전트 공통)

- Isaac Sim integration test는 사용자가 직접 실행
- 오프라인 시각화 우선
- Quality before data
- 코드 비활성화는 주석 처리 (삭제 금지)
- pip은 `--break-system-packages`, venv 금지
- LOG.md 엔트리에 계획 + plan mode 결정안 포함
- PLAN.md는 동적, 매 주차 시작 시 우선순위 확인
- v2.0(photorealism)·v3.0(terramechanics, RL)은 out-of-scope
- 코드 변경 완료 전 반드시 black + ruff + pytest unit 통과
- P1 Flat Architecture는 source code에 적용. `.claude/` 인프라는 P1 미적용.
