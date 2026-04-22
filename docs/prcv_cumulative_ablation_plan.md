# PRCV Cumulative Ablation Plan

Status note (2026-04-22):

- This is now a historical planning document.
- `A1-A3` have already been completed.
- The random-selection follow-up has also been completed as a multi-seed `S1` supplement.
- For the current paper-facing interpretation, use:
  - `docs/prcv_ablation_results_final.md`
  - `review_artifacts/prcv_s1_multiseed_structuring_20260422_044924/`

## Purpose

This note freezes the **minimum cumulative ablation package** for the PRCV paper after the first-wave
baseline results became stable.

The goal is not to reopen baseline expansion. The goal is to answer the reviewer question:

- are the scene-level gains from `UAV-TAlign` more than a thin wrapper around raw pairwise matching?

## Current Local Facts

1. Pairwise baselines are now complete:
   - `raw MINIMA`: `500/500 ok`
   - `RoMa`: `500/500 ok`
   - `LoFTR`: `499/500 ok`
   - `XoFTR-640`: `494/500 ok`
   - `AKAZE`: `479/500 ok`
   - `SIFT`: `457/500 ok`

2. The current full scene-level result is already fixed:
   - `UAV-TAlign full pipeline`: `15 scenes`, `7 ok`, `8 canonical_fail`

3. A crucial implementation fact:
   - under the current default configuration, `minima_full_if_frames_le=300`
   - every scene in `UAV-TAlign-1K` is smaller than that threshold
   - so the current formal run uses `candidate_policy = all_small_dataset`
   - in other words, the current formal result does **not** exercise adaptive candidate expansion on this dataset

4. Therefore the cumulative ablation package must explicitly distinguish:
   - the **formal full-pipeline result** used for the main paper tables
   - the **forced-adaptive ablation mode** used only for method dissection

## Newly Exposed Ablation Controls

The current local code now exposes the minimum knobs needed for scene-level cumulative ablations:

- `--uav_talign_frame_selection_mode {even,random}`
- `--uav_talign_aggregation_mode {robust_weighted,single_best}`
- `--uav_talign_scene_pass_policy {qa_status,legacy_pass,accepted_only}`
- `--uav_talign_initial_candidate_ratio`
- `--uav_talign_candidate_ratio_step`
- `--uav_talign_max_candidate_ratio`
- `--uav_talign_use_all_if_needed`
- `--uav_talign_full_if_frames_le`
- `--uav_talign_use_metadata_h0`
- `--uav_talign_warning_min_accepted_ratio`
- `--uav_talign_warning_max_severe_outlier_ratio`
- `--uav_talign_warning_max_severe_outlier_count`
- `--uav_talign_stability_warn_mean_px`
- `--uav_talign_stability_max_reject_ratio`
- `--uav_talign_max_severe_outliers`

These are exposed through:

- `run_prcv_main_experiment.py`
- `estimate_band_homographies.py`

## Recommended Scene Subset

Use the scene subset already anticipated in the paper plan:

- `01`
- `02`
- `03`
- `04`
- `07`
- `08`
- `13`
- `14`

Rationale:

- includes paired controls `01 vs 02` and `03 vs 04`
- includes both pass and fail outcomes
- includes day / night / lowlight
- includes grayscale and pseudocolor
- keeps the ablation budget bounded before any all-scene expansion

Suggested `--scene_names` value:

```text
01_day_grayscale_wide_substation_power_lines_50,02_day_grayscale_zoom_substation_power_lines_50,03_night_grayscale_wide_substation_power_lines_45,04_night_grayscale_zoom_substation_power_lines_45,07_day_grayscale_transmission_tower_102,08_night_grayscale_urban_22,13_lowlight_pseudocolor_road_21,14_lowlight_pseudocolor_transmission_tower_18
```

## Minimum Cumulative Ablation Matrix

### A0. Raw Pairwise Reference

Use the already completed `raw MINIMA` pairwise result as the reference line.

Do **not** rerun this unless the evaluation code changes materially.

Role in the paper:

- reference matcher availability
- reference pairwise homography success
- not scene-level

### A1. Candidate Strategy Only

Intent:

- add deterministic scene-level candidate handling
- keep final transform simple
- keep scene pass criterion simple

Recommended overrides:

