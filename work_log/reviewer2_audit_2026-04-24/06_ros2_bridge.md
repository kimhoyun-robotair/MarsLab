# Reviewer 2 audit -- `marslab/ros2_bridge/`

메타

- 감사자: Reviewer 2 (hostile external peer reviewer)
- 일자: 2026-04-24
- 스코프: `marslab/ros2_bridge/` 8 파일
  - `__init__.py` (54 LoC)
  - `cmd_vel_subscriber.py` (57 LoC)
  - `context.py` (40 LoC)
  - `odometry_publisher.py` (147 LoC)
  - `rclpy_integration.py` (109 LoC)
  - `sensor_graph.py` (150 LoC)
  - `sensor_graph_builder.py` (140 LoC)
  - `tf_broadcaster.py` (83 LoC)
- 명시적 제외: `odometry_math.py` (별도 감사자)
- 교차 비교 대상: `scripts/phase1/run_stage3_monolithic.py`, `scripts/phase1/run_stage4.py`, `marslab/runtime/main_loop.py`, `marslab/config/schema/ros2_bridge.py`
- 감사 대상 외 파일 (열람 금지 규칙) 준수 완료: `CLAUDE.md`, `PLAN.md`, `.claude/`, `work_log/` (이 보고서 디렉토리 외) 미열람
- 감사 방법: 정적 독서 + grep cross-reference. 하네스 내부 용어가 commment/docstring에 등장하는 경우 ("R4-5 extension", "G5", "Oracle"), 제품 코드 품질 관점에서는 "comments-as-deodorant" 신호로 간주함 (주석이 리팩토링 흔적을 정리하지 못한 채 축적되고 있다).

---

## Findings

### CRITICAL

#### C1. QoS 프로파일 전무 — sensor_data / SystemDefault / Reliable 구분이 **없음**
- 파일/라인: `marslab/ros2_bridge/cmd_vel_subscriber.py:57`, `marslab/ros2_bridge/odometry_publisher.py:85`
- 인용:
  ```python
  # cmd_vel_subscriber.py:57
  return node.create_subscription(Twist, topic, _cb, queue_size)
  ```
  ```python
  # odometry_publisher.py:85
  publisher = node.create_publisher(Odometry, topic, queue_size)
  ```
- 문제: 전체 모듈에서 `rclpy.qos.QoSProfile`, `ReliabilityPolicy`, `DurabilityPolicy`, `HistoryPolicy` 가 **한 번도 import되지 않는다** (repo-wide grep 결과 `QoSProfile` / `qos_profile` 매치 0건). 전체 topic이 rclpy default profile (KEEP_LAST depth=10, **RELIABLE**, VOLATILE) 로 broadcast 된다. 결과:
  - `/cmd_vel` 은 외부 teleop (Nav2 `controller_server` default = RELIABLE) 과는 일치하지만, `teleop_twist_keyboard` default (BEST_EFFORT) 와는 불일치 → publisher-side가 RELIABLE-only 이면 최신 teleop 입력이 조용히 drop. Stage-3 첫 정량 실험이 재현 불가능해진다.
  - `/odom` 은 하이레이트 스트리밍임에도 RELIABLE 로 publish 되어 slam_toolbox / Nav2 side가 BEST_EFFORT 로 구독하면 0 msg 수신으로 말없이 끝남. REP-2003 (`nav_msgs/Odometry` -> SystemDefault = RELIABLE) 는 맞지만 실무 컨벤션은 sensor_data. **명시적 계약이 없으므로 하부 스택이 바뀌면 즉시 "왜 TF tree가 안 자라요?" 버그 발생**.
  - `/imu`, `/camera/*`, `/lidar/*` 는 OmniGraph 측 Isaac Sim ROS2 bridge가 만들지만 여기도 YAML에는 QoS 필드 없음 (sensor_graph_builder.py `_build_set_values` 의 SET_VALUES 리스트에 `qosProfile` key 없음).
- 수정:
  1. `marslab/config/schema/ros2_bridge.py` 에 `cmd_vel_qos`, `odom_qos`, `sensor_qos` pydantic 필드 도입 (`Literal["sensor_data","system_default","reliable","best_effort"]`).
  2. `create_cmd_vel_subscriber` / `create_odometry_publisher` 의 `queue_size: int` 시그니처를 `qos: QoSProfile | int` 로 확장하고, `from rclpy.qos import qos_profile_sensor_data, qos_profile_system_default` 을 lazy import.
  3. slam_toolbox / Nav2 스택과의 계약을 README 또는 schema field description에 문서화 (`/odom` = RELIABLE + KEEP_LAST 100, `/cmd_vel` = RELIABLE + KEEP_LAST 10, `/imu` = sensor_data).
  - 이게 없으면 "v1.0 SLAM/Nav2 integration" 은 environment-sensitive 한 회색지대 그대로 iSpaRo paper 에 들어간다. **최우선 차단.**

