# UAV-TAlign

**UAV-TAlign-12K: Benchmarking Scene-Level Reliability in Cross-FOV UAV
Infrared-Visible Alignment**

UAV-TAlign consolidates pretrained pairwise matches into a scene homography
through representative evidence selection, robust consensus, and cross-modal
quality verification. This repository provides the alignment pipeline, seven
pairwise baseline evaluation paths, and the scene-level reliability analysis.
No matcher is trained or fine-tuned on UAV-TAlign-12K.

## Dataset

**UAV-TAlign-12K contains 6,037 RGB-infrared pairs (12,074 images) across
15 scenes.** The data cover day, night, and low-light capture; native grayscale
and pseudocolor infrared rendering; and wide, zoom, and general views from a
DJI Matrice 350 RTK with a Zenmuse H30T.

Download the images separately and retain the scene directory names:

```text
workspace/
  UAV-TAlign/                 # this code repository
  UAV-TAlign-12K/             # downloaded images
    README.md
    scenes.csv
    LICENSE.txt
    01_day_grayscale_wide_substation_power_lines_50/
      rgb/000001.jpg
      thermal/000001.jpg
      ...
    ...
  weights/                   # downloaded checkpoints
  runs/                      # independent experiment outputs
```

The dataset release link/DOI will be added after deposit. Images and model
weights are not included in this code package. Evaluation reads the supplied
`manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json`; no additional
manifest needs to be copied into the image directory. This frozen manifest
preserves the pair identities used in the experiments.

`UAV-TAlign-1K-Lite` is the earlier 500-pair diagnostic subset used for ablations,
not the main benchmark. Its image subset and subset manifest are separate inputs.

## Installation

The journal-scale learned baselines and scene pipeline were evaluated on a
Windows workstation with an NVIDIA RTX 4090 (24 GB), Python 3.10, PyTorch 2.0.1,
torchvision 0.15.2, CUDA 11.8, OpenCV 4.11.0, and Kornia 0.6.11. Earlier
1K-Lite experiments used Linux. RIFT2 uses a separate Python 3.11 environment.

Create an isolated environment; do not upgrade another project's environment:

```bash
conda env create -f environment.yml
conda activate uav-talign
```

`environment.yml` specifies the main dependency set, including pandas for the
offline protocol analysis. `requirements.txt` is a pip alternative; install the
CUDA-compatible PyTorch 2.0.1 / torchvision 0.15.2 build separately when using
that route. The package recipes do not install an NVIDIA driver.

All examples below run from the code root. They use Bash continuation syntax;
on PowerShell, put each command on one line or replace trailing `\` with a
backtick. Use an unoccupied GPU and a new output directory for each run.

## Pretrained Weights

| Evaluation path | Required model | Loading |
|---|---|---|
| `raw_minima`, `uav_talign_full` | MINIMA-RoMa, **large/full** | Explicit MINIMA checkpoint arguments below |
| `roma_outdoor` | RoMa outdoor **full**, with DINOv2 ViT-L/14 | PyTorch Hub cache |
| `loftr_outdoor` | Kornia LoFTR outdoor | PyTorch Hub cache |
| `xoftr_official` | XoFTR **640** | `--official_xoftr_ckpt` |
| SIFT, AKAZE, RIFT2 | None | Classical feature extraction |

Obtain `minima_roma.pth` from the
[MINIMA release](https://github.com/LSXI7/storage/releases/download/MINIMA/minima_roma.pth)
and `weights_xoftr_640.ckpt` from the
[XoFTR project](https://github.com/OnderT/XoFTR).
The vendored RoMa loader uses the public
[RoMa outdoor checkpoint](https://github.com/Parskatt/storage/releases/download/roma/roma_outdoor.pth)
and [DINOv2 checkpoint](https://dl.fbaipublicfiles.com/dinov2/dinov2_vitl14/dinov2_vitl14_pretrain.pth).
LoFTR loads the outdoor checkpoint through `kornia.feature.LoFTR`.

RoMa, DINOv2, and LoFTR may download on first use. For offline evaluation,
populate the PyTorch Hub checkpoint cache in advance (optionally set
`TORCH_HOME` to a writable cache outside the source and data directories).
Do not substitute MINIMA-XoFTR for XoFTR-640, or a tiny RoMa model for full RoMa.
Pass the MINIMA checkpoint explicitly: an omitted RoMa checkpoint in the
upstream loader can fall back to ordinary pretrained RoMa.

## Evaluate the Benchmark

### 1. Small readiness check

The smoke runner uses five fixed pairs in each of scenes 01, 08, and 13.
This checks execution and outputs, not the formal scene-level result.

```bash
python run_prcv_smoke_test.py \
  --dataset_root ../UAV-TAlign-12K \
  --manifest_path manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json \
  --output_root ../runs/smoke_01 \
  --methods raw_minima \
  --raw_minima_ckpt ../weights/minima_roma.pth \
  --device cuda:0 --seed 0
