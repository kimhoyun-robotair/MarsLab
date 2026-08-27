# Third-party notices

## MarsLab-Utils

Scene migration source: `kimhoyun-robotair/MarsLab-Utils` at commit
`6f30d67f036462c6fb0d520945fde01d90f525d1`.

The retained HiRISEGen, RockyComposer, and HabitatGen composer code is made
available under the MIT License. The original copyright and license text is
preserved in `LICENSES/MarsLab-Utils-MIT.md`.

## Mars Rocks candidate asset

The inspected `RockAssetGen/data/rock_asset/mars_rocks.glb` embeds this
attribution in GLB extras and existing RockyComposer output metadata:

- Title: Mars Rocks
- Author: Ivan Vakulko (`https://sketchfab.com/milos4`)
- Source: `https://sketchfab.com/3d-models/mars-rocks-9f5c946255a24f1cb630ea95dceea587`
- License: CC BY 4.0 (`http://creativecommons.org/licenses/by/4.0/`)

This is candidate provenance, not approval to redistribute the generated rock
bundle. Phase 0 found no tracked license sidecar at the location expected by
RockyComposer. Redistribution remains `BLOCKED` until the asset terms and
required attribution material are reviewed and preserved with the bundle.

## Habitat candidate asset

`HabitatGen/data/mars_base.glb` and its generated `HabitatGen/out/habitat_assets`
bundle exist only as ignored local files. No source attribution or license text
for the GLB was found in the inspected source tree. Redistribution is
`BLOCKED`; these blobs are not copied into MarsLab.

## Terrain imagery candidates

The Jezero DEM, orthomosaic, and Mastcam-Z reference image are ignored local
inputs. Their content digests are inventoried in `PAPER_INPUTS.md`, but no
source license or redistribution record was found in the inspected tree.
Redistribution is `BLOCKED`; these files are not copied into MarsLab.
