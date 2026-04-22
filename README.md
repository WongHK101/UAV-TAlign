# UAV-TAlign

**UAV-TAlign: RGB-Thermal Registration for UAV Imagery**

This repository contains the standalone 2D UAV RGB-thermal registration code
used for the current PRCV study. It includes:

- scene-level RGB-thermal rectification with MINIMA-family backends;
- pairwise baseline runners for SIFT, AKAZE, LoFTR, RoMa, XoFTR, and raw MINIMA;
- PRCV smoke-test and main-evaluation entry points;
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
  Small fixed-subset smoke evaluation for baseline readiness.
- `run_prcv_main_experiment.py`
  Main PRCV evaluation runner on `UAV-TAlign-1K`.
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
The current PRCV experiments were run in a Linux `uav-talign` Conda environment
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

The reference runtime is Linux with CUDA. The server launcher scripts under
`scripts/` assume a Bash-compatible shell.

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

### 2. `UAV-TAlign-1K` pairwise evaluation layout

`run_prcv_smoke_test.py` and `run_prcv_main_experiment.py` expect a dataset root
with a manifest plus per-scene `rgb/` and `thermal/` folders:

```text
UAV-TAlign-1K/
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

## Quick Start

### Rectification pipeline

```bash
python run_uav_talign_rectification.py \
  --prepared_root /path/to/prepared \
  --rectified_root /path/to/rectified \
  --bands T \
  --minima_method roma
```

### PRCV smoke test

```bash
python run_prcv_smoke_test.py \
  --dataset_root /path/to/UAV-TAlign-1K \
  --output_root /path/to/outputs/prcv_smoke_test \
  --methods sift_ransac,akaze_ransac,loftr_outdoor,roma_outdoor,xoftr_official,raw_minima,uav_talign_full \
  --device cuda \
  --official_xoftr_ckpt /path/to/weights_xoftr_640.ckpt
```

### PRCV main evaluation

```bash
python run_prcv_main_experiment.py \
  --dataset_root /path/to/UAV-TAlign-1K \
  --output_root /path/to/outputs/prcv_main_experiment \
  --methods raw_minima,uav_talign_full \
  --device cuda \
  --seed 0
```

For the default main PRCV comparison set, use:

```text
sift_ransac,akaze_ransac,loftr_outdoor,roma_outdoor,xoftr_official,raw_minima,uav_talign_full
```

## Reproducibility Notes

- `run_prcv_main_experiment.py` and `run_prcv_smoke_test.py` both enforce path
  guards so outputs cannot be written into the dataset root or the MINIMA code
  tree.
- The server launcher scripts now derive `REPO_ROOT` from their own location by
  default, so they are not tied to a specific username or absolute server path.
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
