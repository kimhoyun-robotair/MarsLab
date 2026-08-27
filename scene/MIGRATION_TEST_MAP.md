# Migration test map

Every source test is inventoried at source revision
`6f30d67f036462c6fb0d520945fde01d90f525d1`. Every disposition below is final
for this migration: `MIGRATED`, `REPLACED`, or `EXCLUDED`. A replacement names
the target contract that supersedes the old test surface; an exclusion records
why the old surface is intentionally absent.

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
| `HiRISEGen/tests/test_cli_export.py` | 5 | build script/output artifact | `REPLACED`: public `build_scene.py` subprocess tests and terrain artifact contract; Typer entry point excluded |
| `HiRISEGen/tests/test_config.py` | 6 | strict scene config | `REPLACED`: Phase-1 strict recipe tests and typed `HiriseBuildConfig` boundary |
| `HiRISEGen/tests/test_coordinates.py` | 10 | frame/coordinate parity | `MIGRATED`: all nodes in `test_legacy_coordinates.py` |
| `HiRISEGen/tests/test_crop.py` | 7 | DEM crop parity | `MIGRATED`: all nodes in `test_legacy_crop.py` |
| `HiRISEGen/tests/test_dem_info.py` | 6 | raster metadata contract | `MIGRATED`: all nodes in `test_legacy_dem_info.py` |
| `HiRISEGen/tests/test_elevation.py` | 9 | elevation parity | `MIGRATED`: all nodes in `test_legacy_elevation.py` plus direct source comparison |
| `HiRISEGen/tests/test_heightfield_mesh.py` | 8 | terrain mesh parity | `MIGRATED`: all nodes in `test_legacy_heightfield_mesh.py` plus direct source comparison |
| `HiRISEGen/tests/test_import.py` | 1 | package import | `REPLACED`: clean Python 3.11 wheel install/import gate |
| `HiRISEGen/tests/test_isaac_smoke_script.py` | 6 | script contract only, not actual Isaac runtime | `REPLACED`: Phase-7 actual Isaac/Kit and MarsLab assembly runtime node |
| `HiRISEGen/tests/test_nodata.py` | 6 | nodata failure modes | `MIGRATED`: all nodes in `test_legacy_nodata.py` |
| `HiRISEGen/tests/test_texture_config.py` | 6 | texture schema | `REPLACED`: typed `HiriseBuildConfig` and real public pipeline comparison |
| `HiRISEGen/tests/test_texture_export.py` | 7 | texture artifact | `REPLACED`: pinned-source pipeline semantic comparison and relocatable artifact test |
| `HiRISEGen/tests/test_usd_writer.py` | 8 | standalone terrain USD | `MIGRATED`: all nodes in `test_legacy_usd_writer.py` |
| `HiRISEGen/tests/test_visual_enhancement_colorize.py` | 3 | appearance numerical behavior | `MIGRATED`: all nodes in `test_legacy_visual_enhancement_colorize.py` |
| `HiRISEGen/tests/test_visual_enhancement_config.py` | 4 | appearance schema | `REPLACED`: typed appearance section of `HiriseBuildConfig` |
| `HiRISEGen/tests/test_visual_enhancement_e2e.py` | 2 | synthetic cross-component contract | `REPLACED`: real pinned-source pipeline comparison and Phase-7 public build contract |
| `HiRISEGen/tests/test_visual_enhancement_finalize.py` | 3 | appearance determinism | `MIGRATED`: all nodes in `test_legacy_visual_enhancement_finalize.py` |
| `HiRISEGen/tests/test_visual_enhancement_metadata.py` | 1 | provenance manifest | `REPLACED`: terrain and final artifact manifest contract tests |
| `HiRISEGen/tests/test_visual_enhancement_orthomosaic.py` | 2 | orthomosaic sampling | `MIGRATED`: all nodes in `test_legacy_visual_enhancement_orthomosaic.py` |
| `HiRISEGen/tests/test_visual_enhancement_palette.py` | 3 | palette behavior | `MIGRATED`: all nodes in `test_legacy_visual_enhancement_palette.py` |
| `HiRISEGen/tests/test_visual_enhancement_sources.py` | 6 | source validation failures | `REPLACED`: retained real-source validation in public build and missing-input failure node |
| `HiRISEGen/tests/test_visual_enhancement_usd_binding.py` | 2 | standalone material binding | `MIGRATED`: both nodes in `test_legacy_visual_enhancement_usd_binding.py` |

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
| `RockyComposer/tests/test_authoring.py` | 8 | relative paths, metadata, final builder | `REPLACED`: Phase-6 single `SceneBuilder`, manifest, relocation, and output-safety tests |
| `RockyComposer/tests/test_config.py` | 4 | rock config boundary | `REPLACED`: Phase-1 strict `RocksEnabled` recipe boundary |
| `RockyComposer/tests/test_ingest.py` | 10 | explicit input, license, USD validation | `REPLACED`: explicit CSV loader, asset contract negatives, and removal of implicit discovery |
| `RockyComposer/tests/test_isaac_smoke.py` | 1 | actual Isaac runtime only | `REPLACED`: Phase-7 actual Kit app/world smoke; source skip is not counted as PASS |
| `RockyComposer/tests/test_pipeline.py` | 4 | deterministic rock layer pipeline | `MIGRATED`: Phase-4 public deterministic layer test; authoring moved to Phase 6 |
| `RockyComposer/tests/test_placement.py` | 8 | selection, scale, stable orientation | `MIGRATED`: Phase-4 direct pinned-source selection/orientation comparison |
| `RockyComposer/tests/test_proto_meta.py` | 6 | rock bundle topology/metadata | `REPLACED`: Phase-2A real-USD asset contract; canonical Release Gate remains `BLOCKED` |
| `RockyComposer/tests/test_raster_diff.py` | 1 | DEM/placement numerical mismatch | `REPLACED`: Phase-4 same-DEM pinned-source position comparison |
| `RockyComposer/tests/test_raster_mesh_consistency.py` | 1 | raster/mesh Z consistency | `REPLACED`: Phase-3 terrain frame plus Phase-4 profile-specific Z oracles |
| `RockyComposer/tests/test_sampling.py` | 9 | DEM sampling and bounds failures | `MIGRATED`: Phase-4 actual GeoTIFF sampling, nodata/OOB filtering, and failure boundaries |

