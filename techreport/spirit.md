# Spirit: MarsLab implementation technical report

**Inspection date:** 2026-10-27. **Scope:** the current working-tree Spirit profile, supplied assets, and shared Isaac Sim/ROS 2 runtime. Values below describe this implementation; source-derived quantities, geometry estimates, and simulation tuning are distinguished explicitly.

MarsLab implements Spirit as a six-wheel rover with passive rocker-bogie suspension, four steering joints, nine rendered cameras, and an idealized IMU. Its appearance comes from NASA's shared Spirit/Opportunity visualization model. Its camera records identify **MER-2, Spirit**, whereas Opportunity uses MER-1. MarsLab authored the articulation and dynamics; this is not a NASA flight dynamics model.

## 1. Runtime assets and visual provenance

The [Spirit profile](../configs/robots/spirit.yaml) selects [spirit.usda](../assets/robots/spirit/spirit.usda) for Isaac Sim and [spirit.urdf](../assets/robots/spirit/spirit.urdf) for the ROS robot description. The default scenario selects another rover, so Spirit must be selected explicitly. The shared scenario supplies terrain and Mars gravity, currently **3.72 m/s²**; these are environment settings, not properties embedded in Spirit's mass model.

The supplied USD contains the visual geometry, materials, bodies, joints, contact proxies, and camera prims. The companion URDF uses local COLLADA meshes and textures for ROS visualization. The technical appendices below preserve the model derivation, physical estimates, calibration coefficients, reference poses, inspection results, and hardware evidence in this document.

