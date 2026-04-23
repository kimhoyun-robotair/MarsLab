# SLAM Candidate Survey for MarsLab v1.0

**Document type:** Research survey / technical justification for the v1.0 SLAM choice.
**Author:** MarsLab development harness (P1-3 task, `log-md-r4-addendum-jolly-spring.md` section 9)
**Date:** 2026-04-23
**Audience:** iSpaRo 2026 paper reviewers; future MarsLab contributors (v2.0/v3.0 planners)
**Status:** Decision record. v1.0 pipeline is `slam_toolbox`; §2-§7 compare the six
candidates that justify that choice and frame v2.0/v3.0 upgrade paths.

---

## 1. Purpose and scope

MarsLab v1.0 (iSpaRo 2026, deadline 2026-06-16) ships with exactly one SLAM
pipeline integrated: **slam_toolbox** driven by a 2D planar LiDAR. The 8-page
iSpaRo paper needs to (a) justify that narrow choice and (b) point future work
at a defensible upgrade path.

This survey answers four questions:

1. Why `slam_toolbox` for v1.0, given six credible alternatives?
2. Which alternatives should be tried in v2.0 when photorealism tightens the
   benchmark, and what is the testable hypothesis for each?
3. Which alternatives are structurally incompatible with the MarsLab operating
   envelope (GPS-denied, tau 0.3-2.0, ROS 2 Jazzy, feature-sparse Mars terrain)?
4. Where are the research gaps that MarsLab itself can help close?

Per guideline G3, this document is a comparison and justification only. No code
from any surveyed repository is reused in MarsLab. Algorithmic inspiration only.

### 1.1 MarsLab operating envelope (the constraints every candidate is judged against)

| Constraint | Value | Why it matters |
|---|---|---|
| ROS 2 distribution | Jazzy Jalisco (LTS through May 2029) [12] | Humble-only ports are a short-term liability. |
| GPS availability | None (Mars) | Any SLAM that requires GNSS priors is disqualified. |
| Visual texture | Low (regolith, repeating rocks) | Visual front-ends with DBoW vocabularies trained on Earth imagery are brittle. |
| Illumination dynamic range | ~10x (tau 0.3 → 2.0) [MarsLab `configs/mars_env.yaml`] | Feature detectors with fixed thresholds thrash across a single sol. |
| Dust opacity (tau) | 0.3 .. 2.0 | Particulate scattering degrades both LiDAR returns and camera contrast. |
| Gravity | 3.72 m/s^2 | IMU biases identified on Earth do not transfer; gravity-vector estimation differs. |
| Terrain | Sparse 3D geometry, scattered rocks, slopes, canyons, caves | LiDAR-degenerate in open plains; camera-degenerate under shadowing. |
| Compute budget | 1x RTX-class GPU for Isaac Sim, CPU for SLAM stack | SLAM must run alongside rendering on one workstation. |

### 1.2 The six candidates

| # | Candidate | Family | v1.0 role |
|---|---|---|---|
| 1 | `slam_toolbox` | 2D graph SLAM (Karto derivative) | **Integrated** |
| 2 | `rtabmap_ros` | RGB-D / stereo / LiDAR hybrid, appearance-based | v2.0 contender |
| 3 | LIO-SAM | Tightly-coupled 3D-LiDAR + IMU, factor graph | v2.0 contender |
| 4 | FAST-LIO2 | Iterated EKF, 3D-LiDAR + IMU | v2.0 contender |
| 5 | ORB-SLAM3 | Visual / visual-inertial / stereo | Disqualified for v1.0 (see § 8.5) |
| 6 | `cartographer_ros` | 2D/3D submap SLAM (Google) | v2.0 fallback |

---

## 2. Candidate 1 -- slam_toolbox

### 2.1 Summary

`slam_toolbox` is a 2D pose-graph SLAM package maintained by Steve Macenski,
originally derived from the Karto SLAM stack [1]. It is the de-facto Nav2
companion and the most feature-complete 2D SLAM package with first-class ROS 2
support. MarsLab v1.0 consumes the 2D LiDAR already attached to the rover (see
`marslab/ros2_bridge/sensor_graph.py` -- planar scan publisher).

### 2.2 Specifications

| Axis | Value |
|---|---|
| Sensors required | `sensor_msgs/LaserScan` (2D planar LiDAR) + odom TF [1] |
| IMU | Optional; not required |
| Compute | CPU-only, Ceres solver. No GPU path [1] |
| Real-time factor | "5x+ real-time up to ~30,000 sq. ft." (indoor warehouse claim) [1] |
| Loop closure | Scan-match with `loop_match_minimum_response_{coarse,fine}` and `loop_search_maximum_distance` parameters [1] |
| ROS 2 Jazzy | **Yes** -- released 2025-04-15, latest tag 2.8.4 (2026-01-24) [1][13] |
| License | LGPL-2.1 [1] |
| Active maintenance | **Yes** -- 50 releases to date, active through Jan 2026 [1] |

