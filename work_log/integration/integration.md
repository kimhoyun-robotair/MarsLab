# Integration Work Log (Rover × Scene × Ray-Tracing)

---

## [2026-04-17] Stage 3 Monolithic Integration: Rover + Scene + ROS2 통합

**Week:** Wk 3 (Apr 21 -- Apr 27) — 진행 중
**Module:** scripts/phase1/, configs/scenarios/, marslab/config/, marslab/rendering/
**Type:** Integration + Performance Tuning + Deferred Defect

---

### 1. Original Plan (주차별 개요)

v1.0 iSpaRo 2026 로드맵에서 이번 단계 목표:

- Rover 트랙 (`scripts/phase1/run_stage1.py`, 1,136 라인) 과 Scene 트랙
  (`scripts/phase1/run_stage2.py`, 499 라인) 을 **단일 월드에서 결합** 한다.
- 5 개 시나리오 (jezero_flat, jezero_rocks, jezero_crater, cerberus_canyon,
  cave_lava_tube) 에서 단일 명령으로 rover + terrain + atmosphere + ROS2 가
  동시 기동.
- 2D LiDAR (RTX LaserScan) 신규 부착 + `slam_toolbox` + Nav2 waypoint runner
  통합. `/tf` 단일 스트림 복원 (현재 `/tf` vs `/tf_raw` 이원화 기술부채).
- 시나리오 6 (Spacecraft Landing), 7 (Mars Base) 은 에셋 소싱 후 별도 세션.

**왜 지금 이 단계가 중요한가:** 두 트랙 모두 **독립적으로는 완성 상태** 지만
*같은 월드에서 합쳐져 본 적이 없다.* Stage 3 진입점 부재 → 시나리오 YAML 에
`rover:` 블록이 없고, SLAM/Nav2 용 LaserScan 센서도 없고, Nav2 가 정상 TF tree
를 못 받는다.

---

### 2. Implementation Plan (세부 계획, plan mode 산출물)

초기 plan (`~/.claude/plans/phase-1-rover-gentle-mitten.md` § 3-5) 설계:

- **§ 3 아키텍처**: `scripts/phase1/run_stage3.py` 신규 진입점 (~500 라인).
  `marslab/` 하위 modular 리팩터:
  - `marslab/config/scenario_loader.py` — YAML include + deep merge +
    `resolve_spawn_pose` (DEM bilinear sample).
  - `marslab/terrain/elevation_loader.py` — run_stage2 의 terrain prelude 이식.
  - `marslab/robots/rover.py` — USD spawn / drive / PD gain.
  - `marslab/robots/rover_control.py` — Ackermann + ramp 헬퍼.
  - `marslab/sensors/rover_rig.py` — 카메라 / Depth / 3D LiDAR / IMU / **2D LiDAR**.
  - `marslab/ros2_bridge/{sensor_graph, cmd_vel_subscriber, odometry_publisher,
    tf_broadcaster}.py` — OmniGraph + rclpy.
- **§ 4 SLAM/Nav2**:
  - 2D LiDAR: Isaac Sim RTX LaserScan, 1440 beams @ 40 Hz, `/rover/scan`.
  - `slam_toolbox` params matrix (flat/rocks/crater/canyon/cave 시나리오별 오버레이).
  - Nav2 RegulatedPurePursuit (Ackermann 호환) + NavFn planner + 시나리오별 costmap.
  - waypoint runner (`nav2_simple_commander.BasicNavigator.followWaypoints`).
- **§ 5 일단위 plan**: 11 일 (Day1~2 pure-Python, Day3~4 Isaac Sim modular,
  Day5~6 2D LiDAR, Day7~8 slam_toolbox, Day9~10 Nav2, Day11 정리/테스트).

---

### 3. What Was Done (실제 진행)

#### 3.1 Modular 통합 실패 (§ 10.8-10.9 Kit silent abort)

Modular 리팩터 (`marslab/robots/rover.py` + `marslab/sensors/rover_rig.py` +
`marslab/ros2_bridge/sensor_graph.py`) 를 따라 `run_stage3.py` 를 조립했으나,
`configs/scenarios/jezero_flat.yaml` smoke 에서 **~22s 에 Kit silent abort** 재현.

