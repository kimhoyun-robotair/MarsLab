# R1-R8+P1 이후 삭제 파일 목록

> 조사 일시: 2026-04-23 / subagent 12개 전수조사 결과 중 **파일/디렉토리 통째 삭제** 대상만 추림.
> 모든 `rm` / `git rm` 은 사용자가 직접 실행.

## marslab/

- [x] `marslab/sensors/rover_rig.py` — 호출부 0건, `sensor_spawner.py` (R4-2) 가 대체.

## scripts/

- [x] `scripts/phase1/ackermann.py` — 2026-04-23 Oracle 배제 override. 3 consumer (`tests/unit/test_ackermann.py`, `scripts/phase1/run_stage3_monolithic.py`, `run_stage3_monolithic_new.py`) import 를 `marslab.robots.rover_control` 로 redirect 한 뒤 파일 전체 삭제. Oracle md5 `d4e147cd…` → `beefa12579dd43f3da27b1dae3c6f852`.
- [x] `scripts/phase1/__init__.py` — 빈 파일.
- [x] `scripts/eval/` — 빈 디렉토리.

## tests/

- [x] `tests/unit/test_nav2_waypoint_runner.py` — `pytestmark.skip` + 56줄 commented-out, 2026-04-17 이후 dead-locked.

## configs/terrain/ (고아 YAML, 어디서도 로드되지 않음)

- [x] `configs/terrain/jezero_crater.yaml` — LEGACY v0, `configs/scenarios/jezero_crater.yaml` 이 R8-3 에서 대체.
- [x] `configs/terrain/procedural_crater.yaml`
- [x] `configs/terrain/procedural_flat.yaml`
- [x] `configs/terrain/procedural_hills.yaml`

## delete_later/ (디렉토리 전체 제거)

- [x] `delete_later/schema.py`
- [x] `delete_later/scripts/run_test.py`
- [x] `delete_later/scripts/run_integration_test.py`
- [x] `delete_later/scripts/run_sensor_test.py`
- [x] `delete_later/scripts/run_multi_robot_test.py`
- [x] `delete_later/scripts/run_scene_test.py`
- [x] `delete_later/marslab/robots/rotorcraft.py`
- [x] `delete_later/marslab/robots/quadruped.py`
- [x] `delete_later/configs/robots/rover.yaml`
- [x] `delete_later/configs/robots/rotorcraft.yaml`
- [x] `delete_later/configs/robots/quadruped.yaml`
- [x] `delete_later/tests/integration/test_robot_spawn.py`
- [x] `delete_later/README.md`
- [x] `delete_later/` (디렉토리 자체)

## 루트 개인 노트

- [x] `NEW_WEEK_PLAN_KOR.md` — 2026-04-09 Week 11 예비 계획, 현 하네스로 superseded.
- [x] `실행명령어.md` — 루트 commit 된 개인 메모, 구 진입점 참조.

---

## 주석/docstring 삭제 대상 (2026-04-23 subagent 5개 전수조사)

> `feedback_no_delete_comment` 정책이 2026-04-23 retired 됨 → "DISABLED but preserved"
> 블록, "kept for history" tombstone, 완료된 R-phase 마이그레이션 transitional 주석,
> 삭제된 모듈 참조는 모두 hard-delete 대상. 라인 번호는 **조사 시점 기준**이며
> 한 파일 내 여러 블록을 순서대로 삭제하면 이후 블록 라인 번호가 위로 밀리므로
> **파일 내 아래쪽 블록부터 위로 삭제**할 것.

### scripts/phase1/

- [x] `scripts/phase1/run_stage3_monolithic_new.py` L241 — `import omni.usd  # noqa: E402,F401  # kept for parity with DISABLED R4-1 block` → parity 대상 (DISABLED R4-1) 가 이미 사라졌으므로 F401 근거 소실. `import omni.usd` 자체 + 주석 제거.
- [x] `scripts/phase1/run_stage3_monolithic_new.py` L75-L79 — "R3-A1: rpy_to_quat relocated ... DISABLED but preserved as a comment per feedback_no_delete_comment" 주석 블록. 실제 함수는 L79 active import 로 대체됨. 주석만 dead.
- [x] `scripts/phase1/run_stage3_monolithic_new.py` L49 — `import argparse  # noqa: F401  # kept for DISABLED block type reference`. DISABLED 블록 참조 근거 소실.

