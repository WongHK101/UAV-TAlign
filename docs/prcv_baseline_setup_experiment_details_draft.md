# PRCV Baseline Setup / Experiment Details Draft

## Purpose

This note turns the frozen first-wave PRCV experimental setup into paper-facing prose. It is meant
to support the `Baselines`, `Implementation Details`, and `Experiment Setup` parts of the paper
without overstating how the current code was run.

The main local sources are:

- `E:\UAV-TAlign\run_prcv_main_experiment.py`
- `E:\UAV-TAlign\utils\baseline_backends.py`
- `E:\UAV-TAlign\utils\minima_bridge.py`
- `E:\UAV-TAlign\docs\prcv_main_table_draft.md`
- `E:\UAV-TAlign\docs\README-paper.md`

The writing constraints are:

- keep the off-the-shelf setting explicit
- keep method naming frozen
- do not casually rewrite local wrappers as untouched official-script runs

## Baseline Setup Draft

### 6.1 Baselines

We evaluate both classical and learning-based baselines under an explicit off-the-shelf setting.
All learning-based methods use public pretrained weights or public pretrained model interfaces, and
none of the baselines are retrained or fine-tuned on `UAV-TAlign-1K`. This choice keeps the
comparison focused on practical deployability rather than dataset-specific adaptation.

The classical baselines are `SIFT + RANSAC` and `AKAZE + RANSAC`. They are implemented through the
OpenCV detector-and-matcher stack with standard ratio-test filtering, followed by a shared
homography estimation backend. These methods provide the classical sparse-feature reference point
for the paper.

The deep pairwise baselines are `Kornia LoFTR (pretrained="outdoor")`, `official pretrained RoMa
via local wrapper`, and `official pretrained XoFTR-640 via local wrapper`. `LoFTR` is run through
the public Kornia model API rather than an untouched standalone repository script, and the formal
full-run result uses a bounded resize-aware inference setting. `RoMa` is invoked through a local
wrapper around the public pretrained outdoor model. `XoFTR` is run with the official 640-resolution
checkpoint family as the frozen main-table setting, again through a local wrapper so that it fits
the unified experiment runner.

We also include `raw MINIMA` as a source-method baseline. In the current PRCV setup, this baseline
uses the MINIMA RoMa branch in its direct pairwise form, without the scene-level candidate
selection, robust multi-frame aggregation, or QA-aware decision logic introduced by `UAV-TAlign`.
This comparison is especially important because it distinguishes the full pipeline from a mere
wrapper around an already-strong pairwise matcher.

Finally, the method under study is reported as `UAV-TAlign full pipeline`. Unlike the pairwise
baselines, it is evaluated at the scene level rather than the individual-pair level. The key point
is therefore not just whether it can produce correspondences, but whether it can deliver a
scene-level alignment that remains acceptable after aggregation and QA-aware reliability control.

## Experiment Details Draft

### 6.2 Implementation Details

All first-wave PRCV experiments are run through a unified formal runner so that pairwise baselines
share the same dataset split, the same scene and pair identity definitions, and the same downstream
geometric fitting interface where applicable. The runner also enforces output-root isolation so that
raw dataset directories and algorithm source trees are treated as read-only inputs during formal
evaluation.

For the pairwise methods, the common downstream step is homography fitting from the predicted
correspondences. After each matcher returns point pairs and optional confidence values, the
evaluation script estimates a homography with a shared RANSAC-style backend and then records a
unified status code such as `ok`, `fit_failed`, `insufficient_matches`, `no_matches`, or `error`.
This unified post-processing is important because it makes the pairwise baseline table comparable at
the level of usable registration outcomes rather than raw matcher outputs alone.

The current homography fitting backend uses the same configuration across pairwise baselines:

- robust fitting method: `USAC-MAGSAC`
- reprojection threshold: `3.0`
- confidence: `0.999`
- maximum iterations: `10000`
- spatial coverage grid: `4 x 4`

This means that the main pairwise comparison is not confounded by each method using a separate
geometric fitting script.

### 6.3 Frozen Baseline Choices

The current frozen main-table baseline choices are as follows.

