---
title: wiki "확인 필요" 플래그 집계
last_updated: 2026-04-21
scope: wiki/**/*.md 전수
status: T4 초판
total_count: 89
---

## 1. 요약

- 전체 건수: **89**
- 출현 md 수: **57** (전체 147 중 약 **38.8%**)
- 상위 5개 파일: `scripts/phase1/run_stage3.md` (4), `scripts/blender_generate_rocks.md` (4), `_risks.md` (4), `scripts/visualize_atmosphere.md` (3), `scripts/phase1/run_stage3_monolithic.md` (3)

카테고리별 건수 (중복 분류 없음, 단일 분류 기준):

| 카테고리 | 건수 |
|---------|------|
| 2.1 구현 부재·스텁 | 19 |
| 2.2 외부 에셋 실재성 | 10 |
| 2.3 런타임 동작 미검증 | 19 |
| 2.4 문서·코드 드리프트 | 27 |
| 2.5 기타 (메타/원칙 언급) | 14 |

> 주: 메타 언급(2.5) 은 "CLAUDE.md, PLAN.md, \_glossary.md, \_risks.md" 에서 본 추적 규약 자체를 인용하는 문장을 포함. 실제 미해결 이슈는 **75 건 (89 − 14)** 으로 볼 수 있다.

## 2. 카테고리별 그룹핑

### 2.1 구현 부재·스텁

1. [marslab/environment/sun_position.md:86](marslab/environment/sun_position.md) "`start_azimuth_deg > end_azimuth_deg` 조합(예: 북반구 겨울, 태양이 남쪽만 횡단) 에 대한 unit test 커버리지 확인 필요."
   - 배경: sun_position 유닛 테스트 커버리지 점검
   - 해결 단서: `tests/unit/test_sol_sun_position.py` 를 grep 해서 실제 케이스 확인

2. [marslab/terrain/mesh_builder.md:79](marslab/terrain/mesh_builder.md) "현재 `tests/unit/test_mesh_builder.py` 가 법선 방향 assert 하는지는 확인 필요"
   - 배경: 법선 반전 회귀 방지용 테스트 존재 여부
   - 해결 단서: `tests/unit/test_mesh_builder.py` 파일 내부 assertion 검사

3. [marslab/terrain/material_applicator.md:88](marslab/terrain/material_applicator.md) "`tests/unit/test_materials.py` 가 어떻게 검증하는지 확인 필요"
   - 배경: pxr import 때문에 offline 테스트 가능 범위 불명
   - 해결 단서: 기존 `tests/unit/test_materials.py` 의 mocking 전략 확인

4. [marslab/ros2_bridge/cmd_vel_subscriber.md:63](marslab/ros2_bridge/cmd_vel_subscriber.md) "직접 단위 테스트 없음. `test_ros2_bridge_structure.py` 는 surface 검사만 하므로 콜백 동작은 통합 smoke 에서만 검증된다."
   - 배경: cmd_vel subscriber 콜백 테스트 부재
   - 해결 단서: callback 단독 unit test 신규 작성 필요

5. [marslab/config/scenario_loader.md:165](marslab/config/scenario_loader.md) "deep_merge / spawn mode 3종 / bilinear 의 edge case 모두 커버 (확인 필요: 실제 테스트 수는..."
   - 배경: scenario_loader 테스트 커버리지 측정
   - 해결 단서: `tests/unit/test_scenario_loader.py` LoC 및 케이스 수 확인

6. [marslab/config/scenario_loader.md:184](marslab/config/scenario_loader.md) "`_format_missing_file_message` 의 8개 nearby 제한 근거가 주석에도 없음"
   - 배경: 8 하드코딩 상수 이유 불명
   - 해결 단서: git blame → PR 메시지에서 UX 근거 추출

7. [marslab/config/schema.md:156](marslab/config/schema.md) "`MarsEnvConfig.solar_constant_mean` 의 default 589 W/m² 는 Appelbaum & Flood..."
   - 배경: solar constant 출처 논문 재확인
   - 해결 단서: Appelbaum & Flood (1990) TM-102299 값과 비교

8. [scripts/phase1/run_stage2.md:195](scripts/phase1/run_stage2.md) "본 파일 전용 유닛 테스트 유무 확인 필요... 실제 τ 동적 변동 로직이 어디서 구현되는지 확인 필요"
   - 배경: P3 offline-first 정합성
   - 해결 단서: `tests/unit/test_run_stage2.py` 존재 여부 + `dynamic-atmosphere-update` skill 구현부

9. [scripts/phase1/run_stage2.md:198](scripts/phase1/run_stage2.md) "`tau_profile_name` 을 이름 문자열로 다루지만 실제 프로파일 함수 매핑... dict lookup 구현이 보이지 않으므로... 실제 τ 동적 변동 로직이 어디서 구현되는지 확인 필요."
   - 배경: τ 프로파일 switch 누락 가능성
   - 해결 단서: `marslab/environment/tau_profiles.py` 유무 grep