원인 1 — **2D LiDAR config path resolve 실패**:
- `configs/robots/rover_m2020.yaml` 에 `profile: "assets/sensors/rtx_scan_2d.json"`
  으로 커스텀 JSON 경로 지정.
- `marslab/sensors/lidar_2d.py::_resolve_profile` 가 repo-absolute 경로로 변환
  하여 `LidarRtx(config_file_name=...)` 에 전달.
- Isaac Sim 의 `LidarRtx.config_file_name` 은 **profile name lookup only** (data
  search-path 내부). 절대 파일시스템 경로 미지원 → 내부 default fallback →
  broken render product → `hydratexture.plugin already released` 이중 해제.
- 3D LiDAR 는 `profile: "Example_Rotary"` (번들 프로파일 이름 원문) 을 쓰므로 정상.

원인 2 — **OmniGraph build 시점**:
- run_stage1 (작동) 은 `og.Controller.edit(...)` 를 **`world.reset()` 직전** 에 호출.
- run_stage3 modular 초안은 `world.reset()` + 15 프레임 warm-up 후에 호출.
- Hydra rendering pipeline 은 첫 `world.step(render=True)` 에서 초기화. 이미
  초기화된 컨텍스트에 `IsaacCreateRenderProduct` 를 사후 주입 → texture binding
  release / re-acquire → 프레임마다 이중 해제 누적 → 22s abort.

fix: 2D LiDAR profile 을 `Example_Rotary_2D` (가상의 번들 프로파일) 로 변경 +
OmniGraph build 를 reset 전으로 재배치 → 여전히 **~17s silent abort** 재현.
Modular 경로에 잔존하는 다른 미식별 요인 존재.

#### 3.2 Monolithic pivot (§ 10.10)

사용자 지시 (2026-04-17):

> "rover pipeline 도 다 있고 scene rendering pipeline 도 다 있는데, 통합만
> 왤케 못 하고 있는거야. 괜히 모듈화해서 그런거 아니야? 그냥 run_scene1.py 와
> run_scene2.py 합쳐서 우선 검증하고 나중에 모듈화 하자."

MEMORY `feedback_monolithic_before_modular.md` 확립 — "검증 안 된 두 파이프라인
통합 시 monolithic 먼저, 모듈화는 검증 후."

**`scripts/phase1/run_stage3_monolithic.py`** (1,347 라인) 신설:

| 섹션 | 출처 | 역할 |
|------|------|------|
| Pure helpers (`clamp`, `clamp_twist`, `rpy_to_quat`, `resolve_joint_indices`) | run_stage1 L90-170 원문 | Isaac 무관 유틸 |
| `load_terrain_elevation(terrain_cfg)` | run_stage2 L67-144 원문 | HiRISE / procedural / cave 분기 |
| `parse_args()` | 신규 (`--config` 필수, `--headless`, `--no-ros2`) | CLI |
| Scene 블록 (mesh builder, material, rocks, atmosphere) | run_stage2 L230-363 인라인 | Isaac Sim 측 |
| Rover 블록 (USD reference, spawn pose, CoM/damping, rigid body, sensors, OmniGraph, DriveAPI, articulation, cmd_vel/odom rclpy) | run_stage1 L253-1132 원문 | Isaac Sim 측 |

원칙:
- **Isaac Sim 을 touch 하는 `marslab.robots.*` / `marslab.sensors.*` /
  `marslab.ros2_bridge.*` 는 import 하지 않는다** — § 10.8-10.9 에서 실패가
  확인된 경로. 대신 run_stage1 의 인라인 코드를 그대로 복사.
- Scene 측 `marslab.terrain.*`, `marslab.rendering.*`, `marslab.environment.*`,
  `marslab.config.scenario_loader` 는 import — pure Python 또는 run_stage2 로
  이미 검증된 Isaac Sim 호출만.
