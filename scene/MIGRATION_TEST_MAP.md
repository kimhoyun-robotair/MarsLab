# Migration test map

Every source test is inventoried at source revision
`6f30d67f036462c6fb0d520945fde01d90f525d1`. `Pending port` is an explicit
Phase-0 disposition, not a claim that target behavior is already covered.

## Phase-0 target tests

| Target test | Marker | Contract / failure mode | Independent oracle |
| --- | --- | --- | --- |
| `tests/legacy_reference/test_phase0_baseline.py::test_phase0_documents_exist_when_baseline_is_locked` | `legacy_parity` | Required provenance, license, paper inventory, and mapping records cannot disappear | Phase-0 file contract |
| `tests/legacy_reference/test_phase0_baseline.py::test_phase0_snapshot_is_self_authenticating_when_loaded` | `legacy_parity` | Fixture cannot silently drift or lose source revision/input digest/seed | SHA-256 plus locked source snapshot |

## Phase-1 target tests

| Target test | Marker | Contract / failure mode | Independent oracle |
| --- | --- | --- | --- |
| `tests/contracts/test_phase1_contracts.py::test_public_loader_resolves_valid_recipe_when_files_exist` | `unit`, `contract` | Recipe paths resolve relative to the recipe and required files exist | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_public_loader_rejects_missing_profile_when_recipe_is_loaded` | `unit`, `contract` | Schema-v1 compatibility profile has no implicit default | Required-field contract in §7.6/§9.1 |
| `tests/contracts/test_phase1_contracts.py::test_public_loader_rejects_unknown_profile_when_recipe_is_loaded` | `unit`, `contract` | Unknown compatibility profile fails closed | Immutable profile registry |
| `tests/contracts/test_phase1_contracts.py::test_public_loader_rejects_unknown_key_when_recipe_is_loaded` | `unit`, `contract` | Schema keys are strict | Pydantic `extra=forbid` boundary |
| `tests/contracts/test_phase1_contracts.py::test_public_loader_rejects_non_relative_input_path` | `unit`, `contract` | Absolute paths and file URIs are forbidden | Recipe-relative path contract |
| `tests/contracts/test_phase1_contracts.py::test_public_loader_rejects_missing_input_file` | `unit`, `contract` | Required input files fail immediately when absent | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_manifest_loader_rejects_invalid_world_convention` | `unit`, `contract` | Only Z-up and one meter per unit are accepted | World convention contract |
| `tests/contracts/test_phase1_contracts.py::test_manifest_loader_rejects_absolute_manifest_path` | `unit`, `contract` | Manifest file paths are root-relative POSIX paths | Manifest path contract |
| `tests/contracts/test_phase1_contracts.py::test_manifest_loader_rejects_profile_mismatch` | `unit`, `contract` | Imported terrain profile cannot be rebound implicitly | Profile equality contract |
| `tests/contracts/test_phase1_contracts.py::test_terrain_frame_applies_profile_specific_z_contract` | `unit`, `contract` | Canonical and legacy rock Z formula remain distinct | Hand-calculated §7.6 values |
| `tests/contracts/test_phase1_contracts.py::test_asset_descriptor_rejects_missing_contract_files` | `unit`, `contract` | Asset descriptors cannot carry missing manifest/stage files | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_terrain_artifact_rejects_missing_contract_files` | `unit`, `contract` | Terrain artifacts require existing stage and manifest files | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_scene_artifact_rejects_missing_contract_files` | `unit`, `contract` | Scene artifacts require existing stage/package/manifest files | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_layer_summary_rejects_negative_count` | `unit`, `contract` | Layer counts cannot be negative | Integer boundary contract |

## HiRISEGen source suite: 111 tests

| Source test file | Collected | Migration contract | Disposition |
| --- | ---: | --- | --- |
| `tests/test_cli_export.py` | 5 | build script/output artifact | Pending port in terrain pipeline phase |
| `tests/test_config.py` | 6 | strict scene config | Pending port in contracts phase |
| `tests/test_coordinates.py` | 10 | frame/coordinate parity | Pending port in terrain phase |
| `tests/test_crop.py` | 7 | DEM crop parity | Pending port in terrain phase |
| `tests/test_dem_info.py` | 6 | raster metadata contract | Pending port in terrain phase |
| `tests/test_elevation.py` | 9 | elevation parity | One non-trivial snapshot locked; full port pending |
| `tests/test_heightfield_mesh.py` | 8 | terrain mesh parity | Pending port in terrain phase |
| `tests/test_import.py` | 1 | package import | Pending port in package phase |
| `tests/test_isaac_smoke_script.py` | 6 | script contract only, not actual Isaac runtime | Replace with real runtime smoke in runtime phase |
| `tests/test_nodata.py` | 6 | nodata failure modes | Snapshot includes nodata; full port pending |
| `tests/test_texture_config.py` | 6 | texture schema | Pending port in terrain phase |
| `tests/test_texture_export.py` | 7 | texture artifact | Pending port in terrain phase |
| `tests/test_usd_writer.py` | 8 | standalone terrain USD | Pending port in terrain/USD phases |
| `tests/test_visual_enhancement_colorize.py` | 3 | appearance numerical behavior | Pending port in terrain phase |
| `tests/test_visual_enhancement_config.py` | 4 | appearance schema | Pending port in contracts phase |
| `tests/test_visual_enhancement_e2e.py` | 2 | synthetic cross-component contract | Reclassify as synthetic pipeline contract when ported |
| `tests/test_visual_enhancement_finalize.py` | 3 | appearance determinism | Pending port in terrain phase |
| `tests/test_visual_enhancement_metadata.py` | 1 | provenance manifest | Pending port in contracts phase |
| `tests/test_visual_enhancement_orthomosaic.py` | 2 | orthomosaic sampling | Pending port in terrain phase |
| `tests/test_visual_enhancement_palette.py` | 3 | palette behavior | Pending port in terrain phase |
| `tests/test_visual_enhancement_sources.py` | 6 | source validation failures | Pending port in terrain phase |
| `tests/test_visual_enhancement_usd_binding.py` | 2 | standalone material binding | Pending port in terrain/USD phases |

## RockyComposer source suite: 52 tests

| Source test file | Collected | Migration contract | Disposition |
| --- | ---: | --- | --- |
| `tests/test_authoring.py` | 8 | relative paths, metadata, final builder | Pending split between contracts and single SceneBuilder |
| `tests/test_config.py` | 4 | rock config boundary | Pending port in contracts phase |
| `tests/test_ingest.py` | 10 | explicit input, license, USD validation | Replace implicit discovery; port remaining contract tests |
| `tests/test_isaac_smoke.py` | 1 | actual Isaac runtime only | Source test skipped; replace with real Kit app/world smoke |
| `tests/test_pipeline.py` | 4 | deterministic rock layer pipeline | Snapshot locks seeded selection; full migration parity pending |
| `tests/test_placement.py` | 8 | selection, scale, stable orientation | Seeded selection/scale snapshot locked; orientation port pending |
| `tests/test_proto_meta.py` | 6 | rock bundle topology/metadata | Pending canonical asset contract and Release Gate |
| `tests/test_raster_diff.py` | 1 | DEM/placement numerical mismatch | Pending migration parity |
| `tests/test_raster_mesh_consistency.py` | 1 | raster/mesh Z consistency | Pending migration parity |
| `tests/test_sampling.py` | 9 | DEM sampling and bounds failures | Pending common sampling port |

The unmodified source run is truthfully recorded as 42 passed, 6 failed, and
4 skipped after ambient pytest plugins were disabled. The six failures remain
mapped and are caused by the absent source rock-license sidecar; they are not
treated as passing or skipped.

## HabitatGen source suite: 14 tests

| Source test file | Collected | Migration contract | Disposition |
| --- | ---: | --- | --- |
| `tests/test_assetgen.py` | 5 | generated bundle topology | Asset generator is retired; replace with canonical bundle contract/Release Gate |
| `tests/test_composer.py` | 6 | config, sampling, transform, USD composition | Transform snapshot locked; split remaining tests across contracts, layer, and SceneBuilder |
| `tests/test_skeleton.py` | 3 | legacy namespaces import | Delete after migration because retired namespaces must not remain active |

HabitatGen collected and passed all 14 tests in its existing environment.
