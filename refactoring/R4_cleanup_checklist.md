# R4-7 + R4-8 Cleanup Checklist

> **Executed 2026-04-23 per Option C (hard-delete).** `feedback_no_delete_comment`
> 정책은 동일 날짜에 retire. 상세 결과는 `work_log/LOG.md` 의 `[2026-04-23]
> Refactor R4 addendum` 엔트리 참조.

| Field | Value |
|-------|-------|
| git HEAD | `e0429e2075bb194265d042249ddcc395c0ff2a44` |
| Created | 2026-04-22 |
| Reviewer | Human user (`suberkut76@gmail.com`) |
| Author | Claude agent, read-only scan |
| Source plan | `/home/hoyunkim/.claude/plans/claude-md-plan-md-log-md-work-log-wiggly-acorn.md` |
| Policy constraints | `feedback_no_git_commands`, `feedback_delete_later_directory` (note: `feedback_no_delete_comment` retired 2026-04-23 — header above) |
| Oracle (frozen) | `scripts/phase1/run_stage3_monolithic.py` md5 `d4e147cd2345f927db18c4d7ad33b854` |

> **HOW TO USE.** Claude has **not** modified any code, YAML, or comment. Every
> action below is for the user to execute manually. Line numbers are frozen at
> the HEAD hash above — if you branch/commit between now and execution, re-run
> `git rev-parse HEAD` and spot-check a few line ranges before deleting.
> **Never touch the Oracle** regardless of which option you pick.

---

## Section 1 — Dead modules (R4-7 / 7-A)

| file | LOC | external imports | action |
|------|----:|-----------------:|--------|
| `marslab/ros2_bridge/topic_config.py` | 48 | **0** | `git mv marslab/ros2_bridge/topic_config.py delete_later/marslab/ros2_bridge/topic_config.py` + append entry to `delete_later/README.md` (date 2026-04-22, reason: R4-7 7-A, no import sites repo-wide). |

Verification (what the agent ran):
- `wc -l marslab/ros2_bridge/topic_config.py` → 48.
- `grep -rn "topic_config" marslab/ scripts/ tests/ configs/` → **no matches**
  anywhere. The file defines `SENSOR_TOPICS`, `build_topic_name`,
  `get_default_sub_topic`, none of which are imported by any runtime or test.

Post-move check: `grep -rn "topic_config" marslab/ scripts/ tests/ configs/`
must still return zero hits.

---

## Section 2 — Dead schema fields (R4-7 / 7-B)

