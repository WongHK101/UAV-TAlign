# UAV-TAlign-12K Experiment Plan

**For:** Collaborator running experiments on GPU server
**Repository:** https://github.com/WongHK101/UAV-TAlign
**Target:** Provide all outputs needed to complete the paper (Infrared Physics & Technology, deadline 2026-07-22)
**Contact:** If any checkpoint fails or numbers diverge significantly from expected values, stop and ask before proceeding.

---

## Quick Start

```bash
git clone git@github.com:WongHK101/UAV-TAlign.git
cd UAV-TAlign
conda env create -f environment.yml
conda activate uav-talign
# Place weights:
#   third_party/MINIMA/weights/minima_roma.pth
#   third_party/MINIMA/weights/minima_xoftr.ckpt
#   <your path>/weights_xoftr_640.ckpt
```

Current audited Windows 4090 host note:

- The runnable environment on `G:\UAV-TAlign` is the prefix environment
  `G:\UAV-TAlign\uav_talign_envs\uav-talign-e10a8be-py310`.
- On that host, prefer `conda run -p ...` or the PowerShell launchers under
  `scripts/`; do not assume `conda run -n uav-talign` exists.

Verify environment and data before any real run:

```bash
python run_prcv_smoke_test.py \
  --dataset_root /path/to/UAV-TAlign-12K \
  --manifest_path manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json \
  --output_root outputs/smoke_verify \
  --methods sift_ransac,akaze_ransac \
  --device cuda
```

**Smoke checkpoint:** Confirm `manifest_sha256` in the summary equals
`a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c`.
On the currently audited Windows 4090 host, the accepted smoke reference is:

- `akaze_ransac`: `15/15 ok`
- `sift_ransac`: `14 ok + 1 fit_failed`
- the isolated SIFT failure is scene `13_lowlight_pseudocolor_road_469`, pair
  `000235`, and does not block the formal 12K run

---

## Experiment Priority and Sequencing

Run experiments in priority order. Each experiment depends on the previous one completing successfully.

---

### P1 — Main 12K Experiment (BLOCKING everything else)

**Why first:** All Supplement CSVs (S2–S4, S8) and the post-processing script depend on this output.

```bash
python run_prcv_main_experiment.py \
  --dataset_root /path/to/UAV-TAlign-12K \
  --manifest_path manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json \
  --output_root outputs/ipt_p0c_12k_main \
  --methods sift_ransac,akaze_ransac,loftr_outdoor,roma_outdoor,xoftr_official,raw_minima,uav_talign_full \
  --device cuda \
  --seed 0 \
  --official_xoftr_ckpt /path/to/weights_xoftr_640.ckpt
```

Current Windows 4090 host shortcut:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\server_run_prcv_main_12k_windows.ps1 `
  -DatasetRoot G:\UAV-TAlign\UAV-TAlign-12K `
  -OfficialXoftrCkpt <PATH_TO_WEIGHTS_XOFTR_640_CKPT>
```

The Windows launcher uses the audited prefix environment, writes stdout/stderr
to separate `_launcher` logs, and validates the finished output package with
`scripts/check_prcv_main_outputs.py`.

**Estimated runtime (RTX 4090):** 4–6 hours total for all methods.

**Checkpoint — must pass before P2:**

| Method | Expected H availability | Tolerance |
|---|---|---|
| sift_ransac | ~87% | ±2% |
| akaze_ransac | ~94% | ±2% |
| RIFT2* | 100% | 0% |
| loftr_outdoor | ~99.5% | ±1% |
| roma_outdoor | 100% | 0% |
| raw_minima | 100% | 0% |
| xoftr_official | ~99.2% | ±1% |
| uav_talign_full | 15/15 H available, 9/15 retained | ±0 retained |

*RIFT2 runs separately — see P1-B below.

**Required output files:**
```
outputs/ipt_p0c_12k_main/
  main_experiment_summary.json                     ← REQUIRED for P2
  sift_ransac/results.jsonl
  akaze_ransac/results.jsonl
  loftr_outdoor/results.jsonl
  roma_outdoor/results.jsonl
  xoftr_official/results.jsonl
  raw_minima/results.jsonl
  uav_talign_full/results.jsonl
  uav_talign_full/scene_results.jsonl
  uav_talign_full_scene_metrics_detailed.jsonl
```

---

### P1-B — RIFT2 Full 12K Run (runs in parallel with P1 or after)

RIFT2 uses a separate Python environment and is not in `create_pairwise_matcher`. Run with your existing RIFT2 setup. Paper configuration (must match exactly):

- `max_dim=1200`
- `npt=2000`
- `patch_size=64`
- Lowe ratio: `0.95`
- Homography backend: OpenCV `USAC-MAGSAC`, `reproj_threshold=3.0`, `confidence=0.999`, `max_iter=10000`

Output must conform to the same `pair_result_record` schema as other pairwise methods (see `BENCHMARK_PROTOCOL.md §3 Track A`). Store results as:
```
outputs/ipt_p0c_12k_main/rift2/results.jsonl
outputs/ipt_p0c_12k_main/rift2/summary.json
```

**Checkpoint:** 6037/6037 pairs processed, `homography_available=true` for all, `mean inlier_ratio ≈ 0.086`, `mean coverage ≈ 0.354`.

**Also run RIFT2 sanity check (for Supplement S5):**

Run two configurations on a fixed 100-pair subset (any scene):
- Light: `max_dim=800`
- Strong: `max_dim=1200` (main-table setting)

Output both to: `outputs/rift2_sanity/light/` and `outputs/rift2_sanity/strong/`

---

### P2 — Protocol Artifact Generation (requires P1 main output)

```bash
python scripts/build_ipt_p0d_protocol_artifacts.py \
  --input_dir outputs/ipt_p0c_12k_main \
  --output_dir outputs/ipt_p0d_protocol_closure