### marslab/config/

- [x] `marslab/config/schema/mars_env.py` L4 — `delete_later/schema.py` 참조. `delete_later/` 디렉토리는 오늘 통째 삭제됨.
- [x] `marslab/config/schema/rendering.py` L212-L216 — R2-A1 PathTracingConfig 마이그레이션 레거시 필드 설명 주석.
- [x] `marslab/config/schema/rendering.py` L265-L280 — R2-A1 RayTracing/Fog 12 flat → 4 nested 마이그레이션 설명 주석. `_migrate_flat_to_nested()` 검증기에 이미 구현됨.
- [x] `marslab/config/schema/robot.py` L186-L187 — `feedback_no_delete_comment` 언급 주석. 정책 폐기.

### marslab/ros2_bridge/

- [x] `marslab/ros2_bridge/__init__.py` L19-L20 — "original definitions are preserved as DISABLED comments below per feedback_no_delete_comment" 주석. 정작 아래(L55까지)에 DISABLED 블록 없음 → 참조 자체가 stale.

### marslab/runtime/ (R7-2 stage2 split transitional notes)

- [x] `marslab/runtime/stage2_boot.py` L14-L16 — "removed DISABLED-R3-A* parity comments as part of the split" 완료된 마이그레이션 설명.
- [x] `marslab/runtime/stage2_loop.py` L13-L15 — 동일한 R7-2 transitional note.
- [x] `marslab/runtime/stage2_scene.py` L11-L13 — 동일한 R7-2 transitional note.

### marslab/robots/

- [x] `marslab/robots/rover_control.py` L3 — docstring "replaces the scripts/phase1/ackermann.py one-off script". shim 은 2026-04-23 삭제됨 → historical artifact.
- [x] `marslab/robots/drive_api_setup.py` L11-L12 — "Per feedback_no_delete_comment, the original function bodies in rover.py are retained as #-commented blocks". 정책 폐기 + 실제 블록은 이미 사라짐.
- [x] `marslab/robots/rover.py` L45-L46 — "retained below as #-commented DISABLED blocks per feedback_no_delete_comment". 실제 DISABLED 블록이 파일에 존재하지 않음.
- [x] `marslab/robots/rover.py` L33 — `import numpy as np  # noqa: F401  # kept for parity with DISABLED reinforce_pd_gains body`. DISABLED 블록 소실 → F401 근거 무효. numpy 가 실제 사용되면 noqa 만 제거, 아니면 import 전체 제거.

### marslab/sensors/

- [x] `marslab/sensors/sensor_spawner.py` L6 — "pre-R4-2 revision)" 시점 표기. R4-2 완료 이후 의미 없음.

### marslab/rendering/

- [x] `marslab/rendering/render_settings.py` L28-L32 — R2-A1 flat → nested 마이그레이션 설명.
- [x] `marslab/rendering/render_settings.py` L38-L41 — "Pre-R2-A1 flat reads (kept for traceability)" 주석 블록 (spp/total_spp/max_bounces read-back).
- [x] `marslab/rendering/render_settings.py` L45 — "Pre-R2-A1: rendering_config.denoiser_optix_pathtracing" 한 줄 마이그레이션 메모.
- [x] `marslab/rendering/render_settings.py` L59-L69 — "Pre-R2-A1 flat reads (kept for traceability)" 주석 블록 (denoiser/antialiasing/dlss read-back).
- [x] `marslab/rendering/atmosphere_fog.py` L37-L40 — R2-A1 fog_* 마이그레이션 설명 + "kept as comments per feedback_no_delete_comment".
- [x] `marslab/rendering/atmosphere_fog.py` L53-L56 — "Legacy flat-field writes (pre R2-A1), preserved for diffable review" 주석 블록.

### marslab/environment/

- [x] `marslab/environment/sky_dome.py` L18-L26 — R2-A1 butterscotch 상수 마이그레이션 설명 + `# _CLEAR_SKY_RGB = (0.76, 0.57, 0.35)` dead constant.
- [x] `marslab/environment/sky_dome.py` L62-L65 — docstring "pre-R2-A1 defaults ... bit-for-bit identical" Oracle 호환 설명. Oracle 도 오늘 수정됨 → 전제 무효.
- [x] `marslab/environment/sky_dome.py` L88 — `# Pre-R2-A1: brightness = max(0.1, 1.0 - 0.3 * t)` 이전 수식 주석.