#### C2. TF 이중 broadcasting — `/tf` (rclpy) vs `/tf_raw` (OmniGraph) 의 frame namespace가 **겹친다**
- 파일/라인: `marslab/ros2_bridge/odometry_publisher.py:131-137`, `marslab/ros2_bridge/sensor_graph_builder.py:104`, `marslab/ros2_bridge/tf_broadcaster.py:80-83`
- 인용:
  ```python
  # sensor_graph_builder.py:104
  ("PubTF.inputs:topicName", "/tf_raw"),
  ```
  ```python
  # odometry_publisher.py:137
  ctx.tf_broadcaster.sendTransform(tf_msg)   # → /tf
  ```
- 문제: OmniGraph `ROS2PublishRawTransformTree` (`PubTF`) 는 articulation joint 체인 전체를 `/tf_raw` 로 publish 하고, rclpy 쪽은 `odom -> base_link` 하나만 `/tf` 로 publish 한다. **그런데 articulation joint chain의 루트 또한 `base_link` 이다** (tf_broadcaster.py 에서 parent_frame_id 기본값이 `base_link`). slam_toolbox / Nav2 는 기본적으로 `/tf` 만 구독하므로:
  - `/tf` 에는 `odom -> base_link` 만 존재.
  - sensor frame (`camera_link`, `lidar_link`, `imu_link`, `scan_frame`) 은 rclpy static broadcaster 로 `/tf_static` 에 발행 → OK.
  - **그러나 articulation joint (rocker/bogie/wheels) 는 `/tf_raw` 에만 존재** → Nav2 costmap 이 `base_link -> wheel_link` 를 필요로 하지 않는다면 문제 없으나, RViz 에서 로버 joint 애니메이션이 `/tf` tree에 안 뜨고, 누군가 `tf2_ros.Buffer()` 기본 설정으로 `base_link -> left_bogie` 를 query 하면 조용히 실패한다.
  - 더 심각한 문제: docstring (`sensor_graph_builder.py:95-97`) 는 "`/tf_raw` 는 `/tf` 와 collision 하지 않도록 분리" 라고 주장하지만, 실제로는 `/tf_raw -> /tf` bridge 가 **어디에도 없다**. 즉 joint TF 가 Nav2 에서 영원히 안 보인다 (REP-105 violation).
- 수정:
  - 옵션 A: OmniGraph `PubTF` 의 `topicName` 을 `/tf` 로 되돌리고 (collision 없음 — TF2 design 상 여러 source가 같은 topic에 송신 가능), rclpy 의 `odom -> base_link` 와 merge.
  - 옵션 B: `tf2_ros/static_transform_publisher` 또는 `topic_tools/relay /tf_raw /tf` 런치 파일을 v1.0 bringup 에 포함하고 docstring에 명시.
  - 현 상태는 "문제 회피를 위해 따로 분리" 라고 주장하지만 근거가 부재하고 (`per user directive` 라는 코멘트 제외), 실측 효과는 Nav2 tf fail. CRITICAL.

#### C3. `rclpy_integration.py:48` — `rclpy.ok()` 는 `rclpy.init()` 필요 여부를 판단할 수 없다
- 파일/라인: `marslab/ros2_bridge/rclpy_integration.py:48-49`
- 인용:
  ```python
  if not rclpy.ok():
      rclpy.init(args=None)
  ```
- 문제: `rclpy.ok()` 는 **init 이후에** default context 가 살아있는지를 반환한다 (init 전에는 기본 context가 not-ok). 따라서 "init 안 됐다면 init 한다" 는 의도는 가짜 truthy처럼 동작하지만, 두 가지 케이스에서 바로 깨진다:
  - 동일 프로세스에서 한 번 shutdown 후 재init: `rclpy.ok() == False` → `rclpy.init()` 재호출 시 이미 일부 전역 상태가 남아 있어 `RuntimeError("rclpy.init() has already been called")` 혹은 executor zombie 가 발생할 수 있다.
  - 이미 외부 스크립트가 init 한 상태: `rclpy.ok() == True` → init 건너뜀 (정상).
  - test harness 에서 double init 방어: `rclpy.init()` 은 `already initialized` 에서 예외를 던진다. 현재 코드는 단순히 `if not ok()` 로 분기하지만, **초기 호출 시 `ok()` 가 False 인 것과 shutdown 이후 False 는 의미가 다르다**. 안전한 패턴은 `rclpy.utilities.ok()` 보다 `try/except RuntimeError` 또는 `rclpy.Context` 명시적 관리.
