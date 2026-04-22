# README-paper

## Purpose

This package is a lightweight paper-writing handoff for the PRCV version of `UAV-TAlign`.
It is meant to help a writing assistant start drafting the paper without receiving the raw
datasets, model weights, caches, or large experiment outputs.

The package is intentionally focused on:

- the current 2D RGB-thermal alignment codebase
- the PRCV paper plan and baseline protocol
- the exact wording constraints that are currently safest
- the latest cumulative ablation summary and GPT audit brief
- the code entry points needed to understand the method and evaluation setup

## Scope of This Paper

The paper scope is the later **2D alignment** line, not the earlier multispectral / 3DGS line.
When describing the work, treat the earlier multispectral direction only as historical context.
The actual PRCV submission target is a standalone UAV RGB-thermal registration paper centered on:

- `UAV-TAlign` as the full pipeline
- `UAV-TAlign-1K` as the public subset / evaluation package
- off-the-shelf baselines with public pretrained weights and no retraining

Working title:

- `UAV-TAlign: Reliable RGB-Thermal Registration for Cross-FOV UAV Imagery`

## Safe Writing Positioning

These points are currently safe to write as the main paper narrative:

1. UAV RGB-thermal registration is hard because of cross-FOV mismatch, cross-resolution sensors,
   weak thermal texture, grayscale vs pseudocolor renderings, and day/night/lowlight variation.
2. The proposed method is not a brand-new matcher. It is a UAV-oriented registration pipeline
   built on top of strong off-the-shelf multimodal matching.
3. The key pipeline additions are deterministic frame selection, adaptive candidate expansion,
   robust homography aggregation, and baseline-aware QA / acceptance logic.
4. The PRCV version should be framed as a practical, label-free, reproducible evaluation package,
   not as a fully supervised benchmark with manual geometric ground truth.

## Wording Constraints

Please keep the following wording strict and consistent.

### Method naming

- `UAV-TAlign full pipeline`
- `raw MINIMA`
- `Kornia LoFTR (pretrained="outdoor")`
- `official pretrained RoMa via local wrapper`
- `official pretrained XoFTR-640 via local wrapper`

Do **not** casually rewrite these as:

- `official LoFTR repo`
- `official RoMa repo`
- `official XoFTR repo`
- `all baselines run exactly from untouched official scripts`

That wording would be too strong for the current implementation state.

### Weight / backend choices

Current frozen baseline choices are:

- `raw MINIMA`:
  - backend: `RoMa`
  - size: `large/full`
  - checkpoint family: `minima_roma`
- `RoMa baseline`:
  - model: `roma_outdoor`
- `official XoFTR baseline`:
  - checkpoint: `weights_xoftr_640.ckpt`
- `LoFTR baseline`:
  - `kornia.feature.LoFTR(pretrained="outdoor")`
  - resize-aware inference setting for the current formal result: `match_max_dim=1600`, `use_amp=false`

For the paper, `XoFTR-640` should be treated as the main official XoFTR setting.
`XoFTR-840` is a sensitivity / alternative setting, not the default main-table weight.

### What not to overclaim

- Do not claim manual point-level or dense ground truth.
- Do not claim full determinism across all hardware / third-party kernels.
- Do not claim that every baseline was run from a fully isolated repo + fully isolated env.
- Do not treat the tiny smoke subset as the basis for formal quality conclusions.

## Current Experiment Status

The paper assistant can start writing **Introduction / Related Work / Method / Dataset / Protocol**
immediately, and the first-wave baseline package is now stable enough to support draft result tables.

Current verified formal snapshot:

- `raw_minima`: `500/500 ok`
- `uav_talign_full`: `15/15 scenes finished`, `7 ok`, `8 canonical_fail`
- `sift_ransac`: `457 ok`, `22 fit_failed`, `11 insufficient_matches`, `3 no_matches`, `7 error`
- `akaze_ransac`: `479 ok`, `7 fit_failed`, `8 insufficient_matches`, `6 no_matches`
- `roma_outdoor`: `500/500 ok`
- `xoftr_official (640)`: `494 ok`, `4 insufficient_matches`, `2 no_matches`
- `loftr_outdoor`: `499 ok`, `1 insufficient_matches`, `0` OOM in the bounded salvage run
- cumulative ablation wave on the fixed 8-scene subset:
  - `A1`: `8/8`
  - `A2`: `8/8`
  - `A3`: `5/8`
  - `S1 (seed 0)`: `6/8`
- multi-seed random-selection supplement on the same fixed subset:
  - `seed 1`: `4/8`
  - `seed 2`: `7/8`
  - `seed 3`: `5/8`

Important interpretation:

- the earlier local-to-server sync discrepancy was limited to runner-level isolation / metadata code
  in `run_prcv_main_experiment.py` and `run_prcv_smoke_test.py`
- sync-rerun verification already confirmed the previously completed baseline waves instead of
  overturning them
- the former `LoFTR 500/500 error` result should now be treated as superseded by the later
  resize-aware formal salvage run

For writing, the safest current practice is:

- treat the baseline setup and naming as frozen
- treat the current numeric snapshot as a stable draft result package
- explicitly state that the reported `LoFTR` full-run result uses resize-aware inference
  (`match_max_dim=1600`, `use_amp=false`)
- use `docs/prcv_results_discussion_skeleton.md` as the first writing scaffold for the
  `Results` / `Discussion` sections
