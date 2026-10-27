# Opportunity: MarsLab Technical Report

**Implementation inspected:** 2026-10-27. This report describes the current working tree, including uncommitted implementation files. Opportunity is a MarsLab-authored mobile simulation derived from NASA visualization geometry and NASA/JPL camera records. Its articulated suspension, mass distribution, collisions, drives, and rendered sensors are simulation constructions; NASA did not supply or validate this dynamic model.

The entry point is [opportunity.yaml](../configs/robots/opportunity.yaml). Isaac Sim loads [opportunity.usda](../assets/robots/opportunity/opportunity.usda); ROS visualization and robot transforms use [opportunity.urdf](../assets/robots/opportunity/opportunity.urdf). The appendices consolidate the construction, mass properties, complete retained camera calibration, mounting derivations, visibility audits, and instrument reference data. This report can be read without the former standalone derivation and metadata files.

## Visual assets and provenance

Opportunity and Spirit share NASA's **Mars Exploration Rover – Spirit and Opportunity** Blender visualization. The pinned upstream is [NASA-3D-Resources, commit `11ebb4ee043715aefbba6aeec8a61746fad67fa7`](https://github.com/nasa/NASA-3D-Resources/tree/11ebb4ee043715aefbba6aeec8a61746fad67fa7/3D%20Models/Mars%20Exploration%20Rover%20-%20Spirit%20and%20Opportunity). Its source file is `Mars Exploration Rover - Spirit and Opportunity.blend`.

MarsLab evaluated the source at animation frame 1243. Its derivation records 32,562 retained physical triangles, including genuine arm meshes hidden from rendering in the original scene. Rig helpers, pivot helpers, camera transforms, and shadow planes were excluded by explicit object identity. The remaining geometry was divided among simulated links; arm, mast, antenna, solar panels, and payload stay in their fixed visualization poses.

The USD contains 40 physical visual mesh prims distributed among the 15 rigid links. It embeds visual geometry and references local texture assets; the URDF references the local COLLADA exports. The runtime does not load an alternate Opportunity GLB.

The original `.blend` and former upstream source archive are absent from the distributed tree. Their provenance survives in [LICENSE-NASA-3D-RESOURCES.txt](../LICENSE-NASA-3D-RESOURCES.txt). Running the supplied model does not require Blender or the removed archive; reproducing its construction requires reacquiring the pinned source and using generation tooling that is not a distributed rebuild workflow. NASA and the upstream contributors are credited there; [LICENSE-NAIF.txt](../LICENSE-NAIF.txt) separately records sensor-data attribution.

## Coordinate system and articulation

The rover reference is nominal ground between the middle wheels, with **X forward, Y left, Z up**. `Body_Chassis` uses that reference, so a camera's Z coordinate is approximately its height above nominal ground, not its height above the deck. The source geometry receives the recorded axis rotation and translation; source objects called `right` are assigned to the physical left where their geometry requires it. Wheel centers are made laterally symmetric and their radial geometry scaled to 0.13 m while retaining source widths.

| Articulated group | Joint count | Behavior |
| --- | ---: | --- |
| Rockers | 2 | Passive; right angle mimics negative left angle |
| Bogies | 2 | Passive rocker-to-bogie rotation |
| Corner steering carriers | 4 | Active steering about local +Z; limits ±1.2 rad |
| Wheels | 6 | Continuous drive about local +Y |

The model has **15 massive links and 14 joints**, comprising eight revolute and six continuous joints. The rocker coupling leaves 13 independent relative joint coordinates before contact constraints; this excludes the floating base. Rocker and bogie limits of ±π are numerical envelopes, not documented flight mechanism limits. Arm, mast, and antenna pointing add no simulated degrees of freedom.

