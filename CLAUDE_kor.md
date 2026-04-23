# CLAUDE.md -- MarsLab 개발 가이드라인

## 프로젝트 개요

MarsLab은 행성/필드 로보틱스 연구를 위한 표준화된 미션 시나리오를 제공하는
오픈소스 화성 시뮬레이션 플랫폼으로, NVIDIA Isaac Sim 위에 구축되었다.
목표: iSpaRo 2026 Regular Paper (8페이지), 마감 2026년 6월 16일.

**저장소**: `MarsLab/` (Apache 2.0 라이선스)
**엔진**: Isaac Sim 5.x + Isaac Lab
**핵심 스택**: Python 3.10+, ROS2 Jazzy, Isaac Sim Extensions, USD/URDF

## 사용자 가이드라인 (G1-G13)

다음 13가지 가이드라인이 모든 개발 결정을 지배한다. 모든 기능, 모듈, 태스크는
이 가이드라인 중 하나 이상에 추적 가능해야 한다.

1. **G1: 필드 로보틱스 플랫폼.** MarsLab = SLAM, Nav, Exploration을 위한 표준화된
   화성 로보틱스 테스트 플랫폼. v1.0 = 7개 미션 시나리오 + 로버 + SLAM/Nav2 (iSpaRo 2026).
   v2.0 = 고품질 Photorealism. v3.0 = Terramechanics + RL.
2. **G2: RL은 향후 작업 (v3.0).** v3.0까지 RL 환경, 보상 함수, Gym API wrapper 없음.
3. **G3: 코드 재사용 금지.** OmniLRS/RLRoverLab에서 알고리즘/흐름도 영감만 허용.
   코드 복사 금지. 참조 코드베이스 유래 명명 금지.
4. **G4: 로보틱스 우선, Photorealism은 나중.** v1.0 = 충분한 수준 렌더링 + 강력한
   로보틱스 (시나리오, SLAM, Nav2). v2.0 = OmniLRS급 Photorealism. v3.0 = Terramechanics.
5. **G5: 모든 설정 YAML로.** Python 소스에 하드코딩된 상수 제로.
6. **G6: 극단적 모듈성.** 가장 작은 단위부터, 점진적 확장.
7. **G7: 모든 것에 단위 테스트.** 자동화 불가 시 시각 검수.
8. **G8: 작업 이력 로그.** 모든 태스크 요약, 새 팀원이 추적 가능.
9. **G9: PLAN.md = 아키텍처 + 구현 계획.**
10. **G10: 사용자 검토 게이트.** 사용자가 검토하고 수정 요청 가능.
11. **G11: Ultrathink 전반 적용.** 모든 설계 결정에 깊은 추론.
12. **G12: 13-Agent 적대적 토론.** 다중 agent 리뷰를 통한 계획 생성.
13. **G13: 4개 산출물 파일.** PLAN.md (EN), PLAN_kor.md (KR), CLAUDE.md (EN),
    CLAUDE_kor.md (KR).

## 아키텍처 원칙

세 가지 원칙이 모든 구조적 결정을 지배한다:

**P1: 평면 P0 아키텍처.**
조기 추상화 금지. 평면 절차적 코드로 시작. 경험적 복잡도가 요구할 때만 클래스/패턴
추출. Phase 1에 플러그인 시스템, 만능 객체, 등록 메커니즘 금지.
**적용 범위:** P1은 MarsLab 소스 코드(`marslab/`, `scripts/`, `tests/`)에 적용된다.
개발 하네스(`.claude/agents/`, `.claude/skills/`)는 제품 코드가 아닌 인프라 계층이므로
P1 미적용이다.

**P2: 단방향 데이터 흐름.**
Config -> 순수 연산 모듈 -> Isaac Sim 씬 구성 -> 네이티브 시뮬레이션 루프.
어떤 모듈도 시뮬레이션 루프를 수정하지 않음. 순환 의존성 금지. Config만이 모듈 간
공유 의존성.

**P3: 오프라인 우선 테스트.**
모든 순수 연산 모듈(환경 물리, 설정 검증, 암석 SFD, 레이블 변환)은 Isaac Sim이나
GPU 없이 테스트 가능해야 함. Isaac Sim 의존 코드는 통합 전용으로 명확히 표시된
별도 함수/파일에 격리.