`raw MINIMA` uses the MINIMA RoMa backend with the `minima_roma` checkpoint family and the
large/full RoMa branch. `official pretrained RoMa via local wrapper` uses the public outdoor RoMa
model. `official pretrained XoFTR-640 via local wrapper` uses the 640-resolution XoFTR checkpoint
family as the default main-table XoFTR setting. `Kornia LoFTR (pretrained="outdoor")` uses the
public pretrained outdoor model from Kornia.

For writing, these names should remain fixed. In particular:

- write `Kornia LoFTR (pretrained="outdoor")`, not `official LoFTR repo`
- write `official pretrained RoMa via local wrapper`, not `untouched official RoMa script`
- write `official pretrained XoFTR-640 via local wrapper`, not `official XoFTR repo`

This wording is stricter than casual implementation descriptions, but it is the safest accurate
description of the current code path.

### 6.4 Resize-Aware and Wrapper Details

The formal `LoFTR` result should be described explicitly as a resize-aware inference setting. In
the current full-run configuration, the longest image dimension used for matching is limited to
`1600`, and automatic mixed precision is disabled. This is a deployment-oriented memory-control
choice, not a training modification or a special adaptation on `UAV-TAlign-1K`.

The current `XoFTR` and `raw MINIMA` paths also pass through a local bridge that normalizes the
input images and resizes them for matching when necessary. In the current bridge implementation,
the matching-side maximum dimension is also capped at `1600`, and grayscale or single-channel
inputs are converted to uint8 RGB-like images so that they can be processed by the relevant
pretrained pipelines. These details should be framed as practical inference wrappers rather than as
algorithmic modifications to the underlying models.

For `RoMa`, the local wrapper uses the public outdoor model and samples dense correspondences from
the predicted warp field before the shared homography fitting stage. Again, the safest writing
position is that this is an off-the-shelf pretrained model evaluated through a local inference
wrapper inside a unified experiment pipeline.

### 6.5 Reproducibility and Runtime Policy

The formal runner stores both a per-method result stream and a top-level experiment configuration
file. For scene-level `UAV-TAlign`, it additionally records accepted-frame counts, attempted-frame
counts, QA status, and canonical scene-pass outcomes. This design supports later result aggregation
and provenance checks without mixing scene-level pipeline outputs into the raw dataset or source
directories.

When randomization is involved, the runner exposes an explicit seed and initializes Python, NumPy,
and torch random states accordingly. In the main formal paper line, however, deterministic-even
selection remains the default operating policy, while random selection is reserved for the completed
sensitivity supplement rather than for the main headline configuration.

## Code-Grounded Facts

The following statements are directly grounded in the current implementation and are safe to use in
the paper draft.

- The default first-wave formal method set is:
  - `sift_ransac`
  - `akaze_ransac`
  - `loftr_outdoor`
  - `roma_outdoor`
  - `xoftr_official`
  - `raw_minima`
  - `uav_talign_full`
- Pairwise baseline creation is centralized in `create_pairwise_matcher(...)`.
- `SIFT` and `AKAZE` use OpenCV detectors plus BFMatcher ratio filtering.
- `LoFTR` is instantiated through `kornia.feature.LoFTR(pretrained="outdoor")`.
- `RoMa` is instantiated through the public outdoor model exposed by the vendored `romatch` path.
- `XoFTR` and `raw MINIMA` both pass through `MinimaMatcherBridge(...)`.
- `raw MINIMA` defaults to the RoMa branch in the current formal main-table setup.
- Pairwise homography estimation is shared through `estimate_homography_ransac(...)`.
- Pairwise statuses are normalized into:
  - `ok`
  - `fit_failed`
  - `insufficient_matches`
  - `no_matches`
  - `error`
- The formal runner records:
  - `experiment_config.json`
  - `main_experiment_summary.json`
  - per-method result files under isolated output roots

## Writing Notes

- Keep the phrase `off-the-shelf` visible in this section; it is one of the strongest stabilizing
  constraints in the current paper.
- Emphasize that the baselines are unified at the level of downstream geometric fitting and failure
  handling where possible.
- Avoid describing the local wrappers as if they were untouched official evaluation scripts.
- Do not over-explain every wrapper detail in the main text; move lower-level path and environment
  notes to appendix or release documentation if needed.
- The main paper should use this section to make the comparison look disciplined and reproducible,
  not to invite side arguments about packaging details.
