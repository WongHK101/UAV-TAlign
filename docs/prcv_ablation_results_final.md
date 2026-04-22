# PRCV Ablation Results Final

## Purpose

This note condenses the completed cumulative ablation wave into a paper-facing summary that can be
quoted in drafting, GPT review, and result-table polishing without reopening the experiment logic.

The intended high-level interpretation is:

- strong pairwise multimodal matching is already available off the shelf
- the main contribution of `UAV-TAlign` is scene-level reliability rather than pairwise feasibility
- the most clearly supported pipeline components are robust aggregation and QA-aware scene decision

## Source Artifacts

Completed remote output roots:

- `A1`: `/home/user2/whk/UAV-TAlign/outputs/prcv_ablation_A1_candidate_only_20260422_020224`
- `A2`: `/home/user2/whk/UAV-TAlign/outputs/prcv_ablation_A2_candidate_plus_aggregation_20260422_020224`
- `A3`: `/home/user2/whk/UAV-TAlign/outputs/prcv_ablation_A3_candidate_plus_aggregation_plus_qa_20260422_020224`
- `S1 (seed 0)`: `/home/user2/whk/UAV-TAlign/outputs/prcv_ablation_S1_random_selection_20260422_020224`
- `S1` multi-seed supplement:
  - `seed 1`: `/home/user2/whk/UAV-TAlign/outputs/prcv_ablation_S1_random_selection_seed1_20260422_035943`
  - `seed 2`: `/home/user2/whk/UAV-TAlign/outputs/prcv_ablation_S1_random_selection_seed2_20260422_035943`
  - `seed 3`: `/home/user2/whk/UAV-TAlign/outputs/prcv_ablation_S1_random_selection_seed3_20260422_035943`

Reference results already frozen before this wave:

- `A0` pairwise baseline reference:
  - `raw MINIMA`: `500/500`
- `A4-subset`:
  - 8-scene subset slice of the completed formal run
- `A4-all`:
  - 15-scene full formal headline result

## Stable Paper-Level Reading

The completed ablation package supports the following paper-facing narrative:

1. `raw MINIMA` is already a very strong pairwise backend, so the full paper should not be framed as
   "making matching possible."
2. The scene-level improvement space lies in selecting usable candidates, aggregating homographies
   robustly, and filtering unreliable scenes through QA-aware decision logic.
3. The strongest empirical evidence in the current ablation line supports:
   - robust aggregation
   - QA-aware scene-level decision
4. The fixed-subset `A3` result aligns closely with the formal `A4-subset` result, which means the
   ablation runner is capturing the same decision regime that matters for the formal pipeline.

## Headline Tables

### Pairwise Reference

| Stage | Eval Unit | Method | OK / N | Mean Inlier Ratio | Mean Coverage | Mean Reproj Error | Mean Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | 500 pairs | raw MINIMA | 500/500 | 0.378 | 0.996 | 1.707 | 1.859 |

### Main Scene-Level Ablation Line

| Stage | Scene Set | Candidate Policy | Aggregation | Scene Pass Policy | Pass / N | Pass Rate (%) | Mean Accepted Ratio (%) | Mean Delta Edge F1 | Mean Delta Grad NCC | Mean Reject Ratio (%) | Mean Severe-Outlier Ratio (%) | Mean Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 8 scenes | forced adaptive | single_best | accepted_only | 8/8 | 100.0 | 77.428 | 0.124071 | 0.126086 | 18.063 | 10.417 | 61.561 |
| A2 | 8 scenes | forced adaptive | robust_weighted | accepted_only | 8/8 | 100.0 | 77.428 | 0.145186 | 0.148185 | 18.063 | 4.167 | 60.666 |
| A3 | 8 scenes | forced adaptive | robust_weighted | qa_status | 5/8 | 62.5 | 77.234 | 0.146515 | 0.148964 | 19.049 | 4.167 | 88.234 |
| S1 (seed 0) | 8 scenes | forced adaptive, random selection | robust_weighted | qa_status | 6/8 | 75.0 | 80.854 | 0.158431 | 0.169214 | 19.408 | 3.125 | 89.513 |
| A4-subset | 8 scenes | formal default slice | robust_weighted | qa_status | 5/8 | 62.5 | 80.387 | 0.146872 | 0.148504 | 20.891 | 4.167 | 106.239 |
| A4-all | 15 scenes | formal default | robust_weighted | qa_status | 7/15 | 46.7 | 64.522 | 0.132167 | 0.119804 | 17.120 | 6.667 | 89.807 |