### 2.3 Fit against the MarsLab envelope

| Criterion | Verdict | Notes |
|---|---|---|
| Feature sparsity | **Strong** | 2D scan matcher is topology-based, not descriptor-based. Mars rocks silhouetted at rover height produce stable scan features. |
| Illumination | **Immune** | LiDAR sensor -- unaffected by tau. |
| GPS-denied | **Native** | Pose-graph anchored to TF; no GNSS assumption. |
| Dust tolerance | **Partial** | At tau > ~1.5 simulated particulate scattering attenuates LiDAR returns; MarsLab models this in `marslab/ros2_bridge/sensor_graph.py`. `slam_toolbox` degrades gracefully (longer scan-match search) rather than failing. TODO(v1.1): verify attenuation model matches physical lidar Mie scattering. |
| ROS 2 Jazzy | **Native** | First-party binary. |
| Loop closure robustness | **Moderate** | Scan-match based. Works well in structured environments; can produce false positives in self-similar rock fields. Tunable. |
| Real-time factor | **High** | CPU-bound, leaves GPU free for rendering. |

### 2.4 Known limitations in Mars context

- 2D projection discards slope information; the rover cannot see rocks shorter
  than the LiDAR mount height.
- `slam_toolbox` assumes a roughly planar world; on canyon walls and crater
  interiors (MarsLab scenarios 3 and 4) the 2D assumption is locally violated.
- "Loop closure" in self-similar open terrain (scenario 1: Basic Mars) has no
  unique anchoring features. Long traverses accumulate yaw drift that only a
  loop closure or external heading cue can correct.
- Requires high-quality wheel odometry [1]; Mars wheel slip (modelled in v3.0
  terramechanics) is not yet simulated, so v1.0 odometry is optimistic.

---

## 3. Candidate 2 -- rtabmap_ros

### 3.1 Summary

`rtabmap_ros` is the ROS binding for RTAB-Map (Real-Time Appearance-Based
Mapping) by Labbé and Michaud, maintained by IntRoLab, Université de
Sherbrooke. It is the most flexible multi-sensor SLAM in this survey:
monocular, stereo, RGB-D, and 3D LiDAR inputs are all supported, and can be
combined in the same run. The loop-closure detector is a DBoW2-style
bag-of-visual-words model layered over hierarchical memory management [2][8].

### 3.2 Specifications

| Axis | Value |
|---|---|
| Sensors | Stereo, RGB-D, monocular + depth, 3D LiDAR [2] |
| IMU | Optional (for odom fusion) |
| Compute | CPU dominant; optional CUDA acceleration for feature extraction |
| Real-time factor | Not published with single number. Reported to sustain real-time on modern laptop CPUs for indoor RGB-D [8] |
| Loop closure | DBoW2-style BoW over BRIEF/ORB/SIFT/SURF; hierarchical working/long-term memory; semantic zone management (2024) [8] |
| ROS 2 Jazzy | **Yes** -- binary builds for Humble, Jazzy, Rolling [2] |
| License | BSD-3-Clause [2] |
| Active maintenance | **Yes** -- frequent releases |

### 3.3 Fit against the MarsLab envelope

| Criterion | Verdict | Notes |
|---|---|---|
| Feature sparsity | **Mixed** | LiDAR mode survives. Visual modes depend on BoW vocabulary hits; off-the-shelf DBoW2 vocab is Earth-trained and produces noisy matches on regolith. |
| Illumination | **Weak** in visual mode | BoW frequencies shift under 10x illumination change. Strong in LiDAR-only mode. |
| GPS-denied | **Native** | |
| Dust tolerance | **Weak** (visual) / **Partial** (LiDAR) | At tau > 1.5 camera contrast drops below feature-detection threshold. |
| ROS 2 Jazzy | **Native** | |
| Loop closure robustness | **Highest** of the six in terms of algorithmic depth, assuming the visual front-end is healthy |
| Real-time factor | **Adequate** but heavier than slam_toolbox |

### 3.4 Known limitations in Mars context

- DBoW2 vocabulary is trained on Earth imagery. Its discriminative power on
  homogeneous Mars regolith is, to the authors' knowledge, unquantified. **Gap
  worth publishing**: retrain BoW on MarsLab-generated imagery and measure
  loop-closure precision/recall vs tau.
- Memory management works by demoting "least-weight" nodes; in a self-similar
  Mars plain every node is low weight and the memory policy can churn.
