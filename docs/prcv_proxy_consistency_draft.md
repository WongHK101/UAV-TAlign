# PRCV Proxy-Consistency Draft

Source artifacts: `E:\UAV-TAlign\review_artifacts\prcv_p0_structuring_20260421_222446`

## Currently Available Scene-Level Proxy Fields

The current `uav_talign_full` scene outputs already store the following QA-facing metrics per scene:

- `accepted_ratio`
- `delta_edge_f1`
- `delta_grad_ncc`
- `improved_grad_ratio`
- `robust_reject_ratio`
- `severe_outlier_ratio`
- `severe_outlier_count`
- `median_disp_to_aggregate_mean_px`
- Boolean decision inputs such as `match_ok`, `geometry_ok`, `stability_ok`, `grad_ok`, `edge_floor_ok`, `qa_outlier_ok`, `warning_path_ok`
- Warning codes such as `baseline_relative_qa_outliers`, `low_accepted_ratio`, `high_robust_reject_ratio`, and `homography_dispersion_warning`

## Pass / Fail Aggregate Summary

| Status | Scenes | Mean Accepted Ratio (%) | Mean Delta Edge F1 | Mean Delta Grad NCC | Mean Improved-Grad Ratio (%) | Mean Reject Ratio (%) | Mean Severe-Outlier Ratio (%) | Mean Median Disp (px) | Mean Scene Inlier Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ok | 7 | 82.500 | 0.162 | 0.151 | 96.400 | 14.400 | 0.000 | 66.556 | 0.446 |
| canonical_fail | 8 | 48.800 | 0.106 | 0.092 | 76.000 | 19.500 | 12.500 | 25.181 | 0.403 |

## Boolean Driver Counts

| Metric | Status | Scenes | True | False | True Rate (%) |
| --- | --- | --- | --- | --- | --- |
| match_ok | ok | 7 | 5 | 2 | 71.400 |
| match_ok | canonical_fail | 8 | 2 | 6 | 25.000 |
| geometry_ok | ok | 7 | 3 | 4 | 42.900 |
| geometry_ok | canonical_fail | 8 | 4 | 4 | 50.000 |
| stability_ok | ok | 7 | 3 | 4 | 42.900 |
| stability_ok | canonical_fail | 8 | 4 | 4 | 50.000 |
| grad_ok | ok | 7 | 7 | 0 | 100.000 |
| grad_ok | canonical_fail | 8 | 8 | 0 | 100.000 |
| edge_floor_ok | ok | 7 | 7 | 0 | 100.000 |
| edge_floor_ok | canonical_fail | 8 | 8 | 0 | 100.000 |
| qa_outlier_ok | ok | 7 | 7 | 0 | 100.000 |
| qa_outlier_ok | canonical_fail | 8 | 5 | 3 | 62.500 |
| warning_path_ok | ok | 7 | 3 | 4 | 42.900 |
| warning_path_ok | canonical_fail | 8 | 0 | 8 | 0.000 |

## Warning-Code Frequency

| Status | Warning Code | Scenes | Scene Rate (%) |
| --- | --- | --- | --- |
| ok | high_modality_gap | 7 | 100.000 |
| ok | weak_h0_baseline | 7 | 100.000 |
| ok | homography_dispersion_warning | 4 | 57.100 |
| ok | low_accepted_ratio | 2 | 28.600 |
| canonical_fail | baseline_relative_qa_outliers | 8 | 100.000 |
| canonical_fail | high_modality_gap | 8 | 100.000 |
| canonical_fail | weak_h0_baseline | 8 | 100.000 |
| canonical_fail | low_accepted_ratio | 6 | 75.000 |
| canonical_fail | homography_dispersion_warning | 3 | 37.500 |
| canonical_fail | qa_outliers_exceed_warning_limit | 3 | 37.500 |
| canonical_fail | high_robust_reject_ratio | 2 | 25.000 |

## Joint Rule Diagnostics

