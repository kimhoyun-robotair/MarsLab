---
title: Phase 1 감사 종료 시점 삭제 가능 파일 목록 (제안)
last_updated: 2026-04-21
scope: ~/MarsLab/ 전체
status: T6 초판
important: 본 문서는 제안 목록. 실제 삭제는 사용자 승인 후에만 수행.
---

# Phase 1 감사 종료 시점 삭제 가능 파일 목록 (제안)

## 주의 사항

- 본 문서는 **제안 목록일 뿐**이며, 실제 `rm`, `git clean`, `find -delete` 등은 작성 과정에서 **수행되지 않았다**.
- 각 카테고리의 삭제 이행은 사용자 판단에 따르며, 사용자 정책(`feedback_no_delete_comment`, `feedback_no_git_commands`)에 따라 에이전트는 절대 자체 삭제·git 호출을 하지 않는다.
- 카테고리 **D** 와 **E** 는 삭제 제안이 아니라 **관찰 / 경고** 항목이다.
- 검증 시각: 2026-04-21, 검증 도구: `find`, `ls`, `du`, `git status`.

---

## A. 안전 삭제 (재생성 가능 캐시)

Python/테스트/빌드 도구가 실행 시 자동 재생성하므로, 삭제해도 기능에 영향 없음.

| 대상                           | 건수   | 경로 예시                                                                        | 크기 / 비고                                 |
| ------------------------------ | ------ | -------------------------------------------------------------------------------- | ------------------------------------------- |
| `__pycache__/` (디렉터리)      | **17** | `marslab/*/__pycache__`, `scripts/*/__pycache__`, `tests/*/__pycache__`, `launch/__pycache__`, `삭제대상/utils-code/__pycache__` | 총 약 **1.70 MB** (1,784,026 B)            |
| `*.pyc`                        | **147** | `marslab/**/*.pyc` 등                                                           | `__pycache__/` 내부에 포함                  |
| `.pytest_cache/`               | 1      | `/home/hoyunkim/MarsLab/.pytest_cache/`                                          | 약 **46 KB**                                |
| `.ruff_cache/`                 | 1      | `/home/hoyunkim/MarsLab/.ruff_cache/`                                            | 약 **6 KB**                                 |
| `marslab.egg-info/`            | 1      | `/home/hoyunkim/MarsLab/marslab.egg-info/`                                       | 약 **1.3 KB**, `pip install -e .` 재실행 시 자동 재생성 |
| `build/` `install/` `log/`     | 0      | (로컬에 존재하지 않음, .gitignore 선제 패턴)                                      | 해당 없음                                    |
| `.devenv/` `.colcon_workspace` | 0      | (로컬에 존재하지 않음)                                                            | 해당 없음                                    |

**A 카테고리 총 추정 용량: 약 1.75 MB (1,839,142 B)**

복구 방법:
- `__pycache__`, `*.pyc`: Python 실행 시 자동 생성
- `.pytest_cache`: `pytest` 실행 시 자동 생성
- `.ruff_cache`: `ruff check` 실행 시 자동 생성
- `marslab.egg-info`: `pip install -e .` 로 재생성

---

## B. 조건부 삭제 (재실행 시 재다운로드/재변환 필요)

대용량 원본 데이터. 삭제하면 재다운로드 또는 재변환이 필수.

| 대상                                        | 크기      | 경로                                                                          | 복구 절차                                                       |
| ------------------------------------------- | --------- | ----------------------------------------------------------------------------- | --------------------------------------------------------------- |
| `cerberus_fossae.IMG`                       | **336 MB** | `/home/hoyunkim/MarsLab/assets/terrain/dem/cerberus_fossae.IMG`               | PDS/HiRISE 원본 다운로드 필요                                    |
| `cerberus_fossae.tif`                       | **216 MB** | `/home/hoyunkim/MarsLab/assets/terrain/dem/cerberus_fossae.tif`               | `gdal_translate` 로 `.IMG` → `.tif` 재변환 가능                   |
| `cerberus_fossae_converted/` (elevation.npy) | **336 MB** | `/home/hoyunkim/MarsLab/assets/terrain/dem/cerberus_fossae_converted/`        | `scripts/phase1/*` DEM 변환 파이프라인으로 재생성                 |
| `jezero_crater.tif`                         | 988 KB    | `/home/hoyunkim/MarsLab/assets/terrain/dem/jezero_crater.tif`                 | HiRISE DEM 원본 재다운로드 필요                                  |
| `jezero_crater_converted/` (elevation.npy)  | 988 KB    | `/home/hoyunkim/MarsLab/assets/terrain/dem/jezero_crater_converted/`          | DEM 변환 스크립트로 재생성                                       |

**B 카테고리 총 용량: 약 888 MB** (DEM 폴더 전체)

주의:
- v1.0 scenario 3/4 (Crater+Slopes, Canyon)의 재현 실험에 필요.
- 삭제 시 재실행까지 수 분~수십 분 소요 가능.
- `.gitkeep` 은 삭제하지 말 것 (디렉터리 구조 보존용).

---

## C. 개인 파일 / `.gitignore` 에 있지만 로컬 잔존

