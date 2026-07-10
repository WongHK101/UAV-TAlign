# UAV-TAlign-12K Experiment Runbook

This runbook defines the reproducible execution and acceptance path for the
UAV-TAlign-12K journal experiments. It is an engineering document; paper-facing
claims must be sourced from the frozen result packages rather than copied from
intermediate console logs.

## 1. Fixed Input Contract

- Dataset: `UAV-TAlign-12K`
- Candidate collection: 6,039 RGB-infrared pairs / 12,078 images
- Official evaluation split: 6,037 integrity-checked pairs / 12,074 images
- Scenes: 15
- Manifest: `manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json`
- Canonical manifest SHA256:
  `a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c`

All dataset directories are read-only inputs. Every run must use a new output
directory outside the source repository, normally under a sibling `runs/`
directory. Reusing a non-empty output directory is permitted only for an
explicit, safe resume of the same experiment.

## 2. Environment And Weights

The audited Windows RTX 4090 environment is a prefix environment:

```text
G:\UAV-TAlign\uav_talign_envs\uav-talign-e10a8be-py310
```

Required external weights or model interfaces are:

- MINIMA RoMa family, large/full branch;
- public RoMa outdoor full model;
- Kornia LoFTR outdoor pretrained model;
- official XoFTR-640 checkpoint;
- RIFT2 Python implementation in its independent Python 3.11 environment.

Weights, datasets, caches, and run outputs must not be committed to Git.

## 3. Main 12K Run

The default Windows launcher uses a timestamped output directory under
`G:\UAV-TAlign\runs` and rejects a non-empty target unless `-Resume` is set.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\server_run_prcv_main_12k_windows.ps1 `
  -DatasetRoot G:\UAV-TAlign\UAV-TAlign-12K `
  -OfficialXoftrCkpt <PATH_TO_WEIGHTS_XOFTR_640_CKPT>
```

The formal method set is:

```text
sift_ransac,akaze_ransac,loftr_outdoor,roma_outdoor,xoftr_official,raw_minima,uav_talign_full
```

LoFTR must use the accepted resize-aware execution profile:

```text
loftr_match_max_dim=1200
loftr_use_amp=true
```

The accepted June 2026 evidence is a composed package: the original main run
provides all methods except LoFTR, while an isolated LoFTR output package
provides the accepted resize-aware replacement. Validate such a package with:

```powershell
python scripts\check_prcv_main_outputs.py `
  --output_dir <MAIN_OUTPUT_DIR> `
  --method_output_override loftr_outdoor=<LOFTR_OUTPUT_DIR> `
  --expect_manifest_sha256 a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c `
  --expect_pair_count 6037 `
  --expect_scene_count 15
```

The validator must report `"ok": true`. A structurally complete package with
an all-error method is not accepted.

## 4. Protocol Artifacts

Protocol artifacts are generated read-only from an immutable main-run output.
The input directory is required explicitly; the output defaults to a new
timestamped directory outside the repository.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\server_run_prcv_protocol_artifacts_windows.ps1 `
  -InputDir <MAIN_OUTPUT_DIR>
```

Required outputs include:

```text
canonical_operating_point.csv
condition_reliability_profile.csv
per_scene_reliability_table.csv
reliability_score_design.md
risk_coverage.csv
threshold_sensitivity.csv
paper_facing_summary.md
```

The accepted canonical result is 15/15 scene homographies and 9/15 retained
scenes. The reliability score is used for ranking and operating-profile
analysis; it does not replace the canonical gate.

## 5. RIFT2 Domain Baseline

The accepted complete RIFT2 run uses the following method-specific evaluated
setting:

```text
RIFT2 (Python, resize-aware)
max_dim=1200
npt=2000
patch_size=64
Lowe ratio=0.95
estimator=USAC_MAGSAC
reproj_threshold=5.0
```

The frozen run contains 6,037/6,037 records and homographies. Do not describe
this as a shared-threshold 3.0 run. A future harmonized-threshold rerun, if
performed, must use a new output root and a distinct table label until it is
formally accepted.

## 6. Ablation And Multi-Seed Supplement

The Windows supplement launcher resolves the fixed eight scene IDs at runtime,
uses independent stage directories, and writes under a timestamped bundle in
the sibling `runs/` directory by default:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\server_run_prcv_supplement_bundle_windows.ps1
```

The accepted supplement contains:

- candidate-only evidence;
- robust scene consensus;
- QA-aware verification;
- random-selection seeds 0--3.

The random-selection spread is reported as boundary sensitivity. Deterministic
even selection is the reproducible default, not a claim of strict average
superiority over every random seed.

## 7. Acceptance Checklist

- Manifest canonical hash matches the fixed value above.
- Each pairwise method has exactly 6,037 records.
- `uav_talign_full` has exactly 15 unique scene records.
- Compatibility scene JSONL files are scene-name aligned with canonical output.
- No required pairwise method collapses to all runtime errors.
- The accepted LoFTR source is explicitly identified in the validator report.
- Main and protocol outputs are outside dataset and source-code directories.
- Every formal output records environment, seed, weights, manifest, and status
  provenance.

## 8. Frozen Paper-Facing Reference Values

These values are acceptance references, not targets to tune toward:

| Method | H availability (%) | Mean inlier ratio | Mean coverage | Median reprojection |
|---|---:|---:|---:|---:|
| SIFT + RANSAC | 87.08 | 0.242 | 0.627 | 0.000 |
| AKAZE + RANSAC | 94.29 | 0.160 | 0.730 | 0.105 |
| RIFT2 (Python, resize-aware) | 100.00 | 0.086 | 0.354 | 0.121 |
| raw MINIMA | 100.00 | 0.319 | 1.000 | 1.773 |
| RoMa outdoor | 100.00 | 0.328 | 0.997 | 1.741 |
| Kornia LoFTR outdoor (resize-aware) | 99.12 | 0.074 | 0.895 | 0.823 |
| XoFTR-640 | 99.20 | 0.089 | 0.949 | 1.732 |

Pairwise fitting statistics are complementary diagnostics and must not be
presented as one scalar ranking of heterogeneous correspondence regimes.
