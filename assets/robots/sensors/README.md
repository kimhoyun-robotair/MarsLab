# Research LiDAR attachments

These original Blender models add a planar scanner and a spinning 3-D scanner
to the existing Perseverance mesh. They are simulated research equipment, not
flight Perseverance instruments or exact vendor CAD. All dimensions are metres.

| Assembly | Optical centre in `Body_Chassis` | Orientation |
| --- | --- | --- |
| 2-D | `(0.90, 0.25, 1.40)` | +X forward, +Y left, +Z up |
| 3-D | `(0.45, 0.25, 2.20)` | +X forward, +Y left, +Z up |

The 2-D assembly sits on a short pedestal on the forward deck. The 3-D assembly
uses a bolted, braced aluminium tube on the clear deck opposite the existing
camera mast. The deck surface at the mounts is `z=1.13338005`; the existing
camera head's highest initial vertex is `z=2.086054`, below the 3-D scan centre.
These placements were inspected using front, oblique and close-up Blender
renders of the actual composed USD in `previews/`. Terrain, tilted rover poses,
articulation movements and lower 3-D beams can still cause real occlusions.

The optical centres lie inside the modeled windows. Runtime settings come from
[`configs/config.yaml`](../../../configs/config.yaml), currently:

| Scanner | Range | Field of view | Rotation rate |
| --- | --- | --- | --- |
| 2-D | 0.20–200 m | Forward 135° horizontal sector | 10 Hz |
| 3-D | 3.5–200 m | 220° horizontal × 45° vertical | 30 Hz |

The 2-D scanner acquires a full 360° turn internally and returns only the
configured forward sector, including in the ROS LaserScan. The 3-D minimum
range places ray origins beyond the nearby rover structure. These settings
reduce self-returns; they do not guarantee an unobstructed view in every pose
or detection of every object out to 200 m.

## Assets and ownership

- `lidar_mounts.blend`: editable Blender source for housings, plates, struts and fasteners.
- `lidar_2d.usda`, `lidar_3d.usda`: USD assets with visual materials and convex collision meshes.
- Matching OBJ/MTL files provide the companion URDF visuals.
- `mounts.json`: optical origins and geometric design assumptions.
- `mass_properties.json`: source hashes, component masses, full inertia tensors,
  chassis and rover centre-of-mass changes.
- `../rover/m2020_lidar.usda`: additive composition over the existing rover USD.
- `../rover/m2020_lidar.urdf`: derived companion URDF with chassis visuals and
  merged inertial properties; its original articulation joints are retained.

The Blender source, previews and JSON files document asset construction; runtime
loads the supplied USD assets and does not run an asset builder. In particular,
the JSON design assumptions are not the active sensor range configuration.

Both assemblies belong to the existing chassis rigid body. The supplied URDF
adds no sensor links or joints. MarsLab publishes the `lidar_link` and
`lidar_2d_link` static frames below `Body_Chassis`.

## Mass and inertia

The supplied assets preserve the source chassis inertia and include component
inertias combined using the parallel-axis theorem. The construction calculation
used aluminium plates and struts with a density of 2700 kg/m³; the tube has
22 mm outer and 18.5 mm inner radii. Scanner masses
(0.38 kg and 0.65 kg) are disclosed engineering assumptions. The sensors use
uniform envelope inertia; small mesh bevels are omitted from analytic mass.
This is an approximation, not a measured flight mass distribution.

Added mass is **5.688155 kg**. Chassis mass becomes **675.688155 kg**, and its
centre moves **(+5.526, +2.607, +2.072) mm**. The initial whole-rover mass becomes
**957.328155 kg** and COM becomes **(-0.026153, -0.044401, 0.950190) m**.
Its COM projection remains 1.048827 m inside the six wheel-centre support hull;
no counterweight is warranted by that initial static calculation. This does
not establish dynamic stability: the actual Isaac run must supply that evidence.