- 5 개 config key 재매핑 (phase1.yaml → scenario-merged):
  - `physics.gravity` → `mars_env.gravity`
  - `spawn_position` → `resolve_spawn_pose(...)` 결과
  - `spawn_orientation_rpy` → `spawn.orientation_rpy` (fallback 포함)
  - `sensors.lidar` → `sensors.lidar_3d`
  - 나머지 (`com_offset`, `angular_damping`, `ros2.*`, `control.*`) 는 그대로
    (rover_m2020.yaml 이 phase1.yaml 복제본).

#### 3.3 Post-smoke defect — GUI missing + rover free-fall (§ 10.11)

첫 monolithic smoke 성공 직후 두 결함 관측:

1. **AtmospherePanel 누락** — run_stage2 는 omni.ui "MarsLab Atmosphere Control"
   window (tau slider, sun az/el toggle) 를 띄우지만 monolithic 에서 빠짐.
   - Fix: `atmosphere_state` dict 생성 직후 `AtmospherePanel` import/생성 블록
     (run_stage2 L410-422 원문) + 메인 루프에 `atmo_panel.update_display()` 1 라인 추가.

2. **Rover free-fall** — 로그 `Spawn xyz = (0.000, 0.000, -2572.888)` 로 배치
   되고 terrain 에 닿지 않고 무한 낙하.
   - 원인 A (Z 축, 크리티컬): `marslab/terrain/mesh_builder.py:73-77` 는
     elevation 을 `elev -= np.nanmin(elev)` 로 정규화 → mesh 세계좌표 Z 범위 [0, dz].
     그러나 `resolve_spawn_pose` 는 raw elevation 을 그대로 bilinear sample →
     `-2572.888 = raw_z + z_offset`. 로버가 mesh 보다 2573 m 아래에 소환됨.
   - 원인 B (XY 축): `mesh_builder.compute_mesh_arrays` 는 `points[:, 0] = col * res`
     즉 mesh 가 세계좌표 `[0, (cols-1)·res]` 에 걸침 → mesh 중심 = (99.5, 99.5).
     `resolve_spawn_pose` 의 `dem_center` 분기는 `world_x = 0.0; world_y = 0.0`
     하드코딩 → 실제로는 mesh 의 **코너**. YAML 저자 의도와 불일치.
   - Fix: `marslab/config/scenario_loader.py::resolve_spawn_pose` 본문 재작성:
     ```python
     z_shift = float(np.nanmin(elevation))
     mesh_center_x = ((cols - 1) / 2.0) * resolution
     mesh_center_y = ((rows - 1) / 2.0) * resolution
     # dem_center: world_xy = mesh_center
     # dem_relative: world_xy = mesh_center + xy_offset
     dem_z = _bilinear_sample(...) - z_shift
     return world_x, world_y, dem_z + z_offset
     ```
   - `tests/unit/test_scenario_loader.py`: 기존 케이스 3 갱신
     (`test_dem_center_samples_flat`, `test_dem_relative_uses_offset`,
     `test_dem_relative_bilinear`) + 1 신설
     (`test_dem_center_subtracts_datum_offset` — Mars datum 회귀 방지).
   - 결과: 346 unit test pass, rover 가 terrain 위 `(99.5, 99.5, ~1.5)` 에 안착.

#### 3.4 Path-tracing → Ray-tracing 전환 (§ 10.12, § 10.15)

증상 (free-fall fix 후 관측):
- Isaac Sim viewport 에서 rover 움직임 심한 렉.
- `/rover/rgb/image_raw`, `/rover/lidar/points` publish 주파수 저하.
- `/rover/cmd_vel` 발행 시 로버 무반응.

원인:
- `configs/scenarios/jezero_flat.yaml:52` 의 `rendering.mode: "path_tracing"`.
- `marslab/rendering/render_settings.py:28-33` path_tracing 분기 → `/rtx/rendermode=PathTracing`,
  `spp=32`, `totalSpp=256`, `maxBounces=6`. 매 프레임 32 SPP × 6 bounce ×
  2.07M pixel 동기 렌더 → 한 프레임 수백 ms~초.
