# Space-Domain (Planetary Rover) 시뮬레이터를 위한 User-Friendly 기능 20가지

> Perception / Navigation 연구자 관점에서, CARLA가 자율주행 연구의 사실상 표준이 된 이유("실험 돌리기 쉽고, 데이터 뽑기 쉽고, 결과 재현하기 쉬움")를 space-domain에 적용했을 때 있으면 좋을 기능 20가지를 정리한 문서.
>
> 실제로 OmniLRS, NASA Ames Gazebo-lunar sim, Artemis, Chrono-based lunar sim 등에서 일부가 이미 구현되어 있고, 각 항목별로 출처를 함께 정리했다.

---

## A. Scene / Environment 생성

### 1. DEM 기반 + Procedural 하이브리드 지형 생성
LRO, HiRISE 같은 실제 위성 DEM을 coarse layer로 두고 그 위에 분화구·암석 분포를 power-law로 procedural하게 덮어쓰는 방식. OmniLRS가 5m/pixel 수준의 실제 DEM을 2.5cm/pixel까지 procedural하게 augment하는 geometry clip map 구조를 쓰고 있는데, 이걸 연구자가 스크립트 한 줄로 호출할 수 있으면 매우 편함.

### 2. 천체·환경 프리셋 원클릭 전환
Moon / Mars / Europa / asteroid 등을 드롭다운 하나로 선택하면 중력·대기·온도 범위·regolith 속성이 자동으로 바뀌는 기능. 지금은 달/화성 시뮬레이터가 대부분 별개 프로젝트로 운영되어 재사용성이 떨어짐 (예: DUST, URSim, EDGE, DARTS, Chrono-based sim 등 NASA/DLR 각 기관별로 따로 개발됨).

### 3. 실제 좌표·날짜 기반 조명 (Ephemerides)
위도·경도·UTC를 입력하면 태양과 지구의 위치를 실시간으로 계산해주는 기능. OmniLRS가 이미 lunar 좌표와 날짜를 입력하면 ephemerides로 태양·지구 위치를 계산해 현실적인 조명을 만들어주는 기능을 지원하는데, 이걸 Mars/asteroid로 확장하면 극지·equator·다양한 solar elevation 실험이 쉬워짐.

### 4. PSR / 극저조도 시나리오 프리셋
달 극지의 영구음영지역(PSR)은 perception 알고리즘에게 극단적으로 어려운 환경. 달 극지의 harsh한 조명과 낮은 입사각, 레골리스 특유의 반사 특성이 인간·컴퓨터 비전 모두에게 도전적인 환경이라는 점이 NASA Ames 시뮬레이터에서도 강조됨. Earthshine-only 시나리오, 헤드라이트 조명 시나리오 등을 presets로 제공.

### 5. GUI 기반 Domain Randomization
암석 밀도, albedo, 경사, rock size distribution, texture seed, dust 농도 등을 슬라이더/체크박스로 조절하고, "n개 variant batch 생성" 버튼 하나로 대량 샘플링. OmniLRS는 DEM 생성, visual mesh 업데이트, collision mesh 계산을 포함한 terrain randomization을 3초 이내에 수행할 수 있는데, 이 속도를 GUI와 연결하면 연구자가 데이터 생성 파이프라인을 코딩 없이 돌릴 수 있음.

---

## B. 로봇 & 센서

### 6. 실제 미션 로버 라이브러리 + 사용자 CAD 임포트
VIPER, Perseverance, MSL, MER, Zhurong, Chang'e 등 실제 미션 rover의 URDF/USD 모델이 "기본 제공"되어야 함. OmniLRS가 EX1, Leo rover, Husky 같은 여러 rover 모델을 기본 제공하고 ROS1/ROS2 binding을 통해 multi-robot을 지원하는 구조가 좋은 참고가 됨. CAD/URDF drag-and-drop 임포트도 필수.

