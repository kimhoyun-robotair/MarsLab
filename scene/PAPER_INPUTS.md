# Paper input inventory

Status vocabulary is limited to `PASS`, `FAIL`, `BLOCKED`, and `NOT RUN`.
Paths below are relative to the locked MarsLab-Utils revision. Local ignored
files are candidates, not committed or distributable paper inputs.

## Ordinary Jezero candidate chain

| Role | Exact source path | Bytes | SHA-256 | Git state | License / status | Expected output |
| --- | --- | ---: | --- | --- | --- | --- |
| HiRISE config | `HiRISEGen/examples/config_jezero.yaml` | 2,408 | `3a15475e96c26fc3e1cd492e1b0aed7ab422655e4b62c123c9f26135f9213d1e` | tracked | code config; `PASS` | `HiRISEGen/out/jezero_enhanced/` |
| DEM | `HiRISEGen/data/raw/jezero/JEZ_hirise_soc_006_DTM_MOLAtopography_DeltaGeoid_1m_Eqc_latTs0_lon0_blend40.tif` | 1,839,545,409 | `44c3819caa33922b06f7a8228534d1e32ab4087aca85144136d825c371c747d8` | ignored | source/license record absent; `BLOCKED` | cropped DEM, terrain stage, metadata |
| Orthomosaic | `HiRISEGen/data/raw/jezero/JEZ_hirise_soc_006_orthoMosaic_25cm_Eqc_latTs0_lon0_first.tif` | 7,358,523,457 | `83f3faeabc87ba54db9af278611bd070494a0b0d43757108c871c763943e80d9` | ignored | source/license record absent; `BLOCKED` | enhanced albedo |
| Mastcam-Z palette reference | `HiRISEGen/data/mastcamz_reference/ZL0_1849_0831078481_223RAD_N0880000ZCAM04368_1100LMN02.png` | 3,747,509 | `86f126dd0fe5e0c1ab19b5f90ab23c7ba8bb35ed44672c8eb57261d5af8478fe` | ignored | source/license record absent; `BLOCKED` | enhanced albedo palette |
| Rocky config | `RockyComposer/examples/compose_jezero_enhanced.yaml` | 478 | `5dd747b1282e5266b4f73bafa183e08539bdbedf91433f5904830ebcfacb71e8` | tracked | MIT code config; `PASS` | `RockyComposer/out/jezero_rocky/rocky_scene.usda` |
| Precomputed rock CSV referenced by config | `RockyComposer/tmp/jezero_rocks.csv` | 14,146 | `7e61044651a14c84060c92b36a741c940c553d8d138d6d56dbae93bff6c76244` | ignored | generation provenance/license record absent; `BLOCKED` | seeded rock placement |
| Alternate CSV used by recorded output | `RockyComposer/tmp/jezero_rocks_enh.csv` | 42,555 | `b54e6ad8abd85f848853831cb724b97241b84fbde2a1bf72fe2686d50cf47099` | ignored | does not match tracked config; `BLOCKED` pending authoritative choice | recorded output reports 767 rows, 766 placed |
| Habitat config | `HabitatGen/examples/compose_habitat.yaml` | 1,430 | `611cb9ed5bc865546fb4b0cbde79e3f49d32f8686850b2a9d80bdf6a2b4e68f4` | tracked | MIT code config; `PASS` | `HabitatGen/out/jezero_habitat/terrain_scene.usda` |

The tracked Rocky config and recorded output disagree on which CSV was used,
and the habitat config points at the ordinary terrain while the inspected
habitat output metadata points at the ORB-SLAM 1 km/dusted variants. Therefore
there is no verified full paper recipe. Creating `configs/scene/paper.yaml`
would require guessing and is `BLOCKED`.

## Legacy crater candidate chain

| Role | Exact source path | Bytes | SHA-256 | Git state | Status |
| --- | --- | ---: | --- | --- | --- |
| Crater config | `CraterComposer/examples/compose_procedural_flatland.yaml` | 637 | `acb4221376964cd09d6330510ddb8b88c71b5ca05bcb6b9d85c590e4a8c51da0` | tracked | config `PASS`; CraterComposer migration excluded |
| Cropped crater DEM | `CraterComposer/out/procedural_flatland/cropped_dem.tif` | 9,009,704 | `d7f6c64ecf98bd4f79c1e7d79c642fca260971f8815c23c3a8aa56a00d1f9f3c` | ignored | candidate exists; redistribution `BLOCKED` |
| Legacy metadata | `CraterComposer/out/procedural_flatland/metadata.json` | 4,721 | `bb9dbfa20e32e72a74ed886cffe98a99819fa6658b6c5ee140cf886579ba7b05` | ignored | candidate exists; contains developer absolute paths requiring normalization |
| Legacy stage | `CraterComposer/out/procedural_flatland/terrain_scene.usdc` | 2,267,349,846 | `bcd7e68279feda961b1e3753988f14f15bc907004c2bca59cf7ffd33962ccafe` | ignored | candidate exists; dependency/license audit `BLOCKED` |
| Rock CSV referenced by rocky metadata | `RockyComposer/tmp/procedural_flatland_rocks_enh.csv` | 382,996 | `b6a4cbaeae5ed0432d37dad1d86078c2e2f191add81cf109d9cc9b312139b7be` | ignored | candidate exists; provenance `BLOCKED` |
| Composed stage | `CraterComposer/out/procedural_flatland_rocky/rocky_scene.usda` | 816,588 | `ed4a1a7628b0fbf50e46aca3f4614ce567a1aae690ad04ed47126a66c374803c` | ignored | expected 6,903 placed rocks; canonical comparison `NOT RUN` |