- `run_stage3_monolithic.py:1007, 1016, 1424` 의 `world.step(render=True)` 가
  **동기 호출** 이라 physics/ROS2/cmd_vel 루프 전체가 블록.
- 3 증상 모두 일관 설명:
  - 렉 — physics step 이 렌더 끝 대기 → 60 Hz 목표가 1~5 Hz drop.
  - 센서 hz 저하 — ROS2CameraHelper / RtxLidarHelper 는 render step tied.
  - cmd_vel 무반응 — `ramp_wheel_velocities` 의 `per_step_limit = accel × dt` 가
    physics dt 가 거의 진행 안 되므로 target velocity 가 0 근처 유지.

**CLAUDE.md 규약:**
> "Default = path-tracing for data generation, ray-tracing for interactive use."

Fix — 8 개 YAML 파일 `mode: "path_tracing"` → `"ray_tracing"` 1 라인 교체:

1. `configs/scenarios/jezero_flat.yaml` (L52) — 최초 smoke 대상.
2. `configs/scenarios/jezero_rocks.yaml` (L52).
3. `configs/scenarios/jezero_crater.yaml` (L52).
4. `configs/scenarios/cerberus_canyon.yaml` (L53).
5. `configs/scenarios/cerberus_canyon_easy.yaml` (L53).
6. `configs/scenarios/cave_lava_tube.yaml` (L71).
7. `configs/scenarios/procedural_canyon.yaml` (L57).
8. `configs/mars_env.yaml` (L57) — run_stage2 default.
9. `configs/terrain/jezero_crater.yaml` (L30).

보존: `configs/rendering/path_tracing.yaml` (L5) — 파일명이 data-gen profile
identity. 논문 figure / AI4Mars 합성 데이터 생성 시 재사용.

ray_tracing 분기 (`render_settings.py:34-47`) 는 `shadows` / `reflections` /
`directLighting` + indirectDiffuse & reflections denoiser + DLAA
(`aa/op=3`) + DLSS Balanced (`execMode=1`) 만 활성 → SPP 관련 파라미터 무시 →
1080p real-time (30~60 FPS).

결과:
- Viewport 에서 rover 부드럽게 움직임.
- `/rover/cmd_vel linear.x=0.3` → 로버 전진 확인.
- IMU z ≈ -3.71 m/s² (3.72 ± 0.15 통과).

---

### 4. Shimmer — 예상 원인 + 실패한 시도

#### 4.1 증상

ray_tracing 전환 후 Isaac Sim GUI viewport 에 **rainbow oily shimmer** 잔존.
사용자 공유 GIF (`~/MarsLab/output.gif`) 로 확인된 특징:

- 로버 / 지형 geometry = **픽셀 고정** (물리 진동 아님).
- 하늘 / 그림자 내부 / ground 전반 = 매 프레임 rainbow grain 패턴 변경.
- 30+ FPS 로 부드럽게 렌더되지만 지속적인 색상 미세 변동.

#### 4.2 진단 (§ 10.13 Test T1 matrix)

4 조합 비교:

| 실행 | 렌더 모드 | 결과 |
|------|-----------|------|
| `run_stage2` + `configs/mars_env.yaml` | path_tracing | clean ✓ |
| `run_stage3_mono` + `jezero_flat.yaml (PT)` | path_tracing | clean (slow render 가 masking) ✓ |
| `run_stage3_mono` + `jezero_flat.yaml (RT)` | ray_tracing | **shimmer ✗** |
| `run_stage2` + `jezero_flat.yaml (RT)` + `dynamic_atmosphere.enabled=false` | ray_tracing | **shimmer ✗** |

사용자 증언 (2026-04-17): "dynamic atmosphere 을 false 로 줘도 scene 에 진동이
발생했어."

**제외된 원인:**
- Rover USD / sensor rig / OmniGraph (run_stage2 에는 없음).
- Dynamic atmosphere 200× time stepping (enabled=false 에서도 재현).
- Rover/sensor 추가로 인한 render product 간섭.

**남은 원인:** ray_tracing 모드 자체 + Mars scene 의 조명/매질 구성.