```

### 2. Pairwise evidence and scene alignment

```bash
python run_prcv_main_experiment.py \
  --dataset_root ../UAV-TAlign-12K \
  --manifest_path manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json \
  --output_root ../runs/main_01 \
  --methods sift_ransac,akaze_ransac,loftr_outdoor,roma_outdoor,xoftr_official,raw_minima,uav_talign_full \
  --raw_minima_ckpt ../weights/minima_roma.pth \
  --uav_talign_minima_ckpt ../weights/minima_roma.pth \
  --official_xoftr_ckpt ../weights/weights_xoftr_640.ckpt \
  --loftr_match_max_dim 1200 --loftr_use_amp true \
  --device cuda:0 --seed 0 --resume false
```

SIFT and AKAZE use CPU feature extraction even when `--device cuda:0` is
specified. They may also be run separately with `--device cpu` and their own
output directory. RIFT2 is evaluated separately, as described below.

The scene pipeline defaults to deterministic even selection, robust weighted
consensus, and the canonical QA decision. `--uav_talign_frame_count 12` is a
base count for the adaptive evidence schedule, **not** a fixed twelve-pair
scene evaluation: scenes of at most 300 pairs use all candidates; larger
scenes expand through the configured 15%, 30%, 45%, and 50% candidate pools,
with an all-frame fallback when needed. Leave these settings unchanged for
the reference configuration.

Historical filenames containing `prcv` are retained for compatibility; these
same entry points support the current journal benchmark. Outputs include:

```text
runs/main_01/
  experiment_config.json
  main_experiment_summary.json
  <pairwise_method>/results.jsonl
  uav_talign_full/results.jsonl
  uav_talign_full/<scene>/scene_result.json
  uav_talign_full/<scene>/rectification_homographies.json
```

Use `--resume true` only to continue the same run with unchanged inputs,
weights, and settings. Never point an output root at an image directory or
an existing unrelated experiment.

### 3. RIFT2 (Python, resize-aware)

The released runner preserves the matching and fitting path of the archived
RIFT2 experiment. Install the external implementation separately:

```bash
git clone https://github.com/canyagmur/RIFT2-multimodal-matching-rotation-python.git ../RIFT2
git -C ../RIFT2 checkout 7d92f005f84c25dd23c07670c2aad90e0f3997e5
conda create -n uav-talign-rift2 python=3.11 pip
conda activate uav-talign-rift2
python -m pip install -r ../RIFT2/requirements.txt
python scripts/run_rift2_evaluation.py \
  --rift2_root ../RIFT2 \
  --dataset_root ../UAV-TAlign-12K \
  --manifest_path manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json \
  --output_root ../runs/rift2_01
```

The fixed profile is `max_dim=1200`, `npt=2000`, `patch_size=64`, Lowe ratio
`0.95`, and `USAC_MAGSAC` with a `5.0`-pixel threshold. The shared main runner
uses a `3.0`-pixel threshold, confidence `0.999`, and `10000` iterations.
RIFT2's archived diagnostics are measured in its resized matching coordinates:
residuals follow the RGB-to-infrared fit and coverage uses RGB inlier cells.
The main runner reports original-coordinate residuals and infrared candidate
match coverage. Preserve these evaluated profiles rather than treating the
diagnostics as a single accuracy ranking.

RIFT2 writes incremental `results.jsonl`, `summary.json`, and scene/condition
CSV summaries. Use `--resume` only for an interrupted run with the same
configuration; `--dry_run` checks paths and pair identities without inference.

### 4. Reliability analysis and protocol validation

Return to the main environment and use a new output directory for each analysis:

```bash
conda activate uav-talign
python scripts/build_ipt_p0d_protocol_artifacts.py \
  --input_dir ../runs/main_01 --output_dir ../runs/protocol_01