- License (BSD-3) is more permissive than LGPL (slam_toolbox) and GPL
  (ORB-SLAM3, FAST-LIO). Advantage for downstream integrators.

---

## 4. Candidate 3 -- LIO-SAM

### 4.1 Summary

LIO-SAM (Shan et al., IROS 2020) is a tightly-coupled 3D-LiDAR + IMU SLAM
system built on the GTSAM factor graph. It runs two factor graphs concurrently:
one for global map optimisation and one that resets at each keyframe for
low-latency IMU-rate odometry [3]. It popularised the pattern later refined by
FAST-LIO, Voxel-SLAM, and others.

### 4.2 Specifications

| Axis | Value |
|---|---|
| Sensors | 3D mechanical LiDAR (Velodyne, Ouster) with ring + timestamp; 9-axis IMU ≥ 200 Hz (500 Hz recommended) [3] |
| IMU | **Required** (9-axis) |
| Compute | CPU. "Up to 10x faster than real-time" on modern CPUs [3] |
| Loop closure | ICP-based, adapted from LeGO-LOAM [3] |
| ROS 2 Jazzy | **No first-party port.** Upstream branch targets Humble; issue #549 (opened 2025-07-08) is still open [14]. Third-party `crystaldust/lio_sam_ros2` exists. |
| License | BSD-3-Clause [3] |
| Active maintenance | Moderate (146 commits, 170 open issues) [3] |

### 4.3 Fit against the MarsLab envelope

| Criterion | Verdict | Notes |
|---|---|---|
| Feature sparsity | **Strong** | LiDAR-based; robust to low-texture. Confirmed on lunar analog data: FAST-LIO (same family) outperformed LeGO-LOAM RMSE_ATE 10.86% → ~1% on LuSNAR [4]. |
| Illumination | **Immune** | LiDAR. |
| GPS-denied | **Native** | GPS factor is optional in mapOptimization.cpp [3]. |
| Dust tolerance | **Moderate** | Point filtering via ring geometry is robust but attenuated returns at tau > 1.5 need validation on MarsLab's scattering model. |
| ROS 2 Jazzy | **Weak** | Community ports only, tracking Humble. Porting risk for a 2-month v1.0 schedule is high. |
| Loop closure robustness | **Moderate** | ICP loop closures are reliable when geometry is distinctive; false on self-similar plains. |
| Real-time factor | **Very high** | |

### 4.4 Known limitations in Mars context

- 9-axis IMU assumption requires a magnetometer. Mars has a very weak, static,
  crustal magnetic field with no global dipole; a 9-axis IMU on Mars behaves as
  a 6-axis (accel + gyro) instrument for all practical purposes. TODO(v1.1):
  verify whether LIO-SAM degrades gracefully if the magnetometer channel is
  noise-dominated.
- IMU pre-integration requires well-calibrated gravity (3.72 m/s^2 on Mars).
  Default LIO-SAM config assumes Earth gravity; configs must be overridden.
- Loop closure via ICP is memory-heavy for multi-kilometre traverses.

---

## 5. Candidate 4 -- FAST-LIO2

### 5.1 Summary

FAST-LIO2 (Xu et al., 2021) is a tightly-coupled iterated EKF LiDAR-inertial
odometry system built on the `ikd-Tree` incremental k-d tree. It drops the
feature-extraction stage used in FAST-LIO and LOAM/LIO-SAM and operates
directly on raw scan points, making it both broader in LiDAR compatibility and
the fastest system in this survey [5][6]. FAST-LIO2 does **not** include
built-in loop closure; third-party wrappers (`FAST-LIO-SAM`,
`FAST-LIO-SAM-QN`) bolt on pose-graph optimisation [6].

### 5.2 Specifications

| Axis | Value |
|---|---|
| Sensors | Spinning (Velodyne, Ouster) + solid-state (Livox Avia, Horizon, MID-70); 6- or 9-axis IMU [5] |
| IMU | Required (6-axis sufficient; useful for Mars) |
| Compute | CPU; runs on ARM-class hardware (Khadas VIM3, TX2, Pi 4B 8GB) [5] |
| LiDAR rate | > 100 Hz sustained [5] |
| Loop closure | **None built-in.** Add-on via FAST-LIO-SAM / FAST-LIO-SAM-QN [6] |
| ROS 2 Jazzy | **No first-party port.** Issue #234 open. Community ports (`Taeyoung96`, `Ericsii`, `Lee-JaeWon`, `MIT-SPARK/spark-fast-lio`) target Humble [15]. |
| License | GPL-2.0 [5] |
| Active maintenance | Active upstream; ROS 2 is community-maintained |

### 5.3 Fit against the MarsLab envelope

