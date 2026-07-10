# UAV-TAlign Benchmark Closure Spec

This document is the engineering-side closure note for the current
`UAV-TAlign-12K` benchmark package. It is not paper prose. Its purpose is to
make sure the benchmark has a closed loop from official inputs, to executable
commands, to machine-checkable outputs, to protocol-level artifacts.

## 1. Input Contract

The benchmark is anchored to one official manifest and one fixed evaluation
population.

- Dataset: `UAV-TAlign-12K`
- Official manifest: `manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json`
- Canonical manifest SHA256: `a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c`
- Official evaluation size: `6037` valid RGB-thermal pairs from `15` scenes
- Required Track A/B/C method set:
  `sift_ransac, akaze_ransac, loftr_outdoor, roma_outdoor, xoftr_official, raw_minima, uav_talign_full`

Every formal run must preserve three invariants.

- The evaluated pair set must come from the manifest, not folder traversal.
- The run must record the exact manifest hash and execution profile in
  `experiment_config.json` and `main_experiment_summary.json`.
- The runtime must stay isolated from the dataset tree and from
  `third_party/MINIMA`; outputs are only allowed under the chosen output root.

## 2. Execution And Output Contract

The execution chain is:

1. `run_prcv_main_experiment.py` consumes the manifest-filtered 6037-pair set.
2. Pairwise baselines write one `results.jsonl` per method.
3. `uav_talign_full` writes one scene record per scene plus per-scene
   `scene_result.json` payloads.
4. `scripts/check_prcv_main_outputs.py` performs structural and semantic
   acceptance.
5. `scripts/build_ipt_p0d_protocol_artifacts.py` converts scene-level outputs
   into Track B/C protocol artifacts.

The required main-run output package is:

```text
outputs/<run_name>/
  experiment_config.json
  main_experiment_summary.json
  sift_ransac/results.jsonl
  akaze_ransac/results.jsonl
  loftr_outdoor/results.jsonl
  roma_outdoor/results.jsonl
  xoftr_official/results.jsonl
  raw_minima/results.jsonl
  uav_talign_full/results.jsonl
  uav_talign_full/scene_results.jsonl
  uav_talign_full_scene_metrics_detailed.jsonl
  uav_talign_full/<scene>/scene_result.json
```

The required protocol-closure package is:

```text
outputs/<protocol_name>/
  canonical_operating_point.csv
  per_scene_reliability_table.csv
  threshold_sensitivity.csv
  condition_reliability_profile.csv
  risk_coverage.csv
  paper_facing_summary.md
  reliability_score_design.md
```

The closure logic between the two stages is now explicit.

- Track A reads pairwise `results.jsonl` files.
- Track B reads `uav_talign_full/results.jsonl` as the canonical scene record.
- Track C enriches the scene rows with per-scene `scene_result.json`
  `band_payload` fields when the compact scene JSONL does not carry enough QA
  observables.
- The compatibility aliases
  `uav_talign_full/scene_results.jsonl` and
  `uav_talign_full_scene_metrics_detailed.jsonl`
  must stay scene-name aligned with the canonical
  `uav_talign_full/results.jsonl`.

## 3. Acceptance And Guardrails

Benchmark acceptance has two layers, and both must pass.

- Structural acceptance:
  the manifest hash matches, the required files exist, and each pairwise method
  has exactly `6037` records while `uav_talign_full` has exactly `15` scene
  records.
- Semantic acceptance:
  summary statistics must match the JSONL contents, pairwise methods must not
  collapse into all-runtime-error outputs, pairwise methods must expose at
  least one `homography_available=true` record, and the scene-level method must
  expose at least one non-error scene homography.

The validator now enforces this semantic layer directly.

- It cross-checks `status_counts` and `homography_available_count` between
  `main_experiment_summary.json` and each method JSONL.
- It fails any pairwise method whose `results.jsonl` is entirely `status=error`.
- It fails any pairwise method whose `homography_available_count` is zero.
- It checks that `uav_talign_full` scene rows have unique scene names and use
  the `__scene__` sentinel pair id.

The current method-specific guardrail is LoFTR.

- On the audited RTX 4090 24GB Windows host, running `loftr_outdoor` with the
  unbounded profile `loftr_match_max_dim=0` and `loftr_use_amp=false` caused a
  full runtime collapse: `6037/6037` records were `status=error` with CUDA OOM.
- Therefore, formal runs on that host must use an explicit memory-safe LoFTR
  profile. The current launcher default is:
  `--loftr_match_max_dim 1200 --loftr_use_amp true`
- If LoFTR is launched without a safe profile and returns all-error outputs,
  the run is treated as benchmark-invalid even if the file tree is complete.

The current closure status is therefore:

- Track B/C pipeline is logically closed and executable.
- Track A file schema is closed for all methods.
- Formal acceptance is now strict enough to reject false-positive runs.
- The remaining evidence task after this spec is a LoFTR-only rerun under the
  safe execution profile, not a redesign of the benchmark itself.
