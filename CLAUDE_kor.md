# CLAUDE.md — MarsLab 개발 가이드라인

## 프로젝트 개요

MarsLab은 행성/필드 로보틱스 연구를 위한 표준화된 미션 시나리오를 제공하는
오픈소스 화성 시뮬레이션 플랫폼으로, NVIDIA Isaac Sim 5.1 위에 구축되었다.
목표: iSpaRo 2026 Regular Paper (8페이지), 제출 마감 **2026-06-15**.

**저장소**: `MarsLab/` (Apache 2.0 라이선스)
**엔진**: Isaac Sim 5.1 + Isaac Lab
**핵심 스택**: Python 3.10+, ROS2 Jazzy, Isaac Sim Extensions, USD/URDF

---

## 운영 원칙 (always-on, OP-1 ~ OP-5)

다섯 가지 원칙이 작업이 *어떻게* 수행되는지를 지배한다. 협상 불가능하며
phase·scope에 관계없이 모든 개발 작업에 적용된다.

### OP-1: 병렬 서브에이전트 실행
- 모든 non-trivial 개발 작업은 서브에이전트에 위임하여 병렬 실행한다.
- 동시 실행 서브에이전트 **최대 5개**. 5개를 초과해야 하는 작업은 사용자
  명시적 승인과 서면 정당화가 필요하다.
- 엄격한 scope 격리: 각 에이전트의 write-surface 를 사전에 문서화하고,
  다른 에이전트의 surface 에는 승인 없이 쓸 수 없다.
- 교차 검증 게이트: 에이전트 결과는 (a) 별도 에이전트 또는 (b) file:line
  evidence 가 포함된 자기 검증 단계로 확인한다.

### OP-2: Reviewer 2 모드 (always-on)
- 모든 주장·결정·산출물에 공격적이고 근거 기반의 비판.
- non-trivial 한 주장에는 file:line citation 필수.
- 검증 없이 주장 수용 금지. 사용자 제안, 외부 참조, 자체 산출물 모두에
  동등하게 적용.
- 침묵의 동조보다 반대 의견이 우선.

### OP-3: 하드 데드라인
- **MarsLab v1.0 dev 완료: 2026-04-30** (public-availability 품질 + user-friendly
  기능). Dockerize 와 Wiki 는 sprint 종료 후 사용자 주도이며 더 늦게
  마칠 수 있지만, 코드/기능 scope 는 2026-04-30 에 동결된다.
- **iSpaRo 2026 논문 제출: 2026-06-15.**
- v0.7 baseline: 2026-04-24 (Isaac Sim 5.1 base + 대규모 refactor + bugfix).

### OP-4: 롤백 준비
- 모든 task 는 git commit 단위로 lands 되어 단일 `git revert` 로 이전 상태
  복구 가능.
- 모든 git 명령은 사용자가 실행, 어시스턴트는 실행하지 않음
  (memory: feedback_no_git_commands).

### OP-5: 에이전트 간 scope 격리
- 두 에이전트가 동일한 line·function·file section 을 동시에 수정 불가.
- 두 에이전트가 같은 파일을 손대야 한다면 클래스·블록·YAML 키 namespace
  로 분할. 이 분할은 sprint 계획에 기록.
- main thread 가 에이전트 launch 전에 분할을 cross-check 하고 검증 시점에
  위반을 차단하는 책임을 진다.

---

## 버전 타임라인

