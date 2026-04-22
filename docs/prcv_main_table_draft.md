# PRCV Main Table Draft

Source artifacts: `E:\UAV-TAlign\review_artifacts\prcv_p0_structuring_20260421_222446`

## Pairwise Baselines (500 paired registrations)

| Method | OK / N | OK Rate (%) | Homography (%) | Mean Inlier Ratio | Mean Coverage | Mean Reproj Error | Mean Runtime (s) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| raw MINIMA | 500/500 | 100.000 | 100.000 | 0.378 | 0.996 | 1.707 | 1.859 |
| official pretrained RoMa via local wrapper | 500/500 | 100.000 | 100.000 | 0.400 | 0.982 | 1.672 | 1.077 |
| official pretrained XoFTR-640 via local wrapper | 494/500 | 98.800 | 98.800 | 0.151 | 0.951 | 1.610 | 1.204 |
| AKAZE + RANSAC | 479/500 | 95.800 | 95.800 | 0.177 | 0.646 | 0.393 | 2.368 |
| SIFT + RANSAC | 457/500 | 91.400 | 91.400 | 0.240 | 0.599 | 0.260 | 4.605 |
| Kornia LoFTR (pretrained="outdoor") | 499/500 | 99.800 | 99.800 | 0.096 | 0.919 | 1.411 | 0.549 |

## Scene-Level Pipeline Table

| Method | Eval Unit | Scene Pass | Pass Rate (%) | Mean Accepted Ratio (%) | Mean Runtime (s) |
| --- | --- | --- | --- | --- | --- |
| UAV-TAlign full pipeline | 15 scenes | 7/15 | 46.700 | 64.500 | 89.807 |

## Baseline Completion Note

All first-wave pairwise baselines now have usable 500-pair full-run results.


## Immediate Takeaways

- `raw MINIMA` and `official pretrained RoMa via local wrapper` both reach `500/500` usable pairwise results in the current off-the-shelf setup.
- `official pretrained XoFTR-640 via local wrapper` remains a strong learning baseline with `494/500` usable pairwise results.
- `Kornia LoFTR (pretrained="outdoor")` is now usable under the bounded resize-aware inference setting, reaching `499/500` usable pairwise results with only `1` insufficient-match case.
- Classical baselines are still serviceable, but their pairwise `OK` rates are visibly lower than the multimodal matchers.
- `UAV-TAlign full pipeline` is a scene-level QA-aware system. Its current formal result is `7/15` canonical scene passes with a mean accepted-frame ratio of about `64.5%`.
- For writing and GPT review, the LoFTR setting should be described explicitly as `Kornia LoFTR (pretrained="outdoor")` with resize-aware inference (`match_max_dim=1600`, `use_amp=false`), not as an untouched official-script full-resolution run.