10. [scripts/phase1/run_stage3.md:181](scripts/phase1/run_stage3.md) "`--no-rover` 모드면 OmniGraph sensor graph 자체가 만들어지지 않아 `/clock` 도 publish 되지 않는다. SLAM/Nav2 노드를 띄우고 scene-only 로 외부 로봇을 붙이는 케이스에 대한 지원은 아직 없음."
   - 배경: 외부 로봇 bring-up 지원 부재
   - 해결 단서: scene-only clock publisher 별도 스크립트 신설

11. [scripts/phase1/run_stage3.md:153](scripts/phase1/run_stage3.md) "scenario_loader 내부에서 이를 처리하는지 확인 필요... scenario_loader 가 같은 계약을 지키는지 검증 필요."
   - 배경: propagate_seeds 호출 계약 확인
   - 해결 단서: `marslab/config/scenario_loader.py` 내 `propagate_seeds` grep

12. [scripts/phase1/run_stage3_monolithic.md:199](scripts/phase1/run_stage3_monolithic.md) "scenario_loader 가 내부에서 propagate_seeds 를 호출하는지 여부 확인 필요"
   - 배경: 이슈 #1 — propagate_seeds 누락
   - 해결 단서: #11 과 동일 소스 조사로 동시 해소

13. [scripts/phase1/run_stage1.md:190](scripts/phase1/run_stage1.md) "`clamp, clamp_twist, rpy_to_quat, resolve_joint_indices` 는 offline-testable 이지만... 전용 테스트가 있는지 확인 필요. 없으면 P3(offline-first testing) 미달."
   - 배경: offline-testable 함수 전용 테스트 누락
   - 해결 단서: `tests/unit/test_run_stage1*.py` 존재 여부

14. [scripts/run_integration_test.md:57](scripts/run_integration_test.md) "`simple_rover.urdf` 가 저장소 내에 실제 존재하는지 확인 필요... 테스트가 이 경로를 요구하는 것은 구 버전 잔재일 수 있음."
   - 배경: 구 버전 잔재 코드 가능성
   - 해결 단서: `find . -name 'simple_rover.urdf'` → 없으면 dead

15. [scripts/run_multi_robot_test.md:51](scripts/run_multi_robot_test.md) "`simple_rover.urdf`, `simple_rotorcraft.urdf` 존재 여부 확인 필요 — Rotorcraft 는 실제 MarsLab v1.0 스코프... 포함 여부도 불명"
   - 배경: scope 밖 스크립트 가능성
   - 해결 단서: #14 와 동시 확인 + CLAUDE.md v1.0 범위 대조

16. [scripts/analyze_dem_regions.md:66](scripts/analyze_dem_regions.md) "`concavity` 필드는 dict 에 저장되지만 `select_steep_candidates` 는 사용 안 함. dead field 또는 미래 확장?"
   - 배경: dead field 의심
   - 해결 단서: grep 으로 `concavity` 참조 전수 추적

17. [scripts/ros2/scan_header_fix.md:75](scripts/ros2/scan_header_fix.md) "파일/노드 이름이 `scan_header_fix` 이지만 `header.{frame_id,stamp}` 는 수정하지 않고 body 의 `angle_max` 만 수정... `scan_angle_fix` 또는 `scan_inclusive_end_fix` 로 개명하는 편이 의도에 부합. 과거 header 쪽 fix 가 초안에 있었을 가능성"
   - 배경: 이름-동작 불일치, 미완 마이그레이션 가능성
   - 해결 단서: git log 에서 header fix 초기 구현 유무 확인

18. [scripts/tools/generate_instruction_index.md:74](scripts/tools/generate_instruction_index.md) "`generate_instruction_skeleton.py` 파일이 없어 안내가 깨진 링크. (PLAN 의 Phase A-2 산출물이었을 가능성"
   - 배경: dead reference
   - 해결 단서: PLAN.md Phase A-2 체크리스트 대조

19. [scripts/phase1/run_stage3.md:162](scripts/phase1/run_stage3.md) "`configs/robots/rover_m2020.yaml` 에 `lidar_2d:` 섹션이 여전히 존재할 경우 `attach_rover_sensor_rig` 나 `build_sensor_graph` 가 무엇을 하는지 확인 필요"
   - 배경: 제거 누락된 lidar_2d 설정의 런타임 경로
   - 해결 단서: yaml 파일 확인 후 호출부 grep

### 2.2 외부 에셋 실재성

1. [marslab/robots/rover.md:339](marslab/robots/rover.md) "`m2020_physics.usd`, `m2020_robot.usd`, `m2020_sensor.usd` 는 컨버터 중간 산출로 보이나 쓰임 미확인"
   - 배경: 미사용 USD 산출물 판별
   - 해결 단서: `grep -r m2020_physics.usd` → 참조 0 이면 dead

2. [marslab/robots/README.md:153](marslab/robots/README.md) "`configs/robots/rover.yaml` — rover 파생 설정 (확인 필요)"
   - 배경: 파일 실존 여부
   - 해결 단서: `configs/robots/` 디렉터리 ls

