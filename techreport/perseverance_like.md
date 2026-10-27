# Perseverance-like Rover: Implementation Technical Report

**Inspection date:** 2026-10-27. **Scope:** the current MarsLab working tree, including uncommitted implementation changes. Numerical values below describe authored assets and selected configuration; they are not measurements from a new simulator run.

## 1. Implementation and asset provenance

MarsLab implements a mobile research rover with Perseverance-derived appearance, six driven wheels, four steering wheels, passive rocker-bogie suspension, and a custom perception payload. The active entry is [the Perseverance profile](../configs/robots/perseverance.yaml), selected by [the scenario configuration](../configs/config.yaml). Isaac Sim loads [m2020_lidar.usda](../assets/robots/perseverance/m2020_lidar.usda); ROS robot-description preparation uses [m2020_lidar.urdf](../assets/robots/perseverance/m2020_lidar.urdf). These are complementary descriptions: the URDF is not imported anew to construct the Isaac vehicle at each launch.

The visual lineage begins with NASA/JPL's [m2020-urdf-models repository](https://github.com/nasa-jpl/m2020-urdf-models), released for operations visualization. It credits NASA/JPL-Caltech, rover modeler and texture artist Zareh Gorjian, the Perseverance/Ingenuity teams, and the JPL RSVP team. MarsLab's immediate source is [the adapted fork at commit `8b591ec417d34d3b152e067b378fe45f2b5810dc`](https://github.com/kimhoyun-robotair/m2020-urdf-models/tree/8b591ec417d34d3b152e067b378fe45f2b5810dc). Consequently, NASA ancestry establishes visual provenance, not NASA validation of the fork's dynamics.

The vendored source subset contains all transitive mesh, buffer, and image dependencies of the current companion URDF: 20 glTF meshes, their 20 binary buffers, and one shared JPEG texture. These 41 files were copied byte-for-byte from the pinned adapted fork; that does not assert byte identity with NASA's original release. They represent the chassis, differential, rockers, bogies, steering structures, six wheels, remote-sensing mast and head, and high-gain antenna axes. Isaac's prebuilt [m2020.usd](../assets/robots/perseverance/m2020.usd) composes separate base, physics, robot, and sensor layers in [configuration/](../assets/robots/perseverance/configuration/), with a local texture copy. The runtime uses these USD layers rather than the glTF files directly. Rendering also references the Isaac material library's `gltf/pbr.mdl` shader; local geometry does not mean that the asset is independent of Isaac's material environment.

The LiDAR overlay references MarsLab-authored [2-D](../assets/robots/sensors/lidar_2d.usda) and [3-D](../assets/robots/sensors/lidar_3d.usda) sensor assemblies. Their housings, pedestal, braced tube, plates, and fasteners are illustrative research hardware. No Blender source or asset regeneration step is needed for normal loading. The repository records attribution and the upstream license-status limitation in [LICENSE-M2020.txt](../LICENSE-M2020.txt) and [the local notice](../assets/robots/perseverance/LICENSE.md).

## 2. Coordinates, articulation, and mobility

The USD declares meters and a Z-up world. Runtime mount poses use **+X forward, +Y left, +Z up**. The chassis frame is `Body_Chassis`; ROS operational odometry uses `odom` and `base_link`. Sensor translations are coordinates in their parent frame, not heights above arbitrary terrain or offsets from the chassis center of mass.

The raw companion URDF contains **86 links and 85 joints**: 19 revolute, 64 fixed, and two floating. [ROS preparation](../launch/companion_urdf.py) removes the synthetic ground/root joint and fixes the debris-shield connection, yielding **85 links and 84 joints**: 19 revolute and 65 fixed. Static USD inspection independently found **85 rigid bodies**, 19 revolute joints, and 65 fixed joints. A rigid-body or joint count is not a count of independent actuated degrees of freedom.

The 19 revolute joints comprise six `*_DRIVE`, four `*_STEER`, three differential, two bogie, two mast, and two high-gain-antenna joints. The selected controller actively commands the ten wheel/steering coordinates. Mast and antenna articulation does not imply that MarsLab provides their flight pointing or science-operation controllers. Likewise, the model has no independently actuated sampling-arm or turret joint chain, even where surface detail may be incorporated into the chassis mesh.

The [runtime differential implementation](../marslab/robots/differential.py) adds a PhysX mimic constraint between `LEFT_DIFFERENTIAL` and `RIGHT_DIFFERENTIAL`, preserving equal-and-opposite physical rocker rotation. Its sign is resolved from the authored joint axes. This is a runtime constraint, not an extra motor or an additional independent degree of freedom. Rocker stiffness remains zero. Infinite imported rocker limits are replaced with numerical bounds of ±10¹⁰ degrees when needed by PhysX; these are not mechanical travel specifications.

The [drive setup](../marslab/robots/drive_api_setup.py) verifies steering travel and applies the configured gains before simulation reset, then verifies owned gains afterward. [Rover kinematics](../marslab/robots/rover_control.py) converts linear/angular commands to six wheel rates and four steering angles, accounting for unequal middle-wheel and corner-wheel tracks. These are geometric commands, not NASA motor-current or gearbox models.

| Configured quantity | Current value |
|---|---:|
| Wheel rolling radius used by control/odometry | 0.2667 m |
| Front-to-rear axle spacing | 2.26 m |
| Steering-axle midpoint offset | 0.05502 m |
| Corner / middle wheel track | 2.125 / 2.369 m |
| Linear / yaw command caps | 4 m/s / 0.7 rad/s |
| Maximum steering angle | ±0.9 rad |
| Steering ramp rate | 2 rad/s |
| Wheel angular-target acceleration / deceleration limit | 0.5 / 1.5 rad/s² |
| Steering alignment tolerance / wheel angular stopping threshold | 0.02 rad / 0.05 rad/s |
| Command timeout | 0.5 s |

The [runtime ramp](../marslab/runtime/main_loop.py) limits wheel angular-target changes by `max_wheel_accel_rate × physics_dt`; its deceleration multiplier is 3. These limits are controller settings, not documented flight-motor acceleration limits. The speed caps describe accepted commands, not demonstrated sustained speed on terrain.

## 3. Mass, inertia, and contact physics

The source asset supplies explicit link masses, centers of mass, and inertias. MarsLab retains these imported values and combines its added LiDAR hardware with the existing chassis. The source masses are round engineering assignments; this report found no traceable NASA per-component mass/inertia dataset establishing that they are flight measurements. Appendix A preserves the complete attachment geometry, component mass/tensor register, original and merged chassis properties, and whole-rover COM calculation without requiring separate construction metadata.

| Mass group | Assigned mass |
|---|---:|
| Original chassis | 670 kg |
| Added LiDAR assemblies, including supports | 5.688155 kg |
| Combined chassis | 675.688155 kg |
| Six wheels | 30 kg each; 180 kg total |
| Two rockers | 18 kg each; 36 kg total |
| Two bogies | 12 kg each; 24 kg total |
| Four steering bodies | 4 kg each; 16 kg total |
| Center differential | 8 kg |
| Mast azimuth / elevation bodies | 2 / 8 kg |
| Antenna azimuth / elevation bodies | 1 / 4 kg |
| Debris shield | 2 kg |
| Auxiliary frame links retained in the moving tree | 0.64 kg combined |
| Whole modeled rover before / after added assemblies | 951.64 / 957.328155 kg |

The many auxiliary `Frame_*` links have small positive inertial placeholders, typically 0.01 kg and diagonal inertia 10⁻⁶ kg·m². They are coordinate-frame bookkeeping, not a component-level reconstruction of all flight hardware. The raw URDF also contains a synthetic `ground` link whose 0.01 kg is excluded from the moving rover total; robot-description preparation removes that root.

Added hardware uses aluminum density 2,700 kg/m³, idealized box/cylinder envelopes, and a tube with outer/inner radii 0.022/0.0185 m. The two scanner masses are assumptions of 0.38 and 0.65 kg. Plate, tube, brace, and fastener contributions account for the remainder. The calculation neglects cosmetic bevels, retains the original chassis inertia, and combines contributions using mass-weighted centers and the parallel-axis theorem. It therefore documents an explicit approximation rather than a measured vendor assembly.

The resulting chassis center of mass is **(-0.056155, -0.057125, 1.148635) m**, a shift of approximately (+5.526, +2.607, +2.072) mm. Its inertia tensor about that center, in the chassis coordinate axes, is:

```text
I [kg·m²] = [158.068855    4.219007   25.284254
               4.219007 413.871612   13.536386
              25.284254  13.536386  457.640310]
```

The USD stores equivalent principal inertias **(155.9131, 410.05435, 463.61334) kg·m²** and a principal-axis quaternion. Their diagonal entries should not be compared directly with the diagonal of the unrotated tensor. Float storage rounds the chassis mass to 675.688171 kg; fresh inspection sums the composed USD masses to **957.328171 kg**, effectively matching the URDF's 957.328155 kg at storage precision. The recorded initial whole-rover center of mass is **(-0.026153, -0.044401, 0.950190) m**. The recorded 1.048827 m support-polygon margin is a static, initial-pose calculation, not a dynamic rollover certificate.

[Runtime physics overrides](../marslab/robots/rover.py) set wheel static/dynamic friction to **0.6/0.5**, restitution to **0**, chassis angular/linear damping to **12/0.5**, and rocker/bogie damping to **75/50**. The active scenario uses Mars gravity **3.72 m/s²**. Wheel friction is bound and checked on effective colliders. These are rigid-body contact settings; they do not establish calibrated soil sinkage, regolith deformation, flexible spokes, or wheel damage.

Instance-aware USD inspection finds **42 active collision-API prims**, all authored with `convexHull` approximation: 20 rover collision-wrapper Xforms and 22 LiDAR-assembly meshes. The original rover geometry is instanced; traversing only ordinary stage prims would miss those 20 wrappers. These are authored collision declarations, not a newly measured count of PhysX's cooked shapes. Convex-hull contact does not reproduce every visible recess, spoke opening, or tread detail.

The companion URDF has no collision elements. Isaac collision behavior comes from the USD composition, while the URDF serves the ROS description and transforms. This distinction matters when reusing the URDF in another physics engine: its visual meshes alone do not reproduce MarsLab contact behavior.

Wheel velocity drives use damping **1,000**, maximum drive-force setting **10⁶**, and brake stiffness **50,000**. Steering uses stiffness/damping **50,000/5,000** and maximum drive-force setting **100,000**. The drive type is `acceleration`; these PhysX settings must not be presented as measured NASA actuator torques or gearbox specifications.

## 4. Sensors, mounts, and ROS outputs

All four acquired sensor types below attach to the chassis in this profile. The prebuilt USD contains no authored Camera prim; runtime creates the single acquired camera. In particular, that camera is **not parented to the articulated mast head**, despite its elevated placement. Mount orientations use roll/pitch/yaw in degrees.

| Sensor | Translation (m) | Mount RPY (°) | Acquisition/configuration |
|---|---|---|---|
| Primary camera | (0.752095, -0.774360, 1.837690) | (0, 6.6, 0) | 640 × 480; 135° horizontal FOV; clipping 0.3–200 m |
| 2-D RTX LiDAR | (0.90, 0.25, 1.40) | (0, 0, 0) | 0.2–200 m; published 135° forward sector; 10 Hz scan rate |
| 3-D RTX LiDAR | (0.45, 0.25, 2.20) | (0, 0, 0) | 3.5–200 m; 220° horizontal / 45° vertical FOV; 30 Hz scan-rate override |
| IMU | (0, 0, 0) | (0, 0, 0) | 30 Hz; gravity included in acquisition |

The camera's YAML contains `focal_length_mm: 18`, but [camera spawning](../marslab/sensors/camera_spawner.py) gives an explicit horizontal FOV precedence: it derives focal length from aperture and 135° FOV. Thus 18 mm is not an independently effective calibrated focal length here. The camera uses one render product for RGB and image-plane depth. `depth_output` defaults to true; **`depth_sensor.enabled: false` disables the optional depth-noise processing, not the raw depth output**. The configured depth sigma of 0.005 m is consequently inactive. Renderer depth is privileged scene geometry, not stereo matching or a reconstruction of a real Perseverance depth instrument.

The [2-D LiDAR spawner](../marslab/sensors/lidar_2d_spawner.py) uses Isaac's `Example_Rotary_2D` model, enforces a horizontal plane, acquires a full turn, and crops the usable sector to ±67.5°. This preserves native full-scan timing; the reported sector need not equal exactly 135° because rays are discretized. The [3-D spawner](../marslab/sensors/lidar_3d_spawner.py) starts from `OS1_REV6_128ch10hz1024res`, then applies the YAML range, horizontal sector, **30 Hz** scan rate, and rescaled 45° emitter elevations. The variant's `10hz` name therefore does not describe the effective requested scan rate. Both use [range overrides](../marslab/sensors/lidar_runtime.py) that set `nearRangeM` and also `rangeOffsetM` to the configured minimum: this shifts the ray origin and is more than simply discarding near returns. Neither is a verified replica of flight or commercial sensor behavior.

The two sensor meshes are rigidly integrated into the existing chassis mass. They introduce no separate URDF sensor joints. Their runtime frames are instead broadcast through [static sensor transforms](../marslab/ros2_bridge/tf_broadcaster.py). The 3-D mount's optical center is above the recorded 2.086054 m camera-head envelope. This is a documented mount-clearance choice, not a claim that all dynamic scan occlusions have been measured.

The [IMU acquisition](../marslab/sensors/imu_spawner.py) feeds both raw and noisy streams from the same timestamped sample. [Noise processing](../marslab/ros2_bridge/imu_noise_publisher.py) adds independent Gaussian acceleration and angular-rate noise with standard deviations **0.05 m/s²** and **0.005 rad/s**. [Runtime setup](../marslab/runtime/post_reset.py) derives separate deterministic child seeds from sensor master seed **42** for wheel odometry and IMU noise. Orientation is copied rather than independently noise-modeled. Bias instability, temperature response, misalignment, and long-term drift are not implemented by this Gaussian model.

| ROS topic | Meaning / frame |
|---|---|
| `/rover/rgb/image_raw`, `/rover/rgb/camera_info` | RGB image and rendered camera intrinsics; `camera_optical_frame` |
| `/rover/depth/image_raw`, `/rover/depth/points` | Renderer depth and derived cloud; `camera_optical_frame` |
| `/rover/scan` | Cropped 2-D `LaserScan`; `lidar_2d_link` |
| `/rover/lidar/points` | RTX 3-D cloud; `lidar_link` |
| `/rover/imu`, `/rover/imu_noisy` | Raw/noisy inertial samples; `imu_link` |
| `/rover/joint_states` | Articulation state for robot-description consumers |
| `/rover/odom` | Wheel-derived operational odometry; `odom` → `base_link` |
| `/rover/GT_Trajectory` | Simulator absolute pose for evaluation, separate from operational odometry |
| `/rover/cmd_vel` | Linear/yaw motion command input |

Camera optical axes are represented by a separate fixed transform from `camera_link`. Wheel odometry is enabled with left/right slip settings of **0.02** and wheel-rate noise sigma **0.05**; these perturb the odometry estimate and do not themselves implement physical wheel–soil slip. Camera and ROS publishing throughput still depends on render/physics scheduling; scan-rate settings are not measured end-to-end topic rates.

## 5. Comparison with official NASA descriptions

| Aspect | NASA reference | Current MarsLab interpretation |
|---|---|---|
| Mass | 1,025 kg | 957.328155 kg nominal moving-tree total, about 67.67 kg or 6.60% lower; includes custom LiDAR hardware. |
| Overall size | Approximately 3 m long × 2.7 m wide × 2.2 m high | NASA-derived appearance; added mounts change the envelope. Controller wheelbase/track parameters are not overall dimensions. |
| Wheels and steering | Six driven wheels; four corner steering motors; 52.5 cm wheel diameter | Same mobility arrangement; controller diameter is 53.34 cm, about 1.6% larger. |
| Speed | 152 m/hour on flat, hard terrain | 4 m/s command cap, about 94.7 times that reference; no equal-performance claim. |
| Suspension | Rocker-bogie with differential | Rigid articulated bodies, passive damping, and an ideal mimic constraint; no flight-compliance calibration. |

The NASA values in this table come from [Perseverance Rover Components](https://science.nasa.gov/mission/mars-2020-perseverance/rover-components/). Percentage and speed-ratio comparisons are calculations from the cited values and MarsLab parameters.

NASA describes Mastcam-Z as a stereo zoom instrument with **24.2 cm separation** and up to **1600 × 1200 pixels**. MarsLab's single fixed 640 × 480 wide-angle camera has neither that stereo baseline nor zoom operation. NASA's **23-camera Mars 2020 total includes entry/descent/landing cameras across spacecraft components**; it should not be interpreted as 23 currently operating rover-body cameras that this implementation merely omits. See [NASA's instrument description](https://science.nasa.gov/mission/mars-2020-perseverance/science-instruments/) and [JPL's landing press kit](https://www.jpl.nasa.gov/news/press_kits/mars_2020/landing/mission/spacecraft/perseverance_rover/).

The research LiDARs have no equivalent in the documented flight payload. SuperCam's laser spectroscopy and RIMFAX's subsurface radar are different measurement systems; neither justifies labeling the RTX scanners as NASA sensor replicas. MarsLab also lacks operational implementations of the flight science-instrument suite, sample caching, radiation/power/thermal systems, and mission communications. Visible housings do not establish functional instrument simulation. NASA's [science-instrument inventory](https://science.nasa.gov/mission/mars-2020-perseverance/science-instruments/) is the comparison source.

## 6. Evidence and limits

This report combines direct inspection of the selected YAML, companion URDF, USD composition, physical-property record, controller, sensor spawners, and ROS publishers with the linked NASA/JPL references. Fresh static checks used [inspect_models.py](../tmp/techreport/inspect_models.py), with results in [model_audit.json](../tmp/techreport/model_audit.json) and input hashes in [evidence_hashes.json](../tmp/techreport/evidence_hashes.json). These local working artifacts are under ignored `tmp/`; the report's recorded values remain available without those artifacts in a clean clone. The checks verify composed configuration, description counts, and authored mass values; source notices and earlier mass calculations remain provenance evidence rather than new simulator experiments.

No Isaac playback, ROS topic-rate measurement, traction test, slope trial, sensor calibration experiment, or asset regeneration was performed for this report. The model is suitable to describe as a **Perseverance-like research platform**: recognizable visual heritage and useful rover articulation coexist with approximate mass properties, deliberately different motion limits, synthetic depth, added LiDAR equipment, and a simplified sensor suite. Quantitative conclusions about the actual NASA rover require additional validation beyond these authored settings.

## Appendix A. LiDAR construction and mass-property derivation

This appendix preserves the engineering design and calculation inputs for the two research attachments. Numbers carry enough digits to reproduce the construction calculation; those digits do not indicate measurement accuracy. Lengths and coordinates are in meters, masses in kilograms, and inertias in kg·m² unless stated otherwise. The assemblies are MarsLab designs, not NASA flight instruments or vendor CAD.

### A.1 Mount geometry, provenance, and construction boundary

The calculation starts from [the unmodified base rover USD](../assets/robots/perseverance/m2020.usd) and [the fork's original URDF at the pinned source revision](https://github.com/kimhoyun-robotair/m2020-urdf-models/blob/8b591ec417d34d3b152e067b378fe45f2b5810dc/rover/m2020.urdf). It retains the original chassis inertia before adding the component contributions below. The results are embodied in the LiDAR overlay USD and companion URDF linked in Section 1. Both additions belong to the existing `Body_Chassis` rigid body; there are no added sensor links or articulation joints.

Each sensor asset's mesh origin is its optical center. Its local +X/+Y/+Z axes point forward/left/up, respectively; the configured roll, pitch, and yaw are all zero. The centers lie inside the modeled optical windows, rather than at the scanner mass centers.

| Design quantity | Value / interpretation |
|---|---|
| Parent frame | `Body_Chassis` |
| Deck surface at the mounts | z = 1.13338005 |
| 2-D optical center | (0.9, 0.25, 1.4) |
| 3-D optical center | (0.45, 0.25, 2.2) |
| Optical-center elevation above the modeled deck | 0.26661995 for 2-D; 1.06661995 for 3-D |
| Existing camera-head highest initial vertex | z = 2.086054 |
| 3-D optical center above that initial camera-head vertex | 0.113946 |
| Scanner COM below its optical center | 0.0225 for 2-D; 0.014 for 3-D |
| Construction near-clip guidance | 0.20 for 2-D; 0.15 for 3-D, to start beyond the housing |

The 2-D scanner sits on a short solid pedestal on the forward deck. The 3-D scanner uses a bolted, diagonally braced aluminum tube on clear deck opposite the existing camera mast. Prior construction work inspected the composed USD in front, oblique, and close-up Blender renders. This is historical visual inspection, not a new validation run. The Blender editing source is not distributed.

The near-clip guidance describes construction clearance; it neither specifies measured housing radii nor overrides the active profile. The runtime settings remain 0.20–200 m for 2-D and 3.5–200 m for 3-D, with the FOV and scan rates in Section 4. In particular, the 3-D `rangeOffsetM` setting moves ray origins beyond nearby rover structure; the 0.15 m design figure is not its current minimum range. The optical-window placement and clipping reduce self-returns, but terrain, body tilt, articulated parts, and lower 3-D beams can still occlude rays. A far range of 200 m does not guarantee detection of every object at that distance.

The USD sensor assets supply materials and convex collision geometry. Their OBJ/MTL counterparts supply companion-URDF visuals. The prebuilt USD composition is loaded at runtime; construction metadata and prior previews do not supply live range settings or execute an asset builder. Static TF publication supplies `lidar_2d_link` and `lidar_link` below `Body_Chassis`.

### A.2 Component geometry and mass register

The eight principal components and eight fasteners are the complete 16-component analytical addition. All centers below are expressed directly in `Body_Chassis`. For boxes, dimensions are the component's principal geometric lengths; the two braces are inclined, so their inertia is rotated into chassis axes in A.3. For cylinders, `R`, `r`, and `h` denote outer radius, inner radius, and axial height. The scanner and vertical tube/cylinder axes are parallel to chassis Z.

| ID | Component | Mass | COM in chassis axes | Analytical envelope / dimensions |
|---|---|---:|---|---|
| S2 | 2-D scanner electronics and optics | 0.38 | (0.9, 0.25, 1.3775) | Box; 0.104 × 0.104 × 0.141 |
| P2 | 2-D deck plate | 0.7776 | (0.9, 0.25, 1.13938005) | Box; 0.16 × 0.15 × 0.012 |
| B2 | 2-D solid pedestal | 0.63938528388 | (0.9, 0.25, 1.223690025) | Box; 0.036 × 0.042 × 0.15661995 |
| S3 | 3-D scanner assembly | 0.65 | (0.45, 0.25, 2.186) | Solid cylinder; R=0.0595, r=0, h=0.14 |
| P3 | 3-D deck plate | 1.6632 | (0.45, 0.25, 1.14038005) | Box; 0.22 × 0.2 × 0.014 |
| T3 | 3-D mast tube | 1.16463574163 | (0.45, 0.25, 1.631690025) | Hollow cylinder; R=0.022, r=0.0185, h=0.96861995 |
| D− | 3-D diagonal brace, negative-X side | 0.174667088142 | (0.409, 0.25, 1.25538005) | Box; 0.014 × 0.02 × 0.231041121881 |
| D+ | 3-D diagonal brace, positive-X side | 0.174667088142 | (0.491, 0.25, 1.25538005) | Box; 0.014 × 0.02 × 0.231041121881 |

There are four F2 fasteners and four F3 fasteners. **Each has assigned mass 0.008 kg**, a uniform solid-cylinder envelope of radius **0.007 m**, inner radius **0**, and height **0.009 m**. Their individual centers are:

| Fastener | COM in chassis axes |
|---|---|
| F2-1 | (0.84, 0.195, 1.15138005) |
| F2-2 | (0.84, 0.305, 1.15138005) |
| F2-3 | (0.96, 0.195, 1.15138005) |
| F2-4 | (0.96, 0.305, 1.15138005) |
| F3-1 | (0.39, 0.195, 1.15138005) |
| F3-2 | (0.39, 0.305, 1.15138005) |
| F3-3 | (0.51, 0.195, 1.15138005) |
| F3-4 | (0.51, 0.305, 1.15138005) |

Aluminum density **2,700 kg/m³** determines the two plate, pedestal, mast-tube, and brace masses from their idealized volumes. The scanner masses **0.38 kg** and **0.65 kg** and each **0.008 kg** fastener mass are separate assignments. In particular, the fastener mass is not derived from that aluminum density: the listed cylindrical volume at 2,700 kg/m³ would weigh approximately 0.00374069437 kg. No material or measured vendor mass is thereby established for the fasteners. Small visual bevels are omitted; scanner inertias use uniform envelopes rather than detailed internal parts.

Including its four fasteners, the 2-D assembly contributes **1.82898528388 kg** and the 3-D assembly **3.85916991791 kg**. Their sum is **5.68815520179385 kg**. Direct mass weighting of the register gives an added-assembly COM of **(0.594694254736, 0.25, 1.39271541304) m** in chassis axes; this is a derived check, not a separately measured property.

### A.3 Component tensors and composition equations

The following symmetric tensors are about each component's own center of mass and expressed in chassis axes. Each row lists the six independent matrix entries; the lower triangle mirrors the upper triangle. **These are signed tensor entries**, not unsigned products of inertia. Zero entries are shown explicitly.

| Component | Ixx | Iyy | Izz | Ixy | Ixz | Iyz |
|---|---:|---:|---:|---:|---:|---:|
| S2 | 0.000972071666667 | 0.000972071666667 | 0.000685013333333 | 0 | 0 | 0 |
| P2 | 0.0014673312 | 0.0016682112 | 0.00311688 | 0 | 0 | 0 |
| B2 | 0.00140098953035 | 0.00137605350428 | 0.000163043247389 | 0 | 0 | 0 |
| S3 | 0.00163695729167 | 0.00163695729167 | 0.00115058125 | 0 | 0 | 0 |
| P3 | 0.0055711656 | 0.0067354056 | 0.01225224 | 0 | 0 | 0 |
| T3 | 0.091298062705 | 0.091298062705 | 0.000481140140761 | 0 | 0 | 0 |
| D− | 0.000685287239358 | 0.000779830326191 | 0.000106187559376 | 0 | -0.000256862003702 | 0 |
| D+ | 0.000685287239358 | 0.000779830326191 | 0.000106187559376 | 0 | 0.000256862003702 | 0 |
| Each F2 / F3 fastener | 1.52e-07 | 1.52e-07 | 1.96e-07 | 0 | 0 | 0 |

For a uniform box with principal dimensions $a,b,c$, the local tensor is

$$
I_{box}=\frac{m}{12}\operatorname{diag}(b^2+c^2,\ a^2+c^2,\ a^2+b^2).
$$

For a cylinder or tube with radii $R,r$ and height $h$, axis along its local Z,

$$
I_{cylinder}=\operatorname{diag}\left(
\frac{m}{12}[3(R^2+r^2)+h^2],
\frac{m}{12}[3(R^2+r^2)+h^2],
\frac{m}{2}(R^2+r^2)\right).
$$

Solid cylinders use $r=0$. Density-based mass uses $m=\rho abc$ for a box and $m=\rho\pi(R^2-r^2)h$ for a tube. Component rotation applies $I_i=R_i I_{local,i}R_i^T$; the opposite signs of brace $I_{xz}$ retain their mirrored inclinations. Thus applying the unrotated box formula directly to the chassis-axis brace tensors would be incorrect.

Let the original chassis have mass $m_0$, center $c_0$, and COM-centered tensor $I_0$, and the 16 additions have $(m_i,c_i,I_i)$. The merged mass, center, and tensor are

$$
M=m_0+\sum_i m_i,\qquad
C=\frac{m_0c_0+\sum_i m_ic_i}{M},
$$

$$
I_C=I_0+m_0\left[\|c_0-C\|^2\mathbf{1}-(c_0-C)(c_0-C)^T\right]
+\sum_i\left\{I_i+m_i\left[\|c_i-C\|^2\mathbf{1}-(c_i-C)(c_i-C)^T\right]\right\}.
$$

Here $\mathbf{1}$ is the 3 × 3 identity matrix. The original chassis tensor is retained as a component of this sum; the addition does not replace it with a new uniform chassis envelope. Diagonalizing $I_C=Q\Lambda Q^T$ gives the USD principal moments and principal-axis rotation. Static recomputation from the component register reproduces the recorded merged tensor at floating-point precision. This arithmetic consistency does not validate the assigned masses against real hardware.

### A.4 Original, merged, and whole-rover properties

The construction calculation recorded the following values. Whole-rover centers refer to the initial articulated pose and the same chassis-based coordinate system; they will change when articulated parts move.

| State | Mass (kg) | COM (m) |
|---|---:|---|
| Original chassis | 670 | (-0.0616804249584675, -0.0597322694957256, 1.14656329154968) |
| Chassis with both assemblies | 675.688155201794 | (-0.0561548566620771, -0.0571248459286079, 1.14863547745309) |
| Original whole rover | 951.639999985695 | (-0.0298638970568474, -0.0461610022476038, 0.947545431303649) |
| Whole rover with both assemblies | 957.328155187489 | (-0.0261529608635552, -0.0444013028839376, 0.950190497087617) |

The original chassis tensor about its original COM, in chassis axes, is:

```text
I_before [kg·m²] =
[    156.42206629253     5.3656768039137    26.0521847700414 ]
[    5.3656768039137    410.082499079656    13.9664068909662 ]
[   26.0521847700414    13.9664068909662    454.398877010627 ]
```

The merged chassis tensor about its new COM, in the same axes, is:

```text
I_after [kg·m²] =
[   158.068855478386     4.2190074420883    25.2842541604363 ]
[    4.2190074420883    413.871612172371    13.5363855863713 ]
[   25.2842541604363    13.5363855863713    457.640310001862 ]
```

The merged principal moments from the construction calculation are **(155.913101900716, 410.054338853253, 463.613336898651) kg·m²**. The [authored overlay](../assets/robots/perseverance/m2020_lidar.usda) expresses the corresponding principal rotation as the scalar-first quaternion **(w, x, y, z) = (0.9898891, -0.13549902, 0.04194739, -0.00029115428)**. The chassis COM shift is **(0.00552556829639043, 0.00260742356711777, 0.00207218590340608) m**, equivalent to approximately **(+5.526, +2.607, +2.072) mm**.

The construction masses differ in their final digits from independently summed URDF and float-valued USD masses in Section 3. This is numerical representation/rounding, not a different physical allocation. No whole-rover aggregate inertia tensor was supplied by this construction calculation; the chassis tensor must not be relabeled as a whole-rover tensor.

### A.5 Initial support calculation and validation limits

The recorded initial whole-rover COM projection lies **1.04882705965952 m** inside the convex hull of the **six initial wheel centers**. The hull is the chosen static support approximation; it is not a measurement of terrain contact patches or a compliant wheel/soil support region. This initial-pose criterion did not call for an added counterweight. It does not establish stability while steering, accelerating, articulating, climbing, or traversing sloped/deformable terrain. Those claims require dynamic Isaac observations and an appropriate physical-validation design.

The historical render inspection, explicit geometric mass assumptions, and successful arithmetic reconstruction answer different questions: appearance/clearance in inspected views, internally consistent modeled mass properties, and static support in one pose. None independently demonstrates flight fidelity or measured sensor performance.