| file | lines | symbol | real consumers | verdict | action |
|------|-------|--------|----------------|---------|--------|
| `marslab/config/schema/telemetry.py` | 1-29 (whole file, 29 LOC) | `TelemetryConfig` | **0 runtime consumers.** Imported by `schema/__init__.py:37`, `schema/root.py:15,35`. No code under `marslab/` / `scripts/` / `tests/` reads `config.telemetry.*`. `marslab.telemetry.json_sink` referenced in the docstring does **not exist** on disk. | dead whole-module | Option B: move to `delete_later/marslab/config/schema/telemetry.py`; then remove the `TelemetryConfig` import + `__all__` entry in `schema/__init__.py:37,68` and the `telemetry: TelemetryConfig` field in `schema/root.py:15,35`. Also delete the YAML block — see Section 3. |
| `marslab/config/schema/benchmark.py` | 1-18 (whole file, 18 LOC) | `BenchmarkConfig` | Seed-only consumers: `marslab/config/loader.py:56-57` (seed propagation) + `tests/unit/test_config_schema.py:7,66` + `tests/unit/test_seed_reproducibility.py:10,24,93`. **No runtime code** reads `annotation_format` / `dr_axes` / `num_samples` — the four fields are placeholders for v1.0 benchmark harness that does not exist yet. | schema declaration is live (seed plumbing) but field contents are dead | **Keep file** (loader needs the seed hook). Either (a) leave as-is, or (b) drop `annotation_format`/`dr_axes`/`num_samples` and keep only `seed`. Recommend leaving as-is — these are v1.0 placeholders and the cost is 4 fields * ~1 LOC each. |
| `marslab/config/schema/sensors.py` | 12-125 (`SensorImuConfig`, 114 LOC) | `SensorImuConfig` | **0 runtime consumers.** Docstring (line 15) claims `marslab.sensors.imu_probe.run_live_gravity_probe` reads it; **that module does not exist**. Docstring (line 89-94) claims `marslab.ros2_bridge.imu_node.IMUPublisher` reads `publish_rate_hz`/`frame_id`/`topic_name`; **that class does not exist** either (`grep -rn "IMUPublisher" marslab/` → 0 hits). Only import is the declaration in `SensorsConfig.imu` (line 137) → `root.py:28-34`. | dead whole-class; flagged as a SURPRISE finding (not explicitly listed in the plan but identical posture to telemetry) | Defer by default. If user picks Option B, also move/trim `sensors.py` — but this is **out of R4-7 scope as written**. See "Surprise findings" note at bottom. |
| `marslab/config/schema/sensors.py` | 128-137 (`SensorsConfig`, 10 LOC) | `SensorsConfig` | Referenced only by `schema/root.py:14,28`. No runtime consumer. | dead wrapper (depends on `SensorImuConfig`) | Same as row above — defer unless user wants to expand scope. |
| 2D LiDAR `pointcloud_frame_id` / `pointcloud_topic` fields | n/a | n/a | **Do not exist in the schema.** `grep -rn "pointcloud_frame_id\|pointcloud_topic" marslab/ scripts/ tests/ configs/` returns zero hits. The plan text was speculative. | not present | No action. |

---

## Section 3 — Dead YAML keys (R4-7 / 7-C)

### `configs/mars_env.yaml`

| lines | key | action |
|-------|-----|--------|
| 122-130 | comment header "Wk1 Phase B #23 … sensor subsystem + telemetry" | delete alongside the blocks below |
| 131-162 | `sensors:` block with `imu:` sub-tree (`sample_count`, `settle_steps`, `target_gz`, `tolerance`, `stddev_z_max`, `mount_link`, `fallback_link`, `publish_rate_hz`, `frame_id`, `topic_name`) | delete only if `SensorImuConfig` is also removed (Section 2 surprise finding). **Default: keep** — schema still declares it; YAML without schema would pass validation because `SensorsConfig` has defaults. |
| 164-168 | `telemetry:` block (`json_sink_path: "_workspace/wk1_imu_gate.json"`) | delete once `TelemetryConfig` is gone per Section 2. |
| 170-179 | `benchmark:` block (`annotation_format`, `dr_axes`, `num_samples`, `seed`) | **keep** — `seed` is plumbed through `loader.py`. `dr_axes`/`num_samples`/`annotation_format` harmless to keep. |

### `configs/scenarios/jezero_flat.yaml`, `jezero_rocks.yaml`, `jezero_crater.yaml`, `cave_lava_tube.yaml`, `cerberus_canyon.yaml`, `cerberus_canyon_easy.yaml`, `procedural_canyon.yaml`

- **No dead keys found.** Grep for `telemetry`, `benchmark`, `topic_config`,
  `lidar_2d` in these seven scenario files returned zero hits. The scenario
  layer is clean.

### `configs/robots/rover_m2020.yaml`

| lines | key | consumers | action |
|-------|-----|-----------|--------|
| 85-94 | `sensors.lidar_2d:` (`parent_link`, `local_translation`, `local_orientation_rpy_deg`, `profile`) | `marslab/sensors/sensor_spawner.py:181-194`, `scripts/phase1/run_stage3_monolithic_new.py:870-882`, `scripts/phase1/run_stage3_monolithic.py:777-789` (Oracle). | **KEEP** — this block is load-bearing for the 2D LaserScan pipeline consumed by slam_toolbox / Nav2. |
| n/a | `topic_config` block | — | not present in the file; no action. |
| n/a | `telemetry` / `benchmark` blocks | — | not present; no action. |