The upstream file is [NASA's Mars Exploration Rover — Spirit and Opportunity Blender model](https://github.com/nasa/NASA-3D-Resources/blob/11ebb4ee043715aefbba6aeec8a61746fad67fa7/3D%20Models/Mars%20Exploration%20Rover%20-%20Spirit%20and%20Opportunity/Mars%20Exploration%20Rover%20-%20Spirit%20and%20Opportunity.blend), pinned to commit `11ebb4ee043715aefbba6aeec8a61746fad67fa7`. Conversion evaluated animation frame **1243**. The conversion retained **32,562 source triangles** across **40 assigned physical objects** and excluded **23 helpers**. Physical arm meshes were retained even where their source visibility flags hid them; rig cubes, transform helpers, and shadow planes were excluded.

The mesh was rotated and translated into **X forward, Y left, Z up**, with origin at nominal ground between the middle wheels. Wheel placement was made laterally symmetric, and wheel radii were adjusted to **0.13 m** while preserving source hub widths. Thus this is a modified visualization, not a dimensional survey. Arm, mast, antenna, and payload remain fixed at the selected visual pose. The Blender source and an automated rebuild workflow are not distributed; the supplied USD, URDF, meshes, and textures are the runtime assets. Attribution is recorded in [LICENSE-NASA-3D-RESOURCES.txt](../LICENSE-NASA-3D-RESOURCES.txt) and [LICENSE-NAIF.txt](../LICENSE-NAIF.txt).

## 2. Kinematics, mass, and contact

There are **15 rigid links and 14 joints**: two rockers, two bogies, four corner steering joints, and six wheel drives. Joint count is not the number of independent coordinates: the right rocker mimics the negative left rocker angle. The [differential implementation](../marslab/robots/differential.py) establishes the corresponding PhysX relationship and keeps the rockers passive. Wheels rotate about +Y; steering rotates about +Z. Suspension limits of ±π radians are numerical envelopes; steering limits are ±1.2 radians. Neither is documented as a measured flight hard stop.

| Geometry/control quantity | Implemented value | Interpretation |
| --- | --- | --- |
| Wheel radius | 0.130 m | Mission-size target; visual wheels adjusted to match. |
| Front-to-rear wheel-center distance | 1.212032 m | Derived from visualization geometry. |
| Corner-wheel center track | 1.060973 m | Derived from visualization geometry. |
| Middle-wheel center track | 0.950000 m | Derived from visualization geometry. |
| Steering-axis offset | 0.105778 m | Geometry-derived controller input. |
| Left front/middle/rear centers, m | `(0.711794, 0.530486, 0.130)`; `(0, 0.475000, 0.130)`; `(-0.500238, 0.530486, 0.130)` | Right centers mirror Y. |
| Total mass | 185.0 kg | Selected nominal mission value, not independently measured. |

NASA's [Spirit overview](https://science.nasa.gov/mission/mer-spirit/) reports 185 kg. The historical evidence also includes an archival 180 kg design figure rather than treating the sources as identical. Published overall dimensions or dimensions “at wheelbase” should not be substituted for tire-center coordinates: MarsLab's controller uses the derived centers above.

| Link group | Count × mass | Group total | Assignment basis |
| --- | --- | --- | --- |
| Chassis and fixed payload | 1 × 158.8 kg | 158.8 kg | Residual after the allocations below. |
| Wheels | 6 × 1.5 kg | 9.0 kg | Engineering estimate. |
| Steering carriers | 4 × 0.8 kg | 3.2 kg | Engineering estimate. |
| Rockers | 2 × 4.0 kg | 8.0 kg | Engineering estimate. |
| Bogies | 2 × 3.0 kg | 6.0 kg | Engineering estimate. |
| **Total** | **15 links** | **185.0 kg** | No public flight per-link mass distribution was identified in the recorded derivation. |

Wheel inertia uses a solid cylinder with the source width. Chassis and suspension inertia use uniform thin shells over their assigned triangles, weighted by surface area. Consequently, heavy internal equipment is not placed according to an equipment-level mass budget. The nominal aggregate center of mass is **(0.096086, 0.015576, 0.627869) m** in the ground FLU frame. The estimated inertia about that center, expressed in FLU axes, is:

```text
I [kg m²] = [[49.799396,  0.689749, -3.086133],
            [ 0.689749, 41.556863, -0.266507],
            [-3.086133, -0.266507, 62.165619]]
```

URDF stores full symmetric link tensors; USD stores equivalent principal moments and principal-axis orientations. Positive moments and valid tensor structure establish mathematical consistency, not agreement with Spirit's flight mass properties.

Contact comprises **six cylindrical wheels and one chassis box**, the latter measuring **1.0 × 0.7 × 0.35 m**, centered at **(0.05, 0, 0.48) m**. The solar panels, suspension, arm, mast, and antennas have no contact geometry; self-collision is disabled. Wheel static/dynamic friction is **0.6/0.5**, with zero restitution. Chassis linear/angular damping is **0.5/12.0**, and rocker/bogie damping is **75/50**. These are simulation settings, not measured flight dampers or identified Martian soil parameters. The contact model cannot substantiate panel strikes, arm clearance, wheel sinkage, or soil excavation.

## 3. Driving and ROS interfaces

The [shared rover controller](../marslab/robots/rover_control.py) consumes velocity commands and coordinates six wheel drives and four steering joints. Spirit's current command caps are **4 m/s** linear velocity and **0.07 rad/s** yaw rate, with a **0.5 s** command timeout. Wheel acceleration rate is **0.5 rad/s²**, steering ramp rate **2.0 rad/s**, and steering alignment tolerance **0.02 rad**. The 4 m/s command cap is an application setting, **80 times** the historical 0.05 m/s MER reference speed. It does not establish that the contact model can achieve or accurately simulate that speed. These configured rates and thresholds should not be interpreted as flight actuator performance measurements.

Acceleration-drive tuning uses wheel damping **1,000**, wheel drive limit **1,000,000**, brake stiffness **50,000**, steering stiffness **200,000**, steering damping **5,000**, and steering drive limit **100,000**. In particular, an acceleration-drive limit is not evidence of a motor's physical torque rating. Electrical power, motor current, thermal state, and solar charging are not represented by these gains.

Under the default `rover` namespace, commands use `/rover/cmd_vel`; outputs include `/rover/joint_states`, `/rover/odom`, `/rover/imu`, and `/rover/imu_noisy`. Primary Navcam-left publishes `/rover/rgb/image_raw` and `/rover/rgb/camera_info`; the other eight cameras use `/rover/cameras/<name>/image_raw` and matching `camera_info`. The [sensor graph builder](../marslab/ros2_bridge/sensor_graph_builder.py) uses camera-specific optical frames. Wheel odometry has zero configured slip bias and zero angular-rate noise, which does **not** prohibit physical wheel slip in contact simulation.

## 4. Camera placement and calibration

All nine cameras render **1024 × 1024** images and attach to `Body_Chassis` under `Sensors/<name>`. There is no articulated mast or arm to move their mounts. The following are rounded YAML camera-link poses in FLU coordinates; roll/pitch/yaw are degrees, not raw USD optical Euler angles. Their distinct coordinate conventions are handled by [camera mounting](../marslab/sensors/camera_mount.py).

| Camera | Position X, Y, Z (m) | Roll, pitch, yaw (°) | Horizontal FOV (°) | Near clip (m) |
| --- | --- | --- | --- | --- |
| `navcam_left` | 0.463452, 0.059836, 1.540868 | 0.233, -0.203, -0.754 | 45.8345 | 0.06 |
| `navcam_right` | 0.462802, -0.140508, 1.541310 | 0.296, -0.296, -0.577 | 45.8537 | 0.06 |
| `pancam_left` | 0.488541, 0.109260, 1.540896 | -0.343, -0.032, -0.655 | 16.0004 | 0.06 |
| `pancam_right` | 0.485911, -0.189231, 1.541827 | -0.435, 0.085, 1.343 | 16.0523 | 0.06 |
| `hazcam_front_left` | 0.606185, 0.043367, 0.524891 | -1.362, 44.533, -2.332 | 125.3412 | 0.05 |
| `hazcam_front_right` | 0.605777, -0.055065, 0.525306 | -1.181, 44.493, -2.270 | 125.7148 | 0.05 |
| `hazcam_rear_left` | -0.352830, -0.027840, 0.510359 | -0.778, 33.474, 178.818 | 126.1784 | 0.01 |
| `hazcam_rear_right` | -0.352856, 0.071599, 0.510484 | -0.875, 33.199, 178.862 | 126.7893 | 0.01 |
| `microscopic_imager` | 0.512452, 0.088431, 0.389603 | ≈0, ≈0, -30.000 | 24.2529 | 0.01 |

Far clipping is **200 m** throughout. Individual NAIF sources are [Navcam left](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_nl_20031204_c174.ti), [Navcam right](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_nr_20031204_c175.ti), [Pancam left F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f2_20031204_c177.ti), [Pancam right F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f2_20031204_c185.ti), [front Hazcam left](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_fl_20031204_c58.ti), [front Hazcam right](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_fr_20031204_c59.ti), [rear Hazcam left](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_rl_20031204_c60.ti), [rear Hazcam right](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_rr_20031204_c61.ti), and [MI F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_mi_f2_20031204_c172.ti).

The YAML records nominal focal lengths of **14.67 mm** for Navcam, **42.97 mm** for Pancam, **5.58 mm** for Hazcam, and **20.13 mm** for MI. However, every camera specifies a horizontal FOV. In that branch, [camera_spawner.py](../marslab/sensors/camera_spawner.py) computes focal length from the current USD aperture and requested FOV, and sets vertical aperture from image aspect ratio. It does not directly apply the recorded millimeter focal length. Original principal-point offsets, separate calibrated vertical FOVs, and CAHVOR distortion coefficients are retained as evidence but are not fully reproduced by the centered pinhole rendering.

Pancam uses the **F2 red-stereo calibration** for both eyes; MI uses **F2, cover open**. The official [MER camera product specification, Sections 2.3–2.4](https://pds-imaging.jpl.nasa.gov/documentation/MER_camsis_v4_9-25-07.pdf) distinguishes these filter/cover states. MarsLab renders ordinary RGB images, without changing spectral transmission, filter wheels, dust-cover state, CCD response, or science radiometric calibration.

The MI mount is particularly approximate. MarsLab placed its virtual pinhole on the front face of the visualization's small optics box, using `arm_turret` triangles 1500 and 1501. It looks about 30° right of forward. The original extended-arm calibration pose is preserved in [Appendix C](#spirit-mi-derivation), but is **not** the active mount. The source mesh does not resolve the physical entrance pupil. Both MER robots share this stowed geometry proxy while retaining separate calibration records. This virtual camera cannot reproduce close-focus microscopy or arm-based focusing.

Navcam/Pancam and front Hazcam near clips bypass opaque visualization housings. Recorded 9 × 9 ray audits explain the chosen values, but clipping removes **all** geometry inside the near plane, including some nearby arm fragments. It is not an optical minimum focus distance. These historical audits also do not replace a fresh rendered visibility test.

## 5. IMU, missing instrumentation, and NASA comparison

The simulated IMU is at chassis translation **(0, 0, 0)** with zero local rotation and **8 Hz** requested sampling. It reads simulated gravity and has zero configured accelerometer/gyro noise. The [recorded NASA PDS IMU reference](https://pds.nasa.gov/ds-view/pds/viewContext.jsp?identifier=urn:nasa:pds:context:instrument:imu.mer2&version=1.2) describes an LN-200S and distinguishes 400 Hz sampling from 8 Hz accumulated spacecraft data. MarsLab's rate is a chosen approximation, not proof of a required surface-operation cadence or a surveyed flight mounting location.

| Topic | Official hardware/evidence | Current MarsLab consequence |
| --- | --- | --- |
| Camera count | Nine cameras on each rover; the tenth camera belongs to the lander. [Maki et al., 2003](https://www-robotics.jpl.nasa.gov/media/documents/maki-jgr-2003je002077.pdf) | Nine rover cameras; no descent-camera omission from the surface vehicle. |
| Mast stereo geometry | Approximately 0.20 m Navcam and 0.30 m Pancam baselines, with movable mast pointing. [Maki et al., Table 3](https://www-robotics.jpl.nasa.gov/media/documents/maki-jgr-2003je002077.pdf) | Individual calibrated placements preserve approximately those separations; mast pointing is fixed. |
| MI and science payload | MI is arm-mounted; Spirit also carries Mini-TES, APXS, Mössbauer spectroscopy, RAT, and magnets. [NASA science instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/) | Only MI contributes a rendered image. Other payload descriptions/visible geometry do not provide science measurement emulators or an operating RAT. |
| Mission history | Spirit lost wheel functionality and ultimately became immobilized. [NASA Spirit overview](https://science.nasa.gov/mission/mer-spirit/) | All six drives remain available; historical failures, soil entrapment, and mission degradation are not replayed. |
| Range sensing | MER engineering cameras supported stereo ranging. [Maki et al., 2003](https://www-robotics.jpl.nasa.gov/media/documents/maki-jgr-2003je002077.pdf) | No LiDAR; both synthetic depth acquisition and depth publication are disabled. Reserved YAML depth/LiDAR topic names do not create sensors. |
| Engineering telemetry | The hardware inventory in Appendix E lists encoders, potentiometers, contact switches, and housekeeping channels. | Joint states supply the implemented mobility joints; listed arm/antenna sensors and housekeeping interfaces are descriptive metadata, not additional simulated channels. |

## 6. Verification boundaries

Read-only configuration, XML, and OpenUSD inspection confirmed 15 URDF links, eight revolute plus six continuous joints, 15 USD rigid bodies, 40 USD visual meshes, seven colliders, and nine cameras. URDF mass sums to 185.0 kg; USD sums to 185.0000031 kg because of stored floating-point precision. Source and runtime-code inspection established the distinctions above. No fresh Isaac Sim drive, rendered capture, ROS launch, terrain-contact experiment, or flight-telemetry comparison was performed. Recorded mass-tensor and ray-audit results remain derivation evidence. The model supports approximate mobility, rendered perception, and ROS integration; flight dynamics, soil interaction, science radiometry, and instrument deployment need further implementation and validation.

<a id="spirit-appendices"></a>

## Technical appendices: consolidated implementation evidence

These appendices are self-contained technical records. Values are retained at their recorded floating-point precision to preserve reconstruction information; this precision is **not** a statement of measurement accuracy. Repeated calibration aliases are identified, while source coordinates and current simulation coordinates remain separate. The historical sensor evidence was collected on **2026-10-22**; the implementation inspection above is later.

Contents: [A — frames and physical properties](#spirit-physical); [B — camera calibration](#spirit-calibration); [C — MI mounting derivation](#spirit-mi-derivation); [D — rendering audits](#spirit-render-audit); [E — hardware inventory and limits](#spirit-instruments); [F — source register](#spirit-sources).

<a id="spirit-physical"></a>

## Appendix A. Frames, geometry, and physical properties

### A.1 Coordinate transformations and construction

Use column-vector coordinates. The visualization transform is `p_ground = R_visual p_visual + t_visual`:

```text
R_visual =
  [ 0.0, -1.0, 0.0 ]
  [ 1.0, 0.0, 0.0 ]
  [ 0.0, 0.0, 1.0 ]
```

`t_visual [m] = (-0.39703237265348434, 6.881852944691976e-06, 0.002056402751089398)`.

The NASA MER navigation convention is X forward, Y right, Z down. Its conversion is `p_ground = R_nav p_nav + t_nav`:

```text
R_nav =
  [ 1, 0, 0 ]
  [ 0, -1, 0 ]
  [ 0, 0, -1 ]
```

`t_nav [m] = (0, 0, 0.29)`. The 0.29 m vertical offset combines nominal body clearance from [JPL surface mobility, §2.1](https://robotics.jpl.nasa.gov/media/documents/tradeoffs_ijrr_07.pdf) with the navigation-origin definition at the bottom panel between middle wheels in the [MER-2 structures SPK](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/spk/mer2_struct_ver11.bsp). It is not a rover-specific optical/mechanical survey. The mechanical origin being **0.29 m forward** of the navigation origin is a distinct horizontal offset, not another height correction.

The [PLACES SIS §2.1.1](https://planetarydata.jpl.nasa.gov/w10n/msl/msl_places/document/PLACES_PDS_SIS.pdf) is retained as a general frame-convention reference; it describes MSL and is not a Spirit mounting survey. The current chassis reference equals ground FLU: its additional NASA-ground-to-chassis translation is (0, 0, 0) m. Steering sign inversion is disabled (`negate_steer = false`).

At source frame 1243, genuine physical meshes, including hidden arm parts, were retained. Named rig transforms, non-mesh lighting/camera helpers, pivot-material geometry, and shadow planes were excluded; **vertex count alone was never an exclusion criterion**. Source `right` objects were assigned to physical left where the coordinate transform required it. Wheel geometry was moved to exact physics centers, symmetrized laterally, and radially scaled to 0.13 m while preserving hub width. Chassis/payload geometry includes the fixed mast, arm, antenna, and payload; the 15 body assignments are a simulation partition, not flight subsystem boundaries.

| Quantity | Recorded value (m) |
| --- | --- |
| wheel radius | 0.13 |
| wheelbase | 1.2120322799310088 |
| steering axle offset | 0.10577812464907765 |
| track steer | 1.0609725341200829 |
| track middle | 0.9500002264976501 |

The six wheel centers equal the corresponding wheel-link origins in A.2. Passive suspension limits are ±π rad in both USD and URDF; corner steering is limited to ±1.2 rad. The right rocker is coupled to the negative left angle. The model's masses, collision shapes, drive gains, damping, friction, and solver settings are MarsLab constructions.

### A.2 Link origins, local centers of mass, and full tensors

For each link, `origin` is its nominal ground-FLU origin (m); `COM_local` is relative to that origin in the aligned local axes (m). `I_local` is the full inertia about the link COM in those axes (kg m²); `principal` gives its ascending eigenvalues. The minute numerical asymmetry of some stored off-diagonal entries is retained. These are engineering estimates, not flight measurements.

#### Body_Chassis

Mass **158.8 kg**; `origin = (0.0, 0.0, 0.0)`; `COM_local = (0.10152446466490919, 0.01814587343597275, 0.6945021625121687)`.

```text
I_local [kg m²] =
  [ 39.24171144180523, 0.7053872464771085, -2.683968455902145 ]
  [ 0.7053872464771087, 30.8514115343005, -0.07447931930157761 ]
  [ -2.683968455902145, -0.07447931930157815, 51.503542565817945 ]
```

`principal [kg m²] = (30.79140314412789, 38.73773546690159, 52.067526930894175)`.

#### Body_RockerLeft

Mass **4.0 kg**; `origin = (0.22003603726625443, 0.3657357667883237, 0.36396284181702265)`; `COM_local = (0.056226182311081785, -0.006109187605853605, -0.02443418508843581)`.

```text
I_local [kg m²] =
  [ 0.03420255485000018, -0.032421066152354516, 0.06185048436172913 ]
  [ -0.032421066152354516, 0.3719923073581094, 0.010061129856562101 ]
  [ 0.061850484361729186, 0.010061129856562101, 0.3569276371185565 ]
```

`principal [kg m²] = (0.019530308477150874, 0.3665524280076403, 0.377039762841875)`.

#### Body_BogieLeft

Mass **3.0 kg**; `origin = (-0.2268720492720604, 0.3389466678102811, 0.2964259215079559)`; `COM_local = (-0.028066720498709452, 0.048348361433922904, -0.046568699049899104)`.

```text
I_local [kg m²] =
  [ 0.02615619304134699, 0.009033455162128487, 0.005940648093727005 ]
  [ 0.009033455162128487, 0.14183182803181077, 0.010653904955182161 ]
  [ 0.005940648093727005, 0.010653904955182161, 0.14170821827999025 ]
```

`principal [kg m²] = (0.025229813264598867, 0.13115809797363812, 0.15330832811491102)`.

#### Body_WheelLeftFront

Mass **1.5 kg**; `origin = (0.7117942646145821, 0.5304862670600414, 0.13)`; `COM_local = (0.0, 0.0, 0.0)`.

```text
I_local [kg m²] =
  [ 0.009618299360667165, 0.0, 0.0 ]
  [ 0.0, 0.012675000000000002, 0.0 ]
  [ 0.0, 0.0, 0.009618299360667165 ]
```

`principal [kg m²] = (0.009618299360667165, 0.009618299360667165, 0.012675000000000002)`.

#### Body_SteerLeftFront

Mass **0.8 kg**; `origin = (0.7117942646145821, 0.5304862670600414, 0.17191444117653495)`; `COM_local = (2.7867381067747665e-05, -0.0056338625303070655, -0.020830155127176675)`.

```text
I_local [kg m²] =
  [ 0.0012156075968744323, -1.2543687346600053e-07, 1.374248543850598e-07 ]
  [ -1.2543687351040946e-07, 0.0011538448721667288, -0.00013992035455464568 ]
  [ 1.3742485437395758e-07, -0.00013992035455464568, 0.001800420714213713 ]
```

`principal [kg m²] = (0.0011248646346693598, 0.001215607654531121, 0.0018294008940543927)`.

#### Body_WheelLeftMiddle

Mass **1.5 kg**; `origin = (0.0, 0.4750001132488251, 0.13)`; `COM_local = (0.0, 0.0, 0.0)`.

```text
I_local [kg m²] =
  [ 0.009537505817415975, 0.0, 0.0 ]
  [ 0.0, 0.012675000000000002, 0.0 ]
  [ 0.0, 0.0, 0.009537505817415975 ]
```

`principal [kg m²] = (0.009537505817415975, 0.009537505817415975, 0.012675000000000002)`.

#### Body_WheelLeftRear

Mass **1.5 kg**; `origin = (-0.5002380153164268, 0.5304862670600414, 0.13)`; `COM_local = (0.0, 0.0, 0.0)`.

```text
I_local [kg m²] =
  [ 0.009537510585793668, 0.0, 0.0 ]
  [ 0.0, 0.012675000000000002, 0.0 ]
  [ 0.0, 0.0, 0.009537510585793668 ]
```

`principal [kg m²] = (0.009537510585793668, 0.009537510585793668, 0.012675000000000002)`.

#### Body_SteerLeftRear

Mass **0.8 kg**; `origin = (-0.5002380153164268, 0.5304862670600414, 0.1592677064620269)`; `COM_local = (3.2679903319010606e-06, -0.005666036364995519, -0.008159529003121863)`.

```text
I_local [kg m²] =
  [ 0.001216024105004135, 1.96170990562905e-09, 5.6040641172039333e-08 ]
  [ 1.96170990562905e-09, 0.0011543636539482454, -0.00013997225791440027 ]
  [ 5.6040641172039333e-08, -0.00013997225791440027, 0.0018009134187842335 ]
```

`principal [kg m²] = (0.0011253618213242418, 0.00121602410211821, 0.001829915254294163)`.

#### Body_RockerRight

Mass **4.0 kg**; `origin = (0.220035620033741, -0.36574334154526394, 0.36396281201470027)`; `COM_local = (0.056257953126770344, 0.006097927629400479, -0.02444795414161055)`.

```text
I_local [kg m²] =
  [ 0.03421491488132511, 0.0324243456411728, 0.06188232492931106 ]
  [ 0.0324243456411728, 0.37219329910110305, -0.010062631092439545 ]
  [ 0.06188232492931106, -0.010062631092439545, 0.35711677466567143 ]
```

`principal [kg m²] = (0.019538228644832057, 0.36674719653700444, 0.37723956346626303)`.

#### Body_BogieRight

Mass **3.0 kg**; `origin = (-0.22687246650457382, -0.3389536167184512, 0.29642598111260066)`; `COM_local = (-0.028066778599403652, -0.0483482883326517, -0.04656869746912709)`.

```text
I_local [kg m²] =
  [ 0.02615616724788096, -0.009033311064962038, 0.005940638397530534 ]
  [ -0.009033311064962038, 0.14183186266797393, -0.010653909873715117 ]
  [ 0.005940638397530534, -0.010653909873715117, 0.14170821862944177 ]
```

`principal [kg m²] = (0.0252298097361108, 0.13115810644099385, 0.15330833236819194)`.

#### Body_WheelRightFront

Mass **1.5 kg**; `origin = (0.7117942646145821, -0.5304862670600414, 0.13)`; `COM_local = (0.0, 0.0, 0.0)`.

```text
I_local [kg m²] =
  [ 0.009609554090103894, 0.0, 0.0 ]
  [ 0.0, 0.012675000000000002, 0.0 ]
  [ 0.0, 0.0, 0.009609554090103894 ]
```

`principal [kg m²] = (0.009609554090103894, 0.009609554090103894, 0.012675000000000002)`.

#### Body_SteerRightFront

Mass **0.8 kg**; `origin = (0.7117942646145821, -0.5304862670600414, 0.17191463489163047)`; `COM_local = (2.73690742084165e-05, 0.005667337397005201, -0.02079344971247507)`.

```text
I_local [kg m²] =
  [ 0.0012162725388197794, 1.2522014345428544e-07, 1.3740548283625033e-07 ]
  [ 1.2522014345428544e-07, 0.00115466201059527, 0.00013997687030704588 ]
  [ 1.3740548282514808e-07, 0.00013997687030703476, 0.001801216568359987 ]
```

`principal [kg m²] = (0.0011256584454796875, 0.001216272596194414, 0.0018302200761009342)`.

#### Body_WheelRightMiddle

Mass **1.5 kg**; `origin = (0.0, -0.4750001132488251, 0.13)`; `COM_local = (0.0, 0.0, 0.0)`.

```text
I_local [kg m²] =
  [ 0.009537505817415975, 0.0, 0.0 ]
  [ 0.0, 0.012675000000000002, 0.0 ]
  [ 0.0, 0.0, 0.009537505817415975 ]
```

`principal [kg m²] = (0.009537505817415975, 0.009537505817415975, 0.012675000000000002)`.

#### Body_WheelRightRear

Mass **1.5 kg**; `origin = (-0.5002380153164268, -0.5304862670600414, 0.13)`; `COM_local = (0.0, 0.0, 0.0)`.

```text
I_local [kg m²] =
  [ 0.009537504625322107, 0.0, 0.0 ]
  [ 0.0, 0.012675000000000002, 0.0 ]
  [ 0.0, 0.0, 0.009537504625322107 ]
```

`principal [kg m²] = (0.009537504625322107, 0.009537504625322107, 0.012675000000000002)`.

#### Body_SteerRightRear

Mass **0.8 kg**; `origin = (-0.5002380153164268, -0.5304862670600414, 0.17191509682762748)`; `COM_local = (-2.2846073062243732e-06, 0.005663285489436398, -0.02080034607134945)`.

```text
I_local [kg m²] =
  [ 0.001216143977255671, -2.0106474707404234e-09, 5.617602554242041e-08 ]
  [ -2.0106474707404234e-09, 0.0011545100043741901, 0.00013998180467083012 ]
  [ 5.617602554242041e-08, 0.00013998180467083012, 0.0018010565463952412 ]
```

`principal [kg m²] = (0.0011255042456687415, 0.001216143974371073, 0.0018300623079852874)`.

### A.3 Aggregate mass properties and estimation method

Total mass is **185.0 kg**. Nominal ground-FLU aggregate COM is `(0.0960858261500372, 0.015575639537681702, 0.627869209206479)` m. The aggregate tensor about that COM, in FLU axes, is:

```text
I_aggregate [kg m²] =
  [ 49.79939622491091, 0.6897494247936405, -3.086132706525749 ]
  [ 0.6897494247936405, 41.55686263240846, -0.2665072547907428 ]
  [ -3.0861327065257487, -0.2665072547907432, 62.165618573087436 ]
```

Wheels use solid-cylinder moments with their source widths. For suspension and chassis/payload, triangle areas weight the centroid and surface second moments of a uniform thin shell; a watertight volume is not required. The residual chassis mass is 158.8 kg after the wheel/carrier/rocker/bogie estimates. The aggregate includes translated link moments about the aggregate COM. No NASA aggregate reference tensor, complete per-link mass set, or full flight tensor was supplied. Historical generation checks tested positive eigenvalues and principal-moment triangle inequalities. URDF carries the full tensors, while USD carries principal moments and axes; these checks establish mathematical plausibility rather than hardware fidelity.

<a id="spirit-calibration"></a>

## Appendix B. Complete individual camera calibration records

### B.1 Reading the records

All nine records describe cameras, with **1024 × 1024 calibration and photoactive dimensions** and **0.012 mm pixels**. Kernel `PIXEL_SAMPLES`, `PIXEL_LINES`, and `CAHVOR_DIMS` agree with those dimensions. The kernel FOV is a polygon (`FOV_SHAPE = POLYGON`, `FOV_CLASS_SPEC = CORNERS`) with eight ordered unit boundary vectors in the listed NAIF camera frame; `FOV_FRAME` equals that frame. Native `BORESIGHT = (0, 0, 1)` and `FOV_CENTER_PIXEL = (511.5, 511.5)` are common. These are source-model definitions, not a claim that the runtime reproduces the polygonal projection.

`C`, `A`, `H`, and `V` are the source CAHV center, axis, horizontal vector, and vertical vector. `O` and `R` preserve the optical-axis/radial terms; Hazcams also retain `E` and the exact model designation **CAHVORE3,0.37**. `HS/VS`, `HC/VC`, and `THETA` retain the source scale, center, and angular terms. `POS` and `QUAT` are the original calibration reference pose: the MER kernel explicitly defines `QUAT` in **engineering order `(s1, s2, s3, c)`**, scalar last, rather than SPICE scalar-first order. Raw vectors remain in their source calibration convention.

Each current rotation matrix below maps USD graphics-camera basis vectors into ground FLU; its third column points opposite the viewing direction. The accompanying USD RPY is therefore different from the camera-link FLU RPY used by ROS/YAML in Section 4. `boresight_FLU` is the current viewing direction. Mast cameras have their calibration reference quaternion removed to produce a canonical forward/level PMA head, then are fixed to the chassis. Hazcams are rigid body-fixed. MI instead uses the explicit stowed proxy in Appendix C.

The current renderer uses the central ray of a pinhole approximation. It does not apply radial/fisheye distortion, filter spectral response, microscope close focus, dust-cover transmission, or detector response. All records below remain useful calibration evidence even when the corresponding quantity is inactive in that renderer. Nominal focal length and independently derived vertical FOV must not be confused with the FOV-controlled runtime projection described in Section 4.

<a id="spirit-cal-navcam-left"></a>

### B.2 navcam_left

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_nl_20031204_c174.ti); frame `MER-2_NAVCAM_LEFT`; calibration `MER_CAL_174_SN_112.cahvor`; model `CAHVOR`.

Mast calibration quaternion removed to canonical forward/level PMA head.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (45.83446131, 45.840762989999995) |
| fx / fy (pixels) | (1188.254864, 1188.344549) |
| Derived principal point (pixels) | (469.930313, 516.903291) |
| Current ground-FLU optical center (m) | (0.46345157753611543, 0.059835644765946674, 1.5408684599516322) |
| Current USD-camera RPY in FLU (degrees) | (90.20304135827315, 0.2327106501132536, -90.75350730437171) |
| Current boresight in FLU | (0.9999070566557189, -0.013165113561308048, 0.0035437035732407036) |
| Mount interpretation | mast_reference_pose |

```text
R_ground_from_USD_camera =
  [ -0.013150695841750751, -0.003596838747413546, -0.9999070566557189 ]
  [ -0.9999052769951232, -0.004014576219687102, 0.013165113561308048 ]
  [ -0.004061555882118784, 0.9999854728588818, -0.0035437035732407036 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 14.67 |
| IFOV_NOMINAL | 0.0468677 |
| IFOV_HORIZONTAL | 0.04480397 |
| IFOV_VERTICAL | 0.04481013 |
| IFOV | 0.04480705 |
| CAHVOR_HS | 1188.254864 |
| CAHVOR_HC | 469.930313 |
| CAHVOR_VS | 1188.344549 |
| CAHVOR_VC | 516.903291 |
| CAHVOR_THETA | -1.570189 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (469.93031287, 516.90329089) |
| DISTORTION_PIXEL | (317.90442672, 482.97864067) |
| CAHVOR_C | (0.427748, 0.11446, -1.248564) |
| CAHVOR_A | (-0.989991, -0.011243, 0.140682) |
| CAHVOR_H | (-450.458717, -1193.412639, 75.082092) |
| CAHVOR_V | (-344.660526, 4.426849, 1249.216269) |
| CAHVOR_O | (-0.98714, 0.115434, 0.110584) |
| CAHVOR_R | (0.019876, -0.014281, 0.020876) |
| CAHVOR_POS | (0.45781, 0.02779, -1.09668) |
| CAHVOR_QUAT | (0.070093, 0.001171, 0.997401, -0.016658) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.36565281, 0.3653392, 0.85605215 ]
  [ 0.0, 0.38860797, 0.92140319 ]
  [ -0.3587112, 0.35908628, 0.86161669 ]
  [ -0.38565562, 0.00029913, 0.92264275 ]
  [ -0.36012624, -0.3595755, 0.86082202 ]
  [ -0.00048295, -0.39029473, 0.92068985 ]
  [ 0.36649473, -0.36735021, 0.85483065 ]
  [ 0.39313965, -0.00035611, 0.91947871 ]
```

<a id="spirit-cal-navcam-right"></a>

### B.3 navcam_right

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_nr_20031204_c175.ti); frame `MER-2_NAVCAM_RIGHT`; calibration `MER_CAL_175_SN_113.cahvor`; model `CAHVOR`.

Mast calibration quaternion removed to canonical forward/level PMA head.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (45.85365279, 45.83355084) |
| fx / fy (pixels) | (1209.160516, 1209.718102) |
| Derived principal point (pixels) | (519.184563, 524.80122) |
| Current ground-FLU optical center (m) | (0.4628023010286607, -0.14050849655036057, 1.5413101320566778) |
| Current USD-camera RPY in FLU (degrees) | (90.29583249010743, 0.29617540465390296, -90.5751757389349) |
| Current boresight in FLU | (0.9999360157636376, -0.0100650964843747, 0.00516315906229953) |
| Mount interpretation | mast_reference_pose |

```text
R_ground_from_USD_camera =
  [ -0.010038407693522723, -0.005214858552348427, -0.9999360157636376 ]
  [ -0.9999362527723556, -0.005117052309677708, 0.0100650964843747 ]
  [ -0.005169212953475001, 0.9999733101567957, -0.00516315906229953 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 14.67 |
| IFOV_NOMINAL | 0.0468677 |
| IFOV_HORIZONTAL | 0.04482273 |
| IFOV_VERTICAL | 0.04480308 |
| IFOV | 0.04481291 |
| CAHVOR_HS | 1209.160516 |
| CAHVOR_HC | 519.184563 |
| CAHVOR_VS | 1209.718102 |
| CAHVOR_VC | 524.80122 |
| CAHVOR_THETA | -1.570393 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (519.18456275, 524.80122027) |
| DISTORTION_PIXEL | (507.38426042, 520.61729313) |
| CAHVOR_C | (0.435019, -0.085753, -1.249092) |
| CAHVOR_A | (-0.988104, -0.049381, 0.145646) |
| CAHVOR_H | (-452.075834, -1233.255239, 79.557598) |
| CAHVOR_V | (-342.762187, -13.628939, 1273.248298) |
| CAHVOR_O | (-0.989044, -0.039669, 0.142189) |
| CAHVOR_R | (0.0003, -0.004874, 0.018766) |
| CAHVOR_POS | (0.45781, 0.02779, -1.09668) |
| CAHVOR_QUAT | (0.070093, 0.001171, 0.997401, -0.016658) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.36083623, 0.36047786, 0.86014704 ]
  [ -0.0, 0.38785644, 0.9217198 ]
  [ -0.36218903, 0.36217702, 0.85886374 ]
  [ -0.39044071, 0.00018727, 0.92062806 ]
  [ -0.36475067, -0.3644002, 0.85683688 ]
  [ -8.9e-07, -0.39092983, 0.92042048 ]
  [ 0.36328689, -0.36327974, 0.85793383 ]
  [ 0.3886693, -0.00018287, 0.92137731 ]
```

<a id="spirit-cal-pancam-left"></a>

### B.4 pancam_left

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f2_20031204_c177.ti); frame `MER-2_PANCAM_LEFT_F2`; calibration `MER_CAL_177_SN_104_F_2.cahvor`; model `CAHVOR`.

Mast calibration quaternion removed to canonical forward/level PMA head.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (16.000425869999997, 15.99878907) |
| fx / fy (pixels) | (3556.419415, 3556.791275) |
| Derived principal point (pixels) | (518.019386, 498.280082) |
| Current ground-FLU optical center (m) | (0.48854077214233194, 0.1092599168895244, 1.5408956824778548) |
| Current USD-camera RPY in FLU (degrees) | (90.0317701112145, -0.34340384468210666, -90.65514279629791) |
| Current boresight in FLU | (0.9999345122520077, -0.011430824811844556, 0.0005544830566805155) |
| Mount interpretation | mast_reference_pose |

```text
R_ground_from_USD_camera =
  [ -0.0114339443314687, -0.0004859262949273053, -0.9999345122520077 ]
  [ -0.9999166680140038, 0.005999439298267329, 0.011430824811844556 ]
  [ 0.005993491870149688, 0.9999818851377971, -0.0005544830566805155 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 42.97 |
| IFOV_NOMINAL | 0.01600068 |
| IFOV_HORIZONTAL | 0.01564069 |
| IFOV_VERTICAL | 0.01563909 |
| IFOV | 0.01563989 |
| CAHVOR_HS | 3556.419415 |
| CAHVOR_HC | 518.019386 |
| CAHVOR_VS | 3556.791275 |
| CAHVOR_VC | 498.280082 |
| CAHVOR_THETA | -1.570293 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (518.01938639, 498.28008211) |
| DISTORTION_PIXEL | (523.38930593, 458.80236254) |
| CAHVOR_C | (0.401265, 0.163027, -1.245082) |
| CAHVOR_A | (-0.989679, -0.046318, 0.135607) |
| CAHVOR_H | (-349.960356, -3576.595824, 44.320764) |
| CAHVOR_V | (-10.046627, -28.461764, 3591.399075) |
| CAHVOR_O | (-0.991056, -0.047812, 0.124591) |
| CAHVOR_R | (0.022997, 0.024872, -0.407146) |
| CAHVOR_POS | (0.45781, 0.02779, -1.09668) |
| CAHVOR_QUAT | (0.070093, 0.001171, 0.997401, -0.016658) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.13787056, 0.13779231, 0.98081853 ]
  [ -0.0, 0.13923181, 0.99025982 ]
  [ -0.13793245, 0.13799277, 0.98078164 ]
  [ -0.13921182, 7.418e-05, 0.99026262 ]
  [ -0.13782703, -0.13773803, 0.98083227 ]
  [ -1.63e-06, -0.13909353, 0.99027925 ]
  [ 0.13775984, -0.13781262, 0.98083123 ]
  [ 0.13914176, -6.528e-05, 0.99027247 ]
```

**Selected filter: F2.** All eight preserved calibration alternatives are listed below. These identify source calibration variants, not eight simultaneously instantiated cameras or a functioning filter wheel.

| Variant | Source kernel | Calibration ID |
| --- | --- | --- |
| F1 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f1_20031204_c176.ti) | MER_CAL_176_SN_104_F_1.cahvor |
| F2 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f2_20031204_c177.ti) | MER_CAL_177_SN_104_F_2.cahvor |
| F3 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f3_20031204_c178.ti) | MER_CAL_178_SN_104_F_3.cahvor |
| F4 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f4_20031204_c179.ti) | MER_CAL_179_SN_104_F_4.cahvor |
| F5 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f5_20031204_c180.ti) | MER_CAL_180_SN_104_F_5.cahvor |
| F6 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f6_20031204_c181.ti) | MER_CAL_181_SN_104_F_6.cahvor |
| F7 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f7_20031204_c182.ti) | MER_CAL_182_SN_104_F_7.cahvor |
| F8 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pl_f8_20031204_c183.ti) | MER_CAL_183_SN_104_F_8.cahvor |

