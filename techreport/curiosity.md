# Curiosity Technical Report

**Implementation examined:** MarsLab working tree, 27 October 2026.  
**Runtime profile:** [`configs/robots/curiosity.yaml`](../configs/robots/curiosity.yaml), selected with `--robot curiosity`.

## 1. Scope and implementation status

MarsLab implements Curiosity as an articulated rover with six driven wheels, four steering joints, passive rocker-bogie suspension, a two-axis mast, a five-axis arm, 17 rendered cameras and one IMU. Isaac Sim loads the supplied [USD asset](../assets/robots/curiosity/curiosity.usda); the companion [URDF](../assets/robots/curiosity/curiosity.urdf) and [DAE meshes](../assets/robots/curiosity/meshes) support ROS visualization. This is a MarsLab-authored simulation assembled from NASA visualization and engineering references, rather than a NASA-issued flight dynamics model.

The report distinguishes values directly supported by NASA/JPL publications, estimates introduced during asset construction, and runtime numerical settings. Evidence is the current configuration, URDF, USD and runtime source linked below. Appendices A–F preserve the construction, physical-property and sensor-calibration evidence within this report, without requiring separate model metadata or derivation documents.

## 2. Visual asset lineage

The source is NASA's **Curiosity Rover (MSL) (Clean).blend**, from [`nasa/NASA-3D-Resources` at commit `11ebb4ee043715aefbba6aeec8a61746fad67fa7`](https://github.com/nasa/NASA-3D-Resources/tree/11ebb4ee043715aefbba6aeec8a61746fad67fa7). The conversion evaluated the source at Blender frame 180, the deployed visualization pose.

The conversion retained 73 physical source objects and 48,384 triangles, retained once each. Rig helpers, pivot markers, camera transform helpers and shadow planes were excluded; physical arm objects hidden from rendering in the original scene were included. The resulting USD contains 73 mesh prims distributed among 22 rigid bodies. The ROS companion contains 22 DAE files and five PNG textures. Wheel radii were adjusted to the target mobility geometry; source wheel widths were retained.

The source Blender file is no longer distributed. Startup uses prebuilt assets and does not run Blender or reconstruct the model. Generation utilities are development material under `tmp/`, and a distributed automated rebuild workflow is absent. The root [NASA visual-source notice](../LICENSE-NASA-3D-RESOURCES.txt) and [NAIF data notice](../LICENSE-NAIF.txt) document provenance and applicable notices.