### Random-Selection Multi-Seed Supplement

| Variant | Pass / N | Pass Rate (%) | Note |
| --- | --- | --- | --- |
| S1 (seed 0) | 6/8 | 75.0 | Original single-seed random-selection run. |
| S1 (seed 1) | 4/8 | 50.0 | Supplement run. |
| S1 (seed 2) | 7/8 | 87.5 | Supplement run. |
| S1 (seed 3) | 5/8 | 62.5 | Supplement run. |
| Random-selection range | 4-7/8 | 50.0-87.5 | Seed-sensitive spread on the same fixed subset. |

## Main Takeaways

### 1. Robust Aggregation Is Clearly Supported

`A2` keeps the same `8/8` accepted-only scene survivability as `A1`, but improves the quality side
substantially:

- mean delta edge F1:
  - `0.124071 -> 0.145186`
- mean delta grad NCC:
  - `0.126086 -> 0.148185`
- mean severe-outlier ratio:
  - `10.417% -> 4.167%`

This is a strong paper-facing result because it shows that robust aggregation is not merely
relabeling outcomes; it is materially improving alignment quality and suppressing severe outliers.

### 2. QA-Aware Scene Decision Matches the Formal Regime

`A3` is the first ablation stage whose scene-pass semantics match the full paper story. Its pass
policy is `qa_status`, and its fixed-subset result is almost numerically identical to the subset
slice of the completed formal run:

- scene pass:
  - `A3 = 5/8`
  - `A4-subset = 5/8`
- mean delta edge F1:
  - `A3 = 0.146515`
  - `A4-subset = 0.146872`
- mean delta grad NCC:
  - `A3 = 0.148964`
  - `A4-subset = 0.148504`
- mean severe-outlier ratio:
  - `A3 = 4.167%`
  - `A4-subset = 4.167%`

This close alignment is valuable because it lets the paper use `A1-A3` as a clean method-dissection
story without losing contact with the formal headline pipeline behavior.

### 3. The Formal Bottleneck Is Reliability, Not Raw Pairwise Availability

The broader result package is now internally consistent:

- pairwise baselines are already very strong:
  - `raw MINIMA 500/500`
  - `RoMa 500/500`
  - `LoFTR 499/500`
  - `XoFTR-640 494/500`
- the full scene-level pipeline still reaches:
  - `7/15` canonical scene passes

The paper should therefore emphasize that the remaining challenge in UAV RGB-thermal registration
is not "can a matcher produce correspondences at all," but "can the system deliver a scene-level
alignment that remains usable after QA-aware reliability checks."

## Sensitivity Note on Frame Selection

The random-selection supplement is now complete. Across the same fixed 8-scene subset, random
selection yields:

- `seed 0`: `6/8`
- `seed 1`: `4/8`
- `seed 2`: `7/8`
- `seed 3`: `5/8`

This `4/8 -> 7/8` spread confirms that random selection is clearly seed-sensitive on the current
subset.

Observed scene-level stability under random selection:

- always fail:
  - `02`
- always pass:
  - `04`, `07`, `13`, `14`
- seed-sensitive:
  - `01` passes in `1/4` random seeds
  - `03` passes in `2/4` random seeds
  - `08` passes in `3/4` random seeds

Current safest interpretation:

- deterministic-even selection remains the reproducible default for the paper
- the earlier single-seed `S1 = 6/8` should **not** be treated as a stable superiority signal over
  deterministic `A3 = 5/8`
- the ablation evidence does **not** justify a hard claim that deterministic-even selection is
  universally stronger than random selection
- the more defensible paper message is that deterministic-even selection provides a stable operating
  policy while robust aggregation and QA-aware decision remain the more strongly supported sources
  of gain

## Writing Guidance

The strongest safe wording is to emphasize:

- `UAV-TAlign` builds on a strong pairwise multimodal backbone rather than replacing it
- robust aggregation improves scene-level alignment quality and suppresses outliers
- QA-aware acceptance brings the ablation line into close agreement with the formal full-pipeline
  decision regime
- the paper's main contribution is reliable scene-level RGB-thermal registration under realistic
  UAV conditions

Avoid centering the narrative on:

- deterministic frame selection as the main proven source of gain
- any implication that the work is mainly about making pairwise matching feasible