<a id="spirit-cal-pancam-right"></a>

### B.5 pancam_right

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f2_20031204_c185.ti); frame `MER-2_PANCAM_RIGHT_F2`; calibration `MER_CAL_185_SN_103_F_2.cahvor`; model `CAHVOR`.

Mast calibration quaternion removed to canonical forward/level PMA head.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (16.05233289, 16.04333049) |
| fx / fy (pixels) | (3550.646478, 3552.647123) |
| Derived principal point (pixels) | (502.248577, 494.089683) |
| Current ground-FLU optical center (m) | (0.4859109330989981, -0.18923116240825627, 1.5418272350808633) |
| Current USD-camera RPY in FLU (degrees) | (89.91484594832231, -0.4346573861635769, -88.65619841233261) |
| Current boresight in FLU | (0.9997241334166005, 0.02344031457817279, -0.0014861752599846937) |
| Mount interpretation | mast_reference_pose |

```text
R_ground_from_USD_camera =
  [ 0.023450937198211574, 0.001307902501193115, -0.9997241334166005 ]
  [ -0.9996962059446179, 0.00761888918495278, -0.02344031457817279 ]
  [ 0.007586129741958483, 0.9999701205129256, 0.0014861752599846937 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 42.97 |
| IFOV_NOMINAL | 0.01600068 |
| IFOV_HORIZONTAL | 0.01569143 |
| IFOV_VERTICAL | 0.01568263 |
| IFOV | 0.01568703 |
| CAHVOR_HS | 3550.646478 |
| CAHVOR_HC | 502.248577 |
| CAHVOR_VS | 3552.647123 |
| CAHVOR_VC | 494.089683 |
| CAHVOR_THETA | -1.57023 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (502.24857671, 494.08968265) |
| DISTORTION_PIXEL | (416.88147058, 421.34700635) |
| CAHVOR_C | (0.413705, -0.135215, -1.246372) |
| CAHVOR_A | (-0.990622, -0.007005, 0.136451) |
| CAHVOR_H | (-474.046354, -3554.067848, 56.808555) |
| CAHVOR_V | (-4.611697, -13.887297, 3586.811043) |
| CAHVOR_O | (-0.993079, 0.017077, 0.116202) |
| CAHVOR_R | (0.022082, -0.033675, 0.611672) |
| CAHVOR_POS | (0.45781, 0.02779, -1.09668) |
| CAHVOR_QUAT | (0.070093, 0.001171, 0.997401, -0.016658) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.13839264, 0.13822202, 0.98068453 ]
  [ 0.0, 0.13960724, 0.99020696 ]
  [ -0.13831955, 0.13831689, 0.98068147 ]
  [ -0.13961299, 7.439e-05, 0.99020614 ]
  [ -0.13813329, -0.13796259, 0.98075762 ]
  [ -1.883e-05, -0.13948778, 0.99022379 ]
  [ 0.13821635, -0.138244, 0.9807063 ]
  [ 0.13963762, -9.171e-05, 0.99020267 ]
```