The legacy artifact has no new-schema manifest or machine-readable external
dependency allowlist. It may only enter later work through the fail-closed
`legacy_artifact` normalizer specified by the migration contract.

## Canonical asset candidates

| Bundle role | Exact source path | Bytes | SHA-256 | Git state | License / status | Expected semantic output |
| --- | --- | ---: | --- | --- | --- | --- |
| Rock source GLB | `RockAssetGen/data/rock_asset/mars_rocks.glb` | 3,791,772 | `492e42380c1f994806d9f094c13f59b0c467563ad705d870e22410bf0d0158f9` | ignored | embedded CC BY 4.0 attribution; redistribution review `BLOCKED` | 15 prototypes |
| Rock library candidate | `RockAssetGen/out/glb_library/rock_library.usda` | 13,463 | `4bc80a5099d4c5c9d5ca78ed227181e7bf0a0e6d379a2fc748cf936ca6a2b9e8` | ignored | generated from candidate GLB; sidecar absent; `BLOCKED` | 15 prototypes, 4,666 polygons total per metadata |
| Rock metadata | `RockAssetGen/out/glb_library/metadata.json` | 640 | `99197f731f3ff1f1b5a57f9cdf777bd7199d1620228536a6e600cc5e19a88253` | ignored | timestamp/absolute paths require normalization; `BLOCKED` | seed 42, 15 prototypes |
| Habitat source GLB | `HabitatGen/data/mars_base.glb` | 9,139,440 | `4083e1455295a5cb04490e62a2dc8c0cbd5921a45c16866c0f5ec32b86a5ff38` | ignored | license/source record absent; `BLOCKED` | habitat geometry |
| Habitat library candidate | `HabitatGen/out/habitat_assets/library.usda` | 1,757 | `104708f82dd7cb1b163d26a9705668b3a84d1d8c1ceb0fcc43cf9a710d9e1ef1` | ignored | redistribution `BLOCKED` | nine materials |
| Habitat metadata | `HabitatGen/out/habitat_assets/metadata.json` | 5,505 | `252473754bbf21241350764255b70b0fa5fb6d75fe486dec60d225cfa10be3ab` | ignored | absolute source path requires normalization; `BLOCKED` | AABB, body floor, centroid, material topology |

## Existing candidate outputs

These ignored outputs are evidence that local runs occurred, not canonical or
paper artifacts:

| Output | SHA-256 | Recorded semantic expectation |
| --- | --- | --- |
| `HiRISEGen/out/jezero_enhanced/cropped_dem.tif` | `4f029a9f14cde32fe07ffa0ca2018b2724bb79883ba001f4500a0a3a1e976522` | 500 x 500 m crop, reference Z `-2454.172119140625 m` |
| `HiRISEGen/out/jezero_enhanced/terrain_scene.usdc` | `8f1ac5c315cafcba392eff9541a1988eda7437f7de34964b888e8308b7720587` | Z-up, meters per unit 1, `/World/MarsTerrain` |
| `RockyComposer/out/jezero_rocky/rocky_scene.usda` | `759bc583145a1edd84e1a590df8388563266e093c1e277179bf8b189c42fdd77` | 767 CSV rows, 766 placed, seed 42 |
| `HabitatGen/out/jezero_habitat/terrain_scene.usda` | `bd0720e921a131cbc7877ac4dd38ab6f06d9185482be3dff312abc90904dd3e4` | habitat translation `[34.5271, 162.154, 30.4455] m` in its recorded, mismatched recipe |

## Release Gate

`BLOCKED`. The required paper/canonical package lacks an authoritative recipe,
tracked or checksum-pinned distribution, and complete redistribution evidence.
Consequently Phase 0 does not create `paper.yaml`, does not claim paper parity,
and does not approve copying either canonical bundle.