The unmodified source run is truthfully recorded as 42 passed, 6 failed, and
4 skipped after ambient pytest plugins were disabled. The six failures remain
mapped and are caused by the absent source rock-license sidecar; they are not
treated as passing or skipped.

## Phase-4 RockyComposer target tests

The Phase-4 fixture uses a 2.5 m/px DEM with non-unit vertical scale, non-zero
reference/offset, nodata, and out-of-bounds rows. The synthetic rock bundle is
contract data only and does not satisfy the canonical asset Release Gate.

| Target test | Marker | Source / contract disposition | Independent oracle |
| --- | --- | --- | --- |
| `tests/layers/rocks/test_phase4_rocks.py::test_legacy_selection_scale_and_orientation_match_read_only_source` | `unit`, `legacy_parity` | Replaces seeded selection, scale, and stable-orientation nodes from source `test_placement.py`, including ordered selection from two non-coplanar stable faces | Direct execution of pinned RockyComposer selection/orientation on the same diameters and seed; quaternion sign equivalence at `1e-5` |
| `tests/layers/rocks/test_phase4_rocks.py::test_legacy_positions_match_read_only_source_on_same_dem` | `unit`, `legacy_parity` | Replaces source sampling and terrain-frame pipeline positioning | Direct execution of pinned `RasterSampler` and `_apply_terrain_frame_transform` on the same GeoTIFF and XY rows |
| `tests/layers/rocks/test_phase4_rocks.py::test_public_place_rocks_returns_deterministic_layer_and_filters_invalid_samples` | `unit`, `legacy_parity` | Replaces the non-authoring portion of source `test_pipeline.py`; authoring remains mapped to SceneBuilder | Real public `place_rocks`, actual CSV/GeoTIFF, Phase-2A asset descriptor, repeat equality, and explicit OOB/nodata counts |
| `tests/layers/rocks/test_phase4_rocks.py::test_profile_specific_z_values_have_independent_expected_values` | `unit`, `legacy_parity` | Locks the deliberate §7.6 legacy/canonical Rock Z delta | Separately hand-calculated legacy `((110-100)+3.25)*1.75=23.1875` and canonical `(110-100)*1.75+3.25=20.75` |
| `tests/layers/rocks/test_phase4_rocks.py::test_quaternion_comparison_treats_sign_as_equivalent` | `unit`, `legacy_parity` | Locks the §12 quaternion comparator contract | Algebraic identity that `q` and `-q` encode the same rotation |
| `tests/layers/rocks/test_phase4_rocks.py::test_csv_and_dem_boundaries_fail_closed` | `unit`, `contract`, `legacy_parity` | Ports malformed/missing CSV and invalid sampler-shape failures from source ingest/sampling suites | Real malformed/missing filesystem inputs and array shape boundary |

