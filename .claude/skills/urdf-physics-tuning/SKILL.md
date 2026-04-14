---
name: urdf-physics-tuning
description: "MarsLab 로버 URDF 물리 안정화 워크플로우. fix_base=False 전환, 질량·관성 텐서·관절 한계·마찰·충돌 메시 조정, IMU 중력 검증(z=3.72±0.05 m/s²) 준비, rocker-bogie 섀시 안정화. 'URDF 고쳐줘', 'URDF 재튜닝', 'rover 안정화', 'fix_base 풀어줘', 'URDF 수정 다시', 'rover 넘어져', 'wheel 관성 조정' 등의 요청에 반드시 사용. URDF 관련 물리 이슈 디버깅 시 이 스킬을 따른다."
---

# urdf-physics-tuning — MarsLab Rover URDF 물리 안정화

MarsLab v1.0 Week 1의 **THE critical task**: rover URDF를 `fix_base=False` 하에서 Mars 중력(3.72 m/s²) 지형 위에 안정적으로 안착시키고 주행 가능하게 만드는 워크플로우.

## Why this matters
Foundation(Wk1~9 구 일정)에서 rover는 `fix_base=True`로 정적 배치만 확인했다. 동적 물리로 전환 시 모멘트·충돌·관절 한계 오류로 즉시 튀거나 관통·진동이 발생한다. `run_scene.py`와 `mars_env.yaml`에서 로봇 스폰이 주석 처리된 것은 이 이슈가 해결되지 않아서다. 이 스킬은 그 디버깅을 체계화한다.

## 워크플로우

### Step 1: 현황 읽기
1. `git log --oneline -20` 으로 rover URDF 관련 최근 commit 훑어보기
2. `assets/robots/rover/` 디렉토리의 URDF·메시 파일 목록 확인
3. `marslab/robots/rover.py` 읽기 — fix_base 로직, 스폰 API, 현재 주석 상태
4. `scripts/run_scene.py`, `configs/mars_env.yaml`의 로봇 블록 주석 상태 기록

### Step 2: 기준선 측정 (fix_base=True 상태)
1. 사용자에게 Isaac Sim을 `fix_base=True`로 1회 실행 요청
2. 확인할 로그: IMU z축 값, 관절 각도 초기값, 충돌 경고 유무
3. `_workspace/urdf_baseline_{YYYYMMDD}.md`에 결과 기록

### Step 3: 물리 파라미터 오프라인 검증
Isaac Sim 없이 다음을 체크:
- `urdfpy`로 URDF 파싱, 관성 텐서의 대각·비대각 성분 검토
- 질량 분포(rocker-bogie 무게 중심이 섀시 하단에 있는가)
- 관절 한계(상하한, effort, velocity)
- 충돌 메시 vs 시각 메시 정합성

오프라인 시각화: `trimesh`로 URDF를 로드해 matplotlib에 렌더링, `_workspace/urdf_wireframe.png` 저장 후 사용자에 공유.

### Step 4: 수정 및 검증 루프 (한 번에 하나씩)
우선순위:
1. **휠 관성**: 너무 크면 트랙션 부족, 너무 작으면 미끄럼. 기대값 계산(cylinder I = 0.5·m·r²).
2. **마찰**: 초기값을 Isaac Sim 기본 + Mars 지형 마찰 계수로. config YAML에.
3. **충돌 메시**: 시각 메시보다 단순한 convex hull로 교체(침투·클립 방지).
4. **관절 damping/stiffness**: rocker-bogie 링크의 진동 방지.
5. **질량**: 실제 MER/MSL 사양 참조(논문 참고, 복사 금지 G3).

각 변경 후 Step 2를 반복(사용자가 Isaac Sim 재실행).

### Step 5: fix_base 전환
- `marslab/robots/rover.py`에서 `fix_base=False` 전환. 기존 `True` 경로는 `# DISABLED (fix_base_true_fallback): reverted 2026-04-14`로 주석 처리(삭제 금지).
- `configs/mars_env.yaml`, `scripts/run_scene.py`의 로봇 블록 주석 해제.
- 사용자에 Isaac Sim 실행 요청, 1초·5초·30초 후 rover 상태 확인.

### Step 6: IMU 중력 검증 (THE critical test)
- 정지 상태 로버의 IMU z축 읽기 → **3.72 ± 0.05 m/s² 범위**여야 함.
- 벗어나면 URDF spawn orientation·Isaac Lab gravity 세팅 재점검.
- `qa-validator`와 `code-quality-reviewer`에 결과 공유.

### Step 7: LOG.md 엔트리
`qa-validator`가 작성하도록 결과 요약을 `_workspace/wk1_robotics_urdf_report.md`에 저장.

## 안전 원칙

- 한 번에 한 파라미터만 변경. 여러 변경 동시 적용 금지.
- 기존 작동 파라미터는 주석 처리(삭제 금지). 예: `# old_mass: 180.0  # replaced 2026-04-14`
- Mars 중력·마찰 상수는 `configs/mars_env.yaml`에서만 변경. 파이썬 하드코딩 금지(G5).
- `omni.isaac.orbit` 사용 금지 → `omni.isaac.lab`.
- 외부 오픈소스 URDF를 참고하되, 파일명·관절명·링크명을 그대로 복사하지 않는다(G3). 별도 네이밍으로 재작성.

## 후속 작업 키워드
"URDF 다시", "rover 재튜닝", "fix_base 다시", "IMU 검증 다시", "wheel 관성 조정", "rocker-bogie 진동", "마찰 재조정" 같은 후속 요청에도 이 스킬을 재실행. 단, 이전 `_workspace/urdf_baseline_*.md` 를 Read로 회귀 비교 후 증분 수정만 수행.

## 테스트 프롬프트 (2~3개)

1. "Rover URDF 불안정한데 고쳐줘. fix_base=False에서 튀어오름."
2. "IMU z축 읽기가 3.72 근처가 안 나와. 재검증."
3. "휠 관성 다시 계산해서 URDF 반영."
