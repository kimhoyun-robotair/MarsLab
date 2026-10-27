# Spirit MarsLab derivative model

NASA publishes the visualization mesh used here. NASA did **not** publish this URDF,
USD articulation, collision geometry, per-link masses, or dynamics settings.
MarsLab authored them as an explicitly approximate simulation model.

Sources: [NASA 3D Resources](https://github.com/nasa/NASA-3D-Resources),
[MER mission overview](https://science.nasa.gov/mission/mars-exploration-rovers-spirit-and-opportunity/).
See [source provenance and rights](../../../LICENSE-NASA-3D-RESOURCES.txt),
[model metadata](model_metadata.json), and the
[NASA NAIF sensor-data notice](../../../LICENSE-NAIF.txt)
for upstream mesh provenance, hashes and sensor-data attribution.

The source mesh is evaluated at Blender frame 1243; all genuine physical
meshes are retained, including physical arm objects marked hide-render in the source.
Explicitly named rig/helper cubes, pivot-material meshes, camera transform helpers and
shadow planes are excluded. Every excluded object and reason is recorded in model_metadata.json;
vertex count alone is not an exclusion criterion.
Arm, mast, antenna and payload are fixed at their visualization pose. They are not
articulated manipulation mechanisms. The authored suspension contains two rockers,
two bogies, four corner steering joints and six wheel drive joints. The right rocker
mimics the negative left rocker angle. Passive joint limits are ±pi radians in both
USD and URDF (numerical envelope, not claimed flight mechanical limits); steering
limits are ±1.2 radians. All wheel axes are +Y, steering axes +Z.

The frame is X forward, Y left, Z up, at nominal ground between the middle wheels.
Native source coordinates are rotated and translated as recorded in model_metadata.json.
Source side names are interpreted geometrically; MER native `right` is physical left.
Wheel positions are made laterally symmetric. Wheels are shifted onto their exact
physics centers and radially scaled to nominal mission wheel radii (0.13 m).
Source hub widths are preserved. Camera calibration positions use the same ground
frame; NASA mission camera parameters and all sensor limitations are recorded in
sensors.json (if attached).

The Microscopic Imager (MI) now uses a fixed stowed-arm mounting proxy matched to
this visualization, at `[0.5124522, 0.08843082, 0.38960254]` metres in the ground
frame, looking approximately 30 degrees to the right of rover forward. Both MER
models share that source geometry. MarsLab identifies the small MI optics box next
to its contact feeler by comparison with [NASA's MI turret photograph, Figure 1](https://ntrs.nasa.gov/api/citations/20030066751/downloads/20030066751.pdf).
The pinhole is placed at the center of that box's front face (evaluated
`arm_turret` triangles 1500 and 1501 at source frame 1243), directed along its
outward normal. The mesh does not separately resolve the entrance pupil, so this
is **geometry-derived, not NASA flight-calibrated stowed extrinsics**. The original
extended-arm calibration pose is retained under `calibration_reference_pose` in
sensors.json; individual NASA intrinsics and raw kernel data are unchanged.
USD pose and YAML camera-link TF describe the same mount. This virtual view does
not reproduce physical dust-cover transmission or MI close-focus behavior.
The 0.01 m near clipping plane is unchanged; no visibility exception or enlarged
near plane is used. `pose_source` and `sensor_mount_overrides` record the derivation.

MER wheelbase and track are measured from the official visualization, not precision flight drawings.

Total mass is 185.0 kg.
The 185 kg total is the NASA mission summary value; some archival pages round the rover to 180 kg. No official per-link inertia or complete tensor was located.

**Estimated link mass distribution:** wheels 1.5 kg each,
corner steering carriers 0.8 kg each, rockers 4 kg each,
bogies 3 kg each; all remaining mass belongs to the fixed chassis/payload.
Those allocations are MarsLab engineering assumptions, not measured NASA subsystem masses.
Wheel moments use a solid cylinder of the source width. Suspension mass moments use a
uniform thin shell over the assigned source triangles; triangle areas determine the
centroid and second moments without requiring a watertight mesh.
Chassis/payload COM and moments also use the uniform thin-shell approximation. The resulting aggregate tensor is an estimate, not NASA data.
All tensors are checked for positive eigenvalues and principal-moment triangle inequalities.
The USD stores principal axes; the URDF stores the equivalent full symmetric tensor.
MER aggregate off-diagonal moments come from the thin-shell geometry estimate; no NASA aggregate tensor is claimed.

Rendering uses pinhole cameras with individually documented near planes to bypass
opaque lens/camera-housing triangles in the official visualization mesh. Other camera calibration
centers and orientations are unchanged; the MI mounting override is described above. The visualization is not a precision
optical/mechanical CAD model: Curiosity Mastcam-left's housing is approximately
16 cm ahead of its calibration center. Near-plane clipping removes all objects closer
than that camera's near plane, including some nearby stowed-arm edge fragments in
MER front Hazcam views; wheels, farther suspension, arm and terrain remain visible.
This is a rendering approximation, not a claim about flight focus range. The per-camera
`rendering_overrides` in sensors.json and model_metadata.json record near planes,
identified source objects, measured forward-depth ranges and a 9×9-frustum-ray audit.
Original NASA calibration/NAIF data is unchanged.

Collision geometry is intentionally simple: six exact-radius cylinders and a conservative
chassis box. Suspension, antennas, panels, arm and mast have visual geometry but no
contact geometry. Self-collision is disabled. Terrain contact therefore tests mobility,
not instrument/arm collision avoidance or hardware loads. Drive gains, limits, material
friction, damping and solver iterations are numerical simulation choices, not flight values.

Reconstruction, generation and validation utilities live only under MarsLab/tmp/.
The source temporary Git clone was removed after vendoring the mesh files.
The Blender source is not distributed; its pinned upstream location and hash
are retained in the upstream record. Runtime uses the supplied USD, URDF,
meshes and textures. An automated rebuild workflow is not included.