## HabitatGen source suite: 14 tests

| Source test file | Collected | Migration contract | Disposition |
| --- | ---: | --- | --- |
| `HabitatGen/tests/test_assetgen.py` | 5 | generated bundle topology | `REPLACED`: Phase-2A habitat bundle validator; Phase-2B canonical Release Gate remains `BLOCKED` |
| `HabitatGen/tests/test_composer.py` | 6 | config, sampling, transform, USD composition | `MIGRATED`: Phase-5 numerical layer tests; config and final authoring replaced by Phases 1 and 6 |
| `HabitatGen/tests/test_skeleton.py` | 3 | legacy namespaces import | `EXCLUDED`: retired namespace imports are forbidden and target import gate replaces them |

HabitatGen collected and passed all 14 tests in its existing environment.

## Phase-5 HabitatGen target tests

The Phase-5 fixture uses a 2 x 3 m/px DEM with a nodata cell, a non-unit
vertical scale, non-zero Z reference and offset, and distinct non-zero legacy
and canonical centroids. The Phase-2A habitat bundle remains synthetic
contract data and does not satisfy the canonical asset Release Gate.

| Target test | Marker | Source / contract disposition | Independent oracle |
| --- | --- | --- | --- |
| `tests/layers/habitat/test_phase5_habitat.py::test_legacy_profile_matches_read_only_source_on_nontrivial_fixture` | `unit`, `legacy_parity` | Migrates the numerical portions of source `test_composer.py`: legacy flatness window, bilinear sampling, centroid transform, body-floor alignment and transformed AABB | Direct execution of pinned HabitatGen `find_flattest_anchor`, `sample_dem_z` and `compute_transform` on the same GeoTIFF and metadata |
| `tests/layers/habitat/test_phase5_habitat.py::test_canonical_profile_uses_independent_resolution_and_alignment_oracle` | `unit`, `legacy_parity` | Locks canonical §5.3/§7.6 resolution, elevation, Z-up centroid and body-floor contracts | Hand-derived 3 x 3 window at row/column `(2,2)`, projected center `(1005,1992.5)`, surface Z `9.5 m`, translation `(1,-2.5,9)` and translated AABB |
| `tests/layers/habitat/test_phase5_habitat.py::test_profiles_have_deliberately_distinct_expected_anchor_and_transform` | `unit`, `legacy_parity` | Records the deliberate profile delta instead of sharing expected values | Legacy row/column `(6,6)` and translation `(8.75,-13.75,24.5)` versus canonical `(2,2)` and `(1,-2.5,9)` |
| `tests/layers/habitat/test_phase5_habitat.py::test_anchor_boundaries_nodata_and_malformed_settings_fail_closed` | `unit`, `contract`, `legacy_parity` | Replaces source config/anchor edge coverage with explicit schema-v1 absolute-anchor failure modes | Real GeoTIFF boundary/nodata samples: canonical OOB rejection, legacy edge clamp, missing absolute XY rejection, and oversized footprint rejection |
| `tests/layers/habitat/test_phase5_habitat.py::test_public_api_authors_no_stage_and_imports_no_asset_generator` | `unit`, `legacy_parity` | Replaces the non-authoring composer pipeline behavior; old authoring moves to Phase 6 and assetgen is explicitly retired | Public `place_habitat` on actual TerrainArtifact/manifest inputs, filesystem inventory equality, and loaded-module inventory |