- use `docs/prcv_abstract_contributions_final.md` for the final abstract / contribution wording
- use `docs/prcv_opening_sections_draft.md` for near-paper-ready opening text covering title,
  abstract, introduction opening, contribution bullets, and results opening paragraphs
- use `docs/prcv_dataset_protocol_draft.md` for the paper-facing `Dataset` and `Evaluation Protocol`
  draft
- use `docs/prcv_method_draft.md` for code-grounded `Method` section drafting
- use `docs/prcv_related_work_draft.md` for the paper-facing `Related Work` draft and positioning
- use `docs/prcv_baseline_setup_experiment_details_draft.md` for the paper-facing `Baselines` and
  `Implementation Details` sections
- use `docs/prcv_ablation_table_schema.md` to keep the cumulative ablation summary format fixed
  as the schema reference
- use `docs/prcv_ablation_results_final.md` as the current paper-facing ablation reading
- use `docs/prcv_gpt_audit_brief_20260422.md` when asking GPT to audit writing strategy,
  claim strength, and whether more experiments are still necessary
- use `docs/prcv_gpt_forward_message_20260422.md` as the ready-to-send transfer text
- use `review_artifacts/prcv_ablation_structuring_20260422_031955/` for the lightweight machine-
  readable ablation summary
- use `review_artifacts/prcv_s1_multiseed_structuring_20260422_044924/` for the completed
  random-selection sensitivity supplement

## Code Map

Read these files first for the paper draft.

### Main method and evaluation entry points

- `estimate_band_homographies.py`
- `run_uav_talign_rectification.py`
- `run_prcv_main_experiment.py`
- `run_prcv_smoke_test.py`
- `build_rectified_band_dataset.py`
- `qa_rectification.py`

### Core local utilities

- `utils/minima_bridge.py`
- `utils/minima_match_utils.py`
- `utils/rectification_utils.py`
- `utils/baseline_backends.py`
- `utils/uav_talign_dataset.py`
- `utils/prepared_scene_adapter.py`
- `utils/spectral_image_utils.py`

### Third-party patched reference files

These are included because they affect how the local experiments are run:

- `third_party/MINIMA/load_model.py`
- `third_party/MINIMA/src/utils/data_io.py`
- `third_party/MINIMA/src/utils/data_io_loftr.py`
- `third_party/MINIMA/src/utils/data_io_roma.py`
- `third_party/MINIMA/src/utils/data_io_sp_lg.py`
- `third_party/MINIMA/third_party/RoMa_minima/romatch/utils/kde.py`

## Recommended Writing Order

1. Use `docs/prcv_paper_plan.md` as the main structural outline.
2. Use `docs/prcv_opening_sections_draft.md` to seed title, abstract, intro opening, and results
   opening prose.
3. Use `docs/prcv_related_work_draft.md` to draft the `Related Work` section.
4. Use `docs/prcv_dataset_protocol_draft.md` to draft the `Dataset` and `Evaluation Protocol`
   sections.
5. Use `docs/prcv_method_draft.md` to draft the `Method` section.
6. Use `docs/prcv_baseline_setup_experiment_details_draft.md` to draft the `Baselines` and
   `Implementation Details` sections.
7. Use `docs/prcv_results_discussion_skeleton.md` to draft the `Results` / `Discussion` sections.
8. Use `docs/prcv_ablation_table_schema.md` to keep the future ablation reporting format stable.
9. Use the experiment snapshot in this file only as a temporary scaffold for result-table wording.
10. Keep final quantitative wording easy to refresh while proxy-credibility analysis and ablations
   are still being expanded.

## What Is Omitted from This Package

The package deliberately excludes:

- raw datasets
- image subsets
- model weights
- caches
- `.git`
- experiment output directories
- large third-party trees that are not needed for paper drafting

This means the package is **for understanding and writing**, not for one-click reproduction.

## Included Package Files

The archive should include:

- core local method code
- PRCV experiment runners
- relevant utility modules
- the small set of patched third-party files that materially affect the current setup
- planning documents in `docs/`
- `docs/prcv_results_discussion_skeleton.md`
- `docs/prcv_abstract_contributions_final.md`
- `docs/prcv_opening_sections_draft.md`
- `docs/prcv_dataset_protocol_draft.md`
- `docs/prcv_method_draft.md`
- `docs/prcv_related_work_draft.md`
- `docs/prcv_baseline_setup_experiment_details_draft.md`
- `docs/prcv_ablation_table_schema.md`
- `docs/prcv_ablation_results_final.md`
- `docs/prcv_gpt_audit_brief_20260422.md`
- `docs/prcv_gpt_forward_message_20260422.md`
- `review_artifacts/prcv_s1_multiseed_structuring_20260422_044924/`
- `README-paper.md`
- `THIRD_PARTY_NOTICES.md`
- environment metadata files

## Final Reminder for the Writing Assistant

Treat the following as the current safest paper-level message:

- `UAV-TAlign` is a practical UAV RGB-thermal registration pipeline built on top of strong public
  multimodal matchers.
- The PRCV contribution is the pipeline, the evaluation protocol, and the `UAV-TAlign-1K` subset.
- The first writing pass should emphasize motivation, method design, protocol clarity, and careful
  wording, while treating the current result tables as stable draft evidence rather than final camera-ready wording.