- 수정:
  ```python
  try:
      rclpy.init(args=None)
  except RuntimeError:
      pass  # 이미 initialized
  ```
  또는 자체 `Context` 를 생성해 `rclpy.init(context=ctx)` / `create_node(context=ctx)` 로 lifecycle 를 고립. 현 구조는 pytest fixture 가 조용히 node 누수 발생 시 두 번째 테스트에서 폭발한다 (이미 `test_ros2_bridge_lazy_import.py` 류가 부분 우회 중).

---

### HIGH

#### H1. 노드/퍼블리셔 shutdown path 가 모듈 내부에 **없다** — 리소스 누수 고스란히 호출자에게 책임 전가
- 파일/라인: `marslab/ros2_bridge/rclpy_integration.py:100-106` (BridgeContext 반환), `marslab/ros2_bridge/context.py:18-37`
- 인용:
  ```python
  return BridgeContext(
      node=node,
      cmd_vel_subscription=cmd_vel_sub,
      static_tf_broadcaster=static_broadcaster,
      odom_ctx=odom_ctx,
      twist_state=twist_state,
  )
  ```
- 문제: `init_rclpy_side` 는 `rclpy.init()` 을 호출하고 노드/퍼블리셔/브로드캐스터를 생성하지만, **대응되는 `shutdown_rclpy_side(ctx)` 가 없다**. 현재 destroy/shutdown 은 오직:
  - `scripts/phase1/run_stage3_monolithic.py:1471-1479` — `node.destroy_node()` + `rclpy.shutdown()`, 각자 bare `except Exception`.
  - `scripts/phase1/run_stage4.py` — 동일 shutdown 패턴 없음 (grep 결과 `destroy_node` 한 번 등장 안 함, `rclpy.shutdown` 도 부재).
  즉 Stage-4 런타임은 **노드를 절대 destroy 하지 않고 프로세스를 죽인다**. Isaac Sim 5.x 의 "shutdown heap corruption" 회피를 빌미로 모든 리소스 정리 책임이 암묵적으로 OS 에 넘어간 상태. BridgeContext 에 `__enter__` / `__exit__` 도 없고 `close()` 메서드도 없으므로 사용자는 어떻게 정리해야 하는지 시그니처 상 알 수 없다.
- 수정:
  - `BridgeContext` 에 `close()` 메서드 추가 (`node.destroy_node()` → `rclpy.shutdown()` try/except 로 감싸서), 또는
  - `init_rclpy_side` 대신 context manager (`@contextmanager init_rclpy_side`) 로 리팩토링하여 `with` 블록 종료 시 자동 정리.
  - 최소한 docstring 에 "caller must destroy node and call rclpy.shutdown()" 을 명시 (현재 전혀 언급 없음 → H1 이 그대로 CRITICAL 로 승격될 여지).

#### H2. `odom_publisher` 를 `publish_odometry` 대신 `main_loop._publish_odometry` 가 **복제** — dead public API
- 파일/라인: `marslab/ros2_bridge/odometry_publisher.py:98-147`, `marslab/runtime/main_loop.py:420-492`
- 인용: `odometry_publisher.publish_odometry` 본문 (quaternion math, tf+odom publish) 가 `main_loop._publish_odometry` 에 거의 완전히 재구현되어 있다. Cross-reference:
  - `publish_odometry` 의 실제 호출처: **없음** (repo-wide grep 결과 `marslab/`, `scripts/` 내 호출 0건. 오직 `tests/unit/test_odometry_publisher.py` 가 호출).
  - `main_loop._publish_odometry` 는 `OdomPublisherContext` 가 아닌 `OdomPublishState` (별도 dataclass in main_loop.py) 을 받는다. `frame_id / child_frame_id` 는 **하드코딩** (`main_loop.py:439,440`) 으로 `"odom"` / `"base_link"` 이므로 `OdometryPublisherContext.frame_id` / `child_frame_id` 필드가 production 에서 무시된다.
- 문제: Reviewer 2 관점에서 이것은 전형적인 Shotgun Surgery + Parallel Hierarchy 스멜.
  - `rclpy_integration` 은 `ros2_cfg["odom_publisher"]["frame_id"]` 를 YAML 에서 읽어 `OdometryPublisherContext.frame_id` 로 흘려보내지만, 실제 publish 시점에는 `main_loop.py` 가 `"odom"` 리터럴을 쓴다 → YAML 에서 `frame_id: "odom_m2020"` 같이 오버라이드해도 조용히 무시된다 (lying schema).
  - `publish_odometry(ctx, ...)` 는 public `__all__` 로 export 되지만 call site 0 → dead code.
  - 동일 로직 2곳 존재 → 버그 수정 시 한 쪽만 고치면 오라클 대비 회귀.