| 버전 | 날짜 | 상태 | 범위 |
|------|------|------|------|
| v0.7 | 2026-04-24 | ✓ 완료 | Isaac Sim 5.1 base, terrain/atmosphere/sensors/ROS2/SLAM 스택, 893 unit + 3 integration tests, 대규모 refactor + bugfix |
| **v1.0 sprint** | **2026-04-25 ~ 04-30** | **진행 중** | 엔지니어링 강화 (rover physics, sensor YAML 외부화, RGB-D PointCloud2, structure_assets drop-in, ideas.md polish). 계획: `~/.claude/plans/marslab_v1_0_sprint_2026-04-25.md` |
| v1.0 release | sprint 후, 사용자 주도 | 대기 | Dockerize (Isaac Sim 5.1 layer) + Wiki (mkdocs-material 추천). 사용자가 코드베이스 먼저 리뷰. |
| v1.5 | 논문 후, 취미 | 향후 | 엔지니어링 후속: GUI .obj 로더, 비-ROS2 데이터셋 export, scenario DSL, 다중 로버, fault injection |
| v2.0 | 논문 후, 취미 | 향후 | Photorealism: Hapke optics (#13), dust dynamics (#14), CARLA2Real-style sim2real |
| v3.0 | 미래 | 보류 | Terramechanics (Bekker/Janosi), RL 환경, 다중 로봇 협조 |

**v1.5/v2.0 후보 기능 참조:** `planetary_rover_simulator_ideas.md`.

---

## v1.0 Sprint 범위 (현재 sprint, 2026-04-25 ~ 04-30)

| ID | 작업 | Day | Owner |
|----|------|-----|-------|
| A | CLAUDE.md + CLAUDE_kor.md 재작성 + schema-bypass triage | Day 1 | main thread |
| B | Rover M2020 ballpark physics + YAML inject (mass 1025 kg, friction/damping/inertia) | Day 2 | robotics-mobility-lead |
| D | 센서 파라미터 YAML 외부화 (lidar JSON 포함) | Day 2 | atmosphere-rendering-specialist |
| E | Lidar USD import + 위치 고정 + YAML swap | Day 2 | atmosphere-rendering-specialist (D 와 묶음) |
| F | RGB-D depth → PointCloud2 publish (RealSense-style) | Day 2 | slam-nav-integrator |
| G | TF tree + extrinsic 검증 (unit + integration) | Day 2 | qa-validator |
| H | .obj/.stl YAML drop-in (GUI 없이) | Day 2-4 | scenario-terrain-architect |
| I | ideas #1, #3, #6 (M2020 only), #7 sensor preset, #16 YAML scenario doc, #17 bit-exact replay | Day 4-5 | atmosphere-rendering-specialist + qa-validator |

**Rocker-bogie 컨트롤러, Hapke optics, dust dynamics, GUI, 다중 로버는
이번 sprint 에서 명시적으로 제외.**

### v1.0 Roadmap (sprint 후, 사용자 주도)

다음 항목들이 v1.0 release 준비를 완성하며, 사용자가 (어시스턴트가 아닌)
코드베이스 리뷰 후 직접 수행:

- **Dockerize.** 추천: `nvcr.io/nvidia/isaac-sim:5.1.0` base + MarsLab layer.
  Headless-only image 우선; full GUI image 는 v1.5 로 이월.
- **Wiki.** 추천: GitHub Pages 의 mkdocs-material (`docs/` 에서 자동 배포).

두 항목 완료 = MarsLab v1.0 public release.

---

## 사용자 가이드라인 (G1-G10)

10가지 가이드라인이 *무엇을* 만들고 무엇이 scope 밖인지를 지배한다. 모든
기능·모듈·태스크는 이 가이드라인 중 하나 이상에 추적 가능해야 한다.

1. **G1: 필드 로보틱스 플랫폼.** MarsLab = SLAM, Nav, Exploration 을 위한
   표준화된 화성 로보틱스 테스트 플랫폼. v1.0 scope 는 본 CLAUDE.md 에.
2. **G2: RL 은 향후 작업 (v3.0).** v3.0 까지 RL 환경, 보상 함수, Gym API
   wrapper 없음.
3. **G3: 코드 재사용 금지.** OmniLRS / RLRoverLab 에서 알고리즘/흐름도
   영감만 허용. 코드 복사 금지. 참조 코드베이스 유래 명명 금지.
4. **G4: 로보틱스 우선, Photorealism 은 나중.** v1.0 = 충분한 수준 렌더링
   + 강력한 로보틱스. v2.0 = OmniLRS급 photorealism. v3.0 = terramechanics.
5. **G5: 모든 설정 YAML로.** Python 소스에 하드코딩된 상수 제로.
6. **G6: 극단적 모듈성.** 가장 작은 단위부터, 점진적 확장.
7. **G7: 모든 것에 단위 테스트.** 자동화 불가 시에만 시각 검수.
8. **G8: 작업 이력 로그.** `work_log/LOG.md` 가 추가 전용 로그; 항목은
   날짜 키 3 줄 요약 + artifact 링크.
9. **G9: 사용자 검토 게이트.** 사용자가 검토하고 수정 요청 가능; sprint
   계획은 `~/.claude/plans/` 에 위치.
10. **G10: Ultrathink 전반 적용.** 모든 설계 결정에 깊은 추론.

> **폐기:** 구 G9 (PLAN.md = 아키텍처; PLAN.md 는 2026-04-24 삭제),
> 구 G12 (13-Agent 적대적 토론; OP-1 병렬 서브에이전트로 대체),
> 구 G13 (4-파일 산출 PLAN.md/PLAN_kor.md/CLAUDE.md/CLAUDE_kor.md;
> PLAN.md 가 사라져 2 파일로 축소).

---

## 아키텍처 원칙 (P1-P3)

**P1: 평면 P0 아키텍처.**
조기 추상화 금지. 평면 절차적 코드로 시작. 경험적 복잡도가 요구할 때만
클래스/패턴 추출. 플러그인 시스템·만능 객체·등록 메커니즘 금지.
MarsLab 소스(`marslab/`, `scripts/`, `tests/`) 에 적용. 개발 하네스
(`.claude/agents/`, `.claude/skills/`) 는 인프라 계층이므로 P1 미적용.

**P2: 단방향 데이터 흐름.**
Config → 순수 연산 모듈 → Isaac Sim 씬 구성 → 네이티브 시뮬레이션 루프.
어떤 모듈도 시뮬레이션 루프를 수정하지 않음. 순환 의존성 금지. Config
만이 모듈 간 공유 의존성.

**P3: 오프라인 우선 테스팅.**
순수 연산 모듈(환경 물리, config validation, rock SFD, label conversion) 은
Isaac Sim 또는 GPU 없이 테스트 가능해야 한다. Isaac Sim 의존 코드는 별도
함수/파일로 격리하고 integration-only 로 명시.

---

## 코딩 표준

### 일반
- Python 3.10+. 모든 public 함수에 type hint.
- Docstring: Google style. 모든 public 클래스/함수에 docstring.
- Line length: 100 chars 이내.
- Formatter: `black`. Linter: `ruff` (`E,F,W,I,B,SIM` rule set).
- Type checker: `mypy` 는 `marslab/config/` + `marslab/environment/` scope
  (Isaac-Sim 의존 코드는 runtime typing 에 위임).
- 의존성 감사: `pip-audit --strict` (CVE 1 건이라도 fail).
- **모든 코드 변경은 완료 전에 다음을 통과해야 함:**
  ```bash
  black --check marslab/ scripts/ tests/
  ruff check marslab/ scripts/ tests/
  mypy
  pytest tests/unit/ -q
  pip-audit --strict
  ```
- Global state 금지. Isaac Sim app instance 외에는 singleton 금지.

### 명명 규약
- 파일/모듈: `snake_case.py`
- 클래스: `PascalCase`
- 함수/변수: `snake_case`
- 상수: `UPPER_SNAKE_CASE`
- ROS2 토픽: `/{robot_name}/{sensor_type}` (예: `/rover/rgb/image_raw`)
- Config 키: YAML 의 `snake_case`

### Isaac Sim 특정
- 시뮬레이션 셋업에는 `omni.isaac.lab` API **선호**.
- Isaac Lab wrapper 가 없을 때 `pxr.*` (USD Python API) 와 `omni.isaac.core`
  **허용**. 사유는 주석으로 기록.
- `omni.isaac.orbit` (deprecated) **사용 금지**.
- import 경로의 **"omni"** 는 NVIDIA namespace 로 G3 면제.
- OmniLRS, RLRoverLab, 또는 어떤 참조 코드베이스에서도 **코드/명명 파생 금지**.
  알고리즘/패턴 영감만.
- 내장 USD 에셋(G1, Go2, Valkyrie): Isaac Sim asset path 로 로드, 저장소에
  복사 **금지**.
- 로봇 import: URDF → USD 오프라인 변환 스크립트(`scripts/phase1/convert_urdf_to_usd.py`).
  런타임 URDF import 금지 (memory: reference_rover_usd_source).

### Configuration
- 모든 물리 파라미터는 `configs/` 에. Python 에 하드코딩 금지.
- pydantic 으로 schema validation. 모든 BaseModel 은
  `model_config = ConfigDict(extra="forbid")` 사용 — 알 수 없는 YAML 키는
  load time 에 fail (silently drop 금지).
- 시드 기반 재현성: 모든 randomized process 는 `seed` 매개변수 수용.

### 화성 물리 상수 (Reference — 코드 아닌 config 에)
```yaml
# configs/mars_env.yaml
mars_env:
  gravity: 3.72             # m/s^2
  atmo_pressure: 610        # Pa
  atmo_density: 0.020       # kg/m^3
  surface_temp_mean: -60    # Celsius
  sol_duration_seconds: 88642  # 24h 37m 22s
  dust_opacity_range: [0.5, 2.0]
```

---

## 모듈 아키텍처

### 모듈 의존성 규칙
1. 순환 import 금지. A 가 B 를 import 하면 B 는 A 를 import 하지 않음.
2. `config/` 만 공유 의존성. 모든 모듈은 `MarsLabConfig` 에서 읽음.
3. `environment/` 는 Isaac Sim import 제로. 순수 Python. 오프라인 테스트 가능.
4. `terrain/dem_loader.py`, `terrain/rock_placer.py` 는 Isaac Sim import 제로.
5. `rendering/` 은 `environment/` 에 단방향 의존 (계산된 파라미터를 위해).
6. `robots/` 는 `config/` 에만 의존.
7. 어떤 모듈도 Isaac Sim 시뮬레이션 루프를 수정하지 않음.
8. 모든 randomized 함수는 `seed` 매개변수 수용.

### 모듈 요약
| 모듈 | 책임 | Isaac Sim 필요? |
|------|------|---------------|
| `config/` | YAML load, pydantic validation, seed propagation | No |
| `environment/` | Mars physics: sun position, Beer's law, COMIMART, sky params | No |
| `terrain/` | DEM loading, mesh building, rock placement, materials | Partial |
| `rendering/` | Sky dome, sun light, atmosphere fog, render mode | Yes |
| `robots/` | URDF→USD spawn for rover, Ackermann controller | Yes |
| `sensors/` | Camera, LiDAR, IMU spawn (Path B unified API) | Yes |
| `ros2_bridge/` | Sensor → ROS2 topic publishing, QoS profiles | Yes |
| `scene/` | structure_loader, mesh-only assets | Yes |
| `runtime/` | Stage-2 / Stage-3 main loop orchestration | Yes |
| `math/` | Quaternion utilities, transforms (offline) | No |

---

## 에러 처리

- Config validation error: 설명적 메시지로 `pydantic.ValidationError` raise.
- 누락 파일(DEM, URDF, HDRI): full path 와 함께 `FileNotFoundError` raise.
- Isaac Sim API 실패: catch, `logging.error()` 로 로그, context 와 함께 re-raise.
  Kit teardown 실패에는 `os._exit(1)` 사용.
- runtime 에서 범위 초과 물리 값: 매개변수 이름·값·유효 범위와 함께
  `ValueError` raise.
- **예외를 silently swallow 금지.** **bare `except:` 금지.**
- Teardown 노이즈를 카테고리별로 1 회 로그하려면 `marslab/runtime/main_loop.py`
  의 `_log_once(target_logger, exc, category, step_count, grace_steps=120)` 사용.
- 모든 에러 메시지는 디버거 없이 진단 가능한 context 포함.

---

## 테스팅 요구사항

### 유닛 테스트 (Isaac Sim 불필요)
실행: `pytest tests/unit/ -q`. 현재 카운트: **893 tests** (post-v0.7 sweep).

커버리지:
- Config schema (`extra="forbid"` 강제, pydantic validator)
- Beer's Law (Appelbaum airmass, NASA TM-102299, 5% 이내)
- COMIMART diffuse fraction (Vicente-Retortillo et al. 2015, Rayleigh floor 0.10)
- 태양 위치 (Allison & McEwen 구면 삼각법, obliquity 24.94°)
- Golombek SFD (CFA 곡선, VL1/VL2/MPF/InSight 의 10% 이내)
- Seed determinism (같은 seed = 동일 출력)
- Quaternion math (gimbal-lock 분기, non-unit warning)
- Sensor YAML schema, ROS2 QoS profile mapping

### 통합 테스트 (Isaac Sim 필요)
실행: `scripts/isaac_python.sh scripts/run_integration_test.py`.
`@pytest.mark.integration` 마킹, `pytest.importorskip("isaacsim")` 게이트.

현재 인벤토리:
- `tests/integration/test_imu_gravity_actual.py` — Rover IMU z ∈ [3.67, 3.77] m/s²
- `tests/integration/test_robot_spawn_ros2_topics.py` — `/rover/odom` 30s 이내
- `tests/integration/test_slam_toolbox_receives_scan.py` — `/rover/scan` BEST_EFFORT QoS

### 시각 검수
`tests/visual_inspection/checklist.md` 에 문서화.
스크린샷 링크와 함께 `work_log/LOG.md` 에 로그.

### CI 파이프라인
- `.github/workflows/unit_tests.yaml` — matrix [3.10, 3.12], black + ruff + mypy + pytest
- `.github/workflows/security.yaml` — `pip-audit`
- 통합 테스트: `scripts/run_integration_test.py` 로 수동 실행 (GPU 필요)

---

## 금지 사항

1. **v1.0 에서 terramechanics 충실도를 주장하지 말 것.** 물리 = 강체 +
   Mars 보정 마찰. BCM/SCM/DEM 없음. Terramechanics 는 v3.0.
2. **v1.0 에서 photorealism 을 쫓지 말 것.** 충분한 수준 렌더링 + 강력한
   로보틱스. v2.0 이 Hapke optics + dust dynamics 담당. 시각적 폴리시로
   로보틱스 작업을 차단하지 말 것.
3. **화성 파라미터를 하드코딩하지 말 것.** 모든 것을 YAML 에.
4. **Isaac Sim 내장 USD 에셋을 저장소에 복사하지 말 것.** path 로 참조.
5. **폐기된 Isaac Sim API 사용 금지** (`omni.isaac.orbit`).
6. **OmniLRS 또는 RLRoverLab 코드 복사 금지.** 영감만.
7. **에이전트 context 에서 `git` 실행 금지.** 모든 git 작업은 사용자 주도
   (memory: feedback_no_git_commands).
8. **venv 사용 금지** — `--break-system-packages` 옵션의 pip install 이
   프로젝트 선호 (memory: feedback_no_venv).
9. **dead code 를 hedge 로 주석 처리 금지.** hard-delete 가 default;
   롤백은 `git log -p` (memory: feedback_no_delete_comment, R4 Option C).
10. **불확실할 때 추측 금지.** 검증된 우회 구현 또는 진단을 먼저 수행
    (memory: feedback_no_speculative_fixes).

---

## 참조 코드베이스 (구현 전 연구 — G3)

| 코드베이스 | 학습 내용 | 링크 |
|-----------|----------|------|
| OmniLRS | 지형 생성 파이프라인, ROS2 바인딩, 암석 배치 | github.com/OmniLRS/OmniLRS |
| SRB | 모듈러 태스크 레지스트리, sim-to-real 자동화 | arXiv:2509.23328 |
| RLROVERLAB | Isaac Lab API 패턴, three-mesh 패턴 | github.com/abmoRobotics/isaac_rover_orbit |
| unitree_sim_isaaclab | G1/H1 Isaac Lab 통합 패턴 | github.com/unitreerobotics/unitree_sim_isaaclab |
| Sim2Dust | DreamerV3 world model RL, zero-shot 전이 | arXiv:2508.11503 |

---

## 커뮤니케이션 프로토콜

기능 구현 요청 시:
1. `~/.claude/plans/` 의 sprint 계획과 위 버전 타임라인 확인. v2.0/v3.0
   작업은 명시적으로 거절.
2. OP-1 (병렬 서브에이전트, max 5) 와 OP-2 (Reviewer 2 모드) 적용.
3. 참조 코드베이스가 이미 해결했는지 확인. 재구현 전 연구
   (G3: 연구만, 복사 금지).
4. config 기반, seed 재현 가능 코드 작성 (G5).
5. 단위 테스트 포함 (G7).
6. Isaac Sim API 가 불확실하면, 폐기된 API 추측 대신 불확실성을 명시.
7. 완료 시 `work_log/LOG.md` 에 3-line entry (G8).

**Sprint 모드 (현재):** 활성 sprint 계획 하에서 Agent tool 로 직접
서브에이전트를 launch. 이전 Wk1-Wk6 6-에이전트 하네스는 OP-1 sprint-scoped
위임으로 대체되어 폐기되었다.