3. [configs/scenarios/cerberus_canyon.md:16](configs/scenarios/cerberus_canyon.md) "crop 500×500 이 원본 DEM 범위 내여야 함"
   - 배경: DEM 범위 초과 시 crash
   - 해결 단서: 원본 DEM size 메타데이터 추출 후 비교

4. [configs/scenarios/cerberus_canyon.md:30](configs/scenarios/cerberus_canyon.md) "500×500 crop 은 Cerberus 원본 DEM 기준 row 8000~8500, col 2800~3300. easy 버전과 공간적으로 인접... 겹치는 영역 있음"
   - 배경: 데이터셋 분할 오염 가능성
   - 해결 단서: easy/hard scenario 쌍 dem_crop 블록 diff

5. [configs/scenarios/jezero_crater.md:18](configs/scenarios/jezero_crater.md) "확인 필요: jezero DEM 크기 vs crop 끝 index=500"
   - 배경: crop 범위 초과 가능성
   - 해결 단서: gdalinfo 로 DEM size 확인

6. [configs/terrain/procedural_hills.md:39](configs/terrain/procedural_hills.md) "Procedural hills 알고리즘 (확인 필요): `marslab/terrain/procedural_generator.py`"
   - 배경: 경로 실존 여부
   - 해결 단서: `ls marslab/terrain/procedural_generator.py`

7. [configs/terrain/jezero_crater.md:23](configs/terrain/jezero_crater.md) "`scripts/convert_dem.py` 가 유일 후보지만 실제 import 경로 확인 필요"
   - 배경: 미사용 YAML 가능성
   - 해결 단서: scripts/convert_dem.py 가 이 YAML 을 참조하는지 grep

8. [configs/sensors/stereo_rgb.md:50](configs/sensors/stereo_rgb.md) "`CameraInfo.P` 매핑: `marslab/ros2_bridge/camera_info_publisher.py` (확인 필요)"
   - 배경: 파일 실존 여부
   - 해결 단서: ros2_bridge 디렉터리 ls

9. [scripts/blender_generate_rocks.md:34](scripts/blender_generate_rocks.md) "호스트 시스템에 Blender ≥ 2.9x 필요 (정확한 버전 확인 필요)"
   - 배경: 명시적 버전 미기재
   - 해결 단서: blender_generate_rocks.py 내 `bpy` API 호출로 minimum 버전 추정

10. [scripts/blender_generate_rocks.md:37](scripts/blender_generate_rocks.md) "`marslab.terrain.rock_instancer` 등 하류 모듈이 `rock_blender_*.obj` 를 로드 (확인 필요)"
    - 배경: Blender 산출물 소비자 확인
    - 해결 단서: rock_instancer.py 내 `rock_blender` glob 패턴 grep

### 2.3 런타임 동작 미검증

1. [marslab/gui/atmosphere_panel.md:166](marslab/gui/atmosphere_panel.md) "omni.ui 콜백은 Kit app 틱에 동기적으로 디스패치됨 — 명시적 동기화 불필요 추정, 확인 필요"
   - 배경: GUI 콜백 스레딩 모델
   - 해결 단서: omni.ui 공식 문서 synchronization 섹션

2. [marslab/terrain/cave_generator.md:178](marslab/terrain/cave_generator.md) "반타원 winding (392-437): inward normal 설계... 충돌 계산 시 normal 방향 재확인 필요. Stage1.6 통합 테스트에서 로버가 벽을 관통하면 이 부분을 먼저 점검."
   - 배경: cave 충돌 체커 동작 미검증
   - 해결 단서: 사용자 Isaac Sim 실행 테스트

3. [marslab/terrain/rock_instancer.md:171](marslab/terrain/rock_instancer.md) "실제 AI4Mars annotation 파이프라인이 이 속성을 어떻게 집계하는지 확인 필요"
   - 배경: `semanticLabel` 집계 방식 미확인
   - 해결 단서: annotation 모듈 구현 후 재확인 (v1.0 scope 외)

4. [marslab/robots/rotorcraft.md:97](marslab/robots/rotorcraft.md) "`omni.kit.commands.execute('URDFParseAndImportFile', ...)` 사용... Isaac Lab 의 `UrdfConverter` 가 권장 경로... 동일 프로젝트의 `rover.py` 가 어떤 경로를 쓰는지에 따라 일관성 판단이 달라짐"
   - 배경: Isaac Lab API 정책 위반 여부
   - 해결 단서: rover.py 의 URDF 변환 API 확인

5. [marslab/robots/quadruped.md:186](marslab/robots/quadruped.md) "`isaacsim.storage.native.get_assets_root_path`: Isaac Sim 공식 문서 (버전별 경로 변경 이력 확인 필요)"
   - 배경: API 경로 안정성
   - 해결 단서: Isaac Sim 5.x 공식 API 문서 확인