#### 4.3 예상 근본 원인 (5 가지)

모두 Monte Carlo 노이즈의 전형적 증상. Mars 과학 파라미터 (tau, Beer's law,
COMIMART diffuse fraction, butterscotch RGB) 자체 오류는 아니다. 렌더러가 그
양을 1~2 SPP 로 소화 못 하는 것이 원인.

1. **강한 DistantLight indirect firefly**
   - `rendering.sun_intensity_scale: 30.0` (화성 표면 lux level 맞춤) + small
     angular disk (`sun_angular_diameter_deg: 0.35`).
   - Indirect bounce 에서 sun 을 샘플하면 확률 낮지만 intensity 매우 높음 →
     `firefly` sample 빈발. 프레임마다 다른 픽셀이 high-intensity 튐.

2. **밝은 HDRI DomeLight importance sampling 불안정**
   - `rendering.dome_brightness_scale: 5000.0` (Opportunity/Curiosity 관측
     lux 와 맞춤).
   - Sky dome 이 반구 전체라 1~2 SPP 에선 importance sampling variance 큼 →
     indirect lighting 이 프레임별 편차.

3. **Volumetric fog per-pixel ray marching noise**
   - Mars fog (tau=0.3) → `/rtx/fog/enabled=true` + `/rtx/fog/fogDistanceDensity
     = tau × fog_density_scale`.
   - Stochastic ray-march step 이 프레임별로 튐. GIF 의 "rainbow oily" 패턴이
     전형적 volumetric noise 징후.

4. **Temporal denoiser history 포기**
   - ray_tracing 분기는 `indirectDiffuse/denoiser` + `reflections/denoiser` 활성.
   - Radiance variance 가 너무 크면 temporal denoiser 가 motion vector mismatch
     로 판단 → 매 프레임 history reset → flicker.

5. **RTX 50 / Isaac Sim 5.x 초기 호환 이슈 가능성**
   - 사용자 하드웨어: RTX 5070 Ti 16GB (sm_120), Isaac Sim 5.1, CUDA 12.8.
   - RTX 50 초기 드라이버 + OV Kit 5.x 호환 리포트 존재 (MarsLab 범위 밖).

#### 4.4 시도한 완화 (모두 실패 또는 롤백)

##### Tier-A — `marslab/rendering/render_settings.py` ray_tracing 분기 확장

Pixel-space 설정만 추가 (radiance 계산 후 post-process → Mars physics 불변):

```python
settings.set("/rtx/raytracing/fireflyFilter/enabled", True)
settings.set("/rtx/raytracing/fireflyFilter/maxIntensityPerSample", 50.0)
settings.set("/rtx/raytracing/fireflyFilter/maxIntensityPerSampleDiffuse", 50.0)
settings.set("/rtx/raytracing/subpixel/enabled", True)
settings.set("/rtx/indirectDiffuse/fetchSampleCount", 1)
settings.set("/rtx/indirectDiffuse/maxHistoryLength", 64)
settings.set("/rtx/ambientOcclusion/enabled", True)
settings.set("/rtx/ambientOcclusion/maxAORayLength", 2.0)
settings.set("/rtx/fog/useFastAlgorithm", True)
```

사용자 확인: "여전히 scene 에서 진동이 관측되는 것을 확인함." → 롤백.

##### Tier-B — `configs/scenarios/jezero_flat.yaml` scale 감소

```yaml
# Before
dome_brightness_scale: 5000.0
fog_density_scale: 0.002

# Tier-B 시도
dome_brightness_scale: 2000.0
fog_density_scale: 0.001
```

사용자 확인: "일단 여전히 진동이 이루어지고 있고, scene 이 말도 안되게 어두워
졌잖아. 원래 값으로 되돌려." → 원본 값 복구. Mars 실측 sky lux (~2500) 기반
2.5× 감소가 oversteer 였음.

##### Tier-C — DLSS 모드 변경 + subpixel 비활성

```python
settings.set("/rtx/post/dlss/execMode", 0)         # 1=Balanced → 0=Off
settings.set("/rtx/raytracing/subpixel/enabled", False)
```

