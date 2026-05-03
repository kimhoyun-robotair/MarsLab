# m2020 URDF 좌표계 변환 + Jackal 도입 가능성 — 요약

> 본 문서는 **가능성 조사 결과 요약**이다. 코드 수정 계획서가 아니다.
> 상세 보고서: `~/.claude/plans/1-m2020-urdf-models-piped-falcon.md`

---

## Q1. m2020 URDF FRD→ROS 표준 변환 가능성

### 핵심 결론
- 좌표계 추정 **정확** (+X forward, +Y left, **+Z down** — ROS REP-103과 Z축만 불일치)
- **이미 80% 완료된 변환 sandbox 존재**: `tmp/v1_release_blocker_fixes/rc1b_urdf_rep103/`
- mesh 깨질 가능성 **LOW**, 새 mesh 제작 **불필요**
- TF 근본 이슈 제거 **YES** (단, 4 영역 동시 변환 필수)

### 좌표계 증거 (`tmp/diag_a_urdf.md`, `m2020.urdf:1108-1206`)
| 축 | m2020 | ROS REP-103 | 판정 |
|---|-------|------|------|
| X | forward | forward | 일치 |
| Y | left (or right, frame inversion) | left | **단일 180° X축 회전으로 해결** |
| Z | **DOWN** | up | **불일치** |

### 변환 sandbox 인벤토리
| 파일 | 상태 |
|------|------|
| `rewrite_urdf_xml.py` (URDF 변환) | 완료, 순수 stdlib |
| `rotate_meshes_to_rep103.py` (73 glTF 회전) | 완료, smoke (5/73) 통과 |
| `test_rewrite_urdf.py` (13 pytest, scipy 비교) | 완료 |
| `m2020_rep103.urdf` | 생성됨 |
| `INTEGRATION.md` (6 단계 통합 가이드) | 완료 |

### Mesh 영향 (`INTEGRATION.md:85-122`)
- trimesh 알려진 quality 이슈 2건:
  1. Buffer fragmentation: `CHASSIS.bin` 4.44MB → 5.29MB (~19% bloat), vertex bit-exact
  2. Material `samplers` 메타데이터 드롭 (texture는 buffer 인라인)
- Isaac Sim USD bake 검증 필요. 실패 시 **Blender bpy fallback** 명시됨
- NASA-JPL 원본 mesh 그대로 사용 (회전만), 새 mesh 모델링 불필요

### TF 근본 이슈 제거 (`work_log/tf_chain_diagnosis_2026-04-26/00_consolidated.md`)
| 현재 이슈 | URDF 변환 후 |
|-----------|------------|
| cmd_vel CW → /tf CCW (yaw 부호 반전) | **자동 해결** |
| LiDAR 스캔 world position 드리프트 | **자동 해결** |
| RViz mesh 거꾸로 표시 | **자동 해결** |
| `/robot_description` 안 보임 | 별개 이슈 (publisher hard-deleted) |

### 변환 시 손봐야 할 코드 surface (`INTEGRATION.md:65-77`)
| 사이트 | 작업 |
|--------|------|
| `marslab/ros2_bridge/tf_broadcaster.py:50-52` | Y/Z negate 제거 |
| `tests/unit/test_tf_broadcaster.py:92-101` | assertion 부호 반전 |
| `tests/unit/test_ros2_bridge_structure.py:129-141` | 동일 |
| `tests/unit/test_m2020_sensor_presets.py` | sensor mount Z 부호 flip |
| `configs/robots/rover_m2020.yaml:spawn_orientation_rpy` | `[π,0,0]` → `[0,0,0]` |
| 11개 scenario YAML | spawn rpy 오버라이드 모두 identity |

### 평가
| 축 | 결과 |
|---|------|
| 가능성 | **EASY (80% 완료)** |
| 위험 | URDF만 바꾸고 bridge 미수정 시 **현재 우회 깨짐** → 한 번에 끝내거나 안 하거나 |
| 권장 시점 | **v1.5** (post-iSpaRo). v1.0 freeze 후 무리한 변환은 회귀 위험 |

