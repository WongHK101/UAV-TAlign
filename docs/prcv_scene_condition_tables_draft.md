# PRCV Scene / Condition Tables Draft

Source artifacts: `E:\UAV-TAlign\review_artifacts\prcv_p0_structuring_20260421_222446`

## Per-Scene Condensed Table

| Scene | Scene Name | Light | Thermal | View | Classical Mean OK (%) | LoFTR OK (%) | XoFTR OK (%) | UAV-TAlign Status | Accepted Ratio (%) | Delta Edge F1 | Delta Grad NCC | Reject Ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 01 | 01_day_grayscale_wide_substation_power_lines_50 | day | grayscale | wide | 100.000 | 100.000 | 100.000 | ok | 98.000 | 0.145 | 0.125 | 0.000 |
| 02 | 02_day_grayscale_zoom_substation_power_lines_50 | day | grayscale | zoom | 96.000 | 100.000 | 100.000 | canonical_fail | 98.000 | 0.043 | 0.054 | 0.306 |
| 03 | 03_night_grayscale_wide_substation_power_lines_45 | night | grayscale | wide | 97.800 | 100.000 | 100.000 | canonical_fail | 82.200 | 0.172 | 0.212 | 0.405 |
| 04 | 04_night_grayscale_zoom_substation_power_lines_45 | night | grayscale | zoom | 100.000 | 100.000 | 100.000 | ok | 80.000 | 0.077 | 0.109 | 0.167 |
| 05 | 05_night_pseudocolor_solar_panels_16 | night | pseudocolor | None | 81.200 | 93.800 | 100.000 | canonical_fail | 6.200 | 0.104 | 0.110 | 0.000 |
| 06 | 06_day_pseudocolor_solar_panels_16 | day | pseudocolor | None | 90.600 | 100.000 | 100.000 | ok | 81.200 | 0.170 | 0.138 | 0.154 |
| 07 | 07_day_grayscale_transmission_tower_102 | day | grayscale | None | 99.000 | 100.000 | 100.000 | ok | 92.200 | 0.142 | 0.201 | 0.213 |
| 08 | 08_night_grayscale_urban_22 | night | grayscale | None | 100.000 | 100.000 | 100.000 | canonical_fail | 36.400 | 0.113 | 0.089 | 0.250 |
| 09 | 09_day_pseudocolor_building_20 | day | pseudocolor | None | 67.500 | 100.000 | 100.000 | ok | 70.000 | 0.115 | 0.086 | 0.143 |
| 10 | 10_day_pseudocolor_factory_24 | day | pseudocolor | None | 64.600 | 100.000 | 100.000 | canonical_fail | 25.000 | 0.226 | 0.168 | 0.167 |
| 11 | 11_night_grayscale_building_25 | night | grayscale | None | 100.000 | 100.000 | 100.000 | canonical_fail | 48.000 | 0.046 | 0.061 | 0.167 |
| 12 | 12_day_grayscale_orchard_20 | day | grayscale | None | 100.000 | 100.000 | 100.000 | canonical_fail | 75.000 | 0.059 | 0.024 | 0.067 |
| 13 | 13_lowlight_pseudocolor_road_21 | lowlight | pseudocolor | None | 81.000 | 100.000 | 100.000 | ok | 61.900 | 0.289 | 0.277 | 0.154 |
| 14 | 14_lowlight_pseudocolor_transmission_tower_18 | lowlight | pseudocolor | None | 100.000 | 100.000 | 100.000 | ok | 94.400 | 0.193 | 0.122 | 0.176 |
| 15 | 15_lowlight_pseudocolor_woodland_26 | lowlight | pseudocolor | None | 82.700 | 100.000 | 76.900 | canonical_fail | 19.200 | 0.088 | 0.022 | 0.200 |

## Condition Breakdown: Light Condition

| Condition | Scenes | UAV Pass | UAV Pass Rate (%) | Mean Accepted Ratio (%) | Mean LoFTR OK (%) | Mean XoFTR OK (%) | Mean Classical OK (%) | Mean Delta Edge F1 | Mean Delta Grad NCC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| day | 7 | 4 | 57.100 | 77.100 | 100.000 | 100.000 | 88.200 | 0.129 | 0.114 |
| lowlight | 3 | 2 | 66.700 | 58.500 | 100.000 | 92.300 | 87.900 | 0.190 | 0.140 |
| night | 5 | 1 | 20.000 | 50.600 | 98.800 | 100.000 | 95.800 | 0.102 | 0.116 |

## Condition Breakdown: Thermal Rendering

| Condition | Scenes | UAV Pass | UAV Pass Rate (%) | Mean Accepted Ratio (%) | Mean LoFTR OK (%) | Mean XoFTR OK (%) | Mean Classical OK (%) | Mean Delta Edge F1 | Mean Delta Grad NCC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| grayscale | 8 | 3 | 37.500 | 76.200 | 100.000 | 100.000 | 99.100 | 0.100 | 0.109 |
| pseudocolor | 7 | 4 | 57.100 | 51.200 | 99.100 | 96.700 | 81.100 | 0.169 | 0.132 |

## Condition Breakdown: View

| Condition | Scenes | UAV Pass | UAV Pass Rate (%) | Mean Accepted Ratio (%) | Mean LoFTR OK (%) | Mean XoFTR OK (%) | Mean Classical OK (%) | Mean Delta Edge F1 | Mean Delta Grad NCC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| None | 11 | 5 | 45.500 | 55.400 | 99.400 | 97.900 | 87.900 | 0.140 | 0.118 |
| wide | 2 | 1 | 50.000 | 90.100 | 100.000 | 100.000 | 98.900 | 0.159 | 0.168 |
| zoom | 2 | 1 | 50.000 | 89.000 | 100.000 | 100.000 | 98.000 | 0.060 | 0.081 |

## Immediate Observations

- The current scene-level bottleneck is not pairwise matcher availability: `raw MINIMA`, `RoMa`, `LoFTR`, and almost all `XoFTR` pairs remain usable across the dataset.
- Night scenes are the hardest group for `UAV-TAlign full pipeline` under the current canonical gate.
- Pseudocolor scenes suppress the classical baselines more than they suppress `XoFTR` / `RoMa`, while the `UAV-TAlign` scene pass rate remains mixed rather than uniformly poor.
- The most informative paired controls are `01 vs 02` and `03 vs 04`, because they keep the scene family fixed while changing view or pass/fail outcome.