| Criterion | Verdict | Notes |
|---|---|---|
| Feature sparsity | **Strong** | No feature-extraction stage; operates on raw points. Outperformed other LiDAR baselines on LuSNAR lunar dataset [4]. |
| Illumination | **Immune** | LiDAR. |
| GPS-denied | **Native** | |
| Dust tolerance | **Strong** (relative) | Raw-point matching degrades more gracefully than feature-based methods when returns are partial. |
| ROS 2 Jazzy | **Weak** | Community ports only. |
| Loop closure robustness | **None built-in** -- this is the key gap. Long traverses drift. |
| Real-time factor | **Highest in survey** | Runs on ARM hardware. |
| IMU requirement | **6-axis** is sufficient, unlike LIO-SAM's 9-axis. Aligns with Mars sensor reality. |

### 5.4 Known limitations in Mars context

- **No loop closure.** For MarsLab traverse scenarios >500 m this is
  disqualifying unless combined with a pose-graph wrapper.
- GPL-2.0 license: downstream users integrating FAST-LIO2 into proprietary
  stacks face copyleft obligations. License is compatible with MarsLab's
  Apache 2.0 only via "mere aggregation" (separate process). If MarsLab ever
  wants to embed SLAM in-process, GPL is a hard stop.
- Gravity vector magnitude must be configured; default values assume Earth.

---

## 6. Candidate 5 -- ORB-SLAM3

### 6.1 Summary

ORB-SLAM3 (Campos et al., 2021) is the visual-SLAM baseline most often cited
in academic benchmarks. It supports monocular, stereo, RGB-D, and
visual-inertial modes with pin-hole and fisheye lens models, uses DBoW2 for
place recognition, and maintains multi-map "Atlas" state for relocalisation [7].

### 6.2 Specifications

| Axis | Value |
|---|---|
| Sensors | Monocular, stereo, RGB-D; optional IMU [7] |
| IMU | Optional (visual-inertial mode) |
| Compute | CPU; "powerful i7 ensures real-time" [7]. No CUDA dependency. |
| Loop closure | DBoW2 bag-of-words [7] |
| ROS 2 Jazzy | **Indirect.** No upstream ROS 2 support. Community wrappers: `Mechazo11/ros2_orb_slam3` has a `jazzy` branch [16]; others are Humble-only. |
| License | GPL-3.0 (commercial license available from authors) [7] |
| Active maintenance | **Weak.** Last upstream release v1.0 is 2021-12-22 [7] |

### 6.3 Fit against the MarsLab envelope

| Criterion | Verdict | Notes |
|---|---|---|
| Feature sparsity | **Weak** | ORB feature detector requires textured, non-blurry scenes to initialise, track, and close loops. MADMAX reports relocalisation failures on low-texture Mars-analog imagery [9]. |
| Illumination | **Weak** | Fixed FAST threshold; 10x dynamic range over a sol causes feature-count collapse in shadow or strong backlight. |
| GPS-denied | **Native** | |
| Dust tolerance | **Very weak** | Contrast degrades with tau; at tau > 1.0 ORB feature count drops sharply. Not quantified on Mars-specific data -- research gap. |
| ROS 2 Jazzy | **Weak** | Community wrapper only. |
| Loop closure robustness | **Good** when features are available; moot when features are not. |
| License | **GPL-3.0** is the most restrictive in the survey. |

### 6.4 Known limitations in Mars context

- LuSNAR lunar simulation benchmark reports ORB-SLAM2 (close cousin) ATE
  3.381 m vs. LVI-SAM 3.617 m and an improved method 2.894 m [4]. ORB-SLAM3
  stereo RMSE_ATE 0.13% (normalised) on LuSNAR [4], but this is on a simulated
  dataset where texture is generated, not the extreme-low-texture regime of
  Mars regolith in MarsLab dust storms.
- MADMAX reports that ORB-SLAM2 relocalisation requires "a textured, non-blurry
  scene" [9]. Shadow transitions on Mars (high dynamic range) violate this.
- Upstream is essentially dormant since 2021. Any production deployment will
  drift from upstream patches quickly.
- **MarsLab recommendation: ORB-SLAM3 is studied as a *failure case* in the
  iSpaRo 2026 paper, not as a baseline.** It illustrates why MarsLab-grade
  illumination and dust randomisation matter for SLAM benchmarking.

---

## 7. Candidate 6 -- cartographer_ros

### 7.1 Summary

`cartographer_ros` is Google Cartographer's ROS integration. Cartographer is
an academically influential submap-based SLAM system supporting both 2D and
3D LiDAR. The ROS 2 port is maintained in the `ros2/cartographer_ros`
repository [10]. Active maintenance has waxed and waned since Google
deprioritised the project internally in 2019, but the ROS 2 community fork is
alive and packaged for Jazzy [11].