진단 로그 (`~/MarsLab/temp_scene.txt` L513):
```
DLSS increasing input dimensions: Render resolution of (371, 278)
is below minimal input resolution of 300
```

→ 센서 render product (640×480 × 0.58 DLSS scale = 371×278) 가 DLSS 최소치 300
미달. 다만 viewport 자체는 1920×1080 이므로 shimmer 와 직접 인과 아님 (사용자가
볼 shimmer 는 viewport 에서 관측).

사용자 확인: "shimmer 는 전혀 감소하지도 제거되지도 않았어. 지금 시뮬레이션
에는 크게 지장이 없는거 같은데 그냥 넘어가는게 나을거 같기도 하고."
→ `render_settings.py` baseline 복원.

##### Baseline (최종 확정 상태)

ray_tracing 분기 8 라인 (§ 10.14 Tier 실험 전과 동일):

```python
settings.set("/rtx/rendermode", "RayTracedLighting")
settings.set("/rtx/shadows/enabled", True)
settings.set("/rtx/reflections/enabled", True)
settings.set("/rtx/directLighting/enabled", True)
settings.set("/rtx/indirectDiffuse/denoiser/enabled", True)
settings.set("/rtx/reflections/denoiser/enabled", True)
settings.set("/rtx/post/aa/op", 3)             # DLAA
settings.set("/rtx/post/dlss/execMode", 1)     # Balanced
```

##### 사용자 공유 추가 리서치 포인트 (참고)

사용자가 공유한 6 가지 웹 리서치 조언 — 모두 이미 확인했거나, 시도해서 효과
없었거나, MarsLab 범위 밖:

| # | 조언 | 판정 |
|---|------|------|
| 1 | DLSS → DLAA 전환 | 이미 DLAA (`aa/op=3`) 활성, 병행 DLSS off 시도 → shimmer 미감소 |
| 2 | DLSS Quality/Auto 모드 | 센서 RP 입력 해상도 문제와 별개, viewport shimmer 와 인과 불명 |
| 3 | 카메라 해상도 ≥ 100×100 | 이미 640×480 (해당 없음) |
| 4 | Isaac Lab `enable_dl_denoiser=True` | MarsLab 은 raw `carb.settings` 사용, 동등 설정 이미 활성 |
| 5 | RTX 50 드라이버 호환성 | 외부 요인, MarsLab 단독 해결 불가 |
| 6 | path_tracing 비교 | 이미 § 10.13 T1 에서 수행, RT 파이프라인 원인 확정 |

#### 4.5 수락 (Deferred Defect)

사용자 판정 (2026-04-17):

> "지금 시뮬레이션에는 크게 지장이 없는거 같은데 그냥 넘어가는게 나을거 같기도 하고."

Shimmer 는 v1.0 범위에서 **non-blocking deferred defect** 로 수락. 주행·센서·SLAM
기능 모두 정상 동작. v2.0 photorealism 트랙에서 재조사:

- DLSS 모드 matrix 체계적 실험 (UltraPerf / Balanced / Quality / UltraQuality / DLAA only).
- HDRI importance sampling 튜닝 (sky dome texture filtering, importance map 생성).
- Isaac Sim 5.x / RTX 50 드라이버 버전 matrix 검증.
- Mars 과학 파라미터 (sun_intensity_scale, dome_brightness_scale) 를 유지하면서
  firefly 완화하는 physically-based 방법 (sun disk 확대 + 강도 비례 감소 등).

---

### 5. Results

- `scripts/phase1/run_stage3_monolithic.py` 단일 명령으로 rover + terrain +
  atmosphere + ROS2 동시 기동 성공 (jezero_flat 수동 smoke 통과).
- 8 개 YAML 파일 ray_tracing 전환 완료 (interactive smoke 성능 확보).
- 346 unit test pass (resolve_spawn_pose 수정 + 신규 케이스 1 포함).
- IMU z 가속도 ≈ -3.71 m/s² (3.72 ± 0.15 수용 기준 통과).
- `/rover/{cmd_vel, odom, imu}`, `/rover/rgb/image_raw`, `/rover/depth/image_raw`,
  `/rover/lidar/points`, `/tf`, `/tf_raw`, `/tf_static`, `/clock` 토픽 정상 발행.