- 수정:
  - `main_loop._publish_odometry` 를 제거하고 `marslab.ros2_bridge.odometry_publisher.publish_odometry(ctx.odom_ctx, ...)` 를 호출하도록 통합.
  - `OdomPublishState` 와 `OdometryPublisherContext` 중복을 하나로 병합.
  - 또는 `publish_odometry` 와 `OdometryPublisherContext` 를 `__all__` 에서 제거하고 DELETE candidate 로 분류.

#### H3. `static_broadcaster` 는 한 번만 send 하고 node 이후에 stale — `/tf_static` latched QoS 의존
- 파일/라인: `marslab/ros2_bridge/tf_broadcaster.py:80-83`
- 인용:
  ```python
  broadcaster = StaticTransformBroadcaster(node)
  msgs = build_static_sensor_transforms(sensor_frames, parent_frame_id)
  broadcaster.sendTransform(msgs)
  return broadcaster
  ```
- 문제: `/tf_static` 는 `transient_local` durability 로 late-joiner 에게 latched 되지만, 다음 경우 실패:
  - Stage-3 런타임이 slam_toolbox 보다 늦게 기동하면 broadcaster.sendTransform 은 slam_toolbox 의 subscription 확립 **이전에** 한 번 호출되고 끝난다. `StaticTransformBroadcaster` 는 내부적으로 transient_local 로 publish 하지만 **Isaac Sim 런타임에서 실제 rclpy QoS 레벨이 보장되는지 확인 주석 없음**.
  - `cmd_vel_subscription` 만 반환값으로 keep-alive 되고, `static_broadcaster` 도 keep-alive 목적으로 `BridgeContext` 에 들어있으나, 재전송 API 가 외부에 공개되지 않아 런타임 중 sensor 추가/이동이 불가능.
  - 또한 한 번도 재호출되지 않는데 `return broadcaster` 의 타입은 `Any` — 호출자가 뭘 받는지 알 수 없다.
- 수정:
  - docstring 에 "transient_local latching 가정" 명시.
  - `BridgeContext` 에 `publish_static_tf(frames)` 메서드 추가해 런타임 재게시 가능하게.
  - 또는 ROS2 launch 의 `tf2_ros/static_transform_publisher` 로 outsource 하고 본 모듈에서 제거.

#### H4. `ros2_cfg` dict 타입을 신뢰하지 않는 defensive guard 가 들쭉날쭉 — 설계 누수
- 파일/라인: `marslab/ros2_bridge/rclpy_integration.py:89`, `marslab/ros2_bridge/sensor_graph.py:134`, `sensor_graph.py:87-88`
- 인용:
  ```python
  # rclpy_integration.py:89
  odom_pub_cfg = ros2_cfg.get("odom_publisher", {}) if isinstance(ros2_cfg, dict) else {}
  ```
  ```python
  # sensor_graph.py:87
  ns = str(ros2_cfg["namespace"])   # dict 단언 후 바로 indexed access
  # sensor_graph.py:134
  raw = ros2_cfg.get("graph_path") if isinstance(ros2_cfg, dict) else None
  ```
- 문제: 같은 함수 시작에서 `ros2_cfg["namespace"]`, `ros2_cfg["topics"]` 로 dict 를 전제하다가 수 줄 아래에서 `isinstance(ros2_cfg, dict)` 를 체크한다. 논리적으로 두 가지 모두 참이거나 모두 거짓이 되어야 한다 — 이중 확인은 Dead Code (앞에서 이미 dict 아니면 TypeError 로 실패) + 잘못된 안전감을 유발.
  - `Ros2BridgeConfig` pydantic 스키마가 존재하는데 (`marslab/config/schema/ros2_bridge.py`), `rclpy_integration` / `sensor_graph` 는 **검증된 객체가 아닌 raw dict** 를 그대로 받는다. schema validation 이 실제 런타임 경계를 통과하지 못한 상태이므로 `"graph_path": " /World/Graph"` 같은 잘못된 값은 여전히 `_resolve_graph_path` 안에서 pydantic 으로 **두 번째 검증** 이 필요하다 (현 코드가 그렇게 함). double validation + inconsistent shape.
- 수정:
  - `init_rclpy_side(ros2_cfg: Ros2BridgeConfig, ...)` 로 시그니처를 변경하고 caller 가 scenario_loader 에서 검증된 객체를 전달하도록 강제. 현재 schema 가 부분적으로만 필드를 가지므로 `namespace`, `topics`, `rates`, `odom_publisher` 까지 모두 스키마화 필요 (이미 `ros2_bridge.py:41` 의 docstring 이 "R4-6+ 에 나머지 promote" 라고 인정).
  - 문서화된 부채가 CRITICAL 되기 전에 정리해야 함.