python scripts/evaluate_leave_frame_out_stability.py \
  --input_dir ../runs/main_01 --output_dir ../runs/leave_frame_out_01 --folds 5
python scripts/evaluate_synthetic_qa_perturbations.py \
  --dataset_root ../UAV-TAlign-12K --input_dir ../runs/main_01 \
  --output_dir ../runs/perturbations_01 --frames_per_scene 3 \
  --severities 2,5,10,20,40
```

The protocol analysis exports per-scene and condition tables, risk-coverage,
threshold sensitivity, and the canonical operating point. The **canonical QA
gate** defines the retained scene set; the **reliability score** ranks scenes
for operating-profile analysis. The score-ranked top-nine set and the nine
canonical retained scenes are not interchangeable.

For the full shared-runner method set, check output completeness with:

```bash
python scripts/check_prcv_main_outputs.py \
  --output_dir ../runs/main_01 --expect_pair_count 6037 --expect_scene_count 15
```

For a partial method run, pass `--required_methods` with the evaluated method
names. An independently completed replacement can be checked with
`--method_output_override METHOD=OUTPUT_DIR`. RIFT2 retains its independent
summary format rather than being passed to this validator.

## Reference Results

| Method | Homographies / pairs |
|---|---:|
| SIFT | 5,257 / 6,037 |
| AKAZE | 5,692 / 6,037 |
| RIFT2 (Python, resize-aware) | 6,037 / 6,037 |
| Kornia LoFTR (1200, AMP) | 5,984 / 6,037 |
| XoFTR-640 | 5,989 / 6,037 |
| RoMa outdoor full | 6,037 / 6,037 |
| raw MINIMA-RoMa full | 6,037 / 6,037 |

UAV-TAlign produces scene homographies for all 15 scenes and retains 9 under
the canonical criterion: 60.0% scene coverage and 74.4% pair coverage. Accepted
frame support is 1,491/2,304 (64.7%) within retained scenes and 2,473/3,847
(64.3%) across all scenes. The fixed eight-scene 1K-Lite ablation and the
five-fold stability analysis use different evaluation units.

## Code Map

| Entry | Purpose |
|---|---|
| `estimate_band_homographies.py` | Candidate scheduling, robust consensus, scene verification |
| `run_uav_talign_rectification.py` | Estimate, warp, and QA for a prepared scene |
| `build_rectified_band_dataset.py` | Warp infrared images and write validity masks |
| `qa_rectification.py` | Alignment diagnostics and visual QA |
| `run_prcv_main_experiment.py` | Shared pairwise/scene evaluation runner |
| `run_prcv_smoke_test.py` | Fixed-subset readiness check |
| `scripts/run_rift2_evaluation.py` | Independent frozen-profile RIFT2 evaluation |
| `scripts/build_ipt_p0d_protocol_artifacts.py` | Reliability score and operating profiles |
| `scripts/evaluate_leave_frame_out_stability.py` | Consensus resampling analysis |
| `scripts/evaluate_synthetic_qa_perturbations.py` | Controlled response of QA observables |
| `BENCHMARK_PROTOCOL.md` | Metric definitions and output schema |
| `DATASET_MANIFEST_SCHEMA.md` | Manifest fields and metadata |
| `third_party/MINIMA/` | Vendored MINIMA and matching dependencies |

The prepared-scene rectification entry expects `RGB/spectral_manifest.json`,
`RGB/images/`, `T_raw/spectral_manifest.json`, and `T_raw/images/`. The main
runner creates this intermediate representation under its output root.

## License

Original software is Apache-2.0 (`LICENSE`, `NOTICE`). Dataset and
project-authored non-software content are CC BY 4.0 (`LICENSE-CONTENT.md`).
Third-party code and pretrained weights retain their upstream terms; see
`THIRD_PARTY_NOTICES.md`. Optional non-redistributable SuperPoint/SuperGlue
components are not included and are not needed for the main MINIMA-RoMa path.