## 코딩 표준

### 일반
- Python 3.10+. 모든 공개 함수에 타입 힌트.
- Docstring: Google 스타일. 모든 공개 클래스/함수에 필수.
- 줄 길이: 최대 100자.
- 포맷터: `black`. 린터: `ruff`.
- 전역 상태 금지. Isaac Sim 앱 인스턴스 외 싱글톤 금지.

### 명명 규칙
- 파일/모듈: `snake_case.py`
- 클래스: `PascalCase`
- 함수/변수: `snake_case`
- 상수: `UPPER_SNAKE_CASE`
- ROS2 토픽: `/{robot_name}/{sensor_type}` (예: `/rover/rgb/image_raw`)
- 설정 키: YAML에서 `snake_case`

### Isaac Sim 관련

#### API 사용 규칙
- **우선** `omni.isaac.lab` API를 모든 시뮬레이션 설정에 사용.
- **허용:** Isaac Lab이 필요한 기능의 wrapper를 제공하지 않을 때 `pxr.*` (USD
  Python API) 및 `omni.isaac.core` 사용. 사유를 주석으로 문서화.
- **절대** `omni.isaac.orbit` 사용 금지 (폐기, `omni.isaac.lab`으로 변경됨).
- **임포트 경로의 "omni"**는 NVIDIA 네임스페이스. 참조 코드베이스 이름이 아니며
  가이드라인 G3 (코드 재사용 명명 금지)에서 면제.
- MarsLab 소스 파일에 OmniLRS, RLRoverLab 또는 어떤 참조 코드베이스에서 유래된
  **코드나 명명 금지**. 알고리즘/패턴 영감만 허용.

#### 렌더링 및 에셋
- 지형: DEM 기반에 `TerrainImporter`, 절차적에 `TerrainGenerator` 사용.
- 로봇 임포트: URDF -> USD, `omni.isaac.lab.sim.converters.UrdfConverter` 경유.
- 내장 USD 에셋 (G1, Go2, Valkyrie): Isaac Sim 에셋 경로에서 로드, 저장소에
  복사 금지.
- 센서: Isaac Sim 내장 센서 클래스 사용. 노이즈 모델은 wrapper로 추가.
- 렌더링: RTX Real-Time (ray-tracing)과 RTX Interactive (path-tracing) 모두
  항상 지원. 기본 = 데이터 생성 시 path-tracing, 인터랙티브 사용 시 ray-tracing.

### 설정
- 모든 물리 파라미터는 `configs/mars_env.yaml`에. 절대 하드코딩 금지.
- 로봇 스폰 위치, 센서 파라미터, 벤치마크 설정: `configs/`의 YAML 파일.
- 설정 스키마 검증에 `dataclass` 또는 `pydantic` 사용.
- 시드 기반 재현성: 모든 랜덤 프로세스가 `seed` 파라미터를 받아야 함.

### 화성 물리 상수 (참고 -- 코드가 아닌 설정에 기재)
```yaml
# configs/mars_env.yaml
mars:
  gravity: 3.72          # m/s^2
  atmo_pressure: 610     # Pa
  atmo_density: 0.020    # kg/m^3
  atmo_composition: "95.3% CO2, 2.7% N2, 1.6% Ar"
  surface_temp_mean: -60  # 섭씨
  sol_duration: 88642     # 초 (24시간 37분 22초)
  dust_opacity_range: [0.5, 2.0]  # tau
```

## 모듈 아키텍처

### 모듈 의존성 규칙
1. 순환 임포트 금지. A가 B를 임포트하면, B는 절대 A를 임포트하지 않음.
2. `config/`만 공유 의존성. 모든 모듈이 `MarsLabConfig`에서 읽음.
3. `environment/`는 Isaac Sim 임포트 제로. 순수 Python. 오프라인 테스트 가능.
4. `terrain/dem_loader.py`와 `terrain/rock_placer.py`는 Isaac Sim 임포트 제로.
5. `rendering/`은 `environment/`에 의존 (단방향).
6. `robots/`는 `config/`에만 의존. terrain이나 rendering을 임포트하지 않음.
7. 어떤 모듈도 Isaac Sim 시뮬레이션 루프를 수정하지 않음.
8. 랜덤성을 사용하는 모든 함수는 `seed` 파라미터를 받음.