The source `test_composer.py` config roundtrip was superseded by the Phase-1
strict recipe schema. Its USD validator and final scene smoke belong to the
single SceneBuilder and runtime phases, because a habitat layer is forbidden
from authoring a stage. `test_assetgen.py` remains replaced by the Phase-2A
bundle contract and the blocked Phase-2B Release Gate. `test_skeleton.py` is
deleted by design because the legacy namespace must not remain active.

## Phase-6 final SceneBuilder target tests

These tests use actual standalone `usd-core`/`pxr` composition and Phase-2A
copyright-safe asset fixtures. They establish final authoring and relocation
contracts only; they are not Isaac, MarsLab runtime, canonical asset, or paper
reproduction evidence.

| Target test | Marker | Source / contract disposition | Independent oracle |
| --- | --- | --- | --- |
| `tests/usd/test_scene_builder.py::test_scene_builder_authors_exact_hierarchy_and_instancer_contract` | `contract`, `standalone_usd` | Consolidates Rocky/Habitat final writers into the sole final author and locks §10.2 hierarchy, conventions, transforms, references, arrays, manifest, and checksums | Actual composed `pxr` stage, Sdf authored reference inventory, and public contract values |
| `tests/usd/test_scene_builder.py::test_scene_builder_rejects_duplicate_layer_kinds` | `contract`, `standalone_usd` | Prevents duplicate composer/layer authoring | Duplicate typed layer input and absent output boundary |
| `tests/usd/test_scene_builder.py::test_working_layout_and_standalone_usdz_relocate_independently` | `contract`, `standalone_usd` | Locks working-layout relocation and single-file USDZ dependency closure | Two distinct temporary roots, actual `Usd.Stage.Open`, and `UsdUtils.ComputeAllDependencies` |
| `tests/usd/test_scene_builder.py::test_enabled_layer_combinations_keep_stable_hierarchy` | `contract`, `standalone_usd` | Locks terrain-only and habitat-enabled hierarchy without placeholder prims | Actual composed child order for both parametrized cases |
| `tests/usd/test_scene_builder.py::test_terrain_owned_physics_and_material_children_are_preserved_before_layers` | `contract`, `standalone_usd` | Preserves terrain-owned physics/material scopes while keeping final layer order deterministic | Actual sublayer composition with non-layer children and `pxr` child inventory |
| `tests/usd/test_output_safety.py::test_existing_output_is_preserved_by_default` | `contract`, `standalone_usd` | Implements §9.3 default no-overwrite policy | Existing sentinel file remains byte-identical after rejection |
| `tests/usd/test_output_safety.py::test_unsafe_output_roots_are_rejected` | `contract`, `standalone_usd` | Rejects filesystem root and user home targets | Resolved root identities for both parametrized cases |
| `tests/usd/test_output_safety.py::test_unresolved_output_variable_is_rejected` | `contract`, `standalone_usd` | Rejects unresolved environment-variable output tokens | Literal unresolved path component boundary |
| `tests/usd/test_output_safety.py::test_failed_validation_removes_only_temporary_output` | `contract`, `standalone_usd` | Implements temporary-build cleanup without touching unrelated files | Invalid actual terrain stage, absent temp/target, and preserved sibling sentinel |
| `tests/usd/test_output_safety.py::test_force_publish_retains_recoverable_sibling_backup` | `contract`, `standalone_usd` | Implements validate-before-backup-and-atomic-publish force policy | Backup contains original sentinel and published stage opens |
| `tests/usd/test_output_safety.py::test_final_manifest_rejects_dependency_checksum_corruption` | `contract`, `standalone_usd` | Requires final manifest schema/path/checksum validation before publication | Independent post-build mutation of the semantic report produces an explicit checksum mismatch |

## Phase-7 public scripts and actual runtime target tests

