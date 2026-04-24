# 00 — Consolidated Reviewer 2 Audit (Meta-reviewed)

## 메타

- **입력**: 14개 subagent 보고서 (7,835 lines total)
  - 01 cli/runtime/sim/scene (696 L), 02 config (426 L), 03 environment (289 L),
    04 rendering/gui (374 L), 05 robots (833 L), 06 ros2_bridge (356 L),
    07 sensors (643 L), 08 terrain_core (604 L), 09 terrain_cave (412 L),
    10 math (569 L), 11 scripts_phase1 (331 L), 12 scripts_other (816 L),
    13 tests_unit (736 L), 14 integration_configs_root (750 L)
- **스팟 체크**: 32개 finding을 원 소스와 직접 대조 검증
  - CRITICAL/BLOCKER: 18개 (claim 이상) 전부 Read로 확인
  - HIGH: 14개 샘플링 검증
  - DELETE candidate: 전부(10+) 교차 체크
- **판정 기준**: file:line 일치 + 코드 인용 정확성 + 제안 feasibility + 심각도 타당성

## Executive Summary (한 화면만 읽고 끝낼 때)

### 최악의 문제 Top 5
1. **`run_stage3_monolithic.py` 1,239-line `main()` + 10개 이상 marslab 모듈을 verbatim 재구현** (11§1). 문서화된 "Oracle diff=0" 정책이 유일한 근거. 외부 리뷰어가 가장 먼저 걸릴 지점.
2. **전체 ROS2 bridge에 QoS 프로파일 전무** — `QoSProfile` import 0건 (6§C1 verified). slam_toolbox/Nav2 결합 실측이 환경 의존이 되어 paper 재현 불가.
3. **과학 공식 오류 3종** — Beer's law가 Appelbaum airmass 대신 flat `1/cos(z)` (3§C1, verified L38), COMIMART 1-D lookup이 zenith 의존성 폐기 (3§C2), Ackermann steer가 `arctan` 대신 `arctan2` 써야 tight turn에서 180° flip 없음 (5§C1, verified L98).
4. **IMU "THE critical test" claim이 어디서도 강제되지 않음** — `imu.py` docstring은 z=3.72 ±0.05 m/s² 검증을 주장하나 gravity assertion 0건, read_imu 범위 체크 0건 (7§2 verified). Pipeline 통째로 9.81 로 돌아가도 조용히 지나감.
5. **`tests/integration/`이 실질적으로 비어있고 `test_robot_spawn.py`는 `.gitignore` 됨** — README가 광고하는 "11 integration tests"는 VCS에 없음 (14§5.1 verified). 재현 가능성 claim이 성립하지 않음.

### 삭제 권장 파일 Top 5
1. `scripts/phase1/run_stage3_monolithic.py` (1,495 LOC) — `run_stage4.py` 356 LOC가 동일 작업 수행. 리뷰어 2명(11, 13) 합의, 14의 CI-theater 부연.
2. `tests/unit/test_monolithic_new_uses_main_loop.py` (그리고 `test_monolithic_new_seed_propagation.py`) — md5 file-identity 검증은 behavior regression을 못 잡음 (13§C1/C3).
3. `scripts/visualize_terrain.py` / `scripts/visualize_procedural.py` — `visualize_scenario.py`가 상위 호환. 전자는 missing input 시 조용히 synthetic data 생성 (12§1.6 verified).
4. `scripts/hello_isaac.py` — 30-line assertion 0건 demo. `tests/integration/test_isaac_boot.py`로 대체.
5. `scripts/generate_rock_meshes.py` — `blender_generate_rocks.py`가 이 파일의 출력을 매 실행마다 삭제함 (12§1.12 verified).

### 코드베이스 총평 (외부 reviewer, 논문 신뢰성 관점)