| Rule | Definition | Fail+ | Fail- | Pass+ | Pass- | Fail Recall (%) | Pass Exclusion (%) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| baseline_relative_qa_outliers | baseline_relative_qa_outliers in warning_codes | 8 | 0 | 0 | 7 | 100.000 | 100.000 |
| accepted_ratio_lt_0_60 | accepted_ratio < 0.60 | 5 | 3 | 0 | 7 | 62.500 | 100.000 |
| accepted_ratio_lt_0_70 | accepted_ratio < 0.70 | 5 | 3 | 1 | 6 | 62.500 | 85.700 |
| low_accepted_ratio_warning | low_accepted_ratio in warning_codes | 6 | 2 | 2 | 5 | 75.000 | 71.400 |
| high_robust_reject_warning | high_robust_reject_ratio in warning_codes | 2 | 6 | 0 | 7 | 25.000 | 100.000 |
| warning_path_fail | warning_path_ok == False | 8 | 0 | 4 | 3 | 100.000 | 42.900 |
| qa_outlier_fail | qa_outlier_ok == False | 3 | 5 | 0 | 7 | 37.500 | 100.000 |
| joint_outlier_or_lowacc | baseline_relative_qa_outliers OR accepted_ratio < 0.60 | 8 | 0 | 0 | 7 | 100.000 | 100.000 |
| joint_outlier_and_warningfail | baseline_relative_qa_outliers AND warning_path_ok == False | 8 | 0 | 0 | 7 | 100.000 | 100.000 |

## Paired Controls

| Scene | Status | Accepted Ratio (%) | Reject Ratio (%) | Delta Edge F1 | Delta Grad NCC | Warning Codes |
| --- | --- | --- | --- | --- | --- | --- |
| 01_day_grayscale_wide_substation_power_lines_50 | ok | 98.000 | 0.000 | 0.145 | 0.125 | high_modality_gap, homography_dispersion_warning, weak_h0_baseline |
| 02_day_grayscale_zoom_substation_power_lines_50 | canonical_fail | 98.000 | 30.600 | 0.043 | 0.054 | baseline_relative_qa_outliers, high_modality_gap, high_robust_reject_ratio, homography_dispersion_warning, qa_outliers_exceed_warning_limit, weak_h0_baseline |
| 03_night_grayscale_wide_substation_power_lines_45 | canonical_fail | 82.200 | 40.500 | 0.172 | 0.212 | baseline_relative_qa_outliers, high_modality_gap, high_robust_reject_ratio, weak_h0_baseline |
| 04_night_grayscale_zoom_substation_power_lines_45 | ok | 80.000 | 16.700 | 0.077 | 0.109 | high_modality_gap, weak_h0_baseline |

## First Read of the Evidence

- `baseline_relative_qa_outliers` appears in all `8/8` failing scenes and in `0/7` passing scenes. This is the cleanest currently stored fail-side discriminator.
- `low_accepted_ratio` is also strongly associated with failure (`6/8` fails), but it is not sufficient by itself because it also appears in some passing scenes.
- `grad_ok` and `edge_floor_ok` are always true in the current 15-scene run, so they do not explain the present pass/fail split.
- `geometry_ok` and `stability_ok` are mixed on both sides, which suggests they are useful but not individually decisive under the current QA rules.
- In the current 15-scene snapshot, `baseline_relative_qa_outliers` alone gives `8/8` fail recall and `7/7` pass exclusion; the combined rules `baseline_relative_qa_outliers OR accepted_ratio < 0.60` and `baseline_relative_qa_outliers AND warning_path_ok == False` are equally separating on the same snapshot.
- `accepted_ratio` by itself is not enough: scene `02` still has `98%` accepted frames yet fails because reject / outlier signals stay high, while scene `04` passes at `80%` accepted frames when those fail-side warnings are absent.
- The paired controls `01 vs 02` and `03 vs 04` therefore support the current interpretation that the scene-level bottleneck is QA-relative reliability rather than raw match availability.