**Net result for Section 3:** only `configs/mars_env.yaml:164-168` (the four
`telemetry:` lines) is a firm delete candidate. Everything else stays until the
user extends R4-7 scope to include `SensorImuConfig`.

---

## Section 4 — DISABLED block inventory (R4-8 / 7-D)

Block ranges are **closed** (both endpoints inclusive). "end_line" = last
physical `#`-prefixed line of the disabled block, found by scanning forward
from the `# DISABLED` header until the first non-`#` line. LOC = `end_line - start_line + 1`.

### `marslab/robots/rover.py` (3 blocks, 22 LOC)

| start | end | LOC | tag | first header line |
|------:|----:|----:|-----|-------------------|
| 41 | 55 | 15 | R3-A1 | `# DISABLED (moved_to_marslab_math_R3-A1): original rpy_to_quat definition.` |
| 276 | 279 | 4 | R2-A3 | `# DISABLED (hardcoded_default_fallback, R2-A3):` |
| 343 | 346 | 4 | R2-A3 | `# DISABLED (hardcoded_default_fallback, R2-A3):` |

No R4-3 block was present at scan time (rover.py line 41 jumps straight into
the R3-A1 block; the drive_api_setup extraction is not yet landed at this HEAD).

### `marslab/ros2_bridge/sensor_graph.py` (1 block, 80 LOC)

| start | end | LOC | tag | first header line |
|------:|----:|----:|-----|-------------------|
| 46 | 125 | 80 | R4-5 | `# DISABLED R4-5 (2026-04-22): list-building helpers moved to` |

### `marslab/ros2_bridge/__init__.py` (1 block, 75 LOC)

| start | end | LOC | tag | first header line |
|------:|----:|----:|-----|-------------------|
| 43 | 117 | 75 | R4-6 | `# DISABLED R4-6 (2026-04-22): original BridgeContext dataclass + init_rclpy_side` |

### `marslab/ros2_bridge/odometry_math.py` (3 blocks, 68 LOC)

The three R3-A1 comment blocks are contiguous (headers at 37, 57, 85). Treated
as one logical span for the archive.

| start | end | LOC | tag | first header line |
|------:|----:|----:|-----|-------------------|
| 37 | 54 | 18 | R3-A1 | `# DISABLED (moved_to_marslab_math_R3-A1): original quat_inverse definition.` |
| 57 | 82 | 26 | R3-A1 | `# DISABLED (moved_to_marslab_math_R3-A1): original quat_multiply definition.` |
| 85 | 104 | 20 | R3-A1 | `# DISABLED (moved_to_marslab_math_R3-A1): original quat_rotate_vec definition.` |

### `scripts/phase1/run_stage2.py` (4 blocks, 169 LOC)

| start | end | LOC | tag | first header line |
|------:|----:|----:|-----|-------------------|
| 41 | 74 | 34 | R3-A4 | `# DISABLED (moved_to_marslab_runtime_R3-A4): inline loader replaced by` |
| 77 | 161 | 85 | R3-A3 | `# DISABLED (moved_to_marslab_terrain_loader_R3-A3): the local copy` |
| 164 | 179 | 16 | R3-A2 | `# DISABLED (moved_to_marslab_cli_R3-A2): argparse block relocated to` |
| 404 | 421 | 18 | R2-A2 | `# DISABLED (dict.get fallback, R2-A2): kept commented per` |

### `scripts/phase1/run_stage3_monolithic_new.py` (9 blocks, 232 LOC)

