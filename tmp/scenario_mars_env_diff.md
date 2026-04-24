# Reviewer 2 #17 — Scenario `mars_env` dedup diff report

**Date:** 2026-04-24
**Scope:** `configs/scenarios/*.yaml` (9 scenarios) vs `configs/mars_env.yaml` master

## Mechanism used

A root-level `base_config` include was **already present** in
`marslab.config.loader.load_and_validate` — but the raw-dict loader
`marslab.config.yaml_loader.load_scenario_config` only handled the
rover-subtree variant.  #17 extended the dict loader to also merge
a root-level `base_config` before the rover merge, so the Stage 2/3
runtime sees the same merged config as the pydantic path.

A new shared fragment lives at `configs/scenarios/_base.yaml` with only
the common `mars_env` + `rendering` blocks (scenarios fully specify
their own `terrain`, so sharing `terrain` would leak the wrong preset
into hirise scenarios).

## Drift observed (pre-#17)

All nine scenarios were byte-identical for the common mars_env/rendering
keys with these exceptions:

| Scenario | Drifted key | Scenario value | Master value | Intentional? |
|---|---|---|---|---|
| `mars_base.yaml` | `sun_elevation_deg` | 50 | 45 | Yes (photography framing) |
| `spacecraft_landing.yaml` | `sun_azimuth_deg` | 135 | 180 | Yes (morning sun for paper figure) |
| `spacecraft_landing.yaml` | `sun_elevation_deg` | 40 | 45 | Yes (morning sun for paper figure) |
| all 9 | `dynamic_atmosphere.enabled` | `True`/`true` (mixed case) | `false` | Yes (runtime sun sweep on) |
| `jezero_flat.yaml`, `mars_base.yaml`, `spacecraft_landing.yaml` | `dynamic_atmosphere.enabled` | **`True`** (capitalised) | — | **No — H-19 drift** |
| `jezero_rocks.yaml`, `jezero_crater.yaml`, `cerberus_canyon.yaml`, `cerberus_canyon_easy.yaml`, `cave_lava_tube.yaml`, `procedural_canyon.yaml` | `dynamic_atmosphere.enabled` | `true` (lowercase) | — | — |

All other `mars_env` keys were verbatim duplicates of `configs/mars_env.yaml`.

## Rendering drift

Every scenario had an identical ~15-line `rendering:` block. No drift
vs master. The scenarios used the flat form (`spp: 32`,
`total_spp: 256`, `max_bounces: 6`) while `configs/mars_env.yaml` uses
the nested `path_tracing` form — but `RenderingConfig._migrate_flat_to_nested`
maps them equivalently, so no functional drift.

## Boolean normalisation

All `enabled: True` (3 files) normalised to `enabled: true` (matches YAML 1.2
canonical boolean, matches the other 6 scenarios). The base fragment uses
`enabled: false`. Source scan now enforced by the regression test
`test_base_yaml_uses_lowercase_boolean_only` which regex-scans raw file text.

## Per-file line delta

| File | Before | After | Delta |
|---|---|---|---|
| `_base.yaml` (new) | 0 | 65 | +65 |
| `jezero_flat.yaml` | 74 | 45 | −29 |
| `jezero_rocks.yaml` | ~76 | 46 | ~−30 |
| `jezero_crater.yaml` | ~75 | 45 | ~−30 |
| `cerberus_canyon.yaml` | 77 | 47 | −30 |
| `cerberus_canyon_easy.yaml` | ~75 | 45 | ~−30 |
| `cave_lava_tube.yaml` | 111 | 79 | −32 |
| `procedural_canyon.yaml` | ~82 | 52 | ~−30 |
| `spacecraft_landing.yaml` | 140 | 113 | −27 |
| `mars_base.yaml` | 141 | 113 | −28 |
| **Total** | ~851 | 650 | **~−201 LOC** (−24%) |

Matches the H-17 audit claim of ~200 LOC duplication removed.

## Keys retained per scenario (post-dedup)

| Scenario | Surviving `mars_env` override keys |
|---|---|
| `jezero_flat.yaml` | `dynamic_atmosphere.enabled` |
| `jezero_rocks.yaml` | `dynamic_atmosphere.enabled` |
| `jezero_crater.yaml` | `dynamic_atmosphere.enabled` |
| `cerberus_canyon.yaml` | `dynamic_atmosphere.enabled` |
| `cerberus_canyon_easy.yaml` | `dynamic_atmosphere.enabled` |
| `cave_lava_tube.yaml` | `dynamic_atmosphere.enabled` |
| `procedural_canyon.yaml` | `dynamic_atmosphere.enabled` |
| `spacecraft_landing.yaml` | `dynamic_atmosphere.enabled`, `sun_azimuth_deg: 135`, `sun_elevation_deg: 40` |
| `mars_base.yaml` | `dynamic_atmosphere.enabled`, `sun_elevation_deg: 50` |

No surviving `rendering:` overrides — every scenario inherited the master
block verbatim, so the block was dropped entirely from each scenario.
