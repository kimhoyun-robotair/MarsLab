# MarsLab interactive demo data

This is a server-free browser viewer of real MarsLab output. It does not run Isaac Sim, MOLA or RTAB-MAP on the visitor's device. Free camera movement is a web rendering feature; it does not generate new sensor observations.

## Scenes and provenance

- **Main Crater:** MarsLab `assets/scene/main_crater/main_crater.usdz`; underlying HiRISE DEM `DTEEC_025735_2185_025801_2185_A01.tif`, exported through HiRISEGen's `main_crater_hq` output.
- **Grand Canyon:** MarsLab `assets/scene/grand_canyon/grand_canyon.usdz`; underlying HiRISE DEM `DTEEC_012340_1750_012195_1750_A01.tif`, exported through HiRISEGen's `grand_canyon_hq` output.
- Height data and textures come from the existing co-registered MarsLab assets. DEM elevations use the original local-ENU origin and vertical reference. North is +Y, east +X, up +Z; no vertical exaggeration is applied.
- HiRISE instrument and planetary data: NASA / JPL-Caltech / University of Arizona. See the MarsLab paper and asset metadata for original source provenance.
- Rock assets appearing in the captured RGB sensor images: **“Mars Rocks” by Ivan Vakulko (milos4)**, [Sketchfab](https://sketchfab.com/3d-models/mars-rocks-9f5c946255a24f1cb630ea95dceea587), CC BY 4.0. Images are simulation renderings using those assets.
- The browser rover uses the original MarsLab `assets/robots/rover/m2020.usd` visual meshes: 20 components, 247,118 triangles, and the original texture. The GLB excludes duplicate collision meshes and physics schemas; no visual mesh decimation is applied. Credit NASA/JPL-Caltech; rover modeling and texturing by Zareh Gorjian, URDF conversion by the JPL RSVP team. The six wheel meshes rotate about their centers using signed cumulative recorded travel divided by their mesh-derived radii, assuming no slip. Rotation is interpolated deterministically with the playback timeline; it is a visual approximation, not recorded joint telemetry. Steering and suspension retain the source asset’s poses. Its geometry is elevated 0.7 m relative to the recorded pose so reduced-mesh approximation does not obscure it. Recorded pose data is unchanged.

## Newly recorded experiments

Recorded September 9, 2026, using the existing MarsLab runtime, the existing PathFollower utility and installed ROS 2 Jazzy MOLA / RTAB-MAP packages. No MarsLab or MarsLab-Utils source was changed.

Settings: static atmosphere, dust optical depth 0.5, solar azimuth 180°, solar elevation 45°, commanded speed 0.5 m/s. Each short recording starts after algorithm initialization; initial map snapshots can have a negative relative time. This is a demo excerpt, not the full paper benchmark.

- Main Crater: existing `main_crater_hq_rocky_xl_natural_loop` trajectory, 79 frames / 19.850 simulation seconds, approximately 9.04 m displacement. 13 MOLA and 19 RTAB-MAP map snapshots.
- Grand Canyon: existing `grand_canyon_hq_stadium` trajectory, 80 frames / 19.833 simulation seconds, approximately 8.88 m displacement. 12 MOLA and 18 RTAB-MAP map snapshots.

RGB callbacks select the most recent depth, LiDAR and GT messages within bounded timestamp tolerances. Observed maximum depth/LiDAR/GT time offsets: Main Crater 50/17/17 ms; Grand Canyon 50/50/17 ms. These are timestamp-matched samples, not exact-time hardware synchronization. Playback uses simulation timestamps and does not claim that the simulator originally ran at real time.

MOLA uses LiDAR input, the existing fixed LiDAR mount (1.45, 0, 2.1 m), with REP105 and localization TF publishing disabled to avoid the known wheel-TF time conflict. RTAB-MAP uses RGB-D plus wheel odometry and the official rover-state-publisher companion. Its default input wheel angular-covariance warning remains; no benchmark accuracy or loop-closure claim is made.

Ground truth is transformed into each algorithm's map frame using the first recorded GT orientation and the estimated pose at/before time zero. This is start-pose alignment for qualitative inspection, not an optimized ATE alignment or an error score.

## Web reductions

- Terrain: 193×193 sampled height grids, at most 1536×1536 JPEG textures.
- RGB and depth previews: approximately 4 Hz; 256×192 pixels per tile in JPEG atlases, 10 columns. Depth is colorized from 0–100 m; red is near, blue is far, invalid values are black. The atlas contains visualizations, not raw metric depth values.
- LiDAR: at most 1,200 finite points per sample, in sensor coordinates, shown in an isometric projection.
- SLAM maps: at most 6,000 displayed points per actual map snapshot. The point counter reports the original source-cloud count. No artificial map-growth animation is substituted for map snapshots.
- Coordinates are rounded to millimetres for compact JSON. GT pose is linearly interpolated and quaternion orientation is interpolated between recorded frames to make the rover model move smoothly.

`data/<scene>/run.json` contains timeline samples, LiDAR points, GT poses, estimated poses, map snapshots and synchronization offsets. Image atlases and terrain files are adjacent (`rgb.jpg`, `depth.jpg`, `terrain.json`, `terrain.jpg`). JSON and image assets remain in the repository; download and provenance controls are omitted from the demo interface.

## Runtime dependencies

Three.js 0.180.0 and OrbitControls are vendored locally under `vendor/`. License: MIT, copyright the Three.js authors; see `vendor/THREE-LICENSE.txt`. No external CDN, analytics, GPU server, login or backend API is used by the demo.
