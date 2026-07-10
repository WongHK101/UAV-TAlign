# UAV-TAlign

**UAV-TAlign: Infrared-Visible Registration for UAV Imagery**

This repository contains the standalone 2D UAV RGB-thermal registration code
used for the UAV-TAlign infrared-visible alignment study. It includes:

- scene-level RGB-thermal rectification with MINIMA-family backends;
- pairwise baseline runners for SIFT, AKAZE, LoFTR, RoMa, XoFTR, and raw MINIMA;
- smoke-test and main-evaluation entry points;
- dataset audit tooling for `UAV-TAlign-12K` and `UAV-TAlign-1K-Lite`;
- vendored third-party code under `third_party/MINIMA/`.

Model weights, datasets, outputs, and internal drafting materials are
intentionally excluded from Git.

## Repository Layout

- `run_uav_talign_rectification.py`
  Convenience entry point for estimate -> warp -> QA on a prepared scene.
- `estimate_band_homographies.py`
  Core scene-level alignment logic with candidate selection, robust homography
  aggregation, and QA-aware acceptance.
- `build_rectified_band_dataset.py`
  Writes rectified thermal imagery and validity masks.
- `qa_rectification.py`
  Produces QA summaries and visual diagnostics.
- `run_prcv_smoke_test.py`
  Small fixed-subset smoke evaluation for baseline readiness. The historical
  filename is retained for compatibility.
- `run_prcv_main_experiment.py`
  Main evaluation runner for `UAV-TAlign-1K-Lite` and `UAV-TAlign-12K`. The
  historical filename is retained for compatibility.
- `BENCHMARK_PROTOCOL.md`
  Authoritative public specification of the UAV-TAlign-12K benchmark protocol:
  the three evaluation tracks, output schemas, status codes, canonical gate vs
  reliability score, statistical views, and reporting stack.
- `DATASET_MANIFEST_SCHEMA.md`
  Dataset metadata schema (per-scene fields, manifest layout, integrity report).
  Complements the benchmark protocol document.
- `scripts/audit_uav_talign_dataset.py`
  Read-only dataset audit utility that emits scene, condition, integrity, and
  frozen-manifest artifacts.
- `scripts/build_official_eval_manifest.py`
  Builds the official `UAV-TAlign-12K` valid evaluation manifest and
  integrity report used by journal-scale experiments.
- `manifests/`
  Versioned small manifest/report files for the official 12K evaluation split.
- `utils/`
  Dataset adapters, matching bridges, QA helpers, and evaluation utilities.
- `scripts/server_run_prcv_ablation_wave.sh`
  GPU launcher for the cumulative ablation package.
- `scripts/server_run_prcv_s1_multiseed.sh`
  GPU launcher for the random-selection multi-seed supplement.
- `third_party/MINIMA/`
  Vendored MINIMA tree plus vendored RoMa/XoFTR family code.

## Tested Environment

The authoritative tested environment is `environment.yml`.
The current experiments were run in a Linux `uav-talign` Conda environment
with the following key package versions:

- Python `3.10.18`
- PyTorch `2.0.1`
- torchvision `0.15.2`
- pytorch-cuda `11.8`
- numpy `1.26.4`
- scipy `1.15.3`
- Pillow `11.1.0`
- opencv-python `4.11.0.86`
- kornia `0.6.11`
- albumentations `2.0.8`
- pytorch-lightning `1.9.5`
- torchmetrics `1.9.0`
- timm `1.0.26`
- poselib `2.0.5`

The reference runtime is Linux with CUDA. The repository now includes both
Bash launchers for Linux-like servers and PowerShell launchers for the current
Windows 4090 host.

## Installation

Recommended: create the tested Conda environment.

```bash
conda env create -f environment.yml
conda activate uav-talign
```

`requirements.txt` is provided as a pip fallback for users who already have a
compatible Python 3.10 + PyTorch environment. For GPU reproduction, prefer
`environment.yml`.

## Weights

By default, `--minima_root` points to `third_party/MINIMA`. Place the required
MINIMA checkpoints under:

```text
third_party/MINIMA/weights/
  minima_roma.pth
  minima_xoftr.ckpt
```

For the official XoFTR baseline, pass the public checkpoint explicitly, e.g.
`--official_xoftr_ckpt /path/to/weights_xoftr_640.ckpt`.

The RoMa baseline is loaded through the vendored RoMa runtime inside
`third_party/MINIMA/third_party/RoMa_minima/`. No separate `romatch` checkout is
required.

Weights are not tracked in Git.

## Data Layouts

### 1. Prepared scene layout for rectification

`run_uav_talign_rectification.py` expects a prepared scene root like:

```text
prepared/
  RGB/
    spectral_manifest.json
    images/
  T_raw/
    spectral_manifest.json
    images/
```

The thermal band defaults to `T`. If `--bands` is changed, the thermal folder
must be named `<band>_raw`.

### 2. `UAV-TAlign-12K` and `UAV-TAlign-1K-Lite` evaluation layout

`run_prcv_smoke_test.py` and `run_prcv_main_experiment.py` expect a dataset root
with a manifest plus per-scene `rgb/` and `thermal/` folders:

```text
UAV-TAlign-12K/
  dataset_manifest.json
  01_day_grayscale_wide_substation_power_lines_50/
    rgb/
      000001.jpg
      ...
    thermal/
      000001.jpg
      ...
  ...
```