6. [marslab/robots/quadruped.md:206](marslab/robots/quadruped.md) "`config.name` 필드를 `RobotConfig` 에 추가... 스키마 변경 범위 확인 필요"
   - 배경: 다중 quadruped 지원 리팩터 영향도
   - 해결 단서: RobotConfig 의존 호출처 전수 grep

7. [marslab/ros2_bridge/tf_broadcaster.md:74](marslab/ros2_bridge/tf_broadcaster.md) "180° X-roll 가정은 M2020 USD 기준... quadruped/rotorcraft 가 센서 rig 를 사용한다면 회전 보정 정책 분기 필요"
   - 배경: 다중 플랫폼 센서 rig 호환성
   - 해결 단서: quadruped/rotorcraft 센서 rig 부착 여부 확인

8. [marslab/ros2_bridge/sensor_graph.md:94](marslab/ros2_bridge/sensor_graph.md) "동일 `camera_prim_path` 를 두 번 바인딩하는 것이 해상도 불일치 시 어떻게 동작하는지 Isaac Sim 공식 문서 재확인 필요"
   - 배경: OmniGraph 바인딩 정책
   - 해결 단서: Isaac Sim 공식 `RenderProduct` 문서

9. [scripts/phase1/run_stage2.md:192](scripts/phase1/run_stage2.md) "`atmosphere_state` 는 thread-safe dict 가 아니다... 확인 필요: AtmospherePanel 내부 스레딩 모델"
   - 배경: GUI panel 스레딩 (#1 과 동일 주제)
   - 해결 단서: #1 과 함께 omni.ui 문서로 확인

10. [scripts/phase1/run_stage3.md:148](scripts/phase1/run_stage3.md) "`load_terrain_elevation` 을 `marslab.terrain.elevation_loader` 로 이전한 이후에도 지속되는지는 해당 모듈 위키에서 확인 필요"
    - 배경: `_cave_data` mutation 잔존 여부
    - 해결 단서: `wiki/marslab/terrain/elevation_loader.md` 생성 후 재확인

11. [scripts/phase1/run_stage3_monolithic.md:50](scripts/phase1/run_stage3_monolithic.md) "`resolve_spawn_pose` 의 좌표 가정이 SW-anchor 기준인지 centered 기준인지 스키마 확인 필요"
    - 배경: 좌표 기준 모호
    - 해결 단서: resolve_spawn_pose 함수 docstring/구현 확인

12. [scripts/convert_urdf.md:64](scripts/convert_urdf.md) "URDF 내부 mesh 경로(`package://`) 해석 여부 스크립트에서 제어 못함 — Isaac Sim 의 `ROS_PACKAGE_PATH` 환경변수 의존"
    - 배경: 환경변수 의존 실행 실패 가능성
    - 해결 단서: Isaac Sim 런타임에서 ROS_PACKAGE_PATH 효과 테스트

13. [scripts/run_sensor_test.md:90](scripts/run_sensor_test.md) "TEST 1 의 RGB shape 가 4 채널(RGBA) — alpha 가 의미 있는 값인지 확인 필요. 일부 Isaac Sim 카메라는 alpha=1 하드코딩."
    - 배경: alpha 채널 의미
    - 해결 단서: Isaac Sim Camera API spec 확인

14. [scripts/run_scene_test.md:78](scripts/run_scene_test.md) "`configure_atmosphere_fog(stage, 0.3)` 호출은 인자 2개만 넘김 — 실제 시그니처 확인 필요"
    - 배경: API 시그니처 불일치 가능성
    - 해결 단서: rendering 모듈 함수 정의 grep

15. [scripts/blender_generate_rocks.md:63](scripts/blender_generate_rocks.md) "`random.seed(seed)` 는 Python stdlib `random` 만 seed — Blender `bpy` 내부 텍스처 생성이 이 seed 를 따르는지 불확실"
    - 배경: 재현성 미검증
    - 해결 단서: 동일 seed 로 2회 실행 diff

16. [configs/scenarios/cave_lava_tube.md:21](configs/scenarios/cave_lava_tube.md) "`skylight_depth_m=90` vs `200×0.5=100` → 90 < 100 조건 실패하지 않나?... 확인 필요: 이 YAML 이 실제로 로드 가능한지"
    - 배경: 스키마 검증 충돌
    - 해결 단서: `python -c "from marslab.config.scenario_loader import load_scenario_config; load_scenario_config('configs/scenarios/cave_lava_tube.yaml')"` 실행

17. [configs/scenarios/cave_lava_tube.md:35](configs/scenarios/cave_lava_tube.md) "이 시나리오는 Scenario 5 완료 보고 (memory: 2026-04-16) 와 동시에 존재 → 실제로 어떻게 통과하는지 확인 필요"
    - 배경: #16 과 동일, 보완 설명
    - 해결 단서: #16 재현과 동시 확인

18. [configs/nav2/README.md:14](configs/nav2/README.md) "`launch/slam_toolbox.launch.py` (확인 필요 — slam_toolbox 가 nav2_params 를 읽는지)"
    - 배경: launch 파일 구조
    - 해결 단서: launch 파일 존재 및 param 바인딩 확인

19. [configs/nav2/nav2_params.md:37](configs/nav2/nav2_params.md) "Stage 3 의 TF broadcaster 가 `base_link → Body_Chassis` static 매핑을 공급하는지 확인 필요"
    - 배경: TF frame 변환 정책
    - 해결 단서: tf_broadcaster.py 에서 base_link→Body_Chassis static 브로드캐스트 grep

### 2.4 문서·코드 드리프트

1. [marslab/gui/atmosphere_panel.md:176](marslab/gui/atmosphere_panel.md) "line 149: `hours = t * 24.66`. 하드코딩된 24.66 h... `configs/mars_env.yaml` 의 `mars.sol_duration=88642s` (=24.62 h) 와 미세 불일치"
   - 배경: G5(YAML) 원칙 위반 의심
   - 해결 단서: sol_duration 을 atmosphere_panel 에서 읽도록 리팩터

2. [marslab/gui/atmosphere_panel.md:180](marslab/gui/atmosphere_panel.md) "`atmosphere_state` dict 스키마는... 암묵 합의. dataclass/TypedDict 로 승격하면 타입 안전성 향상"
   - 배경: 계약 비명문화
   - 해결 단서: atmosphere_state 전용 dataclass 도입

3. [marslab/gui/README.md:56](marslab/gui/README.md) "의도적 설계로 추정되나 확인 필요... `gui/` 는 re-export/초기화 책임을 의도적으로 생략"
   - 배경: 빈 `__init__.py` 의도성
   - 해결 단서: git history 확인

4. [marslab/gui/README.md:67](marslab/gui/README.md) "추가 패널이 들어올 여지를 시사한다. 후보 (모두 미구현, 확인 필요)"
   - 배경: 확장 계획의 구현 상태
   - 해결 단서: PLAN.md v1.0 GUI 섹션 대조

5. [marslab/ros2_bridge/topic_config.md:71](marslab/ros2_bridge/topic_config.md) "향후 2D LiDAR / multi-sensor 확장 시 이 모듈을 살리거나 완전 제거할지 결정... MEMORY 'Comment out, don't delete' 원칙에 따라 당장 제거는 금지"
   - 배경: dead-code 거취 결정
   - 해결 단서: 사용자 결정 필요

6. [_glossary.md:15](_glossary.md) "표기한다. 코드와 충돌하는 교과서 정의는 '확인 필요' 로 플래그한다."
   - 배경: 원칙 명시
   - 해결 단서: (메타)

7. [_glossary.md:382](_glossary.md) "## 확인 필요 항목 (wiki/CLAUDE.md 원칙)"
   - 배경: 섹션 헤더
   - 해결 단서: (메타)

8. [_glossary.md:388](_glossary.md) "있는지(혹은 `.claude/skills/slam-nav-benchmark/` 내부인지) 확인 필요"
   - 배경: ATE/RPE 구현 위치
   - 해결 단서: slam-nav-benchmark skill 내부 grep

9. [configs/sensors/lidar_3d.md:44](configs/sensors/lidar_3d.md) "`rover_m2020.yaml:74` 는 `profile: 'Example_Rotary'` 로 bundled 프로파일 참조 — 이 YAML 과 FOV/resolution 값이 다를 수 있다."
   - 배경: YAML vs Isaac Sim profile 드리프트
   - 해결 단서: Example_Rotary.json 과 lidar_3d.yaml 값 대조

10. [configs/sensors/depth_camera.md:44](configs/sensors/depth_camera.md) "`depth_link` TF frame 은 `camera_link` 와 별도 broadcast 필요. 현재 static TF 정의 위치 확인 필요"
    - 배경: TF 정의 위치 불명
    - 해결 단서: tf_broadcaster.py / URDF grep

11. [configs/scenarios/README.md:66](configs/scenarios/README.md) "spawn yaw 라디안 값이 float 상수... 몇 파일은 `3.14159` (5자리), 다른 곳은 더 정밀할 수 있음"
    - 배경: 상수 정밀도 일관성
    - 해결 단서: `grep -r "3.14159\|3.141592" configs/scenarios/`

12. [configs/phase1.md:20](configs/phase1.md) "`run_stage1.py:30 DEFAULT_CONFIG = ... phase1.yaml` 이 직접 `yaml.safe_load` 로 읽는다 (확인 필요: 로딩 경로)"
    - 배경: 로더 계약 우회
    - 해결 단서: run_stage1.py 내 yaml.safe_load grep

13. [configs/README.md:5](configs/README.md) "본문 내 '확인 필요'는 코드 검증 실패 지점."
    - 배경: 원칙 문장
    - 해결 단서: (메타)

14. [scripts/visualize_dynamic_atmosphere.md:13](scripts/visualize_dynamic_atmosphere.md) "Mars sol = 88642 s ÷ 3600 ≈ 24.623 시간 — 24.66 근사 (소수점 셋째자리에서 약 0.04h 편차"
    - 배경: #1 과 동일 드리프트
    - 해결 단서: sol_duration 중앙화

15. [scripts/visualize_dynamic_atmosphere.md:29](scripts/visualize_dynamic_atmosphere.md) "`dynamic-atmosphere-update` skill 이 이 스크립트를 산출물 기준으로 호출할 가능성 있음"
    - 배경: skill ↔ script 연결
    - 해결 단서: skill 정의 YAML grep

16. [scripts/check_instruction_sync.md:51](scripts/check_instruction_sync.md) "pre-commit hook 또는 CI 워크플로우에서 호출 가능(현재 `.github/workflows/` 연결 여부 확인 필요)"
    - 배경: CI 연결 상태
    - 해결 단서: `.github/workflows/*.yaml` grep

17. [scripts/check_instruction_sync.md:84](scripts/check_instruction_sync.md) "`wiki/` 디렉터리도 공존 중이라 두 가지 패턴이 혼재"
    - 배경: Instruction/ vs wiki/ 패턴 충돌
    - 해결 단서: 사용자 결정 필요

18. [scripts/visualize_scenario.md:63](scripts/visualize_scenario.md) "`_workspace/` 디렉터리 자동 생성 — `.gitignore` 확인 필요"
    - 배경: gitignore 커버
    - 해결 단서: `.gitignore` 에 `_workspace/` 추가 여부 확인

19. [scripts/visualize_scenario.md:71](scripts/visualize_scenario.md) "`measured_cfa = sum(π/4 × d²) / area_m2` 는 원 투영면적 기준. `compute_cfa` 의 정의와 일치하는지 확인 필요"
    - 배경: CFA 정의 일관성
    - 해결 단서: environment/rock_sfd.py 의 compute_cfa 공식 확인

20. [scripts/visualize_atmosphere.md:17](scripts/visualize_atmosphere.md) "`total = direct / (1 - diffuse_frac)` 로 total irradiance 분해 — 검증 필요 수식, COMIMART 원본에서 유래했는지 확인 필요"
    - 배경: 수식 출처
    - 해결 단서: Vicente-Retortillo et al. (2015) 원문 확인

21. [scripts/visualize_atmosphere.md:49](scripts/visualize_atmosphere.md) "Panel 4 의 `total = direct / (1 - diffuse_frac)` 정의... 해당 수식의 출처(논문) 주석 없음"
    - 배경: #20 과 동일
    - 해결 단서: #20 과 동시 해소

22. [scripts/run_ros2_test.md:77](scripts/run_ros2_test.md) "run_ros2_test.py 가 깨진 상태로 방치됨. 의도적 방치 vs 미완 마이그레이션 확인 필요"
    - 배경: 깨진 스크립트 처리 (정책 근거 무효 — `feedback_no_delete_comment` 2026-04-23 retired)
    - 해결 단서: 사용자 결정 필요

23. [scripts/phase1/run_stage3_monolithic.md:212](scripts/phase1/run_stage3_monolithic.md) "`configs/robots/rover_m2020.yaml` — `lidar_2d:` 섹션 잔존"
    - 배경: #19 (2.1) 과 동일 주제
    - 해결 단서: yaml 내 lidar_2d 섹션 삭제/주석 처리 결정

24. [tests/unit/test_materials.md:10](tests/unit/test_materials.md) "`(2.5, 1.8, 1.2)` 는 테스트 내 하드코딩 — 실제 material_applicator 의 공식과 동기 여부 확인 필요"
    - 배경: 테스트 ↔ 구현 동기
    - 해결 단서: material_applicator.py 색 유도 공식 grep

25. [tests/unit/test_sol_sun_position.md:15](tests/unit/test_sol_sun_position.md) "test 들은 `compute_sol_sun_position` 이 elevation 을 `max_el * sin(π*t)` 로 구현한다고 가정. 실제 공식 확인 필요"
    - 배경: 테스트 가정 vs 구현 공식
    - 해결 단서: sun_position.py `compute_sol_sun_position` 수식 확인

26. [tests/unit/README.md:73](tests/unit/README.md) "색 유도 공식이 테스트 내에 하드코딩, `material_applicator.py` 와 sync 확인 필요"
    - 배경: #24 와 동일
    - 해결 단서: #24 와 동시 해소

27. [README.md:249](README.md) "`marslab/utils/` ❌ 삭제됨... `seed.py` → `config/loader.propagate_seeds` 로 이전. 과거 호출자 grep 확인 필요"
    - 배경: 이전 경로 잔존 참조
    - 해결 단서: `grep -r "from marslab.utils" .` → **0 건 (R1 완전 삭제, 2026-04-22)**.
      seed 재현성 단일 구현 = `marslab/config/loader.py:36-50 propagate_seeds()`.

### 2.5 기타 (메타/원칙 언급)

1. [_risks.md:227](_risks.md) "### 6.3 `marslab/ros2_bridge/sensor_graph.py` 일부 — 흔적 가능성 (확인 필요)"
   - 배경: 리스크 문서 섹션 제목
   - 해결 단서: (메타)

2. [_risks.md:229](_risks.md) "확인 필요 (wiki/CLAUDE.md 원칙에 따라 추측하지 않고 flag 만 남김)"
   - 배경: 원칙 인용
   - 해결 단서: (메타)

3. [_risks.md:231](_risks.md) "소비자 쪽 확인 필요."
   - 배경: sensor_graph 소비자 미확인
   - 해결 단서: sensor_graph 의 output 소비자 grep

4. [_risks.md:309](_risks.md) "추측(wiki/CLAUDE.md 원칙) 은 §'확인 필요' 서브불릿으로만 남긴다."
   - 배경: 원칙 문장
   - 해결 단서: (메타)

5. [PLAN.md:389](PLAN.md) "추측 금지, 불명확하면 '확인 필요' 섹션에 기록."
   - 배경: 원칙 문장
   - 해결 단서: (메타)

6. [PLAN.md:419](PLAN.md) "한국어 작성, 추측 표현 없음, 확인 필요 항목은 명시"
   - 배경: 체크리스트 항목
   - 해결 단서: (메타)

7. [PLAN.md:423](PLAN.md) "## 부록 C. 확인 필요 / 향후 과제"
   - 배경: 섹션 헤더
   - 해결 단서: (메타)

8. [CLAUDE.md:6](CLAUDE.md) "코드를 추측하지 않는다. 모르면 '확인 필요' 섹션에 적는다."
   - 배경: wiki 원칙 명문
   - 해결 단서: (메타)

9. [scripts/README.md:119](scripts/README.md) "`simple_rover.urdf` 가 저장소 어디에 있는지 확인 필요"
   - 배경: #14/#15 (2.1) 과 동일 주제
   - 해결 단서: 동시 해소

10. [scripts/README.md:139](scripts/README.md) "`visualize_atmosphere.py:58-65` 의 sky color swatch 는 `compute_sky_dome_params()` 호출에 HDRI 디렉터리를 요구... 해당 디렉터리 부재 시 동작이 달라질 수 있음"
    - 배경: HDRI 디렉터리 의존
    - 해결 단서: compute_sky_dome_params 의 fallback 분기 확인

11. [scripts/run_multi_robot_test.md:52](scripts/run_multi_robot_test.md) "Rotorcraft 물리: CLAUDE 'Do NOT implement Mars aerodynamics for rotorcraft in Phase 1' — `atmo_density` 를 전달하지만 kinematic 모델 한정 (확인 필요)"
    - 배경: CLAUDE.md 원칙 준수 여부
    - 해결 단서: run_multi_robot_test.py 에서 atmo_density 사용처 grep

12. [scripts/visualize_atmosphere.md:47](scripts/visualize_atmosphere.md) "HDRI 디렉터리 무관 — sky_dome 은 파일 없어도 상수로 RGB 반환하는 것으로 보이나 확인 필요"
    - 배경: #10 과 동일 주제
    - 해결 단서: 동시 해소

13. [scripts/blender_generate_rocks.md:62](scripts/blender_generate_rocks.md) "line 103~106 의 `os.remove(...)` 가 기존 trimesh 산출물을 무조건 제거. 사용자는 양쪽 버전 비교를 못 함"
    - 배경: trimesh 산출물 비교 불가
    - 해결 단서: 사용자 결정 필요 (`feedback_no_delete_comment` 정책은 2026-04-23 retired; 근거 재수립 필요)

14. [_risks.md:308 (raw line 309)](_risks.md) 중복: §4 에서 이미 포함

## 3. 파일별 역 인덱스 (상위 10개)

| md | 건수 | question 번호 |
|----|------|--------------|
| [scripts/phase1/run_stage3.md](scripts/phase1/run_stage3.md) | 4 | 2.1-#10, 2.1-#11, 2.1-#19, 2.3-#10 |
| [scripts/blender_generate_rocks.md](scripts/blender_generate_rocks.md) | 4 | 2.2-#9, 2.2-#10, 2.3-#15, 2.5-#13 |
| [_risks.md](_risks.md) | 4 | 2.5-#1, 2.5-#2, 2.5-#3, 2.5-#4 |
| [scripts/visualize_atmosphere.md](scripts/visualize_atmosphere.md) | 3 | 2.4-#20, 2.4-#21, 2.5-#12 |
| [scripts/phase1/run_stage3_monolithic.md](scripts/phase1/run_stage3_monolithic.md) | 3 | 2.3-#11, 2.1-#12, 2.4-#23 |
| [scripts/phase1/run_stage2.md](scripts/phase1/run_stage2.md) | 3 | 2.3-#9, 2.1-#8, 2.1-#9 |
| [PLAN.md](PLAN.md) | 3 | 2.5-#5, 2.5-#6, 2.5-#7 |
| [marslab/gui/atmosphere_panel.md](marslab/gui/atmosphere_panel.md) | 3 | 2.3-#1, 2.4-#1, 2.4-#2 |
| [_glossary.md](_glossary.md) | 3 | 2.4-#6, 2.4-#7, 2.4-#8 |
| [scripts/visualize_scenario.md](scripts/visualize_scenario.md) | 2 | 2.4-#18, 2.4-#19 |

## 4. 해소 권고

### 4.1 즉시 해소 가능 (단순 확인으로 끝나는 경우) — 20 건 추정

grep/ls/git 한 방으로 검증 가능한 항목:

- 2.1-#14, 2.1-#15, 2.5-#9 (`simple_rover.urdf`, `simple_rotorcraft.urdf` 실존) — `find . -name 'simple_rover.urdf'`
- 2.2-#1 (`m2020_physics.usd` 등 중간 산출 참조) — `grep -r m2020_physics.usd`
- 2.2-#2 (`configs/robots/rover.yaml`) — `ls configs/robots/`
- 2.2-#6 (`marslab/terrain/procedural_generator.py`) — ls
- 2.2-#7 (`configs/terrain/jezero_crater.yaml` 참조) — grep
- 2.2-#8 (`camera_info_publisher.py`) — ls
- 2.1-#11, 2.1-#12 (scenario_loader 의 propagate_seeds) — grep 동시 해소
- 2.4-#11 (spawn yaw π 정밀도) — `grep -r 3.14159 configs/scenarios/`
- 2.4-#12 (run_stage1 의 yaml.safe_load) — grep
- 2.4-#16 (CI 워크플로우) — `.github/workflows/` ls
- 2.4-#18 (`.gitignore` 의 `_workspace/`) — cat
- 2.4-#23 (`rover_m2020.yaml` 의 lidar_2d 섹션) — grep
- 2.4-#24, 2.4-#26 (색 유도 공식 sync) — grep material_applicator
- 2.4-#25 (elevation 공식) — sun_position 함수 본문
- 2.4-#27 (`marslab/utils/` 잔존 import) — `grep -r 'from marslab.utils'` → **0 건 (R1 완전 삭제, 2026-04-22)**.
- 2.1-#13 (run_stage1 전용 unit test) — `ls tests/unit/ | grep stage1`
- 2.3-#14 (`configure_atmosphere_fog` 시그니처) — grep rendering
- 2.1-#16 (`concavity` 참조) — grep
- 2.1-#18 (`generate_instruction_skeleton.py`) — ls (확실히 없음)
- 2.1-#1 ~ #7 일부 (tests 커버리지) — grep

### 4.2 외부 실험 필요 (Isaac Sim / Blender 실행) — 10 건 추정

- 2.3-#2 (cave 충돌 관통 여부) — Stage1.6 통합 테스트 실행
- 2.3-#3 (AI4Mars annotation 집계) — annotation 파이프라인 완성 후 재확인 (v1.0 scope 외)
- 2.3-#4 (URDFParseAndImportFile vs UrdfConverter 동작 차이) — Isaac Sim 실행
- 2.3-#5 (get_assets_root_path 버전별) — Isaac Sim 공식 문서 + 런타임 확인
- 2.3-#8 (RenderProduct 중복 바인딩) — Isaac Sim 문서 + 실행
- 2.3-#12 (ROS_PACKAGE_PATH URDF mesh 해석) — 런타임 테스트
- 2.3-#13 (RGBA alpha 의미) — Isaac Sim Camera API 문서
- 2.3-#15 (blender seed 재현성) — 2회 실행 diff
- 2.3-#16, #17 (cave_lava_tube 스키마 로드) — `python` 으로 load_scenario_config 호출
- 2.3-#19 (base_link → Body_Chassis TF) — Stage 3 실행 후 `ros2 run tf2_tools view_frames`

### 4.3 사용자 결정 필요 — 6 건 추정

- 2.4-#5 (`topic_config` 모듈 거취: 살릴지 제거할지)
- 2.4-#17 (Instruction/ vs wiki/ 공존 정책)
- 2.4-#22 (깨진 `run_ros2_test` 스크립트 처리 방향)
- 2.5-#13 (blender `os.remove` 정책 적용)
- 2.1-#10 (scene-only `/clock` publisher 신설 여부)
- 2.3-#7 (TF 180° X-roll 다중 플랫폼 정책 분기)

## 5. 추적 규약

- 새로운 "확인 필요" 추가 시 본 문서에 번호 매겨 동기화 (T4 재실행으로 갱신).
- 해소된 건은 해당 카테고리 내 번호 옆에 `RESOLVED (YYYY-MM-DD, 해소 경로)` 태그만 추가 (항목 삭제 금지).
- 재실행 명령: `grep -rn "확인 필요" ~/MarsLab/wiki/` → 본 문서 §1 total_count, §2 카테고리, §3 역 인덱스 갱신.
- T4 재실행 트리거: wiki md 대량 편집 직후 / 2주마다 / PLAN.md 주차 전환 시점.
