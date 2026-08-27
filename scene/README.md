# MarsLab offline scene toolchain

`marslab_scene` builds relocatable Mars terrain, rock, and habitat scene
packages before MarsLab starts. It is a separate Python project under
`scene/`; it does not change the Isaac runtime entry point or add generation
settings to `configs/config.yaml`.

## Environments and installation

The toolchain supports Python 3.11 and 3.12. Use the standalone extra for
contract tests and USD inspection outside Isaac:

```bash
python3.11 -m pip install -e './scene[standalone-usd,test]'
python3.11 -m build scene
python3.11 -c 'import marslab_scene'
```

Standalone `usd-core` proves USD semantic/open/relocation behavior only. It is
not an Isaac runtime result. For authoring and runtime validation in the
supported simulator, install the core/test dependencies into Isaac's bundled
Python without installing the standalone USD extra:

```bash
marslab/isaac_python.sh -m pip install -e './scene[test]'
marslab/isaac_python.sh -c 'import marslab; import marslab_scene; from pxr import Usd'
```

The repository root `pyproject.toml` remains the MarsLab runtime project.
`scene/pyproject.toml` is the only scene project and contains no console entry
point. Public commands are the thin wrappers in `scripts/scene/`.

## Recipe and compatibility profiles

Every build consumes one schema-versioned YAML recipe. Paths are relative to
the recipe file, unknown keys fail validation, and
`scene.compatibility_profile` is required:

- `canonical` applies the consistent coordinate, elevation, flatness, and
  out-of-bounds contracts used by new synthetic correctness checks.
- `marslab_utils_6f30d67` preserves numerical behavior from the locked
  MarsLab-Utils source revision for migration parity.

The selected profile is resolved once and recorded in the resolved recipe,
terrain manifest, and final scene manifest. An imported terrain artifact with
a missing or different profile is rejected; profile rebinding is never
implicit. `configs/scene/smoke.yaml` is a copyright-safe terrain-only synthetic
recipe using `canonical`. `configs/scene/paper.example.yaml` is documentation,
not a runnable paper recipe: its input paths are intentionally unresolved until
the Paper Input Release Gate is satisfied.

Recipe sections are:

| Section | Contract |
| --- | --- |
| `scene` | scene ID and required compatibility profile |
| `terrain` | explicit HiRISE, new artifact, or normalized legacy-artifact input |
| `layers.rocks` | optional asset manifest, placement CSV, seed and scale policy |
| `layers.habitat` | optional singular habitat asset and anchor/alignment policy |
| `output` | output directory, working stage, runtime package and manifest names |

Scene generation parameters stay in `configs/scene/*.yaml`. MarsLab runtime
settings stay in `configs/config.yaml`; the two schemas are not merged.

## Build and validation

Use a fresh output root for ordinary validation:

```bash
scene_build_root="$(mktemp -d)"
marslab/isaac_python.sh scripts/scene/build_scene.py \
  --config configs/scene/smoke.yaml \
  --output-dir "${scene_build_root}/scene"
marslab/isaac_python.sh scripts/scene/validate_scene.py \
  --scene "${scene_build_root}/scene/scene.usdz"
```

`build_scene.py` performs config load, terrain build/import, layer placement,
single final authoring, validation, packaging, and atomic publish. Existing
output is protected by default. `--force` validates a new sibling temporary
output first, moves the old output to a recoverable sibling backup, and only
then publishes the new output. The command prints JSON with the published path,
runtime package, and backup path (or `null` when there was no previous output).

The published layout is:

```text
<output>/
├── scene.usda             # working composition stage
├── scene.usdz             # self-contained relocatable runtime package
├── manifest.yaml          # schema, profile, provenance and content digests
├── semantic-scene.json    # semantic validation inventory
├── terrain/               # copied TerrainArtifact root
├── rocks/                 # present only when a rock layer is enabled
└── habitats/              # present only when a habitat layer is enabled
```

Terrain and final manifests record relative POSIX paths, SHA-256 digests,
world conventions, source revisions, resolved config/profile data, seed and
layer summaries. They never store a developer home path or file URI. The USDZ
must open after copying that single file to an otherwise empty directory.

Asset contract validation is separate:

```bash
# Copyright-safe test fixtures; standalone/contract evidence only.
marslab/isaac_python.sh scripts/scene/validate_assets.py \
  --fixture scene/tests/fixtures

# Canonical bundles, only after real assets and licenses exist.
marslab/isaac_python.sh scripts/scene/validate_assets.py
```

## Runtime consumption

MarsLab consumes the already-built `scene.usdz`; it does not generate terrain
at startup. Actual runtime validation must start Isaac/Kit and invoke the real
MarsLab assembly path with a temporary copy of the runtime config:

```bash
marslab/isaac_python.sh scripts/scene/smoke_isaac.py \
  --scene "${scene_build_root}/scene/scene.usdz" \
  --base-runtime-config configs/config.yaml \
  --report "${scene_build_root}/isaac-smoke.json"
```

The smoke is a PASS only when the report proves the SimulationApp and world
started, MarsLab assembly was invoked, `/World/Terrain` contains a mesh, and at
least one runtime update completed. It changes only the temporary config copy.
The public MarsLab launch remains:

```bash
marslab/isaac_python.sh marslab/main.py --config configs/config.yaml
```

## Test tiers

Run the standalone development gate with strict marker registration:

```bash
python3.11 -m pytest -q --strict-markers \
  -m 'unit or contract or standalone_usd' scene/tests
```

Markers describe evidence truthfully:

| Marker | What a PASS establishes |
| --- | --- |
| `unit` | pure numerical/config behavior |
| `contract` | schema, path, manifest, artifact or synthetic pipeline boundary |
| `standalone_usd` | actual `usd-core`/`pxr` semantics outside Isaac |
| `legacy_parity` | direct locked-source versus target behavior |
| `isaac_runtime` | actual Isaac/Kit startup and runtime update |
| `marslab_runtime` | actual MarsLab config/assembly terrain resolution |
| `paper_reproduction` | actual paper inputs and canonical assets end to end |

Synthetic fixtures, standalone USD, skipped tests, mocks, and import fallbacks
never count as Isaac, MarsLab runtime, canonical-asset, or paper reproduction
PASS. Test-to-source dispositions are recorded in
`MIGRATION_TEST_MAP.md`.

## Provenance, licenses, and release status

- `PROVENANCE.md` locks source/target revisions, import mapping, environment
  identity, dependency-lock digests and baseline results.
- `PAPER_INPUTS.md` inventories candidate paper inputs, exact digests, missing
  provenance and expected semantic outputs.
- `THIRD_PARTY_NOTICES.md` and `LICENSES/MarsLab-Utils-MIT.md` preserve source
  attribution.
- `../assets/rocks/LICENSES/README.md` and
  `../assets/habitats/LICENSES/README.md` state the current asset redistribution
  status without claiming that absent bundles are available.

Canonical rock/habitat migration and paper reproduction are currently
`BLOCKED`: the repository does not contain authoritative canonical blobs with
complete redistribution evidence or a checksum-pinned paper input package.
Therefore no `configs/scene/paper.yaml` is committed, no generator-retirement
Release Gate is claimed, and no parity branch/tag may be frozen from synthetic
results. The synthetic contracts and actual runtime smoke remain valid only for
their explicitly named tiers.
