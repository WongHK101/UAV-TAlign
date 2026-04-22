# PRCV Method Draft

## Purpose

This note turns the locally verified `UAV-TAlign` implementation into paper-ready method prose.
It is meant to help the writing pass stay aligned with the actual code path in:

- `E:\UAV-TAlign\estimate_band_homographies.py`
- `E:\UAV-TAlign\utils\minima_match_utils.py`
- `E:\UAV-TAlign\utils\rectification_utils.py`
- `E:\UAV-TAlign\run_prcv_main_experiment.py`

The safest paper-level positioning remains:

- `UAV-TAlign` is a scene-level RGB-thermal registration pipeline
- it is built on top of strong off-the-shelf multimodal pairwise matching
- its main supported gains come from robust aggregation and QA-aware scene acceptance
- deterministic selection should be written as a reproducible default operating policy

## Method Draft

### 4. Method

#### 4.1 Problem Formulation

We study RGB-thermal registration at the scene level rather than as an isolated pairwise matching
task. For each scene, the input is a set of paired RGB and thermal UAV frames
`S = {(I_i^R, I_i^T)}_{i=1}^N`, where viewpoint variation, cross-resolution sensing, thermal
appearance changes, and day/night conditions make individual frame estimates uneven in quality.
The goal is to recover a thermal-to-RGB homography that remains usable at the scene level, or to
reject the scene when the evidence is not reliable enough.

This formulation differs from treating registration as a single best-pair problem. In our setting,
many scenes already contain some usable pairwise correspondences, but the central challenge is to
convert those imperfect frame-level estimates into a transform that is geometrically stable,
internally consistent, and acceptable under a reliability-aware QA criterion.

#### 4.2 Pairwise Matching Backbone and Candidate Scheduling

`UAV-TAlign` builds on a strong off-the-shelf multimodal matcher rather than introducing a new
matching backbone. In the current PRCV pipeline, the default backend is the MINIMA family with the
RoMa branch, while the rest of the pipeline remains agnostic to the exact pairwise matcher.

At the scene level, the system does not assume that all frames should be treated equally from the
start. It first constructs a candidate-count schedule that expands progressively with scene size.
The implementation uses a ratio-based schedule with a base candidate count, an initial ratio, a
ratio step, and a maximum ratio; if needed, it can expand to all frames. For small scenes, the
pipeline directly evaluates all available frames. This scheduling policy allows the system to stop
early when the scene is already stable, while still escalating to broader evidence when the current
subset is not sufficient.

Within each candidate stage, representative frames are selected using deterministic evenly
distributed sampling by default. A random-selection variant exists for sensitivity analysis, but the
default paper-facing interpretation should be reproducibility rather than superiority: deterministic
selection is used to reduce seed-dependent drift and to preserve more uniform scene coverage.
Optionally, frames can also be filtered by a minimum structure score so that texture-poor RGB
frames do not dominate the evaluation subset used for scene-level QA.

#### 4.3 Frame-Level Geometry Estimation and Acceptance

For each selected frame pair, the matcher produces cross-modal correspondences that are filtered
into a frame-level homography estimate. The current implementation evaluates each frame using
standard geometric statistics, including the number of matches, the number of inliers, inlier
ratio, reprojection error, and spatial coverage. A frame enters the global candidate pool only when
it passes a minimum-quality gate on these statistics.

Beyond a binary accept/reject decision, the pipeline assigns each accepted frame a quality score so
that better-supported homographies receive more influence during scene aggregation. The score is a
weighted combination of inlier ratio, spatial coverage, reprojection quality, matcher confidence,
and inlier count. This keeps the scene-level estimate from being dominated by weak-but-technically-
accepted frames.

The implementation also retains a lightweight baseline transform `H0` for later QA comparison. When
metadata contain usable alignment priors, `H0` is built from those offsets and scale adjustments;
otherwise the pipeline falls back to a naive resize-based initialization. This distinction matters
later because the QA logic explicitly treats a naive baseline as weak evidence rather than as a
strong geometric reference.

#### 4.4 Scene-Level Robust Aggregation

