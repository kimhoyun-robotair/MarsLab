# Ingenuity: current MarsLab implementation technical report

**Inspection date:** 2026-10-27. **Implementation status:** a locally cached visual asset and cinematic animation adapter; Ingenuity is not currently a selectable MarsLab simulation robot.

## 1. Scope and implementation boundary

MarsLab's [robot selector](../marslab/config/yaml_loader.py) accepts `perseverance`, `spirit`, `opportunity`, and `curiosity`. There is no Ingenuity robot configuration in [configs/robots](../configs/robots), flight controller, or dedicated ROS integration. The existing Ingenuity implementation belongs to the promotional film workspace under `tmp/promo/`.

This report examines the current **v2** adapter, renderer, and cached upstream USD. Links beginning with `../tmp/` identify **local, Git-ignored inspection evidence**, not files distributed by an ordinary clone. The report records their relevant settings explicitly so that its conclusions remain readable without that workspace. Historical film outputs establish what was previously rendered; they do not establish a working flight simulator or a successful rerun of the current repository.

## 2. Visual asset provenance and composition

The cached source is NVIDIA's Isaac Sim **5.1** asset, [`NASA/Ingenuity/ingenuity.usd`](https://omniverse-content-production.s3-us-west-2.amazonaws.com/Assets/Isaac/5.1/Isaac/Robots/NASA/Ingenuity/ingenuity.usd). NVIDIA lists this asset in its [robot asset catalogue](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_robots.html). The preserved [NASA acknowledgement](../tmp/promo/licenses/INGENUITY_NASA_ACKNOWLEDGEMENT.txt) attributes the visual model to NASA. NASA's corresponding [Ingenuity 3D-model page](https://science.nasa.gov/resource/mars-ingenuity-helicopter-3d-model/) credits NASA/JPL-Caltech. The immediate distribution source used here is NVIDIA's USD package; this asset was not imported from the Perseverance URDF package.

The local source consists of `research/ingenuity.usd`, its `configuration/ingenuity_robot_schema.usd` layer, and ten JPEG textures, `Ingenuity_v3/0/texgen_0.jpg` through `texgen_9.jpg`. The [preparation script](../tmp/promo/research/prepare_ingenuity.py) resolves and caches referenced assets, then writes [scene/ingenuity.usda](../tmp/promo/scene/ingenuity.usda), a thin layer referencing the original `/Ingenuity` hierarchy. It preserves the chassis, four landing legs, solar panel, camera-housing meshes, miscellaneous equipment, and the two original rotor groups.

Read-only composition found 38 mesh prims, including three invisible helper meshes; the 35 visible meshes contain 9,092 triangles after polygon triangulation counting. Both stages use a Z-up coordinate system and one metre per stage unit. At the inspected rotor pose, the visible bound is approximately **1.1785 × 1.0063 × 0.5820 m**. The adapter adds **0.0259521 m** vertically to place the lowest visible geometry at zero. This is a static visual bound, not a measured rotor-swept envelope or engineering dimensional validation. NASA lists a rotor diameter of about **1.2 m** and an aircraft height of **0.49 m**; the cached model's roughly 0.582 m visual height does not reproduce that published height. [JPL quick facts](https://www.jpl.nasa.gov/news/press_kits/ingenuity/landing/quick_facts/)

For identification, the inspected source USD SHA-256 is `f8fdc997e218fa08269f4aa1f0663b5564bb224e73411c34fa748262d4d2b198`. Dependency traversal found the source layer, schema layer, and ten textures without unresolved paths on the inspected workstation.

The local [NVIDIA asset notice](../tmp/promo/licenses/NVIDIA_ISAAC_ASSETS_LICENSE.txt) identifies the content pack's NVIDIA terms and points to robot-specific notices; the [Isaac Sim notice](../tmp/promo/licenses/NVIDIA_ISAAC_SIM_LICENSE.txt) and NASA acknowledgement are also preserved locally. These provenance records concern this independently obtained asset. A NASA visual credit alone does not establish the licensing of NVIDIA's complete USD distribution. The report does not repackage the cached model or substitute a new licence for those source notices.

## 3. Authored physical metadata versus active simulation

The original USD contains an articulation skeleton. NVIDIA advertises five links and four joints for the asset, and inspection confirms those structural counts. The cinematic adapter explicitly deactivates every `UsdPhysics.Joint` and removes applied Physics/PhysX APIs throughout the referenced hierarchy. [NVIDIA asset catalogue](https://docs.isaacsim.omniverse.nvidia.com/5.1.0/assets/usd_assets_robots.html), [adapter preparation](../tmp/promo/research/prepare_ingenuity.py)

| Item | Cached upstream source | Composed cinematic adapter |
|---|---|---|
| Articulation roots | 1 | 0 |
| Prims carrying rigid-body and mass APIs | 5 of each | 0 |
| Prims carrying collision API | 11; eight rotor visual colliders already have collision disabled | 0 |
| Active joint prims | 4 revolute joints | 0; all four are explicitly inactive |
| Explicit body masses | Approximately 0.0001 kg on each of the two rotor visual bodies | Values remain as inherited attributes, with no active mass API |
| Chassis and rotor helper masses | No explicit `physics:mass` authored | No active mass calculation |
| Explicit diagonal inertias | None on the five bodies | No active inertia model |
| Camera prims | 0 | 0 before the renderer adds its observation camera |

The source chassis has raw authored density `50000004`; each rotor physics helper has `1000000064`. These imported values are not a documented mass breakdown of the flight vehicle. Centre-of-mass attributes contain the `(-inf, -inf, -inf)` sentinel, while diagonal inertia uses an unauthored zero fallback. These are not measured flight centre-of-mass or inertia values. Summing the two explicit visual-rotor masses would also omit the other three bodies and therefore would not produce a legitimate vehicle mass.

Two source joints named `rotor_physics_0` and `rotor_physics_1` have lower and upper limits both set to zero. The other two connect the visual rotor groups. Consequently, a catalogue joint/DOF count should not be interpreted as a validated free-flight dynamics model. In the adapter all four joints are inactive regardless of their original limits.

API removal does **not** erase every inherited `physics:*` attribute. A text or property scan can still find mass, density, velocity, or collision settings in the composed stage. Their continued presence does not make them operative rigid-body properties. The [inspection output](../tmp/techreport/inspect_ingenuity.json) records both raw attributes and active APIs to make that distinction explicit.

NASA gives the real aircraft's mass as **1.8 kg** and describes two counter-rotating rotors with four blades in total. MarsLab's cinematic adapter has no active 1.8 kg assignment, aerodynamic lift, drag, rotor torque, blade-pitch actuator, motor dynamics, atmospheric density model, or ground-contact response. [JPL spacecraft description](https://www.jpl.nasa.gov/news/press_kits/ingenuity/landing/mission/spacecraft/)

## 4. Motion and rotor animation

The [current renderer](../tmp/promo/scene/render_scene.py) instantiates the adapter under `/World/Fleet/ingenuity/Model`. It deactivates physics scenes, disables remaining collision/rigid-body participation, and directly assigns the wrapper's translation and yaw. Terrain height comes from bilinear interpolation of the scene DEM. Horizontal motion and altitude are scripted functions of shot progress; no integrated force, velocity controller, roll/pitch response, or state estimator determines the trajectory.

The v2 choreography starts at **6 m** above the sampled terrain, climbs to **18 m**, maintains that height during the individual robot shots, rises to **24 m**, then returns to **6 m**. These are render-path parameters rather than demonstrated flight capabilities. Replicator renders with `delta_time=0` and `pause_timeline=True`, so frame generation does not advance a flight-physics integration.

The original blade meshes receive opposite Z rotations around their existing hubs. The script uses **930°/s**, equivalent to **155 revolutions per minute** and **31° per output frame at 30 fps**, with a 45° phase offset for the second rotor. This is explicitly an apparent cinematic speed. NASA reports **2,537 rpm** for the first 13 flights and **2,700 rpm** for subsequent operation in thinner air; the commonly quoted approximately 2,400 rpm is a nominal design description. [NASA atmosphere and rotor-speed explanation](https://science.nasa.gov/resource/mars-atmosphere-density-model/), [JPL spacecraft description](https://www.jpl.nasa.gov/news/press_kits/ingenuity/landing/mission/spacecraft/)

The current v2 renderer adds no rotor discs or replacement blur meshes and disables post-process motion blur. The [v2 metadata](../tmp/promo/scene/render_metadata_v2.json) records these choices. Older material in `tmp/promo/archive/v1/` is historical and should not be used to describe the current blade rendering.

## 5. Sensors and mounting

The cached source contains camera-shaped visual geometry, but neither the source nor its adapter contains a `UsdGeom.Camera`. The renderer adds one `PromoSensorCamera` under the model, independently of the source's camera-housing meshes.

| Property | Current film observation camera |
|---|---|
| Prim path | `/World/Fleet/ingenuity/Model/PromoSensorCamera` |
| Local optical-centre offset | `(0.05, 0, 0.15)` m relative to its model parent |
| Orientation | Recomputed each frame to look toward the fleet centre; cinematic gimbal behaviour |
| Horizontal field of view | 110° |
| Aperture and focal length | Authored aperture values 36 × 20.25; focal-length value approximately 12.60 in the same USD optical units; their ratio yields 110° horizontal FOV |
| Clipping range | 0.05–1,000 m |
| Observation render | 640 × 360 RGB through a Replicator render product |
| ROS and flight processing | No image publication, camera calibration topic, VIO, or flight navigation pipeline |

USD defines aperture and focal length in tenths of a scene unit; the raw authored values above should not be read as millimetres in this metre-scale stage. These are cinematic projection settings, not measured flight optics. [OpenUSD camera units](https://openusd.org/release/api/class_usd_geom_camera.html)

The camera is generally downward-looking, but its continuously changing look-at orientation is not a fixed flight-camera extrinsic calibration. The film models no gimbal hardware or servo dynamics. It also supplies no flight sensor noise, camera response calibration, or flight shutter timing. A rendered camera view therefore demonstrates scene visibility, not sensor fidelity.

NASA/JPL's camera paper describes two distinct flight instruments. The **NAV** camera is monochrome, global shutter, **640 × 480**, directly nadir-pointing, with **166.5° ± 3° diagonal FOV**. The **RTE** camera is colour, rolling shutter, **4208 × 3120**, with **102° horizontal × 82° vertical FOV** and a boresight **45° above nadir**. The film camera matches neither instrument. Horizontal and diagonal fields of view must also not be compared as though they use the same convention. [Maki et al., 2024, Table 1 and Figure 2](https://www.hou.usra.edu/meetings/tenthmars2024/pdf/3479.pdf)

Real Ingenuity used NAV imagery at approximately **30 Hz**, an IMU, laser rangefinder, and an inclinometer for initial attitude determination. Its controller reacted approximately **500 times per second**; this is a control-update figure, not a claim about raw IMU sampling frequency. None of these feedback systems exists in the film adapter. [NASA/JPL aerial guidance, navigation and control assessment, printed pp. 23–24](https://science.nasa.gov/wp-content/uploads/2023/10/gnc-tech-assess-part-iv-aerial-gnc-230306.pdf)

## 6. Verification and reproducibility limits

The read-only [inspection helper](../tmp/techreport/inspect_ingenuity.py) opened both USD stages through OpenUSD, counted geometry and APIs, examined mass/inertia opinions and joint states, calculated bounds and hashes, and resolved file dependencies. Its JSON output is stored alongside it under `tmp/techreport/`. Source assets and the cinematic adapter were not modified, and neither preparation nor rendering scripts were executed for this report. No new GPU render, ROS execution, autonomous-flight test, aerodynamic validation, or contact test was performed.

Existing [production documentation](../tmp/promo/README.txt) describes a previously generated v2 film and its cinematic limitations. Reproduction from a fresh clone is currently incomplete: the source cache, adapter, textures, scripts, and production notices are all under the ignored `tmp/` tree. In addition, the current film renderer still references the former Perseverance path `assets/robots/rover/m2020.usd`, while that asset now resides under `assets/robots/perseverance/`. This unrelated scene dependency prevents treating the historical render recipe as a verified current rerun procedure.

The implementation supports a recognizable NASA-derived appearance, opposing rotor animation, scripted aerial placement, and a rendered observation view within the local film workflow. Its present evidence does not support use as an Ingenuity flight-dynamics, navigation, ROS integration, or flight-camera calibration model.
