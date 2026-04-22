# PRCV Ablation Table Schema

## Purpose

This note freezes how the cumulative ablation package should be summarized once A1-A3 are run.

It is separate from `docs/prcv_cumulative_ablation_plan.md`:

- that file defines what to run
- this file defines how to report it without changing the table logic afterward

## Fixed Comparison Logic

The cumulative ablation package should keep four reporting layers distinct:

1. `A0` raw pairwise `MINIMA` reference
2. `A1-A3` forced-adaptive scene-level ablations on the fixed 8-scene subset
3. `A4-subset` slice of the already completed formal full-pipeline result on the same 8 scenes
4. `A4-all` full 15-scene formal headline result

Do not collapse these into one table without explaining the unit difference.

## Fixed 8-Scene Subset

Use the subset already frozen in the ablation plan:

- `01`
- `02`
- `03`
- `04`
- `07`
- `08`
- `13`
- `14`

Current formal full-pipeline slice on this same subset, derived from the already completed 15-scene
run:

- `5/8` canonical passes
- `62.5%` scene pass rate
- mean accepted ratio `80.387%`
- mean delta edge F1 `0.146872`
- mean delta grad NCC `0.148504`
- mean robust reject ratio `20.891%`
- mean severe-outlier ratio `4.167%`
- mean runtime `106.239 s`

This `A4-subset` slice should be reported without rerunning the full pipeline.

## Fixed Formal Headline Reference

The already completed formal 15-scene full-pipeline result remains the paper headline:

- `7/15` canonical passes
- `46.7%` scene pass rate
- mean accepted ratio `64.522%`
- mean delta edge F1 `0.132167`
- mean delta grad NCC `0.119804`
- mean robust reject ratio `17.120%`
- mean severe-outlier ratio `6.667%`
- mean runtime `89.807 s`

This is `A4-all`, not a replacement for the 8-scene ablation slice.

## Table 1: Pairwise Reference Line

`A0` is not a scene-level number, so it should be reported separately.

Recommended compact schema:

| Stage | Eval Unit | Method Form | OK / N | Homography (%) | Mean Inlier Ratio | Mean Coverage | Mean Reproj Error | Mean Runtime (s) | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A0 | 500 pairs | raw MINIMA | 500/500 | 100.0 | 0.378 | 0.996 | 1.707 | 1.859 | Pairwise reference only; not directly comparable to scene pass counts. |

Reporting rule:

- Keep `A0` out of the scene-level cumulative ablation table.
- Use it only to support the statement that the scene-level pipeline is not being compared against a
  weak pairwise backend.

## Table 2: Main Scene-Level Cumulative Ablation Table

This should be the main ablation table in the paper or appendix.

Recommended schema:

| Stage | Scene Set | Candidate Policy | Aggregation | Scene Pass Policy | Pass / N | Pass Rate (%) | Mean Accepted Ratio (%) | Mean Delta Edge F1 | Mean Delta Grad NCC | Mean Reject Ratio (%) | Mean Severe-Outlier Ratio (%) | Mean Runtime (s) | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 8 scenes | forced adaptive | single_best | accepted_only | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Candidate handling only. |
| A2 | 8 scenes | forced adaptive | robust_weighted | accepted_only | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Adds robust aggregation. |
| A3 | 8 scenes | forced adaptive | robust_weighted | qa_status | TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD | Adds QA-aware scene decision. |
| A4-subset | 8 scenes | formal default slice | robust_weighted | qa_status | 5/8 | 62.5 | 80.387 | 0.146872 | 0.148504 | 20.891 | 4.167 | 106.239 | Derived from the completed formal run; candidate policy is not forced-adaptive here. |
| A4-all | 15 scenes | formal default | robust_weighted | qa_status | 7/15 | 46.7 | 64.522 | 0.132167 | 0.119804 | 17.120 | 6.667 | 89.807 | Main full-pipeline headline result. |

Reporting rules:

- `A1-A3` must use the same fixed scene subset, same seed, and same output-root isolation policy.
- `A4-subset` is the fairest direct reference against `A1-A3`.
- `A4-all` is the paper headline, but it is not a same-universe comparison against `A1-A3`.

## Table 3: Optional Per-Scene Condensed Matrix

If the ablation trends are not obvious from mean values alone, add a per-scene matrix in appendix.

Recommended schema:

| Scene | Light | Thermal | View | A1 Status | A2 Status | A3 Status | A4-subset Status | A1 Accepted (%) | A2 Accepted (%) | A3 Accepted (%) | A4-subset Accepted (%) | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Use cases:

- show whether gains concentrate on a few difficult scenes
- show whether `01 vs 02` and `03 vs 04` remain informative after ablation
- show whether `08` remains unstable or converges with the other hard scenes

## Headline Comparison Rules

Use the cumulative table to support these exact comparisons:

- `A1 vs A0`:
  - not a same-unit quantitative comparison
  - interpret qualitatively as the shift from pairwise availability to scene-level candidate handling
- `A2 vs A1`:
  - isolates the gain from robust aggregation
- `A3 vs A2`:
  - isolates the gain from QA-aware scene decision
- `A4-subset vs A3`:
  - measures the gap between forced-adaptive method dissection and the current formal default policy
- `A4-all`:
  - remains the main full-pipeline headline result for the paper

Do not write that `A4-all` is "better" or "worse" than `A3` without stating that the scene set and
candidate-policy regime differ.

## Headline Wording Templates

Safe template for the ablation paragraph:

```text
The cumulative ablation results show how scene-level reliability changes as UAV-TAlign adds
deterministic/adaptive candidate handling, robust homography aggregation, and QA-aware scene
acceptance on top of the same strong pairwise MINIMA backbone. We report the main ablation line on
a fixed 8-scene subset and retain the completed 15-scene formal result as the full-pipeline
headline. This separation is necessary because the current formal run on UAV-TAlign-1K falls into
the default all-small-dataset regime, whereas A1-A3 are designed to force the adaptive candidate
logic for method dissection.
```

Safe template for the `A4-subset` note:

```text
To keep the comparison honest, we also report the subset slice of the already completed formal
pipeline result on the same 8 scenes rather than rerunning it under a different protocol.
```

## Output Naming Freeze

Use stage-specific output roots such as:

- `prcv_ablation_A1_candidate_only_<timestamp>`
- `prcv_ablation_A2_candidate_plus_aggregation_<timestamp>`
- `prcv_ablation_A3_candidate_plus_aggregation_plus_qa_<timestamp>`

Keep the result summary filenames consistent so the future structuring script can ingest them
without manual remapping.

## Immediate Next Step

Before launching A1-A3, keep the following fixed:

- 8-scene subset
- `seed=0`
- same `uav_talign_full` runner
- this table schema

That is enough to run the ablation package without reopening result-format decisions later.
