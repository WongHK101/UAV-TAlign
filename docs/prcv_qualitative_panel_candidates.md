# PRCV Qualitative Panel Candidates

Source artifacts: `E:\UAV-TAlign\review_artifacts\prcv_p0_structuring_20260421_222446`

| Priority | Scene | Category | Light | Thermal | View | Classical Mean OK (%) | LoFTR OK (%) | XoFTR OK (%) | UAV Status | Accepted Ratio (%) | Representative Images | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 01_day_grayscale_wide_substation_power_lines_50 | paired control / strong pass | day | grayscale | wide | 100.000 | 100.000 | 100.000 | ok | 98.000 | 000001.jpg, 000005.jpg, 000010.jpg | Use with scene 02 to show same scene family under wide-vs-zoom; scene 01 is a clean canonical pass with very strong accepted ratio and positive edge/gradient gains. |
| 2 | 02_day_grayscale_zoom_substation_power_lines_50 | paired control / fail | day | grayscale | zoom | 96.000 | 100.000 | 100.000 | canonical_fail | 98.000 | 000001.jpg, 000005.jpg, 000010.jpg | Use with scene 01 to show a zoom hard case: accepted ratio stays very high, but QA outliers and reject ratio push the scene into canonical fail. |
| 3 | 03_night_grayscale_wide_substation_power_lines_45 | night hard fail | night | grayscale | wide | 97.800 | 100.000 | 100.000 | canonical_fail | 82.200 | 000001.jpg, 000005.jpg, 000009.jpg | Night wide substation case with strong positive proxy gains but large robust reject ratio; good failure-case panel for explaining why QA still rejects it. |
| 4 | 04_night_grayscale_zoom_substation_power_lines_45 | night pass control | night | grayscale | zoom | 100.000 | 100.000 | 100.000 | ok | 80.000 | 000001.jpg, 000005.jpg, 000009.jpg | Natural companion to scene 03: same scene family at night but canonical pass, useful for before/after and pass-vs-fail comparison. |
| 5 | 09_day_pseudocolor_building_20 | classical weak / ours pass | day | pseudocolor | None | 67.500 | 100.000 | 100.000 | ok | 70.000 | 000001.jpg, 000003.jpg, 000004.jpg | Day pseudocolor building scene where classical baselines are visibly weaker while the full pipeline still passes. |
| 6 | 13_lowlight_pseudocolor_road_21 | largest proxy gain pass | lowlight | pseudocolor | None | 81.000 | 100.000 | 100.000 | ok | 61.900 | 000001.jpg, 000003.jpg, 000005.jpg | Lowlight pseudocolor road scene with the strongest positive edge and gradient gains among passing scenes. |
| 7 | 05_night_pseudocolor_solar_panels_16 | low-accepted-ratio fail | night | pseudocolor | None | 81.200 | 93.800 | 100.000 | canonical_fail | 6.200 | 000001.jpg, 000002.jpg, 000004.jpg | Night pseudocolor solar-panel hard case with extremely low accepted ratio; strong candidate for a failure panel. |
| 8 | 15_lowlight_pseudocolor_woodland_26 | baseline weakness + fail | lowlight | pseudocolor | None | 82.700 | 100.000 | 76.900 | canonical_fail | 19.200 | 000001.jpg, 000003.jpg, 000006.jpg | Only scene where official XoFTR pairwise ok-rate visibly drops; useful to show a truly difficult lowlight case rather than a pure QA-only rejection. |

## Suggested First Batch

- Use `01` and `02` as a paired control figure for wide-vs-zoom under the same scene family.
- Use `03` and `04` as a paired night control figure for pass-vs-fail explanation.
- Use `09` and `13` as the first two "ours pass while baselines are weaker" panels.
- Use `05` and `15` as the first two failure panels.