| start | end | LOC | tag | first header line |
|------:|----:|----:|-----|-------------------|
| 124 | 142 | 19 | R3-A1 | `# DISABLED (moved_to_marslab_math_R3-A1): original local rpy_to_quat definition.` |
| 173 | 257 | 85 | R3-A3 | `# DISABLED (moved_to_marslab_terrain_loader_R3-A3): the local copy` |
| 265 | 291 | 27 | R3-A2 | `# DISABLED (moved_to_marslab_cli_R3-A2): argparse block relocated to` |
| 316 | 327 | 12 | R3-A4 | `# DISABLED (moved_to_marslab_runtime_R3-A4): inline rover-block guard` |
| 380 | 390 | 11 | R3-A4 | `# DISABLED (moved_to_marslab_runtime_R3-A4): inline USD existence guard` |
| 400 | 406 | 7 | R4-1 | `# DISABLED R4-1 (2026-04-22): moved to marslab.sim.boot.boot_simulation_app.` |
| 412 | 417 | 6 | R4-1 | `# DISABLED R4-1 (2026-04-22): enable_extension + simulation_app.update()` |
| 446 | 471 | 26 | R4-1 | `# DISABLED R4-1 (2026-04-22): inline world creation + gravity + solver` |
| 617 | 627 | 11 | R2-A2 | `# DISABLED (dict.get fallback, R2-A2): see Oracle for reference.` |
| 788 | 800 | 13 | R3-A4 | `# DISABLED (moved_to_marslab_runtime_R3-A4): inline lidar-block guard` |

(10 rows here; 9 matches the plan's "9 blocks" because the three contiguous
R4-1 spans at 400/412/446 were counted as one R4-1 cluster in the plan. Count
as 10 physical blocks / 4 logical R-tags when scripting the archive.)

### Totals (R4-8)

| file | physical blocks | LOC |
|------|----------------:|----:|
| `marslab/robots/rover.py` | 3 | 23 |
| `marslab/ros2_bridge/sensor_graph.py` | 1 | 80 |
| `marslab/ros2_bridge/__init__.py` | 1 | 75 |
| `marslab/ros2_bridge/odometry_math.py` | 3 | 64 |
| `scripts/phase1/run_stage2.py` | 4 | 153 |
| `scripts/phase1/run_stage3_monolithic_new.py` | 10 | 237 |
| **TOTAL** | **22** | **632** |

(LOC figures include each block's trailing blank-comment separators. Plan
estimate was 372 LOC; the delta mainly comes from the newly-added R4-1 / R4-5 /
R4-6 blocks since the plan was drafted.)

**Oracle (`scripts/phase1/run_stage3_monolithic.py`) is frozen — not scanned,
not touched.**

---

## Section 5 — Execution sequence for the user

Execute top-to-bottom. Each numbered step is one atomic edit. After every step,
run `black --check marslab/ scripts/ tests/ && ruff check marslab/ scripts/ tests/
&& python3 -m pytest tests/unit/ -v`. If anything fails, STOP and revert that
step — do **not** continue.

1. **R4-7 step 1 — YAML dead block.** Delete `configs/mars_env.yaml:164-168`
   (the `telemetry:` YAML block). Rollback: `git checkout -- configs/mars_env.yaml`.
2. **R4-7 step 2 — schema field.** Remove `telemetry: TelemetryConfig = Field(...)`
   from `marslab/config/schema/root.py:35` and the `TelemetryConfig` import at
   `root.py:15`. Remove the `TelemetryConfig` line from `schema/__init__.py:37`
   and its `__all__` entry at line 68. Rollback: two git checkouts.