### 7.2 Specifications

| Axis | Value |
|---|---|
| Sensors | 2D or 3D LiDAR; optional IMU and odometry [10] |
| IMU | Optional |
| Compute | CPU; Ceres solver |
| Loop closure | Submap-based scan matching with branch-and-bound global localisation |
| ROS 2 Jazzy | **Yes** -- released 2025-05-20 [11] |
| License | Apache 2.0 [10] |
| Active maintenance | **"MAINTAINED"** per ROS index; recent build fixes for Rolling and new glog [11] |

### 7.3 Fit against the MarsLab envelope

| Criterion | Verdict | Notes |
|---|---|---|
| Feature sparsity | **Strong** (2D/3D) | Branch-and-bound scan match is robust. |
| Illumination | **Immune** | LiDAR. |
| GPS-denied | **Native** | |
| Dust tolerance | **Moderate** | Similar to slam_toolbox; point attenuation at high tau is the main risk. |
| ROS 2 Jazzy | **Native** | |
| Loop closure robustness | **Strong** | Branch-and-bound is one of the most robust loop-closure techniques for LiDAR. |
| Real-time factor | Reasonable, but heavier than slam_toolbox on 2D. |
| License | **Apache 2.0** -- best license alignment with MarsLab. |

### 7.4 Known limitations in Mars context

- Google-internal development deprioritised circa 2019; community pace is
  slower than `slam_toolbox`'s.
- Lua-based config is awkward for MarsLab's YAML-only constraint (G5). An
  adapter layer would be needed.
- 3D mode is noticeably more resource-intensive than `slam_toolbox` and
  Nav2 integration docs are thinner than for `slam_toolbox`.

---

## 8. Cross-cutting comparison

### 8.1 Sensor requirements

| Candidate | 2D LiDAR | 3D LiDAR | Mono | Stereo | RGB-D | IMU required | GPS required |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| slam_toolbox | Y | - | - | - | - | N | N |
| rtabmap_ros | - | Y | Y+depth | Y | Y | optional | N |
| LIO-SAM | - | Y | - | - | - | **9-axis** | optional |
| FAST-LIO2 | - | Y | - | - | - | 6-axis | N |
| ORB-SLAM3 | - | - | Y | Y | Y | optional | N |
| cartographer_ros | Y | Y | - | - | - | optional | N |

### 8.2 Real-time factor on MarsLab target hardware

Reproducible numbers on MarsLab hardware do not exist yet (see research gap
§ 10). Published relative rankings from third-party benchmarks:

| Candidate | Reported real-time factor | Source |
|---|---|---|
| FAST-LIO2 | Runs on ARM (Raspberry Pi 4B) > 100 Hz LiDAR | [5] |
| LIO-SAM | "Up to 10x real-time" | [3] |
| slam_toolbox | "5x+ real-time" 2D | [1] |
| cartographer_ros | Real-time 2D on CPU | [10] |
| rtabmap_ros | Real-time on modern laptop CPU for RGB-D indoor | [8] |
| ORB-SLAM3 | Real-time on "i7" (author claim) | [7] |

TODO(v1.1): benchmark all six candidates on the same MarsLab scenario-1 bag
(Basic Mars, tau=0.5, 200 s traverse) and publish real-time factor per CPU core
on the reference workstation.

### 8.3 Feature-sparsity and illumination tolerance

| Candidate | Feature-sparsity | Illumination |
|---|:-:|:-:|
| slam_toolbox | Good (2D scan topology) | Immune |
| rtabmap_ros (LiDAR) | Good | Immune |
| rtabmap_ros (RGB-D/stereo) | Weak | Weak |
| LIO-SAM | Good | Immune |
| FAST-LIO2 | **Best** (raw-point matching) | Immune |
| ORB-SLAM3 | **Weak** | **Weak** |
| cartographer_ros | Good | Immune |

The LuSNAR lunar benchmark [4] reports FAST-LIO's RMSE_ATE significantly below
LeGO-LOAM's 10.86% and below ORB-SLAM3 stereo's 0.13% (normalised units are
not directly comparable; the paper's own conclusion is that LiDAR methods
dominate visual methods in low-texture planetary scenes). This is consistent
with the MADMAX finding [9] that visual methods relocalise unreliably on
Mars-analog terrain.

### 8.4 ROS 2 Jazzy maturity

| Candidate | Jazzy status | Evidence |
|---|:-:|---|
| slam_toolbox | **First-party** | [1][13] |
| cartographer_ros | **First-party** | [11] |
| rtabmap_ros | **First-party** | [2] |
| LIO-SAM | Community / open issue | [14] |
| FAST-LIO2 | Community only, Humble-tracking | [15] |
| ORB-SLAM3 | Community wrappers | [16] |