**Selected filter: F2.** All eight preserved calibration alternatives are listed below. These identify source calibration variants, not eight simultaneously instantiated cameras or a functioning filter wheel.

| Variant | Source kernel | Calibration ID |
| --- | --- | --- |
| F1 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f1_20031204_c184.ti) | MER_CAL_184_SN_103_F_1.cahvor |
| F2 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f2_20031204_c185.ti) | MER_CAL_185_SN_103_F_2.cahvor |
| F3 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f3_20031204_c186.ti) | MER_CAL_186_SN_103_F_3.cahvor |
| F4 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f4_20031204_c187.ti) | MER_CAL_187_SN_103_F_4.cahvor |
| F5 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f5_20031204_c188.ti) | MER_CAL_188_SN_103_F_5.cahvor |
| F6 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f6_20031204_c189.ti) | MER_CAL_189_SN_103_F_6.cahvor |
| F7 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f7_20031204_c190.ti) | MER_CAL_190_SN_103_F_7.cahvor |
| F8 | [NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_pr_f8_20031204_c191.ti) | MER_CAL_191_SN_103_F_8.cahvor |

<a id="spirit-cal-hazcam-front-left"></a>

### B.6 hazcam_front_left

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_fl_20031204_c58.ti); frame `MER-2_FRONT_HAZCAM_LEFT`; calibration `MER_CAL_58_SN_107.cahvore`; model `CAHVORE3,0.37`.