#### H5. `cmd_vel` 콜백이 `rclpy.spin_once` 없이 작동하지 않음 — 암묵적 의존성이 docstring 에 없음
- 파일/라인: `marslab/ros2_bridge/cmd_vel_subscriber.py:53-57`, `marslab/ros2_bridge/rclpy_integration.py` (spin 관련 언급 0건)
- 인용:
  ```python
  def _cb(msg: Twist) -> None:
      twist_state["v"] = float(msg.linear.x)
      twist_state["w"] = float(msg.angular.z)
  return node.create_subscription(Twist, topic, _cb, queue_size)
  ```
- 문제: `create_cmd_vel_subscriber` 및 `init_rclpy_side` docstring 어디에도 "콜백이 호출되려면 호출자가 `rclpy.spin_once()` 를 주기적으로 돌려야 한다" 는 언급이 없다. 실제로 Stage-4 런타임 (`run_stage4.py:283-287`) 이 `_spin_once` 를 수동으로 만들어 `LoopContext.spin_once` 에 주입한다. 모듈 API 계약이 외부 런타임에 암묵적으로 전가되어 있다 (Coupling by Convention).
  - 새 사용자가 `init_rclpy_side` 호출 후 cmd_vel 이 안 들어온다고 조사하면 `/cmd_vel` publish 측 문제로 오진단할 가능성 높음.
- 수정:
  - docstring에 "The returned node requires periodic `rclpy.spin_once(node, timeout_sec=0.0)` calls from the main loop; this module does not spawn an executor" 명시.
  - 또는 `BridgeContext.spin_once()` 편의 메서드 추가.

---

### MEDIUM

#### M1. `SensorFrameSpec` 타입 힌트가 `Tuple[str, Sequence[float]]` 인데 호출자는 `Tuple[str, np.ndarray]` 를 넘긴다
- 파일/라인: `marslab/ros2_bridge/tf_broadcaster.py:24-25`, `scripts/phase1/run_stage4.py:250-256`
- 인용:
  ```python
  SensorFrameSpec = Tuple[str, Sequence[float]]
  ```
- 문제: `np.ndarray` 는 `Sequence[float]` 의 정확한 subtype 이 아니다 (대부분의 타입 체커가 허용하지만 strict mypy 는 에러). 호출자가 `camera_cfg["local_translation"]` (YAML loader 가 `list[float]` 또는 `np.ndarray` 반환) 을 그대로 넘기므로 정답은 `Sequence[float] | np.ndarray` union 또는 `Iterable[float]`.
- 수정: `SensorFrameSpec = Tuple[str, "ArrayLike"]` (numpy.typing.ArrayLike) 로 변경.

#### M2. `Dict[str, float]` 으로만 정의된 `twist_state` — 확장 시 key proliferation
- 파일/라인: `marslab/ros2_bridge/cmd_vel_subscriber.py:50-55`, `marslab/ros2_bridge/context.py:37`
- 인용:
  ```python
  if not {"v", "w"} <= set(twist_state.keys()):
      raise KeyError("twist_state must contain keys 'v' and 'w'")
  ```
- 문제: Primitive Obsession. `v / w` 외에 `vy` (strafing), `vz` (aerial) 등이 필요해지는 순간 (Phase 2 rotorcraft 스코프가 있음) 이 dict 는 graceful 하게 확장되지 않는다. `@dataclass class TwistCommand` 로 묶어야 타입 안전 + 확장 용이. 현재 dict 는 "shared mutable state" 라고 docstring 이 자랑스럽게 말하지만 (`cmd_vel_subscriber.py:37`), 이는 thread safety 도 보장 안 됨 (rclpy executor thread vs sim step thread).

#### M3. Silent swallow 없이도 bare `except:` 와 가까운 패턴이 main_loop 에는 있으나 bridge 내부에는 **조용한 dict 변경** 이 존재
- 파일/라인: `marslab/ros2_bridge/cmd_vel_subscriber.py:53-55`
- 인용:
  ```python
  def _cb(msg: Twist) -> None:
      twist_state["v"] = float(msg.linear.x)
      twist_state["w"] = float(msg.angular.z)
  ```
- 문제: 콜백이 `float()` 캐스팅 중 `TypeError` 또는 `ValueError` 를 던질 수 있으나 rclpy executor 에서는 일반적으로 이를 로그로만 남긴다. `msg.linear.x` 가 NaN 이면 그대로 전파되어 articulation `set_joint_velocity_targets` 이 NaN 으로 폭발. validation 부재.
- 수정: NaN/Inf 체크 후 clip 또는 reject.