The committed smoke recipe uses the Phase-2A copyright-safe terrain fixture and
is therefore synthetic input. Its standalone results do not satisfy canonical
asset, paper reproduction, Isaac, or MarsLab runtime gates. The actual runtime
node has no mock, stub, fallback, or standalone substitute; an absent runtime
input is a skipped `NOT RUN`, never a `PASS`.

| Target test | Marker | Source / contract disposition | Independent oracle |
| --- | --- | --- | --- |
| `tests/pipeline/test_phase7_scripts.py::test_json_boundaries_reuse_adapter_loaded_before_usd_runtime` | `contract`, `standalone_usd` | Locks the actual Isaac failure where a late recursive `JsonValue` adapter is built after Kit changes the typing-extension identity | One preloaded adapter object shared by every YAML/manifest boundary; actual bundled build is the runtime toggle proof |
| `tests/pipeline/test_phase7_scripts.py::test_public_build_uses_recipe_and_records_output_override` | `contract`, `standalone_usd` | Replaces the old HiRISE CLI wrapper with the single recipe-to-artifact public boundary and records temporary-output override without absolute manifest paths | Real public build, manifest text, and published USDZ |
| `tests/pipeline/test_phase7_scripts.py::test_runtime_package_validator_observes_terrain_and_dependency_closure` | `contract`, `standalone_usd` | Validates final package terrain and missing-reference contracts without claiming Isaac | Actual `usd-core` package open, terrain prim traversal, and dependency inventory |
| `tests/pipeline/test_phase7_scripts.py::test_build_script_reports_existing_output_and_force_backup` | `contract`, `standalone_usd` | Locks public CLI exit status, existing-output rejection, validate-before-force publish, and recoverable backup reporting | Three real subprocess invocations and preserved sibling backup |
| `tests/pipeline/test_phase7_scripts.py::test_scripts_expose_help_and_invalid_recipe_is_nonzero` | `contract`, `standalone_usd` | Locks all four thin script surfaces and strict invalid-recipe rejection | Real subprocess exit codes with malformed YAML recipe |
| `tests/pipeline/test_phase7_scripts.py::test_asset_and_scene_validation_scripts_drive_real_public_validators` | `contract`, `standalone_usd` | Replaces old script-only smoke assertions with real synthetic bundle and USDZ validation | Actual Phase-2A bundle loaders and actual `usd-core` final package inspection |
| `tests/runtime/test_phase7_actual_runtime.py::test_actual_isaac_and_marslab_assembly_load_final_scene` | `isaac_runtime`, `marslab_runtime` | Replaces legacy skipped Isaac smoke nodes with one truthful actual runtime gate | Actual bundled interpreter, SimulationApp/Kit, world, MarsLab `assemble_pre_reset`, `/World/Terrain` mesh traversal, and runtime update; no mock or fallback |

## Phase-8 documentation and cleanup target tests

| Target test | Marker | Contract / failure mode | Independent oracle |
| --- | --- | --- | --- |
| `tests/contracts/test_phase8_inventory.py::test_locked_source_test_inventory_has_final_dispositions` | `contract` | The locked source test inventory cannot regress to an ambiguous or unfinished disposition | Frozen source-test path inventory and final disposition vocabulary |
| `tests/contracts/test_phase8_inventory.py::test_phase8_topology_has_documented_asset_license_roots_and_no_retired_dependency` | `contract` | Asset license status roots must exist even while blobs are blocked, and retired direct dependencies cannot return | Filesystem topology and `scene/pyproject.toml` direct dependency list |

## Production source module inventory

The import graph was inspected at the locked source revision and against all
target production/test imports. Package-only `__init__.py` files do not carry
behavior: target packages recreate them under `marslab_scene`, while legacy
top-level namespace markers are `EXCLUDED`. Every behavior-bearing source
module has the explicit disposition below. The source checkout itself is not
modified or deleted.

### HiRISEGen modules