Rigid body-fixed camera.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (125.34122337000001, 125.21371665) |
| fx / fy (pixels) | (455.966429, 456.421531) |
| Derived principal point (pixels) | (515.289585, 511.510827) |
| Current ground-FLU optical center (m) | (0.606185, 0.043367, 0.524891) |
| Current USD-camera RPY in FLU (degrees) | (45.45873129120145, -0.9708613991325886, -91.37704372704533) |
| Current boresight in FLU | (0.712253962634595, -0.029009854220549205, -0.701322123613265) |
| Mount interpretation | body |

```text
R_ground_from_USD_camera =
  [ -0.024028183312669187, 0.7015104697137527, -0.712253962634595 ]
  [ -0.9995676815898111, -0.004783124425770559, 0.029009854220549205 ]
  [ 0.01694391713455556, 0.7126430962289032, 0.701322123613265 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 5.58 |
| IFOV_NOMINAL | 0.12321654 |
| IFOV_HORIZONTAL | 0.12252319 |
| IFOV_VERTICAL | 0.12239855 |
| IFOV | 0.12246087 |
| CAHVOR_HS | 455.966429 |
| CAHVOR_HC | 515.289585 |
| CAHVOR_VS | 456.421531 |
| CAHVOR_VC | 511.510827 |
| CAHVOR_THETA | -1.571117 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (515.2895848, 511.51082651) |
| DISTORTION_PIXEL | (515.68378893, 510.88172451) |
| CAHVOR_C | (0.606185, -0.043367, -0.234891) |
| CAHVOR_A | (0.712013, 0.037316, 0.701174) |
| CAHVOR_H | (353.340667, 474.872862, 350.820311) |
| CAHVOR_V | (44.010163, 16.904013, 683.916158) |
| CAHVOR_O | (0.712953, 0.038186, 0.700171) |
| CAHVOR_R | (3e-06, -0.013032, -0.00754) |
| CAHVOR_E | (0.000942, 0.00228, 0.001613) |
| CAHVOR_POS | (0.0, 0.0, 0.0) |
| CAHVOR_QUAT | (0.0, 0.0, 0.0, 1.0) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.70816374, 0.70560806, -0.02492766 ]
  [ -0.0, 0.88713447, 0.46151104 ]
  [ -0.70740183, 0.70667602, -0.01384426 ]
  [ -0.88806132, -0.00376415, 0.45970961 ]
  [ -0.70130197, -0.71251382, -0.02235189 ]
  [ 0.00610206, -0.88859365, 0.45865464 ]
  [ 0.71218043, -0.70123575, -0.03267199 ]
  [ 0.88868963, 0.00286468, 0.45850031 ]
```

<a id="spirit-cal-hazcam-front-right"></a>