Once enough frame-level homographies have been accepted, `UAV-TAlign` aggregates them into a
scene-level transform. The default aggregation mode is robust weighted aggregation. In the
implementation, homographies are first mapped into parameter space, centered with a median
reference, and filtered by a median-absolute-deviation rule to suppress outliers before weighted
averaging. The retained homographies are then combined using the previously defined frame quality
scores. This design directly targets the failure mode in which a small number of unstable but
plausible frame estimates would otherwise skew the scene-level result.

The pipeline records stability diagnostics around the aggregate transform, including the dispersion
of each accepted homography relative to the aggregate and the ratio of robustly rejected frame-level
estimates. These diagnostics are later used both for scene-level stopping decisions and for the
baseline-aware QA stage.

An optional residual refinement module is also implemented. When enabled, it refines the aggregated
transform on a reduced alignment grid through an optimization backend. However, the core PRCV method
line should remain centered on candidate scheduling, robust aggregation, and QA-aware scene
acceptance, since these are the parts with the clearest empirical support in the current results.

#### 4.5 QA-Aware Scene Acceptance

The final decision is not based only on whether some frames matched successfully. Instead,
`UAV-TAlign` evaluates the optimized scene-level transform against a label-free QA summary computed
on representative frames. The current summary uses cross-modal proxy signals such as edge-overlap
improvement, gradient-NCC improvement, the ratio of improved frames, and the count of severe
relative outliers. It also retains scene-level match and stability statistics such as accepted-frame
ratio, mean inlier ratio, mean reprojection error, spatial coverage, dispersion relative to the
aggregate transform, and the robust reject ratio.

The implementation keeps the original hard gate as `legacy_pass`, but the formal PRCV decision uses
a baseline-aware three-way status: `pass`, `pass_with_warning`, or `fail`. The warning path is
intentionally narrow. It is only available when the baseline transform is weak, the modality gap is
high, the accepted-frame statistics remain strong, the aggregated homography is stable, the
baseline-relative severe-outlier ratio stays within limits, and the transform still improves
gradient-based alignment beyond configured floors. This prevents the pipeline from mistaking weak
scene evidence for a reliable success while still avoiding over-penalizing scenes whose naive
baseline is intrinsically poor.

The canonical scene decision then combines two requirements: enough accepted frames and an
acceptable scene-level QA status. In the current formal configuration, `qa_status` is the default
scene-pass policy. This is exactly the point of the method: scene-level reliability is treated as a
first-class criterion rather than an afterthought appended to pairwise matching.

#### 4.6 Practical Execution and Isolation

The formal experiment runner packages this pipeline as `uav_talign_full` and enforces runtime
isolation between the raw dataset root, the MINIMA source tree, and the experiment output root.
Prepared intermediate data, scene outputs, summaries, and diagnostics are written under the
experiment root only. This detail is mostly an implementation safeguard, but it is still worth
mentioning briefly in the paper or appendix because it supports reproducible formal runs without
polluting the raw dataset or algorithm directories.

## Code-Grounded Implementation Facts

These facts are directly supported by the current local code and are safe to use when refining the
paper draft.

- Candidate expansion is implemented through `build_candidate_pool_schedule(...)`.
- The default representative-frame policy is `selection_mode=\"even\"`; the random variant is
  implemented with an explicit seed.
- Frame acceptance uses minimum requirements on:
  - number of matches
  - inlier ratio
  - reprojection error
  - spatial coverage
- Frame quality scoring currently combines:
  - inlier ratio
  - coverage
  - reprojection term
  - confidence mean
  - inlier count
- Robust aggregation uses median-centered MAD filtering plus weighted averaging in homography
  parameter space.
- Formal scene acceptance defaults to `scene_pass_policy=\"qa_status\"`.
- The warning path is not a generic soft pass:
  - it only opens under weak baseline plus high modality gap
  - it still requires acceptable match quality, stability, outlier control, and gradient
    improvement

## Writing Notes

- Do not write this section as if `UAV-TAlign` were a new matcher architecture.
- Keep the strongest emphasis on scene-level reliability, robust aggregation, and QA-aware scene
  acceptance.
- Deterministic selection should appear as a reproducible default operating policy, not as the main
  headline gain.
- If page pressure is high, compress Section 4.6 first rather than weakening Sections 4.4 and 4.5.