### 모듈 요약
| 모듈 | 책임 | Isaac Sim 필요? |
|------|------|----------------|
| `config/` | YAML 로드, pydantic 검증, 시드 전파 | 아니오 |
| `environment/` | 화성 물리: 태양 위치, Beer 법칙, COMIMART, 하늘 파라미터 | 아니오 |
| `terrain/` | DEM 로딩, 메시 빌드, 암석 배치, 재질, 레이블 | 부분 |
| `rendering/` | 스카이돔, 태양광, 대기 안개, 렌더 모드 | 예 |
| `robots/` | URDF->USD 스폰 (로버/로터크래프트/사족보행/휴머노이드) | 예 |
| `sensors/` | 카메라, LiDAR, IMU 부착 및 설정 | 예 |
| `ros2_bridge/` | 센서 -> ROS2 토픽 퍼블리싱 | 예 |
| `annotation/` | Replicator 설정, 레이블 변환, 데이터셋 쓰기 | 예 |
| `benchmark/` | Domain randomization, 대량 데이터 생성, AP/mIoU/F1 평가 | 부분 |

## 우선순위 등급

버전별 분류 (iSpaRo 2026 마감: 6/16):

- **v1.0 MUST:** 로버 URDF 수정, 7개 미션 시나리오, 동적 대기,
  SLAM + Nav2 통합, 실험 평가, 8페이지 iSpaRo 논문.
- **v1.0 SHOULD:** 7개 시나리오 전부 완성. GitHub v1.0.0 릴리스.
- **v2.0 (iSpaRo 이후):** OmniLRS급 Photorealism (고폴리 암석, 4K HDRI,
  anti-tiling, pebble scatter).
- **v3.0 (향후):** Terramechanics, RL 환경, 다중 로봇 협조.

MVP 정의: 3+ 시나리오 + 로버 + SLAM + Nav2 + 논문.
최소 제출 가능: 시나리오 1-3 + 동적 대기 + SLAM/Nav2 실험.

## 에러 처리

- 설정 검증 에러: 설명적 메시지와 함께 `pydantic.ValidationError` 발생.
- 파일 누락 (DEM, URDF, HDRI): 전체 경로와 함께 `FileNotFoundError` 발생.
- Isaac Sim API 실패: catch 후 `logging.error()`로 로깅, 컨텍스트와 함께 재발생.
- 런타임 물리값 범위 초과: 파라미터명, 값, 유효 범위와 함께 `ValueError` 발생.
- 예외를 절대 묵묵히 삼키지 않음. bare `except:` 절대 사용 금지.
- 모든 에러 메시지는 디버거 없이 진단할 수 있는 충분한 컨텍스트 포함.

## 테스트 요구사항

### 단위 테스트 (Isaac Sim 불필요)
실행: `pytest tests/unit/ -v`
- 설정 검증: 유효/부적절/범위 초과 파라미터
- Beer 법칙: Appelbaum & Flood (1990) NASA TM-102299 대비 5% 이내 검증
- COMIMART 확산 비율: Vicente-Retortillo et al. (2015) 대비 검증
- Golombek SFD: CFA 곡선이 VL1/VL2/MPF/InSight 데이터 대비 10% 이내
- 시드 결정론: 동일 시드 = 모든 랜덤 함수에서 동일 출력
- 레이블 변환: AI4Mars 4클래스 형식 준수
- 스카이돔 파라미터: 낮은 tau에서 버터스카치 RGB 범위
- 재질 알베도: 화성 범위 [0.10, 0.40] 이내
- 로봇 설정: URDF 경로 유효, 스폰 위치 유효
- Domain randomizer: 시드 재현성, 파라미터 범위