#### M4. `graph_path` 하드코딩 문자열이 schema default, 모듈 상수, docstring 셋에 걸쳐 중복
- 파일/라인: `marslab/ros2_bridge/sensor_graph.py:44`, `marslab/config/schema/ros2_bridge.py:47`, `marslab/ros2_bridge/sensor_graph.py:10`
- 인용:
  ```python
  # sensor_graph.py:44
  GRAPH_PATH = "/World/Stage3ROS2Graph"
  ```
  ```python
  # schema/ros2_bridge.py:47
  default="/World/Stage3ROS2Graph",
  ```
- 문제: G5 ("모든 설정은 YAML") 원칙에서도 **DRY violation**. 동일 리터럴이 두 번 반복됨. 스키마 default가 이미 이 값이므로 모듈 상수는 불필요. 더구나 `_resolve_graph_path` 에서 `GRAPH_PATH` 를 fallback 으로 쓰면서 스키마의 `Ros2BridgeConfig()` 또한 default 를 주므로 두 중 어느 경로로든 같은 값이 나온다 (death by two constants).
- 수정: `GRAPH_PATH` 를 삭제하고 `_resolve_graph_path` 는 `Ros2BridgeConfig().graph_path` 만 fallback 으로 사용. `__all__` 과 legacy test (`test_ros2_bridge_structure.py` 는 `GRAPH_PATH` export 를 체크하진 않음) 마이그레이션 후.

#### M5. `_set_xyz` / `_set_wxyz` 는 타입 힌트가 `Any` — ROS2 msg 인터페이스를 그냥 포기
- 파일/라인: `marslab/ros2_bridge/odometry_publisher.py:22-34`
- 인용:
  ```python
  def _set_xyz(target: Any, vec: np.ndarray) -> None:
  def _set_wxyz(target: Any, quat: np.ndarray) -> None:
  ```
- 문제: `target: Any` 는 docstring 으로만 "`.x/.y/.z` 필드를 가진다" 고 명시. Protocol 클래스로 타입 안전화 가능 (`class HasXYZ(Protocol): x: float; y: float; z: float`). 현 상태는 오타 (`.y` 대신 `.yy`) 가 런타임까지 잡히지 않는다.

#### M6. 토픽 이름 생성이 **문자열 concat** — namespace 유효성 검증 없음
- 파일/라인: `marslab/ros2_bridge/sensor_graph_builder.py:17-19`
- 인용:
  ```python
  def _ns_topic(ns: str, name: str) -> str:
      return f"/{ns}/{name}"
  ```
- 문제: `ns` 가 `"rover/prefix"` 또는 `"/leading"` 또는 `""` 등 비정상 값일 때 `//rover//prefix//cmd_vel` 같은 깨진 topic 이름이 나온다. ROS2 topic name grammar (`[a-zA-Z_][a-zA-Z0-9_/]*`) validator 가 없다. 보안 측면에서 eval 은 아니므로 injection 은 아니지만, Nav2 를 쓰는 다중 로버 시나리오에서 topic crash 발생 가능.
- 수정: `rclpy.validate_topic_name` 또는 정규식으로 검증. ns 가 비어있으면 namespace 없이 `/{name}` 반환하는 fallback.

#### M7. `sensor_graph.py:137` — pydantic `model_validator` 를 매 호출 재실행 (성능은 사소하나 의도 불명)
- 파일/라인: `marslab/ros2_bridge/sensor_graph.py:132-138`
- 인용:
  ```python
  from marslab.config.schema.ros2_bridge import Ros2BridgeConfig
  raw = ros2_cfg.get("graph_path") if isinstance(ros2_cfg, dict) else None
  if raw is None:
      return GRAPH_PATH
  validated = Ros2BridgeConfig(graph_path=str(raw))
  return validated.graph_path
  ```
- 문제: 이미 검증된 scenario config 에서 다시 `Ros2BridgeConfig(...)` 를 쌓는 것은 H4 의 결과. `graph_path` 하나만 검증하자고 전체 pydantic 모델 인스턴스화. 또한 `cmd_vel_queue_size` 는 여기서 검증되지 않는다 — 대칭성 붕괴.
- 수정: H4 수정 이후 자연 해결. 별개 수정 시엔 정규식 1줄로 prim-path 검증.

---

### LOW

#### L1. `__init__.py` 의 docstring 이 R4-6 타임스탬프 + 내부 migration note 를 포함
- 파일/라인: `marslab/ros2_bridge/__init__.py:16-18`
- 인용: `"R4-6 (2026-04-22): ``BridgeContext`` dataclass and ``init_rclpy_side`` moved to ..."`
- 문제: 퍼블릭 docstring 에 개발팀 내부 단계 명칭이 새어나감. 외부 사용자에게는 잡음이고, 외부 리뷰어에게는 "리팩토링 흔적 정리 못함" 신호. 주석-데오도란트 패턴.
- 수정: 이 문단을 git log 또는 CHANGELOG 로 이동, docstring 은 공개 API 만 기술.