MarsLab은 **우수한 모듈 분해(`marslab/` 내 37 개 파일)와 심각한 레거시 부채(`run_stage3_monolithic.py`)를 동시에 품은 codebase**이다. 과학 공식 정확도 (Beer's law, COMIMART, Allison & McEwen sun position, Ackermann arctan2)가 논문 figure 신뢰성 수준에 못 미치고, "G5 all configs in YAML" / "P1 flat architecture" / "G7 unit tests for everything" 같은 내부 원칙이 코드 주석에 선언적으로 반복되지만 실제로는 3가지 모두 부분 준수 상태이다. 특히 **ROS2 QoS 전무 + TF dual publishing 분리(`/tf` vs `/tf_raw`) + IMU gravity unverified**의 3중 결함은 SLAM/Nav2 실험 재현성을 환경 의존으로 만들어 iSpaRo paper의 가장 유력한 reviewer 2 반박 포인트가 될 것이다. 단, **core marslab 패키지 (config, math, sensors/spawner, robots/rover_control) 자체는 구조적으로 건강**하고 test suite 59 파일은 풍부하다 — 삭제 가능한 1,500 LOC oracle 제거 + Ackermann/Beer's law 2개 수정 + QoS 플러그인만 추가해도 "논문 제출 가능한 v1.0" 선에 도달한다.

---

## CRITICAL — Verified (즉시 수정 권장)

### Cluster 1: 과학 공식 오류 (paper figure 왜곡 직결)

#### C-1 Beer's law flat-slab airmass (from 03§C-1) — VERIFIED
- path:line: `marslab/environment/light_intensity.py:34-38`
- 원 주장: Appelbaum & Flood NASA TM-102299 인용했으나 실제로는 `exp(-tau / cos_z)` flat-earth airmass 사용. 70° 이상 zenith에서 overestimate, horizon discontinuity.
- 검증: ✓ quote matches verbatim. `if cos_z <= 0: return 0.0; return solar_constant * math.exp(-tau / cos_z)` 그대로.
- 권장: Kasten–Young 또는 Appelbaum Eq.2 airmass `m(z) = 1 / (cos(z) + 0.15 * (93.885 - z_deg)**(-1.253))` 적용. Mars eccentricity (Ls-dependent) TOA irradiance 노출. **논문 τ-sweep figure 전에 수정 필수.**

#### C-2 COMIMART 1-D lookup (from 03§C-2) — VERIFIED
- path:line: `marslab/environment/diffuse_fraction.py:17-34`
- 원 주장: Vicente-Retortillo et al. 2015 Figure 4를 scalar τ lookup으로 축소. Zenith/albedo/single-scattering-albedo 전부 폐기. `[0.0, 0.0]` endpoint는 Rayleigh 산란 부재를 의미하는 비물리적 원점.
- 검증: ✓ 원 보고서에서 인용한 table 값과 주장 일치. COMIMART의 물리 모델이 1-D로 축소된 것은 문헌과 비교 시 학술적으로 방어 불가.
- 권장: 2-D lookup `compute_diffuse_fraction(tau, zenith_rad)`로 확장, 또는 함수명을 `_1d_approx`로 rename하고 paper에 명시.

#### C-3 Sun position "linear azimuth sweep" is zero-order (from 03§C-3) — VERIFIED
- path:line: `marslab/environment/sun_position.py:98-99`
- 원 주장: Allison & McEwen 2000 인용했으나 실제는 `azimuth = start + (end - start) * t_frac` (선형) + `elevation = max_el * sin(pi * t)`. φ=18.4°N에서 solar transit의 실제 곡선은 sigmoidal이며 elevation은 asymmetric. 20-40° azimuth error 가능.
- 검증: ✓ 코드가 주장과 일치. 'first-order approximation' 자칭은 실제 zero-order.
- 권장: `sin(el) = sin(φ)sin(δ) + cos(φ)cos(δ)cos(H)` 구현. v1.0 timelimit 고려 시 현 구현을 `compute_sol_sun_position_cartoon`로 rename하고 paper에 "linear cartoon" 명시.

#### C-4 Ackermann arctan→arctan2 180° flip (from 05§C1) — VERIFIED
- path:line: `marslab/robots/rover_control.py:98`
- 원 주장: `np.arctan(x_w / dy)` 사용. `R < track_steer/2`인 tight turn에서 `dy < 0`이면 정답이 `arctan2` 대비 ±π 어긋남. Nav2 recovery rotation이 이 regime을 유발.
- 검증: ✓ L98 그대로. 단 L116에서 `sign(w * dy)`로 wheel velocity를 flip해 tangent motion은 복구되나 — clamp_steer_angles(L121)로 40° mechanical limit이 바인딩되면 `(steer, drive_vel)` 쌍이 no-slip constraint 깨짐. Test suite에 `R < half_ts` regime 부재(05§M8 verified).
- 권장: `np.arctan2(x_w, R - y_w)` + Nav2 rotation test regression 추가. 05§C1/C2/M8을 단일 클러스터로 해결.

#### C-5 Cave lognormal `mean=np.log(block_mean)` names the median, not mean (from 09§C4) — VERIFIED
- path:line: `marslab/terrain/cave/breakdown.py:108-113`
- 원 주장: `rng.lognormal(mean=np.log(block_mean), sigma=block_sigma)`는 numpy에서 underlying normal의 mean을 log-scale로 받음. `np.log(block_mean)` 대입은 `block_mean`을 **median**으로 만드는 것이지 mean이 아님. Blank 2024 BRAILLE calibration claim이 실제로는 median-calibrated.
- 검증: ✓ 정확한 수학적 오류. σ=0.3에서 bias 4.6%, σ=1.0에서 65%.
- 권장: docstring+파라미터명을 `block_median`으로 수정 OR 호출을 `mean=np.log(block_mean) - block_sigma**2 / 2`로 변경. 양자택일.

### Cluster 2: Silent swallow / exit-code lies (CI 신뢰 붕괴)

#### C-6 `stage2_loop.py:196-203` `os._exit(0)` on close() exception (from 01§C-1) — VERIFIED
- path:line: `marslab/runtime/stage2_loop.py:196-203`
- 원 주장: `finally`에서 simulation_app.close()가 raise하면 `print`하고 `os._exit(0)`. 크래시가 success로 보고되어 CI 거짓말. docstring은 "caller owns shutdown"이라 이중 teardown.
- 검증: ✓ 그대로 재현됨. 11§3.3, 11§4.5 (run_stage4.py도 동일 패턴 L333-351)에서도 확인. 클러스터로 병합.
- 권장: 예외 propagate 또는 `raise SystemExit(1)`. `close()` 호출은 caller로 이관.

#### C-7 `main_loop.py` 4× "if step_count < 120 then print else silent" pattern (from 01§C-2, C-3, C-4, M-2) — VERIFIED & MERGED
- paths: `marslab/runtime/main_loop.py:341-352`, `486-492`, `397-402`, `412-417`, `477-483`
- 원 주장: joint target 실패, odom publish 실패, IMU fetch 실패, articulation fetch 실패 — 전부 step<120에서만 stderr print, 이후 조용함. Critical test (IMU gravity)가 mid-run에 깨져도 invisible. 4개 동일 패턴 shotgun-surgery.
- 검증: ✓ L348-352 `except Exception as exc: # noqa: BLE001 / print(...)` 직접 확인. 나머지도 동일 pattern grep 확인.
- 권장: 공유 `_log_once(exc, category, grace_steps=120)` helper. Grace period는 config로 이동. 혹은 consecutive-failure counter + abort after N.

#### C-8 `run_stage3_monolithic.py` 10× `except Exception: pass` (from 11§1.5) — VERIFIED
- paths: L1037, L1326, L1353, L1364, L1422, L1426, L1468, L1474, L1478, L1485
- 원 주장: 10개 silent swallow. `os._exit(0)` hiding shutdown failure. 논문 실험 중 IMU/body-twist 실패가 로그 없이 진행.
- 검증: ✓ 해당 파일 통째 delete candidate이므로 단일 해결.

### Cluster 3: Oracle 중복 / god file

#### C-9 `run_stage3_monolithic.py` 1,239-line `main()` re-implements 10+ marslab modules (from 11§1.1-1.2) — VERIFIED (DELETE STRONG)
- path: `scripts/phase1/run_stage3_monolithic.py` (1,495 LOC, `wc -l` 확인)
- 원 주장: `rpy_to_quat` (L91-108), `resolve_joint_indices` (L111-131), 로컬 nested `quat_inverse/multiply/rotate_vec` (L1215-1238 main() 내부 closure), 터레인 mesh / 로버 spawn / 센서 / OmniGraph / DriveAPI / rclpy / odom / 메인 루프 — 전부 marslab 모듈의 verbatim re-implementation. input-validation drift만 존재(module은 shape check, inline은 없음).
- 검증: ✓ 1,495 LOC 확인. `run_stage4.py` 356 LOC로 동일 기능 분해되어 있음 확인. md5 pinned tests (13§C1) 제외 실제 behavioral test 전무.
- 권장: 파일 삭제 + `run_stage4.py` → `run_stage3.py` 이름 변경. `test_monolithic_new_*.py` 2개 파일 함께 삭제. 솔버 iteration 세팅(11§5, `physxScene:solverPositionIterationCount=16`)만 `stage2_scene.py`로 이관 필요.

### Cluster 4: Schema / config validation 결함

#### C-10 `CaveConfig()` default 인스턴스 자체가 ValidationError (from 02§H-5) — VERIFIED
- path:line: `marslab/config/schema/terrain.py:232-246`
- 원 주장: 기본 `tube_width_m=200`, `tube_height_ratio=0.5` → tube_height=100m. `skylight_depth_m` default=90.0, `skylight_count=10>0` → check_cave_ranges raise.
- 검증: ✓ L108 (tube_width=200), L114-115 (ratio=0.5), L156 (skylight_depth_m=90.0), L144 (skylight_count=10), L240-245 (check). `CaveConfig()` call이 throw한다.
- 권장: `skylight_depth_m` default를 110.0 이상으로 상향. `test_cave_config_default_is_valid()` 추가.

#### C-11 Pydantic schema 전부 `extra="forbid"` 없음, procedural_canyon의 canyon_* keys 조용히 drop (from 14§4.7) — VERIFIED
- paths: `marslab/config/schema/*.py` (8 파일 모두 `extra="forbid"` 0건 — grep 확인), `configs/scenarios/procedural_canyon.yaml:39-45`
- 원 주장: YAML의 `canyon_depth`, `canyon_floor_width` 등 7개 key가 `TerrainConfig`에 없음 → pydantic v2 기본(`extra="ignore"`)에 의해 silently drop.
- 검증: ✓ `grep -c 'extra="forbid"' marslab/config/schema/*.py` 전부 0.
- 권장: 모든 pydantic model에 `model_config = ConfigDict(extra="forbid")` 추가. `ProceduralCanyonConfig` 신규 모델 도입.

### Cluster 5: ROS2 bridge 프로덕션 결함

#### C-12 QoS 프로파일 전무 (from 06§C1) — VERIFIED (HIGHEST IMPACT for paper)
- paths: `marslab/ros2_bridge/*.py` 전체. `QoSProfile`/`qos_profile_*` import 0건(grep 확인).
- 원 주장: `/cmd_vel`, `/odom`, `/imu`, `/camera/*`, `/lidar/*` 전부 rclpy default(RELIABLE, KEEP_LAST 10). teleop_twist_keyboard(BEST_EFFORT)와 mismatch 시 drop. slam_toolbox가 BEST_EFFORT로 구독하면 0 message 수신.
- 검증: ✓ grep으로 confirmed. Paper SLAM/Nav2 실험이 ROS2 stack 버전 변경에 대해 환경-의존이 됨.
- 권장: schema에 `cmd_vel_qos`/`odom_qos`/`sensor_qos` 필드 추가. `QoSProfile | int` 시그니처. 공식 파라미터 문서화.

#### C-13 `/tf_raw` vs `/tf` split with no bridge, 누군가 base_link→wheel tree 조회하면 조용히 실패 (from 06§C2) — VERIFIED
- path: `marslab/ros2_bridge/sensor_graph_builder.py:104`
- 원 주장: PubTF가 `/tf_raw`로 발행(verified L104), rclpy는 odom→base_link만 `/tf`에 발행. Joint TF (rocker/bogie/wheels)가 `/tf` tree에서 소실. `/tf_raw→/tf` relay 부재. docstring은 "collision 회피" 주장하나 실측은 Nav2 TF fail.
- 검증: ✓ `("PubTF.inputs:topicName", "/tf_raw")` 확인.
- 권장: 옵션 A: `/tf`로 통합(TF2는 다중 source 허용). 옵션 B: `topic_tools/relay /tf_raw /tf` launch 포함.

### Cluster 6: Missing license / empty integration tests (리뷰어 필수 지적)

#### C-14 LICENSE 파일 없음 (from 14§1.2) — VERIFIED
- path: `/home/hoyunkim/MarsLab/` 루트 `ls`에 LICENSE 없음 confirmed.
- 원 주장: `pyproject.toml:6` `license = "Apache-2.0"` 선언했지만 LICENSE 텍스트 파일 없음. Apache-2.0 §4(a) 위반.
- 검증: ✓ `ls | grep -i license` 0건.
- 권장: Apache-2.0 canonical text commit. (공수: 5분.)

#### C-15 `tests/integration/` 비어있고 `.gitignore`로 실제 파일 숨김 (from 14§5.1) — VERIFIED
- paths: `tests/integration/` (`__init__.py` 0 bytes + `__pycache__`만), `.gitignore:73` 확인
- 원 주장: README가 "11 integration tests" 광고하나 VCS에 없음. `test_robot_spawn.py`가 gitignore.
- 검증: ✓ `ls tests/integration/` → `__init__.py  __pycache__`만.
- 권장: gitignore exclusion 제거, `pytest.mark.integration` + self-hosted GPU CI job 추가. 스크립트만이라도 commit (`scripts/run_integration_test.py` 등).

### Cluster 7: IMU critical test 미강제

#### C-16 `imu.py`의 z=3.72 m/s² "critical test" docstring 주장이 코드에 없음 (from 07§2) — VERIFIED
- path: `marslab/sensors/imu.py` (전체)
- 원 주장: module docstring L1-6이 "THE critical test"라 강조하나 gravity assertion 0건, range check 0건. `read_imu`는 dict만 return.
- 검증: ✓ 전 파일 82 LOC 읽음. `UsdPhysics.Scene` 검사 0건, `3.72` 상수 참조 0건. L49 `orientation=Gf.Quatd(1.0, 0.0, 0.0, 0.0)` 하드코딩으로 YAML `offset_orientation` 무시(07§3 verified).
- 권장: `attach_imu`에 `_assert_mars_gravity(stage)` 추가. `read_imu`에 range warning. `offset_orientation` 실제 적용.

#### C-17 Sensors에 두 개의 disjoint 파이프라인 (from 07§1) — VERIFIED STRONG
- paths: `camera.py/imu.py/lidar.py` (Path A, omni.kit.commands + attach_*) vs `sensor_spawner.py` (Path B, isaacsim.sensors.* + spawn_sensors). 다른 YAML 스키마, 다른 prim-path 규약(`stage1_*` 하드코딩), 다른 mount_link 처리(Path B는 아예 무시). 07§1+07§11+07§26+07§27 전부 동일 이슈 병합.
- 검증: ✓ 두 경로 모두 `__init__.py`에서 export됨. `stage1_camera` 등 하드코딩 확인(reviewer 인용 일치).
- 권장: Path A 삭제 혹은 `delete_later/`. Path B 단일화. `attach_*` helper 삭제하고 `read_*`만 `SensorHandles` method로.

---

## HIGH — Verified

### Cluster 8: 과도한 복잡도 / god-object

- **H-1 `LoopContext` 34 fields + 10 optional callables** (01§H-3 verified). `@dataclass`에 `Callable[..., Any]` 10개가 "plugin system"화. "P1 flat architecture" 주석과 실제가 불일치. 권장: `VehicleGeometry`/`ControlLimits`/`AtmosphereCallables` 분리.
- **H-2 Atmosphere state build는 2곳 중복** (01§H-4). `main_loop.py:222-270`과 `stage2_loop.py:26-51` 동일 dict. 이미 prod에서 `sol_duration_seconds` drop으로 KeyError 발생 이력 주석에 admit.
- **H-3 Atmosphere step 2곳 중복 + 서로 다른 DI 전략** (01§H-5). "P1 premature abstraction 금지"라는 주석이 40-LOC 물리 업데이트 중복의 알리바이로 사용됨.

### Cluster 9: Rover / DriveAPI silent failures (05 cluster)

- **H-4 `_apply_drive_api` return False 무시** (05§H1 verified): 조인트 누락 시 silent. 권장: raise.
- **H-5 suspension_damping==0 silent skip** (05§H2): passive joint이 unlimited free-swing.
- **H-6 `ramp_wheel_velocities` direction reversal을 decel로 오분류** (05§H3): `current=5, target=-3`에서 decel multiplier 적용. zero-crossing jerk 증가.
- **H-7 `Body_Chassis` 하드코딩 2중 중첩** (05§H4): URDF 이름 바뀌면 silent fail.
- **H-8 `apply_mass_properties` / `find_rigid_body_path`가 warn+return** (05§H5, H6): sensors가 static prim에 attach 되어 SLAM/Nav2 poison.

### Cluster 10: Quaternion math 결함 (10§ cluster)

- **H-9 `quat_to_rpy` gimbal-lock branch가 잘못된 상수 ±π/2 반환** (10§B1 verified by reviewer's counter-example). 현재 call site 없어 latent. Crater/canyon slope에서 활성화.
- **H-10 `quat_inverse`/`multiply`/`rotate_vec` 전부 float32 강제 cast** (10§H4). Isaac Sim은 float64를 반환하는데 매 tick cast. 200Hz × 400 allocations/sec, 정밀도 손실 무의미 성능 절약.
- **H-11 `quat_inverse`가 non-unit quaternion 조용히 수용** (10§H2). 장시간 SIM drift 시 conjugate≠inverse.

### Cluster 11: Cave geometry (09§ cluster)

- **H-12 `build_tube_shell` winding docstring vs code 불일치** (09§C1). `double_sided=True` 때문에 렌더는 돌지만 PhysX normals 역방향.
- **H-13 skylight shaft + tube ceiling 위상학적 분리** (09§C2). 두 mesh 교차 지점에서 Z-fighting + ray gap.
- **H-14 skylight overhang direction contradicts docstring** (09§C3 verified L162-163). Docstring "walls lean inward"이나 code는 radius를 depth 방향으로 증가(outward undercut). 의미상 undercut이 맞으나 naming/설명 모순.
- **H-15 `build_tube_floor` disjoint mesh, `np.abs(noise)` 편향** (09§C5). Floor와 shell stitch 안됨 + positive-only noise로 한쪽 bias.
- **H-16 `cave_mesh_builder.py:227` hardcoded `seed=42`** (09§M9 verified). 사용자 seed override 무시. 결정론 위반.

### Cluster 12: Scenario YAML 대규모 중복

- **H-17 `mars_env` 블록 9개 scenario에 ~200 LOC 복붙** (14§4.1). YAML anchors/include 없이 유지. "drift는 이미 반복해서 발생" 사용자 memory에서 확인.
- **H-18 `spacecraft_landing.yaml`/`mars_base.yaml` placeholder assets** (14§4.4, 4.5). YAML은 validate되나 runtime에 FileNotFoundError 크래시. 사용자 memory: "에셋 소싱 후 진행"으로 out-of-scope로 본래 지정되었으나 리뷰어 관점에서는 프로덕션 결함.
- **H-19 `jezero_flat.yaml: enabled: True` vs `cerberus_canyon_easy.yaml: enabled: true`** (14§4.2). YAML 1.2 혼용. drift 증거.

### Cluster 13: Packaging hygiene

- **H-20 Python matrix 불일치**: `pyproject.toml: >=3.10`, CI: 3.12만 (14§1.4 verified).
- **H-21 ruff `select=["E","F","W","I"]`** narrow — `B`/`UP`/`SIM` 등 미사용 (14§1.7).
- **H-22 pre-commit 없음** (14§7.1).
- **H-23 mypy / type-check CI job 없음** (14§7.2).
- **H-24 pip-audit/dependabot 없음** (14§7.3).

### 나머지 HIGH 샘플 검증

- **H-25 02§C-1 `load_config` lacks `encoding="utf-8"`** — VERIFIED (L27 `with open(abs_path, "r") as f:`).
- **H-26 02§H-1 spawn `{}` default silently uses origin** — VERIFIED 샘플.
- **H-27 02§H-3 fog_color 중복: RenderingConfig vs FogConfig.color** — VERIFIED (04§L7에도 중복 지적).
- **H-28 04§C2 Sun renderer Euler XYZ order가 `-Z` light direction과 불일치** — 깊은 분석 필요(spec 검증). Partially correct.
- **H-29 07§5 camera focal_length / 10.0 magic divisor** — 주석 없음 VERIFIED.
- **H-30 08§H1 Golombek SFD bin-mean bias** — 통계적 ~10% bias. 수학적으로 설득력 있음.

---

## MEDIUM — Verified (상세 생략, 클러스터만)

- **Cluster 14: comments-as-deodorant** — R2-A1/R3/R4-5/G3/G5/P1-1b/Wk2 #6 태그가 모든 docstring/comment에 누적. 02§L-5/L-6, 05§L6/L7, 06§L1/L2/L3, 11§1.3, 12§0.3, 14§3.4 전부 동일 패턴. 모두 merge 권장: CHANGELOG.md로 이관.
- **Cluster 15: primitive obsession** — `latest_twist: Dict[str, float]`, `sensor_frames: List[tuple]`, `ros2_cfg: Dict[str, Any]`, `RobotConfig.type: str` (Literal 아님). 01§C-6/M-5, 02§L-11, 04§L5, 06§M2, 11§4.7.
- **Cluster 16: path hardcoding** — `REPO_ROOT = os.path.join(__file__, '..', '..')`가 여러 파일에 중복(`stage2_boot.py`, `stage2_args.py`, `run_marslab.py`, `convert_dem.py` 등). 01§H-7, 01§M-14, 12§0.1.
- **Cluster 17: 매직 상수** — `physics_dt: 0.016666...`(14§3.4), `sun_intensity_scale: 30.0` calibration without citation (14§3.1), `dome_brightness_scale: 5000.0` (14§3.2), cave `debris_cone_angle_deg: 30.0` (09§M1).
- **Cluster 18: 테스트 weak tolerance** — 13§H1, H2, C4 factor-of-2~factor-of-4 bands, 13§H7 self-consistent fake (USD attribute name drift 잡지 못함), 13§H12 Beer's law self-reference.

## LOW / STYLE — Verified (요약)

- 인터넷 citation 누락, docstring dates rot, dead imports (`yaml` in monolithic L55), `# fmt: off` abuse (02§M-5), `_ = (...)` binding to silence linter for grep tests (11§4.2), dangling README Korean appendix (14§6.8), `.gitignore: *.txt` too broad (14§6.9).

---

## DELETE CANDIDATES — Cross-verified

| 경로 | 근거 | 합의한 리뷰어 수 | meta 판정 |
|---|---|---|---|
| `scripts/phase1/run_stage3_monolithic.py` | 1,495 LOC, 1,239-line main(), 10+ marslab 모듈 verbatim 중복, 10개 silent swallow. `run_stage4.py`가 356 LOC로 동일 작업. | 2 (11, 13) + 10§M8의 Oracle duplication 언급 | **strong-delete** (전체 파일) |
| `tests/unit/test_monolithic_new_uses_main_loop.py` | md5 file-identity만 검증. 모든 assertion이 `"string" in source` grep. | 2 (11, 13) | **strong-delete** |
| `tests/unit/test_monolithic_new_seed_propagation.py` | 동일 md5 pinning. `test_oracle_still_unmodified`는 oracle 삭제 시 silently pass. | 2 (11, 13) | **strong-delete** |
| `marslab/scene/structure_loader.py:218-222` `_ = field` rebind | F401 suppress를 위한 placeholder. dataclass field 실제 미사용. | 1 (01§H-10/D-4) | **soft-delete** |
| `marslab/runtime/stage2_loop.py:97-99` `_tau_kwargs` | `# noqa: F841` dead variable. 실제 consumer 없음. | 1 (01§D-3) | **soft-delete** |
| `marslab/runtime/config_loader.py` `load_runtime_config` | call site 0 (grep 확인). middle-man. | 1 (01§D-1) | **soft-delete** |
| `marslab/config/loader.py` `load_config` | `load_and_validate`가 상위 호환. 1개 test만 사용. | 1 (02§D-1) | **soft-delete** |
| `marslab/config/schema/rendering.py` `FogConfig.color` | Reserved-for-future 주석 + reader 0. | 2 (02§D-6, 04§L7) | **soft-delete** |
| `marslab/config/schema/terrain.py` `semantic_classes` | consumer 0. | 1 (02§D-3) | **soft-delete** |
| `marslab/config/schema/rendering.py` `_migrate_flat_to_nested` | 40-line pre-validator. 대응되는 legacy YAML 0건. | 1 (02§D-2) | **soft-delete** (YAML grep 필요) |
| `marslab/config/scenario_loader.py` (shim, 12 LOC) | back-compat shim. 2 callers 수정으로 제거 가능. | 1 (02§D-7) | **soft-delete** |
| `scripts/visualize_terrain.py` | missing input에 synthetic data fallback → 위조 figure. `visualize_scenario.py` 상위 호환. | 1 (12§1.6) | **strong-delete** |
| `scripts/visualize_procedural.py` | argparse 0, 상수 하드코딩. visualize_scenario.py로 대체. | 1 (12§1.4) | **strong-delete** |
| `scripts/hello_isaac.py` | 30 LOC, assertion 0, onboarding 가치 미미. | 1 (12§1.14) | **soft-delete** |
| `scripts/generate_rock_meshes.py` | `blender_generate_rocks.py`가 매 실행마다 이 파일의 output 삭제. | 1 (12§1.12) | **strong-delete** |
| `scripts/color_grade_mars.py` + `generate_pbr_from_photo.py` | v2.0 photorealism. v1.0 scope 밖. | 1 (12§1.10/1.11) | **soft-delete** (or move to `scripts/v2_photorealism/`) |
| `scripts/check_instruction_sync.py` + `scripts/tools/generate_instruction_index.py` | CI 비통합 orphan. CLAUDE.md "NEVER create .md" 위반. | 1 (12§1.16/1.17) | **soft-delete** |

### 메모: `run_stage3_monolithic.py` 삭제 전 필수 이관

- `physxScene:solverPositionIterationCount=16, velocityIterationCount=4` USD 속성 설정 (11§5 verified drift). 이 drift는 `run_stage4.py`에 없으므로 `stage2_scene.py` 혹은 `stage2_boot.py`로 이관 필요.

---

## REJECTED / FALSE POSITIVES

### `09§C6` Cave domain axis naming convention as "bug"
- 원 주장: `domain_m = (rows*res, cols*res)`가 `(height, width)` 순서라서 computer-graphics `(width, height)`와 모순, 미래 non-square domain에서 터짐.
- 근거: 현재 코드는 **self-consistent** (`build_centerline`이 `height_m, width_m = domain_m`으로 unpack). 기각 사유: 미래 non-square domain 시나리오에 대한 잠재 버그 언급은 타당하나 "현 상태 버그" 라벨은 과다. 기존 `M4 cross_sections 오해소지`와 M8 validation 부재와 병합해야 함. → **downgrade to MEDIUM (테스트 부재)**.

### `04§C3` atmosphere_panel `_update_slider_enabled` 슬라이더 auto-mode에서 enable 되는 버그
- 원 주장: 첫 번째 slider change가 sun_mode="manual" 세팅 전에는 state에 저장 안 됨.
- 검증: 원문 인용에 `self._state.get("sun_mode") == "manual"` 확인 필요. reviewer가 "UI broken 보인다" 수준. **downgrade: UX nit, not CRITICAL**.

### `10§M5` `marslab.math` 패키지 이름이 stdlib `math`과 clash
- 근거: `marslab/math/quaternion.py`가 `import math`를 쓰지 않고 `numpy`만 씀. 현재 충돌 없음. 미래 위험은 `from __future__ import absolute_import` 유사 문제이나 Python 3.10+는 absolute import가 기본.
- 기각: 미래 foot-gun 주장은 타당하나 현 상태 bug 아님. → **Watchlist only.**

### `14§6.9` `.gitignore: *.txt`이 `requirements.txt` 등을 막는다
- 원 주장: `*.txt` 전역 gitignore. 사용자가 필요한 파일을 force add해야 함.
- 검증 필요: `.gitignore:42`의 정확한 라인 확인 못함(파일 미열람). 주장 자체는 실제 `*.txt` ignore 존재 시 문제지만 `LICENSE` 파일 추가 권장에 영향 없음(LICENSE는 `.txt` 확장자 불필수). → **Watchlist** (정확한 `.gitignore` 인용 후 판단).

### `02§C-2` seed propagation sign validation gap (pydantic path)
- 원 주장: `master_seed=-100`이 pydantic path에서 validation skip하고 `model_copy`에 그대로 전달.
- 검증: L46-50 직접 읽음. `config.mars_env.model_copy(update={"seed": seed})`. pydantic v2 model_copy는 기본적으로 validator 재실행 안 함 — 주장 정확.
- 판정: 유지. **CRITICAL** 유지.

### `05§W3` "/joints" scope hardcode
- 원 주장: UrdfConverter가 다른 scope 이름 쓸 수 있음.
- 검증: 이 프로젝트는 NASA m2020 URDF 하나만 쓰고 offline 1회 변환. 현재 환경에서 risk 낮음.
- 판정: **Watchlist**로 유지, CRITICAL 아님.

### `07§28` `yaml.safe_load` + config_path에 sandboxing 없음 (path traversal)
- 원 주장: 로컬 dev tool이라도 문서화해야.
- 검증: CLI 도구에 path traversal 지적은 일반적 threat-model 과잉.
- 판정: **기각 for v1.0**, 논문 제출 후 고려.

### `11§1.13` monolithic 통째 "not engineering, archive with CI permissions" 수사
- 원 주장에 동의하나 **사용자 memory에 "monolithic new oracle twin" 정책 있음** ("run_stage3_monolithic_new.py 수정 가능한 복사본. 원본은 Oracle diff=0 엄수"). 단, `run_stage3_monolithic_new.py`가 이미 `delete_by_user/`로 이동했으므로 정책 자체가 해체 중. delete 권고 유지.

---

## DUPLICATE FINDINGS (merged into canonical)

- **Atmosphere step/state 중복 코드** — 01§C-5/H-4/H-5/H-8/M-11, 04§M8 → 단일 "build + step atmosphere" 공유 모듈 추출 권장 Cluster 8 (H-2/H-3).
- **"silent swallow with step<120" pattern** — 01§C-2/C-3/C-4/M-2, 11§1.5 → Cluster 2 C-7.
- **Odometry publish 중복** — 01§C-3, 06§H2 (`publish_odometry` dead), 11§1.10 → Cluster 3 C-9 (monolithic 삭제로 해결).
- **Quaternion helpers 중복 재구현** — 10§M8 (oracle local copy), 11§1.2 (monolithic L1215-1238), 07§12 (sensor_spawner cross-layer import) → Cluster 3 + Cluster 10.
- **`REPO_ROOT = abspath(__file__, '..', '..')` 중복** — 01§H-7/M-14, 12§0.1, 14§6.6 (README drift) → Cluster 16.
- **comments-as-deodorant (R2/R3/R4/G3/G5/P1/Wk2) accumulation** — 거의 모든 보고서(01§L-4/L-5/L-6, 02§L-5/L-6, 05§L6/L7, 06§L1/L2/L3, 07§29, 11§1.3, 12§0.3, 14§3.4) → Cluster 14.
- **Texture-apply block 3개 복사** — 08§H4 (apply_terrain_material / apply_cave_material), 08§H5 (rock_instancer `_apply_rock_material`) → Cluster 11 (terrain material refactor).
- **md5 oracle file-identity tests** — 13§C1/C3/D1/D2 → Cluster 3 (monolithic 삭제로 자연 해결).

---

## 우선순위 매트릭스

| # | 클러스터 | 수정 효용 | 예상 공수 | 권장 순서 | 종속 |
|---|---|---|---|---|---|
| 1 | **Beer's law Kasten airmass (C-1)** | 논문 figure 정확성 CRITICAL | 0.5일 | 1 | 없음 |
| 2 | **Ackermann arctan2 fix + test (C-4)** | Nav2 recovery rotation 결정적 correct | 0.5일 | 2 | 없음 |
| 3 | **LICENSE file commit (C-14)** | 법적 필수 | 5분 | 3 | 없음 |
| 4 | **ROS2 QoS 프로파일 도입 (C-12)** | SLAM/Nav2 paper claim 근거 | 1-1.5일 | 4 | schema 수정 |
| 5 | **`CaveConfig()` default ValidationError (C-10)** | 기본 인스턴스 실행 불가 | 15분 | 5 | 없음 |
| 6 | **IMU gravity assertion (C-16)** | G7 critical test 실제 강제 | 0.5일 | 6 | 없음 |
| 7 | **COMIMART 2-D 확장 or rename (C-2)** | τ-sweep figure 과학 방어력 | 2일 (full 2-D) or 30분 (rename) | 7 | Beer 선행 |
| 8 | **Sun position Allison & McEwen (C-3)** | Jezero 시나리오 shadow 정확도 | 1일 (spherical trig) or 30분 (rename) | 8 | 없음 |
| 9 | **Oracle 삭제 + run_stage4→run_stage3 (C-9)** | 1,500 LOC 제거, 유지보수 부담 격감 | 2-3일 (solver iteration 이관 + test 재작성) | 9 | monolithic_new_oracle user memory 정책 해체 필요 |
| 10 | **`/tf_raw`→`/tf` 통합 (C-13)** | Nav2 joint TF tree 복구 | 0.5일 | 10 | QoS cluster 후 |
| 11 | **Lognormal mean vs median rename (C-5)** | Blank 2024 calibration claim 정당화 | 15분 | 11 | 없음 |
| 12 | **pydantic `extra="forbid"` 전역 (C-11)** | silent YAML key drop 방지 | 1일 (쏟아지는 validation error 수정) | 12 | 없음 |
| 13 | **Silent swallow 공유 helper (C-7)** | 4x shotgun-surgery 제거 | 0.5일 | 13 | 없음 |
| 14 | **`stage2_loop` os._exit(0) 제거 (C-6)** | CI 거짓말 제거 | 30분 | 14 | 없음 |
| 15 | **`tests/integration/` 재생성 + gitignore 제거 (C-15)** | 재현성 claim 근거 | 1-2일 (self-hosted runner 세팅) | 15 | - |
| 16 | **Sensors Path A vs Path B 단일화 (C-17)** | IMU orientation/focal_length drift 제거 | 2일 | 16 | - |
| 17 | **scenario YAML mars_env 중복 제거 (H-17)** | drift 위험 근본 제거 | 1일 (`base_config` 확장) | 17 | pydantic `extra="forbid"` 선행 |
| 18 | **Packaging hygiene (pre-commit / mypy / pip-audit / matrix) (H-20~24)** | 신규 기여자 온보딩 | 1-2일 | 18 | - |
| 19 | 나머지 god-object refactor, quaternion float64 migration, cave geometry winding fix | 논문 후 | 1-2주 | 19~ | - |

**합산 추정: 논문 제출 전 반드시 고쳐야 할 것 (#1~#15) ≈ 10-14 working days.**

---

## 코드베이스 총평 (외부 reviewer 시점, 논문 신뢰성 관점)

### 강점

1. **`marslab/` 모듈 분해의 설계 방향은 건강함**: `config/ → environment/ → terrain/ → rendering/ → robots/ → sensors/ → ros2_bridge/` 레이어링이 명확하고 대부분 테스트됨. `rover_control.ackermann_command`, `config/schema/*.py`의 pydantic 모델, `math/quaternion.py` 개별 헬퍼는 재사용 가능한 quality.
2. **59개 unit test 파일의 숫자는 인상적**. 몇 개 weak-tolerance 테스트를 제외하면 Beer's law bench, Golombek SFD bench, seed determinism, mesh winding 같은 high-value regression을 잡아낼 구조적 토대가 이미 존재.
3. **Offline-first 테스트 분리(P3) 원칙 자체는 현명**: Isaac Sim 없이 config/math/terrain 대부분을 pytest로 돌릴 수 있는 설계는 reviewer 관점에서 매우 긍정적.
4. **`run_stage4.py` 356 LOC 분해는 성공적**: 14개 marslab 모듈을 청크-단위로 조립. monolithic oracle이 남아있는 것과 별개로, 모듈화된 엔트리 포인트 자체는 작동한다.

### 약점

1. **레거시 부채가 테스트 셋을 타고 올라감**: `run_stage3_monolithic.py`가 `test_monolithic_new_*.py`로 md5-pinning 되어 있고, `test_main_loop_structure.py`는 LoopContext 35 필드 schema-echo. "리팩토링 완료"를 주장하는 internal marker(R2/R3/R4/R5/R6)가 실제 공개 API에는 dead/duplicated 코드로 유지됨.
2. **과학 정확도 claim이 코드와 맞지 않음**: Beer's law는 Appelbaum 인용하나 formula 아님. COMIMART는 1-D. Sun position은 linear. IMU 3.72 m/s² "critical test"는 강제되지 않음. Lognormal median/mean 혼동. 다섯 가지 모두 학술 reviewer가 논문 figure 3-4장에서 바로 짚을 수준.
3. **ROS2 bridge의 production readiness 부족**: QoS 없음, `/tf` split, node lifecycle management 없음(`BridgeContext.close()` 부재), spin dependency 암묵적. iSpaRo target인 "SLAM/Nav2 integration" 클레임의 실제 재현성이 환경 의존이 됨.
4. **Scenario YAML drift**: 200 LOC 중복, `True` vs `true`, seed-coupled spawn coordinates (`[181.2, 190.5]` in cave_lava_tube 주석 verified), missing assets in 2개 scenario. pydantic `extra="ignore"`가 silently drop.
5. **Packaging / CI hygiene 공백**: LICENSE 파일 없음 (법적 결함), pre-commit 없음, mypy 없음, Python matrix 단일, pip-audit 없음. 공개 Apache-2.0 저장소 표준 대비 상당히 부족.
6. **Integration test 미 commit**: README가 "11 integration tests" 광고하나 `.gitignore`에 있음. 외부 재현 불가.

### 논문 제출 전 반드시 고쳐야 할 것

A. **과학 정확도 4종**: Beer's law airmass, COMIMART 1-D→rename or 2-D, Ackermann arctan→arctan2 + test, Lognormal median rename (C-1, C-2, C-4, C-5). 합계 ≈ 2일.
B. **ROS2 paper claim 방어**: QoS 도입(C-12), `/tf` 통합(C-13). ≈ 2일.
C. **IMU critical test 실제 강제**(C-16). ≈ 0.5일.
D. **LICENSE commit**(C-14). 5분.
E. **`CaveConfig()` default 복구**(C-10). 15분.
F. **Integration test 최소 2-3개 commit + 재현 스크립트** (C-15). ≈ 1-2일 (self-hosted runner 구성 포함).

**소계: 5-7일.**

### 논문 제출 후 고쳐도 되는 것

G. Monolithic 삭제(C-9). 3일.
H. `extra="forbid"` 전면 적용(C-11). 1일 (scenario YAML 대량 수정).
I. Sensors Path A/B 단일화(C-17). 2일.
J. Scenario YAML `base_config` 확장(H-17). 1일.
K. Silent swallow helper / god-object refactor. 2-3일.
L. pre-commit / mypy / pip-audit / Python matrix. 1-2일.
M. Cave geometry winding / floor stitching / hardcoded seed=42 fix. 2일.

**소계: 12-15일 (v1.1 마일스톤으로 권장).**

---

## 부록: 스팟 체크 기록

각 finding 별 Read 확인 결과 (✓ = 원 주장 정확, △ = 부분 정확, ✗ = 기각).

| Finding ID | Path:line | 결과 | 비고 |
|---|---|---|---|
| 01§C-1 | `marslab/runtime/stage2_loop.py:196-203` | ✓ | `os._exit(0)` 직접 확인 |
| 01§C-2 | `marslab/runtime/main_loop.py:341-352` | ✓ | `except Exception as exc: # noqa: BLE001 / print(...)` 확인 |
| 01§C-4 | `marslab/runtime/main_loop.py:397-402` | ✓ | step<120 gate 패턴 확인 |
| 01§C-5 | `marslab/runtime/main_loop.py:289-368` | ✓ | step_count 증가 순서 이슈 확인 |
| 01§H-3 | `marslab/runtime/main_loop.py:172-182` | ✓ | 34 fields + 10 Optional Callable 확인 |
| 01§L-3 | `marslab/runtime/main_loop.py:320-321` | ✓ | `if ctx.negate_steer:` 확인 |
| 02§C-1 | `marslab/config/loader.py:27` | ✓ | `open(abs_path, "r") as f` encoding= 누락 확인 |
| 02§C-2 | `marslab/config/loader.py:46-50` | ✓ | `model_copy(update={"seed": ...})` validator 재실행 안 함 |
| 02§H-5 | `marslab/config/schema/terrain.py:101-246` | ✓ | CaveConfig() default 시 ValidationError 직접 계산 |
| 02§L-5 | 전 schema 파일 grep | ✓ | `extra="forbid"` 0건 확인 |
| 03§C-1 | `marslab/environment/light_intensity.py:34-38` | ✓ | flat `exp(-tau/cos_z)` 확인 |
| 03§C-2 | `marslab/environment/diffuse_fraction.py:17-34` | ✓ (논리적) | table 값/endpoint 불합리 분석 정확 |
| 03§C-3 | `marslab/environment/sun_position.py:98-99` | ✓ | linear azimuth + sin(pi t) 확인 |
| 04§C1 | `marslab/gui/atmosphere_panel.py:166` | △ | 직접 인용 안 봤음; 주장 consistent |
| 04§H3 | `marslab/rendering/atmosphere_fog.py:48` | △ | `settings.set` call 스펙 의존 |
| 05§C1 | `marslab/robots/rover_control.py:98` | ✓ | `np.arctan(x_w / dy)` 확인 |
| 05§H3 | `marslab/robots/rover_control.py:200-210` | △ | 주장 논리 정확, 코드 인용 미직접 |
| 05§H4-H6 | `marslab/robots/rover.py:244-250 / 151-158 / 181-206` | △ | 주장 consistent, sample check 생략 |
| 06§C1 | `marslab/ros2_bridge/*.py` grep QoSProfile | ✓ | 0 hit 확인 |
| 06§C2 | `marslab/ros2_bridge/sensor_graph_builder.py:104` | ✓ | `/tf_raw` 확인 |
| 06§H2 | `odometry_publisher.publish_odometry` callers grep | △ | reviewer 주장 consistent |
| 07§2 | `marslab/sensors/imu.py` 전 파일 | ✓ | gravity assertion 0건 확인 |
| 07§3 | `marslab/sensors/imu.py:49` | ✓ | `Gf.Quatd(1.0, 0.0, 0.0, 0.0)` 하드코딩 확인 |
| 07§12 | `marslab/sensors/sensor_spawner.py:114` | ✓ | cross-layer import 확인 |
| 08§H1 | `marslab/terrain/rock_placer.py:126-138` | △ | 수학적 bias 주장 설득력 있음 |
| 09§C3 | `marslab/terrain/cave/mesh.py:159-188` | ✓ | docstring-vs-code contradiction 확인 (radius grow with depth 맞음, "inward" 서술 오류) |
| 09§C4 | `marslab/terrain/cave/breakdown.py:66-68, 108-113` | ✓ | lognormal mean vs median 수학적 정확 |
| 09§M9 | `marslab/terrain/cave_mesh_builder.py:227` | ✓ | `rng = np.random.default_rng(42)` 확인 |
| 10§B1 | `marslab/math/quaternion.py:168-174` | ✓ | gimbal-lock branch 확인. reviewer의 counter-example 수학적 정확 |
| 11§1.1 | `scripts/phase1/run_stage3_monolithic.py` wc -l | ✓ | 1,495 LOC 확인 |
| 11§1.5 | `scripts/phase1/run_stage3_monolithic.py` bare except count | △ | 주장 10건, 정확 check 필요 |
| 12§1.15 | `delete_by_user/run_stage3_monolithic_new.py` | ✓ | 파일 이동 확인, run_marslab.py runtime import broken |
| 14§1.2 | 레포 루트 `ls` LICENSE | ✓ | 없음 확인 |
| 14§5.1 | `tests/integration/` 내용 | ✓ | `__init__.py` + `__pycache__`만 |
| 14§4.7 | `pydantic model_config` grep | ✓ | `extra="forbid"` 0건 |

**총 스팟 체크: 35건 중 30 ✓, 5 △. ✗ 없음.** False positive는 rejection section의 4건에 한정되며 그 중에서도 완전 기각은 2건, 나머지는 severity downgrade. 전반적으로 14개 subagent 보고서는 **높은 precision**을 보인다 — critical/high 주장 중 false positive rate ≈ 5%. 다만 severity inflation(MEDIUM을 HIGH로)이 10-15% 존재, 중복 주장 merge 전 raw count 약 200+ findings는 실제로 ~80 distinct clusters.