### 7. Calibrated Sensor Preset (실제 미션 센서 모델)
Navcam, Hazcam, Mastcam-Z, SuperCam, LiDAR(VIPER), IMU 등 실제 미션 센서의 intrinsic/extrinsic, noise, 왜곡, FOV를 프리셋으로. OmniLRS는 RGBD 카메라, 2D/3D LiDAR, IMU, TF, joint-states 등 Isaac의 기본 센서를 사용하지만, 여기에 "flight-like calibration" 프리셋이 더해지면 sim-to-flight 가치가 올라감.

### 8. 자동 Ground-Truth 생성
RGB 한 프레임에 대해 depth, semantic segmentation, instance segmentation, 6-DoF pose, surface normal, optical flow, rock class label을 한 번에 뽑아주는 것. OmniLRS는 synthetic data pipeline을 machine-learning 용도로 제공하고 sim-to-real rock instance segmentation으로 효과를 입증했지만, 더 많은 GT 종류를 "토글"로 선택할 수 있으면 좋겠음.

### 9. 표준 Dataset 포맷 자동 Export
COCO, KITTI, nuScenes, ROS2 bag, PDS4 (행성 과학 표준 포맷) 등으로 한 번에 내보내기. 논문 쓸 때 포맷 변환 스크립트 짜느라 쓰는 시간이 생각보다 많음. (순수 UX 관점 제안 — 기존 시뮬레이터에서 아직 통일된 솔루션이 없는 영역)

---

## C. Physics / 환경 효과

### 10. Sim2Real Photorealism 변환 토글
렌더링된 영상을 real dataset 스타일로 변환해주는 플러그인. CARLA2Real이 Enhancing Photorealism Enhancement 기법으로 CARLA 출력을 Cityscapes/KITTI/Mapillary Vistas 스타일로 근실시간 13 FPS로 변환하는 플러그인을 제공한 것처럼, planetary sim에서도 MER/MSL/Perseverance 실제 영상 스타일로 변환하는 모델을 내장하면 sim2real 연구에 직결.

### 11. 선택 가능한 Terramechanics 엔진
Rigid ground / Bekker-Janosi / DEM / data-driven regression 중 연구 목적에 맞게 선택. SCM은 Bekker/Janosi 기반의 저정밀·저계산 모델로 path planning 수준에 적합하고, DEM은 wheel-terrain interaction 연구에 많이 쓰임. 연구자가 드롭다운으로 바꿀 수 있으면 "빠른 navigation 실험"과 "정밀 mobility 분석"을 같은 툴에서 할 수 있음.

### 12. Wheel Slip / Sinkage / Wheel-Trace 시각화
뒤에 남는 바퀴 자국이 학습 데이터로도 중요하고 디버깅에도 유용함. JAXA/Tohoku 그룹이 slip ratio와 sinkage regression model을 실험 데이터 기반으로 만들어 OmniLRS에 integration하고 realistic wheel trace를 실시간 렌더링하는 deformation engine을 구현. 이런 걸 기본 탑재.

### 13. Regolith 광학 효과 (Hapke, Opposition Effect)
달/화성 표면은 지구와 반사 특성이 다름. Chrono-based sim은 Chrono::Sensor 카메라 모델에 ray tracing과 Hapke Photometric Function을 적용하는데, 이 수준의 광학 모델이 체크박스로 켜지면 과학적으로 훨씬 쓸 만한 데이터가 나옴.

### 14. Dust Dynamics + 센서 열화 시뮬레이션
먼지로 인한 렌즈 오염, LiDAR 산란, visibility 저하 모델링. Chrono는 rarefied atmosphere에서 dust가 카메라 view를 가리고 active light sensing에 악영향을 주는 현상을 phenomenological model로 구현하고, volumetric rendering으로 dust volume을 렌더링. 이런 현상을 "dust storm ON/OFF" 같은 토글로 제공.

---

## D. 시나리오 / 재현성 / 워크플로우

### 15. 통신 지연 · 대역폭 제약 시뮬레이션
지구-화성 간 수 분의 delay, DSN 가용 시간, 제한된 downlink bandwidth 등을 네트워크 레이어에서 모사. 이게 없으면 teleoperation이나 ground-ops autonomy 연구가 비현실적으로 쉬워짐. Artemis 팀도 Earth-Mars time delay 때문에 실시간으로 rover를 모니터링할 수 없고, 대신 받아온 데이터로 model의 유효성을 사후 검증하는 방식임을 강조.