`.gitignore` 에 의해 원격 저장소에는 없으나, 로컬 디스크에만 존재하는 개인 자료. **삭제 전 사용자 승인 필수**.

| 대상                                         | 크기       | 경로                                                      | 삭제 전 확인 사항                                                |
| -------------------------------------------- | ---------- | --------------------------------------------------------- | ---------------------------------------------------------------- |
| `reference/m2020-urdf-models/`               | **109 MB** | `/home/hoyunkim/MarsLab/reference/m2020-urdf-models/`     | Mars rover URDF 원본. 재변환 시 필요 (`reference_rover_usd_source` 메모리 참조) |
| `reference/OmniLRS/`                         | 24 MB      | `/home/hoyunkim/MarsLab/reference/OmniLRS/`               | 알고리즘 학습용 참고 코드베이스. 재확인 필요 시 남김              |
| `reference/RLRoverLab/`                      | **409 MB** | `/home/hoyunkim/MarsLab/reference/RLRoverLab/`            | Isaac Lab API 패턴 학습용. v3.0 전까지 재참조 가능성              |
| `reference_paper/`                           | **125 MB** | `/home/hoyunkim/MarsLab/reference_paper/`                 | 논문 PDF 2개. 인용 시 필요                                        |
| `dev/` (10개 md)                             | 324 KB     | `/home/hoyunkim/MarsLab/dev/`                             | 초기 설계 문서 (architecture/requirements/reference 분석)         |
| `plan/` (PDF 2개)                            | 200 KB     | `/home/hoyunkim/MarsLab/plan/`                            | 주간 스케줄·v2 plan PDF. PLAN.md 와 중복될 가능성                 |
| `codebase-analyzer-workspace/`               | 52 KB      | `/home/hoyunkim/MarsLab/codebase-analyzer-workspace/`     | eval_set.json, iteration-1. 분석 기록                             |
| `내가궁금해서정리하는.md`                    | 4.3 KB     | `/home/hoyunkim/MarsLab/내가궁금해서정리하는.md`          | 개인 메모                                                          |
| `삭제대상/`                                  | 40 KB      | `/home/hoyunkim/MarsLab/삭제대상/`                        | 이름 자체가 "삭제대상". utils, utils-code 하위 포함. **사용자 이미 삭제 의도 표명**했을 가능성 |
| `skills/` (루트)                             | 소량       | `/home/hoyunkim/MarsLab/skills/codebase-analyzer`, `work-report` | `.claude/skills/` 와 다른 루트 레벨 스킬. .gitignore `/skills/` 규칙 적용 대상 |
| `work_record/`                               | 0/빈       | `/home/hoyunkim/MarsLab/work_record/`                     | 존재하지 않음(빈 패턴만). 확인 후 skip               |

**C 카테고리 총 용량: 약 667 MB** (주로 `reference/` 하위 3개 디렉터리)

확인 필요:
- `reference/` 하위는 알고리즘 inspiration 용도. 프로젝트 종료 전까지 남기는 편이 안전.
- `삭제대상/` 은 이름으로 사용자 의도가 명확하지만, 내부에 `utils`, `utils-code` 가 있어 참조 여부 확인 필요.

---

## D. 모순 관찰 (정책 불일치)

삭제 대상이 아니라 **.gitignore 정책 불일치**로 플래그만.

| 대상                                         | 문제                                                                         | 해결 방향                                                                  |
| -------------------------------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| `tests/integration/test_robot_spawn.py`      | `.gitignore` 73라인에 등재되어 있어 커밋에서 제외 — 그러나 IMU z축 중력 3.72 ± 0.05 m/s² 검증(THE critical test)용 파일. CLAUDE.md Testing Requirements 기준 필수 테스트. | `.gitignore` 에서 해당 라인 제거 또는 별도 `scripts/run_integration_test.py` 로 이관 경로 확립. **삭제 금지**. |

관찰:
- `.gitignore` 주석 72라인: "ROS2 플러그인 충돌로 인해서 pytest 실행 불가 > scripts/run_integration_test.py로 대체"
- 즉 파일을 `.gitignore` 로 추적 제외하되 내용은 유지하는 설계. 그러나 이는 새 팀원이 QA 검증 재현 시 파일을 찾지 못할 리스크가 있음.
- 현재 파일은 로컬에 3608 B로 존재. 삭제 금지.

추가 모순:
- `.gitignore` 에 `Instruction.md` (단수 파일) 및 `instruction/` (소문자) 가 등재되어 있음. 그러나 실제 프로젝트는 대문자 `Instruction/` (332 KB) 를 사용 중이며 `git status` 에서 untracked 로 표시됨. 소문자/대문자 분리로 gitignore 회피되는 상태 — 정책 의도 확인 필요.

---

## E. 사용자 정책상 삭제 금지

삭제 제안 대상이 아니며, 재확인 목적.

