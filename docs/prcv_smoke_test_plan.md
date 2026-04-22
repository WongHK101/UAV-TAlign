# PRCV Smoke Test Plan

## Goal

Before any full 15-scene launch, verify that all first-wave methods can:

- read the UAV-TAlign-1K pair structure;
- produce matches or an explicit failure code;
- pass through the same homography-fitting stage;
- emit logs and JSON outputs in a unified format;
- handle empty or weak matches without crashing the pipeline.

This step is meant to catch interface and output mismatches before scarce GPU time is used.

## First-Wave Methods

- `sift_ransac`
- `akaze_ransac`
- `loftr_outdoor`
- `roma_outdoor`
- `xoftr_official`
- `raw_minima`
- `uav_talign_full`

## Representative Smoke-Test Scenes

Use three scenes that stress different parts of the pipeline:

1. `01_day_grayscale_wide_substation_power_lines_50`
   - day
   - grayscale thermal
   - cross-FOV wide-view case

2. `08_night_grayscale_urban_22`
   - night
   - grayscale thermal
   - urban nighttime lighting

3. `13_lowlight_pseudocolor_road_21`
   - lowlight
   - pseudocolor thermal
   - non-substation scene with different rendering statistics

## Pair Budget

Use a small deterministic subset to keep the smoke test cheap:

- 5 pairs per scene
- 15 pairs total

Suggested pair ids:

- scene `01`: `000001`, `000013`, `000025`, `000037`, `000050`
- scene `08`: `000001`, `000006`, `000011`, `000016`, `000022`
- scene `13`: `000001`, `000006`, `000011`, `000016`, `000021`

## Smoke-Test Checks

For each method, verify:

1. image loading succeeds on both RGB and thermal files;
2. matcher returns:
   - matches; or
   - an explicit empty/failed status without uncaught exception;
3. homography fitting returns:
   - a valid homography; or
   - an explicit fit failure code;
4. output JSON contains the same required fields:
   - `method`
   - `scene_id`
   - `pair_id`
   - `status`
   - `num_matches`
   - `num_inliers`
   - `inlier_ratio`
   - `reprojection_error`
   - `coverage`
   - `homography_available`
5. runtime logging is present;
6. methods with empty matches do not break batch execution.

## Passing Criteria

The smoke test is considered passed when:

1. every method completes all scheduled pairs without pipeline crash;
2. every failure is captured as structured output, not as missing output;
3. the downstream homography-fitting wrapper works for all methods;
4. the result schema is stable enough to support later full-scene aggregation.

## UAV-TAlign Full: Canonical Vs Smoke

For `uav_talign_full`, keep the canonical scene-level threshold unchanged.

- Canonical threshold:
  - inherited from the formal rectification pipeline
  - do not relax it just to make the 5-pair smoke subset pass
- Smoke-only threshold:
  - used only for the tiny 5-pair readiness subset
  - default rule: `ceil(0.6 * N_pairs_smoke)`
  - with `5` pairs, this gives `3`

The smoke output should therefore report both:

- `canonical_scene_pass`
- `smoke_scene_pass`
- `canonical_failure_reason`
  - use `accepted_frames_below_min_good_frames` when the formal scene-level threshold is missed on the tiny smoke subset
- `source_pair_ids`
  - keep the smoke subset identity explicit in the result JSON

Interpretation:

- `canonical_scene_pass = True`
  - the scene already clears the formal threshold on the smoke subset
- `canonical_scene_pass = False` and `smoke_scene_pass = True`
  - environment/pipeline is runnable, but the canonical gate is too strict for this tiny subset and should be read as a stress signal
- `canonical_scene_pass = False` and `smoke_scene_pass = False`
  - still a meaningful hard-case signal that deserves diagnosis, not just an environment note

## Notes

- This is not a performance test.
- This is not used for paper tables directly.
- If a method already needs heavy code surgery at the smoke-test stage, lower its priority instead of forcing it into the first-wave baseline pool.