`UAV-TAlign-12K` is the full journal benchmark. `UAV-TAlign-1K-Lite` is the
fixed lightweight subset for development, ablation, and fast evaluation:

```text
UAV-TAlign-1K-Lite/
  subset_manifest.json
  01_day_grayscale_wide_substation_power_lines_50/
    rgb/
      000001.jpg
      ...
    thermal/
      000001.jpg
      ...
  ...
```

The loader also accepts `dataset_manifest.json` in place of `subset_manifest.json`.

For journal-scale 12K experiments, use the versioned official evaluation
manifest:

```text
manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json
```

It fixes the evaluation entry to `6037` integrity-checked RGB-thermal pairs
from the `6039`-pair candidate collection. The corresponding integrity report
is tracked under `manifests/` for reproducibility and paper-facing summaries.

Because `UAV-TAlign-12K` has imbalanced scene lengths, downstream reporting
should include micro pair-level averages, macro scene-level averages,
per-scene statistics, and condition-level statistics.

### 3. Dataset audit

Run the read-only audit before release packaging or large experiments:

```bash
python scripts/audit_uav_talign_dataset.py \
  --dataset UAV-TAlign-1K-Lite /path/to/UAV-TAlign-1K-Lite \
  --dataset UAV-TAlign-12K /path/to/UAV-TAlign-12K \
  --output_root /path/to/review_artifacts/ipt_p0a_dataset_audit \
  --verify_images \
  --hash_duplicates
```

The audit writes all outputs under `--output_root` and does not write into the
dataset directories. See `DATASET_MANIFEST_SCHEMA.md` for the journal-facing
manifest schema.

Build or refresh the official 12K valid evaluation manifest with:

```bash
python scripts/build_official_eval_manifest.py \
  --dataset_root /path/to/UAV-TAlign-12K \
  --output_root manifests \
  --dataset_name UAV-TAlign-12K \
  --manifest_version ipt_valid_v1
```

## Quick Start

### Rectification pipeline

```bash
python run_uav_talign_rectification.py \
  --prepared_root /path/to/prepared \
  --rectified_root /path/to/rectified \
  --bands T \
  --minima_method roma
```

### Smoke test

```bash
python run_prcv_smoke_test.py \
  --dataset_root /path/to/UAV-TAlign-1K-Lite \
  --manifest_path /path/to/subset_manifest.json \
  --output_root /path/to/outputs/prcv_smoke_test \
  --methods sift_ransac,akaze_ransac,loftr_outdoor,roma_outdoor,xoftr_official,raw_minima,uav_talign_full \
  --device cuda \
  --official_xoftr_ckpt /path/to/weights_xoftr_640.ckpt
```

### Main evaluation

```bash
python run_prcv_main_experiment.py \
  --dataset_root /path/to/UAV-TAlign-12K \
  --manifest_path manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json \
  --output_root /path/to/outputs/prcv_main_experiment \
  --methods raw_minima,uav_talign_full \
  --device cuda \
  --seed 0
```

For the default main comparison set, use:

```text
sift_ransac,akaze_ransac,loftr_outdoor,roma_outdoor,xoftr_official,raw_minima,uav_talign_full
```

### Windows 4090 host shortcut

On the currently audited Windows host, the runnable Conda environment is the
prefix environment `G:\UAV-TAlign\uav_talign_envs\uav-talign-e10a8be-py310`.
Use the launcher below instead of assuming a named `uav-talign` environment:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\server_run_prcv_main_12k_windows.ps1 `
  -DatasetRoot G:\UAV-TAlign\UAV-TAlign-12K `
  -OfficialXoftrCkpt <PATH_TO_WEIGHTS_XOFTR_640_CKPT>
```

## Reproducibility Notes

- `run_prcv_main_experiment.py` and `run_prcv_smoke_test.py` both enforce path
  guards so outputs cannot be written into the dataset root or the MINIMA code
  tree.
- For 12K journal experiments, pass `--manifest_path` and use the tracked
  official valid evaluation manifest. Runner summaries record the manifest
  path, SHA256 hash, valid pair count, and excluded pair count.
- The server launcher scripts now derive `REPO_ROOT` from their own location by
  default, so they are not tied to a specific username or absolute server path.
- The Bash launchers accept `ENV_PREFIX=/path/to/conda-prefix` when a named
  Conda environment is unavailable.
- The Windows launchers capture stdout and stderr into separate `_launcher`
  logs and validate the output package before returning success.
- `run_prcv_main_experiment.py` supports `--resume true` and `--seed <int>` for
  resumable and reproducible runs.
- `run_prcv_smoke_test.py` uses a fixed smoke subset defined in
  `utils/uav_talign_dataset.py`.
- Official baseline weights are external inputs and must be provided locally.
- The repository does not contain datasets, trained weights, or experiment
  outputs.

## QA Semantics

The rectification pipeline keeps the original strict `legacy_pass` decision, but
the formal output uses:

- `pass`
- `pass_with_warning`
- `fail`

`pass_with_warning` is reserved for weak-baseline or high-modality cases that
still satisfy the warning-side QA guards on accepted ratio, stability,
gradient/edge quality, and severe-outlier counts.
