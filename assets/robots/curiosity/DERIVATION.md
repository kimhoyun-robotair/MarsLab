# Curiosity MarsLab derivative model

This URDF and USD are MarsLab-authored simulation models. NASA supplied the
visualization meshes, calibration files and cited mission evidence. NASA did
not publish this URDF, link mass allocation, collision geometry or drive tuning.
See the [visual-source provenance and rights](../../../LICENSE-NASA-3D-RESOURCES.txt)
and [NASA NAIF sensor-data notice](../../../LICENSE-NAIF.txt).

## Geometry and articulation

The original [NASA visualization](https://github.com/nasa/NASA-3D-Resources)
is evaluated at Blender frame 180. All 73 physical source objects and 48,384
triangles are present exactly once. The model excludes named rig helpers,
pivot-material meshes, camera transform helpers and rendering shadow planes;
`model_metadata.json` records each excluded object and its reason. Physical arm
objects marked hide-render in the source are included to avoid missing segments.

Coordinates are X forward, Y left, Z up, with the origin at nominal ground
between the middle wheels. The source transform is recorded in metadata.
There are 22 rigid links and 21 joints: six wheel drives, four steering joints,
two rockers, two bogies, two operational mast joints and five arm joints.
The differential enforces equal-and-opposite rocker angles. Lower-mast deployment
hardware and antennas remain fixed. Arm and mast vertices are redistributed
between links without changing their nominal world positions.

Wheel radius is 0.25 m. Source wheel widths are retained and the visual wheel
radius is adjusted to match. Four corner contact positions use the
[NASA POST2 paper, Table 1](https://ntrs.nasa.gov/citations/20140003460):
2.26 m wheelbase and 2.125 m corner track. The middle wheel locations come from
the visualization. Small source asymmetries are symmetrized for steering.

The arm axis families and pivot locations are supported by the source Blender
rig and [NASA NAIF frames](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/fk/msl.tf).
Source arm segment lengths differ from the NASA structural values by less than
4 mm; the shoulder-elevation axis has approximately 16 mm registration error.
The mast uses the common azimuth/elevation intersection
`[0.8044, -0.5594, 1.9061]` m from the retained
[NAIF structure](https://naif.jpl.nasa.gov/pub/naif/MSL/kernels/spk/msl_struct_v02.bsp).

New joint zero positions are the deployed visualization pose, not flight telemetry
zeros. Positive right-hand axes are +Z for arm azimuth, turret and mast pan,
and +Y for shoulder elevation, elbow, wrist and mast tilt. Pan and turret limits
are ±π, mast tilt ±1.2 rad and the remaining arm joints ±1 rad. These conservative
simulation limits are not claimed flight stops. Existing steering limits are
±1.2 rad and passive suspension limits ±π. Additional force drives hold the
new joints at zero; mobility control preserves their targets. Exact parents,
pivots, axes, limits and suggested test amplitudes are in metadata.

## Mass and inertia

Total mass remains **899.18 kg**. The
[JPL arm paper, Table 2](https://www-robotics.jpl.nasa.gov/media/documents/rankin-2540-arm-kinematics-2021-0102.pdf)
gives 67 kg of arm mechanism and 24 kg of turret instruments, totaling 91 kg.
The allocation among individual links is estimated:

| Assembly | Allocated mass |
| --- | ---: |
| Fixed chassis and payload | 674.18 kg |
| Six wheels | 7 kg each |
| Four steering carriers | 3 kg each |
| Two rockers | 18 kg each |
| Two bogies | 12 kg each |
| Five arm links, shoulder to turret | 20, 18, 15, 8, 30 kg |
| Mast pan and tilt links | 4 and 16 kg |

The 30 kg turret allocation combines an estimated 6 kg mechanism with the
published 24 kg instrument mass. The 20 kg mast allocation and all subdivisions
are MarsLab estimates, not NASA measured link masses. Wheel inertias use solid
cylinders. Other link centers and moments use a uniform thin shell over their
assigned NASA visual triangles, normalized to the allocated mass. This method
does not require closed meshes. Every tensor has positive principal moments
and satisfies the principal-moment triangle inequalities. USD principal-axis
properties and URDF full tensors describe the same mass distributions.

The POST2 landing reference tensor `[405.09, 571.41, 774.84]` kg m² in FLU and
COM height 0.8944 m are **comparison data only** for this articulated model.
Forcing that reference onto the 91 kg arm in the deployed visualization pose
would require a chassis residual that violates physical inertia inequalities.
The paper itself describes a simplified landing calculation. Its unpublished
cross-products are shown as zero only in the comparison reference; the final
geometry-derived aggregate has nonzero cross-products.

At the nominal deployed pose, the final aggregate COM is
`[0.087287854, 0.037123568, 1.035039597]` m. Its horizontal projection lies inside
the wheel support polygon. The inertia about this COM, in kg m², is:

```text
  360.204957   -66.366078   -32.104533
  -66.366078  1001.576957    -2.508902
  -32.104533    -2.508902  1115.296627
```

These aggregate values change when the arm and mast move. Metadata retains
both the final values and the earlier landing comparison values.

## Sensors and rendering limits

Seventeen cameras retain NASA instrument intrinsics. Mastcam, Navcam and ChemCam
RMI move with `Body_MastTilt`; MAHLI moves with `Body_ArmTurret`. Hazcams and MARDI
remain on the chassis. YAML mount poses and ROS TF are relative to the selected
rigid parent. Mast and chassis camera poses retain their source calibration.

MAHLI's original CAHVOR extrinsics describe a different arm pose and would place
it outside the present visual turret. The active mount therefore uses an explicitly
approximate registration to the NASA visual MAHLI aperture: the mean of four
LED disk centers estimates its position, their shared disk normal sets its
boresight, and paired LED directions set roll. The raw calibration, original
reference pose, derived mount and method remain separately recorded in
`sensors.json`. This visual registration is not a flight-calibrated extrinsic.
An 81-ray aperture check found no MAHLI housing blockage; legitimate distant
rover geometry can still appear near image edges.

Rendering is pinhole-based and does not reproduce CAHVOR/E distortion, detector
response or instrument filters. Selected near planes bypass opaque camera
housing surfaces in the NASA visualization, without altering mast/chassis camera
poses. Mastcam-left's visual housing is about 16 cm ahead of its optical center.
The near plane also excludes any closer object from rendering. Per-camera
measurements, source objects and rendering overrides are recorded in
`sensors.json` and `model_metadata.json`. These are rendering approximations,
not flight focus limits. Original NASA calibration kernels remain unchanged.
Science instruments without a physical measurement model are explicitly labeled
metadata interfaces; no spectra, chemistry or radiation measurements are invented.

## Contact model and source comparison

Collision geometry consists of six wheel cylinders and a conservative chassis
box. Arm, mast, suspension and antenna visuals have no collision shapes, and
self-collision is disabled. The model supports mobility and articulation tests,
but does not provide manipulation collision avoidance or hardware load prediction.
Drive gains, friction, damping and solver settings are numerical choices.

[Space ROS Curiosity Xacro](https://github.com/space-ros/simulation/tree/13226b067d921ca88f40cd643a7b3ce4ae8de903/models/curiosity_path/urdf)
was inspected for segmentation and axis conventions. No Space ROS or The Construct
code, meshes or mass properties are included in production. Its package's
Apache-2.0 declaration is not treated as NASA flight provenance. The temporary
clone was removed after saving the read-only reference under `tmp/`.
All generation, inspection and validation utilities remain under `MarsLab/tmp/`.
The Blender source is not distributed; its pinned upstream location and hash
are retained in the upstream record. Runtime uses the supplied USD, URDF,
meshes and textures. An automated rebuild workflow is not included.