### B.7 hazcam_front_right

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_fr_20031204_c59.ti); frame `MER-2_FRONT_HAZCAM_RIGHT`; calibration `MER_CAL_59_SN_109.cahvore`; model `CAHVORE3,0.37`.

Rigid body-fixed camera.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (125.71475136, 125.52920985) |
| fx / fy (pixels) | (455.036649, 455.360938) |
| Derived principal point (pixels) | (495.181923, 518.620215) |
| Current ground-FLU optical center (m) | (0.605777, -0.055065, 0.5253059999999999) |
| Current USD-camera RPY in FLU (degrees) | (45.501040960526836, -0.8426631436246454, -91.442457041099) |
| Current boresight in FLU | (0.712777677834595, -0.028259565943322733, -0.7008205040617871) |
| Mount interpretation | body |

```text
R_ground_from_USD_camera =
  [ -0.02517024288811526, 0.7009382575189314, -0.712777677834595 ]
  [ -0.999574995372149, -0.007157203326960645, 0.028259565943322733 ]
  [ 0.014706716143372926, 0.7131860441615926, 0.7008205040617871 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 5.58 |
| IFOV_NOMINAL | 0.12321654 |
| IFOV_HORIZONTAL | 0.12288832 |
| IFOV_VERTICAL | 0.12270695 |
| IFOV | 0.12279763 |
| CAHVOR_HS | 455.036649 |
| CAHVOR_HC | 495.181923 |
| CAHVOR_VS | 455.360938 |
| CAHVOR_VC | 518.620215 |
| CAHVOR_THETA | -1.570801 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (495.18192328, 518.6202153) |
| DISTORTION_PIXEL | (492.80271194, 518.87858283) |
| CAHVOR_C | (0.605777, 0.055065, -0.235306) |
| CAHVOR_A | (0.702176, -0.007688, 0.711962) |
| CAHVOR_H | (347.882684, 451.20496, 357.288613) |
| CAHVOR_V | (39.944126, -7.191921, 688.965306) |
| CAHVOR_O | (0.70176, -0.01292, 0.712296) |
| CAHVOR_R | (2.8e-05, -0.013534, -0.007456) |
| CAHVOR_E | (0.000568, 0.001915, 0.002274) |
| CAHVOR_POS | (0.0, 0.0, 0.0) |
| CAHVOR_QUAT | (0.0, 0.0, 0.0, 1.0) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.69998054, 0.71407664, -0.01103639 ]
  [ -0.0, 0.88927487, 0.45737316 ]
  [ -0.7029172, 0.70671558, -0.08037725 ]
  [ -0.89186653, 0.01950938, 0.45187773 ]
  [ -0.7362069, -0.67452623, -0.05489766 ]
  [ -0.02747922, -0.88878044, 0.45750871 ]
  [ 0.68831806, -0.72540773, -0.00136649 ]
  [ 0.88763839, -0.00857989, 0.46046114 ]
```

<a id="spirit-cal-hazcam-rear-left"></a>

### B.8 hazcam_rear_left

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_rl_20031204_c60.ti); frame `MER-2_REAR_HAZCAM_LEFT`; calibration `MER_CAL_60_SN_106.cahvore`; model `CAHVORE3,0.37`.

Rigid body-fixed camera.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (126.17842611, 126.39905652) |
| fx / fy (pixels) | (452.805133, 452.172169) |
| Derived principal point (pixels) | (511.464893, 522.339997) |
| Current ground-FLU optical center (m) | (-0.35283, -0.02784, 0.510359) |
| Current USD-camera RPY in FLU (degrees) | (56.52308745351583, -0.6493632959289707, 89.24765895325126) |
| Current boresight in FLU | (-0.8339541672845532, 0.017203127849975366, -0.5515654986136322) |
| Mount interpretation | body |

```text
R_ground_from_USD_camera =
  [ 0.013129607747007903, -0.5516774966129552, 0.8339541672845532 ]
  [ 0.9998495737125486, -0.002209601550618087, -0.017203127849975366 ]
  [ 0.011333284927363385, 0.8340545889759556, 0.5515654986136322 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 5.58 |
| IFOV_NOMINAL | 0.12321654 |
| IFOV_HORIZONTAL | 0.12334157 |
| IFOV_VERTICAL | 0.12355724 |
| IFOV | 0.12344941 |
| CAHVOR_HS | 452.805133 |
| CAHVOR_HC | 511.464893 |
| CAHVOR_VS | 452.172169 |
| CAHVOR_VC | 522.339997 |
| CAHVOR_THETA | -1.573266 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (511.46489323, 522.33999723) |
| DISTORTION_PIXEL | (512.90365133, 523.86900772) |
| CAHVOR_C | (-0.35283, 0.02784, -0.220359) |
| CAHVOR_A | (-0.820494, -0.017232, 0.571396) |
| CAHVOR_H | (-414.354735, -461.547168, 286.204206) |
| CAHVOR_V | (-170.157896, -9.813575, 669.513537) |
| CAHVOR_O | (-0.81851, -0.020424, 0.574129) |
| CAHVOR_R | (2.2e-05, -0.012974, -0.007563) |
| CAHVOR_E | (0.000972, 0.001178, 0.001015) |
| CAHVOR_POS | (0.0, 0.0, 0.0) |
| CAHVOR_QUAT | (0.0, 0.0, 0.0, 1.0) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.693755, 0.71529341, -0.08401983 ]
  [ -0.0, 0.89398583, 0.44809522 ]
  [ -0.69699978, 0.71522718, -0.05139443 ]
  [ -0.8900214, 0.00581612, 0.45588165 ]
  [ -0.71251062, -0.70140638, -0.01891315 ]
  [ 0.00209182, -0.89116847, 0.45366771 ]
  [ 0.71788858, -0.69546383, -0.03108142 ]
  [ 0.89337745, 0.01263464, 0.44912927 ]
```

<a id="spirit-cal-hazcam-rear-right"></a>

### B.9 hazcam_rear_right

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_rr_20031204_c61.ti); frame `MER-2_REAR_HAZCAM_RIGHT`; calibration `MER_CAL_61_SN_108.cahvore`; model `CAHVORE3,0.37`.

Rigid body-fixed camera.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (126.7892901, 126.88821420000001) |
| fx / fy (pixels) | (451.859829, 451.748587) |
| Derived principal point (pixels) | (501.118489, 527.211737) |
| Current ground-FLU optical center (m) | (-0.352856, 0.071599, 0.5104839999999999) |
| Current USD-camera RPY in FLU (degrees) | (56.79781962141884, -0.7318070234985746, 89.34045551861215) |
| Current boresight in FLU | (-0.8366075313795341, 0.016625200536205136, -0.5475504005533853) |
| Mount interpretation | body |

```text
R_ground_from_USD_camera =
  [ 0.011510029633514218, -0.5476818032917266, 0.8366075313795341 ]
  [ 0.9998521854818242, -0.0043829093477767474, -0.016625200536205136 ]
  [ 0.012772094779459193, 0.836675225191216, 0.5475504005533853 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 5.58 |
| IFOV_NOMINAL | 0.12321654 |
| IFOV_HORIZONTAL | 0.1239387 |
| IFOV_VERTICAL | 0.1240354 |
| IFOV | 0.12398705 |
| CAHVOR_HS | 451.859829 |
| CAHVOR_HC | 501.118489 |
| CAHVOR_VS | 451.748587 |
| CAHVOR_VC | 527.211737 |
| CAHVOR_THETA | -1.573709 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (501.11848888, 527.21173722) |
| DISTORTION_PIXEL | (501.95200061, 528.48206056) |
| CAHVOR_C | (-0.352856, -0.071599, -0.220484) |
| CAHVOR_A | (-0.81711, 0.006074, 0.57645) |
| CAHVOR_H | (-413.667588, -448.794903, 287.678977) |
| CAHVOR_V | (-170.387722, 1.125681, 673.049507) |
| CAHVOR_O | (-0.815498, 0.004208, 0.578744) |
| CAHVOR_R | (1.1e-05, -0.015912, -0.006998) |
| CAHVOR_E | (0.00092, 0.001679, 0.002273) |
| CAHVOR_POS | (0.0, 0.0, 0.0) |
| CAHVOR_QUAT | (0.0, 0.0, 0.0, 1.0) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.68838489, 0.72038493, -0.0846865 ]
  [ -0.0, 0.89558598, 0.44488848 ]
  [ -0.69313982, 0.71476842, -0.09307682 ]
  [ -0.89271059, 0.0176559, 0.45028443 ]
  [ -0.73029181, -0.6819058, -0.04096769 ]
  [ -0.01447497, -0.89334772, 0.44913285 ]
  [ 0.7072165, -0.70629605, -0.03147544 ]
  [ 0.89548087, 0.00808611, 0.44502654 ]
```

<a id="spirit-cal-microscopic-imager"></a>

### B.10 microscopic_imager

[Individual NAIF kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer2_mi_f2_20031204_c172.ti); frame `MER-2_MICROIMAGER_F2`; calibration `MER_CAL_172_SN_105_F_2.cahvor`; model `CAHVOR`.

Fixed stowed-arm visualization pose. MarsLab derives the virtual pinhole from the MI optics-box front face; original extended NASA calibration pose is retained in calibration_reference_pose. Not flight-calibrated stowed extrinsics.

| Derived optical or mounting quantity | Recorded value |
| --- | --- |
| Horizontal / vertical FOV (degrees) | (24.25288503, 24.28183593) |
| fx / fy (pixels) | (2370.886516, 2368.387193) |
| Derived principal point (pixels) | (493.647556, 514.329535) |
| Current ground-FLU optical center (m) | (0.5124521963424407, 0.08843081744597046, 0.38960254197268984) |
| Current USD-camera RPY in FLU (degrees) | (90.00005332252849, -3.473078704904294e-06, -120.00007441145014) |
| Current boresight in FLU | (0.8660247544209582, -0.5000011247279881, 9.306536878376931e-07) |
| Mount interpretation | fixed_stowed_arm_visualization |