```

Current Windows 4090 host shortcut:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\server_run_prcv_protocol_artifacts_windows.ps1 `
  -InputDir G:\UAV-TAlign\UAV-TAlign\outputs\ipt_p0c_12k_main `
  -OutputDir G:\UAV-TAlign\UAV-TAlign\outputs\ipt_p0d_protocol_closure
```

**Runtime:** < 5 minutes.

**Checkpoint — verify all 7 output files exist:**
```
outputs/ipt_p0d_protocol_closure/
  per_scene_reliability_table.csv      ← Supplement S3
  threshold_sensitivity.csv            ← Supplement S2
  condition_reliability_profile.csv    ← Supplement S4
  risk_coverage.csv                    ← paper Figure (risk-coverage curve)
  canonical_operating_point.csv
  paper_facing_summary.md
  reliability_score_design.md          ← Supplement S1 (if generated)
```

Open `paper_facing_summary.md` and confirm:
- `retained_scenes = 9`
- `retention_rate = 60.0%`
- `accepted_frames = 2473`, `accepted_ratio ≈ 64.3%`

If these numbers differ from the paper values, **stop and report** before continuing.

---

### P3 — Ablation Wave (requires P1 environment, independent of P2)

This produces the cumulative ablation table (already in the paper, but re-run validates reproducibility).

```bash
ENV_PREFIX=/path/to/prefix-env \
OUTPUT_ROOT=outputs/ipt_ablation_wave \
bash scripts/server_run_prcv_ablation_wave.sh
```

The script runs 4 variants on the fixed 1K-Lite / 8-scene subset:
1. Evidence selection only
2. + Robust scene consensus
3. + QA-aware verification
4. UAV-TAlign full

**Checkpoint:** Variant 4 should match paper Table 4:
- `5/8 retained`, `accepted_ratio ≈ 80.4%`, `delta_edge ≈ 0.147`, `delta_grad ≈ 0.149`, `severe ≈ 4.2`

---

### P4 — Multi-Seed Sensitivity Supplement (requires P1 environment)

```bash
ENV_PREFIX=/path/to/prefix-env \
OUTPUT_ROOT=outputs/ipt_multiseed \
bash scripts/server_run_prcv_s1_multiseed.sh
```

Runs the same 8-scene subset with random frame selection over multiple seeds.

**Checkpoint:** Seed spread should show `4/8–7/8` retained scenes across seeds (paper reports this spread).

---

## Return Package

When all experiments are done, send back the following directories (tar or rsync):

```
outputs/ipt_p0c_12k_main/           ← full P1 output
outputs/ipt_p0d_protocol_closure/   ← full P2 output
outputs/rift2_sanity/               ← P1-B sanity
outputs/ipt_ablation_wave/          ← P3
outputs/ipt_multiseed/              ← P4
```

---

## Acceptance Criteria (Full Checklist)

Before sending results, verify each item:

- [ ] `manifest_sha256` in `main_experiment_summary.json` == `a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c`
- [ ] Total pairwise records per method == **6037** (not 6039)
- [ ] `uav_talign_full/results.jsonl` has exactly **15 lines**
- [ ] `uav_talign_full/scene_results.jsonl` has exactly **15 lines**
- [ ] `uav_talign_full_scene_metrics_detailed.jsonl` has exactly **15 lines**
- [ ] `retained_scenes = 9/15` in `paper_facing_summary.md`
- [ ] `per_scene_reliability_table.csv` has 15 rows
- [ ] `threshold_sensitivity.csv` exists and is non-empty
- [ ] `condition_reliability_profile.csv` exists and covers `light_condition`, `thermal_rendering`, `view_type`, `scene_family`
- [ ] Ablation variant 4 matches paper Table 4 values (within ±0.002)
- [ ] RIFT2: 6037/6037 records, `homography_available=true` for all

---

## Reference: Paper-Facing Numbers to Preserve

These are the published results. New runs must match within the stated tolerance.

**Table 1 — Pairwise baselines:**

| Method | H % | Inlier Ratio | Coverage | Median Reproj |
|---|---|---|---|---|
| SIFT | 87.08 | 0.242 | 0.627 | 0.000 |
| AKAZE | 94.29 | 0.160 | 0.730 | 0.105 |
| RIFT2 | 100.00 | 0.086 | 0.354 | 0.121 |
| raw MINIMA | 100.00 | 0.319 | 1.000 | 1.775 |
| RoMa | 100.00 | 0.328 | 0.997 | 1.739 |
| LoFTR | 99.54 | 0.099 | 0.922 | 1.405 |
| XoFTR | 99.20 | 0.089 | 0.949 | 1.732 |

**Table 2 — Scene-level (UAV-TAlign full):**
`15/15 H available · 9/15 retained · 60.0% · 2473/3847 accepted · 64.3%`

**Table 3 — Condition breakdown:**
`Day: 5/7 retained, 71.4% · Night: 3/5, 60.0% · Low-light: 1/3, 33.3%`