### configs/

- [x] `configs/mars_env.yaml` L60-L66 — 주석 처리된 flat rendering 키 (spp/total_spp/max_bounces). R2-A1 에서 `rendering.path_tracing` 블록으로 이전. pydantic pre-validator 가 legacy flat key 수용하므로 YAML 주석은 duplicate dead schema.
- [x] `configs/mars_env.yaml` L81-L90 — 주석 처리된 flat rendering 키 (antialiasing_op, dlss_exec_mode, fog_*, denoiser_*). R2-A1 에서 fog/ray_tracing/path_tracing/sky_dome 로 분할.

### refactoring/ (R4/Open-question/Risks 의 정책 인용)

- [x] `refactoring/R4_cleanup_checklist.md` L28-L50 — §6 "Policy option recap" (Option A/B/C) 전체. `feedback_no_delete_comment` 정책 자체가 2026-04-23 에 retired 됨 → decision-tree dead.
- [x] `refactoring/R4_cleanup_checklist.md` L266-L271 — v2 Policy retirement draft. 정책 폐기 확정 이후 현업 가이드 역할 소실.
- [x] `refactoring/R4_cleanup_checklist.md` L14 — 정책을 active constraint 로 서술한 테이블 셀. L3 에서 이미 "retired" 로 선언된 것과 시제 충돌.
- [x] `refactoring/_delete_ok.md` L113-L127 — 14개 PNG 보존 근거를 `feedback_no_delete_comment` 에 의존. 정책 retire 후 근거 재작성 필요 (또는 삭제).
- [x] `refactoring/_delete_ok.md` L6 — `status: T6 초판` (2026-04-21). 2026-04-23 master refactor 완료 반영 안 됨.
- [x] `refactoring/_open_question.md` L313-L316 — §2.4-#22 `run_ros2_test` 의사결정 근거가 폐기 정책.
- [x] `refactoring/_open_question.md` L389-L391 — §2.5-#13 Blender `os.remove` 의사결정 근거가 폐기 정책.
- [x] `refactoring/_risks.md` L28 — §1.1 "마이그레이션 언급에서 MEMORY feedback_no_delete_comment 준수" 현재형 서술.
- [x] `refactoring/_risks.md` L90 — §2 "feedback_no_delete_comment 에 따라 삭제가 아닌 주석 처리" 현재형 서술.

### PLAN.md (사라진 소스 모듈 참조)

- [x] `PLAN.md` L216 — `marslab/ros2_bridge/topic_config.py` Architecture 트리 엔트리. 해당 파일은 2026-04-22 R4-7 에서 delete_later 격리, 오늘 삭제됨.
- [x] `PLAN.md` L230-L233 — `marslab/utils/seed.py` 엔트리. R1 에서 완전 삭제됨.
- [x] `PLAN.md` L247 — `tests/unit/test_seed.py` 엔트리. R1 에서 완전 삭제됨.

### work_log/ (LOG.md / rover_generation.md 제외)

- [x] `work_log/scenario_asset_strategy.md` L42-L46 — "사용자 확인 필요사항" 3개 pending 항목 (Product ID 유효성, 파일 크기, Cerberus vs Coprates). 2026-04-16 이후 최종 결정 미기재 → 해소 or 파일 폐기.
- [x] `work_log/slam_candidates.md` L1-L8 — "Reference document. Not a commitment" 서두와 본문 6 후보 비교 사이 범위 불일치. 문서 목적 재정의 or 통째 archival.

### R8_P1_deletion_checklist.md 자체 업데이트

- [x] `refactoring/R8_P1_deletion_checklist.md` L53 — "절대 삭제 금지" 섹션의 Oracle md5 표기. 오늘 `d4e147cd…` → `beefa12579dd43f3da27b1dae3c6f852` 로 이전됨을 명시.

---

## 절대 삭제 금지

- `scripts/phase1/run_stage3_monolithic.py` (Oracle md5 `beefa12579dd43f3da27b1dae3c6f852` — 2026-04-23 사용자 승인 1회 override 후 새 md5 고정. 이전 md5 `d4e147cd2345f927db18c4d7ad33b854` 는 historical reference)
- `work_log/LOG.md` (G8 append-only)
- `work_log/rover_generation/rover_generation.md`
- `.claude/agents/` 6개, `.claude/skills/` 10개
- `refactoring/R6_modularization_report.md`