```text
R_ground_from_USD_camera =
  [ -0.5000011247282525, -7.756607338780451e-07, -0.8660247544209582 ]
  [ -0.8660247544213034, 5.178234177121668e-07, 0.5000011247279881 ]
  [ 6.061665881124138e-08, 0.9999999999995651, -9.306536878376931e-07 ]
```

Source scalar parameters: focal length is mm; IFOV values are degrees per pixel; HS/HC/VS/VC are pixel-based source calibration terms; THETA is radians.

| Kernel parameter | Value |
| --- | --- |
| FOCAL_LENGTH | 20.13 |
| IFOV_NOMINAL | 0.03415545 |
| IFOV_HORIZONTAL | 0.02370761 |
| IFOV_VERTICAL | 0.02373591 |
| IFOV | 0.02372176 |
| CAHVOR_HS | 2370.886516 |
| CAHVOR_HC | 493.647556 |
| CAHVOR_VS | 2368.387193 |
| CAHVOR_VC | 514.329535 |
| CAHVOR_THETA | -1.569844 |

The raw boresight/distortion pixel values below retain their own precision; they are not replaced by the rounded derived principal point. C and POS retain source length coordinates (m); the remaining optical-model vectors retain native calibration units.

| Kernel parameter | Components in source order |
| --- | --- |
| BORESIGHT_PIXEL | (493.64755592, 514.32953506) |
| DISTORTION_PIXEL | (329.9558266, 383.30909144) |
| CAHVOR_C | (1.05888, -0.054903, 0.275421) |
| CAHVOR_A | (-0.005821, 0.05838, 0.998277) |
| CAHVOR_H | (26.031857, -2337.838852, 631.36997) |
| CAHVOR_V | (2365.204651, 57.405196, 525.651774) |
| CAHVOR_O | (-0.061672, 0.126116, 0.990097) |
| CAHVOR_R | (0.007629, -0.104219, 0.624037) |
| CAHVOR_POS | (1.048823, -0.053605, 0.328496) |
| CAHVOR_QUAT | (-0.027773, 0.011828, 0.707667, 0.705901) |

```text
FOV_BOUNDARY (8 ordered unit directions) =
  [ 0.20570406, 0.20553254, 0.95678745 ]
  [ 0.0, 0.20994095, 0.97771407 ]
  [ -0.20535731, 0.20565513, 0.95683559 ]
  [ -0.21017302, 0.00014309, 0.9776642 ]
  [ -0.20487538, -0.20466549, 0.95715104 ]
  [ -0.00038708, -0.21069242, 0.97755233 ]
  [ 0.20567972, -0.20676882, 0.95652627 ]
  [ 0.20996618, -0.00037786, 0.97770858 ]
```

<a id="spirit-mi-derivation"></a>

## Appendix C. Microscopic Imager mounting derivation