- `--uav_talign_frame_selection_mode even`
- `--uav_talign_aggregation_mode single_best`
- `--uav_talign_scene_pass_policy accepted_only`
- `--uav_talign_full_if_frames_le 0`
- `--uav_talign_initial_candidate_ratio 0.15`
- `--uav_talign_candidate_ratio_step 0.15`
- `--uav_talign_max_candidate_ratio 0.50`
- `--uav_talign_use_all_if_needed true`

Interpretation:

- this is the first scene-level wrapper over raw pairwise matching
- it answers whether deterministic/adaptive candidate management helps before robust aggregation and QA-aware gating

### A2. Candidate Strategy + Robust Aggregation

Intent:

- isolate the gain from robust homography aggregation

Recommended overrides relative to A1:

- `--uav_talign_aggregation_mode robust_weighted`
- keep `--uav_talign_scene_pass_policy accepted_only`

Interpretation:

- A2 minus A1 estimates the contribution of robust aggregation

### A3. Candidate Strategy + Robust Aggregation + QA-Aware Decision

Intent:

- turn on the scene-level acceptance logic that matches the paper narrative

Recommended overrides relative to A2:

- `--uav_talign_scene_pass_policy qa_status`

Keep the current QA/stability thresholds:

- `--uav_talign_warning_min_accepted_ratio 0.80`
- `--uav_talign_warning_max_severe_outlier_ratio 0.10`
- `--uav_talign_warning_max_severe_outlier_count 1`
- `--uav_talign_stability_warn_mean_px 25.0`
- `--uav_talign_stability_max_reject_ratio 0.25`
- `--uav_talign_max_severe_outliers 0`

Interpretation:

- A3 minus A2 estimates the contribution of baseline-aware QA / acceptance

### A4. Formal Full Pipeline Reference

Use the already completed formal result as the final reference:

- full 15-scene result
- default `all_small_dataset` behavior
- canonical scene pass policy

Role in the paper:

- this remains the main reported full-pipeline number
- do not replace it with forced-adaptive ablation mode

## Optional Supplemental Ablation

Only run this if the cumulative main line is not clear enough:

### S1. Deterministic vs Random Candidate Selection

Same settings as A1/A2/A3, but compare:

- `--uav_talign_frame_selection_mode even`
- `--uav_talign_frame_selection_mode random`

Use the same seed and the same 8-scene subset.

This is a method-detail supplement, not a first-priority experiment.

## Recommended Execution Order

1. Do **not** rerun any pairwise baselines.
2. Do **not** expand the baseline list.
3. Finish P0 paper structuring first.
4. If the current result organization is stable, run:
   - A1
   - A2
   - A3
5. Compare A3 against the already completed formal full-pipeline result A4.
6. Only then decide whether S1 is necessary.

## Reporting Guidance

When writing the paper, explicitly distinguish:

- **formal full-pipeline result**
  - current default runtime policy
  - main paper number

- **forced-adaptive cumulative ablation**
  - targeted method dissection on a scene subset
  - not a replacement for the full-dataset headline result

This distinction is necessary because the current default formal run on `UAV-TAlign-1K`
falls into `all_small_dataset`, so candidate expansion is not naturally activated there.

## Suggested Command Skeleton

The exact output roots should remain isolated per ablation stage. Example skeleton:

```text
python run_prcv_main_experiment.py \
  --methods uav_talign_full \
  --scene_names <8-scene subset> \
  --output_root <ablation_root> \
  --device cuda:0 \
  --seed 0 \
  --uav_talign_frame_selection_mode even \
  --uav_talign_aggregation_mode <single_best|robust_weighted> \
  --uav_talign_scene_pass_policy <accepted_only|qa_status> \
  --uav_talign_full_if_frames_le 0 \
  --uav_talign_initial_candidate_ratio 0.15 \
  --uav_talign_candidate_ratio_step 0.15 \
  --uav_talign_max_candidate_ratio 0.50 \
  --uav_talign_use_all_if_needed true
```

## Immediate Next Step

Before launching A1-A3, freeze:

- final scene subset
- output-root naming
- comparison table schema
- which metric defines the ablation headline:
  - scene pass count
  - accepted ratio
  - proxy deltas
  - runtime

This avoids rerunning the ablations only to discover the summary format was underspecified.