---

## Q2. Isaac Sim 내장 로버 (Jackal 등) 도입 가능성

### 핵심 결론
- 기술적 가능하나 **코드 통합 surface 큼 (~325 LOC)**
- Mars 충실도 **저하** (Jackal은 Earth UGV)
- **더 빠른 대안 발견**: `max_linear_velocity: 4.0`은 URDF 물리 limit이 아닌 **YAML 안전 캡**

### Isaac Sim 5.1 내장 mobile robot
Jackal (4-wheel skid-steer), Dingo, Nova Carter, Carter v1, Create 3, Limo,
Leatherback. **MarsLab 코드는 `omniverse://` 참조 0건** → Nucleus URL resolver
인프라 작업 선행 필요.

### m2020-specific hardcoding (Jackal 도입 장애물)
| 컴포넌트 | m2020 가정 | Jackal 호환성 |
|----------|------------|--------------|
| `rover.py:633` | `Body_Chassis` link 이름 hard-code | runtime fail |
| `rover_m2020.yaml:270-276` | 6-wheel rocker-bogie joint names | dead code (Jackal 무 suspension) |
| `rover_control.py:31-144` | 6-wheel Ackermann IK | 전체 미사용 (skid-steer) |
| `rover_m2020.yaml:146` | sensor parent `Body_Chassis` | frame 매핑 필요 |
| `rover_m2020.yaml:157` | odom→base_link (m2020 X-roll 가정) | frame chain 재설계 |

### Mars 환경 충실도 저하
| 파라미터 | m2020 (Mars) | Jackal (Earth) |
|----------|-------------|---------------|
| Wheel friction | 0.6 (Sullivan 2017, Mars regolith) | 0.7-0.9 (rubber 추정) |
| Mass | 1025 kg | ~18 kg |
| Wheel material | aluminum + spokes | rubber tire |

→ "빠르게 보이지만 Mars 비현실 traction"

### 더 빠른 대안: m2020 속도 캡 풀기
**핵심 발견 (`configs/robots/rover_m2020.yaml:255`):**
```yaml
max_linear_velocity: 4.0   # ← 사용자가 느낀 "느림"의 원인
```
이는 **URDF의 물리 limit이 아닌** scenario-level safety cap. m2020 URDF의
`<limit velocity>`는 `1.79769e+308` (unbounded, `m2020.urdf:1106`).

**한 줄 변경으로 즉시 풀림** — 단:
- 4.0 m/s 결정 history (git blame, work_log) 확인 권장
- Mars + friction 0.6에서 wheel slip 가능성 → integration test 필요
- Rocker-bogie 고속 stability 검증 필요

### 비교
| 축 | [A] Jackal | [B] m2020 캡 풀기 |
|---|------------|-------------------|
| LOC | ~325 | **1줄** |
| 시간 | 3-5일 + friction study | <1시간 + integration test |
| Mars 충실도 | **저하** | 유지 |
| 회귀 위험 | 중 | 저 |
| iSpaRo deadline 위협 | 위협 | 안전 |

---

## 권장 의사결정

| 옵션 | 권장 시점 | 이유 |
|------|----------|------|
| Q1 변환 진행 | **v1.5 (post-paper)** | 80% 완료. iSpaRo 데이터는 현재 우회 코드로 functionally correct |
| Q2 옵션 A (Jackal) | **v1.5 multi-robot 작업과 병합** | Mars 충실도 저하 + 작업량 과대 |
| Q2 옵션 B (속도 캡) | **선검증 후 가능** | 4.0 결정 history 확인 → 8.0+로 올리고 integration test |

### 사용자 다음 액션 옵션
1. Q1 진행 → rc1b sandbox full batch 실행 + Isaac Sim 검증 → 별도 plan 생성
2. Q1 보류 + Q2 옵션 B 진행 → 4.0 m/s history 확인 plan
3. Q1·Q2 모두 보류 → v1.0 freeze 우선

본 보고서는 가능성 조사이며 어느 옵션도 본 단계에서 수행하지 않는다.