[Space ROS's Curiosity Xacro](https://github.com/space-ros/simulation/tree/13226b067d921ca88f40cd643a7b3ce4ae8de903/models/curiosity_path/urdf) was a segmentation and axis-convention reference. No Space ROS/The Construct code, meshes or mass properties were incorporated into the production model.

## 3. Coordinates and articulation

The model uses metres and a forward-left-up frame: +X forward, +Y left, +Z up. The chassis reference origin is at nominal ground between the middle wheels. USD's `/Curiosity` asset is referenced under `/World/Rover`; `Body_Chassis` is the root rigid link.

| Joint family | Count | Implementation |
| --- | ---: | --- |
| Wheel drive | 6 | Continuous rotation about local +Y |
| Corner steering | 4 | Revolute about +Z; ±1.2 rad |
| Rockers | 2 | Revolute about +Y; right rocker mimics left with multiplier −1 |
| Bogies | 2 | Passive revolute joints about +Y |
| Mast | 2 | `MAST_PAN` about +Z, `MAST_TILT` about +Y |
| Arm | 5 | Shoulder azimuth, shoulder elevation, elbow, wrist, turret |

These are **22 links and 21 joints**, not 21 independent degrees of freedom: the differential couples the rockers. Lower-mast deployment hardware and antennas remain fixed. Arm/mast zero angles represent the imported deployed pose, not flight telemetry zeros. Mast pan and turret ranges are ±π, mast tilt ±1.2 rad, and the other arm joints ±1 rad. These are simulation envelopes; flight mechanical stops were not established by this audit.

Wheel radius is 0.25 m, corner wheelbase 2.26 m and corner track 2.125 m. Middle-wheel track is approximately 2.38251 m, derived from the visualization. Source asymmetries were symmetrized for steering. The mast pan/tilt intersection is `[0.8044, -0.5594, 1.9061]` m in the chassis reference frame. Its location and arm-frame evidence come from [NASA NAIF frames](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/fk/msl.tf) and the [MSL structure kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/spk/msl_struct_v02.bsp). The recorded geometric comparison found arm segment-length differences below 4 mm and approximately 16 mm shoulder-elevation axis registration error; these are geometric comparisons, not flight-kinematics certification.

The architecture matches NASA's six-wheel/four-steering rocker-bogie description. NASA describes 0.5 m diameter, roughly 0.4 m wide wheels; the retained MarsLab widths are approximately 0.39473 m. JPL specifies a five-DOF arm, 2.2 m from base to turret center. Matching these features does not establish identical joint zeros, cable constraints or reachable workspace. Sources: [NASA wheel description](https://science.nasa.gov/resource/break-in-raised-tread-on-curiosity-wheel/), [JPL arm paper, Table 2](https://www-robotics.jpl.nasa.gov/media/documents/rankin-2540-arm-kinematics-2021-0102.pdf).

## 4. Mass, inertia, contact and control

### 4.1 Mass allocation and inertia construction

The authored URDF total is **899.18 kg**. NASA's public mission summary gives 899 kg; the more precise value appears in the NASA POST2 touchdown-model paper. That paper uses a simplified single-rigid-body landing model, so its total mass does not validate MarsLab's individual link allocation. Sources: [NASA mission overview](https://science.nasa.gov/mission/msl-curiosity/), [NASA ground-contact paper, Table 1](https://ntrs.nasa.gov/api/citations/20140003460/downloads/20140003460.pdf).

| Rigid link or explicitly listed link family | Mass per link (kg) | Inertia construction |
| --- | ---: | --- |
| `Body_Chassis` | 674.18 | Uniform thin shell on assigned visual triangles |
| `Body_WheelLeftFront`, `Body_WheelLeftMiddle`, `Body_WheelLeftRear` | 7 each | Uniform solid cylinder |
| `Body_WheelRightFront`, `Body_WheelRightMiddle`, `Body_WheelRightRear` | 7 each | Uniform solid cylinder |
| `Body_SteerLeftFront`, `Body_SteerLeftRear` | 3 each | Uniform thin shell |
| `Body_SteerRightFront`, `Body_SteerRightRear` | 3 each | Uniform thin shell |
| `Body_RockerLeft`, `Body_RockerRight` | 18 each | Uniform thin shell |
| `Body_BogieLeft`, `Body_BogieRight` | 12 each | Uniform thin shell |
| `Body_MastPan` | 4 | Uniform thin shell |
| `Body_MastTilt` | 16 | Uniform thin shell |
| `Body_ArmShoulderAzimuth` | 20 | Uniform thin shell |
| `Body_ArmShoulderElevation` | 18 | Uniform thin shell |
| `Body_ArmElbow` | 15 | Uniform thin shell |
| `Body_ArmWrist` | 8 | Uniform thin shell |
| `Body_ArmTurret` | 30 | Uniform thin shell |

JPL provides 67 kg for the arm mechanism excluding turret instruments and 24 kg for those instruments, giving the 91 kg arm total used here. The five-link subdivision remains estimated; the 30 kg turret combines an estimated 6 kg mechanism with 24 kg instruments. The mast's 20 kg allocation and all other subdivisions are MarsLab assumptions. [JPL arm paper](https://www-robotics.jpl.nasa.gov/media/documents/rankin-2540-arm-kinematics-2021-0102.pdf).

Each non-wheel shell is normalized to its assigned mass; this treats exterior visualization triangles as a mass distribution, not a reconstruction of internal structure. Full tensors and local centers of mass are in the URDF; USD stores equivalent principal moments and axes. Wheel axle inertia is 0.21875 kg·m², with transverse moments approximately 0.200265 kg·m².

At the nominal deployed pose, the constructed model has aggregate COM `[0.087288, 0.037124, 1.035040]` m and the following inertia about that COM in chassis-oriented axes, in kg·m²:

```text
 360.204957   -66.366078   -32.104533
 -66.366078  1001.576957    -2.508902
 -32.104533    -2.508902  1115.296627
```

These values change with arm/mast pose. The POST2 comparison, transformed into FLU, has diagonal moments `[405.09, 571.41, 774.84]` kg·m² and COM height 0.8944 m. MarsLab deliberately does not impose that landing-reference tensor on the deployed articulated geometry: the necessary chassis residual was found physically invalid. Published reference diagonals should not be mistaken for measured full-link tensors or proof of zero cross-products.

### 4.2 Contact and actuator behavior

Contact consists of six wheel cylinders and one chassis box, **1.8 × 1.2 × 0.48 m**. Suspension, arm, mast and antenna geometry has no collider; self-collision is disabled. Consequently, visible arm/terrain or arm/chassis intersection is not prevented by this model.

| Runtime setting | Curiosity value | Interpretation |
| --- | ---: | --- |
| Wheel static / dynamic friction | 0.6 / 0.5 | Contact tuning |
| Wheel restitution | 0 | Contact tuning |
| Chassis angular / linear damping | 12 / 0.5 | Numerical damping |
| Rocker / bogie damping | 75 / 50 | Passive-joint tuning |
| Maximum linear command | 4.0 m/s | Current MarsLab simulation command cap; not a flight capability |
| Maximum commanded yaw rate | 0.04 rad/s | MarsLab command cap |
| Command timeout | 0.5 s | MarsLab safety behavior |
| Odometry slip factors / angular noise | 0 / 0 | Encoder-model defaults; contact can still slip |

The shared [rover controller](../marslab/robots/rover_control.py) converts velocity commands into feasible steering arcs or point turns, with wheel and steering ramps. Wheel acceleration drives use damping 1,000, maximum-force setting 1,000,000 and braking stiffness 50,000; steering uses stiffness 50,000, damping 5,000 and maximum-force setting 100,000. These are simulator gains/caps, not flight torque ratings.

Authored arm force drives hold zero targets with stiffness 100,000, damping 2,000 and maximum force 2,000; mast values are 20,000, 500 and 500. [Drive setup](../marslab/robots/drive_api_setup.py) and [articulation reset](../marslab/runtime/articulation_setup.py) preserve those targets while configuring mobility. The standard velocity-command path does not provide a flight-like arm trajectory controller. The current scenario uses Mars gravity, 3.72 m/s².

JPL's documented maximum wheel linear speed is **0.042 m/s**; the current 4 m/s command cap is approximately 95 times that reference. The cap is a configurable command bound, not a measured achievable speed or newly validated operating envelope. JPL reports 64 Hz encoder sampling and 147,456 ticks/output revolution. MarsLab's default wheel odometry does not reproduce this quantization or flight sampling chain. [JPL mobility paper, Tables 2–3](https://robotics.jpl.nasa.gov/media/documents/ROB-20-0040_R3.pdf).

## 5. Sensors and attachment

### 5.1 Camera inventory

The 17-camera layout matches NASA's inventory: seven mast cameras, MAHLI on the arm, and nine chassis cameras. Parent abbreviations below are **M** = `Body_MastTilt`, **T** = `Body_ArmTurret`, **C** = `Body_Chassis`. All far clips are 200 m. Values are the effective profile's resolution, horizontal FOV and near clip. [NASA's camera inventory](https://science.nasa.gov/resource/seventeen-cameras-on-curiosity/).

| Camera | Parent | Raster (pixels) | Horizontal FOV (°) | Near clip (m) |
| --- | --- | --- | ---: | ---: |
| `navcam_left_a` — primary | M | 1024 × 1024 | 45.27707 | 0.03 |
| `navcam_right_a` | M | 1024 × 1024 | 45.67308 | 0.01 |
| `navcam_left_b` | M | 1024 × 1024 | 45.32356 | 0.03 |
| `navcam_right_b` | M | 1024 × 1024 | 45.47438 | 0.01 |
| `mastcam_left` | M | 1648 × 1200 | 20.22154 | 0.18 |
| `mastcam_right` | M | 1648 × 1200 | 7.00805 | 0.07 |
| `chemcam_rmi` | M | 1024 × 1024 | 1.15712 | 0.05 |
| `mahli` | T | 1648 × 1200 | 32.27295 | 0.01 |
| `hazcam_front_left_a` | C | 1024 × 1024 | 125.71467 | 0.01 |
| `hazcam_front_right_a` | C | 1024 × 1024 | 125.98468 | 0.01 |
| `hazcam_front_left_b` | C | 1024 × 1024 | 125.95418 | 0.01 |
| `hazcam_front_right_b` | C | 1024 × 1024 | 126.11627 | 0.01 |
| `hazcam_rear_left_a` | C | 1024 × 1024 | 126.79688 | 0.03 |
| `hazcam_rear_right_a` | C | 1024 × 1024 | 126.43240 | 0.03 |
| `hazcam_rear_left_b` | C | 1024 × 1024 | 125.29868 | 0.03 |
| `hazcam_rear_right_b` | C | 1024 × 1024 | 126.60257 | 0.03 |
| `mardi` | C | 1648 × 1200 | 72.65307 | 0.05 |

The profile cites each [NASA NAIF instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/). For example, the primary Navcam is located at `[0.115177, 0.214144, 0.081125]` m relative to the mast-tilt link. MAHLI is at `[-0.122249, -0.226238, 0.146453]` m relative to the turret; MARDI is at `[0.761636, 0.648275, 0.701654]` m relative to the chassis. Full translations and degree-valued roll/pitch/yaw rotations are in the profile.

The existing USD cameras are nested beneath their rigid mounts. [Camera mounting code](../marslab/sensors/camera_mount.py) validates their configured relative poses and rejects inconsistent parenting; mast cameras therefore follow both mast joints and MAHLI follows the arm chain. [Sensor-frame code](../marslab/runtime/sensor_frames.py) exports the corresponding ROS frames and optical-axis conversion.

Two distinctions are essential:

1. **Calibration-derived pinhole settings are not full flight calibration.** The [camera spawner](../marslab/sensors/camera_spawner.py) prioritizes configured horizontal FOV, deriving focal length from the current aperture and adjusting vertical aperture to the raster aspect ratio. It does not apply NASA principal-point offsets, separate calibrated horizontal/vertical focal scales or CAHVOR/E distortion. Configured nominal Mastcam focal lengths, 34/100 mm, agree with NASA's inventory, but do not independently determine the runtime projection when FOV is set. CameraInfo describes the simulated camera. The 1648-pixel calibration raster should also be distinguished from an active image crop.
2. **Visual registration and clipping are rendering accommodations.** MAHLI's source extrinsics describe another arm pose. Its active mount is estimated from the visualization's four LED-disk centers, disk normal and LED-pair directions; the original reference calibration and the active replacement are both preserved in [Appendix C](#appendix-c) and [Appendix D](#appendix-d). Selected near planes bypass opaque visual housings: Mastcam-left's 0.18 m clip bypasses housing approximately 0.16 m ahead of its optical center. Clipping also removes real nearby geometry; it is not a flight focus-distance model.

All cameras use the generic RGB rendering path. Detector response, spectral filters, monochrome sensor behavior, exposure, compression and flight redundancy scheduling are not reproduced. Publishing both A/B chains simultaneously represents the full inventory, not an asserted flight operating mode.

### 5.2 IMU, absent modalities and ROS interfaces

The IMU is attached at chassis translation `[0, 0, 0]` with identity orientation and 8 Hz readout. JPL documents an LN-200 at 8 Hz but does not publish its accuracy in the cited table. MarsLab's zero linear/angular noise, zero lever arm at the chassis reference and gravity-inclusive measurement settings are separate idealizations. [IMU implementation](../marslab/sensors/imu_spawner.py), [JPL mobility paper](https://robotics.jpl.nasa.gov/media/documents/ROB-20-0040_R3.pdf).

Both LiDAR configurations are null, and all camera depth outputs are disabled. Topic names remaining in configuration do not create depth images or point clouds. Science instrument metadata does not implement APXS spectra, ChemCam laser spectroscopy, CheMin/SAM chemistry, DAN neutron measurements, RAD radiation or REMS environmental sensing; NASA describes these as distinct science capabilities. [NASA instrument overview](https://science.nasa.gov/mission/msl-curiosity/science-instruments/).

| Interface | Default topic or frame behavior |
| --- | --- |
| Mobility command | `/rover/cmd_vel` |
| Primary camera | `/rover/rgb/image_raw`, `/rover/rgb/camera_info` |
| Other 16 cameras | `/rover/cameras/<name>/image_raw`, `/rover/cameras/<name>/camera_info` |
| IMU | `/rover/imu`, `/rover/imu_noisy`; zero-noise defaults |
| Articulation and clock | `/rover/joint_states`, `/clock` |
| Wheel odometry | `/rover/odom`; configured `odom` → `base_link` TF |

ROS camera parents follow the rigid mounts above rather than a single fixed chassis transform. The primary frames are `camera_link`/`camera_optical_frame`; additional cameras use `<name>_camera_link` and `<name>_camera_optical_frame`. Publication is implemented by the shared [sensor graph builder](../marslab/ros2_bridge/sensor_graph_builder.py).

## 6. Verification and practical limits

For this report, read-only configuration composition, URDF parsing and OpenUSD inspection confirmed 22 bodies, 21 URDF joints, 73 USD meshes, seven collision shapes and 17 configured/authored cameras. URDF mass sums to 899.18 kg; USD sums to 899.1799926757812 kg because of floating-point storage. No fresh Isaac Sim or ROS session was launched.

The recorded construction checks found positive principal inertias, satisfaction of principal-moment triangle inequalities and no housing blockage in a historical 81-ray MAHLI aperture check. The [repository README](../README.md) also records dated runtime/articulation checks. Those records are supporting historical evidence, not fresh measurements or proof of complete workspace clearance.

The model is suitable for studying rover mobility integration, articulated camera frames and rendered perception within the stated approximations. Its inferred mass distributions, simplified contacts, missing manipulation collisions, ideal sensors and absent science measurement models prevent treating it as a validated predictor of flight loads, terrain interaction, arm safety or instrument performance.

## 7. Principal references

- [NASA Curiosity mission](https://science.nasa.gov/mission/msl-curiosity/) and [2012 landing press kit](https://www.jpl.nasa.gov/news/press_kits/MSLLanding.pdf): mission scale and hardware context.
- [NASA POST2 ground-contact model](https://ntrs.nasa.gov/api/citations/20140003460/downloads/20140003460.pdf): landing-reference mass, inertia and contact geometry.
- [JPL mobility engineering paper](https://robotics.jpl.nasa.gov/media/documents/ROB-20-0040_R3.pdf): mobility architecture, actuator/encoder properties and IMU sampling.
- [JPL arm kinematics paper](https://www-robotics.jpl.nasa.gov/media/documents/rankin-2540-arm-kinematics-2021-0102.pdf): arm architecture, dimensions and mass totals.
- [NASA's 17-camera diagram](https://science.nasa.gov/resource/seventeen-cameras-on-curiosity/) and [NAIF MSL kernels](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/): camera inventory and calibration/frame evidence.
- [Runtime profile](../configs/robots/curiosity.yaml) and the technical appendices below: implementation-specific allocations, transforms, calibration evidence and approximations.

<a id="appendix-a"></a>

## Appendix A. Construction frames and kinematic reference

These appendices consolidate the retained model-construction and sensor reference data. Numerical tables preserve stored computational precision; their decimal length does not imply equivalent flight accuracy. All positions are in metres, masses in kilograms and inertias in kg·m² unless stated otherwise. Matrices are written row by row; multiplication acts on column vectors. The model is authored by MarsLab from the Curiosity visual-source family. Sensor references were collected on 22 October 2026 and describe historical calibration configurations, not instrument health in 2026.

Navigation: [frames and joints](#appendix-a), [complete mass properties](#appendix-b), [17 camera calibration records](#appendix-c), [visual registration and clipping evidence](#appendix-d), [engineering/science interfaces](#appendix-e), [84 structural reference locations](#appendix-f).

<a id="a-frames"></a>

### A.1 Distinct coordinate conversions

The visualization conversion is `p_ground_FLU = R_visual p_Blender + t_visual`, evaluated at source frame 180. It is distinct from the NASA navigation-frame conversion used for sensor data. The output origin is nominal ground between the middle wheels; the model's ground-to-chassis translation is zero.

| Quantity | Stored value |
| --- | --- |
| Visual-source rotation R_visual | `[0.0, -1.0, 0.0]`<br>`[1.0, 0.0, 0.0]`<br>`[0.0, 0.0, 1.0]` |
| Visual-source translation t_visual (m) | `[0.08899986743927002, 0.0023094316323598227, 0.007220959911743791]` |
| NASA navigation-to-FLU rotation R_nav | `[1, 0, 0]`<br>`[0, -1, 0]`<br>`[0, 0, -1]` |
| Ground-to-chassis translation (m) | `[0, 0, 0]` |

The sensor frame is called `ground_flu`, with X forward, Y left and Z up. Its NASA coordinate reference is [PLACES PDS SIS, section 2.1.1](https://planetarydata.jpl.nasa.gov/w10n/msl/msl_places/document/PLACES_PDS_SIS.pdf). For structural locations centered on the rover mechanical origin (ID −76000), add `[0.09002, 0, -1.1205]` m in source axes before applying `R_nav`; ID −76 already denotes the navigation origin. Entries in moving instrument/arm frames require their parent transforms and are not independently global positions. [Appendix F](#appendix-f) preserves those distinctions.

<a id="a-wheels"></a>

### A.2 Mobility geometry

| Parameter | Value |
| --- | --- |
| Wheel radius (m) | 0.25 |
| Corner wheelbase (m) | 2.26 |
| Steering-axle midpoint X offset (m) | 0.05399986743926999 |
| Corner track (m) | 2.125 |
| Middle-wheel track (m) | 2.3825056850910187 |
| Invert steering sign | false |
| Ground-to-chassis translation (m) | `[0, 0, 0]` |

| Wheel link | Nominal center in ground FLU (m) |
| --- | --- |
| Body_WheelLeftFront | `[1.18399986743927, 1.0625, 0.25]` |
| Body_WheelLeftMiddle | `[0.0, 1.1912528425455093, 0.25]` |
| Body_WheelLeftRear | `[-1.07600013256073, 1.0625, 0.25]` |
| Body_WheelRightFront | `[1.18399986743927, -1.0625, 0.25]` |
| Body_WheelRightMiddle | `[0.0, -1.1912528425455093, 0.25]` |
| Body_WheelRightRear | `[-1.07600013256073, -1.0625, 0.25]` |

Corner contacts use the NASA POST2 wheelbase/track reference; middle-wheel locations come from the visualization. Small visual asymmetries were symmetrized for steering, and the wheel visual radii were adjusted to 0.25 m while retaining their source widths.

<a id="a-joints"></a>

### A.3 Added mast and arm joints

All seven added joint neutral coordinates are zero at the deployed source pose. Axes below follow the right-hand rule in each neutral joint frame. Pivots are nominal ground-FLU positions, not URDF parent-relative translations. Suggested smoke excursions are small historical test amplitudes, not collision-safe or flight-qualified workspace limits.

| Joint | Parent → child | Axis | Limits (rad) | Neutral / smoke amplitude (rad) | Ground-FLU pivot (m) |
| --- | --- | --- | --- | --- | --- |
| MAST_PAN | Body_Chassis → Body_MastPan | `[0, 0, 1]` | `[-3.141592653589793, 3.141592653589793]` | `[0, 0.1]` | `[0.8044, -0.5594, 1.9061]` |
| MAST_TILT | Body_MastPan → Body_MastTilt | `[0, 1, 0]` | `[-1.2, 1.2]` | `[0, 0.1]` | `[0.8044, -0.5594, 1.9061]` |
| ARM_SHOULDER_AZIMUTH | Body_Chassis → Body_ArmShoulderAzimuth | `[0, 0, 1]` | `[-1.0, 1.0]` | `[0, 0.05]` | `[1.2018507719039917, 0.4538093109925588, 1.005270993957917]` |
| ARM_SHOULDER_ELEVATION | Body_ArmShoulderAzimuth → Body_ArmShoulderElevation | `[0, 1, 0]` | `[-1.0, 1.0]` | `[0, 0.05]` | `[1.362350583076477, 0.44996662934621173, 0.8396256330112616]` |
| ARM_ELBOW | Body_ArmShoulderElevation → Body_ArmElbow | `[0, 1, 0]` | `[-1.0, 1.0]` | `[0, 0.05]` | `[2.187127470970154, 0.5204654236634573, 0.840207493553559]` |
| ARM_WRIST | Body_ArmElbow → Body_ArmWrist | `[0, 1, 0]` | `[-1.0, 1.0]` | `[0, 0.05]` | `[2.185860514640808, 0.3612095018227895, 1.622873521099488]` |
| ARM_TURRET | Body_ArmWrist → Body_ArmTurret | `[0, 0, 1]` | `[-3.141592653589793, 3.141592653589793]` | `[0, 0.05]` | `[2.084593176841736, 0.4355072279771169, 1.7668529512981574]` |

The complete articulation has 22 rigid bodies and 21 joints, including the coupled rocker pair. Arm geometry was redistributed between links without changing the neutral world-space vertices. The source rig and NASA frame/structure references support the selected axis families; segment lengths differ from the structural reference by less than 4 mm, while the shoulder-elevation axis registration differs by about 16 mm. Lower-mast deployment and antenna hardware remain fixed. No new manipulation colliders were added. The mast mass is estimated at 20 kg. The arm mass anchor is 67 kg of mechanism plus 24 kg of turret instruments, 91 kg total, from [JPL Table 2](https://www-robotics.jpl.nasa.gov/media/documents/rankin-2540-arm-kinematics-2021-0102.pdf). Its 20/18/15/8/30 kg link partition is estimated; the last 30 kg includes an estimated 6 kg mechanism and the published 24 kg instruments.

Space ROS was consulted only for segmentation/axis comparison, using the [pinned reference](https://github.com/space-ros/simulation/tree/13226b067d921ca88f40cd643a7b3ce4ae8de903/models/curiosity_path/urdf); no source code, meshes or mass properties from that package were incorporated.

<a id="a-selection"></a>

### A.4 Geometry selection and attachment rules

The conversion keeps all 73 physical source objects and 48,384 triangles once each, including hidden-render physical arm segments. Exclusion is based on function: non-mesh camera/light helpers, pivot-material rig helpers, named camera-transform helpers, and rendering-only shadow planes are omitted. Mission cameras are authored from calibration evidence instead of importing those helpers.

| Excluded category | Object count |
| --- | --- |
| Non-mesh source object; mission sensors are authored from calibration. | 11 |
| Source pivot-material rig helper. | 12 |
| Named camera transform helper; calibrated camera authored separately. | 9 |
| Source rendering-only shadow plane. | 1 |

Visual attachments follow the mechanical segmentation: wheel meshes belong to their six wheel bodies; steering carriers, rockers and bogies belong to their corresponding links. Successive arm segments belong to the five arm links. APXS, the drill/sample-handling assembly, dust-removal tool, MAHLI and its four LEDs/lens cover belong to the turret. The visual MAHLI calibration-target object is assigned to the shoulder-azimuth link, an attachment exception that should not be generalized to flight target locations. The upper mast segment, Mastcam/Navcam housing and ChemCam belong to mast tilt; the intermediate mast segment belongs to mast pan. Lower mast, fixed antennas, main chassis/payload, RTG, radiators, Hazcams, MARDI and fixed science hardware remain on the chassis.

| Rigid link | Assigned physical source meshes |
| --- | --- |
| Body_Chassis | 29 |
| Body_ArmTurret | 12 |
| Body_ArmShoulderAzimuth | 2 |
| Body_ArmShoulderElevation | 1 |
| Body_ArmElbow | 1 |
| Body_ArmWrist | 1 |
| Body_MastTilt | 4 |
| Body_MastPan | 1 |
| Body_BogieLeft | 1 |
| Body_BogieRight | 1 |
| Body_RockerLeft | 5 |
| Body_RockerRight | 5 |
| Body_SteerLeftRear | 1 |
| Body_SteerRightRear | 1 |
| Body_SteerLeftFront | 1 |
| Body_SteerRightFront | 1 |
| Body_WheelLeftFront | 1 |
| Body_WheelRightFront | 1 |
| Body_WheelLeftMiddle | 1 |
| Body_WheelRightMiddle | 1 |
| Body_WheelLeftRear | 1 |
| Body_WheelRightRear | 1 |

The supplied USD/URDF/meshes/textures are the runtime products. Blender sources and a distributed automatic regeneration workflow are absent. Development conversion and inspection utilities reside under `tmp/`; runtime does not execute them. Detailed source-object name inventories and integrity hashes are intentionally omitted here because selection/attachment rules and the pinned upstream source establish the technical lineage.

<a id="appendix-b"></a>

## Appendix B. Complete mass-property record

For each link, `origin` is its nominal ground-FLU origin. `COM_local` is measured from that origin in link coordinates. The inertia matrix is about that local COM, expressed in the neutral link axes; principal moments are the stored eigenvalues. These origin vectors must not be substituted directly for parent-relative URDF joint origins. Wheels use solid-cylinder inertia. Other links use a uniform thin shell over their assigned visual triangles, normalized to the allocated mass. Closed/watertight meshes are not required, and internal flight structure is not reconstructed. All stored moments were recorded as positive and satisfying the principal-moment triangle inequalities.

<a id="mass-body-chassis"></a>

### Body_Chassis

| Property | Value |
| --- | --- |
| Mass (kg) | 674.18 |
| Origin in ground FLU (m) | `[0.0, 0.0, 0.0]` |
| COM_local (m) | `[-0.16764966599547412, 0.007110338592623133, 1.0482206523420845]` |
| Full inertia tensor (kg·m²) | `[143.81752793813246, -4.770047877834285, 45.929189563103954]`<br>`[-4.7700478778342825, 479.8472694093037, 2.514853397025263]`<br>`[45.929189563103954, 2.5148533970252647, 549.5593696282122]` |
| Principal moments (kg·m²) | `[138.6095493183448, 479.86929374226355, 554.74532391504]` |

<a id="mass-body-rockerleft"></a>

### Body_RockerLeft

| Property | Value |
| --- | --- |
| Mass (kg) | 18.0 |
| Origin in ground FLU (m) | `[0.300496906042099, 0.7972160478432974, 0.8893821003536383]` |
| COM_local (m) | `[0.08048355185376865, 0.02526595182764957, -0.050878368513468275]` |
| Full inertia tensor (kg·m²) | `[0.5683246135085394, -0.6807878601658777, 0.09516019964899924]`<br>`[-0.6807878601658777, 3.674705602487132, 0.1793809514590876]`<br>`[0.09516019964899924, 0.1793809514590876, 3.698992679663035]` |
| Principal moments (kg·m²) | `[0.42051505318848253, 3.594865173684693, 3.926642668785529]` |

<a id="mass-body-bogieleft"></a>

### Body_BogieLeft

| Property | Value |
| --- | --- |
| Mass (kg) | 12.0 |
| Origin in ground FLU (m) | `[-0.4510035514831543, 0.9895259042580923, 0.6505558254818121]` |
| COM_local (m) | `[-0.06340647059555937, -0.035191558856244254, -0.05657517368340015]` |
| Full inertia tensor (kg·m²) | `[0.33881203549338657, 0.19185993094430875, 0.5653779070843015]`<br>`[0.19185993094430875, 1.915508293693806, -0.02460075131414685]`<br>`[0.5653779070843015, -0.02460075131414685, 1.7439947189456513]` |
| Principal moments (kg·m²) | `[0.11965115247901122, 1.8988028960627026, 1.9798609995911287]` |

<a id="mass-body-wheelleftfront"></a>

### Body_WheelLeftFront

| Property | Value |
| --- | --- |
| Mass (kg) | 7.0 |
| Origin in ground FLU (m) | `[1.18399986743927, 1.0625, 0.25]` |
| COM_local (m) | `[0.0, 0.0, 0.0]` |
| Full inertia tensor (kg·m²) | `[0.20026499576806808, 0.0, 0.0]`<br>`[0.0, 0.21875, 0.0]`<br>`[0.0, 0.0, 0.20026499576806808]` |
| Principal moments (kg·m²) | `[0.20026499576806808, 0.20026499576806808, 0.21875]` |

<a id="mass-body-steerleftfront"></a>

### Body_SteerLeftFront

| Property | Value |
| --- | --- |
| Mass (kg) | 3.0 |
| Origin in ground FLU (m) | `[1.18399986743927, 1.0625, 0.6472190382579962]` |
| COM_local (m) | `[-0.004761117614217714, -0.19824996795013394, -0.1382170877497031]` |
| Full inertia tensor (kg·m²) | `[0.09593619042258483, -0.0010311885285430034, -2.4735212323379052e-05]`<br>`[-0.001031188528541671, 0.0400426141705289, -0.0199420722977528]`<br>`[-2.4735212323379052e-05, -0.0199420722977528, 0.0679853872406263]` |
| Principal moments (kg·m²) | `[0.0296518109603472, 0.07835153476925238, 0.09596084610414048]` |

<a id="mass-body-wheelleftmiddle"></a>

### Body_WheelLeftMiddle

| Property | Value |
| --- | --- |
| Mass (kg) | 7.0 |
| Origin in ground FLU (m) | `[0.0, 1.1912528425455093, 0.25]` |
| COM_local (m) | `[0.0, 0.0, 0.0]` |
| Full inertia tensor (kg·m²) | `[0.20026499576806808, 0.0, 0.0]`<br>`[0.0, 0.21875, 0.0]`<br>`[0.0, 0.0, 0.20026499576806808]` |
| Principal moments (kg·m²) | `[0.20026499576806808, 0.20026499576806808, 0.21875]` |

<a id="mass-body-wheelleftrear"></a>

### Body_WheelLeftRear

| Property | Value |
| --- | --- |
| Mass (kg) | 7.0 |
| Origin in ground FLU (m) | `[-1.07600013256073, 1.0625, 0.25]` |
| COM_local (m) | `[0.0, 0.0, 0.0]` |
| Full inertia tensor (kg·m²) | `[0.20026494087007496, 0.0, 0.0]`<br>`[0.0, 0.21875, 0.0]`<br>`[0.0, 0.0, 0.20026494087007496]` |
| Principal moments (kg·m²) | `[0.20026494087007496, 0.20026494087007496, 0.21875]` |

<a id="mass-body-steerleftrear"></a>

### Body_SteerLeftRear

| Property | Value |
| --- | --- |
| Mass (kg) | 3.0 |
| Origin in ground FLU (m) | `[-1.07600013256073, 1.0625, 0.6499555471042792]` |
| COM_local (m) | `[0.0009066254207159563, -0.16639594677897485, -0.11938399200453143]` |
| Full inertia tensor (kg·m²) | `[0.09326494781703104, -6.790855850613564e-05, 0.00010100453111427932]`<br>`[-6.790855850613564e-05, 0.046543594419712175, -0.015299193017012713]`<br>`[0.00010100453111427932, -0.015299193017012713, 0.05949525811482259]` |
| Principal moments (kg·m²) | `[0.03640612721257, 0.0696320985208436, 0.09326557461815224]` |

<a id="mass-body-rockerright"></a>

### Body_RockerRight

| Property | Value |
| --- | --- |
| Mass (kg) | 18.0 |
| Origin in ground FLU (m) | `[0.30300000309944153, -0.7968534330526987, 0.8921190264324347]` |
| COM_local (m) | `[0.07899141292627115, -0.02420161675901622, -0.052563971884615146]` |
| Full inertia tensor (kg·m²) | `[0.5716937979661039, 0.6838397560030319, 0.0881302405252905]`<br>`[0.6838397560030319, 3.6870007118855765, -0.1798788588043294]`<br>`[0.0881302405252905, -0.1798788588043294, 3.7194835524044]` |
| Principal moments (kg·m²) | `[0.4235794291143424, 3.610736313412408, 3.943862319729329]` |

<a id="mass-body-bogieright"></a>

### Body_BogieRight

| Property | Value |
| --- | --- |
| Mass (kg) | 12.0 |
| Origin in ground FLU (m) | `[-0.4510037899017334, -0.9897101024786631, 0.6505583288768927]` |
| COM_local (m) | `[-0.06340657122553484, 0.035194051589704456, -0.056577704047892086]` |
| Full inertia tensor (kg·m²) | `[0.3388129057385565, -0.19185998955293204, 0.5653789815367092]`<br>`[-0.19185998955293204, 1.915508933829966, 0.024600875370823783]`<br>`[0.5653789815367092, 0.02460087537082245, 1.7439945746345356]` |
| Principal moments (kg·m²) | `[0.11965122844324942, 1.8988035181369194, 1.9798616676228893]` |

<a id="mass-body-wheelrightfront"></a>

### Body_WheelRightFront

| Property | Value |
| --- | --- |
| Mass (kg) | 7.0 |
| Origin in ground FLU (m) | `[1.18399986743927, -1.0625, 0.25]` |
| COM_local (m) | `[0.0, 0.0, 0.0]` |
| Full inertia tensor (kg·m²) | `[0.20026491342108463, 0.0, 0.0]`<br>`[0.0, 0.21875, 0.0]`<br>`[0.0, 0.0, 0.20026491342108463]` |
| Principal moments (kg·m²) | `[0.20026491342108463, 0.20026491342108463, 0.21875]` |

<a id="mass-body-steerrightfront"></a>

### Body_SteerRightFront

| Property | Value |
| --- | --- |
| Mass (kg) | 3.0 |
| Origin in ground FLU (m) | `[1.18399986743927, -1.0625, 0.6499560835460821]` |
| COM_local (m) | `[-0.0022581412850426474, 0.1986128843048861, -0.13821689345498467]` |
| Full inertia tensor (kg·m²) | `[0.09593610977199263, 0.0010311553032611442, -2.4713372924090038e-05]`<br>`[0.0010311553032611442, 0.04004258946830963, 0.019941984916029443]`<br>`[-2.4713372924423105e-05, 0.019941984916029443, 0.06798533416679531]` |
| Principal moments (kg·m²) | `[0.029651852849182335, 0.07835141602979236, 0.09596076452812284]` |

<a id="mass-body-wheelrightmiddle"></a>

### Body_WheelRightMiddle

| Property | Value |
| --- | --- |
| Mass (kg) | 7.0 |
| Origin in ground FLU (m) | `[0.0, -1.1912528425455093, 0.25]` |
| COM_local (m) | `[0.0, 0.0, 0.0]` |
| Full inertia tensor (kg·m²) | `[0.20026491342108463, 0.0, 0.0]`<br>`[0.0, 0.21875, 0.0]`<br>`[0.0, 0.0, 0.20026491342108463]` |
| Principal moments (kg·m²) | `[0.20026491342108463, 0.20026491342108463, 0.21875]` |

<a id="mass-body-wheelrightrear"></a>

### Body_WheelRightRear

| Property | Value |
| --- | --- |
| Mass (kg) | 7.0 |
| Origin in ground FLU (m) | `[-1.07600013256073, -1.0625, 0.25]` |
| COM_local (m) | `[0.0, 0.0, 0.0]` |
| Full inertia tensor (kg·m²) | `[0.20026494087007496, 0.0, 0.0]`<br>`[0.0, 0.21875, 0.0]`<br>`[0.0, 0.0, 0.20026494087007496]` |
| Principal moments (kg·m²) | `[0.20026494087007496, 0.20026494087007496, 0.21875]` |

<a id="mass-body-steerrightrear"></a>

### Body_SteerRightRear

| Property | Value |
| --- | --- |
| Mass (kg) | 3.0 |
| Origin in ground FLU (m) | `[-1.07600013256073, -1.0625, 0.6499557259182135]` |
| COM_local (m) | `[0.0005148558557706018, 0.16621431113961727, -0.11938403434958211]` |
| Full inertia tensor (kg·m²) | `[0.09326501846300411, 0.00015961799381436492, -1.8002084367529925e-05]`<br>`[0.00015961799381436492, 0.04654289049519017, 0.015299226918185083]`<br>`[-1.8002084367529925e-05, 0.015299226918184416, 0.059494680111739195]` |
| Principal moments (kg·m²) | `[0.03640507084856785, 0.06963191363765578, 0.09326560458370982]` |

<a id="mass-body-mastpan"></a>

### Body_MastPan

| Property | Value |
| --- | --- |
| Mass (kg) | 4.0 |
| Origin in ground FLU (m) | `[0.8044, -0.5594, 1.9061]` |
| COM_local (m) | `[-0.0014122680154462497, 0.008942824098768565, -0.13813981254587704]` |
| Full inertia tensor (kg·m²) | `[0.04055844135326048, -1.0414041422546205e-06, -2.5833331251945424e-06]`<br>`[-1.0414041422546205e-06, 0.037586180908417255, 0.0022726258818446254]`<br>`[-2.5833331251945424e-06, 0.0022726258818441814, 0.029566200353587924]` |
| Principal moments (kg·m²) | `[0.028966976556205296, 0.038185403106748, 0.04055844295231238]` |

<a id="mass-body-masttilt"></a>

### Body_MastTilt

| Property | Value |
| --- | --- |
| Mass (kg) | 16.0 |
| Origin in ground FLU (m) | `[0.8044, -0.5594, 1.9061]` |
| COM_local (m) | `[0.0012532958665057992, 0.07574260325028143, 0.10586705995556756]` |
| Full inertia tensor (kg·m²) | `[0.6092459883637527, 0.0018104398205016636, 0.012904092733812433]`<br>`[0.0018104398205016636, 0.311481224246851, 0.07151630234597306]`<br>`[0.012904092733812433, 0.07151630234597306, 0.5233713569796126]` |
| Principal moments (kg·m²) | `[0.2895893392331071, 0.5427597791830867, 0.6117494511740225]` |

<a id="mass-body-armshoulderazimuth"></a>

### Body_ArmShoulderAzimuth

| Property | Value |
| --- | --- |
| Mass (kg) | 20.0 |
| Origin in ground FLU (m) | `[1.2018507719039917, 0.4538093109925588, 1.005270993957917]` |
| COM_local (m) | `[0.08415454125034172, -0.02299595732012094, -0.1611482121369877]` |
| Full inertia tensor (kg·m²) | `[0.1895605400973449, 0.006087154358822566, -0.007340481431414858]`<br>`[0.006087154358822566, 0.22397455431623525, -0.004189701219463604]`<br>`[-0.007340481431414858, -0.004189701219463604, 0.2566030313881479]` |
| Principal moments (kg·m²) | `[0.1878887323621441, 0.2241617960252424, 0.2580875974143417]` |

<a id="mass-body-armshoulderelevation"></a>

### Body_ArmShoulderElevation

| Property | Value |
| --- | --- |
| Mass (kg) | 18.0 |
| Origin in ground FLU (m) | `[1.362350583076477, 0.44996662934621173, 0.8396256330112616]` |
| COM_local (m) | `[0.546290811183282, -0.1423651520753081, 0.018912689157760343]` |
| Full inertia tensor (kg·m²) | `[0.20319573547946881, -0.258275303004309, 0.044723927665581975]`<br>`[-0.258275303004309, 1.4851890968858321, 0.016926410255817093]`<br>`[0.044723927665581975, 0.016926410255817093, 1.6220690200705008]` |
| Principal moments (kg·m²) | `[0.15160820348663526, 1.534529437350257, 1.6243162115989103]` |

<a id="mass-body-armelbow"></a>

### Body_ArmElbow

| Property | Value |
| --- | --- |
| Mass (kg) | 15.0 |
| Origin in ground FLU (m) | `[2.187127470970154, 0.5204654236634573, 0.840207493553559]` |
| COM_local (m) | `[0.01928777849761154, -0.07377255960993784, 0.4656545154368409]` |
| Full inertia tensor (kg·m²) | `[1.2026413692197575, -0.0012035190526321626, 0.03486618858215662]`<br>`[-0.0012035190526321626, 1.1933693765921782, 0.026234919431621373]`<br>`[0.03486618858215662, 0.026234919431621373, 0.06368338686540922]` |
| Principal moments (kg·m²) | `[0.062007554533104574, 1.1939623820040783, 1.2037241961401621]` |

<a id="mass-body-armwrist"></a>

### Body_ArmWrist

| Property | Value |
| --- | --- |
| Mass (kg) | 8.0 |
| Origin in ground FLU (m) | `[2.185860514640808, 0.3612095018227895, 1.622873521099488]` |
| COM_local (m) | `[-0.13276056528664482, 0.06698713647799759, 0.10479457875899034]` |
| Full inertia tensor (kg·m²) | `[0.07776514755526076, -0.0003013441297383679, -0.008997353662255847]`<br>`[-0.0003013441297383679, 0.08578076610406882, 0.002972625516743932]`<br>`[-0.0089973536622594, 0.002972625516743932, 0.06514735086925594]` |
| Principal moments (kg·m²) | `[0.06022207712347599, 0.08181426819708033, 0.08665691920802913]` |

<a id="mass-body-armturret"></a>

### Body_ArmTurret

| Property | Value |
| --- | --- |
| Mass (kg) | 30.0 |
| Origin in ground FLU (m) | `[2.084593176841736, 0.4355072279771169, 1.7668529512981574]` |
| COM_local (m) | `[-0.008472817918888875, 0.03863812293194824, 0.15923120486153763]` |
| Full inertia tensor (kg·m²) | `[0.6521397721172759, -0.07811752607488343, 0.0010194001762053873]`<br>`[-0.07811752607488343, 0.5282298069130009, -0.03699989202756493]`<br>`[0.0010194001762053873, -0.03699989202756493, 1.007827237514066]` |
| Principal moments (kg·m²) | `[0.4883954969914922, 0.6889952750948665, 1.0108060444579845]` |

<a id="b-aggregate"></a>

### B.1 Aggregate and landing-reference comparison

| Quantity | Constructed articulated model at neutral pose |
| --- | --- |
| Total mass (kg) | 899.18 |
| Ground-FLU COM (m) | `[0.08728785426954584, 0.03712356786555233, 1.035039596960991]` |
| Full inertia about aggregate COM (kg·m²) | `[360.204957122644, -66.36607769437897, -32.10453276783466]`<br>`[-66.36607769437896, 1001.5769574351837, -2.5089020827869515]`<br>`[-32.10453276783466, -2.5089020827869533, 1115.2966269509345]` |

The horizontal COM projection lies inside the nominal wheel support polygon. Aggregate COM and inertia change with arm/mast configuration. The comparison-only landing target is:

| Landing target in FLU | Value |
| --- | --- |
| Mass (kg) | 899.18 |
| COM (m) | `[0.08899986743927002, 0.0, 0.8944]` |
| Reference inertia (kg·m²) | `[405.09, 0.0, 0.0]`<br>`[0.0, 571.41, 0.0]`<br>`[0.0, 0.0, 774.84]` |

The earlier landing-reference aggregate evaluates to the same target within numerical roundoff: its transverse COM component is approximately 1.98×10⁻¹⁸ m and off-diagonal tensor residuals are approximately 10⁻¹⁵ kg·m². Those residuals have no physical significance. This target is comparison data only: imposing it on the deployed 91 kg arm would require a chassis residual that violates physical inertia inequalities. The final chassis therefore uses the geometry-derived thin shell, not a residual fit to that reference.

The original [NASA POST2 Table 1](https://ntrs.nasa.gov/api/citations/20140003460/downloads/20140003460.pdf) values, before conversion to FLU, are preserved below. The paper models touchdown with one rigid body. Equal X coordinates at the four contacts identify its vertical axis, while Z is longitudinal; this is a different convention from ROVER_NAV. The FLU diagonal comparison reorders the original diagonal. Products of inertia were not published: zeros in the comparison matrix are a representational assumption, not measured cross-products.

| Original POST2 quantity | Value |
| --- | --- |
| Mass (kg) | 899.18 |
| Diagonal inertia in source body axes (kg·m²) | `[774.84, 571.41, 405.09]` |
| Source-body COM (m) | `[0, 0, 0]` |
| Corner contact 1, source-body axes (m) | `[0.8944, -1.0625, 1.165]` |
| Corner contact 2, source-body axes (m) | `[0.8944, -1.0625, -1.095]` |
| Corner contact 3, source-body axes (m) | `[0.8944, 1.0625, 1.165]` |
| Corner contact 4, source-body axes (m) | `[0.8944, 1.0625, -1.095]` |

<a id="appendix-c"></a>

## Appendix C. Camera calibration and current mount records

Each camera card separates upstream calibration from the active mount. Calibration ground-FLU positions/rotations describe the historical reference pose; the active parent-relative transform is the one used by the current articulated model. For MAHLI these poses intentionally differ. Structural-kernel positions in Appendix F are another reference product and are not interchangeable with IK optical centers.

`R_USD` maps USD camera-local axes to the stated parent/reference axes: USD looks along −Z with +Y up. The stored `USD RPY` uses that convention. The YAML `camera-link RPY` instead describes a forward-left-up camera-link frame, so the two angle triples must not be substituted for one another. Angles in pose tables are degrees. The rotation matrix is the unambiguous orientation record.

The source coefficient symbols preserve the kernel's notation. C/A/H/V form the CAHV model; O/R and, where present, E extend it. POS/QUAT retain the original reference pose. **CAHVOR_QUAT is engineering scalar-last `(s1, s2, s3, c)`**, as explicitly specified in the [MSL Mastcam-left kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_ml_20120731_c03.ti); it is not SPICE scalar-first order. HS/VS are the retained focal scales, HC/VC the principal-point coordinates, DIMS the calibration raster and THETA the source model's angular parameter. Raw values remain in source coordinates; they have not been silently converted to FLU.

FOV_BOUNDARY contains eight ordered direction triples in the kernel's FOV frame, preserving the original corner/mid-edge ordering. IFOV_HORIZONTAL/VERTICAL are degrees per pixel. The source BORESIGHT_PIXEL is kept separately from HC/VC because they can differ. An `absent` coefficient means the source model does not supply it, not a zero coefficient. Hazcams use `CAHVORE3,0.37`, ChemCam RMI uses `CAHV`, and the remaining cameras use `CAHVOR`. The unusual ChemCam principal point outside the raster is retained as reference data; it is not used as the runtime pinhole center.

All cards are imaging sensors. Rendering uses the central ray of the linear CAHV portion and a horizontal-FOV-controlled pinhole approximation. It does not reproduce radial/fisheye distortion, full calibrated principal-point/skew/asymmetric focal scales, detector response or filters. Original coefficients are preserved for interpretation and future work; their presence does not mean the current renderer evaluates them.

<a id="camera-mastcam-left"></a>

### C.1 mastcam_left

**NAIF frame:** `MSL_MASTCAM_LEFT`. **Model:** `CAHVOR`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_ml_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_3003_FILTER_0_FOCUS_02315-MCAML-FLIGHT.cahvor`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1648, 1200] / [1600, 1200] |
| Nominal focal length / pixel pitch (mm) | `[34.0, 0.0074]` |
| fx / fy (pixels) | `[4645.242086, 4644.882626]` |
| Principal point (pixels) | `[829.187822, 601.335144]` |
| Reference horizontal / vertical FOV (degrees) | `[20.2215366, 14.750050040000001]` |

**Reference configuration:** `mast_reference_pose`. CAHVOR calibration mast pose near forward/level; use source reference POS/QUAT for articulation.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[0.767151, -0.433709, 1.971648]` |
| Calibration reference R_USD → ground FLU | `[-0.023864439246027616, 0.006175847780580189, -0.9996961275525996]`<br>`[-0.9996962387833459, -0.006306875347892701, 0.023825479759652844]`<br>`[-0.006157816325950378, 0.9999610403548417, 0.006324481841116543]` |
| Calibration reference USD RPY (degrees) | `[89.63762459657625, 0.35281911625815005, -91.3674873995338]` |
| Calibration central-ray boresight in FLU | `[0.9996961275525996, -0.023825479759652844, -0.006324481841116543]` |
| Current rigid parent | Body_MastTilt |
| Current parent-relative translation (m) | `[-0.03724899999999998, 0.125691, 0.06554800000000016]` |
| Current R_USD → rigid parent | `[-0.02386443924602788, 0.006175847780580002, -0.9996961275525997]`<br>`[-0.9996962387833459, -0.006306875347892982, 0.023825479759653156]`<br>`[-0.0061578163259505825, 0.9999610403548418, 0.006324481841116336]` |
| Current YAML camera-link RPY (degrees) | `[0.35282617277741074, 0.36236853286456155, -1.3652559286057564]` |
| Current raster (pixels) | `[1648, 1200]` |
| Current horizontal FOV (degrees) | 20.2215366 |
| Current near/far clipping (m) | `[0.18, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[0.767151, 0.433709, -1.971648]` |
| CAHVOR_A | `[0.999664, 0.025047, 0.006727]` |
| CAHVOR_H | `[712.373106, 4664.465028, 33.182389]` |
| CAHVOR_V | `[570.612488, -14.279011, 4648.733195]` |
| CAHVOR_O | `[0.999627, 0.026908, 0.004759]` |
| CAHVOR_R | `[-0.000151, -0.139189, -1.250336]` |
| CAHVOR_E | absent |
| CAHVOR_POS | `[0.80436, 0.55942, -1.90608]` |
| CAHVOR_QUAT | `[1e-05, -0.00325, -0.00104, 0.99999]` |
| CAHVOR_DIMS | `[1648.0, 1200.0]` |
| CAHVOR_HS | `[4645.242086]` |
| CAHVOR_VS | `[4644.882626]` |
| CAHVOR_HC | `[829.187822]` |
| CAHVOR_VC | `[601.335144]` |
| CAHVOR_THETA | `[-1.571004]` |
| FOV_BOUNDARY | `[0.17483767, 0.12730492, 0.97633255]`<br>`[-0.0, 0.12834274, 0.99172987]`<br>`[-0.17476887, 0.12719345, 0.9763594]`<br>`[-0.17553059, -5.566e-05, 0.98447398]`<br>`[-0.17480715, -0.12735688, 0.97633124]`<br>`[1.62e-05, -0.12838394, 0.99172454]`<br>`[0.1749107, -0.12728511, 0.97632205]`<br>`[0.17557293, 3.78e-05, 0.98446643]` |
| PIXEL_SAMPLES | `[1648.0]` |
| PIXEL_LINES | `[1200.0]` |
| PIXEL_SIZE | `[0.0074]` |
| FOCAL_LENGTH | `[34.0]` |
| IFOV_HORIZONTAL | `[0.0122778]` |
| IFOV_VERTICAL | `[0.01230196]` |
| BORESIGHT_PIXEL | `[829.18782212, 601.33514402]` |

<a id="camera-mastcam-right"></a>

### C.2 mastcam_right

**NAIF frame:** `MSL_MASTCAM_RIGHT`. **Model:** `CAHVOR`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_mr_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_3004_FILTER_0_FOCUS_02702-MCAMR-FLIGHT.cahvor`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1648, 1200] / [1600, 1200] |
| Nominal focal length / pixel pitch (mm) | `[100.0, 0.0074]` |
| fx / fy (pixels) | `[13376.370999, 13370.635765]` |
| Principal point (pixels) | `[859.446513, 534.294115]` |
| Reference horizontal / vertical FOV (degrees) | `[7.00805088, 5.11956214]` |

**Reference configuration:** `mast_reference_pose`. CAHVOR calibration mast pose near forward/level; use source reference POS/QUAT for articulation.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[0.872866, -0.677208, 1.970931]` |
| Calibration reference R_USD → ground FLU | `[0.02536656230082749, 0.0064777660932854066, -0.9996572292858583]`<br>`[-0.999653064827439, 0.007257868963866508, -0.025319425728313284]`<br>`[0.007091367861454289, 0.9999526798226726, 0.0066596259136311835]` |
| Calibration reference USD RPY (degrees) | `[89.61841912685438, -0.4063088548605288, -88.54641056953018]` |
| Calibration central-ray boresight in FLU | `[0.9996572292858583, 0.025319425728313284, -0.0066596259136311835]` |
| Current rigid parent | Body_MastTilt |
| Current parent-relative translation (m) | `[0.06846600000000003, -0.11780800000000002, 0.06483100000000008]` |
| Current R_USD → rigid parent | `[0.02536656230082679, 0.006477766093285042, -0.9996572292858583]`<br>`[-0.9996530648274391, 0.007257868963865932, -0.025319425728312805]`<br>`[0.007091367861453868, 0.9999526798226727, 0.0066596259136306735]` |
| Current YAML camera-link RPY (degrees) | `[-0.4063178653355237, 0.38157127850939776, 1.4508834601249005]` |
| Current raster (pixels) | `[1648, 1200]` |
| Current horizontal FOV (degrees) | 7.00805088 |
| Current near/far clipping (m) | `[0.07, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[0.872866, 0.677208, -1.970931]` |
| CAHVOR_A | `[0.999741, -0.022668, 0.001764]` |
| CAHVOR_H | `[1162.600942, 13353.117702, -93.448986]` |
| CAHVOR_V | `[512.731806, 83.454058, 13371.22614]` |
| CAHVOR_O | `[0.999495, -0.029483, 0.011824]` |
| CAHVOR_R | `[-0.000106, 1.436779, -0.685884]` |
| CAHVOR_E | absent |
| CAHVOR_POS | `[0.80436, 0.55942, -1.90608]` |
| CAHVOR_QUAT | `[1e-05, -0.00325, -0.00104, 0.99999]` |
| CAHVOR_DIMS | `[1648.0, 1200.0]` |
| CAHVOR_HS | `[13376.370999]` |
| CAHVOR_VS | `[13370.635765]` |
| CAHVOR_HC | `[859.446513]` |
| CAHVOR_VC | `[534.294115]` |
| CAHVOR_THETA | `[-1.570787]` |
| FOV_BOUNDARY | `[0.06091935, 0.04433268, 0.99715768]`<br>`[0.0, 0.04462814, 0.99900367]`<br>`[-0.06080956, 0.04423678, 0.99716864]`<br>`[-0.06106251, -5.126e-05, 0.99813394]`<br>`[-0.06083571, -0.04440396, 0.99715962]`<br>`[2.39e-05, -0.04469527, 0.99900067]`<br>`[0.06099392, -0.0444053, 0.99714989]`<br>`[0.06117482, -3.5e-06, 0.99812707]` |
| PIXEL_SAMPLES | `[1648.0]` |
| PIXEL_LINES | `[1200.0]` |
| PIXEL_SIZE | `[0.0074]` |
| FOCAL_LENGTH | `[100.0]` |
| IFOV_HORIZONTAL | `[0.00425504]` |
| IFOV_VERTICAL | `[0.00426986]` |
| BORESIGHT_PIXEL | `[859.44651228, 534.29411479]` |

<a id="camera-navcam-left-a"></a>

### C.3 navcam_left_a

**NAIF frame:** `MSL_NAVCAM_LEFT_A`. **Model:** `CAHVOR`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_nla_20120731_c04.ti). **Calibration identity:** `MSL_CAL_004_SN_0216-NAVL-FLIGHT-RCE-A.cahvor`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[14.67, 0.012]` |
| fx / fy (pixels) | `[1226.338076, 1226.021488]` |
| Principal point (pixels) | `[503.457929, 506.499548]` |
| Reference horizontal / vertical FOV (degrees) | `[45.27706953, 45.28806678]` |

**Reference configuration:** `mast_reference_pose`. CAHVOR calibration mast pose near forward/level; use source reference POS/QUAT for articulation.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[0.919577, -0.345256, 1.987225]` |
| Calibration reference R_USD → ground FLU | `[-0.017462969244009037, 0.015092421589890447, -0.9997335962723949]`<br>`[-0.9998235571639453, 0.006657602579537327, 0.017565046767032303]`<br>`[0.006920928060447419, 0.9998639383128317, 0.014973497131136895]` |
| Calibration reference USD RPY (degrees) | `[89.14202919839471, -0.3965431339063989, -91.00062926390746]` |
| Calibration central-ray boresight in FLU | `[0.9997335962723949, -0.017565046767032303, -0.014973497131136895]` |
| Current rigid parent | Body_MastTilt |
| Current parent-relative translation (m) | `[0.11517699999999997, 0.214144, 0.08112500000000011]` |
| Current R_USD → rigid parent | `[-0.01746296924400914, 0.015092421589890437, -0.9997335962723949]`<br>`[-0.9998235571639453, 0.006657602579537403, 0.017565046767032466]`<br>`[0.006920928060447529, 0.9998639383128316, 0.014973497131136826]` |
| Current YAML camera-link RPY (degrees) | `[-0.39658759569175994, 0.8579502517463693, -1.00656766195055]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 45.27706953 |
| Current near/far clipping (m) | `[0.03, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[0.919577, 0.345256, -1.987225]` |
| CAHVOR_A | `[0.99988, 0.01098, 0.01094]` |
| CAHVOR_H | `[490.02493, 1231.763481, -3.042639]` |
| CAHVOR_V | `[492.93483, 13.778703, 1231.460873]` |
| CAHVOR_O | `[0.99959, 0.027364, 0.008413]` |
| CAHVOR_R | `[0.000274, -0.004951, 0.021485]` |
| CAHVOR_E | absent |
| CAHVOR_POS | `[0.80436, 0.55942, -1.90608]` |
| CAHVOR_QUAT | `[1e-05, -0.00325, -0.00104, 0.99999]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[1226.338076]` |
| CAHVOR_VS | `[1226.021488]` |
| CAHVOR_HC | `[503.457929]` |
| CAHVOR_VC | `[506.499548]` |
| CAHVOR_THETA | `[-1.570946]` |
| FOV_BOUNDARY | `[0.36007422, 0.36023352, 0.86056863]`<br>`[-0.0, 0.38556597, 0.92268027]`<br>`[-0.35870457, 0.35875141, 0.86175893]`<br>`[-0.38402517, -5.142e-05, 0.92332262]`<br>`[-0.35775756, -0.35789264, 0.86250936]`<br>`[4.23e-06, -0.38444329, 0.92314861]`<br>`[0.3591483, -0.35920036, 0.86138702]`<br>`[0.38580669, 4.813e-05, 0.92257964]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[14.67]` |
| IFOV_HORIZONTAL | `[0.04425911]` |
| IFOV_VERTICAL | `[0.04426986]` |
| BORESIGHT_PIXEL | `[503.45760356, 506.49914993]` |

<a id="camera-navcam-right-a"></a>

### C.4 navcam_right_a

**NAIF frame:** `MSL_NAVCAM_RIGHT_A`. **Model:** `CAHVOR`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_nra_20120731_c04.ti). **Calibration identity:** `MSL_CAL_004_SN_0206-NAVR-FLIGHT-RCE-A.cahvor`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[14.67, 0.012]` |
| fx / fy (pixels) | `[1206.380901, 1206.07888]` |
| Principal point (pixels) | `[501.230884, 500.180268]` |
| Reference horizontal / vertical FOV (degrees) | `[45.67308306, 45.68814162]` |

**Reference configuration:** `mast_reference_pose`. CAHVOR calibration mast pose near forward/level; use source reference POS/QUAT for articulation.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[0.918496, -0.76885, 1.987065]` |
| Calibration reference R_USD → ground FLU | `[-0.007226753297784843, 0.020396855597007983, -0.9997658437446879]`<br>`[-0.9999690518482072, -0.00325640351032728, 0.007161786228005572]`<br>`[-0.0031095630835662465, 0.9997866593018397, 0.020419757576832044]` |
| Calibration reference USD RPY (degrees) | `[88.82994709316327, 0.17816512794328246, -90.41406806969617]` |
| Calibration central-ray boresight in FLU | `[0.9997658437446879, -0.007161786228005572, -0.020419757576832044]` |
| Current rigid parent | Body_MastTilt |
| Current parent-relative translation (m) | `[0.11409599999999998, -0.20945000000000003, 0.08096500000000018]` |
| Current R_USD → rigid parent | `[-0.0072267532977849935, 0.020396855597008323, -0.9997658437446879]`<br>`[-0.9999690518482071, -0.003256403510326855, 0.007161786228005784]`<br>`[-0.0031095630835658583, 0.9997866593018396, 0.020419757576832342]` |
| Current YAML camera-link RPY (degrees) | `[0.17820228412795108, 1.1700472491920177, -0.4104292105260988]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 45.67308306 |
| Current near/far clipping (m) | `[0.01, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[0.918496, 0.76885, -1.987065]` |
| CAHVOR_A | `[0.999939, -0.00132, 0.011008]` |
| CAHVOR_H | `[502.749189, 1205.712037, 9.43477]` |
| CAHVOR_V | `[486.867495, -4.602833, 1211.505435]` |
| CAHVOR_O | `[0.996805, 0.01651, -0.078154]` |
| CAHVOR_R | `[0.008154, -0.008592, 0.007793]` |
| CAHVOR_E | absent |
| CAHVOR_POS | `[0.80436, 0.55942, -1.90608]` |
| CAHVOR_QUAT | `[1e-05, -0.00325, -0.00104, 0.99999]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[1206.380901]` |
| CAHVOR_VS | `[1206.07888]` |
| CAHVOR_HC | `[501.230884]` |
| CAHVOR_VC | `[500.180268]` |
| CAHVOR_THETA | `[-1.570833]` |
| FOV_BOUNDARY | `[0.36382354, 0.36377099, 0.85749816]`<br>`[-0.0, 0.38906747, 0.92120926]`<br>`[-0.36181179, 0.36181218, 0.85917645]`<br>`[-0.38686666, -9.141e-05, 0.92213566]`<br>`[-0.36012719, -0.36042839, 0.86046486]`<br>`[2e-05, -0.38738124, 0.92191961]`<br>`[0.36211698, -0.36240566, 0.85879766]`<br>`[0.38933947, -0.00013379, 0.92109433]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[14.67]` |
| IFOV_HORIZONTAL | `[0.04464622]` |
| IFOV_VERTICAL | `[0.04466094]` |
| BORESIGHT_PIXEL | `[501.23083936, 500.18012365]` |

<a id="camera-navcam-left-b"></a>

### C.5 navcam_left_b

**NAIF frame:** `MSL_NAVCAM_LEFT_B`. **Model:** `CAHVOR`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_nlb_20130530_c05.ti). **Calibration identity:** `MSL_CAL_005_SN_0215-NAVL-FLIGHT-RCE-B.cahvor`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[14.67, 0.012]` |
| fx / fy (pixels) | `[1224.672774, 1224.792081]` |
| Principal point (pixels) | `[507.177038, 502.629022]` |
| Reference horizontal / vertical FOV (degrees) | `[45.32356488, 45.319053450000006]` |

**Reference configuration:** `mast_reference_pose`. CAHVOR calibration mast pose near forward/level; use source reference POS/QUAT for articulation.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[0.919405, -0.345366, 1.939156]` |
| Calibration reference R_USD → ground FLU | `[-0.004710205383789822, 0.008920164270691018, -0.9999491210229781]`<br>`[-0.9999888094600641, 0.00039946838719354203, 0.004713955838933893]`<br>`[0.0004414973230987224, 0.9999601347525768, 0.008918182871088498]` |
| Calibration reference USD RPY (degrees) | `[89.48901893721384, -0.025295934101660613, -90.26987591335215]` |
| Calibration central-ray boresight in FLU | `[0.9999491210229781, -0.004713955838933893, -0.008918182871088498]` |
| Current rigid parent | Body_MastTilt |
| Current parent-relative translation (m) | `[0.11500500000000002, 0.214034, 0.033056000000000196]` |
| Current R_USD → rigid parent | `[-0.004710205383789745, 0.008920164270690978, -0.9999491210229783]`<br>`[-0.9999888094600643, 0.0003994683871935134, 0.004713955838933748]`<br>`[0.0004414973230990049, 0.9999601347525771, 0.008918182871088254]` |
| Current YAML camera-link RPY (degrees) | `[-0.025296940104973038, 0.5109810129846323, -0.2701015161047367]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 45.32356488 |
| Current near/far clipping (m) | `[0.03, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[0.919405, 0.345366, -1.939156]` |
| CAHVOR_A | `[0.999998, 0.001181, 0.001677]` |
| CAHVOR_H | `[505.730471, 1225.270655, 0.318254]` |
| CAHVOR_V | `[500.573345, 1.09336, 1225.633038]` |
| CAHVOR_O | `[0.999969, -0.007128, 0.00343]` |
| CAHVOR_R | `[7.2e-05, -0.000111, 0.007809]` |
| CAHVOR_E | absent |
| CAHVOR_POS | `[0.80436, 0.55942, -1.90608]` |
| CAHVOR_QUAT | `[1e-05, -0.00325, -0.00104, 0.99999]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[1224.672774]` |
| CAHVOR_VS | `[1224.792081]` |
| CAHVOR_HC | `[507.177038]` |
| CAHVOR_VC | `[502.629022]` |
| CAHVOR_THETA | `[-1.570821]` |
| FOV_BOUNDARY | `[0.36057757, 0.36053323, 0.8602323]`<br>`[0.0, 0.38625051, 0.92239392]`<br>`[-0.35974487, 0.35971385, 0.86092368]`<br>`[-0.38479601, 2.7e-07, 0.92300164]`<br>`[-0.3581226, -0.35808823, 0.86227665]`<br>`[4.48e-06, -0.38425767, 0.92322589]`<br>`[0.35895674, -0.35889931, 0.86159233]`<br>`[0.38578506, 2.79e-06, 0.92258869]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[14.67]` |
| IFOV_HORIZONTAL | `[0.04430456]` |
| IFOV_VERTICAL | `[0.04430015]` |
| BORESIGHT_PIXEL | `[507.17703789, 502.62902172]` |

<a id="camera-navcam-right-b"></a>

### C.6 navcam_right_b

**NAIF frame:** `MSL_NAVCAM_RIGHT_B`. **Model:** `CAHVOR`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_nrb_20130530_c05.ti). **Calibration identity:** `MSL_CAL_005_SN_0218-NAVR-FLIGHT-RCE-B.cahvor`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[14.67, 0.012]` |
| fx / fy (pixels) | `[1220.337925, 1219.961039]` |
| Principal point (pixels) | `[509.167383, 517.250162]` |
| Reference horizontal / vertical FOV (degrees) | `[45.474375540000004, 45.48676407]` |

**Reference configuration:** `mast_reference_pose`. CAHVOR calibration mast pose near forward/level; use source reference POS/QUAT for articulation.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[0.919104, -0.768966, 1.939388]` |
| Calibration reference R_USD → ground FLU | `[-0.003723993393775016, 0.008041200536424056, -0.9999607347126865]`<br>`[-0.9999801933521559, 0.005043857013300097, 0.003764626118796468]`<br>`[0.005073931078371205, 0.9999549482853527, 0.008022257977000109]` |
| Calibration reference USD RPY (degrees) | `[89.5403476284584, -0.29071608374346947, -90.21337234421466]` |
| Calibration central-ray boresight in FLU | `[0.9999607347126865, -0.003764626118796468, -0.008022257977000109]` |
| Current rigid parent | Body_MastTilt |
| Current parent-relative translation (m) | `[0.11470400000000003, -0.20956600000000003, 0.033287999999999984]` |
| Current R_USD → rigid parent | `[-0.003723993393774938, 0.00804120053642432, -0.9999607347126868]`<br>`[-0.9999801933521559, 0.005043857013300124, 0.0037646261187963548]`<br>`[0.005073931078371285, 0.9999549482853528, 0.008022257977000291]` |
| Current YAML camera-link RPY (degrees) | `[-0.29072543902802284, 0.4596464545527855, -0.2157046387020198]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 45.474375540000004 |
| Current near/far clipping (m) | `[0.01, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[0.919104, 0.768966, -1.939388]` |
| CAHVOR_A | `[0.999917, 0.001877, 0.012745]` |
| CAHVOR_H | `[506.913101, 1221.276031, 0.315425]` |
| CAHVOR_V | `[501.647485, 7.113463, 1226.438717]` |
| CAHVOR_O | `[0.99986, 0.001297, 0.016707]` |
| CAHVOR_R | `[1.6e-05, 0.00171, -0.004983]` |
| CAHVOR_E | absent |
| CAHVOR_POS | `[0.80436, 0.55942, -1.90608]` |
| CAHVOR_QUAT | `[1e-05, -0.00325, -0.00104, 0.99999]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[1220.337925]` |
| CAHVOR_VS | `[1219.961039]` |
| CAHVOR_HC | `[509.167383]` |
| CAHVOR_VC | `[517.250162]` |
| CAHVOR_THETA | `[-1.570797]` |
| FOV_BOUNDARY | `[0.36023167, 0.36034364, 0.86045663]`<br>`[-0.0, 0.38595358, 0.9225182]`<br>`[-0.35980956, 0.35991235, 0.86081367]`<br>`[-0.38624091, -6.15e-06, 0.92239794]`<br>`[-0.36085188, -0.36096538, 0.85993599]`<br>`[1.64e-06, -0.38725515, 0.92197259]`<br>`[0.36128168, -0.36138439, 0.85957947]`<br>`[0.38676853, 3.27e-06, 0.92217683]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[14.67]` |
| IFOV_HORIZONTAL | `[0.04445198]` |
| IFOV_VERTICAL | `[0.04446409]` |
| BORESIGHT_PIXEL | `[509.16738241, 517.25016168]` |

<a id="camera-hazcam-front-left-a"></a>

### C.7 hazcam_front_left_a

**NAIF frame:** `MSL_HAZCAM_FRONT_LEFT_A`. **Model:** `CAHVORE3,0.37`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_hfla_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0205-FHAZL-FLIGHT-RCE-A.cahvore`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[5.58, 0.012]` |
| fx / fy (pixels) | `[455.104166, 455.167156]` |
| Principal point (pixels) | `[505.512289, 524.155729]` |
| Reference horizontal / vertical FOV (degrees) | `[125.71466952, 125.73709368]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[1.032819, 0.088715, 0.708463]` |
| Calibration reference R_USD → ground FLU | `[-0.01085829898074223, 0.6880577500375117, -0.72557468944042]`<br>`[-0.9999115171095839, -0.0018948431510737052, 0.01316691007955306]`<br>`[0.007684744293404902, 0.725653458740982, 0.6880174434724711]` |
| Calibration reference USD RPY (degrees) | `[46.52501942229367, -0.440307748472513, -90.62216530222983]` |
| Calibration central-ray boresight in FLU | `[0.72557468944042, -0.01316691007955306, -0.6880174434724711]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[1.032819, 0.088715, 0.708463]` |
| Current R_USD → rigid parent | `[-0.01085829898074223, 0.6880577500375117, -0.72557468944042]`<br>`[-0.9999115171095839, -0.0018948431510737052, 0.01316691007955306]`<br>`[0.007684744293404902, 0.725653458740982, 0.6880174434724711]` |
| Current YAML camera-link RPY (degrees) | `[-0.6067454794091249, 43.473376511436584, -1.039624993798721]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 125.71466952 |
| Current near/far clipping (m) | `[0.01, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[1.032819, -0.088715, -0.708463]` |
| CAHVOR_A | `[0.706251, -3.1e-05, 0.707962]` |
| CAHVOR_H | `[356.481676, 455.08774, 358.438893]` |
| CAHVOR_V | `[47.94513, -0.87866, 692.543761]` |
| CAHVOR_O | `[0.704987, -0.000211, 0.709221]` |
| CAHVOR_R | `[3e-06, -0.014403, -0.007247]` |
| CAHVOR_E | `[0.002111, 0.002025, 0.002171]` |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[455.104166]` |
| CAHVOR_VS | `[455.167156]` |
| CAHVOR_HC | `[505.512289]` |
| CAHVOR_VC | `[524.155729]` |
| CAHVOR_THETA | `[-1.570994]` |
| FOV_BOUNDARY | `[0.69550765, 0.71720665, -0.04340201]`<br>`[-0.0, 0.89047955, 0.45502326]`<br>`[-0.6967983, 0.71496287, -0.05744759]`<br>`[-0.88969234, 0.01436066, 0.45633464]`<br>`[-0.72426846, -0.68913474, -0.02298944]`<br>`[-0.00895172, -0.88942201, 0.45699929]`<br>`[0.70874217, -0.70531397, -0.01472224]`<br>`[0.89003227, 0.00551332, 0.45586418]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[5.58]` |
| IFOV_HORIZONTAL | `[0.12288824]` |
| IFOV_VERTICAL | `[0.12291016]` |
| BORESIGHT_PIXEL | `[505.512548, 524.15598937]` |

<a id="camera-hazcam-front-right-a"></a>

### C.8 hazcam_front_right_a

**NAIF frame:** `MSL_HAZCAM_FRONT_RIGHT_A`. **Model:** `CAHVORE3,0.37`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_hfra_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0213-FHAZR-FLIGHT-RCE-A.cahvore`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[5.58, 0.012]` |
| fx / fy (pixels) | `[454.374183, 454.440018]` |
| Principal point (pixels) | `[511.933001, 520.990477]` |
| Reference horizontal / vertical FOV (degrees) | `[125.98468014, 125.99906351999999]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[1.032635, -0.077859, 0.708165]` |
| Calibration reference R_USD → ground FLU | `[0.00013602718506295215, 0.6916397660806163, -0.7222426292268793]`<br>`[-0.9999999360754276, -0.0001447455505473646, -0.0003269523918050025]`<br>`[-0.0003306746827837307, 0.7222426275322414, 0.6916397021785101]` |
| Calibration reference USD RPY (degrees) | `[46.23995093832582, 0.018946264060617314, -89.99220621594671]` |
| Calibration central-ray boresight in FLU | `[0.7222426292268793, 0.0003269523918050025, -0.6916397021785101]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[1.032635, -0.077859, 0.708165]` |
| Current R_USD → rigid parent | `[0.00013602718506295215, 0.6916397660806163, -0.7222426292268793]`<br>`[-0.9999999360754276, -0.0001447455505473646, -0.0003269523918050025]`<br>`[-0.0003306746827837307, 0.7222426275322414, 0.6916397021785101]` |
| Current YAML camera-link RPY (degrees) | `[0.026232545226835016, 43.76004606188093, 0.025937254482672242]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 125.98468014 |
| Current near/far clipping (m) | `[0.01, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[1.032635, 0.077859, -0.708165]` |
| CAHVOR_A | `[0.707644, 0.000621, 0.706569]` |
| CAHVOR_H | `[361.994749, 454.692082, 361.588451]` |
| CAHVOR_V | `[47.582648, 0.251849, 689.697496]` |
| CAHVOR_O | `[0.706118, 0.000198, 0.708094]` |
| CAHVOR_R | `[5e-06, -0.014656, -0.007313]` |
| CAHVOR_E | `[0.002169, 0.00136, 0.001698]` |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[454.374183]` |
| CAHVOR_VS | `[454.440018]` |
| CAHVOR_HC | `[511.933001]` |
| CAHVOR_VC | `[520.990477]` |
| CAHVOR_THETA | `[-1.57073]` |
| FOV_BOUNDARY | `[0.69815069, 0.71371143, -0.05658285]`<br>`[-0.0, 0.89184555, 0.45234004]`<br>`[-0.69791029, 0.71376015, -0.05888701]`<br>`[-0.89118977, 0.00766687, 0.45356589]`<br>`[-0.71409254, -0.69950231, -0.02771941]`<br>`[0.00035812, -0.89015694, 0.45565391]`<br>`[0.71468862, -0.69895775, -0.02604305]`<br>`[0.89070161, 0.00788627, 0.45452002]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[5.58]` |
| IFOV_HORIZONTAL | `[0.12315218]` |
| IFOV_VERTICAL | `[0.12316624]` |
| BORESIGHT_PIXEL | `[511.93296618, 520.99060181]` |

<a id="camera-hazcam-front-left-b"></a>

### C.9 hazcam_front_left_b

**NAIF frame:** `MSL_HAZCAM_FRONT_LEFT_B`. **Model:** `CAHVORE3,0.37`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_hflb_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0208-FHAZL-FLIGHT-RCE-B.cahvore`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[5.58, 0.012]` |
| fx / fy (pixels) | `[453.755256, 453.824156]` |
| Principal point (pixels) | `[501.352813, 515.658123]` |
| Reference horizontal / vertical FOV (degrees) | `[125.95418450999999, 125.91902400000001]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[1.033039, 0.17145, 0.707908]` |
| Calibration reference R_USD → ground FLU | `[-0.01065377384875195, 0.7010272451750121, -0.7130549057576935]`<br>`[-0.9997141181033299, 0.0077974603509414955, 0.022602691807769502]`<br>`[0.021405120127230406, 0.7130918602356986, 0.7007437617973704]` |
| Calibration reference USD RPY (degrees) | `[45.50039476050842, -1.2265167161571828, -90.61056772137067]` |
| Calibration central-ray boresight in FLU | `[0.7130549057576935, -0.022602691807769502, -0.7007437617973704]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[1.033039, 0.17145, 0.707908]` |
| Current R_USD → rigid parent | `[-0.01065377384875195, 0.7010272451750121, -0.7130549057576935]`<br>`[-0.9997141181033299, 0.0077974603509414955, 0.022602691807769502]`<br>`[0.021405120127230406, 0.7130918602356986, 0.7007437617973704]` |
| Current YAML camera-link RPY (degrees) | `[-1.7193505609953201, 44.48670661322416, -1.8155759824842563]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 125.95418450999999 |
| Current near/far clipping (m) | `[0.01, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[1.033039, -0.17145, -0.707908]` |
| CAHVOR_A | `[0.706662, 0.00032, 0.707551]` |
| CAHVOR_H | `[356.71795, 453.90141, 352.099828]` |
| CAHVOR_V | `[43.301107, 3.702505, 685.544287]` |
| CAHVOR_O | `[0.704793, -0.000541, 0.709413]` |
| CAHVOR_R | `[8e-06, -0.013391, -0.007308]` |
| CAHVOR_E | `[0.001868, 0.001572, 0.001665]` |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[453.755256]` |
| CAHVOR_VS | `[453.824156]` |
| CAHVOR_HC | `[501.352813]` |
| CAHVOR_VC | `[515.658123]` |
| CAHVOR_THETA | `[-1.570892]` |
| FOV_BOUNDARY | `[0.70145564, 0.71195188, -0.03293194]`<br>`[-0.0, 0.89196262, 0.45210916]`<br>`[-0.70368865, 0.7082162, -0.05702711]`<br>`[-0.89082506, 0.01183542, 0.45419228]`<br>`[-0.72438076, -0.68868327, -0.03143019]`<br>`[-0.01558763, -0.88933349, 0.4569934]`<br>`[0.69712788, -0.71682265, -0.01334186]`<br>`[0.8907552, -0.00391065, 0.45446659]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[5.58]` |
| IFOV_HORIZONTAL | `[0.12312237]` |
| IFOV_VERTICAL | `[0.123088]` |
| BORESIGHT_PIXEL | `[501.35285384, 515.65797749]` |

<a id="camera-hazcam-front-right-b"></a>

### C.10 hazcam_front_right_b

**NAIF frame:** `MSL_HAZCAM_FRONT_RIGHT_B`. **Model:** `CAHVORE3,0.37`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_hfrb_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0209-FHAZR-FLIGHT-RCE-B.cahvore`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[5.58, 0.012]` |
| fx / fy (pixels) | `[453.773752, 453.745949]` |
| Principal point (pixels) | `[509.65856, 511.072128]` |
| Reference horizontal / vertical FOV (degrees) | `[126.11626863000001, 126.12435033]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[1.033137, 0.004912, 0.708098]` |
| Calibration reference R_USD → ground FLU | `[-0.00043586119283378166, 0.705181693136283, -0.709026508453997]`<br>`[-0.9999657712708577, 0.005550870443676321, 0.006135480746970034]`<br>`[0.008262342990913706, 0.7090049135956414, 0.7051551362540994]` |
| Calibration reference USD RPY (degrees) | `[45.15597629763936, -0.4734027686165315, -90.02497386004488]` |
| Calibration central-ray boresight in FLU | `[0.709026508453997, -0.006135480746970034, -0.7051551362540994]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[1.033137, 0.004912, 0.708098]` |
| Current R_USD → rigid parent | `[-0.00043586119283378166, 0.705181693136283, -0.709026508453997]`<br>`[-0.9999657712708577, 0.005550870443676321, 0.006135480746970034]`<br>`[0.008262342990913706, 0.7090049135956414, 0.7051551362540994]` |
| Current YAML camera-link RPY (degrees) | `[-0.6676624455097445, 44.84207863527255, -0.4957901768002166]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 126.11626863000001 |
| Current near/far clipping (m) | `[0.01, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[1.033137, -0.004912, -0.708098]` |
| CAHVOR_A | `[0.709687, 0.002072, 0.704514]` |
| CAHVOR_H | `[362.792814, 454.822103, 356.624024]` |
| CAHVOR_V | `[43.031434, 3.578514, 682.067149]` |
| CAHVOR_O | `[0.708524, 0.004189, 0.705675]` |
| CAHVOR_R | `[7e-06, -0.014649, -0.00712]` |
| CAHVOR_E | `[0.002889, 0.002264, 0.002178]` |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[453.773752]` |
| CAHVOR_VS | `[453.745949]` |
| CAHVOR_HC | `[509.65856]` |
| CAHVOR_VC | `[511.072128]` |
| CAHVOR_THETA | `[-1.570756]` |
| FOV_BOUNDARY | `[0.70592158, 0.70667818, -0.04775643]`<br>`[0.0, 0.89240416, 0.45123699]`<br>`[-0.70645202, 0.70675711, -0.03768189]`<br>`[-0.89026151, 0.00094128, 0.45544874]`<br>`[-0.70821674, -0.70543114, -0.02821277]`<br>`[-0.0013171, -0.89058907, 0.45480697]`<br>`[0.70561365, -0.70756566, -0.03821272]`<br>`[0.89266507, -0.0004616, 0.45072039]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[5.58]` |
| IFOV_HORIZONTAL | `[0.12328081]` |
| IFOV_VERTICAL | `[0.12328871]` |
| BORESIGHT_PIXEL | `[509.65835283, 511.07211939]` |

<a id="camera-hazcam-rear-left-a"></a>

### C.11 hazcam_rear_left_a

**NAIF frame:** `MSL_HAZCAM_BACK_LEFT_A`. **Model:** `CAHVORE3,0.37`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_hbla_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0211-RHAZL-FLIGHT-RCE-A.cahvore`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[5.58, 0.012]` |
| fx / fy (pixels) | `[451.300295, 451.276945]` |
| Principal point (pixels) | `[495.034761, 513.488201]` |
| Reference horizontal / vertical FOV (degrees) | `[126.79688076000001, 126.73527569999999]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[-0.976174, 0.455344, 0.779765]` |
| Calibration reference R_USD → ground FLU | `[0.019927791733727978, -0.7064260524059411, 0.7075062654130886]`<br>`[0.9994893971693208, -0.003602173048213633, -0.031748532177700545]`<br>`[0.0249765502566893, 0.7077776888483343, 0.7059935659096235]` |
| Calibration reference USD RPY (degrees) | `[45.07230495026118, -1.4311997465752622, 88.85778968102869]` |
| Calibration central-ray boresight in FLU | `[-0.7075062654130886, 0.031748532177700545, -0.7059935659096235]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[-0.976174, 0.455344, 0.779765]` |
| Current R_USD → rigid parent | `[0.019927791733727978, -0.7064260524059411, 0.7075062654130886]`<br>`[0.9994893971693208, -0.003602173048213633, -0.031748532177700545]`<br>`[0.0249765502566893, 0.7077776888483343, 0.7059935659096235]` |
| Current YAML camera-link RPY (degrees) | `[-2.0210545727951725, 44.90986872605299, 177.43064129257908]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 126.79688076000001 |
| Current near/far clipping (m) | `[0.03, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[-0.976174, -0.455344, -0.779765]` |
| CAHVOR_A | `[-0.704643, 0.004698, 0.709546]` |
| CAHVOR_H | `[-351.443149, -448.967093, 351.635654]` |
| CAHVOR_V | `[-41.627897, 0.777433, 682.339745]` |
| CAHVOR_O | `[-0.705089, 0.005337, 0.709099]` |
| CAHVOR_R | `[1e-06, -0.014583, -0.007091]` |
| CAHVOR_E | `[0.002373, 0.001932, 0.001475]` |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[451.300295]` |
| CAHVOR_VS | `[451.276945]` |
| CAHVOR_HC | `[495.034761]` |
| CAHVOR_VC | `[513.488201]` |
| CAHVOR_THETA | `[-1.570692]` |
| FOV_BOUNDARY | `[0.70325154, 0.71008224, -0.03493552]`<br>`[-0.0, 0.89357846, 0.44890705]`<br>`[-0.70692431, 0.70382776, -0.06988924]`<br>`[-0.89379638, 0.01403502, 0.44825333]`<br>`[-0.72915685, -0.68082222, -0.06936416]`<br>`[-0.02532015, -0.89404382, 0.4472634]`<br>`[0.68532869, -0.72733038, -0.03626444]`<br>`[0.89430563, -0.01146908, 0.44730963]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[5.58]` |
| IFOV_HORIZONTAL | `[0.12394612]` |
| IFOV_VERTICAL | `[0.1238859]` |
| BORESIGHT_PIXEL | `[495.03437919, 513.48789531]` |

<a id="camera-hazcam-rear-right-a"></a>

### C.12 hazcam_rear_right_a

**NAIF frame:** `MSL_HAZCAM_BACK_RIGHT_A`. **Model:** `CAHVORE3,0.37`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_hbra_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0217-RHAZR-FLIGHT-RCE-A.cahvore`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[5.58, 0.012]` |
| fx / fy (pixels) | `[452.033814, 451.924769]` |
| Principal point (pixels) | `[498.436837, 525.515557]` |
| Reference horizontal / vertical FOV (degrees) | `[126.43239609, 126.49393977]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[-0.976811, 0.555458, 0.779633]` |
| Calibration reference R_USD → ground FLU | `[0.016708128487481516, -0.6889739443871239, 0.7245935014876232]`<br>`[0.9996615436216849, -0.002942247141616002, -0.02584843100979158]`<br>`[0.019940828627620037, 0.7247801371018705, 0.6886915973178691]` |
| Calibration reference USD RPY (degrees) | `[46.46254915831528, -1.1426010522310501, 89.04245979484888]` |
| Calibration central-ray boresight in FLU | `[-0.7245935014876232, 0.02584843100979158, -0.6886915973178691]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[-0.976811, 0.555458, 0.779633]` |
| Current R_USD → rigid parent | `[0.016708128487481516, -0.6889739443871239, 0.7245935014876232]`<br>`[0.9996615436216849, -0.002942247141616002, -0.02584843100979158]`<br>`[0.019940828627620037, 0.7247801371018705, 0.6886915973178691]` |
| Current YAML camera-link RPY (degrees) | `[-1.575977472553252, 43.526626493761405, 177.9569534431277]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 126.43239609 |
| Current near/far clipping (m) | `[0.03, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[-0.976811, -0.555458, -0.779633]` |
| CAHVOR_A | `[-0.703069, 0.002937, 0.711116]` |
| CAHVOR_H | `[-352.302693, -450.566058, 354.46705]` |
| CAHVOR_V | `[-48.105738, 0.171962, 691.439373]` |
| CAHVOR_O | `[-0.702286, 3.7e-05, 0.711895]` |
| CAHVOR_R | `[1e-05, -0.01408, -0.007074]` |
| CAHVOR_E | `[0.002512, 0.002172, 0.001812]` |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[452.033814]` |
| CAHVOR_VS | `[451.924769]` |
| CAHVOR_HC | `[498.436837]` |
| CAHVOR_VC | `[525.515557]` |
| CAHVOR_THETA | `[-1.570667]` |
| FOV_BOUNDARY | `[0.69329031, 0.71865924, -0.05364184]`<br>`[-0.0, 0.89306314, 0.44993135]`<br>`[-0.69637731, 0.71498897, -0.06204372]`<br>`[-0.89049386, 0.01985432, 0.45456187]`<br>`[-0.732349, -0.68037274, -0.02752948]`<br>`[-0.0176294, -0.89276006, 0.45018738]`<br>`[0.70157134, -0.71202211, -0.02867354]`<br>`[0.89482347, 0.00187226, 0.44641622]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[5.58]` |
| IFOV_HORIZONTAL | `[0.12358983]` |
| IFOV_VERTICAL | `[0.12364999]` |
| BORESIGHT_PIXEL | `[498.43698028, 525.51575933]` |

<a id="camera-hazcam-rear-left-b"></a>

### C.13 hazcam_rear_left_b

**NAIF frame:** `MSL_HAZCAM_BACK_LEFT_B`. **Model:** `CAHVORE3,0.37`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_hblb_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0212-RHAZL-FLIGHT-RCE-B.cahvore`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[5.58, 0.012]` |
| fx / fy (pixels) | `[456.444113, 456.501796]` |
| Principal point (pixels) | `[507.648783, 516.17542]` |
| Reference horizontal / vertical FOV (degrees) | `[125.2986768, 125.28405812999999]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[-0.975657, -0.552157, 0.780044]` |
| Calibration reference R_USD → ground FLU | `[0.003088393138644074, -0.7015603065911357, 0.7126033946337702]`<br>`[0.9999726597817546, -0.002621189765976828, -0.006914409100852164]`<br>`[0.006718743693904768, 0.7126052663150634, 0.7015330305147529]` |
| Calibration reference USD RPY (degrees) | `[45.44859786308813, -0.3849585535967616, 89.82304383228504]` |
| Calibration central-ray boresight in FLU | `[-0.7126033946337702, 0.006914409100852164, -0.7015330305147529]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[-0.975657, -0.552157, 0.780044]` |
| Current R_USD → rigid parent | `[0.003088393138644074, -0.7015603065911357, 0.7126033946337702]`<br>`[0.9999726597817546, -0.002621189765976828, -0.006914409100852164]`<br>`[0.006718743693904768, 0.7126052663150634, 0.7015330305147529]` |
| Current YAML camera-link RPY (degrees) | `[-0.5401928237103696, 44.55012902074753, 179.44407502105997]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 125.2986768 |
| Current near/far clipping (m) | `[0.03, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[-0.975657, 0.552157, -0.780044]` |
| CAHVOR_A | `[-0.705382, 0.001497, 0.708826]` |
| CAHVOR_H | `[-359.390139, -455.682421, 359.500729]` |
| CAHVOR_V | `[-40.522581, -0.430925, 687.887119]` |
| CAHVOR_O | `[-0.706341, 0.000162, 0.707872]` |
| CAHVOR_R | `[4e-06, -0.014132, -0.00714]` |
| CAHVOR_E | `[0.002847, 0.001342, 0.00022]` |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[456.444113]` |
| CAHVOR_VS | `[456.501796]` |
| CAHVOR_HC | `[507.648783]` |
| CAHVOR_VC | `[516.17542]` |
| CAHVOR_THETA | `[-1.570701]` |
| FOV_BOUNDARY | `[0.70369832, 0.71020695, -0.02036581]`<br>`[0.0, 0.88724754, 0.46129361]`<br>`[-0.70453621, 0.70943457, -0.01820246]`<br>`[-0.88732931, 0.00539029, 0.4611048]`<br>`[-0.71409293, -0.699784, -0.01932977]`<br>`[-0.00473481, -0.88904816, 0.45778919]`<br>`[0.7056509, -0.70821436, -0.02211852]`<br>`[0.88908356, 0.0005312, 0.45774462]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[5.58]` |
| IFOV_HORIZONTAL | `[0.1224816]` |
| IFOV_VERTICAL | `[0.12246731]` |
| BORESIGHT_PIXEL | `[507.64864218, 516.17552915]` |

<a id="camera-hazcam-rear-right-b"></a>

### C.14 hazcam_rear_right_b

**NAIF frame:** `MSL_HAZCAM_BACK_RIGHT_B`. **Model:** `CAHVORE3,0.37`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_hbrb_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0207-RHAZR-FLIGHT-RCE-B.cahvore`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[5.58, 0.012]` |
| fx / fy (pixels) | `[452.185301, 452.297746]` |
| Principal point (pixels) | `[516.315156, 500.449382]` |
| Reference horizontal / vertical FOV (degrees) | `[126.60257213999999, 126.57576954000001]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[-0.975248, -0.451863, 0.780144]` |
| Calibration reference R_USD → ground FLU | `[-0.015263453910240013, -0.7234271388079583, 0.6902319912977528]`<br>`[0.9998762899596003, -0.01366594689973907, 0.007787597316163282]`<br>`[0.0037989144969557105, 0.690265468302931, 0.7235462331580341]` |
| Calibration reference USD RPY (degrees) | `[43.651521080828424, -0.21766229095011094, 90.87457176176487]` |
| Calibration central-ray boresight in FLU | `[-0.6902319912977528, -0.007787597316163282, -0.7235462331580341]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[-0.975248, -0.451863, 0.780144]` |
| Current R_USD → rigid parent | `[-0.015263453910240013, -0.7234271388079583, 0.6902319912977528]`<br>`[0.9998762899596003, -0.01366594689973907, 0.007787597316163282]`<br>`[0.0037989144969557105, 0.690265468302931, 0.7235462331580341]` |
| Current YAML camera-link RPY (degrees) | `[-0.3153273339702016, 46.3480455463625, -179.35358324050844]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 126.60257213999999 |
| Current near/far clipping (m) | `[0.03, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[-0.975248, 0.451863, -0.780144]` |
| CAHVOR_A | `[-0.707819, -0.002525, 0.706389]` |
| CAHVOR_H | `[-368.993223, -453.445875, 359.560463]` |
| CAHVOR_V | `[-34.747153, -7.474462, 673.616807]` |
| CAHVOR_O | `[-0.704369, -0.001355, 0.709832]` |
| CAHVOR_R | `[2.5e-05, -0.015148, -0.00709]` |
| CAHVOR_E | `[0.002469, 0.002745, 0.001958]` |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[452.185301]` |
| CAHVOR_VS | `[452.297746]` |
| CAHVOR_HC | `[516.315156]` |
| CAHVOR_VC | `[500.449382]` |
| CAHVOR_THETA | `[-1.570664]` |
| FOV_BOUNDARY | `[0.7133924, 0.69855885, -0.05555908]`<br>`[-0.0, 0.89625418, 0.4435408]`<br>`[-0.71205123, 0.69992798, -0.0555326]`<br>`[-0.89417896, -0.00982765, 0.44760184]`<br>`[-0.69422007, -0.71846431, -0.04321493]`<br>`[0.00638918, -0.89024752, 0.45543225]`<br>`[0.70561308, -0.7071991, -0.04449287]`<br>`[0.89256984, -0.00351735, 0.45089545]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.012]` |
| FOCAL_LENGTH | `[5.58]` |
| IFOV_HORIZONTAL | `[0.12375618]` |
| IFOV_VERTICAL | `[0.12372998]` |
| BORESIGHT_PIXEL | `[516.31492084, 500.44907079]` |

<a id="camera-chemcam-rmi"></a>

### C.15 chemcam_rmi

**NAIF frame:** `MSL_CHEMCAM_RMI`. **Model:** `CAHV`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_chrmi_20120731_c03.ti). **Calibration identity:** `MSL_CAL_003_SN_0001_FOCUS_12658-RMI-FLIGHT.cahv`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1024, 1024] / [1024, 1024] |
| Nominal focal length / pixel pitch (mm) | `[717.0, 0.014]` |
| fx / fy (pixels) | `[48250.0789, 47598.176078]` |
| Principal point (pixels) | `[7644.119676, -10566.326805]` |
| Reference horizontal / vertical FOV (degrees) | `[1.1571152999999998, 1.15488516]` |

**Reference configuration:** `mast_reference_pose`. CAHVOR calibration mast pose near forward/level; use source reference POS/QUAT for articulation.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[0.880676, -0.447699, 2.119346]` |
| Calibration reference R_USD → ground FLU | `[-0.001722588306538016, 0.009753185538762602, -0.9999509528278738]`<br>`[-0.9999965644891884, 0.0019588864030151846, 0.001741773200155184]`<br>`[0.0019757781623641582, 0.9999505178437114, 0.009749777676776565]` |
| Calibration reference USD RPY (degrees) | `[89.44136894690217, -0.11320382360994327, -90.0986972812567]` |
| Calibration central-ray boresight in FLU | `[0.9999509528278738, -0.001741773200155184, -0.009749777676776565]` |
| Current rigid parent | Body_MastTilt |
| Current parent-relative translation (m) | `[0.07627600000000001, 0.111701, 0.21324600000000027]` |
| Current R_USD → rigid parent | `[-0.0017225883065383751, 0.009753185538762699, -0.9999509528278739]`<br>`[-0.9999965644891884, 0.0019588864030148923, 0.0017417732001555053]`<br>`[0.0019757781623640502, 0.9999505178437116, 0.009749777676776539]` |
| Current YAML camera-link RPY (degrees) | `[-0.11320920447441538, 0.5586299626983972, -0.09980104726757823]` |
| Current raster (pixels) | `[1024, 1024]` |
| Current horizontal FOV (degrees) | 1.1571152999999998 |
| Current near/far clipping (m) | `[0.05, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[0.880676, 0.447699, -2.119346]` |
| CAHVOR_A | `[0.964824, 0.147578, -0.217568]` |
| CAHVOR_H | `[409.260658, 48849.782484, -184.218596]` |
| CAHVOR_V | `[16.866533, 171.217481, 48756.579332]` |
| CAHVOR_O | absent |
| CAHVOR_R | absent |
| CAHVOR_E | absent |
| CAHVOR_POS | `[0.80436, 0.55942, -1.90608]` |
| CAHVOR_QUAT | `[1e-05, -0.00325, -0.00104, 0.99999]` |
| CAHVOR_DIMS | `[1024.0, 1024.0]` |
| CAHVOR_HS | `[48250.0789]` |
| CAHVOR_VS | `[47598.176078]` |
| CAHVOR_HC | `[7644.119676]` |
| CAHVOR_VC | `[-10566.326805]` |
| CAHVOR_THETA | `[-1.535886]` |
| FOV_BOUNDARY | `[0.01010592, 0.01008067, 0.99989812]`<br>`[0.0, 0.0101019, 0.99994897]`<br>`[-0.01013631, 0.01012175, 0.9998974]`<br>`[-0.01011328, 4.89e-06, 0.99994886]`<br>`[-0.01008872, -0.0100633, 0.99989847]`<br>`[-4.6e-07, -0.01005423, 0.99994945]`<br>`[0.01005742, -0.01004253, 0.99989899]`<br>`[0.0100819, -5.26e-06, 0.99994918]` |
| PIXEL_SAMPLES | `[1024.0]` |
| PIXEL_LINES | `[1024.0]` |
| PIXEL_SIZE | `[0.014]` |
| FOCAL_LENGTH | `[717.0]` |
| IFOV_HORIZONTAL | `[0.0011311]` |
| IFOV_VERTICAL | `[0.00112892]` |
| BORESIGHT_PIXEL | `[7644.09777601, -10566.33028286]` |

<a id="camera-mahli"></a>

### C.16 mahli

**NAIF frame:** `MSL_MAHLI`. **Model:** `CAHVOR`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_mahli_20120731_c02.ti). **Calibration identity:** `MSL_CAL_002_SN_3002_FOCUS_12594-MAHLI-FLIGHT.cahvor`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1648, 1200] / [1600, 1200] |
| Nominal focal length / pixel pitch (mm) | `[20.0, 0.0074]` |
| fx / fy (pixels) | `[2834.756414, 2834.593957]` |
| Principal point (pixels) | `[833.771443, 596.720506]` |
| Reference horizontal / vertical FOV (degrees) | `[32.27294853, 23.81326706]` |

**Reference configuration:** `arm_reference_pose`. CAHVOR calibration arm reference pose; arm not stowed. Retarget via CAHVOR_POS/QUAT and arm kinematics before use on a different arm pose.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[2.30587, 0.404252, 1.883873]` |
| Calibration reference R_USD → ground FLU | `[0.1193142389722469, -0.07752388261846371, -0.9898253179234366]`<br>`[0.86760421188713, 0.49285849569082435, 0.065980563358385]`<br>`[0.4827287477395414, -0.8666490355669567, 0.12606508341597972]` |
| Calibration reference USD RPY (degrees) | `[-81.72365126735423, -28.863773008933677, 82.16971408049103]` |
| Calibration central-ray boresight in FLU | `[0.9898253179234366, -0.065980563358385, -0.12606508341597972]` |
| Current rigid parent | Body_ArmTurret |
| Current parent-relative translation (m) | `[-0.1222488367557526, -0.22623779495557148, 0.1464529285331566]` |
| Current R_USD → rigid parent | `[-0.7546025066261504, -0.3652366763219337, 0.5451396401499691]`<br>`[0.4812244165917924, 0.2567564311133991, 0.8381522510605095]`<br>`[-0.44609205089243614, 0.8948062948768394, -0.01798824002960764]` |
| Current YAML camera-link RPY (degrees) | `[26.497850650847873, -1.0307058250736068, -123.04023608056788]` |
| Current raster (pixels) | `[1648, 1200]` |
| Current horizontal FOV (degrees) | 32.27294853 |
| Current near/far clipping (m) | `[0.01, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[2.30587, -0.404252, -1.883873]` |
| CAHVOR_A | `[0.990175, 0.062353, 0.125165]` |
| CAHVOR_H | `[1153.714003, -2407.630832, -1266.203131]` |
| CAHVOR_V | `[813.35867, 1434.434517, -2381.562018]` |
| CAHVOR_O | `[0.987321, 0.099893, 0.123364]` |
| CAHVOR_R | `[0.001413, 0.039832, -0.102819]` |
| CAHVOR_E | absent |
| CAHVOR_POS | `[2.348408, -0.402685, -1.881315]` |
| CAHVOR_QUAT | `[0.859133374, -0.009551398, 0.069324227, 0.506944542]` |
| CAHVOR_DIMS | `[1648.0, 1200.0]` |
| CAHVOR_HS | `[2834.756414]` |
| CAHVOR_VS | `[2834.593957]` |
| CAHVOR_HC | `[833.771443]` |
| CAHVOR_VC | `[596.720506]` |
| CAHVOR_THETA | `[-1.570447]` |
| FOV_BOUNDARY | `[0.27208162, 0.19796979, 0.94168973]`<br>`[-0.0, 0.2062844, 0.97849208]`<br>`[-0.27242813, 0.19833703, 0.94151226]`<br>`[-0.27804159, -2.378e-05, 0.96056904]`<br>`[-0.27226745, -0.19835596, 0.94155475]`<br>`[8.632e-05, -0.20635044, 0.97847815]`<br>`[0.27211435, -0.19809768, 0.94165338]`<br>`[0.27781073, -6.865e-05, 0.96063583]` |
| PIXEL_SAMPLES | `[1648.0]` |
| PIXEL_LINES | `[1200.0]` |
| PIXEL_SIZE | `[0.0074]` |
| FOCAL_LENGTH | `[20.0]` |
| IFOV_HORIZONTAL | `[0.01959499]` |
| IFOV_VERTICAL | `[0.01986094]` |
| BORESIGHT_PIXEL | `[833.77144276, 596.72050652]` |

<a id="camera-mardi"></a>

### C.17 mardi

**NAIF frame:** `MSL_MARDI`. **Model:** `CAHVOR`. **Source:** [instrument kernel](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/ik/msl_mardi_20120731_c02.ti). **Calibration identity:** `MSL_CAL_002_SN_3001-MARDI-FLIGHT.cahvor`.

| Calibration quantity | Value |
| --- | --- |
| Calibration raster / photoactive raster (pixels) | [1648, 1200] / [1600, 1200] |
| Nominal focal length / pixel pitch (mm) | `[9.7, 0.0074]` |
| fx / fy (pixels) | `[1302.58719, 1301.254725]` |
| Principal point (pixels) | `[817.983943, 587.477313]` |
| Reference horizontal / vertical FOV (degrees) | `[72.65307339, 52.81579413]` |

**Reference configuration:** `body`. Rigid body-fixed camera.

| Pose or runtime quantity | Value |
| --- | --- |
| Calibration reference ground-FLU position (m) | `[0.761636, 0.648275, 0.701654]` |
| Calibration reference R_USD → ground FLU | `[-0.0027549093040918926, -0.9999406991251991, -0.010536066995526122]`<br>`[0.9999769397615905, -0.0026893024226190233, -0.006235992104234453]`<br>`[0.006207287633951476, -0.010553003623977507, 0.9999250490385475]` |
| Calibration reference USD RPY (degrees) | `[-0.6046654417131514, -0.35565366758828426, 90.15784791673772]` |
| Calibration central-ray boresight in FLU | `[0.010536066995526122, 0.006235992104234453, -0.9999250490385475]` |
| Current rigid parent | Body_Chassis |
| Current parent-relative translation (m) | `[0.761636, 0.648275, 0.701654]` |
| Current R_USD → rigid parent | `[-0.0027549093040918926, -0.9999406991251991, -0.010536066995526122]`<br>`[0.9999769397615905, -0.0026893024226190233, -0.006235992104234453]`<br>`[0.006207287633951476, -0.010553003623977507, 0.9999250490385475]` |
| Current YAML camera-link RPY (degrees) | `[-149.53591348374823, 89.29849794602625, 30.62005773133457]` |
| Current raster (pixels) | `[1648, 1200]` |
| Current horizontal FOV (degrees) | 72.65307339 |
| Current near/far clipping (m) | `[0.05, 200.0]` |

| Original kernel coefficient | Retained value |
| --- | --- |
| CAHVOR_C | `[0.761636, -0.648275, -0.701654]` |
| CAHVOR_A | `[0.001309, -0.001977, 0.999997]` |
| CAHVOR_H | `[-2.440923, -1304.19732, 815.411187]` |
| CAHVOR_V | `[1302.018084, -4.684829, 585.765467]` |
| CAHVOR_O | `[0.000806, -0.002426, 0.999997]` |
| CAHVOR_R | `[-1.1e-05, -0.320914, 0.113923]` |
| CAHVOR_E | absent |
| CAHVOR_POS | `[0.0, 0.0, 0.0]` |
| CAHVOR_QUAT | `[0.0, 0.0, 0.0, 1.0]` |
| CAHVOR_DIMS | `[1648.0, 1200.0]` |
| CAHVOR_HS | `[1302.58719]` |
| CAHVOR_VS | `[1301.254725]` |
| CAHVOR_HC | `[817.983943]` |
| CAHVOR_VC | `[587.477313]` |
| CAHVOR_THETA | `[-1.570782]` |
| FOV_BOUNDARY | `[0.56792025, 0.41206776, 0.71250737]`<br>`[0.0, 0.44460906, 0.89572472]`<br>`[-0.56718115, 0.41156337, 0.71338709]`<br>`[-0.59225612, -0.00092591, 0.80574923]`<br>`[-0.56510848, -0.4125648, 0.71445272]`<br>`[-0.00052784, -0.44490808, 0.89557608]`<br>`[0.56492856, -0.41447897, 0.71348645]`<br>`[0.5925165, -0.00163335, 0.80555665]` |
| PIXEL_SAMPLES | `[1648.0]` |
| PIXEL_LINES | `[1200.0]` |
| PIXEL_SIZE | `[0.0074]` |
| FOCAL_LENGTH | `[9.7]` |
| IFOV_HORIZONTAL | `[0.04411237]` |
| IFOV_VERTICAL | `[0.04404987]` |
| BORESIGHT_PIXEL | `[817.9839437, 587.47731328]` |

<a id="appendix-d"></a>

## Appendix D. Visual-pose retargeting and clipping inspection

<a id="d-mahli"></a>

### D.1 MAHLI visual-pose retarget

The official reference camera pose belongs to a different, non-stowed arm configuration. Applying it directly to the present visualization would misregister the camera with its housing. The replacement optical center is the mean of the four MAHLI LED disk centroids; a principal-component normal of those disks gives a boresight directed away from the camera body; the paired LED-row directions define camera up/roll. The four LED disks are the method's physical registration features. This approximation is not a newly flight-calibrated extrinsic. Original and replacement global poses are:

| Quantity | Value |
| --- | --- |
| Original calibration ground-FLU position (m) | `[2.30587, 0.404252, 1.883873]` |
| Original calibration R_USD → ground FLU | `[0.1193142389722469, -0.07752388261846371, -0.9898253179234366]`<br>`[0.86760421188713, 0.49285849569082435, 0.065980563358385]`<br>`[0.4827287477395414, -0.8666490355669567, 0.12606508341597972]` |
| Replacement visual ground-FLU position (m) | `[1.9623443400859832, 0.2092694330215454, 1.913305879831314]` |
| Replacement visual R_USD → ground FLU | `[-0.7546025066261504, -0.3652366763219337, 0.5451396401499691]`<br>`[0.4812244165917924, 0.2567564311133991, 0.8381522510605095]`<br>`[-0.44609205089243614, 0.8948062948768394, -0.01798824002960764]` |

The parent-relative replacement is in the [MAHLI camera card](#camera-mahli). A recorded 81-ray aperture check found no housing blockage. Distant rover geometry can legitimately appear near the image edges; this finite check does not establish full-volume or full-workspace clearance.

<a id="d-clipping"></a>

### D.2 Camera housing measurements and selected near planes

Ten camera overrides have a recorded 9 × 9 ray-grid inspection. Near clipping removes opaque visualization housing surfaces while keeping the selected optical pose, and removes all other geometry closer than that plane as well. It is a rendering accommodation, not a measured focus limit. Every recorded override has zero remaining housing intersections and zero other-rover intersections inside the near plane. The positive retained counts below are legitimate distant rover intersections and must not be classified as housing artifacts. These are historical finite samples, not fresh renderer runs or a complete FOV-clearance proof.

| Camera | Near/far clip (m) | Ray grid | Housing hits remaining | Other rover hits retained | Other rover hits clipped |
| --- | --- | --- | --- | --- | --- |
| mastcam_left | `[0.18, 200.0]` | `[9, 9]` | 0 | 0 | 0 |
| mastcam_right | `[0.07, 200.0]` | `[9, 9]` | 0 | 0 | 0 |
| navcam_left_a | `[0.03, 200.0]` | `[9, 9]` | 0 | 0 | 0 |
| navcam_left_b | `[0.03, 200.0]` | `[9, 9]` | 0 | 2 | 0 |
| hazcam_rear_left_a | `[0.03, 200.0]` | `[9, 9]` | 0 | 31 | 0 |
| hazcam_rear_right_a | `[0.03, 200.0]` | `[9, 9]` | 0 | 43 | 0 |
| hazcam_rear_left_b | `[0.03, 200.0]` | `[9, 9]` | 0 | 43 | 0 |
| hazcam_rear_right_b | `[0.03, 200.0]` | `[9, 9]` | 0 | 41 | 0 |
| chemcam_rmi | `[0.05, 200.0]` | `[9, 9]` | 0 | 0 | 0 |
| mardi | `[0.05, 200.0]` | `[9, 9]` | 0 | 16 | 0 |

The depth intervals are measured forward distances from the selected optical center. Object names here identify specific inspected surfaces and are retained because they distinguish housing from legitimate rover geometry; this is not an exhaustive source-file inventory.

| Camera | Inspected surface | Classification | Measured forward depth interval (m) |
| --- | --- | --- | --- |
| mastcam_left | MastCam | Housing | `[0.09257939375129516, 0.1648666459111579]` |
| mastcam_left | mast_03.001 | Housing | `[0.07834318197727917, 0.08742459063998591]` |
| mastcam_right | MastCam | Housing | `[0.04029431096738491, 0.06207088045865472]` |
| navcam_left_a | MastCam | Housing | `[0.009419894929304028, 0.015517751601899433]` |
| navcam_left_b | Dust Removal Tool | Other rover geometry | `[1.2194379135873044, 1.2945429726100675]` |
| navcam_left_b | MastCam | Housing | `[0.010753503028591571, 0.015619469679423152]` |
| hazcam_rear_left_a | lens_covers_rear | Housing | `[0.001034258654775913, 0.007939378448209503]` |
| hazcam_rear_left_a | HazCam - rear | Housing | `[0.0011604101790535844, 0.004723421877992122]` |
| hazcam_rear_left_a | wheel_03_L | Other rover geometry | `[0.22411860643014253, 0.704941856840267]` |
| hazcam_rear_left_a | suspension_steer_B_L | Other rover geometry | `[0.15144931599121708, 0.3433865599963362]` |
| hazcam_rear_right_a | lens_covers_rear | Housing | `[0.0005265912098179144, 0.007357205054295891]` |
| hazcam_rear_right_a | HazCam - rear | Housing | `[0.0006283690508567218, 0.004309285124743552]` |
| hazcam_rear_right_a | wheel_03_L | Other rover geometry | `[0.2027457230523088, 0.6855750822292148]` |
| hazcam_rear_right_a | suspension_steer_B_L | Other rover geometry | `[0.14934378723811675, 0.3608513242418565]` |
| hazcam_rear_left_b | lens_covers_rear | Housing | `[0.0016546512156703805, 0.007995522959960087]` |
| hazcam_rear_left_b | HazCam - rear | Housing | `[0.0017487204847190874, 0.005121662272204498]` |
| hazcam_rear_left_b | wheel_03_R | Other rover geometry | `[0.20022041100121882, 0.6768375580962933]` |
| hazcam_rear_left_b | suspension_steer_B_R | Other rover geometry | `[0.14510794752529363, 0.2720338456490434]` |
| hazcam_rear_right_b | lens_covers_rear | Housing | `[0.0018903904391022821, 0.00888422005824968]` |
| hazcam_rear_right_b | HazCam - rear | Housing | `[0.0020315933358387053, 0.005694216283635894]` |
| hazcam_rear_right_b | wheel_03_R | Other rover geometry | `[0.22634063208212216, 0.6966136106465624]` |
| hazcam_rear_right_b | suspension_steer_B_R | Other rover geometry | `[0.14740930119896928, 0.3928346357550423]` |
| hazcam_rear_right_b | wheel_03_L | Other rover geometry | `[0.6634202257377061, 0.675577738242051]` |
| chemcam_rmi | ChemCam | Housing | `[0.032315198432036785, 0.03457023552864207]` |
| mardi | MARDI.001 | Housing | `[0.019361409216874827, 0.023086955213909254]` |
| mardi | wheel_01_L | Other rover geometry | `[0.38237560021794015, 0.6956649844632444]` |

<a id="appendix-e"></a>

## Appendix E. Mission-scale reference and instrument scope

<a id="e-physical"></a>

### E.1 Published mission-scale dimensions

These are published mission-level reference values, not a bounding-box measurement of the current deployed-arm visual pose. The science payload's mass category differs from the arm mechanism plus turret-instrument category. The original source reference is the [NASA MSL press resource](https://mars.nasa.gov/internal_resources/823/), with the [JPL landing press kit](https://www.jpl.nasa.gov/news/press_kits/MSLLanding.pdf) providing mission context.

| Quantity | Reference value |
| --- | --- |
| Nominal mission mass (kg) | 899 |
| Overall reference length (m) | 3.0 |
| Overall reference width (m) | 2.8 |
| Overall reference height (m) | 2.1 |
| Wheel diameter (m) | 0.5 |
| Wheel width (m) | 0.4 |
| Science payload mass (kg) | 75 |

<a id="e-engineering"></a>

### E.2 Engineering sensors and unavailable flight parameters

Reference specifications come from the [JPL mobility paper](https://robotics.jpl.nasa.gov/media/documents/ROB-20-0040_R3.pdf). The proposed interface classifications are interpreted below against the current implementation; merely listing a flight sensor does not instantiate its measurement model.

| Sensor/interface | Flight-reference specification | Current MarsLab scope |
| --- | --- | --- |
| LN-200 IMU | 3 gyroscope + 3 accelerometer axes; 8 Hz; accuracy not published in the cited paper | Dynamic ideal IMU; chassis-origin mount; zero configured noise; no invented flight covariance |
| Six wheel-drive encoders | 64 Hz; 147456 ticks per output revolution | Joint-state/odometry interface; flight sampling and quantization not reproduced |
| Four steering encoders | 64 Hz; 147456 ticks per output revolution | Joint-state interface; flight sampling and quantization not reproduced |
| Three suspension resolvers | 64 Hz; published angle-accuracy range [0.51, 0.65] degrees | Joint-state interface; resolver accuracy/sampling not implemented as a separate sensor model |
| Engineering health telemetry | Motor current, motor temperature, body temperature, power generation and battery storage; complete channel count/calibration unavailable | Metadata classification only; no comprehensive electrical/thermal/health telemetry model |

<a id="e-science"></a>

### E.3 Science instrument component coverage

The inventory follows [NASA's science instrument overview](https://science.nasa.gov/mission/msl-curiosity/science-instruments/). Camera entries generate ordinary rendered images; metadata-only components do not generate scientific measurements.

| Instrument | Included component categories | Implementation status |
| --- | --- | --- |
| Mast Camera (`mastcam`) | Left and right Mastcam | Rendered cameras |
| Mars Hand Lens Imager (`mahli`) | Mars Hand Lens Imager | Rendered camera with visual-pose mount approximation |
| Mars Descent Imager (`mardi`) | Mars Descent Imager | Rendered camera; no descent-stage operational sequencing |
| Chemistry and Camera (`chemcam`) | RMI; LIBS ultraviolet, violet and visible/near-infrared spectrometers; LIBS laser | RMI rendered; spectroscopy and laser components are metadata only |
| Alpha Particle X-ray Spectrometer (`apxs`) | Alpha Particle X-ray Spectrometer | Metadata interface; no compositional measurement |
| Chemistry and Mineralogy (`chemin`) | X-ray diffraction and fluorescence | Metadata interface; no mineralogical measurement |
| Sample Analysis at Mars (`sam`) | Quadrupole mass spectrometer; gas chromatograph; tunable laser spectrometer | Metadata interfaces; no chemical measurement |
| Radiation Assessment Detector (`rad`) | Charged- and neutral-particle detectors | Metadata interface; no radiation measurement |
| Dynamic Albedo of Neutrons (`dan`) | Pulsed neutron generator; thermal- and epithermal-neutron detectors | Metadata interfaces; no neutron-transport measurement |
| Rover Environmental Monitoring Station (`rems`) | Boom 1: three wind sensors, air temperature, ground temperature. Boom 2: three wind sensors, air temperature, humidity. Additional pressure and ultraviolet channels | Metadata interfaces; no weather sensor physics |

MEDLI heat-shield entry instrumentation and cruise/descent-stage IMUs/antennas are excluded from this surface rover. The mission has neither a fitted LiDAR nor a GPS receiver. No public material reviewed supplies a complete flight per-link mass/inertia model; the analytic allocation remains an explicit approximation. Historical camera calibration references do not assert instrument health or active redundancy-chain selection in 2026.

<a id="appendix-f"></a>

## Appendix F. Structural reference locations

The following **84 reference points** are retained from the [NASA NAIF MSL structure comments](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/spk/msl_struct_v02.cmt). They include camera structural centers, arm/tool references, antenna pivots, science instruments, sample inlets, fiducials, observation trays and calibration targets. These are reference geometry, not proof that a corresponding actuator or sensor is simulated.

The `source frame` and `center ID` together define each source position. A ground-FLU coordinate is shown only where the retained construction record composed one. `Not composed` means an additional frame/kinematic transformation is required; it does not mean that the source position is zero or missing. Mechanical-origin-centered points (−76000) use the `[0.09002, 0, -1.1205]` m offset before the NAV-to-FLU rotation; NAV-centered points (−76) do not. The structure record's own `MSL_ROVER` position uses 0.09000000000000001 m rather than that 0.09002 m composition offset, a 20 µm precision difference retained here rather than silently reconciled. Structural camera offsets are not a substitute for the more detailed optical calibration positions in Appendix C.

| Reference point | Source frame | Center ID | Source position (m) | Composed ground-FLU position (m) |
| --- | --- | --- | --- | --- |
| MSL_ROVER | MSL_ROVER | -76 | `[0.09000000000000001, 0.0, -1.1205]` | `[0.09000000000000001, -0.0, 1.1205]` |
| MSL_HAZCAM_BACK_LEFT_A | MSL_ROVER | -76 | `[-0.9762, -0.4553, -0.7797999999999999]` | `[-0.9762, 0.4553, 0.7797999999999999]` |
| MSL_HAZCAM_BACK_LEFT_B | MSL_ROVER | -76 | `[-0.9757, 0.5522, -0.78]` | `[-0.9757, -0.5522, 0.78]` |
| MSL_HAZCAM_BACK_RIGHT_A | MSL_ROVER | -76 | `[-0.9768000000000001, -0.5555, -0.7796]` | `[-0.9768000000000001, 0.5555, 0.7796]` |
| MSL_HAZCAM_BACK_RIGHT_B | MSL_ROVER | -76 | `[-0.9752, 0.45189999999999997, -0.7801]` | `[-0.9752, -0.45189999999999997, 0.7801]` |
| MSL_HAZCAM_FRONT_LEFT_A | MSL_ROVER | -76 | `[1.0328, -0.0887, -0.7085]` | `[1.0328, 0.0887, 0.7085]` |
| MSL_HAZCAM_FRONT_LEFT_B | MSL_ROVER | -76 | `[1.0330000000000001, -0.1714, -0.7079]` | `[1.0330000000000001, 0.1714, 0.7079]` |
| MSL_HAZCAM_FRONT_RIGHT_A | MSL_ROVER | -76 | `[1.0326, 0.0779, -0.7081999999999999]` | `[1.0326, -0.0779, 0.7081999999999999]` |
| MSL_HAZCAM_FRONT_RIGHT_B | MSL_ROVER | -76 | `[1.0331, -0.0049, -0.7081000000000001]` | `[1.0331, 0.0049, 0.7081000000000001]` |
| MSL_MARDI | MSL_ROVER | -76 | `[0.7615999999999999, -0.6483, -0.7017]` | `[0.7615999999999999, 0.6483, 0.7017]` |
| MSL_RSM_HEAD | MSL_ROVER | -76 | `[0.8044, 0.5594, -1.9061]` | `[0.8044, -0.5594, 1.9061]` |
| MSL_MASTCAM_LEFT | MSL_RSM_HEAD | -76205 | `[-0.0374, -0.1258, -0.0653]` | Not composed |
| MSL_MASTCAM_RIGHT | MSL_RSM_HEAD | -76205 | `[0.0678, 0.1179, -0.0653]` | Not composed |
| MSL_NAVCAM_LEFT_A | MSL_RSM_HEAD | -76205 | `[0.11510000000000001, -0.2139, -0.0819]` | Not composed |
| MSL_NAVCAM_LEFT_B | MSL_RSM_HEAD | -76205 | `[0.1153, -0.2138, -0.033800000000000004]` | Not composed |
| MSL_NAVCAM_RIGHT_A | MSL_RSM_HEAD | -76205 | `[0.1132, 0.2097, -0.0817]` | Not composed |
| MSL_NAVCAM_RIGHT_B | MSL_RSM_HEAD | -76205 | `[0.1141, 0.20980000000000001, -0.034100000000000005]` | Not composed |
| MSL_CHEMCAM_RMI | MSL_RSM_HEAD | -76205 | `[0.0752, -0.1116, -0.2138]` | Not composed |
| MSL_CHEMCAM_LIBS_LASER | MSL_CHEMCAM_RMI | -76243 | `[0.0, 0.0, 0.0]` | Not composed |
| MSL_CHEMCAM_LIBS_CAM | MSL_CHEMCAM_RMI | -76243 | `[0.0, 0.0, 0.0]` | Not composed |
| MSL_RA_BASE | MSL_ROVER | -76000 | `[0.8275, -0.5616, 0.2248]` | `[0.91752, 0.5616, 0.8957]` |
| MSL_RA_SHOULDER_AZ | MSL_RA_BASE | -76300 | `[0.285, 0.1095, 0.041]` | Not composed |
| MSL_RA_SHOULDER_EL | MSL_RA_SHOULDER_AZ | -76301 | `[0.15589999999999998, 0.0, 0.0]` | Not composed |
| MSL_RA_ELBOW | MSL_RA_SHOULDER_EL | -76302 | `[0.8262999999999999, 0.0, 0.0]` | Not composed |
| MSL_RA_WRIST | MSL_RA_ELBOW | -76303 | `[0.7865, 0.0, 0.0]` | Not composed |
| MSL_RA_TURRET | MSL_RA_WRIST | -76304 | `[-0.1444, -0.1694, -0.1674]` | Not composed |
| MSL_RA_TURRET_HEAD | MSL_RA_TURRET | -76305 | `[0.0, 0.0, -0.0718]` | Not composed |
| MSL_MAHLI_REF | MSL_MAHLI_REF | -76306 | `[0.2983, 0.0, -0.01]` | Not composed |
| MSL_APXS_REF | MSL_APXS_REF | -76306 | `[0.299, 0.0, -0.0102]` | Not composed |
| MSL_PADS_REF | MSL_PADS_REF | -76306 | `[0.2915, 0.0, 0.0]` | Not composed |
| MSL_DRT_REF | MSL_DRT_REF | -76306 | `[0.2966, 0.0, -0.015000000000000001]` | Not composed |
| MSL_CHIMRA_REF | MSL_CHIMRA_REF | -76306 | `[0.35579999999999995, 0.0, -0.0741]` | Not composed |
| MSL_MAHLI | MSL_MAHLI_REF | -76310 | `[-0.0425, 0.0022, -0.0021]` | Not composed |
| MSL_APXS | MSL_APXS_REF | -76320 | `[0.0, 0.0, 0.0]` | Not composed |
| MSL_PADS | MSL_PADS_REF | -76330 | `[0.0, 0.0, 0.0]` | Not composed |
| MSL_DRT | MSL_DRT_REF | -76340 | `[0.0, 0.0, 0.0]` | Not composed |
| MSL_CHIMRA | MSL_CHIMRA_REF | -76350 | `[0.0, 0.0, 0.0]` | Not composed |
| MSL_HGA_AZ | MSL_ROVER | -76000 | `[-0.27240000000000003, -0.3873, -0.3078]` | `[-0.18238000000000004, 0.3873, 1.4283000000000001]` |
| MSL_HGA_EL | MSL_HGA_AZ | -76122 | `[0.0, -0.0023, -0.0]` | Not composed |
| MSL_HGA | MSL_HGA_EL | -76124 | `[0.21000000000000002, 0.0, 0.0]` | Not composed |
| MSL_DAN_PNG | MSL_ROVER | -76000 | `[-0.87, 0.5, 0.31]` | `[-0.77998, -0.5, 0.8105]` |
| MSL_DAN_DE | MSL_ROVER | -76000 | `[-0.87, -0.5, 0.31]` | `[-0.77998, 0.5, 0.8105]` |
| MSL_DAN_DE_CTN | MSL_ROVER | -76000 | `[-0.95, -0.5, 0.31]` | `[-0.85998, 0.5, 0.8105]` |
| MSL_DAN_DE_CETN | MSL_ROVER | -76000 | `[-0.79, -0.5, 0.31]` | `[-0.69998, 0.5, 0.8105]` |
| MSL_RAD | MSL_ROVER | -76000 | `[0.0746, -0.35300000000000004, -0.015000000000000001]` | `[0.16462, 0.35300000000000004, 1.1355]` |
| MSL_REMS_UVS | MSL_ROVER | -76000 | `[0.5156, 0.24649999999999997, -0.0235]` | `[0.6056199999999999, -0.24649999999999997, 1.1440000000000001]` |
| MSL_REMS_BOOM1_TIP | MSL_ROVER | -76000 | `[0.6057, 0.7323, -0.4256]` | `[0.69572, -0.7323, 1.5461]` |
| MSL_REMS_BOOM2_TIP | MSL_ROVER | -76000 | `[0.9181, 0.5662, -0.3926]` | `[1.0081200000000001, -0.5662, 1.5131000000000001]` |
| MSL_SAM_1_INLET | MSL_ROVER | -76000 | `[0.7127, 0.1754, -0.0304]` | `[0.80272, -0.1754, 1.1509]` |
| MSL_SAM_2_INLET | MSL_ROVER | -76000 | `[0.6462, 0.1519, -0.0304]` | `[0.73622, -0.1519, 1.1509]` |
| MSL_CHEMIN_INLET | MSL_ROVER | -76000 | `[0.6747, -0.1227, -0.028399999999999998]` | `[0.76472, 0.1227, 1.1489]` |
| MSL_FD_RESTRAINT_PORT | MSL_ROVER | -76000 | `[-0.8249000000000001, -0.4661, -0.12769999999999998]` | `[-0.7348800000000001, 0.4661, 1.2482]` |
| MSL_FD_RESTRAINT_SBRD | MSL_ROVER | -76000 | `[-0.8246, 0.4674, -0.1281]` | `[-0.73458, -0.4674, 1.2486000000000002]` |
| MSL_FD_DECK_SIDE_PORT | MSL_ROVER | -76000 | `[0.4093, -0.4424, -0.00039999999999999996]` | `[0.49932, 0.4424, 1.1209]` |
| MSL_FD_DECK_FRONT_PORT | MSL_ROVER | -76000 | `[0.782, -0.30269999999999997, -0.0007]` | `[0.87202, 0.30269999999999997, 1.1212]` |
| MSL_FD_DECK_CENTER_PORT | MSL_ROVER | -76000 | `[0.782, -0.001, -0.0006]` | `[0.87202, 0.001, 1.1211]` |
| MSL_FD_DECK_CENTER_SBRD | MSL_ROVER | -76000 | `[0.7822, 0.22910000000000003, -0.0005]` | `[0.87222, -0.22910000000000003, 1.121]` |
| MSL_FD_DECK_FRONT_SBRD | MSL_ROVER | -76000 | `[0.7824000000000001, 0.43179999999999996, -0.00039999999999999996]` | `[0.8724200000000001, -0.43179999999999996, 1.1209]` |
| MSL_FD_OCM_PORT | MSL_ROVER | -76000 | `[0.9318, -0.0936, -0.016399999999999998]` | `[1.02182, 0.0936, 1.1369]` |
| MSL_FD_OCM_CENTER | MSL_ROVER | -76000 | `[0.9318, 0.0665, -0.053399999999999996]` | `[1.02182, -0.0665, 1.1739]` |
| MSL_FD_OCM_STARBOARD | MSL_ROVER | -76000 | `[0.9318, 0.1691, 0.0356]` | `[1.02182, -0.1691, 1.0849]` |
| MSL_SCI_OBS_TRAY | MSL_ROVER | -76000 | `[1.159, 0.518, 0.158]` | `[1.24902, -0.518, 0.9625]` |
| MSL_ENG_OBS_TRAY | MSL_ROVER | -76000 | `[1.222, 0.518, 0.158]` | `[1.31202, -0.518, 0.9625]` |
| MSL_BIT_BOX_1_TARGET | MSL_ROVER | -76000 | `[1.14, 0.15, 0.3058]` | `[1.23002, -0.15, 0.8147]` |
| MSL_BIT_BOX_2_TARGET | MSL_ROVER | -76000 | `[1.1504, 0.48410000000000003, 0.3882]` | `[1.24042, -0.48410000000000003, 0.7323000000000001]` |
| MSL_OCM_LOCATION_1 | MSL_ROVER | -76000 | `[0.9301, 0.2285, -0.007500000000000001]` | `[1.0201200000000001, -0.2285, 1.1280000000000001]` |
| MSL_OCM_LOCATION_2 | MSL_ROVER | -76000 | `[0.9301, 0.14109999999999998, 0.0292]` | `[1.0201200000000001, -0.14109999999999998, 1.0913000000000002]` |
| MSL_OCM_LOCATION_3 | MSL_ROVER | -76000 | `[0.9301, 0.0915, -0.0313]` | `[1.0201200000000001, -0.0915, 1.1518000000000002]` |
| MSL_OCM_LOCATION_4 | MSL_ROVER | -76000 | `[0.9301, 0.018199999999999997, 0.0176]` | `[1.0201200000000001, -0.018199999999999997, 1.1029]` |
| MSL_OCM_LOCATION_5 | MSL_ROVER | -76000 | `[0.9301, -0.2088, -0.0541]` | `[1.0201200000000001, 0.2088, 1.1746]` |
| MSL_OCM_LOCATION_6 | MSL_ROVER | -76000 | `[0.9523999999999999, -0.104, 0.08789999999999999]` | `[1.04242, 0.104, 1.0326]` |
| MSL_APXS_CALTARGET | MSL_ROVER | -76000 | `[1.049, -0.39120000000000005, 0.4698]` | `[1.13902, 0.39120000000000005, 0.6507000000000001]` |
| MSL_MAHLI_CALTARGET | MSL_ROVER | -76000 | `[1.049, -0.39120000000000005, 0.366]` | `[1.13902, 0.39120000000000005, 0.7545000000000001]` |
| MSL_CCAM_CAL1 | MSL_ROVER | -76000 | `[-0.8502, 0.5575000000000001, -0.1906]` | `[-0.76018, -0.5575000000000001, 1.3111000000000002]` |
| MSL_CCAM_CAL2 | MSL_ROVER | -76000 | `[-0.8502, 0.5313, -0.1906]` | `[-0.76018, -0.5313, 1.3111000000000002]` |
| MSL_CCAM_CAL3 | MSL_ROVER | -76000 | `[-0.8502, 0.5052, -0.1906]` | `[-0.76018, -0.5052, 1.3111000000000002]` |
| MSL_CCAM_CAL4 | MSL_ROVER | -76000 | `[-0.8502, 0.479, -0.1906]` | `[-0.76018, -0.479, 1.3111000000000002]` |
| MSL_CCAM_CAL5 | MSL_ROVER | -76000 | `[-0.8502, 0.4528, -0.1906]` | `[-0.76018, -0.4528, 1.3111000000000002]` |
| MSL_CCAM_CAL6 | MSL_ROVER | -76000 | `[-0.8365999999999999, 0.5445, -0.1731]` | `[-0.7465799999999999, -0.5445, 1.2936]` |
| MSL_CCAM_CAL7 | MSL_ROVER | -76000 | `[-0.8365999999999999, 0.5182, -0.1731]` | `[-0.7465799999999999, -0.5182, 1.2936]` |
| MSL_CCAM_CAL8 | MSL_ROVER | -76000 | `[-0.8365999999999999, 0.4921, -0.1731]` | `[-0.7465799999999999, -0.4921, 1.2936]` |
| MSL_CCAM_CAL9 | MSL_ROVER | -76000 | `[-0.8365999999999999, 0.4659, -0.1731]` | `[-0.7465799999999999, -0.4659, 1.2936]` |
| MSL_CCAM_CAL10 | MSL_ROVER | -76000 | `[-0.8356, 0.4385, -0.1718]` | `[-0.74558, -0.4385, 1.2923]` |
| MSL_MCAM_CAL | MSL_ROVER | -76000 | `[-0.37520000000000003, 0.514, -0.2189]` | `[-0.28518000000000004, -0.514, 1.3394000000000001]` |

