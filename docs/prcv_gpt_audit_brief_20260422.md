# PRCV GPT Audit Brief (2026-04-22)

## Review Goal

This brief is for an external GPT review of the current PRCV paper package. The request is not to
re-litigate basic engineering choices, but to help sharpen:

- the strongest defensible paper narrative
- whether any small follow-up experiment is still worth running
- the most advantageous writing strategy for abstract, contributions, results, and discussion

The preferred review posture is:

- foreground strengths first
- keep claim boundaries tight where needed
- avoid needlessly highlighting implementation trivia that does not change the scientific story

## Stable Result Snapshot

### Pairwise Baselines

All first-wave pairwise baselines now have usable full-run results on `500` paired registrations.

| Method | OK / N | OK Rate (%) | Mean Inlier Ratio | Mean Coverage | Mean Reproj Error | Mean Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- |
| raw MINIMA | 500/500 | 100.0 | 0.378 | 0.996 | 1.707 | 1.859 |
| official pretrained RoMa via local wrapper | 500/500 | 100.0 | 0.400 | 0.982 | 1.672 | 1.077 |
| Kornia LoFTR (pretrained="outdoor") | 499/500 | 99.8 | 0.096 | 0.919 | 1.411 | 0.549 |
| official pretrained XoFTR-640 via local wrapper | 494/500 | 98.8 | 0.151 | 0.951 | 1.610 | 1.204 |
| AKAZE + RANSAC | 479/500 | 95.8 | 0.177 | 0.646 | 0.393 | 2.368 |
| SIFT + RANSAC | 457/500 | 91.4 | 0.240 | 0.599 | 0.260 | 4.605 |

### Full Pipeline Formal Headline

Current full-pipeline headline result:

- `UAV-TAlign full pipeline`
- `7/15` canonical scene passes
- pass rate `46.7%`
- mean accepted ratio `64.522%`
- mean delta edge F1 `0.132167`
- mean delta grad NCC `0.119804`
- mean robust reject ratio `17.120%`
- mean severe-outlier ratio `6.667%`
- mean runtime `89.807 s`

### Proxy / Protocol Signal

The strongest currently stored scene-level fail-side signal remains:

- `baseline_relative_qa_outliers`
  - present in `8/8` failing scenes
  - present in `0/7` passing scenes

The main interpretation already supported by local results is:

- strong off-the-shelf pairwise matchers now make correspondence generation broadly available
- the differentiating problem is scene-level reliability after aggregation and QA-aware filtering

## Completed Cumulative Ablation Package

Fixed 8-scene subset:

- `01`
- `02`
- `03`
- `04`
- `07`
- `08`
- `13`
- `14`

| Stage | Candidate Policy | Aggregation | Scene Pass Policy | Pass / N | Pass Rate (%) | Mean Accepted Ratio (%) | Mean Delta Edge F1 | Mean Delta Grad NCC | Mean Severe-Outlier Ratio (%) | Mean Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | forced adaptive | single_best | accepted_only | 8/8 | 100.0 | 77.428 | 0.124071 | 0.126086 | 10.417 | 61.561 |
| A2 | forced adaptive | robust_weighted | accepted_only | 8/8 | 100.0 | 77.428 | 0.145186 | 0.148185 | 4.167 | 60.666 |
| A3 | forced adaptive | robust_weighted | qa_status | 5/8 | 62.5 | 77.234 | 0.146515 | 0.148964 | 4.167 | 88.234 |
| S1 (seed 0) | forced adaptive, random selection | robust_weighted | qa_status | 6/8 | 75.0 | 80.854 | 0.158431 | 0.169214 | 3.125 | 89.513 |
| A4-subset | formal default slice | robust_weighted | qa_status | 5/8 | 62.5 | 80.387 | 0.146872 | 0.148504 | 4.167 | 106.239 |

Completed random-selection supplement on the same 8-scene subset:

- `seed 0`: `6/8`
- `seed 1`: `4/8`
- `seed 2`: `7/8`
- `seed 3`: `5/8`

This means the random-selection variant spans `4/8 -> 7/8` across seeds on the same subset.

## Strongly Supported Paper Story

The current result package supports these claims well:

1. The paper should be framed around **reliable scene-level RGB-thermal alignment**, not around
   pairwise matching feasibility.
2. `raw MINIMA` is already a strong pairwise backbone, so the scene-level pipeline is not riding on
   a weak starting point.
3. Robust aggregation is clearly beneficial:
   - `A2` materially improves edge / gradient gains relative to `A1`
   - `A2` cuts the mean severe-outlier ratio from `10.417%` to `4.167%`
4. QA-aware scene decision is also strongly supported:
   - `A3` is the first ablation stage whose pass rule matches the full paper logic
   - `A3` closely matches `A4-subset` in pass count and proxy profile
5. The full pipeline result can be narrated as a scene-level reliability challenge:
   - strong pairwise availability does not automatically translate to scene-level canonical passes

## Claim-Tightening Points

These are not paper blockers, but they are the places where wording should be calibrated carefully.

### Deterministic Frame Selection

The completed multi-seed supplement confirms that random selection is seed-sensitive on the fixed
ablation subset. The earlier `S1 = 6/8` single-seed result should therefore not be treated as a
stable superiority signal.

Random-selection scene stability:

- stable fail:
  - `02`
- stable pass:
  - `04`, `07`, `13`, `14`
- seed-sensitive:
  - `01`, `03`, `08`

Current safest presentation:

- deterministic-even selection is the reproducible default used in the main pipeline
- deterministic-even should be framed as a stable operating policy, not as a proven universal
  superiority claim over random selection
- robust aggregation and QA-aware acceptance remain the more strongly validated components

### Candidate Expansion

Forced-adaptive ablation is useful for method dissection, but the current result package does not
yet isolate adaptive candidate expansion as a standalone source of pass-rate gain.

This is acceptable if the paper treats candidate strategy as part of the pipeline design rather than
the single headline result.

## Current Recommendation on More Experiments

The current evidence now appears strong enough to support paper drafting, GPT review, and
results/discussion polishing **without opening any new experiment wave**.

The earlier open sensitivity question has already been resolved by the completed multi-seed random
supplement. The main remaining work is no longer experimental expansion; it is writing strategy and
claim calibration.

## What We Want GPT to Audit

Please focus on the following decisions:

1. Is the current evidence package now sufficient to stop experiments entirely?
2. What is the strongest paper narrative that foregrounds the contribution without overclaiming?
3. How should the abstract and contribution bullets be phrased to maximize perceived novelty and
   practical value?
4. How should deterministic-even selection be written now that the multi-seed random supplement
   confirms clear seed sensitivity?
5. Does the current `robust aggregation + QA-aware decision` evidence already look strong enough for
   PRCV as the final experiment package?

## Packaging Note

This audit brief is intended to be read together with:

- `docs/prcv_main_table_draft.md`
- `docs/prcv_proxy_consistency_draft.md`
- `docs/prcv_results_discussion_skeleton.md`
- `docs/prcv_ablation_results_final.md`
- `docs/prcv_ablation_table_schema.md`
- `docs/prcv_scene_condition_tables_draft.md`
- `review_artifacts/prcv_ablation_structuring_20260422_031955/`
- `review_artifacts/prcv_s1_multiseed_structuring_20260422_044924/`