#### L2. `context.py` docstring 에도 R4-6 참조 (`:15-18`)
- 파일/라인: `marslab/ros2_bridge/context.py:1-8`
- 문제: L1 과 동일. "동일 패키지 top-level import 우회" 와 같은 구현 세부 누수.

#### L3. `sensor_graph.py` docstring 의 R4-5 migration note (`:15-27`)
- 파일/라인: `marslab/ros2_bridge/sensor_graph.py:15-27`
- 문제: L1 과 동일 패턴. R4 / R4-5 / R4-6 / R3 / G5 등 내부 마커가 module docstring 과 inline comment 에 45회 이상 등장 (repo-wide). 감사자 경험: **주석으로 안심감을 팔고 실제 코드는 그대로** 는 전형적 smell.

#### L4. `odometry_publisher.create_odometry_publisher` 기본값이 `"odom"` / `"base_link"` — REP-105 는 준수하나 **YAML 에서도 이 값을 직접 덮어쓰게 허용** (설계 충돌)
- 파일/라인: `marslab/ros2_bridge/odometry_publisher.py:51-52, 61-62`
- 문제: REP-105 는 `odom`, `base_link` 프레임 명칭을 **관례적으로 고정** 하므로 custom 값을 허용하면 slam_toolbox 의 기본 파라미터와 mismatch 로 조용히 실패. 유연성이 부채다. 최소한 schema 레벨에서 Literal 로 제한하거나 경고 로깅.

#### L5. `tf_broadcaster.build_static_sensor_transforms` 가 rotation을 항상 identity 로 고정
- 파일/라인: `marslab/ros2_bridge/tf_broadcaster.py:53-56`
- 인용:
  ```python
  msg.transform.rotation.w = 1.0
  msg.transform.rotation.x = 0.0
  msg.transform.rotation.y = 0.0
  msg.transform.rotation.z = 0.0
  ```
- 문제: IMU / LiDAR 센서가 `base_link` 대비 회전되어 설치되는 경우 (v2.0 multi-sensor rig) 이 함수는 translation 만 지원한다. `SensorFrameSpec` 가 rotation field 없이 정의되어 있어 확장 시 signature breaking change.
- 수정: `SensorFrameSpec = Tuple[str, Sequence[float], Sequence[float]]` (translation, rotation WXYZ) 로 미리 확장하고 default identity quaternion 허용.

#### L6. Lying docstring — `tf_broadcaster.py:10-17`
- 파일/라인: `marslab/ros2_bridge/tf_broadcaster.py:10-17`
- 인용:
  > "The M2020 USD is imported with a 180° X-roll so the chassis "up" maps to world ``+Z``.  The YAML ``local_translation`` is authored in the post-roll body frame where ``+Y_body = -Y_world`` and ``+Z_body = -Z_world``.  We therefore flip Y and Z when broadcasting the transform..."
- 문제: **180° X-roll 의 정확한 효과는 Y flip + Z flip 이 맞다.** 하지만 이 주석은 `broadcast 는 world frame 으로 변환한다` 는 인상을 준다. TF tree 관점에서 parent=`base_link` (which is already in post-roll body frame), child=`camera_link` 이므로 transform 은 **post-roll body frame 의 offset** 이어야 한다. 여기서 Y/Z 를 negate 하는 것은 "YAML 저자가 world frame 에서 offset 을 썼다" 를 가정한 역변환. 즉 docstring 의 전제가 충돌: YAML 이 post-roll body frame 이라면 flip 은 **틀렸고**, YAML 이 pre-roll world-aligned 였다면 "post-roll body frame 에 authored" 라는 문구는 거짓. 최소한 하나는 잘못된 서술.
- 수정: 실측해서 (하나의 scenario 에서 camera_link 위치가 RViz 에 어디 뜨는지) 주석과 코드 중 어느 쪽이 진실인지 확정하고 수정.

#### L7. `__init__.py:__all__` 에 `publish_odometry`, `create_odometry_publisher`, `OdometryPublisherContext` 가 export 되지만 production 비사용 — public surface 비대화
- 파일/라인: `marslab/ros2_bridge/__init__.py:41-53`
- 문제: 외부 사용자가 public API 로 오인할 수 있는 함수들이 모두 dead. H2 와 연결.

#### L8. 보안 이슈 없음 (eval / exec / subprocess / yaml.load 부재 확인)
- Scope 내 모든 파일 grep: `eval` / `exec` / `subprocess` / `pickle` / `yaml.load` 매치 0건. Clean.

#### L9. 타입 힌트 일관성 — `node: Any` 가 전역적. `rclpy.node.Node` TYPE_CHECKING import 필요
- 파일/라인: `cmd_vel_subscriber.py:22`, `odometry_publisher.py:56,99`, `rclpy_integration.py`, `tf_broadcaster.py:62`
- 문제: lazy-import 를 위해 `Any` 를 썼다고 추정되나, `TYPE_CHECKING` 가드 밑에서 `from rclpy.node import Node` 하면 타입 안전성 복구 가능 (런타임 import 회피 유지).

