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
| `tests/contracts/test_phase1_contracts.py::test_rock_asset_descriptor_rejects_missing_contract_files` | `unit`, `contract` | Rock descriptors cannot carry missing manifest/stage files | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_habitat_asset_descriptor_rejects_missing_contract_files` | `unit`, `contract` | Habitat descriptors cannot carry missing manifest/stage files | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_terrain_artifact_rejects_missing_contract_files` | `unit`, `contract` | Terrain artifacts require existing stage and manifest files | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_scene_artifact_rejects_missing_contract_files` | `unit`, `contract` | Scene artifacts require existing stage/package/manifest files | Temporary filesystem layout |
| `tests/contracts/test_phase1_contracts.py::test_layer_summary_rejects_negative_count` | `unit`, `contract` | Layer counts cannot be negative | Integer boundary contract |

## Phase-2A target tests

All fixtures in this section are synthetic contract data. Their results are
standalone USD validation, not canonical asset, Isaac, MarsLab runtime, or paper
reproduction evidence.

| Target test | Marker | Contract / failure mode | Independent oracle |
| --- | --- | --- | --- |
| `tests/contracts/test_asset_contracts.py::test_rock_loader_validates_synthetic_bundle_with_real_usd` | `contract`, `standalone_usd` | Rock schema, prototype metadata, material, texture, collision, checksums, provenance, and license resolve together | Actual `usd-core` stage composition plus manifest checksums |
| `tests/contracts/test_asset_contracts.py::test_habitat_loader_validates_synthetic_bundle_with_real_usd` | `contract`, `standalone_usd` | Habitat schema and Z-up geometry-derived centroid/AABB/body-floor/footprint metadata agree | Actual `usd-core` geometry bounds |
| `tests/contracts/test_asset_contracts.py::test_asset_loaders_resolve_after_bundle_root_is_relocated` | `contract`, `standalone_usd` | Bundle references remain owner-relative after copying the full layout to a different root | Temporary relocated filesystem and actual `usd-core` dependency resolution |
| `tests/contracts/test_asset_contracts.py::test_asset_bundle_digest_is_stable_across_relocation` | `contract`, `standalone_usd` | Bundle digest excludes absolute checkout path | §5.4 lexical path + NUL + file digest algorithm |
| `tests/contracts/test_asset_negatives.py::test_rock_loader_rejects_missing_declared_file` | `contract`, `standalone_usd` | Missing bundle file fails closed | Temporary filesystem deletion |
| `tests/contracts/test_asset_negatives.py::test_asset_loader_rejects_absolute_manifest_path` | `contract`, `standalone_usd` | Manifest paths must be root-relative POSIX paths | Absolute path boundary |
| `tests/contracts/test_asset_negatives.py::test_asset_loader_rejects_bad_world_convention` | `contract`, `standalone_usd` | Y-up and non-meter manifests fail closed | Z-up, meter literals in §6 |
| `tests/contracts/test_asset_negatives.py::test_asset_loader_rejects_checksum_mismatch` | `contract`, `standalone_usd` | Modified content cannot retain its declared checksum | Independent SHA-256 of modified bytes |
| `tests/contracts/test_asset_negatives.py::test_asset_loader_rejects_missing_attribution_field` | `contract`, `standalone_usd` | Provenance and license attribution are required | Strict schema required fields |
| `tests/contracts/test_asset_negatives.py::test_rock_loader_rejects_missing_declared_prim` | `contract`, `standalone_usd` | Geometry, material, and collision prim declarations must resolve to correct USD types | Actual `usd-core` prim lookup |
| `tests/contracts/test_asset_negatives.py::test_rock_loader_rejects_absolute_usd_reference` | `contract`, `standalone_usd` | Authored USD asset paths must be relative and bundle-contained | Owning-layer token inspection before dependency resolution |
| `tests/contracts/test_asset_negatives.py::test_rock_loader_rejects_prototype_path_that_disagrees_with_stable_id` | `contract`, `standalone_usd` | Stable prototype ID and composed prototype prim path cannot disagree | Manifest prototype-root and stable-ID contract |
| `tests/contracts/test_asset_negatives.py::test_rock_loader_rejects_texture_that_is_not_bound_under_prototype` | `contract`, `standalone_usd` | Per-prototype texture metadata must identify the actual bound material dependency | Actual composed USD asset attributes under the prototype subtree |

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

## Phase-3 HiRISE target tests

The mechanically ported files below preserve every source node name one for
one. For example, each node in `test_legacy_crop.py` maps to the identically
named node in source `tests/test_crop.py`; no wildcard adds untracked tests.

| Target test file | Marker | Source / contract disposition | Independent oracle |
| --- | --- | --- | --- |
| `tests/terrain/hirise/test_legacy_coordinates.py` | `unit`, `legacy_parity` | All 10 nodes from `tests/test_coordinates.py`, namespace-only port | Read-only source assertions and REP-103 analytical values |
| `tests/terrain/hirise/test_legacy_crop.py` | `unit`, `legacy_parity` | All 7 nodes from `tests/test_crop.py`, namespace-only port | Read-only source window/affine behavior |
| `tests/terrain/hirise/test_legacy_dem_info.py` | `unit`, `legacy_parity` | All 6 nodes from `tests/test_dem_info.py`, namespace-only port | Actual rasterio metadata |
| `tests/terrain/hirise/test_legacy_elevation.py` | `unit`, `legacy_parity` | All 9 nodes from `tests/test_elevation.py`, namespace-only port | Read-only source formulas and hand-checkable arrays |
| `tests/terrain/hirise/test_legacy_heightfield_mesh.py` | `unit`, `legacy_parity` | All 8 nodes from `tests/test_heightfield_mesh.py`, namespace-only port | Source topology/winding and analytical bounds |
| `tests/terrain/hirise/test_legacy_nodata.py` | `unit`, `legacy_parity` | All 6 nodes from `tests/test_nodata.py`, namespace-only port | Source mask/fill behavior |
| `tests/terrain/hirise/test_legacy_usd_writer.py` | `unit`, `legacy_parity` | All 8 nodes from `tests/test_usd_writer.py`, writer renamed to the required `usd.terrain` owner | Actual `pxr` semantic prim/schema inspection |
| `tests/terrain/hirise/test_legacy_visual_enhancement_colorize.py` | `unit`, `legacy_parity` | All 3 nodes from `tests/test_visual_enhancement_colorize.py`, appearance namespace port | Read-only source pixel arrays |
| `tests/terrain/hirise/test_legacy_visual_enhancement_finalize.py` | `unit`, `legacy_parity` | All 3 nodes from `tests/test_visual_enhancement_finalize.py`, appearance namespace port | SHA/pixel determinism from actual raster output |
| `tests/terrain/hirise/test_legacy_visual_enhancement_orthomosaic.py` | `unit`, `legacy_parity` | All 2 nodes from `tests/test_visual_enhancement_orthomosaic.py`, appearance namespace port | Actual raster quadrant orientation |
| `tests/terrain/hirise/test_legacy_visual_enhancement_palette.py` | `unit`, `legacy_parity` | All 3 nodes from `tests/test_visual_enhancement_palette.py`, appearance namespace port | Actual raster percentile selection |
| `tests/terrain/hirise/test_legacy_visual_enhancement_usd_binding.py` | `standalone_usd`, `legacy_parity` | Both nodes from `tests/test_visual_enhancement_usd_binding.py`, writer renamed to `usd.terrain` | Actual `pxr` shader and relative asset inspection |
| `tests/terrain/hirise/test_phase3_terrain.py::test_numerical_migration_matches_read_only_source` | `unit`, `legacy_parity` | Direct source-to-target elevation and mesh comparison | Read-only `hirisegen` imported from pinned checkout |
| `tests/terrain/hirise/test_phase3_terrain.py::test_pipeline_semantics_match_read_only_source` | `unit`, `legacy_parity`, `standalone_usd` | Replaces pipeline/texture synthetic duplication with one real source pipeline comparison | Pinned source pipeline, actual GeoTIFF/PNG, semantic USD arrays |
| `tests/terrain/hirise/test_phase3_terrain.py::test_public_build_returns_relocatable_terrain_artifact` | `unit`, `contract`, `standalone_usd`, `legacy_parity` | `ExportResult` replacement, manifest, public build and relocation contract | Actual public API, copied artifact root and `pxr` reopen |
| `tests/terrain/hirise/test_phase3_terrain.py::test_public_build_rejects_missing_dem` | `unit`, `contract`, `legacy_parity` | Missing input failure mode | Real filesystem absence |

The remaining source-suite dispositions are deliberate replacements rather
than silent deletions. `test_cli_export.py` is replaced by the public build and
artifact tests because the old Typer entry point is explicitly not migrated.
`test_config.py`, `test_texture_config.py`, and
`test_visual_enhancement_config.py` are replaced by Phase-1 strict recipe tests
and the typed `HiriseBuildConfig` boundary. `test_texture_export.py`,
`test_visual_enhancement_e2e.py`, and `test_visual_enhancement_metadata.py` are
replaced by the direct pinned-source pipeline semantic comparison plus manifest
contract/relocation test. `test_visual_enhancement_sources.py` is represented
by retained source validation in the real public build and its missing-input
negative node; source-specific error wording is not promoted to a new public
contract. `test_import.py` is covered by the clean Python 3.11 wheel/import
gate. `test_isaac_smoke_script.py` is not migrated because it only tested an old
script surface; actual Isaac startup belongs to the later runtime phase.

Import-graph inspection found no production or test reference to
`dem/metrics.py` or `ingest/pds_to_geotiff.py`; both are one-line placeholders
and are intentionally removed. `cli.py` and its Typer entry point are omitted
by specification. The old `usd/write_*.py` modules are consolidated only in
`marslab_scene/usd/terrain.py`; appearance processing is renamed without
algorithm changes from `visual_enhancement/` to `appearance/`.

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