3. **R4-7 step 3 — dead module (Option B).**
   `git mv marslab/config/schema/telemetry.py delete_later/marslab/config/schema/telemetry.py`
   and append an entry to `delete_later/README.md` (date, reason "R4-7 7-B
   dead schema, 0 runtime consumers, git HEAD `e0429e2…`"). Rollback: `git mv`
   back.
4. **R4-7 step 4 — dead ros2_bridge module (Option B).**
   `git mv marslab/ros2_bridge/topic_config.py delete_later/marslab/ros2_bridge/topic_config.py`
   and extend the `delete_later/README.md` entry. Rollback: `git mv` back.
5. **R4-7 verification gate.** Re-run the 3-gate. Confirm
   `grep -rn "topic_config\|TelemetryConfig" marslab/ scripts/ tests/ configs/`
   returns only matches under `delete_later/`.
6. **R4-8 — only if Option B or C is chosen.** Process the R4-8 tables
   per-file, **from the bottom of each file upward** (so line numbers do not
   shift under you). For Option B, copy each block verbatim into
   `delete_later/disabled_blocks/<relative/path>.py.txt` before deleting it
   from the live file. For Option C, skip the archive step.
   Recommended order (highest noise first, so gains are visible early):
   1. `scripts/phase1/run_stage3_monolithic_new.py` (10 blocks, 237 LOC)
   2. `scripts/phase1/run_stage2.py` (4 blocks, 153 LOC)
   3. `marslab/ros2_bridge/sensor_graph.py` (1 block, 80 LOC)
   4. `marslab/ros2_bridge/__init__.py` (1 block, 75 LOC)
   5. `marslab/ros2_bridge/odometry_math.py` (3 blocks, 64 LOC)
   6. `marslab/robots/rover.py` (3 blocks, 23 LOC)
7. **R4-8 verification gate.** Re-run the 3-gate after each file. Then run
   the user-side Isaac Sim smoke trio from the plan (Phase 4 step 10):
   `run_stage2`, `run_stage3_monolithic_new`, `run_stage3_monolithic`.
8. **Oracle hash check (final).** `md5sum scripts/phase1/run_stage3_monolithic.py`
   must still return `d4e147cd2345f927db18c4d7ad33b854`. If not, **revert
   everything** — you accidentally edited the Oracle.

---

## Section 6 — `feedback_no_delete_comment` policy revision draft

Only needed if the user picks **Option B** or **Option C** for R4-8.

### Draft for Option B (archive-then-delete) — recommended

> **feedback_no_delete_comment (v2, 2026-04-22): Archive-then-delete carve-out.**
> Inline comment-outs remain the default for *new* deactivations (code change
> in the same file as the live replacement). Blocks tagged `# DISABLED R<n>-<tag>`
> may be deleted from live source **iff** a verbatim copy is first archived
> under `delete_later/disabled_blocks/<relative/path>.<ext>.txt` and the move
> is logged in `delete_later/README.md` per `feedback_delete_later_directory`.
> Rationale: the delete_later archive already satisfies the rollback intent
> of the original policy; keeping ~600 LOC of commented blocks in hot files
> (`run_stage2.py`, `run_stage3_monolithic_new.py`) costs readability with no
> rollback-safety benefit once the archive exists.

Pick exactly one draft; drop it into `CLAUDE.md` or the corresponding auto-memory
entry. Do not silently retire the policy without an explicit revision.

---

## Surprise findings (flagged for user decision)

1. **`SensorImuConfig` + `SensorsConfig` are fully dead** (Section 2, rows 3-4).
   The plan only named telemetry/benchmark/lidar_2d, but the sensor-IMU schema
   branch has the same "schema declared, no runtime consumer, docstring points
   at a nonexistent module" posture as `TelemetryConfig`. Leaving it alone is
   safe; consolidating with the telemetry cleanup would drop another ~124 LOC.
   Recommend: **ask the user whether to expand R4-7 scope before executing**.
2. **`BenchmarkConfig.seed` flips the field from dead to keep.**
   `marslab/config/loader.py:56-57` does `benchmark.model_copy(update={"seed": ...})`
   during seed propagation. Removing the class would break the loader. Keep
   the file; trim only the three placeholder fields (`annotation_format`,
   `dr_axes`, `num_samples`) if you want a smaller schema.
3. **`pointcloud_frame_id` / `pointcloud_topic` do not exist** anywhere in the
   repo (Section 2 last row). The plan item was speculative; no action needed.
4. **R4-3 `drive_api_setup` extraction has not landed yet at this HEAD.** The
   plan said another agent would add an R4-3 block to `rover.py`; the file
   currently has only the pre-R4 R3-A1 and R2-A3 disabled blocks. If R4-3
   lands before the user executes R4-8, re-scan `rover.py` with
   `grep -n "# DISABLED" marslab/robots/rover.py` and extend the table in
   Section 4.
