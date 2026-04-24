# Meta-Plan: 17 Priority Items from 00_consolidated.md

## 제약
- Reviewer 2 모드 (공격적·비판적, file:line 근거 필수)
- 샘플링/압축 금지, 라인 단위 읽기
- 병렬 subagent 최대 5개
- 임시 파일: `~/MarsLab/tmp/`
- git/rm/chmod/web fetch: 사용자 승인 필요
- 수동 테스트 필요 시 일시정지

## Baseline (2026-04-24)
- 716 unit tests passing
- `run_stage3_monolithic.py` + monolithic tests 삭제 완료 (사용자)
- `reference/`, `dev/`, `codebase-analyzer-workspace/`, `PLAN.md` 삭제 완료

## 17 Items — Execution Order

### Batch 1: Isolated small fixes (5 parallel Reviewer-2 agents)
- #2  C-4  Ackermann arctan→arctan2 + 회귀 테스트     (rover_control.py:98)
- #5  C-10 CaveConfig() default ValidationError 복구  (config/schema/terrain.py)
- #11 C-5  Lognormal mean vs median rename/fix        (terrain/cave/breakdown.py:108)
- #14 C-6  stage2_loop os._exit(0) 제거 + run_stage4 동일 패턴  (runtime/stage2_loop.py:196, scripts/phase1/run_stage4.py:333)
- #6  C-16 IMU gravity assertion + offset_orientation 실제 적용 (sensors/imu.py)

### Batch 2: Science formulas (3 parallel agents)
- #1  C-1  Beer's law Kasten-Young airmass             (environment/light_intensity.py)
- #8  C-3  Sun position Allison & McEwen or rename     (environment/sun_position.py)
- #7  C-2  COMIMART 2-D or rename (Beer 종속)           (environment/diffuse_fraction.py)
  → #7은 #1 완료 후 순차

### Batch 3: Local refactor + cleanup (3 parallel)
- #9  C-9  Oracle cleanup leftover refs (주로 문서/주석)
- #13 C-7  Silent swallow 공유 helper                   (runtime/main_loop.py L341-517)
- #4  C-12 ROS2 QoS 프로파일 도입                        (ros2_bridge/*.py + schema)

### Batch 4: Schema-wide changes (순차, 테스트 대량 영향)
- #12 C-11 pydantic extra="forbid" + canyon_* 수용     (config/schema/*.py + 기본 fix)
- #17 H-17 scenario YAML mars_env 중복 제거             (configs/scenarios/*.yaml)

### Batch 5: Large refactor
- #16 C-17 Sensors Path A/B 단일화                      (camera.py/imu.py/lidar.py vs sensor_spawner.py)

### Batch 6: User approval required
- #15 C-15 tests/integration/ 재생성 + gitignore 편집   (사용자 git 개입 필요)
- #18 H-20~24 Packaging hygiene                         (pre-commit/mypy/pip-audit/CI matrix)
- #19 god-object + quaternion float64 + cave geometry   (논문 후 권장이나 이번 pass에 포함)

## 진행 로그
- Batch 1 시작: [TBD]