### 8.5 Licenses

| Candidate | License | MarsLab (Apache 2.0) compatibility |
|---|---|---|
| cartographer_ros | **Apache 2.0** | Identical; best fit. |
| rtabmap_ros | BSD-3 | Permissive; easy. |
| LIO-SAM | BSD-3 | Permissive; easy. |
| slam_toolbox | **LGPL-2.1** | OK if dynamically linked / used as-is via ROS 2 bindings. |
| FAST-LIO2 | **GPL-2.0** | In-process embedding triggers copyleft. |
| ORB-SLAM3 | **GPL-3.0** | Most restrictive; commercial license sold separately. |

### 8.6 Dust tolerance (qualitative)

No public SLAM benchmark isolates dust opacity (tau) as an independent
variable. This is a MarsLab-specific research gap and a **publishable
contribution**: MarsLab can sweep tau ∈ {0.3, 0.5, 1.0, 1.5, 2.0} against
each candidate and report ATE/RPE curves. First-order expectations:

- **LiDAR-based (slam_toolbox, cartographer, LIO-SAM, FAST-LIO2):** degrade
  gradually as scattering reduces return density. FAST-LIO2 likely degrades
  most gracefully (raw-point, no feature threshold).
- **Visual (ORB-SLAM3, rtabmap visual modes):** collapse sharply once contrast
  drops below the ORB/BRIEF feature threshold (approximately tau > 1.0 in
  MarsLab's current atmosphere model; TODO(v1.1): verify).

### 8.7 Loop-closure robustness (qualitative ranking)

1. rtabmap_ros (DBoW + hierarchical memory) -- most sophisticated when visual
   front-end is healthy.
2. cartographer_ros (branch-and-bound) -- most reliable in LiDAR-only mode.
3. LIO-SAM (ICP-based) -- good in geometry-rich scenes.
4. slam_toolbox (scan match) -- simple but robust.
5. ORB-SLAM3 (DBoW2 + Atlas) -- strong when features present, brittle
   otherwise.
6. FAST-LIO2 -- none built-in; requires third-party wrapper.

### 8.8 Dependency matrix at a glance

| Candidate | Sensor | IMU | GPU | Jazzy | License | LC built-in |
|---|---|:-:|:-:|:-:|---|:-:|
| slam_toolbox | 2D LiDAR | N | N | **Y** | LGPL-2.1 | Y |
| rtabmap_ros | RGB-D/Stereo/3D LiDAR | optional | optional | **Y** | BSD-3 | Y (appearance) |
| LIO-SAM | 3D LiDAR | 9-axis Y | N | Community | BSD-3 | Y (ICP) |
| FAST-LIO2 | 3D LiDAR | 6-axis Y | N | Community | **GPL-2.0** | **N** |
| ORB-SLAM3 | Cameras | optional | N | Community | **GPL-3.0** | Y |
| cartographer_ros | 2D/3D LiDAR | optional | N | **Y** | Apache 2.0 | Y (B&B) |

---

## 9. Recommendation

### 9.1 v1.0 (iSpaRo 2026): slam_toolbox + 2D LiDAR

**Decision:** keep the existing `slam_toolbox` integration.

**Rationale.** For an 8-page paper whose contribution is a simulation
platform (not a SLAM algorithm), the SLAM stack only needs to be:

1. Robust enough to close short loops on all seven v1.0 scenarios.
2. ROS 2 Jazzy native with Nav2 integration documented.
3. CPU-only (Isaac Sim already uses the GPU).
4. Low-maintenance so engineering effort stays on scenarios and atmosphere.

`slam_toolbox` satisfies all four. The alternatives either lack first-party
Jazzy support (LIO-SAM, FAST-LIO2, ORB-SLAM3), introduce license complications
(FAST-LIO2, ORB-SLAM3), or add operational overhead without benchmark lift for
the v1.0 scenario set (rtabmap, cartographer).

**Claim in the paper:** MarsLab v1.0 integrates `slam_toolbox` as a reference
baseline; the platform is sensor-agnostic and any ROS 2-compatible SLAM can
replace it. The paper presents SLAM accuracy (ATE, RPE) on all seven scenarios
with `slam_toolbox` as the reference, and flags tau > 1.5 as the regime where
a 2D LiDAR baseline approaches its limit.

### 9.2 v2.0 (post-iSpaRo): rtabmap vs LIO-SAM head-to-head

**Proposed experiment.** Run `rtabmap_ros` (RGB-D + 3D LiDAR hybrid) and
LIO-SAM (3D LiDAR + IMU) on the same MarsLab scenarios with tau swept over
{0.3, 0.5, 1.0, 1.5, 2.0}. Report ATE and loop-closure precision/recall per
tau bucket.

**Testable hypothesis (H1):** LIO-SAM's ATE at tau ≥ 1.5 is within 20% of its
ATE at tau = 0.3, because its reliance on IMU pre-integration compensates for
partial LiDAR returns. rtabmap's visual-component-enabled ATE at the same tau
degrades by > 50% because the BoW front-end loses features first.

**Secondary hypothesis (H2):** FAST-LIO2 (with a pose-graph wrapper such as
FAST-LIO-SAM-QN) beats both on real-time factor while achieving ATE within 10%
of LIO-SAM, validating the raw-point approach for Mars.

**Secondary hypothesis (H3):** ORB-SLAM3 (stereo or stereo-inertial) fails to
track for > 10 s continuously on scenario 1 (Basic Mars, open plain) at any
tau. This is a null-result contribution: MarsLab can quantify the regime where
visual SLAM is infeasible.

### 9.3 v3.0: co-evolution with terramechanics and RL

When terramechanics (Bekker/Janosi) lands in v3.0, wheel slip will make the
odometry input to `slam_toolbox` much worse than today's (optimistic) rigid
kinematic model. At that point:

- A tightly-coupled LIO stack (LIO-SAM or FAST-LIO2) becomes **necessary**,
  not optional, because IMU pre-integration absorbs wheel-slip odometry
  errors.
- RL exploration policies need onboard SLAM uncertainty estimates as reward
  input; rtabmap's appearance-based re-localisation confidence is the
  best-documented API.
- Multi-robot scenarios require a SLAM stack with sub-map merging; only
  `cartographer_ros` and rtabmap have mature multi-session merge support.

### 9.4 Recommendation matrix

| Version | Primary SLAM | Secondary SLAM | Sensor suite |
|---|---|---|---|
| v1.0 (iSpaRo 2026) | **slam_toolbox** | - | 2D LiDAR + wheel odom |
| v2.0 (photorealism) | LIO-SAM *or* FAST-LIO2+wrapper | rtabmap_ros (hybrid) | 3D LiDAR + IMU (+ stereo for rtabmap) |
| v3.0 (terramechanics + RL + multi-robot) | FAST-LIO2 + pose-graph | cartographer_ros (multi-session merge) | 3D LiDAR + IMU + stereo + RGB-D |

---

## 10. Research gaps (what MarsLab can publish)

These are gaps in the literature that MarsLab is uniquely positioned to close
because of its controllable dust (tau), illumination (sun elevation), and
terrain (DEM + scenario randomisation):

- **G-R1.** No public SLAM benchmark isolates dust opacity (tau) as an
  independent variable. MarsLab can publish ATE vs tau curves for all six
  candidates.
- **G-R2.** DBoW2 vocabulary for Mars regolith does not exist. Retraining BoW
  on MarsLab imagery and measuring loop-closure precision/recall is
  publishable.
- **G-R3.** No SLAM paper has reported IMU pre-integration behaviour under
  Mars gravity (3.72 m/s^2) with wheel-slip odometry. v3.0 MarsLab +
  terramechanics would be the first.
- **G-R4.** ORB-SLAM3 failure regime under tau sweep is not quantified in
  published work. Null-result contribution.
- **G-R5.** LIO-SAM's 9-axis IMU assumption vs. Mars's effectively
  magnetometer-free environment: has anyone run LIO-SAM with a 6-axis-only
  configuration against Mars-analog data? No evidence found in this survey.

---

## 11. Known caveats in this survey

- Real-time-factor numbers above are author claims from READMEs, not
  measurements on MarsLab hardware. Flagged TODO(v1.1): verify.
- Two primary sources (MDPI Applied Sciences visual-vs-LiDAR comparison and
  IET Cyber-Systems and Robotics 2025 GPS-denied LiDAR survey) were
  unreachable via automated fetch (HTTP 403). Citations for them are by
  metadata only and should be reviewed directly before inclusion in the
  iSpaRo paper.
- Dust-tolerance statements are qualitative; no candidate in this survey
  publishes Mie-scattering-calibrated SLAM benchmarks.
- The visual-SLAM failure mode for Mars is inferred from MADMAX (Morocco
  analog) [9] and LuSNAR (lunar simulation) [4]; neither fully captures Mars
  atmospheric dust.
- No code was copied from any repository in this survey. Per G3, algorithm and
  flowchart inspiration only. License obligations of candidates integrated as
  binaries (slam_toolbox LGPL-2.1) are separate from MarsLab's Apache 2.0
  source licence.

---

## References

[1] S. Macenski, "slam_toolbox: SLAM for the dynamic world,"
github.com/SteveMacenski/slam_toolbox, latest release 2.8.4, 2026-01-24.

[2] M. Labbé and F. Michaud, `rtabmap_ros`,
github.com/introlab/rtabmap_ros. Binaries for Humble, Jazzy, Rolling; license
BSD-3-Clause.

[3] T. Shan, B. Englot, D. Meyers, W. Wang, C. Ratti, D. Rus, "LIO-SAM:
Tightly-coupled Lidar Inertial Odometry via Smoothing and Mapping," IROS
2020; github.com/TixiaoShan/LIO-SAM.

[4] J. Chen et al., "LuSNAR: A Lunar Segmentation, Navigation and
Reconstruction Dataset based on Multi-sensor for Autonomous Exploration,"
arXiv:2407.06512v3, 2024. Benchmarks ORB-SLAM3 stereo, VINS-Mono,
VINS-Fusion, A-LOAM, LeGO-LOAM, FAST-LIO on lunar-analog data derived from
Chang'e-2 (50 m/pix) and Tianwen-1 (3.5 m/pix) DEMs.

[5] W. Xu, Y. Cai, D. He, J. Lin, F. Zhang, "FAST-LIO2: Fast Direct LiDAR-
Inertial Odometry," github.com/hku-mars/FAST_LIO. License GPL-2.0.

[6] engcang/FAST-LIO-SAM and engcang/FAST-LIO-SAM-QN: pose-graph wrappers
that add loop closure to FAST-LIO2.

[7] C. Campos, R. Elvira, J. J. Gómez Rodríguez, J. M. M. Montiel, J. D.
Tardós, "ORB-SLAM3: An Accurate Open-Source Library for Visual, Visual-
Inertial and Multi-Map SLAM," github.com/UZ-SLAMLab/ORB_SLAM3. Last upstream
release v1.0, 2021-12-22. License GPL-3.0.

[8] M. Labbé and F. Michaud, "Memory Management for Real-Time Appearance-
Based Loop Closure Detection," arXiv:2407.15890, 2024. Describes
hierarchical working/long-term memory and DBoW2-style vocabulary.

[9] L. Meyer, M. Smíšek, A. Fontán Villacampa et al., "The MADMAX data set
for visual-inertial rover navigation on Mars," J. Field Robotics, 2021.
Morocco analog dataset; ORB-SLAM2 and VINS-Mono baselines.

[10] W. Hess, D. Kohler, H. Rapp, D. Andor, "Real-Time Loop Closure in 2D
LIDAR SLAM," ICRA 2016; github.com/ros2/cartographer_ros. License Apache 2.0.

[11] ROS Index, cartographer_ros package page, Jazzy release 2025-05-20.
index.ros.org/p/cartographer_ros/, ROS status "MAINTAINED."

[12] ROS 2 Documentation, "Jazzy Jalisco,"
docs.ros.org/en/jazzy/Releases.html. LTS release; support window through
May 2029.

[13] ROS Index, slam_toolbox Jazzy release tracking: Jazzy sync 2025-04-15;
2.8.4 2026-01-24. index.ros.org/p/slam_toolbox/.

[14] TixiaoShan/LIO-SAM Issue #549, "Compatibility with ROS2 Jazzy?" opened
2025-07-08, open as of 2026-04.

[15] Community ROS 2 wrappers for FAST-LIO2 targeting Humble:
Taeyoung96/FAST_LIO_ROS2, Ericsii/FAST_LIO_ROS2, Lee-JaeWon/FAST_LIO_ROS2,
MIT-SPARK/spark-fast-lio. hku-mars/FAST_LIO Issue #234.

[16] Mechazo11/ros2_orb_slam3 (ROS 2 Humble main, Jazzy branch);
suchetanrs/ORB-SLAM3-ROS2-Docker; zang09/ORB_SLAM3_ROS2.

[17] H. Jiang et al., "GPS-Denied LiDAR-Based SLAM: A Survey," IET
Cyber-Systems and Robotics, 2025. (Accessed via search metadata only;
HTTP 403 on direct fetch. TODO(v1.1): re-verify before iSpaRo submission.)

[18] S. Hu et al., "Comprehensive Performance Evaluation between Visual
SLAM and LiDAR SLAM for Mobile Robots: Theories and Experiments," MDPI
Applied Sciences 14(9):3945, 2024. (Accessed via search metadata only;
HTTP 403 on direct fetch. TODO(v1.1): re-verify before iSpaRo submission.)

[19] ISPRS Archives, "Visual-LiDAR Odometry for Planetary Rover with Plane
Constraints," XLVIII-G-2025. Notes that planetary surfaces cause "low
texture, significant illumination variations, feature extraction errors,
inaccurate depth estimation, and unreliable terrain mapping."