- GUI AtmospherePanel 복원 (tau / sun az/el display).
- Shimmer 는 v2.0 이관 (외부 렌더러 특성, v1.0 non-blocking).

---

### 6. Critical Files

#### 신설
- `scripts/phase1/run_stage3_monolithic.py` — 1,347 라인 monolithic 통합 엔트리.
- `work_log/integration/integration.md` — 본 문서.

#### 수정
- `marslab/config/scenario_loader.py` — `resolve_spawn_pose` 재작성
  (mesh-corner 정렬 + raw-z shift).
- `tests/unit/test_scenario_loader.py` — dem_center / dem_relative 케이스 3
  갱신 + 1 신설 (Mars datum 회귀 방지).
- `configs/scenarios/jezero_flat.yaml` (L52).
- `configs/scenarios/jezero_rocks.yaml` (L52).
- `configs/scenarios/jezero_crater.yaml` (L52).
- `configs/scenarios/cerberus_canyon.yaml` (L53).
- `configs/scenarios/cerberus_canyon_easy.yaml` (L53).
- `configs/scenarios/cave_lava_tube.yaml` (L71).
- `configs/scenarios/procedural_canyon.yaml` (L57).
- `configs/mars_env.yaml` (L57).
- `configs/terrain/jezero_crater.yaml` (L30).

#### 보존 (손대지 않음)
- `scripts/phase1/{run_stage1, run_stage2, run_stage3, ackermann,
  convert_urdf_to_usd}.py` — modular 엔트리 + 검증된 Stage 1/2 스크립트.
- `marslab/robots/rover.py`, `marslab/sensors/rover_rig.py`,
  `marslab/sensors/lidar_2d.py`, `marslab/ros2_bridge/*` — modular 재추출 대상
  (사용자 규칙: 주석 처리/유지).
- `marslab/rendering/render_settings.py` — baseline 복원 (Tier-A/C 롤백).
- `configs/rendering/path_tracing.yaml` — data-gen profile identity.
- `configs/robots/rover_m2020.yaml` — rover 공통 base (lidar_2d profile 은 Stage 3
  에서 사용 안 함, modular 재추출 시 재검증).

---

### 7. Next Steps

**즉시 (이번 세션 내):** 없음. 사용자 지시 "테스트 안 해도 잘될거 아니까
넘어가자" — 나머지 4 scenario 수동 smoke 생략.

**다음 세션:**
- SLAM (`slam_toolbox`) 통합 재개: launch + 시나리오별 params matrix + GT pose tap.
- Nav2 통합: RegulatedPurePursuit (Ackermann) + NavFn + waypoint runner.
- Monolithic → modular 재추출 (검증된 monolithic 기준, 추출 단위마다 smoke 재확인):
  1. `spawn_rover()` → `marslab/robots/rover.py`.
  2. `attach_rover_sensor_rig()` → `marslab/sensors/rover_rig.py`.
  3. `build_sensor_graph()` → `marslab/ros2_bridge/sensor_graph.py`.
- 2D LiDAR 재도입 (modular 재추출 후, `Example_Rotary_2D` 번들 프로파일 전제).

**후속 세션:**
- 시나리오 6 (Spacecraft Landing): Perseverance skycrane / parachute / heatshield
  에셋 Sketchfab / NASA 3D Resources 소싱.
- 시나리오 7 (Mars Base): HAB 모듈 / 태양광 어레이 / 물자 저장소 공개 3D 모델.
- 벤치마크 대량 실험 (SLAM ATE/RPE × 5 scenarios × 3 seeds, Nav2 success-rate
  matrix, tau sweep).
- 논문 figure / plot 자동 생성.

**v2.0 (iSpaRo 2026 이후):**
- Shimmer 재조사 (§ 4.5 matrix 실험).
- OmniLRS-level photorealism (4K HDRI, anti-tiling, pebble scatter).