MarsLab identified the small optics box next to the contact feeler using [The Athena Microscopic Imager Investigation, Figure 1, page 1](https://ntrs.nasa.gov/api/citations/20030066751/downloads/20030066751.pdf) and the [NASA hardware photograph](https://science.nasa.gov/wp-content/uploads/2024/03/mi1-500.jpg). The shared NASA source mesh at frame 1243 provides `arm_turret` triangles **1500 and 1501**, with vertex triples **(1436, 1432, 1431)** and **(1436, 1431, 1435)**. These particular identifiers matter because they define the selected front face; they are not a general mesh-object inventory.

The virtual pinhole is the front-face center, its view direction is the outward normal, and image up follows turret-local +Z. This is MarsLab's geometry-derived construction, not a flight-calibrated entrance pupil.

| Source-space construction quantity | Value |
| --- | --- |
| Front-face center, local m | (0.06830248848254535, -0.03943445270196513, 0.03034990735705799) |
| Local forward normal | (0.8660252614946273, -0.5000002464530587, 2.0682048452482977e-07) |

```text
T_source_world_from_turret (4×4) =
  [ -9.26034658732533e-07, 1.0000003576278687, 1.8777086552290712e-07, 0.1278584599494934 ]
  [ -1.0000003576278687, -1.2784774980900693e-06, 2.0399468780851748e-07, -0.8411821126937866 ]
  [ 7.449639269907493e-07, -1.5735164993202488e-07, 0.9999997615814209, 0.357196182012558 ]
  [ 0.0, 0.0, 0.0, 1.0 ]
```

Apply the visualization-to-ground transform in Appendix A after the source object world transform. The resulting current center, orientation, and boresight are preserved in [B.10](#spirit-cal-microscopic-imager). Spirit and Opportunity share this mounting proxy because they use the same stowed geometry, while their individual optical calibration remains different. The mesh resolves no separate entrance pupil, dust-cover optical transmission, or close-focus response.

### Original extended-arm calibration reference

This original arm-reference pose is not stowed and is not used as the active mount. Retargeting to another arm pose requires the source POS/QUAT convention and a suitable arm transform; the current fixed-arm runtime does not perform this operation.

| Reference quantity | Value |
| --- | --- |
| Ground-FLU center (m) | (1.05888, 0.054903, 0.014578999999999953) |
| USD-camera RPY in FLU (degrees) | (0.36415341966023357, 2.9189597511660286, 89.35217911787119) |
| Boresight in FLU | (-0.0069309743802021965, -0.05084728106491435, -0.9986823897528416) |
| Mount | arm_reference_pose |

```text
R_ground_from_USD_camera_reference =
  [ 0.011291697129774922, -0.9999122257328743, 0.0069309743802021965 ]
  [ 0.9986387247168749, 0.011629768018296136, 0.05084728106491435 ]
  [ -0.05092342360626605, 0.006347387318432903, 0.9986823897528416 ]
```

The MI retains the **0.01 m** near plane without a special visibility exception or enlarged near clip. Its source F2 calibration denotes cover open, but this proxy does not model a physical cover state, cover transmission, or focus stacking.

<a id="spirit-render-audit"></a>

## Appendix D. Rendering near-plane inspections

These are **historical static ray inspections**, not a fresh render test. Each of the six inspected cameras used a **9 × 9 frustum-ray grid**. The near plane bypasses opaque lens/housing surfaces while preserving the camera pose; it also removes other objects nearer than that plane. Counts below are ray/geometry intersections and must not be interpreted as percentages of visible image pixels. The four mast-camera housings are source `mast_top`; front-Hazcam housings are `body`. Source object names remain here because they identify measured occluders.

| Camera | Clip range (m) | Housing hits after clip | Other-rover hits retained | Other-rover hits inside clip |
| --- | --- | --- | --- | --- |
| navcam_left | (0.06, 200.0) | 0 | 0 | 0 |
| navcam_right | (0.06, 200.0) | 0 | 0 | 0 |
| pancam_left | (0.06, 200.0) | 0 | 0 | 0 |
| pancam_right | (0.06, 200.0) | 0 | 0 | 0 |
| hazcam_front_left | (0.05, 200.0) | 0 | 62 | 43 |
| hazcam_front_right | (0.05, 200.0) | 0 | 40 | 6 |

Measured intervals are forward depths in each camera's viewing coordinates, in metres. They explain both housing removal and collateral clipping of nearby arm fragments.

### navcam_left

| Measured source component | Minimum / maximum forward depth (m) |
| --- | --- |
| mast_top | (0.010403770383767087, 0.04254760486455556) |

### navcam_right

| Measured source component | Minimum / maximum forward depth (m) |
| --- | --- |
| mast_top | (0.006708622328066532, 0.04341594294005592) |

### pancam_left

| Measured source component | Minimum / maximum forward depth (m) |
| --- | --- |
| mast_top | (0.009353732622439659, 0.03659993337093064) |

### pancam_right

| Measured source component | Minimum / maximum forward depth (m) |
| --- | --- |
| mast_top | (0.011854055831365073, 0.03933093732458509) |

### hazcam_front_left

| Measured source component | Minimum / maximum forward depth (m) |
| --- | --- |
| arm_base | (0.029171668805228514, 0.08804191668476333) |
| arm_joint1 | (0.032685275468917425, 0.06604798409047301) |
| arm_mount | (0.018571015680772435, 0.02824322514252401) |
| suspension_right_front_rocker | (0.16866638216698226, 0.3239364840871838) |
| suspension_right_front_wheel | (0.21958824793342707, 0.4625383146882466) |
| suspension_left_front_wheel | (0.25435490417991413, 0.44226783209086695) |
| suspension_right_front_axl | (0.3483402639275967, 0.3483402639275967) |
| suspension_left_front_rocker | (0.29563541277942484, 0.3503606453754436) |
| suspension_left_front_axl | (0.37523067873268745, 0.37523067873268745) |
| body | (0.0028496434885331642, 0.018766680353082512) |

### hazcam_front_right

| Measured source component | Minimum / maximum forward depth (m) |
| --- | --- |
| arm_joint1 | (0.03793767651212934, 0.06499857980273548) |
| suspension_right_front_wheel | (0.2631033046984533, 0.4546059898187751) |
| suspension_left_front_wheel | (0.24028280162649962, 0.4910946059576267) |
| suspension_left_front_rocker | (0.1653557244385702, 0.32584424869562745) |
| suspension_right_front_rocker | (0.3099716224224972, 0.3099716224224972) |
| suspension_right_front_axl | (0.32009180771683393, 0.32009180771683393) |
| suspension_left_front_axl | (0.34678885913666646, 0.34678885913666646) |
| body | (0.002854930917418134, 0.019375878157558354) |

No enlarged rendering override was recorded for rear Hazcams or MI: their configured range is 0.01–200 m. The audit does not prove exact optics, full-lens distortion, detector response, or collision clearance. Wheels, farther suspension, arm geometry, and terrain can remain visible beyond the near plane. These clipping distances are rendering accommodations, not measured flight near-focus limits.

<a id="spirit-instruments"></a>

## Appendix E. Hardware reference inventory and implementation limits

### E.1 Mission reference dimensions and mass selection

The historical MER-2 host description provides the following nominal quantities. They are reference evidence, not replacements for the current mesh-derived centers or the **4 m/s command cap**.

| Historical reference | Value | Qualification |
| --- | --- | --- |
| Recommended total mass | 185.0 kg | NASA mission summary and JPL telecommunications description: [mass_current](#spirit-source-mass-current), [mass_telecom](#spirit-source-mass-telecom) |
| Archival design mass | 180.0 kg | Original PDS host description; disagreement retained: [geometry](#spirit-source-geometry) |
| Wheel diameter | 0.26 m | [geometry](#spirit-source-geometry) |
| Dimensions at wheelbase, length × width | 1.41 × 1.22 m | Not explicit axle-center or tire-center separations. |
| Solar-panel length × width | 1.51 × 2.25 m | Published nominal envelope. |
| Deployed height | 1.54 m | Published nominal dimension. |
| Historical maximum speed | 0.05 m/s | Flight reference; not current simulation command cap. |
| Driven / steerable wheels | 6 / 4 | Nominal intact mechanism. |

No complete official per-link mass distribution or inertia tensors were located in the reviewed evidence. Published total mass and sparse individual instrument masses constrain an explicitly approximate partition; they do not certify it. The MER navigation-origin height is nominal, not a millimetre-accurate flight survey.

### E.2 Engineering instruments

The former planning labels `dynamic_ideal_imu`, `joint_state_interface`, and `metadata_interface` distinguish intended representation types, not an assertion that every listed channel is implemented. In particular, fixed arm and antenna geometry creates no arm/antenna encoder stream.

| Flight instrument | Count and reference specification | Current representation | Evidence |
| --- | --- | --- | --- |
| Litton LN-200S IMU | 1; 3 fiber-optic gyros + 3 silicon accelerometers; 0.75 kg; recorded accelerometer range 80 g; 400 Hz nominal sampling, 8 Hz accumulated data; inside rover, explicitly not at COM | Ideal dynamic IMU at chassis origin; requested 8 Hz, zero configured noise. EDL averaging evidence does not mandate a surface sampling rate. | [imu](#spirit-source-imu) |
| Wheel-drive rotary encoders | 6, inferred as one per independently driven wheel | Joint-state representation for the six drive joints; no detector model | [mobility](#spirit-source-mobility) |
| Steering magnetic encoders | 4 incremental encoders | Steering joint states; no separate magnetic sensor model | [potentiometers](#spirit-source-potentiometers) |
| Arm magnetic encoders | 5 incremental encoders | Historical inventory only; no arm articulation/channel | [potentiometers](#spirit-source-potentiometers) |
| High-gain antenna magnetic encoders | 2 incremental encoders | Historical inventory only; fixed antenna | [potentiometers](#spirit-source-potentiometers) |
| Steering potentiometers | 4 backup joint-angle sensors | No separate potentiometer model | [potentiometers](#spirit-source-potentiometers) |
| Arm potentiometers | 5 backup joint-angle sensors | Historical inventory only | [potentiometers](#spirit-source-potentiometers) |
| High-gain antenna potentiometers | 2 backup joint-angle sensors | Historical inventory only | [potentiometers](#spirit-source-potentiometers) |
| Suspension potentiometers | 3: left and right rocker–bogie relative angles; differential left/right rocker relative angle | Suspension joint states, without separate potentiometer response | [potentiometers](#spirit-source-potentiometers) |
| Wheel-motor current/voltage | Engineering telemetry; quantity unspecified | Descriptive metadata, no electrical telemetry emulator | [engineering_additional](#spirit-source-engineering-additional) |
| Reference solar cells | Irradiance/dust telemetry; quantity unspecified | Descriptive metadata, no solar-cell response model | [engineering_additional](#spirit-source-engineering-additional) |
| Warm electronics box temperature monitoring | Thermal telemetry; quantity unspecified | Descriptive metadata, no housekeeping thermal model | [engineering_additional](#spirit-source-engineering-additional) |
| MI contact/proximity switch | 1, at the arm-turret MI | Descriptive metadata, no contact-switch output | [science](#spirit-source-science) |

The 80 g field is preserved as a magnitude/range figure; the record does not establish whether this means ±80 g or a total span. Instrument masses are historical reference specifications, not extra rigid bodies to add to the already assigned 185 kg.

### E.3 Science payload and passive references

The following hardware specifications are attributed to [science](#spirit-source-science). Their representation status concerns current MarsLab behavior.

| Instrument | Mount, count, and reference specification | Current representation |
| --- | --- | --- |
| Pancam | Two components: left and right cameras | Rendered RGB cameras; no filter wheel/spectral radiometry |
| Microscopic Imager | One arm-turret camera | Rendered RGB stowed proxy; no close-focus science response |
| Mini-TES | 1 thermal-IR emission spectrometer; body-mounted with mast optical path; 2.4 kg; 0.235 × 0.163 × 0.155 m; 5.0–29.5 μm; selectable 8.0/20.0 mrad FOV | Descriptive inventory; no thermal-IR measurement emulator |
| Mössbauer spectrometer | 1 iron-mineralogy instrument on arm turret; sampled diameter 0.015–0.020 m | Descriptive inventory; no spectrum |
| APXS | 1 alpha-particle X-ray spectrometer on arm turret; sampled diameter 0.038 m; recorded dimensions (0.084, 0.052) m, axis labels unspecified | Descriptive inventory; no elemental/spectral measurement |
| Rock Abrasion Tool | 1 arm-turret tool; mass upper bound 0.72 kg | Passive tool description; no abrasion operation |
| Magnet array | 7 passive dust collectors: 4 RAT, 1 front capture, 1 front filter, 1 deck sweep | Passive references; no magnetic/dust collection physics |
| Calibration targets | Pancam deck sundial; Mössbauer target beneath panels also usable by APXS; APXS target inside dust doors; Mini-TES internal mast and external deck targets | Passive reference inventory; no calibration measurement workflow |

### E.4 Exclusions and scope limits

| Hardware outside the surface rover model | Recorded complement | Evidence |
| --- | --- | --- |
| Descent camera | 1 on lander radar bracket; 1024 × 1024; 45° × 45° FOV | [engineering_cameras](#spirit-source-engineering-cameras) |
| Backshell IMU | 1 | [imu](#spirit-source-imu) |
| Lander-petal encoders and potentiometers | 3 units in the source inventory | [potentiometers](#spirit-source-potentiometers) |

The reference complement describes the original rover rather than subsequent failures. The flight rover had neither LiDAR nor GPS. Spectrometer, environment, and housekeeping inventory entries do not claim physical sensor emulation. The nominal ground-height assumption, engineering mass partition, fixed instrument mechanisms, and geometry-derived MI mount remain material limits. Preparation and historical validation utilities are not a distributed rebuild workflow; the temporary upstream clone was removed, and the Blender source is reacquired upstream if reconstruction is required.

<a id="spirit-sources"></a>

## Appendix F. Primary evidence register

This register preserves the referenced publications and archive locations independently of the original metadata files. Some entries support historical design context rather than active runtime features; the camera-specific and MI-construction sources are linked at their relevant appendices.

<a id="spirit-source-science"></a>

- **science** — NASA, [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/).

<a id="spirit-source-engineering-cameras"></a>

- **engineering_cameras** — NASA JPL, [Mars Exploration Rover Engineering Cameras](https://www-robotics.jpl.nasa.gov/media/documents/maki-jgr-2003je002077.pdf). Locator: Table 3, page 4; sections 2.4.2–2.4.4, pages 5–7. DOI: 10.1029/2003JE002077.

<a id="spirit-source-imu"></a>

- **imu** — NASA PDS, [Mars Exploration Rover Spirit Inertial Measurement Unit](https://pds.nasa.gov/ds-view/pds/viewContext.jsp?identifier=urn:nasa:pds:context:instrument:imu.mer2&version=1.2).

<a id="spirit-source-mobility"></a>

- **mobility** — NASA JPL, [Mars Exploration Rover Mobility and Robotic Arm Operational Performance](https://robotics.jpl.nasa.gov/media/documents/MobIDDPerf90sols.pdf). Locator: section 3.1, page 2.

<a id="spirit-source-potentiometers"></a>

- **potentiometers** — NASA NTRS/JPL, [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf). Locator: Introduction, first page.

<a id="spirit-source-geometry"></a>

- **geometry** — NASA PDS, [Mars Exploration Rover 2 instrument host, version 1.0](https://pds.nasa.gov/data/pds4/context-pds4/instrument_host/spacecraft.mer2_1.0.xml). Locator: Rover on the Surface of Mars.

<a id="spirit-source-mass-current"></a>

- **mass_current** — NASA, [Spirit](https://science.nasa.gov/mission/mer-spirit/).

<a id="spirit-source-mass-telecom"></a>

- **mass_telecom** — NASA JPL, [Mars Exploration Rover Telecommunications System](https://descanso.jpl.nasa.gov/DPSummary/MER_article_cmp20051028.pdf). Locator: section 1.3/Table 1-2.

<a id="spirit-source-sun-finding"></a>

- **sun_finding** — NASA NTRS/JPL, [The Mars Exploration Rover Cameras: A Status Report](https://ntrs.nasa.gov/citations/20050175949).

<a id="spirit-source-engineering-additional"></a>

- **engineering_additional** — JPL author paper, Wiley primary publication, [Mars Exploration Rover mission](https://doi.org/10.1029/2002JE002038). Locator: abstract; section 3.8.2.

<a id="spirit-source-naif-camera-kernels"></a>

- **naif_camera_kernels** — NASA JPL NAIF, [MER camera instrument kernels](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/).

<a id="spirit-source-naif-frame-kernels"></a>

- **naif_frame_kernels** — NASA JPL NAIF, [MER reference frame kernels](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/fk/).