---

### DELETE candidates

#### D1. `marslab/ros2_bridge/odometry_publisher.py::publish_odometry` + `OdometryPublisherContext.frame_id` / `child_frame_id` 필드
- 이유: production call site 0개. `main_loop._publish_odometry` 가 병행 구현으로 사용 중. H2 참조.
- 액션: 통합 or 삭제. 삭제 시 user rule "delete_later 디렉토리로 git mv" 따를 것.

#### D2. `marslab/ros2_bridge/sensor_graph.GRAPH_PATH` 모듈 상수
- 이유: M4. 스키마 default 로 대체 가능.
- 액션: deprecation warning 1 릴리즈 → 삭제.

#### D3. `marslab/ros2_bridge/__init__.py` docstring 내 R4-6 migration note
- 이유: L1, L2, L3. public 문서에 부적합.
- 액션: CHANGELOG 로 이관.

#### D4. `sensor_graph.py:129` `_resolve_graph_path` 의 fallback-to-module-constant branch
- 이유: `Ros2BridgeConfig` 가 이미 default 를 가지므로 항상 모델 초기화만으로 충분.
- 액션: `_resolve_graph_path` 를 `Ros2BridgeConfig(**{k:v for k,v in ros2_cfg.items() if k=='graph_path'}).graph_path` 로 단순화.

---

### WATCHLIST

#### W1. `main_loop.py` 와 `ros2_bridge/` 의 odom 책임 중복이 v1.1 마감 시점까지 해소되지 않으면 frame_id / child_frame_id YAML override 가 **조용히 무시되는 현상** 이 paper 재현 실패로 이어질 수 있다. (H2 + L4)

#### W2. slam_toolbox / Nav2 기본 QoS 와 현재 default QoS 의 mismatch 가 첫 Stage-3 실측에서 드러날 것. C1 수정 전에 ros2-bridge-verification skill 로 topic hz 측정 필수.

#### W3. Static TF lifetime — slam_toolbox 가 bridge 보다 먼저 올라올 때 `/tf_static` latch 가 실제 수신되는지 integration test 로 확인 필요. H3.

#### W4. `rclpy_integration.init_rclpy_side` 가 `rclpy.init()` 재진입 방어 부족 (C3). pytest 동일 세션에서 Stage-3 two-pass 테스트 시 잠복 버그.

#### W5. `sensor_graph_builder._build_set_values` 에 QoS 관련 Isaac Sim ROS2 helper 속성 (`qosProfile`, `queueSize`) 이 없음. Isaac Sim 5.x 의 `ROS2CameraHelper` / `ROS2RtxLidarHelper` 가 해당 입력을 노출한다면 v1.0 SLAM 튜닝 시 여기를 건드릴 수밖에 없다. 현재는 default 에 의존 (문서화도 없음).

#### W6. `tf_broadcaster` 의 Y/Z flip 로직 (L6) 이 URDF import 회전과 실제 sensor 배치 사이의 single source of truth 를 **주석** 에만 의존. scenario 추가 시 매번 재검증 필요한 암묵적 결합.

#### W7. `BridgeContext` 가 `twist_state: Dict[str, float]` 을 그대로 외부에 노출 → main_loop 가 직접 쓰기/읽기. thread safety 와 encapsulation 둘 다 포기 상태 (M2).

---

## 요약

- CRITICAL 3 (C1 QoS 누락, C2 `/tf` vs `/tf_raw` split, C3 rclpy.init race) · HIGH 5 (H1 shutdown 부재, H2 publish_odometry dead-duplication, H3 static TF lifecycle, H4 schema 경계 누수, H5 spin 암묵의존) · MEDIUM 7 · LOW 9 · DELETE 4 · WATCHLIST 7.
- 가장 시급: C1 + C2 + H2. 세 가지는 v1.0 SLAM/Nav2 integration 주장의 바탕이 되어야 하는데, QoS 미설정 + joint TF 고립 + odom publish 경로 중복이 하나라도 남으면 iSpaRo 실측 재현이 환경 의존으로 흔들린다.
- 부가 평가: 보안 이슈 없음 (L8). 그러나 주석-데오도란트 패턴이 모든 파일 docstring/comment 에 누적되어 있어 "리팩토링 완료" 주장은 내부 마커 (R4-5/R4-6/G5/Oracle) 로만 뒷받침되고 실제 공개 API 의 dead-code/duplication 은 정리되지 않았다 — 외부 리뷰어 시점에서 신뢰도 하락 요인.