| Locked source module(s) | Disposition | Target / reason |
| --- | --- | --- |
| `HiRISEGen/src/hirisegen/cli.py` | `EXCLUDED` | Console entry point retired; `scripts/scene/build_scene.py` is the public wrapper |
| `HiRISEGen/src/hirisegen/config.py` | `MIGRATED` | `config/models.py` plus `terrain/hirise/config.py` |
| `HiRISEGen/src/hirisegen/dem/coordinates.py` | `MIGRATED` | `terrain/frame.py` |
| `HiRISEGen/src/hirisegen/dem/elevation.py` | `MIGRATED` | `terrain/elevation.py` |
| `HiRISEGen/src/hirisegen/dem/crop.py` | `MIGRATED` | `terrain/hirise/dem/crop.py` |
| `HiRISEGen/src/hirisegen/dem/nodata.py` | `MIGRATED` | `terrain/hirise/dem/nodata.py` |
| `HiRISEGen/src/hirisegen/dem/resample.py` | `MIGRATED` | `terrain/hirise/dem/resample.py` |
| `HiRISEGen/src/hirisegen/dem/metrics.py` | `EXCLUDED` | One-line placeholder with no production or source-test import |
| `HiRISEGen/src/hirisegen/ingest/dem_info.py` | `MIGRATED` | `terrain/hirise/ingest/dem_info.py` |
| `HiRISEGen/src/hirisegen/ingest/geotiff.py` | `MIGRATED` | `terrain/hirise/ingest/geotiff.py` |
| `HiRISEGen/src/hirisegen/ingest/pds_to_geotiff.py` | `EXCLUDED` | Placeholder with no production or source-test import |
| `HiRISEGen/src/hirisegen/mesh/heightfield.py` | `MIGRATED` | `terrain/hirise/mesh/heightfield.py` |
| `HiRISEGen/src/hirisegen/mesh/obj_export.py` | `MIGRATED` | `terrain/hirise/mesh/obj_export.py` |
| `HiRISEGen/src/hirisegen/mesh/validate.py` | `MIGRATED` | `terrain/hirise/mesh/validate.py` |
| `HiRISEGen/src/hirisegen/pipeline.py` | `MIGRATED` | `terrain/hirise/build.py`; returns `TerrainArtifact` |
| `HiRISEGen/src/hirisegen/texture/prepare.py` | `MIGRATED` | `terrain/hirise/texture/prepare.py` and `images.py` |
| `HiRISEGen/src/hirisegen/texture/uv.py` | `MIGRATED` | `terrain/hirise/texture/uv.py` |
| `HiRISEGen/src/hirisegen/usd/write_material.py` | `MIGRATED` | consolidated into reusable `usd/terrain.py` |
| `HiRISEGen/src/hirisegen/usd/write_mesh.py` | `MIGRATED` | consolidated into reusable `usd/terrain.py` |
| `HiRISEGen/src/hirisegen/usd/write_physics.py` | `MIGRATED` | consolidated into reusable `usd/terrain.py` |
| `HiRISEGen/src/hirisegen/usd/write_scene.py` | `MIGRATED` | terrain sub-stage responsibility in `usd/terrain.py` |
| `HiRISEGen/src/hirisegen/usd/write_stage.py` | `MIGRATED` | terrain sub-stage responsibility in `usd/terrain.py` |
| `HiRISEGen/src/hirisegen/visual_enhancement/colorize.py` | `MIGRATED` | `terrain/hirise/appearance/colorize.py` |
| `HiRISEGen/src/hirisegen/visual_enhancement/finalize.py` | `MIGRATED` | `terrain/hirise/appearance/finalize.py` |
| `HiRISEGen/src/hirisegen/visual_enhancement/material.py` | `MIGRATED` | `terrain/hirise/appearance/material.py` |
| `HiRISEGen/src/hirisegen/visual_enhancement/orthomosaic.py` | `MIGRATED` | `terrain/hirise/appearance/orthomosaic.py` |
| `HiRISEGen/src/hirisegen/visual_enhancement/palette.py` | `MIGRATED` | `terrain/hirise/appearance/palette.py` |
| `HiRISEGen/src/hirisegen/visual_enhancement/prepare.py` | `MIGRATED` | `terrain/hirise/appearance/prepare.py` |
| `HiRISEGen/src/hirisegen/visual_enhancement/validation.py` | `MIGRATED` | `terrain/hirise/appearance/validation.py` |

