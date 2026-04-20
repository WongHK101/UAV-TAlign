# UAV-TAlign

**UAV-TAlign: RGB-Thermal Registration for UAV Imagery**

This repository contains the standalone 2D registration code extracted from the
multispectral 3DGS project. It focuses on scene-level RGB-thermal rectification
for raw UAV captures using MINIMA-family cross-modal matchers plus reliability
diagnostics.

## What Is Included

- `estimate_band_homographies.py`  
  Estimates band-to-RGB homographies with MINIMA/RoMa or MINIMA/XoFTR, adaptive
  candidate expansion, robust homography aggregation, and QA decision inputs.
- `build_rectified_band_dataset.py`  
  Warps raw thermal images into the RGB plane and writes validity masks.
- `qa_rectification.py`  
  Runs final standalone QA and exports edge-overlay/panel visual diagnostics.
- `run_uav_talign_rectification.py`  
  Convenience runner for estimate -> warp -> QA.
- `third_party/MINIMA/`  
  Local copy of MINIMA code. Model weights are intentionally ignored by Git.

## Expected Prepared Data Layout

The current scripts expect a prepared scene root with RGB and thermal scenes:

```text
prepared/
  RGB/
    spectral_manifest.json
    images/
  T_raw/
    spectral_manifest.json
    images/
```

The thermal band name defaults to `T`. You can use a different name through
`--bands`, but the corresponding folder must be `<band>_raw`.

## Quick Start

```bash
conda env create -f environment.yml
conda activate uav-talign

python run_uav_talign_rectification.py \
  --prepared_root /path/to/prepared \
  --rectified_root /path/to/rectified \
  --bands T \
  --minima_method roma
```

By default, `--minima_root` points to `third_party/MINIMA`. Place the required
MINIMA weights under:

```text
third_party/MINIMA/weights/
  minima_roma.pth
  minima_xoftr.ckpt
```

The weights are not tracked in Git.

## QA Semantics

UAV-TAlign keeps the original strict pass criteria as `legacy_pass`, but the
formal decision uses:

- `pass`
- `pass_with_warning`
- `fail`

The warning path is allowed only for weak-baseline/high-modality cases with
acceptable match quality, homography stability, gradient improvement, edge
floor, and severe-outlier ratio/count guards.

