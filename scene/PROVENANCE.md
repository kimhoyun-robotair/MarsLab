# Scene migration provenance

## Locked revisions

| Role | Repository | Branch | Revision | Phase-0 state |
| --- | --- | --- | --- | --- |
| Target | `kimhoyun-robotair/MarsLab` | `refactor/scene-integration` | `93767119552ba7b2fc8515b3fef1e9a04f1a20c2` | clean before Phase-0 edits |
| Read-only source | `kimhoyun-robotair/MarsLab-Utils` | `main` | `6f30d67f036462c6fb0d520945fde01d90f525d1` | pre-existing modified `.gitignore` and six untracked files; preserved |
| Source submodule | `kimhoyun-robotair/synthterrain` | pinned submodule | `a3b3aa8e88d9fffc77fe0b3d7a7c6be1a06d2a47` | present at the specified revision |

The source dirty state predates this migration and is not part of the baseline.
The exact pre/post status and scoped diff are retained in the task evidence.

## Source-to-target map

| Source at the locked revision | Intended target | Phase-0 disposition |
| --- | --- | --- |
| `HiRISEGen/src/hirisegen/config.py` | `scene/marslab_scene/config/` | map only; migration pending |
| `HiRISEGen/src/hirisegen/dem/` | `scene/marslab_scene/terrain/hirise/dem/` | numerical snapshot locked |
| `HiRISEGen/src/hirisegen/mesh/` | `scene/marslab_scene/terrain/hirise/mesh/` | map only; migration pending |
| `HiRISEGen/src/hirisegen/texture/` and `visual_enhancement/` | `scene/marslab_scene/terrain/hirise/texture/` and `appearance/` | map only; migration pending |
| `HiRISEGen/src/hirisegen/usd/` | `scene/marslab_scene/usd/terrain.py` | map only; migration pending |
| `RockyComposer/src/rockycomposer/ingest/` and `library/` | `scene/marslab_scene/layers/rocks/input.py` and `assets/rocks.py` | map only; migration pending |
| `RockyComposer/src/rockycomposer/sampling/` and `placement/` | `scene/marslab_scene/terrain/sampling.py` and `layers/rocks/` | selection/scale snapshot locked |
| `RockyComposer/src/rockycomposer/authoring/scene.py` | `scene/marslab_scene/usd/builder.py` | behavior reference only; no writer copied in Phase 0 |
| `HabitatGen/src/habitatgen/composer/placement/` | `scene/marslab_scene/layers/habitat/` | transform snapshot locked |
| `HabitatGen/src/habitatgen/composer/authoring/scene.py` | `scene/marslab_scene/usd/builder.py` | behavior reference only; no writer copied in Phase 0 |
| `CraterComposer` | later `terrain.modifiers.craters` work | excluded from this migration |
| `RockAssetGen` and `HabitatGen/src/habitatgen/assetgen/` | canonical asset bundles only | generator source is retired, not copied |

All retained source is attributed under the verbatim MIT text in
`LICENSES/MarsLab-Utils-MIT.md`. Candidate data licenses are separate and are
recorded in `THIRD_PARTY_NOTICES.md`.

## Characterization fixture

`tests/fixtures/legacy_reference/phase0_inputs.json` is an explicit, small,
non-trivial input: `2.5 m/px`, non-unit vertical scale, non-zero Z reference and
offset, one nodata sample, seeded rock selection, and a non-zero habitat
centroid. `tests/legacy_reference/generate_phase0_snapshot.py` calls the locked
source implementations directly:

- `hirisegen.dem.elevation.normalize_elevation`
- `rockycomposer.placement.selection.select_prototypes_batch`
- `habitatgen.composer.placement.transform.compute_transform`

Run from the MarsLab checkout with the sibling source checkout available:

```bash
export PYTHONPATH=../MarsLab-Utils/HiRISEGen/src:../MarsLab-Utils/RockyComposer/src:../MarsLab-Utils/HabitatGen/src
../MarsLab-Utils/HabitatGen/.venv/bin/python \
  scene/tests/legacy_reference/generate_phase0_snapshot.py \
  --input scene/tests/fixtures/legacy_reference/phase0_inputs.json \
  --output phase0-snapshot.json \
  --source-revision 6f30d67f036462c6fb0d520945fde01d90f525d1
```

Two clean output paths produced byte-identical JSON with SHA-256
`0134dc386171ca6088ff8f30dcc5e34296531a7ecd7027e809eb6320fd8d38fd`.
The input digest, seed, source revision, and formatting-independent semantic
digest are embedded in the committed snapshot. No target implementation is
called to create expected values.

## Environments and source test disposition

| Environment | Identity | Dependency lock evidence | Result |
| --- | --- | --- | --- |
| HiRISEGen legacy | Python 3.12.3, USD 0.26.5 | `pip freeze` SHA-256 `52ea4bf855869f3da37b77944c163f799c1b511a701a534b34a2be60e293a7a4` | 111 passed; warnings preserved |
| RockyComposer legacy | Python 3.12.3, USD 0.26.5 | `pip freeze` SHA-256 `95f9d95cf073fe6e9b81b3e6e7355de35d619a2cb4fb239764bf51ec08578f92` | normal command failed during ambient ROS plugin load; isolated collection found 52 tests, and isolated run was 42 passed, 6 failed, 4 skipped |
| HabitatGen legacy | Python 3.12.3, USD 0.26.5 | `pip freeze` SHA-256 `5f3b3ea0aecda27aadebeff1f2f624d7af8202bce1b0c5f72511c841d6600a0c` | 14 passed |
| Isaac runtime | Isaac Sim/Kit 5.1.0, bundled Python 3.11.13 via `marslab/isaac_python.sh` | installation-local | `numpy`, `scipy`, `yaml`, `isaacsim`, and `omni` found before app startup; `rasterio` absent and `pxr` unavailable before Kit startup |

The RockyComposer failures are not promoted to skips or repaired in the
read-only checkout. Six failures originate from the missing rock license
sidecar used by source tests and pipeline fixtures. Four source skips remain
skips. Isaac/Kit baseline status is recorded separately from standalone USD.

## Baseline status

- Source revision and fixture input digest: `PASS`.
- Repeatable small legacy semantic output: `PASS`.
- Actual Isaac/Kit baseline open: `PASS`. `SimulationApp` started headless,
  opened the candidate `RockyComposer/out/jezero_rocky/rocky_scene.usda`
  (SHA-256 `759bc583145a1edd84e1a590df8388563266e093c1e277179bf8b189c42fdd77`),
  observed default prim `/World`, completed one runtime update, closed cleanly,
  and exited zero. This is a legacy baseline open, not target runtime parity.
- Full paper reproduction: `BLOCKED` by the missing canonical input/license
  package described in `PAPER_INPUTS.md`.
- Canonical asset redistribution: `BLOCKED` by unresolved legal provenance.
- `configs/scene/paper.yaml`: intentionally absent; required values cannot be
  resolved without guessing.