### 통합 테스트 (Isaac Sim 필요)
실행: `pytest tests/integration/ -v`
- 지형이 에러 없이 렌더링
- 로봇 스폰: IMU z축 = 3.72 +/- 0.05 m/s^2 (핵심 테스트)
- 센서가 설정 Hz +/- 10%로 ROS2 토픽에 퍼블리시
- 전체 씬: 화성 유사 외관 (달도 지구도 아님)
- 어노테이션: AI4Mars 레이블이 RGB와 픽셀 정렬
- 대기 안개: tau에 따라 가시거리 변화
- ROS2 bridge: 토픽 표시, 5초 이내 메시지 수신
- 다중 로봇: 2+ 로봇이 독립 네임스페이스로 동작

### 시각 검수
`tests/visual_inspection/checklist.md`에 문서화. 결과는 work_log에 기록.

### CI 파이프라인
- `.github/workflows/unit_tests.yaml`: 모든 push/PR에서 실행. GPU 불필요.
- `.github/workflows/lint.yaml`: black + ruff 모든 push/PR에서 실행.
- 통합 테스트: 수동 실행 또는 GPU 지원 CI (가용 시).

## 버전 범위

### v1.0 (iSpaRo 2026, 현재)

**범위 내:**
- 7개 미션 시나리오: Basic Mars, Rock-Dense, Crater+Slopes, Canyon, Cave,
  Spacecraft Landing, Mars Base
- 동적 물리 로버 (fix_base=False, 안정적 URDF)
- ROS2 풀 스택: cmd_vel, TF, odometry, 센서
- SLAM 통합 (slam_toolbox 또는 rtabmap)
- Nav2 자율 내비게이션
- 동적 대기: sol 내 태양 이동 + tau 변화
- 실험 평가: 시나리오별 SLAM 정확도, SLAM vs tau
- 8페이지 iSpaRo 논문

**v1.0에서 명시적으로 범위 밖:**
- OmniLRS급 Photorealism (v2.0으로 이월)
- Terramechanics (v3.0으로 이월)
- RL 환경 (v3.0으로 이월)
- 다중 로봇 협조 (향후 작업)

### v2.0 (iSpaRo 이후): High Photorealism

- OmniLRS급 PBR, anti-tiling, 4K HDRI, pebble scatter
- Photogrammetry 암석, production 렌더 설정
- Sim2Real perception 벤치마크 (AI4Mars)

### v3.0 (향후): High Physical Fidelity

- Terramechanics (Bekker/Janosi)
- RL 환경 (Isaac Lab Gym API)
- 다중 로봇 협조
- Ls 파라미터화 계절 변동

## 작업 이력 로그

**위치:** `work_log/LOG.md` (추가 전용)

완료된 모든 개발 태스크에 구조화된 항목을 기록:
- 날짜, 주차 번호, 모듈명
- 수행 내용 (파일 참조 포함 글머리 기호)
- 근거가 포함된 핵심 결정
- 테스트 결과 (통과/실패 수)
- 차단 요소 및 해결
- 다음 단계

프로젝트 중간에 합류하는 제3자가 이 파일을 읽고 전체 개발 이력을 파악.
항목 템플릿은 PLAN.md 섹션 7 참조.

## 금지 사항

1. **v1.0에서 Terramechanics 충실도를 주장하지 말 것.** 물리 = 강체 + 화성
   보정 마찰. BCM/SCM/DEM 없음. Terramechanics는 v3.0 플러그인.
2. **v1.0에서 Photorealism을 쫓지 말 것.** 충분한 수준 렌더링 + 강력한 로보틱스.
   OmniLRS급 Photorealism은 v2.0. 로보틱스 작업을 시각적 폴리시로 차단하지 말 것.
3. **화성 파라미터를 하드코딩하지 말 것.** 모든 것을 설정 YAML에.
4. **Isaac Sim 내장 USD 에셋을 저장소에 복사하지 말 것.** 에셋 경로로 참조.
5. **Phase 1에서 로터크래프트 화성 공기역학을 구현하지 말 것.** 단순화 운동학
   모델 사용. 전체 CFD 공기역학 = 별도 프로젝트.
6. **OmniLRS나 RLRoverLab에서 코드를 복사하지 말 것.** ROS2 바인딩 패턴과
   지형 파이프라인 알고리즘은 영감용으로만 연구. 코드 복사나 API 호환성
   유지 금지.