- **`work_log/*.png` 등 중간 산출 이미지 (14개)**: `feedback_no_delete_comment` 정책상 삭제 금지. 주요 파일:
  - `work_log/atmosphere_visualization.png`
  - `work_log/procedural_terrain_visualization.png`
  - `work_log/terrain_visualization.png`, `terrain_visualization_full.png`
  - `work_log/mars_scene_v1.png`
  - `work_log/rover_generation/depth_noise.png`
  - `work_log/scene_generation/cerberus_*.png` (4개)
  - `work_log/scene_generation/cave_preview*.png` (2개)
  - `work_log/scene_generation/dem_regions_overview.png`
  - `work_log/scene_generation/dynamic_atmosphere_visualization.png`
  - `work_log/scene_generation/procedural_canyon_preview.png`
- **`Instruction/` (대문자)**: Isaac Sim 학습용 instruction 위키 (332 KB). `feedback_instruction_wiki_pattern` 에 명시된 프로젝트 필수 컴포넌트. **삭제 금지**.
- **`tests/integration/test_robot_spawn.py`**: 위 D 참조. THE critical test 파일 — **삭제 금지**.
- **`assets/terrain/dem/.gitkeep`**: 디렉터리 구조 보존용.

---

## F. 드라이런 bash 스니펫 (사용자가 직접 실행)

```bash
# A 카테고리 — 먼저 목록 확인 (-print)
find /home/hoyunkim/MarsLab -name "__pycache__" -type d -print
find /home/hoyunkim/MarsLab -name "*.pyc" -type f -print
ls -la /home/hoyunkim/MarsLab/.pytest_cache /home/hoyunkim/MarsLab/.ruff_cache /home/hoyunkim/MarsLab/marslab.egg-info

# A 카테고리 — 실제 삭제 (사용자가 검토 후 -print 를 -delete 로 바꿔 실행)
# find /home/hoyunkim/MarsLab -name "__pycache__" -type d -exec rm -rf {} +
# find /home/hoyunkim/MarsLab -name "*.pyc" -type f -delete
# rm -rf /home/hoyunkim/MarsLab/.pytest_cache /home/hoyunkim/MarsLab/.ruff_cache
# rm -rf /home/hoyunkim/MarsLab/marslab.egg-info

# B 카테고리 — DEM (실제 삭제 전 v1.0 실험 완료 여부 반드시 확인)
# du -sh /home/hoyunkim/MarsLab/assets/terrain/dem/cerberus_fossae.IMG
# du -sh /home/hoyunkim/MarsLab/assets/terrain/dem/cerberus_fossae_converted

# C 카테고리 — 사용자 개인 자료 (승인 후에만)
# du -sh /home/hoyunkim/MarsLab/reference/* /home/hoyunkim/MarsLab/reference_paper
# du -sh /home/hoyunkim/MarsLab/dev /home/hoyunkim/MarsLab/plan /home/hoyunkim/MarsLab/삭제대상
```

실행 권고 순서: **A → 사용자 검토 → B/C** 단계별 분리. A 만으로도 1.75 MB 회수되며 리스크 0.

---

## G. 요약

| 항목                        | 값                                                      |
| --------------------------- | ------------------------------------------------------- |
| **A. 안전 삭제 건수**       | 디렉터리 20개 (`__pycache__` 17 + 캐시 3개), 파일 147개 |
| **A. 안전 삭제 용량**       | 약 **1.75 MB**                                          |
| **B. 조건부 삭제 건수**     | 파일 3개 + 변환 디렉터리 2개                            |
| **B. 조건부 삭제 용량**     | 약 **888 MB** (주로 cerberus_fossae)                    |
| **C. 개인 파일 건수**       | 디렉터리 7개 + 파일 1개                                 |
| **C. 개인 파일 용량**       | 약 **667 MB** (reference/ 하위 위주)                    |
| **D. 정책 불일치**          | **1건** (`tests/integration/test_robot_spawn.py` .gitignore 이슈) |
| **E. 삭제 금지 확인**       | `work_log/*.png` 14개, `Instruction/`, test_robot_spawn.py |
| **총 회수 가능 용량 (최대)**| 약 **1.55 GB** (A+B+C 모두 삭제 시)                     |
| **안전 회수 용량 (A만)**    | 약 **1.75 MB**                                          |

---

## 사용자 확인 필요 항목

1. **`삭제대상/` (40 KB)**: 이름만으로 삭제 의도 명확한가? 내부 `utils`, `utils-code` 는 본 프로젝트 소스와 참조 관계 없는가?
2. **`reference/RLRoverLab/` (409 MB)**: 가장 큰 개인 자료. v1.0 개발 중 추가 참조 여부?
3. **`assets/terrain/dem/cerberus_fossae.IMG` (336 MB)**: 이미 `.tif` 로 변환되어 있다면 원본 `.IMG` 삭제 가능 여부?
4. **`tests/integration/test_robot_spawn.py` `.gitignore` 라인 제거**: 해당 파일을 THE critical test 로 유지하려면 `.gitignore` 73라인 제거하고 `scripts/run_integration_test.py` 대체 경로 명시 필요?
5. **`Instruction.md` (단수) vs `Instruction/` (대문자 디렉터리)**: `.gitignore` 58~59 라인의 의도와 현재 untracked 상태가 일치하는가?
