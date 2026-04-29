# Scene Structure Assets — Licenses & Sourcing

This directory holds pre-authored USD assets (``.usd`` / ``.usda`` /
``.usdc``) referenced from ``configs/scenarios/spacecraft_landing.yaml``
and ``configs/scenarios/mars_base.yaml`` through
``marslab.scene.structure_loader``.

Runtime OBJ / FBX / URDF import is forbidden (see project memory
``reference_rover_usd_source``).  All assets must be converted to USD
**offline** before reaching this directory.

## Expected files

### ``spacecraft/`` — Scenario 6 (Spacecraft Landing Site)

| File | Source | License |
|------|--------|---------|
| ``insight_lander.usd`` | NASA JPL "InSight Lander 3D Model" (NASA 3D Resources) | NASA public domain |
| ``heat_shield.usd`` | Artist-authored from Mars-2020 EDL reference imagery | Apache-2.0 (user-made) |
| ``backshell.usd``   | Artist-authored from Mars-2020 EDL reference imagery | Apache-2.0 (user-made) |
| ``parachute.usd``   | Artist-authored (simplified crumpled-canopy geometry) | Apache-2.0 (user-made) |
| ``inspection_beacon.usd`` | Artist-authored reference prop | Apache-2.0 (user-made) |

### ``base/`` — Scenario 7 (Mars Base / Crewed Outpost)

| File | Source | License |
|------|--------|---------|
| ``habitat_module.usd`` | Artist-authored, geometry inspired by NASA Mars DRA 5.0 | Apache-2.0 (user-made) |
| ``solar_array.usd``    | Artist-authored, generic foldable Mars solar panel | Apache-2.0 (user-made) |
| ``airlock.usd``        | Artist-authored, cylindrical pressurised airlock | Apache-2.0 (user-made) |
| ``comm_dish.usd``      | Artist-authored, high-gain parabolic dish | Apache-2.0 (user-made) |
| ``isru_plant.usd``     | Artist-authored, simplified MOXIE-style ISRU rack | Apache-2.0 (user-made) |

## Attribution

When distributing MarsLab v1.0 with the full asset set, reproduce the
NASA 3D Resources usage guidelines (https://nasa3d.arc.nasa.gov/) in
``LICENSE`` and credit the user-made Apache-2.0 sources in the paper
supplementary material.

## Missing-file behaviour

``marslab.scene.structure_loader.load_structure`` raises
``FileNotFoundError`` with the absolute path and a pointer to this
document when a ``.usd`` file is missing.  YAML validation succeeds
even without the assets in place, so peer agents can iterate on the
scenario structure (coordinates, RPY, scale) ahead of asset delivery.