7. **폐기된 Isaac Sim API를 사용하지 말 것** (`omni.isaac.orbit` -> `omni.isaac.lab`
   사용).

## 주요 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| Isaac Sim | 5.x | 코어 시뮬레이션 엔진 |
| Isaac Lab | latest | 로봇 학습 프레임워크 |
| ROS2 | Humble | 로봇 통신 |
| Python | 3.10+ | 주요 언어 |
| GDAL | latest | GeoTIFF/DEM 처리 |
| trimesh | latest | 메시 처리 |
| PyTorch | 2.x | ML 학습 (벤치마크) |
| MMSegmentation or HuggingFace | latest | SegFormer/DeepLab 학습 |

## 벤치마크 설계 규칙

- 출력 형식: AI4Mars 호환 4클래스 레이블 (soil, bedrock, sand, big_rock).
- 모든 벤치마크 설정은 재현성을 위해 시드 고정.
- zero-shot (합성 전용) 및 fine-tune 결과 모두 보고.
- 평가 지표: AP, mIoU, F1 (클래스별 및 평균).
- Domain randomization 축: 조명 (Sol 위상), 먼지 불투명도 (tau), 지형 유형,
  암석 밀도, 카메라 궤적.

## 참조 코드베이스 (구현 전 연구)

| 코드베이스 | 학습 내용 | 링크 |
|-----------|----------|------|
| OmniLRS | 지형 생성 파이프라인, ROS2 바인딩, 암석 배치 | github.com/OmniLRS/OmniLRS |
| SRB | 모듈러 태스크 레지스트리, sim-to-real 자동화 | arXiv:2509.23328 |
| RLROVERLAB | Isaac Lab API 패턴, three-mesh 패턴 | github.com/abmoRobotics/isaac_rover_orbit |
| unitree_sim_isaaclab | G1/H1 Isaac Lab 통합 패턴 | github.com/unitreerobotics/unitree_sim_isaaclab |
| Sim2Dust | DreamerV3 world model RL, zero-shot 전이 | arXiv:2508.11503 |

## 커뮤니케이션 프로토콜

기능 구현 요청 시:
0. **활성화된 하네스 확인.** `.claude/agents/` 가 존재하고 작업이 v1.0 범위(Wk1~Wk6)
   안이라면, 직접 구현 대신 `marslab-dev-orchestrator` 스킬을 통해 라우팅한다.
   단일 개발자 직접 모드는 단순 질문, 문서 오타 수정, Wk7~8 논문 작성에만 사용.
1. 해당 Phase/Week를 확인. 의존성 순서 준수.
2. 참조 코드베이스가 이미 해결했는지 확인. 재구현 전 연구.
3. 설정 기반, 시드 재현 가능 코드 작성.
4. 단위 테스트 포함.
5. Isaac Sim API에 확신이 없으면, 폐기된 API를 추측하기보다 불확실성을
   명시적으로 밝힐 것.

## 하네스: MarsLab v1.0 개발팀

**목표:** iSpaRo 2026 v1.0 (8주, 2026-04-14 ~ 2026-06-16) 개발을 6명 에이전트 팀으로 병렬 수행.

**트리거:** Wk1~Wk6 범위의 개발 작업 요청 시 `marslab-dev-orchestrator` 스킬을 사용한다. 단순 질문, 문서 오타 수정, Wk7~8 논문 작성은 직접 응답 가능. v2.0(photorealism) / v3.0(terramechanics, RL) 작업은 out-of-scope로 거절.

**팀 실행 모드:** 에이전트 팀 (6명). 모든 Agent 호출은 `model: "opus"`.

**상세 정의:** 에이전트 역할·통신 프로토콜·사용 스킬은 `.claude/agents/` 및 `.claude/skills/` 에 있다. 이 CLAUDE_kor.md는 포인터만 제공한다(중복 회피).

**변경 이력:**
| 날짜 | 변경 내용 | 대상 | 사유 |
|------|----------|------|------|
| 2026-04-14 | 초기 하네스 구성 (에이전트 6, 스킬 9, 오케스트레이터 1) | `.claude/` 전체 | iSpaRo v1.0 8주 병렬 개발 체계 구축. 계획: `~/.claude/plans/cheerful-brewing-hammock.md`. |