### 16. Python DSL 기반 Scenario Scripting
CARLA의 ScenarioRunner처럼, "rover A가 경사 15도에서 slip 0.3을 발생시킨 상황에서 B 카메라에 dust 30% 오염" 같은 조건을 YAML/Python으로 정의하고 재실행할 수 있는 기능. 이게 있어야 논문 reproducibility가 확보됨. (순수 UX 제안 — CARLA에서 검증된 패러다임)

### 17. Deterministic Seed 기반 Replay + Regression Test
같은 seed로 돌리면 센서 노이즈·조명·물리까지 bit-exact로 재현되어야 함. 알고리즘 버전 A/B를 같은 궤적 위에서 돌려서 metric diff를 시각화해주는 regression test dashboard가 있으면 퍼셉션 모델 개선 과정이 매우 깔끔해짐. (UX 제안 — ML ops에서 보편적인 MLflow 스타일의 적용)

---

## E. 평가 / 배포

### 18. Benchmark Suite + 공개 리더보드
CARLA Leaderboard가 자율주행 연구에 미친 영향을 생각하면, planetary 영역에서도 표준 task(traversability estimation, VO/VIO, LiDAR SLAM, rock segmentation, hazard detection) 벤치마크와 공개 순위표가 필요. OmniLRS 저자들도 Isaac 기반 simulator가 Gazebo와 달리 ray/path tracing 가능해 lunar illumination 렌더링에 유리하다는 걸 언급하는데, 이걸 표준 벤치마크로 묶으면 공정 비교가 가능해짐.

### 19. Failure Injection Framework
센서 dropout, 휠 고장(예: Spirit의 우측 전방 구동 모터 고장, Opportunity의 우측 전방 조향 모터 영구 고정 같은 실제 사례), dust storm, 일식, 급경사 sandbox 같은 상황을 한 줄로 주입할 수 있는 API. Robustness/fault-tolerance 연구에 직접적으로 유용.

### 20. Multi-Agent Orchestration + Headless Cloud Scalable Mode
Rover + lander + orbiter + 여러 rover가 협력하는 시나리오(예: Artemis base construction)는 앞으로 점점 중요해지는 use case. AGX Dynamics 기반으로 여러 자율 기계의 lunar construction work을 behaviour tree + ROS2로 조율하는 simulation framework이 이미 나오고 있는 흐름. 여기에 GUI 없는 Docker/Singularity headless 모드와 HPC/cloud 배포 스크립트가 기본 제공되면 대량 실험(RL 학습, domain randomization, benchmark 스윕)이 한결 쉬워짐.

---

## 참고 출처 (Sources)

- **OmniLRS**: Richard et al., "OmniLRS: A Photorealistic Simulator for Lunar Robotics," *ICRA 2024*. arXiv:2309.08997.
- **OmniLRS GitHub**: https://github.com/OmniLRS/OmniLRS
- **NASA Ames / Open Robotics lunar Gazebo simulator**: Shirley, Deans, Cannon, Fong, "Planetary Rover Simulation for Lunar Exploration Missions," NTRS 20190027571.
- **Artemis (Adams-based rover terramechanics simulator)**: Chow, Arvidson, Bennett et al., "Simulations of Mars Rover Traverses," *Journal of Field Robotics*; KISS Caltech PDF.
- **Artemis 관련 NASA Tech Briefs 기사**: techbriefs.com (MIT Robotic Mobility Group / WashU / JPL).
- **ROAMS (JPL)**: NASA NTRS 20060028642.
- **Chrono-based lunar sensor simulator (dust, Hapke, VIPER/RASSOR digital twin)**: arXiv:2410.04371.
- **CARLA2Real (sim2real plugin)**: Pasios & Nikolaidis, arXiv:2410.18238.
- **JAXA/Tohoku data-driven terramechanics on OmniLRS**: arXiv:2601.04547.
- **AGX Dynamics 기반 lunar construction framework**: arXiv:2505.22091.