### RockyComposer modules

| Locked source module(s) | Disposition | Target / reason |
| --- | --- | --- |
| `RockyComposer/src/rockycomposer/authoring/metadata.py` | `REPLACED` | common artifact/scene manifest writers |
| `RockyComposer/src/rockycomposer/authoring/paths.py` | `REPLACED` | `usd/packaging.py`, `runtime_package.py`, and manifest path validation |
| `RockyComposer/src/rockycomposer/authoring/scene.py` | `MIGRATED` | final authoring consolidated in `usd/builder.py` only |
| `RockyComposer/src/rockycomposer/cli.py` | `EXCLUDED` | console entry point retired |
| `RockyComposer/src/rockycomposer/config.py` | `MIGRATED` | strict `config/models.py` rocks section |
| `RockyComposer/src/rockycomposer/ingest/csv_loader.py` | `MIGRATED` | `layers/rocks/input.py` |
| `RockyComposer/src/rockycomposer/ingest/discovery.py` | `EXCLUDED` | output-directory discovery prohibited; typed artifacts are passed directly |
| `RockyComposer/src/rockycomposer/ingest/license.py` | `REPLACED` | strict asset manifest provenance/license fields |
| `RockyComposer/src/rockycomposer/ingest/validators.py` | `REPLACED` | common asset and USD validators |
| `RockyComposer/src/rockycomposer/library/proto_meta.py` | `REPLACED` | `assets/rocks.py` canonical/synthetic manifest loader |
| `RockyComposer/src/rockycomposer/pipeline.py` | `MIGRATED` | calculations in `layers/rocks/build.py`; authoring in `usd/builder.py` |
| `RockyComposer/src/rockycomposer/placement/orientation.py` | `MIGRATED` | `layers/rocks/orientation.py` |
| `RockyComposer/src/rockycomposer/placement/selection.py` | `MIGRATED` | `layers/rocks/placement.py` |
| `RockyComposer/src/rockycomposer/sampling/dem.py` | `MIGRATED` | common `terrain/sampling.py` |

### HabitatGen modules

| Locked source module(s) | Disposition | Target / reason |
| --- | --- | --- |
| `HabitatGen/src/habitatgen/assetgen/build.py` | `EXCLUDED` | generator code is forbidden from active target code |
| `HabitatGen/src/habitatgen/assetgen/cli.py` | `EXCLUDED` | generator/console entry point retired |
| `HabitatGen/src/habitatgen/assetgen/lib.py` | `EXCLUDED` | generator-only GLB/Blender conversion; bundle validator replaces runtime need |
| `HabitatGen/src/habitatgen/assetgen/viewer.py` | `EXCLUDED` | generator-only viewer is outside the scene toolchain |
| `HabitatGen/src/habitatgen/composer/authoring/scene.py` | `MIGRATED` | final authoring consolidated in `usd/builder.py` only |
| `HabitatGen/src/habitatgen/composer/cli.py` | `EXCLUDED` | console entry point retired |
| `HabitatGen/src/habitatgen/composer/config.py` | `MIGRATED` | strict singular habitat section in `config/models.py` |
| `HabitatGen/src/habitatgen/composer/ingest/discovery.py` | `EXCLUDED` | directory discovery prohibited; typed artifacts are passed directly |
| `HabitatGen/src/habitatgen/composer/ingest/validators.py` | `REPLACED` | common asset/USD validators |
| `HabitatGen/src/habitatgen/composer/pipeline.py` | `MIGRATED` | calculations in `layers/habitat/build.py`; authoring in `usd/builder.py` |
| `HabitatGen/src/habitatgen/composer/placement/flatness.py` | `MIGRATED` | `layers/habitat/flatness.py` with explicit profile policy |
| `HabitatGen/src/habitatgen/composer/placement/transform.py` | `MIGRATED` | `layers/habitat/placement.py` |
| `HabitatGen/src/habitatgen/composer/sampling/dem.py` | `REPLACED` | common `terrain/sampling.py` |