Controller geometry is a 1.212032 m wheelbase, 1.060973 m steering-wheel track, 0.950000 m middle-wheel track, and 0.105778 m steering-axle offset. These are visualization-derived dimensions. They should not be interpreted as engineering-drawing tolerances. Real MER instruments were positioned by a five-revolute-joint arm with encoder and contact feedback; this fixed-arm model cannot reproduce that operation. [NASA/JPL MER mobility and robotic-arm paper](https://robotics.jpl.nasa.gov/media/documents/MobIDDPerf90sols.pdf).

## Mass, inertia, contact, and control

The URDF's assigned mass totals **185 kg**, matching NASA's mission-summary value. NASA also describes mast cameras approximately 1.5 m above the ground. These establish useful scale checks, but do not establish link masses or inertias. [NASA Opportunity mission overview](https://science.nasa.gov/mission/mer-opportunity/).

| Link family | Count | Mass per link | Subtotal |
| --- | ---: | ---: | ---: |
| Fixed chassis and payload | 1 | 158.8 kg | 158.8 kg |
| Rockers | 2 | 4.0 kg | 8.0 kg |
| Bogies | 2 | 3.0 kg | 6.0 kg |
| Steering carriers | 4 | 0.8 kg | 3.2 kg |
| Wheels | 6 | 1.5 kg | 9.0 kg |
| **Total** | **15** | — | **185.0 kg** |

Every subdivision in this table is a MarsLab engineering estimate. Wheel inertias use solid cylinders with the source widths. Chassis and suspension centers and tensors use area-weighted uniform thin shells over their assigned visualization triangles. That procedure provides explicit, internally usable dynamics without representing the actual distribution of electronics, batteries, structures, and instruments. No NASA aggregate flight tensor was adopted as a target; [Appendix A](#physical-register) preserves the complete assigned mass properties.

At the nominal reference configuration, the recorded aggregate center of mass is `(0.096086, 0.015576, 0.627869)` m. Its estimated inertia about that center, expressed in ground-FLU axes, is:

```text
I [kg m²] = [ 49.799396   0.689749  -3.086133
               0.689749  41.556863  -0.266507
              -3.086133  -0.266507  62.165619 ]
```

URDF stores each link's full symmetric tensor; USD stores principal moments and principal-axis orientation. The current USD's mass sum is 185.0000031 kg, consistent with float serialization of the 185 kg assignments. The derivation records historical positive-eigenvalue and principal-moment triangle checks; those assertions do not make the tensors flight measurements.

Contact uses **seven primitives**: six radius-0.13 m wheel cylinders and a chassis box of `1.0 × 0.7 × 0.35` m centered at `(0.05, 0, 0.48)` m. Suspension, mast, panels, antenna, and arm have no independent collision shapes; self-collision is disabled. Consequently, their visible surfaces cannot establish clearance, contact forces, or instrument collision safety.

The [main scenario](../configs/config.yaml) sets gravity to 3.72 m/s². Opportunity's YAML sets wheel static/dynamic friction to 0.6/0.5, restitution to zero, chassis angular/linear damping to 12/0.5, and rocker/bogie damping to 75/50. These are simulation choices. The URDF's generic joint damping and effort tags are not the complete Isaac runtime settings.

The current linear command cap is **4.0 m/s**, an experimental simulation setting, while the retained NASA/MER maximum-speed reference is **0.05 m/s**. The commanded yaw-rate cap remains 0.07 rad/s, with a 0.5 s command timeout. Six wheel drives and four steering drives implement the common rover controller. Configured drive damping is 1,000, drive force ceiling 1,000,000, and brake stiffness 50,000; steering stiffness/damping/ceiling are 200,000/5,000/100,000. `drive_type: acceleration` and these large numerical limits describe solver/controller tuning, not measured MER actuator torque ratings. Wheel odometry is enabled with zero injected slip factors and encoder noise; terrain-induced physical slip can still occur.

## Cameras and other sensors

The nine rendered cameras match the rover-mounted camera inventory: two Navcams, two Pancams, four Hazcams, and one Microscopic Imager (MI). The lander's descent camera is outside this rover model. NASA/JPL describes the actual engineering cameras as 1024 × 1024 detectors, with approximately 45° Navcam and 124° Hazcam fields of view. [Maki et al., MER Engineering Cameras](https://www-robotics.jpl.nasa.gov/media/documents/maki-jgr-2003je002077.pdf).

Opportunity uses **MER-1** instrument kernels; Spirit uses MER-2. Their shared visual geometry does not imply identical calibration. Each linked camera below identifies the actual Opportunity kernel used. All positions are metres relative to `Body_Chassis`; RPY is degrees in the camera-link FLU convention, rounded for readability. The full retained precision and source calibration appear in [Appendix B](#camera-register).

| Camera and source kernel | Position `(x, y, z)` | RPY `(roll, pitch, yaw)` | Horizontal FOV | Near clip |
| --- | --- | --- | ---: | ---: |
| [Navcam left](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_nl_20040125_c196.ti) | `(0.464877, 0.061132, 1.541584)` | `(0.0354, 0.3831, 0.0419)` | 45.3326° | 0.06 m |
| [Navcam right](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_nr_20040125_c197.ti) | `(0.465458, -0.138984, 1.541267)` | `(-0.0683, 0.4015, -0.0246)` | 45.7503° | 0.06 m |
| [Pancam left, F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f2_20040125_c199.ti) | `(0.485350, 0.109850, 1.541456)` | `(-0.1721, 0.0220, -1.1197)` | 16.0486° | 0.06 m |
| [Pancam right, F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f2_20040125_c207.ti) | `(0.484954, -0.187803, 1.541662)` | `(-0.1748, -0.0361, 0.9360)` | 16.0309° | 0.06 m |
| [Front Hazcam left](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_fl_20040125_c33.ti) | `(0.609331, 0.041064, 0.523849)` | `(-1.7841, 45.4039, -2.3475)` | 125.5002° | 0.05 m |
| [Front Hazcam right](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_fr_20040125_c34.ti) | `(0.609774, -0.060081, 0.524332)` | `(-1.9097, 45.4485, -2.3350)` | 124.4668° | 0.05 m |
| [Rear Hazcam left](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_rl_20040125_c35.ti) | `(-0.352486, -0.029107, 0.509509)` | `(0.0258, 35.3962, 179.2501)` | 125.2831° | 0.01 m |
| [Rear Hazcam right](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_rr_20040125_c36.ti) | `(-0.352347, 0.071376, 0.508263)` | `(-0.2733, 35.5866, 179.2266)` | 125.1309° | 0.01 m |
| [MI, F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_mi_f2_20040125_c194.ti) | `(0.512452, 0.088431, 0.389603)` | `(0, 0, -30.0001)` | 24.2795° | 0.01 m |

All nine use 1024 × 1024 RGB output and a 200 m far clip. Their existing USD prims are under the chassis at `Sensors/<name>`. [camera_mount.py](../marslab/sensors/camera_mount.py) checks agreement between authored USD poses and configured static ROS transforms, including the change from camera-link +X-forward to USD camera −Z-forward axes. Mast calibration poses were normalized to a canonical forward/level mast reference, then fixed to the chassis. They do not follow a moving mast.

The stored focal-length values are 14.67 mm for Navcam, 42.97 mm for Pancam, 5.58 mm for Hazcam, and 20.13 mm for MI. However, [camera_spawner.py](../marslab/sensors/camera_spawner.py) prioritizes `horizontal_fov_deg`, recomputes focal length from the USD aperture, and sets the vertical aperture for square pixels. The source's independent vertical calibration, off-center principal point, and CAHVOR/E distortion are not reproduced. A source-derived FOV therefore does not imply complete camera-calibration equivalence.

The near planes bypass opaque lens/housing triangles in the visualization. They also clip other nearby geometry, including some stowed-arm fragments in front Hazcam views. These values are rendering accommodations, not flight focus distances. [Appendix D](#visibility-audit) preserves the housing measurements and historical ray audits.

MI has an additional mounting approximation: its optical center is the front-face center of the visually identified stowed-arm optics box, derived from `arm_turret` triangles 1500 and 1501. Its axis points approximately 30° right of forward. Identification used [NASA's MI turret photograph, Figure 1](https://ntrs.nasa.gov/api/citations/20030066751/downloads/20030066751.pdf). This is not a flight-calibrated stowed entrance pupil. [Appendix C](#mi-mount) preserves the original extended-arm reference alongside the active pose; no arm motion, dust-cover optics, or microscope focus is implemented.

The IMU is an ideal simulated chassis-origin sensor with identity orientation, requested 8 Hz sampling, and zero acceleration/angular-velocity noise. The configuration cites a [PDS MER2 IMU record](https://pds.nasa.gov/ds-view/pds/viewContext.jsp?identifier=urn:nasa:pds:context:instrument:imu.mer2&version=1.2) for the shared MER accumulated-data cadence; neither an Opportunity-specific mounting survey nor a certified surface sampling rate is established. Both LiDAR configurations are null, and direct depth output is disabled for every camera.

The primary Navcam publishes through `/rover/rgb/image_raw` and `/rover/rgb/camera_info`; other cameras use `/rover/cameras/<name>/image_raw` and corresponding `camera_info`. The configuration also names IMU, odometry, joint-state, and velocity-command topics. Merely having depth/LiDAR topic strings in the configuration does not activate those absent sensors.

## Comparison with NASA hardware and supported uses

| Aspect | NASA hardware evidence | Current MarsLab consequence |
| --- | --- | --- |
| Pancam | Eight filters per eye; approximately 39 mm nominal focal length and 16.8° FOV | One selected kernel variant per eye, approximately 16.04° FOV, rendered RGB; no filter wheel or spectral response |
| MI | Arm-mounted monochrome close-up camera; approximately 68 mm optimal focus | Fixed stowed proxy producing ordinary RGB pinhole images |
| Arm and instrument placement | Five arm joints and contact feedback | No deployment, contact placement, abrasion, or arm collision checking |
| Scientific payload | Mini-TES, Mössbauer, APXS, RAT, magnets, calibration targets | Visual/metadata representations do not generate instrument measurements |
| Dynamics | 185 kg mission-summary mass | Matching total; estimated mass partition, inertias, contact and gains |

The camera and scientific-instrument comparisons use NASA's [MER science-instrument specifications](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/); the arm comparison uses the [JPL operational-performance paper](https://robotics.jpl.nasa.gov/media/documents/MobIDDPerf90sols.pdf). Differences between generic NASA nominal optics and the selected kernel values are retained explicitly rather than silently replacing one with the other.

This implementation supports rover visualization, ROS integration, synthetic camera experiments, and approximate rocker-bogie mobility. It does not establish flight-equivalent terrain performance, soil sinkage, instrument science, thermal/power behavior, or historical Opportunity wear and faults.

## Inspection and validation limits

The initial inspection examined the configuration, URDF, USD, construction records, and sensor-spawning implementation. The present consolidation additionally preserves their substantive technical data in the appendices. The shared inspection confirmed 15 USD rigid bodies, 14 URDF joints, nine USD cameras, seven collisions, metre units, and Z-up coordinates. No Isaac simulation, terrain-driving experiment, or ROS streaming trial was rerun for this report.

The tensor checks and camera-occlusion measurements reproduced here are historical construction evidence, distinct from the report's static inspection. They were not rerun during consolidation. New inspection utilities and machine-readable results are located only under `tmp/techreport/`; those temporary artifacts are not runtime dependencies and are not required to read this report or load the delivered robot.

<!-- OPPORTUNITY TECHNICAL APPENDICES -->

The following reference appendices preserve the substantive construction records at their stored numerical precision. Extra digits preserve the record; they do not imply equivalent measurement accuracy. Camera-source records were retrieved on **2026-10-22**. Quantities described as historical measurements were not recomputed for this consolidation.

Appendix navigation: [A — geometry and mass](#physical-register), [B — camera calibration](#camera-register), [C — MI mounting](#mi-mount), [D — visibility audits](#visibility-audit), [E — hardware reference and sources](#hardware-reference).

<a id="physical-register"></a>

## Appendix A. Frames, geometry, and complete mass properties

### A.1 Distinct source transformations

The visualization and camera records originate in different frames. They must not share a single implicit axis conversion. All equations below use column vectors.

**Blender visualization to nominal ground FLU:** `p_ground = R_visual p_visual + t_visual`, with:

```text
[ 0.0  -1.0  0.0 ]
[ 1.0  0.0  0.0 ]
[ 0.0  0.0  1.0 ]
```

`t_visual [m] = [-0.39703237265348434, 6.881852944691976e-06, 0.002056402751089398]`. The evaluated source pose is frame 1243.

**MER navigation to ground FLU:** native +X is forward toward the PMA, +Y right, and +Z down. The navigation origin is at the bottom panel above the middle wheels. Use `p_ground = diag(1, -1, -1) p_nav + (0, 0, 0.29)` m. The mechanical origin described in PDS is a separate origin 0.29 m forward; that longitudinal offset must not be confused with the 0.29 m ground-clearance translation. The ground height is a nominal construction assumption, not a rover-specific survey. Sources: [JPL surface-mobility study, §2.1](https://robotics.jpl.nasa.gov/media/documents/tradeoffs_ijrr_07.pdf), [Opportunity navigation-origin structure kernel](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/spk/mer1_struct_ver11.bsp), and [PDS MER coordinate description](https://pds.nasa.gov/data/pds4/context-pds4/instrument_host/spacecraft.mer2_1.0.xml).

The original shared frame record additionally cited [MSL PLACES PDS SIS §2.1.1](https://planetarydata.jpl.nasa.gov/w10n/msl/msl_places/document/PLACES_PDS_SIS.pdf) for the coordinate convention; the MER-specific navigation origin is established by the MER sources above. The output frame is `ground_flu`, with origin at nominal ground between the middle wheels. The authored chassis uses this same origin; `nasa_ground_to_chassis_translation = (0, 0, 0)` m.

### A.2 Mobility geometry and selection criteria

All genuine physical surfaces, including source-hidden physical arm meshes, were retained. Named transform/rig helpers without physical surface material, non-mesh lighting/camera helpers, pivot-material helpers, and shadow planes are excluded by function; vertex count alone is not a removal criterion. The retained model has 40 assigned physical objects and 32,562 triangles. Chassis geometry includes the fixed arm, mast, antennas, panels, and payload. Rockers, bogies, steering carriers, and wheels receive the corresponding physical geometry. Original source side names are interpreted geometrically, so native `right` can mean physical left.

| Controller geometry | Value |
| --- | --- |
| Wheel radius (m) | 0.13 |
| Wheelbase (m) | 1.2120322799310088 |
| Steering-axle offset (m) | 0.10577812464907765 |
| Steering-wheel track (m) | 1.0609725341200829 |
| Middle-wheel track (m) | 0.9500002264976501 |
| Negate steer | No |

Lengths above are metres; `negate steer = No` means the controller does not apply an extra steering-sign inversion. The exact nominal wheel centers are:

| Wheel link | Ground FLU center (m) |
| --- | --- |
| Body_WheelLeftFront | `(0.7117942646145821, 0.5304862670600414, 0.13)` |
| Body_WheelLeftMiddle | `(0.0, 0.4750001132488251, 0.13)` |
| Body_WheelLeftRear | `(-0.5002380153164268, 0.5304862670600414, 0.13)` |
| Body_WheelRightFront | `(0.7117942646145821, -0.5304862670600414, 0.13)` |
| Body_WheelRightMiddle | `(0.0, -0.4750001132488251, 0.13)` |
| Body_WheelRightRear | `(-0.5002380153164268, -0.5304862670600414, 0.13)` |

### A.3 Link-local mass properties

For each link below, **origin** is its nominal position in the common ground FLU construction frame. **Local COM** is relative to that link origin. Inertia matrices are about the local COM, expressed in that link's nominal axes, in **kg·m²**; principal moments have the same units. Mass is kg and positions are m. These are engineering estimates. The full matrices preserve even insignificant floating-point asymmetry in the source record; the physical tensors are symmetric to numerical precision. USD stores the corresponding principal-axis representation.

Wheel moments follow `I_axle = m r²/2` and `I_transverse = m(3r² + width²)/12`. The other link tensors use area-weighted uniform thin shells over the retained source triangles, normalized to the assigned mass. This permits open meshes and does not reconstruct internal hardware distribution. Historical checks required positive eigenvalues and principal-moment triangle inequalities.

<a id="link-body_chassis"></a>

#### Body_Chassis


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 158.8 | `(0.0, 0.0, 0.0)` | `(0.10152446466490919, 0.01814587343597275, 0.6945021625121687)` | `(30.79140314412789, 38.73773546690159, 52.067526930894175)` |

Full COM inertia:

```text
[ 39.24171144180523  0.7053872464771085  -2.683968455902145 ]
[ 0.7053872464771087  30.8514115343005  -0.07447931930157761 ]
[ -2.683968455902145  -0.07447931930157815  51.503542565817945 ]
```


<a id="link-body_rockerleft"></a>

#### Body_RockerLeft


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 4.0 | `(0.22003603726625443, 0.3657357667883237, 0.36396284181702265)` | `(0.056226182311081785, -0.006109187605853605, -0.02443418508843581)` | `(0.019530308477150874, 0.3665524280076403, 0.377039762841875)` |

Full COM inertia:

```text
[ 0.03420255485000018  -0.032421066152354516  0.06185048436172913 ]
[ -0.032421066152354516  0.3719923073581094  0.010061129856562101 ]
[ 0.061850484361729186  0.010061129856562101  0.3569276371185565 ]
```


<a id="link-body_bogieleft"></a>

#### Body_BogieLeft


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 3.0 | `(-0.2268720492720604, 0.3389466678102811, 0.2964259215079559)` | `(-0.028066720498709452, 0.048348361433922904, -0.046568699049899104)` | `(0.025229813264598867, 0.13115809797363812, 0.15330832811491102)` |

Full COM inertia:

```text
[ 0.02615619304134699  0.009033455162128487  0.005940648093727005 ]
[ 0.009033455162128487  0.14183182803181077  0.010653904955182161 ]
[ 0.005940648093727005  0.010653904955182161  0.14170821827999025 ]
```


<a id="link-body_wheelleftfront"></a>

#### Body_WheelLeftFront


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 1.5 | `(0.7117942646145821, 0.5304862670600414, 0.13)` | `(0.0, 0.0, 0.0)` | `(0.009618299360667165, 0.009618299360667165, 0.012675000000000002)` |

Full COM inertia:

```text
[ 0.009618299360667165  0.0  0.0 ]
[ 0.0  0.012675000000000002  0.0 ]
[ 0.0  0.0  0.009618299360667165 ]
```


<a id="link-body_steerleftfront"></a>

#### Body_SteerLeftFront


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 0.8 | `(0.7117942646145821, 0.5304862670600414, 0.17191444117653495)` | `(2.7867381067747665e-05, -0.0056338625303070655, -0.020830155127176675)` | `(0.0011248646346693598, 0.001215607654531121, 0.0018294008940543927)` |

Full COM inertia:

```text
[ 0.0012156075968744323  -1.2543687346600053e-07  1.374248543850598e-07 ]
[ -1.2543687351040946e-07  0.0011538448721667288  -0.00013992035455464568 ]
[ 1.3742485437395758e-07  -0.00013992035455464568  0.001800420714213713 ]
```


<a id="link-body_wheelleftmiddle"></a>

#### Body_WheelLeftMiddle


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 1.5 | `(0.0, 0.4750001132488251, 0.13)` | `(0.0, 0.0, 0.0)` | `(0.009537505817415975, 0.009537505817415975, 0.012675000000000002)` |

Full COM inertia:

```text
[ 0.009537505817415975  0.0  0.0 ]
[ 0.0  0.012675000000000002  0.0 ]
[ 0.0  0.0  0.009537505817415975 ]
```


<a id="link-body_wheelleftrear"></a>

#### Body_WheelLeftRear


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 1.5 | `(-0.5002380153164268, 0.5304862670600414, 0.13)` | `(0.0, 0.0, 0.0)` | `(0.009537510585793668, 0.009537510585793668, 0.012675000000000002)` |

Full COM inertia:

```text
[ 0.009537510585793668  0.0  0.0 ]
[ 0.0  0.012675000000000002  0.0 ]
[ 0.0  0.0  0.009537510585793668 ]
```


<a id="link-body_steerleftrear"></a>

#### Body_SteerLeftRear


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 0.8 | `(-0.5002380153164268, 0.5304862670600414, 0.1592677064620269)` | `(3.2679903319010606e-06, -0.005666036364995519, -0.008159529003121863)` | `(0.0011253618213242418, 0.00121602410211821, 0.001829915254294163)` |

Full COM inertia:

```text
[ 0.001216024105004135  1.96170990562905e-09  5.6040641172039333e-08 ]
[ 1.96170990562905e-09  0.0011543636539482454  -0.00013997225791440027 ]
[ 5.6040641172039333e-08  -0.00013997225791440027  0.0018009134187842335 ]
```


<a id="link-body_rockerright"></a>

#### Body_RockerRight


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 4.0 | `(0.220035620033741, -0.36574334154526394, 0.36396281201470027)` | `(0.056257953126770344, 0.006097927629400479, -0.02444795414161055)` | `(0.019538228644832057, 0.36674719653700444, 0.37723956346626303)` |

Full COM inertia:

```text
[ 0.03421491488132511  0.0324243456411728  0.06188232492931106 ]
[ 0.0324243456411728  0.37219329910110305  -0.010062631092439545 ]
[ 0.06188232492931106  -0.010062631092439545  0.35711677466567143 ]
```


<a id="link-body_bogieright"></a>

#### Body_BogieRight


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 3.0 | `(-0.22687246650457382, -0.3389536167184512, 0.29642598111260066)` | `(-0.028066778599403652, -0.0483482883326517, -0.04656869746912709)` | `(0.0252298097361108, 0.13115810644099385, 0.15330833236819194)` |

Full COM inertia:

```text
[ 0.02615616724788096  -0.009033311064962038  0.005940638397530534 ]
[ -0.009033311064962038  0.14183186266797393  -0.010653909873715117 ]
[ 0.005940638397530534  -0.010653909873715117  0.14170821862944177 ]
```


<a id="link-body_wheelrightfront"></a>

#### Body_WheelRightFront


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 1.5 | `(0.7117942646145821, -0.5304862670600414, 0.13)` | `(0.0, 0.0, 0.0)` | `(0.009609554090103894, 0.009609554090103894, 0.012675000000000002)` |

Full COM inertia:

```text
[ 0.009609554090103894  0.0  0.0 ]
[ 0.0  0.012675000000000002  0.0 ]
[ 0.0  0.0  0.009609554090103894 ]
```


<a id="link-body_steerrightfront"></a>

#### Body_SteerRightFront


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 0.8 | `(0.7117942646145821, -0.5304862670600414, 0.17191463489163047)` | `(2.73690742084165e-05, 0.005667337397005201, -0.02079344971247507)` | `(0.0011256584454796875, 0.001216272596194414, 0.0018302200761009342)` |

Full COM inertia:

```text
[ 0.0012162725388197794  1.2522014345428544e-07  1.3740548283625033e-07 ]
[ 1.2522014345428544e-07  0.00115466201059527  0.00013997687030704588 ]
[ 1.3740548282514808e-07  0.00013997687030703476  0.001801216568359987 ]
```


<a id="link-body_wheelrightmiddle"></a>

#### Body_WheelRightMiddle


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 1.5 | `(0.0, -0.4750001132488251, 0.13)` | `(0.0, 0.0, 0.0)` | `(0.009537505817415975, 0.009537505817415975, 0.012675000000000002)` |

Full COM inertia:

```text
[ 0.009537505817415975  0.0  0.0 ]
[ 0.0  0.012675000000000002  0.0 ]
[ 0.0  0.0  0.009537505817415975 ]
```


<a id="link-body_wheelrightrear"></a>

#### Body_WheelRightRear


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 1.5 | `(-0.5002380153164268, -0.5304862670600414, 0.13)` | `(0.0, 0.0, 0.0)` | `(0.009537504625322107, 0.009537504625322107, 0.012675000000000002)` |

Full COM inertia:

```text
[ 0.009537504625322107  0.0  0.0 ]
[ 0.0  0.012675000000000002  0.0 ]
[ 0.0  0.0  0.009537504625322107 ]
```


<a id="link-body_steerrightrear"></a>

#### Body_SteerRightRear


| Mass (kg) | Origin (m) | Local COM (m) | Principal moments (kg·m²) |
| --- | --- | --- | --- |
| 0.8 | `(-0.5002380153164268, -0.5304862670600414, 0.17191509682762748)` | `(-2.2846073062243732e-06, 0.005663285489436398, -0.02080034607134945)` | `(0.0011255042456687415, 0.001216143974371073, 0.0018300623079852874)` |

Full COM inertia:

```text
[ 0.001216143977255671  -2.0106474707404234e-09  5.617602554242041e-08 ]
[ -2.0106474707404234e-09  0.0011545100043741901  0.00013998180467083012 ]
[ 5.617602554242041e-08  0.00013998180467083012  0.0018010565463952412 ]
```

### A.4 Aggregate values and interpretation


| Quantity | Stored value |
| --- | --- |
| Total mass (kg) | 185.0 |
| Ground FLU COM (m) | `(0.0960858261500372, 0.015575639537681702, 0.627869209206479)` |

Aggregate inertia about this COM, in ground FLU axes (kg·m²):

```text
[ 49.79939622491091  0.6897494247936405  -3.086132706525749 ]
[ 0.6897494247936405  41.55686263240846  -0.2665072547907428 ]
[ -3.0861327065257487  -0.2665072547907432  62.165618573087436 ]
```

No official complete link mass distribution or inertia tensor was identified in the retained research; no NASA tensor target was imposed. The off-diagonal terms result from the thin-shell geometry estimate. NASA visualization provenance does not certify these dynamic properties. The seven simple contact shapes, disabled self-collision, drive gains, damping, friction, and solver settings described above remain simulation approximations.

<a id="camera-register"></a>

## Appendix B. Complete retained camera calibration

### B.1 Reading the calibration register

All nine sensors are cameras with 1024 × 1024 calibration and photoactive rasters and 0.012 mm pixels. The common kernel FOV specification is a polygon described by corner/edge rays (`FOV_SHAPE=POLYGON`, `FOV_CLASS_SPEC=CORNERS`); its instrument-frame boresight is `(0,0,1)` and FOV center pixel `(511.5,511.5)`. Each camera's instrument frame is listed below and equals its kernel `FOV_FRAME`. The raw pixel counts and `CAHVOR_DIMS` repeat the same 1024 × 1024 dimensions.

`C`, `A`, `H`, `V`, `O`, `R`, and optional `E` below retain the source CAHVOR/E coefficients without reinterpreting them as runtime pinhole settings. `C` and source pose translation are metres; H/V, their scales HS/VS, and centers HC/VC retain the calibration pixel convention. THETA is radians. IFOV values are degrees/pixel; focal length and pixel size are millimetres. The eight boundary rays are dimensionless XYZ vectors in the named instrument frame, in original order. `CAHVOR_POS` and `CAHVOR_QUAT` preserve the calibration reference pose. The raw quaternion uses engineering order **(s1, s2, s3, c), scalar last**; it is not a SPICE scalar-first quaternion. The kernel explicitly documents this distinction.

The **derived pose** uses ground FLU, with a rotation matrix taking USD graphics-camera local vectors into ground FLU. Its columns are the local camera axes; viewing direction is minus its third column. Stored USD-camera RPY angles differ from ROS camera-link RPY. Matrices are preserved to remove Euler ambiguity. Source mast quaternions were removed to create a canonical forward/level PMA reference; body cameras are rigid mounts. The MI uses the separate stowed proxy in [Appendix C](#mi-mount).

MarsLab renders a centered pinhole using configured horizontal FOV, with vertical aperture derived from raster aspect ratio. It does not implement CAHVOR/E lens distortion, the original off-center principal points, independent vertical focal calibration, spectral filters, physical close focus, or detector response. Preserving these coefficients documents source evidence and supports later reimplementation; it does not imply that current rendering uses them.

<a id="calibration-navcam-left"></a>

### B.2 navcam_left

Source: [MER-1_NAVCAM_LEFT](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_nl_20040125_c196.ti). Camera model `MER_CAL_196_SN_102.cahvor`, CAHVOR. Mast calibration quaternion removed to canonical forward/level PMA head.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 14.67 |
| Focal scales fx, fy (pixels) | `(1223.283631, 1223.700117)` |
| Principal point (pixels) | `(500.748355, 502.777337)` |
| Horizontal, vertical FOV (degrees) | `(45.3326082, 45.31916598)` |
| Ground FLU center (m) | `(0.4648766963356724, 0.06113156828839758, 1.5415835129461481)` |
| Ground FLU boresight | `(0.9999773735324012, 0.0007308318434808383, -0.006687174893560193)` |
| USD-camera RPY in FLU (degrees) | `(89.6168501727663, 0.03543968600670549, -89.9583624765256)` |
| Mount group | mast_reference_pose |

Derived camera-to-ground rotation:

```text
[ 0.000726711674024515  0.006687623896672409  -0.9999773735324012 ]
[ -0.999999544649617  -0.0006136655238309225  -0.0007308318434808383 ]
[ -0.0006185391672487426  0.9999774492963537  0.006687174893560193 ]
```

Source model tag: `CAHVOR`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(500.74835479, 502.77733662)` |
| DISTORTION_PIXEL | `(529.45570391, 527.46073693)` |
| FOCAL_LENGTH (mm) | 14.67 |
| IFOV_NOMINAL (degrees/pixel) | 0.0468677 |
| IFOV_VERTICAL (degrees/pixel) | 0.04430026 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.0443134 |
| IFOV (degrees/pixel) | 0.04430683 |
| CAHVOR_C | `(0.41197, 0.105641, -1.249215)` |
| CAHVOR_A | `(-0.972195, -0.193555, 0.131811)` |
| CAHVOR_H | `(-247.726578, -1296.609863, 67.858466)` |
| CAHVOR_V | `(-331.07028, -63.484371, 1279.291928)` |
| CAHVOR_O | `(-0.964543, -0.215917, 0.151779)` |
| CAHVOR_R | `(0.00096, -0.002183, 0.018547)` |
| CAHVOR_HS | 1223.283631 |
| CAHVOR_HC | 500.748355 |
| CAHVOR_VS | 1223.700117 |
| CAHVOR_VC | 502.777337 |
| CAHVOR_THETA (radians) | -1.571214 |
| CAHVOR_POS | `(0.45729, 0.02605, -1.0962)` |
| CAHVOR_QUAT | `(0.065924, 0.006818, 0.992507, -0.102653)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.36090495, 0.36091219, 0.85993605)` |
| 2 | `(0.0, 0.3862159, 0.92240841)` |
| 3 | `(-0.35910674, 0.35883328, 0.86155733)` |
| 4 | `(-0.38417723, -0.0001345, 0.92325936)` |
| 5 | `(-0.35756844, -0.35756945, 0.8627218)` |
| 6 | `(-4.79e-06, -0.38429409, 0.92321073)` |
| 7 | `(0.35942831, -0.35922442, 0.86126018)` |
| 8 | `(0.38654902, 0.00013089, 0.92226885)` |


<a id="calibration-navcam-right"></a>

### B.3 navcam_right

Source: [MER-1_NAVCAM_RIGHT](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_nr_20040125_c197.ti). Camera model `MER_CAL_197_SN_117.cahvor`, CAHVOR. Mast calibration quaternion removed to canonical forward/level PMA head.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 14.67 |
| Focal scales fx, fy (pixels) | `(1211.743669, 1212.882704)` |
| Principal point (pixels) | `(522.622799, 514.016326)` |
| Horizontal, vertical FOV (degrees) | `(45.75031956, 45.71598768)` |
| Ground FLU center (m) | `(0.4654579098127498, -0.13898417540673472, 1.5412674540304694)` |
| Ground FLU boresight | `(0.9999753528282854, -0.00042899568652083594, -0.007007831237047506)` |
| USD-camera RPY in FLU (degrees) | `(89.59847727512569, -0.06826131495697413, -90.02410187084443)` |
| Mount group | mast_reference_pose |

Derived camera-to-ground rotation:

```text
[ -0.00042065669117994064  0.007008336742348915  -0.9999753528282854 ]
[ -0.9999992018252424  0.001188407160542051  0.00042899568652083594 ]
[ 0.0011913844158988516  0.9999747351331065  0.007007831237047506 ]
```

Source model tag: `CAHVOR`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(522.62279864, 514.01632563)` |
| DISTORTION_PIXEL | `(565.70779498, 508.63099285)` |
| FOCAL_LENGTH (mm) | 14.67 |
| IFOV_NOMINAL (degrees/pixel) | 0.0468677 |
| IFOV_VERTICAL (degrees/pixel) | 0.04468816 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.04472172 |
| IFOV (degrees/pixel) | 0.04470494 |
| CAHVOR_C | `(0.452404, -0.090348, -1.248825)` |
| CAHVOR_A | `(-0.967006, -0.212014, 0.14124)` |
| CAHVOR_H | `(-246.433204, -1294.549308, 69.794922)` |
| CAHVOR_V | `(-329.064749, -75.301543, 1273.320289)` |
| CAHVOR_O | `(-0.959404, -0.246709, 0.136667)` |
| CAHVOR_R | `(0.001281, -0.011721, 0.036593)` |
| CAHVOR_HS | 1211.743669 |
| CAHVOR_HC | 522.622799 |
| CAHVOR_VS | 1212.882704 |
| CAHVOR_VC | 514.016326 |
| CAHVOR_THETA (radians) | -1.571607 |
| CAHVOR_POS | `(0.45729, 0.02605, -1.0962)` |
| CAHVOR_QUAT | `(0.065924, 0.006818, 0.992507, -0.102653)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.36044042, 0.3605187, 0.86029586)` |
| 2 | `(0.0, 0.38815795, 0.92159286)` |
| 3 | `(-0.36302377, 0.36234583, 0.85844)` |
| 4 | `(-0.38998568, -0.00034673, 0.92082086)` |
| 5 | `(-0.36333534, -0.36336512, 0.85787716)` |
| 6 | `(7.303e-05, -0.38873906, 0.92134789)` |
| 7 | `(0.36101946, -0.36038877, 0.86010749)` |
| 8 | `(0.38746244, 0.00034164, 0.92188543)` |


<a id="calibration-pancam-left"></a>

### B.4 pancam_left

Source: [MER-1_PANCAM_LEFT_F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f2_20040125_c199.ti). Camera model `MER_CAL_199_SN_115_F_2.cahvor`, CAHVOR. Mast calibration quaternion removed to canonical forward/level PMA head.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 42.97 |
| Focal scales fx, fy (pixels) | `(3624.521054, 3625.551633)` |
| Principal point (pixels) | `(519.893737, 506.022495)` |
| Horizontal, vertical FOV (degrees) | `(16.04858871, 16.044148890000002)` |
| Ground FLU center (m) | `(0.48534962918889235, 0.10984971537098955, 1.5414561778508857)` |
| Ground FLU boresight | `(0.9998089856585739, -0.01954085448202051, -0.000383669761702935)` |
| USD-camera RPY in FLU (degrees) | `(89.97801724226056, -0.1720657092862627, -91.11961382076875)` |
| Mount group | mast_reference_pose |

Derived camera-to-ground rotation:

```text
[ -0.0195396158217977  0.00044227809136263376  -0.9998089856585739 ]
[ -0.9998045732802067  0.0029950382462372847  0.01954085448202051 ]
[ 0.0030031086428030365  0.9999954170574951  0.000383669761702935 ]
```

Source model tag: `CAHVOR`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(519.89373722, 506.02249463)` |
| DISTORTION_PIXEL | `(554.47518442, 525.95532848)` |
| FOCAL_LENGTH (mm) | 42.97 |
| IFOV_NOMINAL (degrees/pixel) | 0.01600068 |
| IFOV_VERTICAL (degrees/pixel) | 0.01568343 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.01568777 |
| IFOV (degrees/pixel) | 0.0156856 |
| CAHVOR_C | `(0.382152, 0.149178, -1.246381)` |
| CAHVOR_A | `(-0.965675, -0.22424, 0.131104)` |
| CAHVOR_H | `(315.089938, -3647.728413, 47.302857)` |
| CAHVOR_V | `(-20.801368, -26.864694, 3660.536632)` |
| CAHVOR_O | `(-0.962756, -0.233389, 0.13649)` |
| CAHVOR_R | `(0.000998, 0.003762, -0.057232)` |
| CAHVOR_HS | 3624.521054 |
| CAHVOR_HC | 519.893737 |
| CAHVOR_VS | 3625.551633 |
| CAHVOR_VC | 506.022495 |
| CAHVOR_THETA (radians) | -1.570681 |
| CAHVOR_POS | `(0.45729, 0.02605, -1.0962)` |
| CAHVOR_QUAT | `(0.065924, 0.006818, 0.992507, -0.102653)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.13823833, 0.13818495, 0.98071152)` |
| 2 | `(0.0, 0.13958379, 0.99021026)` |
| 3 | `(-0.13832356, 0.13829999, 0.98068329)` |
| 4 | `(-0.13963791, 1.533e-05, 0.99020263)` |
| 5 | `(-0.13826675, -0.13821203, 0.9807037)` |
| 6 | `(1.4e-07, -0.1395254, 0.99021849)` |
| 7 | `(0.13818058, -0.13815646, 0.98072367)` |
| 8 | `(0.13954802, -1.519e-05, 0.99021531)` |

Selected filter is **F2**. The retained alternate filter calibration identities are included because switching filter requires selecting a different optical calibration, not merely renaming the rendered image. No alternate-filter coefficients were present in the retained register.

| Filter kernel | Associated camera calibration |
| --- | --- |
| [mer1_pl_f1_20040125_c198.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f1_20040125_c198.ti) | MER_CAL_198_SN_115_F_1.cahvor |
| [mer1_pl_f2_20040125_c199.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f2_20040125_c199.ti) | MER_CAL_199_SN_115_F_2.cahvor |
| [mer1_pl_f3_20040125_c200.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f3_20040125_c200.ti) | MER_CAL_200_SN_115_F_3.cahvor |
| [mer1_pl_f4_20040125_c201.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f4_20040125_c201.ti) | MER_CAL_201_SN_115_F_4.cahvor |
| [mer1_pl_f5_20040125_c202.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f5_20040125_c202.ti) | MER_CAL_202_SN_115_F_5.cahvor |
| [mer1_pl_f6_20040125_c203.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f6_20040125_c203.ti) | MER_CAL_203_SN_115_F_6.cahvor |
| [mer1_pl_f7_20040125_c204.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f7_20040125_c204.ti) | MER_CAL_204_SN_115_F_7.cahvor |
| [mer1_pl_f8_20040125_c205.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pl_f8_20040125_c205.ti) | MER_CAL_205_SN_115_F_8.cahvor |


<a id="calibration-pancam-right"></a>

### B.5 pancam_right

Source: [MER-1_PANCAM_RIGHT_F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f2_20040125_c207.ti). Camera model `MER_CAL_207_SN_114_F_2.cahvor`, CAHVOR. Mast calibration quaternion removed to canonical forward/level PMA head.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 42.97 |
| Focal scales fx, fy (pixels) | `(3584.213602, 3584.285816)` |
| Principal point (pixels) | `(488.804743, 514.422586)` |
| Horizontal, vertical FOV (degrees) | `(16.03090104, 16.0309215)` |
| Ground FLU center (m) | `(0.4849536569146074, -0.18780281391372697, 1.5416623898024924)` |
| Ground FLU boresight | `(0.9998663664647764, 0.016335626769931944, 0.0006296908437523475)` |
| USD-camera RPY in FLU (degrees) | `(90.03607879796735, -0.17476600779344567, -89.06410576136379)` |
| Mount group | mast_reference_pose |

Derived camera-to-ground rotation:

```text
[ 0.016333633564683807  -0.0006794314533912592  -0.9998663664647764 ]
[ -0.9998619447031704  0.003039544773141195  -0.016335626769931944 ]
[ 0.0030502375266660423  0.9999951497584737  -0.0006296908437523475 ]
```

Source model tag: `CAHVOR`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(488.80474283, 514.42258593)` |
| DISTORTION_PIXEL | `(506.48897135, 531.86267602)` |
| FOCAL_LENGTH (mm) | 42.97 |
| IFOV_NOMINAL (degrees/pixel) | 0.01600068 |
| IFOV_VERTICAL (degrees/pixel) | 0.0156705 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.01567048 |
| IFOV (degrees/pixel) | 0.01567049 |
| CAHVOR_C | `(0.443429, -0.142099, -1.246638)` |
| CAHVOR_A | `(-0.974596, -0.180627, 0.132429)` |
| CAHVOR_H | `(176.69083, -3612.502474, 64.120658)` |
| CAHVOR_V | `(-34.618632, -6.528287, 3620.840003)` |
| CAHVOR_O | `(-0.973043, -0.185358, 0.137249)` |
| CAHVOR_R | `(0.013087, 0.023504, -0.374157)` |
| CAHVOR_HS | 3584.213602 |
| CAHVOR_HC | 488.804743 |
| CAHVOR_VS | 3584.285816 |
| CAHVOR_VC | 514.422586 |
| CAHVOR_THETA (radians) | -1.570938 |
| CAHVOR_POS | `(0.45729, 0.02605, -1.0962)` |
| CAHVOR_QUAT | `(0.065924, 0.006818, 0.992507, -0.102653)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.13820879, 0.13822768, 0.98070966)` |
| 2 | `(0.0, 0.13942422, 0.99023274)` |
| 3 | `(-0.13797093, 0.13794903, 0.98078239)` |
| 4 | `(-0.13931585, -2.229e-05, 0.990248)` |
| 5 | `(-0.13799149, -0.13801454, 0.98077028)` |
| 6 | `(1.63e-06, -0.13945636, 0.99022822)` |
| 7 | `(0.13823251, -0.13821275, 0.98070842)` |
| 8 | `(0.13956442, 1.895e-05, 0.99021299)` |

Selected filter is **F2**. The retained alternate filter calibration identities are included because switching filter requires selecting a different optical calibration, not merely renaming the rendered image. No alternate-filter coefficients were present in the retained register.

| Filter kernel | Associated camera calibration |
| --- | --- |
| [mer1_pr_f1_20040125_c206.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f1_20040125_c206.ti) | MER_CAL_206_SN_114_F_1.cahvor |
| [mer1_pr_f2_20040125_c207.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f2_20040125_c207.ti) | MER_CAL_207_SN_114_F_2.cahvor |
| [mer1_pr_f3_20040125_c208.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f3_20040125_c208.ti) | MER_CAL_208_SN_114_F_3.cahvor |
| [mer1_pr_f4_20040125_c209.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f4_20040125_c209.ti) | MER_CAL_209_SN_114_F_4.cahvor |
| [mer1_pr_f5_20040125_c210.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f5_20040125_c210.ti) | MER_CAL_210_SN_114_F_5.cahvor |
| [mer1_pr_f6_20040125_c211.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f6_20040125_c211.ti) | MER_CAL_211_SN_114_F_6.cahvor |
| [mer1_pr_f7_20040125_c212.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f7_20040125_c212.ti) | MER_CAL_212_SN_114_F_7.cahvor |
| [mer1_pr_f8_20040125_c213.ti](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_pr_f8_20040125_c213.ti) | MER_CAL_213_SN_114_F_8.cahvor |


<a id="calibration-hazcam-front-left"></a>

### B.6 hazcam_front_left

Source: [MER-1_FRONT_HAZCAM_LEFT](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_fl_20040125_c33.ti). Camera model `MER_CAL_33_SN_120.cahvore`, CAHVORE3,0.37. Rigid body-fixed camera.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 5.58 |
| Focal scales fx, fy (pixels) | `(454.771801, 454.80462)` |
| Principal point (pixels) | `(496.068975, 510.414937)` |
| Horizontal, vertical FOV (degrees) | `(125.50017711, 125.43394808999999)` |
| Ground FLU center (m) | `(0.609331, 0.041064, 0.523849)` |
| Ground FLU boresight | `(0.7015155856798296, -0.0287587987231367, -0.7120736019150603)` |
| USD-camera RPY in FLU (degrees) | `(44.582230734546386, -1.2524879759721834, -91.07696180041819)` |
| Mount group | body |

Derived camera-to-ground rotation:

```text
[ -0.01879093189919701  0.7124063334408569  -0.7015155856798296 ]
[ -0.9995844715103341  0.0019534101996856942  0.0287587987231367 ]
[ 0.021858298052818876  0.7017644905963442  0.7120736019150603 ]
```

Source model tag: `CAHVORE3,0.37`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(496.06897489, 510.41493673)` |
| DISTORTION_PIXEL | `(495.66063137, 509.8002074)` |
| FOCAL_LENGTH (mm) | 5.58 |
| IFOV_NOMINAL (degrees/pixel) | 0.12321654 |
| IFOV_VERTICAL (degrees/pixel) | 0.12261383 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.12267857 |
| IFOV (degrees/pixel) | 0.1226462 |
| CAHVOR_C | `(0.609331, -0.041064, -0.233849)` |
| CAHVOR_A | `(0.703447, -0.005161, 0.710729)` |
| CAHVOR_H | `(351.36173, 452.204294, 353.494013)` |
| CAHVOR_V | `(35.806531, -1.751429, 682.70452)` |
| CAHVOR_O | `(0.704402, -0.006062, 0.709775)` |
| CAHVOR_R | `(3e-06, -0.012015, -0.007525)` |
| CAHVOR_E | `(0.001442, 0.001522, 0.000483)` |
| CAHVOR_HS | 454.771801 |
| CAHVOR_HC | 496.068975 |
| CAHVOR_VS | 454.80462 |
| CAHVOR_VC | 510.414937 |
| CAHVOR_THETA (radians) | -1.571183 |
| CAHVOR_POS | `(0.0, 0.0, 0.0)` |
| CAHVOR_QUAT | `(0.0, 0.0, 0.0, 1.0)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.70630346, 0.70788166, -0.00624342)` |
| 2 | `(-0.0, 0.88815382, 0.45954628)` |
| 3 | `(-0.71053724, 0.70300488, -0.03034741)` |
| 4 | `(-0.88876118, 0.0098938, 0.45826377)` |
| 5 | `(-0.72567885, -0.68671525, -0.04257201)` |
| 6 | `(-0.02316307, -0.88919943, 0.45693308)` |
| 7 | `(0.685395, -0.72804901, -0.01335382)` |
| 8 | `(0.88913479, -0.01238458, 0.45747781)` |


<a id="calibration-hazcam-front-right"></a>

### B.7 hazcam_front_right

Source: [MER-1_FRONT_HAZCAM_RIGHT](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_fr_20040125_c34.ti). Camera model `MER_CAL_34_SN_122.cahvore`, CAHVORE3,0.37. Rigid body-fixed camera.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 5.58 |
| Focal scales fx, fy (pixels) | `(459.02845, 458.986965)` |
| Principal point (pixels) | `(514.400475, 508.007205)` |
| Horizontal, vertical FOV (degrees) | `(124.46678343, 124.48197498)` |
| Ground FLU center (m) | `(0.609774, -0.060081, 0.524332)` |
| Ground FLU boresight | `(0.7009676019302438, -0.028582963373042832, -0.7126201198738208)` |
| USD-camera RPY in FLU (degrees) | `(44.535589274856655, -1.3396088828763784, -90.97390126074413)` |
| Mount group | body |

Derived camera-to-ground rotation:

```text
[ -0.016992319588985335  0.7129906606114481  -0.7009676019302438 ]
[ -0.9995822671944864  0.004278471122461153  0.028582963373042832 ]
[ 0.023378455580218026  0.7011604756157502  0.7126201198738208 ]
```

Source model tag: `CAHVORE3,0.37`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(514.40047503, 508.00720471)` |
| DISTORTION_PIXEL | `(515.03027704, 506.88920791)` |
| FOCAL_LENGTH (mm) | 5.58 |
| IFOV_NOMINAL (degrees/pixel) | 0.12321654 |
| IFOV_VERTICAL (degrees/pixel) | 0.12168326 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.12166841 |
| IFOV (degrees/pixel) | 0.12167584 |
| CAHVOR_C | `(0.609774, 0.060081, -0.234332)` |
| CAHVOR_A | `(0.706252, 0.03486, 0.707102)` |
| CAHVOR_H | `(353.645269, 476.6754, 350.756881)` |
| CAHVOR_V | `(33.985059, 19.794709, 683.515455)` |
| CAHVOR_O | `(0.707943, 0.036219, 0.70534)` |
| CAHVOR_R | `(8e-06, -0.01279, -0.007496)` |
| CAHVOR_E | `(0.001158, 0.001904, 0.000674)` |
| CAHVOR_HS | 459.02845 |
| CAHVOR_HC | 514.400475 |
| CAHVOR_VS | 458.986965 |
| CAHVOR_VC | 508.007205 |
| CAHVOR_THETA (radians) | -1.571352 |
| CAHVOR_POS | `(0.0, 0.0, 0.0)` |
| CAHVOR_QUAT | `(0.0, 0.0, 0.0, 1.0)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.7105282, 0.70366027, -0.00344927)` |
| 2 | `(-0.0, 0.88376244, 0.46793584)` |
| 3 | `(-0.7099724, 0.70418494, 0.00792181)` |
| 4 | `(-0.88422596, -0.00625173, 0.46701753)` |
| 5 | `(-0.69909321, -0.71496037, -0.01001782)` |
| 6 | `(0.00505661, -0.8860537, 0.46355503)` |
| 7 | `(0.70833527, -0.70556792, -0.02085799)` |
| 8 | `(0.88546793, -0.00033743, 0.46470038)` |


<a id="calibration-hazcam-rear-left"></a>

### B.8 hazcam_rear_left

Source: [MER-1_REAR_HAZCAM_LEFT](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_rl_20040125_c35.ti). Camera model `MER_CAL_35_SN_119.cahvore`, CAHVORE3,0.37. Rigid body-fixed camera.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 5.58 |
| Focal scales fx, fy (pixels) | `(456.486649, 456.984195)` |
| Principal point (pixels) | `(504.841728, 509.72025)` |
| Horizontal, vertical FOV (degrees) | `(125.28307605, 125.13364644)` |
| Ground FLU center (m) | `(-0.352486, -0.029107, 0.509509)` |
| Ground FLU boresight | `(-0.8150963274962417, 0.01066842827327796, -0.5792272106352716)` |
| USD-camera RPY in FLU (degrees) | `(54.603790164448405, 0.02103742637433649, 89.23517577155903)` |
| Mount group | body |

Derived camera-to-ground rotation:

```text
[ 0.013348303659755825  -0.5791716495923696  0.8150963274962417 ]
[ 0.9999108400121852  0.008030981528070146  -0.01066842827327796 ]
[ -0.0003671723481278624  0.8151660589377784  0.5792272106352716 ]
```

Source model tag: `CAHVORE3,0.37`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(504.84172836, 509.72025012)` |
| DISTORTION_PIXEL | `(504.19656859, 510.49439864)` |
| FOCAL_LENGTH (mm) | 5.58 |
| IFOV_NOMINAL (degrees/pixel) | 0.12321654 |
| IFOV_VERTICAL (degrees/pixel) | 0.12232028 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.12246635 |
| IFOV (degrees/pixel) | 0.12239331 |
| CAHVOR_C | `(-0.352486, 0.029107, -0.219509)` |
| CAHVOR_A | `(-0.817454, 0.003886, 0.575981)` |
| CAHVOR_H | `(-412.111787, -454.507817, 294.672076)` |
| CAHVOR_V | `(-153.453457, 5.657748, 667.135065)` |
| CAHVOR_O | `(-0.816478, 0.005312, 0.577352)` |
| CAHVOR_R | `(5e-06, -0.013636, -0.007433)` |
| CAHVOR_E | `(0.002913, 0.00249, 0.001988)` |
| CAHVOR_HS | 456.486649 |
| CAHVOR_HC | 504.841728 |
| CAHVOR_VS | 456.984195 |
| CAHVOR_VC | 509.72025 |
| CAHVOR_THETA (radians) | -1.571148 |
| CAHVOR_POS | `(0.0, 0.0, 0.0)` |
| CAHVOR_QUAT | `(0.0, 0.0, 0.0, 1.0)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.70704488, 0.7069369, -0.018104)` |
| 2 | `(-0.0, 0.88854157, 0.45879612)` |
| 3 | `(-0.70897554, 0.70432635, -0.03575028)` |
| 4 | `(-0.88864207, 0.00430085, 0.45858126)` |
| 5 | `(-0.71582976, -0.69767582, -0.02891704)` |
| 6 | `(-0.01062192, -0.88652013, 0.46256808)` |
| 7 | `(0.69742376, -0.71658611, -0.01021927)` |
| 8 | `(0.88762593, -0.00576094, 0.46052906)` |


<a id="calibration-hazcam-rear-right"></a>

### B.9 hazcam_rear_right

Source: [MER-1_REAR_HAZCAM_RIGHT](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_rr_20040125_c36.ti). Camera model `MER_CAL_36_SN_121.cahvore`, CAHVORE3,0.37. Rigid body-fixed camera.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 5.58 |
| Focal scales fx, fy (pixels) | `(456.252633, 456.820712)` |
| Principal point (pixels) | `(509.212276, 523.405238)` |
| Horizontal, vertical FOV (degrees) | `(125.13087411, 125.00541338999999)` |
| Ground FLU center (m) | `(-0.352347, 0.071376, 0.508263)` |
| Ground FLU boresight | `(-0.8131628292105065, 0.010977580537695056, -0.5819327331538442)` |
| USD-camera RPY in FLU (degrees) | `(54.413095574293614, -0.2222674202389231, 89.38561245830192)` |
| Mount group | body |

Derived camera-to-ground rotation:

```text
[ 0.010722799304862056  -0.5819374835542322  0.8131628292105065 ]
[ 0.9999349842340919  0.003085454635037161  -0.010977580537695056 ]
[ 0.003879288573192688  0.8132276711993159  0.5819327331538442 ]
```

Source model tag: `CAHVORE3,0.37`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(509.21227639, 523.40523796)` |
| DISTORTION_PIXEL | `(510.21247113, 523.17750397)` |
| FOCAL_LENGTH (mm) | 5.58 |
| IFOV_NOMINAL (degrees/pixel) | 0.12321654 |
| IFOV_VERTICAL (degrees/pixel) | 0.12219493 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.12231757 |
| IFOV (degrees/pixel) | 0.12225625 |
| CAHVOR_C | `(-0.352347, -0.071376, -0.218263)` |
| CAHVOR_A | `(-0.797769, -0.005895, 0.602934)` |
| CAHVOR_H | `(-403.318552, -459.244833, 306.418265)` |
| CAHVOR_V | `(-142.127421, -1.605314, 680.026212)` |
| CAHVOR_O | `(-0.798053, -0.008088, 0.602532)` |
| CAHVOR_R | `(5e-06, -0.012461, -0.00752)` |
| CAHVOR_E | `(0.003556, 0.003197, 0.000849)` |
| CAHVOR_HS | 456.252633 |
| CAHVOR_HC | 509.212276 |
| CAHVOR_VS | 456.820712 |
| CAHVOR_VC | 523.405238 |
| CAHVOR_THETA (radians) | -1.571239 |
| CAHVOR_POS | `(0.0, 0.0, 0.0)` |
| CAHVOR_QUAT | `(0.0, 0.0, 0.0, 1.0)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.698413, 0.71511822, -0.02872656)` |
| 2 | `(0.0, 0.88625362, 0.4632003)` |
| 3 | `(-0.69939721, 0.71451261, -0.01775604)` |
| 4 | `(-0.88626024, 0.00892975, 0.46310155)` |
| 5 | `(-0.71707456, -0.6969695, -0.00613047)` |
| 6 | `(-0.00186653, -0.88780814, 0.46020997)` |
| 7 | `(0.71417235, -0.69982554, -0.0142151)` |
| 8 | `(0.88880804, 0.00800199, 0.45820982)` |


<a id="calibration-microscopic-imager"></a>

### B.10 microscopic_imager

Source: [MER-1_MICROIMAGER_F2](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/mer1_mi_f2_20040125_c194.ti). Camera model `MER_CAL_194_SN_110_F_2.cahvor`, CAHVOR. Fixed stowed-arm visualization pose. MarsLab derives the virtual pinhole from the MI optics-box front face; original extended NASA calibration pose is retained in calibration_reference_pose. Not flight-calibrated stowed extrinsics.


| Derived optical quantity | Retained value |
| --- | --- |
| Nominal focal length (mm) | 20.13 |
| Focal scales fx, fy (pixels) | `(2369.763957, 2367.210982)` |
| Principal point (pixels) | `(528.690417, 521.685826)` |
| Horizontal, vertical FOV (degrees) | `(24.27949326, 24.31013211)` |
| Ground FLU center (m) | `(0.5124521963424407, 0.08843081744597046, 0.38960254197268984)` |
| Ground FLU boresight | `(0.8660247544209582, -0.5000011247279881, 9.306536878376931e-07)` |
| USD-camera RPY in FLU (degrees) | `(90.00005332252849, -3.473078704904294e-06, -120.00007441145014)` |
| Mount group | fixed_stowed_arm_visualization |

Derived camera-to-ground rotation:

```text
[ -0.5000011247282525  -7.756607338780451e-07  -0.8660247544209582 ]
[ -0.8660247544213034  5.178234177121668e-07  0.5000011247279881 ]
[ 6.061665881124138e-08  0.9999999999995651  -9.306536878376931e-07 ]
```

Source model tag: `CAHVOR`. Source optical and reference-pose parameters:

| Kernel parameter | Value in source convention |
| --- | --- |
| BORESIGHT_PIXEL | `(528.69041694, 521.68582568)` |
| DISTORTION_PIXEL | `(476.2593271, 606.7713876)` |
| FOCAL_LENGTH (mm) | 20.13 |
| IFOV_NOMINAL (degrees/pixel) | 0.03415545 |
| IFOV_VERTICAL (degrees/pixel) | 0.02376357 |
| IFOV_HORIZONTAL (degrees/pixel) | 0.02373362 |
| IFOV (degrees/pixel) | 0.02374859 |
| CAHVOR_C | `(1.12098, 0.084947, 0.105077)` |
| CAHVOR_A | `(0.025729, -0.014067, 0.99957)` |
| CAHVOR_H | `(-605.098814, 2279.629747, 576.574483)` |
| CAHVOR_V | `(-2269.908949, -629.901082, 571.473228)` |
| CAHVOR_O | `(-0.003143, -0.04477, 0.998992)` |
| CAHVOR_R | `(0.001715, 0.070042, -0.724357)` |
| CAHVOR_HS | 2369.763957 |
| CAHVOR_HC | 528.690417 |
| CAHVOR_VS | 2367.210982 |
| CAHVOR_VC | 521.685826 |
| CAHVOR_THETA (radians) | -1.572354 |
| CAHVOR_POS | `(1.12183, 0.083616, 0.160306)` |
| CAHVOR_QUAT | `(-0.004108, 0.010736, -0.612627, 0.790289)` |


| Boundary ray | Instrument-frame direction (x, y, z) |
| --- | --- |
| 1 | `(0.2057308, 0.20635582, 0.95660447)` |
| 2 | `(-0.0, 0.21033064, 0.97763031)` |
| 3 | `(-0.20669936, 0.2066294, 0.95633658)` |
| 4 | `(-0.2105935, -0.00040036, 0.97757364)` |
| 5 | `(-0.20637125, -0.20698622, 0.95633028)` |
| 6 | `(3.863e-05, -0.21078577, 0.97753228)` |
| 7 | `(0.20575381, -0.2056589, 0.9567496)` |
| 8 | `(0.20999946, 0.00027938, 0.97770146)` |


<a id="mi-mount"></a>

## Appendix C. Microscopic Imager mounting derivation and original reference

The runtime MI is a **MarsLab visualization-derived mounting proxy**, shared by Spirit and Opportunity because they use the same fixed stowed geometry. Their individual camera calibration remains distinct. The pinhole is placed at the center of the optics-box front face, looking along its outward face normal; image up follows turret local +Z. The entrance pupil is not separately resolved. This construction does not model dust-cover transmission or microscope focus and is not flight-calibrated stowed extrinsics.

The source is the [pinned NASA MER Blender visualization](https://github.com/nasa/NASA-3D-Resources/blob/11ebb4ee043715aefbba6aeec8a61746fad67fa7/3D%20Models/Mars%20Exploration%20Rover%20-%20Spirit%20and%20Opportunity/Mars%20Exploration%20Rover%20-%20Spirit%20and%20Opportunity.blend), evaluated at frame 1243. Instrument identity was checked against [The Athena Microscopic Imager Investigation, Figure 1, page 1](https://ntrs.nasa.gov/api/citations/20030066751/downloads/20030066751.pdf) and the [NASA MI hardware photograph](https://science.nasa.gov/wp-content/uploads/2024/03/mi1-500.jpg).

| Construction measurement | Retained value |
| --- | --- |
| Physical source surface | arm_turret |
| Evaluated triangle indices | `(1500, 1501)` |
| Triangle vertex indices | `(1436, 1432, 1431)`<br>`(1436, 1431, 1435)` |
| Front-face center in source-object coordinates (m) | `(0.06830248848254535, -0.03943445270196513, 0.03034990735705799)` |
| Outward forward vector in source-object coordinates | `(0.8660252614946273, -0.5000002464530587, 2.0682048452482977e-07)` |
| Active ground FLU center (m) | `(0.5124521963424407, 0.08843081744597046, 0.38960254197268984)` |
| Active ground FLU boresight | `(0.8660247544209582, -0.5000011247279881, 9.306536878376931e-07)` |

Source-object homogeneous world transform:

```text
[ -9.26034658732533e-07  1.0000003576278687  1.8777086552290712e-07  0.1278584599494934 ]
[ -1.0000003576278687  -1.2784774980900693e-06  2.0399468780851748e-07  -0.8411821126937866 ]
[ 7.449639269907493e-07  -1.5735164993202488e-07  0.9999997615814209  0.357196182012558 ]
[ 0.0  0.0  0.0  1.0 ]
```

Apply the visualization-to-ground rotation and translation in [A.1](#physical-register) to this world transform to recover the active pose. The complete active USD-camera rotation and RPY are in [B.10](#calibration-microscopic-imager). The source-derived pose is an optics-box-face estimate, not a high-precision survey. The MI keeps its 0.01 m near plane and 200 m far plane; no visibility exception or enlarged near plane was introduced.

### C.1 Original extended-arm calibration pose

This reference is preserved for retargeting using source `CAHVOR_POS/QUAT`; it is **not** the active stowed mount.

| Reference quantity | Value |
| --- | --- |
| Ground FLU center (m) | `(1.12098, -0.084947, 0.18492299999999998)` |
| Ground FLU boresight | `(0.03178482877617587, 0.019939079992445242, -0.9992958309473345)` |
| USD-camera RPY in FLU (degrees) | `(1.4576092350324792, 1.5810624980038392, -105.21607328896819)` |
| Mount group | arm_reference_pose |
| Interpretation | Calibration reference arm pose; not stowed. Retarget using CAHVOR_POS/QUAT for a different arm pose. |

Reference camera-to-ground rotation:

```text
[ -0.2623599648215005  0.964446459643318  -0.03178482877617587 ]
[ -0.9645755398600978  -0.2630522020296652  -0.019939079992445242 ]
[ -0.027591244307967663  0.025427652050749597  0.9992958309473345 ]
```


<a id="visibility-audit"></a>

## Appendix D. Historical visibility measurements and clipping overrides

These are recorded **9 × 9 frustum-ray construction audits**, not newly rendered validation. Depth ranges measure forward depth of intersected source surfaces in metres. A source object label is retained only where it identifies the surface behind a meaningful measurement. Native left/right labels can be opposite physical rover sides. Counts are intersections, not necessarily distinct rays; they can exceed 81.

Near clipping bypasses opaque lens/camera-housing surfaces while preserving the selected camera pose. Every object inside the near plane disappears, including legitimate nearby rover geometry. The selected values therefore cannot be treated as hardware focus limits. Lens distortion and detector response remain unmodeled. Historical records cover the four mast cameras and two front Hazcams; the rear Hazcams and MI retain 0.01 m near clips without these override records. All far clips are 200 m.

| Camera | Clip near/far (m) | Housing surface | Housing intersections remaining | Other intersections retained | Other intersections clipped |
| --- | --- | --- | --- | --- | --- |
| navcam_left | `(0.06, 200.0)` | mast_top | 0 | 0 | 0 |
| navcam_right | `(0.06, 200.0)` | mast_top | 0 | 0 | 0 |
| pancam_left | `(0.06, 200.0)` | mast_top | 0 | 0 | 0 |
| pancam_right | `(0.06, 200.0)` | mast_top | 0 | 0 | 0 |
| hazcam_front_left | `(0.05, 200.0)` | body | 0 | 68 | 36 |
| hazcam_front_right | `(0.05, 200.0)` | body | 0 | 34 | 4 |

### navcam_left: measured source-surface forward depth

| Surface | Minimum and maximum forward depth (m) |
| --- | --- |
| mast_top | `(0.0105398981568082, 0.04123185635633625)` |

### navcam_right: measured source-surface forward depth

| Surface | Minimum and maximum forward depth (m) |
| --- | --- |
| mast_top | `(0.004003593698148679, 0.040562702309480975)` |

### pancam_left: measured source-surface forward depth

| Surface | Minimum and maximum forward depth (m) |
| --- | --- |
| mast_top | `(0.012528384633524178, 0.03975083078011999)` |

### pancam_right: measured source-surface forward depth

| Surface | Minimum and maximum forward depth (m) |
| --- | --- |
| mast_top | `(0.012819866454137064, 0.040245468949006075)` |

### hazcam_front_left: measured source-surface forward depth

| Surface | Minimum and maximum forward depth (m) |
| --- | --- |
| arm_base | `(0.03096957025592566, 0.09071015803682111)` |
| arm_joint1 | `(0.03231787638391216, 0.06504721502810107)` |
| arm_mount | `(0.018064692483769487, 0.02751139238705168)` |
| suspension_right_front_rocker | `(0.16974848227738853, 0.32076348013536926)` |
| suspension_right_front_wheel | `(0.220167016238386, 0.4603385042669505)` |
| suspension_left_front_wheel | `(0.2538124413750862, 0.43835989540939496)` |
| suspension_right_front_axl | `(0.3449377836398091, 0.3449377836398091)` |
| body | `(0.0020557592947574675, 0.015453597606714492)` |
| suspension_left_front_rocker | `(0.2923400534704549, 0.34853689970468804)` |
| suspension_left_front_axl | `(0.3733630002371462, 0.3733630002371462)` |

### hazcam_front_right: measured source-surface forward depth

| Surface | Minimum and maximum forward depth (m) |
| --- | --- |
| arm_joint1 | `(0.04096859615966507, 0.061731136433141154)` |
| suspension_right_front_wheel | `(0.3363728333085063, 0.45831578360272285)` |
| suspension_left_front_wheel | `(0.23755350404701997, 0.4923417955346242)` |
| suspension_right_front_rocker | `(0.24977950234123766, 0.31160015910620065)` |
| suspension_right_front_axl | `(0.3334981992937976, 0.3334981992937976)` |
| body | `(0.0017999785587066832, 0.015459655341437138)` |
| suspension_left_front_rocker | `(0.32689020301056004, 0.32935395188961836)` |
| suspension_left_front_axl | `(0.3499942192857828, 0.3499942192857828)` |

The front Hazcam records demonstrate the compromise: nearby arm fragments are clipped along with housing geometry, while farther arm, suspension, wheel, and terrain geometry can remain visible. Source calibration data is unchanged. As a cross-model illustration retained from the construction notes, Curiosity Mastcam-left's visualization housing was about 0.16 m ahead of its calibration center; this is **not** an Opportunity camera measurement. The broader reason for overrides is that the NASA visualization is not precision optical/mechanical CAD.

<a id="hardware-reference"></a>

## Appendix E. Hardware reference inventory, scope, and sources

### E.1 Published physical reference versus the current profile

These NASA/JPL/PDS entries are reference hardware descriptions. They do not add masses to the link budget or create sensors. The MER2 host record and Spirit mass/IMU references describe the shared MER hardware class; Opportunity-specific optical calibration remains MER1. The current 4.0 m/s command cap deliberately exceeds the retained **0.05 m/s** flight reference and is a simulation profile choice, not evidence of MER performance.

| Reference quantity | Recorded value |
| --- | --- |
| Selected reference mass (kg) | 185.0 |
| Archival design mass (kg) | 180.0 |
| Wheel diameter (m) | 0.26 |
| PDS dimension at wheelbase: length (m) | 1.41 |
| PDS dimension at wheelbase: width (m) | 1.22 |
| Solar-panel length (m) | 1.51 |
| Solar-panel width (m) | 2.25 |
| Deployed height (m) | 1.54 |
| Reference maximum speed (m/s) | 0.05 |
| Wheel count | 6 |
| Steering wheel count | 4 |
| Official link mass distribution found | No |
| Official link inertia tensors found | No |

The original PDS host description gives 180 kg, whereas NASA's Spirit overview and the JPL flight-system telecom description give 185 kg. MarsLab selects 185 kg while retaining the discrepancy. PDS dimensions ‘at wheelbase’ do not explicitly identify axle centers, so they do not replace the visualization-derived controller coordinates. Published total mass and sparse instrument masses constrain the engineering estimate; geometry-derived inertia remains computed rather than a NASA flight tensor. The native MER frame and distinct mechanical/navigation origins are explained in Appendix A.

Mass selection sources: [Spirit](https://science.nasa.gov/mission/mer-spirit/), [Mars Exploration Rover Telecommunications System](https://descanso.jpl.nasa.gov/DPSummary/MER_article_cmp20051028.pdf). Geometry source: [PDS instrument host description, Rover on the Surface of Mars](https://pds.nasa.gov/data/pds4/context-pds4/instrument_host/spacecraft.mer2_1.0.xml).

### E.2 Scientific instruments

Among the scientific instruments below, only Pancam and MI have rendered camera outputs. The other entries preserve historical instrument specifications and their original proposed integration category; metadata interfaces and passive-tool descriptions do **not** mean implemented physical emulators. Individual instrument masses below are reference specifications, not extra rigid-body masses.

#### Panoramic Camera

Rendered camera (implemented RGB pinhole).

| Specification | Recorded reference |
| --- | --- |
| Components | `(pancam_left, pancam_right)` |

#### Microscopic Imager

Rendered camera (implemented RGB pinhole).

| Specification | Recorded reference |
| --- | --- |
| Components | `(microscopic_imager)` |

#### Mini-TES

Reference metadata only; no measurement emulator.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 1 |
| Type | thermal infrared emission spectrometer |
| Mount | body, optical path through Pancam mast |
| Mass (kg) | 2.4 |
| Dimensions (m) | `(0.235, 0.163, 0.155)` |
| Spectral range (µm) | `(5.0, 29.5)` |
| Selectable FOV (mrad) | `(8.0, 20.0)` |

Source: [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/).

#### Mössbauer spectrometer

Reference metadata only; no measurement emulator.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 1 |
| Type | iron mineralogy spectrometer |
| Mount | robotic arm turret |
| Sampled diameter (m) | `(0.015, 0.02)` |

Source: [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/).

#### APXS

Reference metadata only; no measurement emulator.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 1 |
| Type | alpha particle x-ray spectrometer |
| Mount | robotic arm turret |
| Sampled diameter (m) | 0.038 |
| Dimensions (m) | `(0.084, 0.052)` |

Source: [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/).

#### Rock Abrasion Tool

Passive reference metadata only; no tool/material process.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 1 |
| Type | tool |
| Mount | robotic arm turret |
| Upper mass bound (kg) | 0.72 |

Source: [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/).

#### Magnet Array

Passive reference metadata only; no tool/material process.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 7 |
| Type | passive dust collector |
| Components — Rat | 4 |
| Components — Front capture | 1 |
| Components — Front filter | 1 |
| Components — Deck sweep | 1 |

Source: [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/).

#### Calibration Targets

Passive reference metadata only; no tool/material process.

| Specification | Recorded reference |
| --- | --- |
| Type | passive calibration references |
| Components | `(pancam sundial on deck, mossbauer target beneath panels, also usable by APXS, apxs target inside dust doors, mini_tes internal mast target, mini_tes external deck target)` |

Source: [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/).

### E.3 Engineering sensors and telemetry

Unknown quantities are explicitly marked as not specified, rather than inferred from the number of visible parts.

#### IMU

Ideal dynamic IMU implemented with runtime assumptions.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 1 |
| Model | Litton LN-200S |
| Channels — Fiber optic gyro | 3 |
| Channels — Silicon accelerometer | 3 |
| Mass (kg) | 0.75 |
| Nominal sampling frequency (Hz) | 400 |
| Spacecraft accumulated-data frequency (Hz) | 8 |
| Mount | inside rover, explicitly not rover center of mass |
| Accelerometer range (g) | 80 |
| Notes | Source describes EDL telemetry averaging; avoid asserting 8 Hz is mandatory surface simulation rate. |

Source: [Mars Exploration Rover Spirit Inertial Measurement Unit](https://pds.nasa.gov/ds-view/pds/viewContext.jsp?identifier=urn:nasa:pds:context:instrument:imu.mer2&version=1.2).

Actual runtime: chassis origin `(0,0,0)`, identity rotation, requested 8 Hz, gravity-inclusive readings, and zero injected acceleration/angular-rate noise. The historical 400 Hz hardware and 8 Hz accumulated EDL telemetry are distinct from a guaranteed surface-simulation cadence. The 80 g range is copied as an instrument specification; no Mars-g conversion or simulator saturation model is implied.

#### Wheel drive encoders

Joint-state representation proposed; see actual implementation below.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 6 |
| Type | rotary position |
| Quantity note | One per six independently driven wheels; count follows described six-wheel mechanism. |

Source: [Mars Exploration Rover Mobility and Robotic Arm Operational Performance](https://robotics.jpl.nasa.gov/media/documents/MobIDDPerf90sols.pdf).

Actual runtime: mobility joint states/odometry are available; separate physical encoder or potentiometer electronics, redundancy, quantization, and failure modes are not modeled.

#### Steering encoders

Joint-state representation proposed; see actual implementation below.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 4 |
| Type | incremental magnetic encoder |

Source: [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf).

Actual runtime: mobility joint states/odometry are available; separate physical encoder or potentiometer electronics, redundancy, quantization, and failure modes are not modeled.

#### Arm encoders

Joint-state representation proposed; see actual implementation below.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 5 |
| Type | incremental magnetic encoder |

Source: [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf).

Actual runtime: this channel has no dedicated simulated measurement. In particular, the arm and high-gain antenna remain fixed and do not acquire active joints merely because the historical inventory lists their transducers.

#### High gain antenna encoders

Joint-state representation proposed; see actual implementation below.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 2 |
| Type | incremental magnetic encoder |

Source: [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf).

Actual runtime: this channel has no dedicated simulated measurement. In particular, the arm and high-gain antenna remain fixed and do not acquire active joints merely because the historical inventory lists their transducers.

#### Steering potentiometers

Joint-state representation proposed; see actual implementation below.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 4 |
| Type | backup joint angle |

Source: [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf).

Actual runtime: mobility joint states/odometry are available; separate physical encoder or potentiometer electronics, redundancy, quantization, and failure modes are not modeled.

#### Arm potentiometers

Joint-state representation proposed; see actual implementation below.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 5 |
| Type | backup joint angle |

Source: [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf).

Actual runtime: this channel has no dedicated simulated measurement. In particular, the arm and high-gain antenna remain fixed and do not acquire active joints merely because the historical inventory lists their transducers.

#### High gain antenna potentiometers

Joint-state representation proposed; see actual implementation below.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 2 |
| Type | backup joint angle |

Source: [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf).

Actual runtime: this channel has no dedicated simulated measurement. In particular, the arm and high-gain antenna remain fixed and do not acquire active joints merely because the historical inventory lists their transducers.

#### Suspension potentiometers

Joint-state representation proposed; see actual implementation below.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 3 |
| Components | `(left rocker-bogie relative angle, right rocker-bogie relative angle, differential left-right rocker relative angle)` |

Source: [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf).

Actual runtime: mobility joint states/odometry are available; separate physical encoder or potentiometer electronics, redundancy, quantization, and failure modes are not modeled.

#### Wheel motor current voltage

Reference metadata only; no measurement emulator.

| Specification | Recorded reference |
| --- | --- |
| Quantity | Not specified |
| Type | engineering telemetry |

Source: [Mars Exploration Rover mission](https://doi.org/10.1029/2002JE002038).

Actual runtime: this channel has no dedicated simulated measurement. In particular, the arm and high-gain antenna remain fixed and do not acquire active joints merely because the historical inventory lists their transducers.

#### Reference solar cells

Reference metadata only; no measurement emulator.

| Specification | Recorded reference |
| --- | --- |
| Quantity | Not specified |
| Type | engineering irradiance/dust telemetry |

Source: [Mars Exploration Rover mission](https://doi.org/10.1029/2002JE002038).

Actual runtime: this channel has no dedicated simulated measurement. In particular, the arm and high-gain antenna remain fixed and do not acquire active joints merely because the historical inventory lists their transducers.

#### Warm Electronics Box (WEB) temperature monitoring

Reference metadata only; no measurement emulator.

| Specification | Recorded reference |
| --- | --- |
| Quantity | Not specified |
| Type | engineering thermal telemetry |

Source: [Mars Exploration Rover mission](https://doi.org/10.1029/2002JE002038).

Actual runtime: this channel has no dedicated simulated measurement. In particular, the arm and high-gain antenna remain fixed and do not acquire active joints merely because the historical inventory lists their transducers.

#### Microscopic imager contact sensor

Reference metadata only; no measurement emulator.

| Specification | Recorded reference |
| --- | --- |
| Quantity | 1 |
| Type | contact/proximity switch |
| Mount | arm turret MI |

Source: [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/).

Actual runtime: this channel has no dedicated simulated measurement. In particular, the arm and high-gain antenna remain fixed and do not acquire active joints merely because the historical inventory lists their transducers.

### E.4 Equipment excluded from the surface-rover model

**Descent camera.** Quantity: 1; Location: lander radar bracket; Raster (pixels): `(1024, 1024)`; Field of view (degrees): `(45, 45)`. Source: [Mars Exploration Rover Engineering Cameras](https://www-robotics.jpl.nasa.gov/media/documents/maki-jgr-2003je002077.pdf).

**Backshell imu.** Quantity: 1. Source: [Mars Exploration Rover Spirit Inertial Measurement Unit](https://pds.nasa.gov/ds-view/pds/viewContext.jsp?identifier=urn:nasa:pds:context:instrument:imu.mer2&version=1.2).

**Lander petal encoders and potentiometers.** Quantity: 3. Source: [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf).

### E.5 Limits of the reference inventory

- No public source reviewed provides all flight link masses/inertias; any analytic partition is explicitly a MarsLab engineering approximation.
- No lidar fitted. No GPS receiver fitted.
- Spectrometer/environment/housekeeping interfaces do not claim physical sensor emulation.
- Historical original complement, excluding later hardware failures.
- MER Nav-origin ground height uses published nominal body clearance, not a millimetre-accurate flight survey.
- MI runtime mounting is a MarsLab geometry-derived proxy matched to the fixed stowed arm mesh; source NASA reference pose is preserved separately.

The surface-rover complement describes the original hardware, not later Opportunity failures or degradation. No GPS or LiDAR is fitted in the retained mission description; neither is introduced by this model. Spectrometer, environmental, and housekeeping records remain descriptive. Native close-focus microscopy, filter spectral response, solar power, motor electronics, and thermal evolution require separate physical models.

### E.6 Retained primary-source catalog

- **science** — [Science Instruments](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/science-instruments/). NASA.
- **engineering_cameras** — [Mars Exploration Rover Engineering Cameras](https://www-robotics.jpl.nasa.gov/media/documents/maki-jgr-2003je002077.pdf). NASA JPL. Locator: Table 3, page 4; sections 2.4.2–2.4.4, pages 5–7. DOI: `10.1029/2003JE002077`.
- **imu** — [Mars Exploration Rover Spirit Inertial Measurement Unit](https://pds.nasa.gov/ds-view/pds/viewContext.jsp?identifier=urn:nasa:pds:context:instrument:imu.mer2&version=1.2). NASA PDS.
- **mobility** — [Mars Exploration Rover Mobility and Robotic Arm Operational Performance](https://robotics.jpl.nasa.gov/media/documents/MobIDDPerf90sols.pdf). NASA JPL. Locator: section 3.1, page 2.
- **potentiometers** — [Mars Exploration Rover Potentiometer Problems, Failures and Lessons Learned](https://ntrs.nasa.gov/api/citations/20060028248/downloads/20060028248.pdf). NASA NTRS/JPL. Locator: Introduction, first page.
- **geometry** — [Mars Exploration Rover 2 instrument host, version 1.0](https://pds.nasa.gov/data/pds4/context-pds4/instrument_host/spacecraft.mer2_1.0.xml). NASA PDS. Locator: Rover on the Surface of Mars.
- **mass_current** — [Spirit](https://science.nasa.gov/mission/mer-spirit/). NASA.
- **mass_telecom** — [Mars Exploration Rover Telecommunications System](https://descanso.jpl.nasa.gov/DPSummary/MER_article_cmp20051028.pdf). NASA JPL. Locator: section 1.3/Table 1-2.
- **sun_finding** — [The Mars Exploration Rover Cameras: A Status Report](https://ntrs.nasa.gov/citations/20050175949). NASA NTRS/JPL.
- **engineering_additional** — [Mars Exploration Rover mission](https://doi.org/10.1029/2002JE002038). JPL author paper, Wiley primary publication. Locator: abstract; section 3.8.2.
- **naif_camera_kernels** — [MER camera instrument kernels](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/ik/). NASA JPL NAIF.
- **naif_frame_kernels** — [MER reference frame kernels](https://naif.jpl.nasa.gov/pub/naif/MER/kernels/fk/). NASA JPL NAIF.

Local research-cache paths, extraction schema/version fields, hash inventories, and exhaustive mesh/helper-name inventories are intentionally omitted. The pinned source identity, physical selection criteria, all substantive numerical data, meaningful measurement-surface identities, and primary-source links are retained. No original asset metadata files were deleted as part of this consolidation.
