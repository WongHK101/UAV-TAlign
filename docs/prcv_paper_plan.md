# PRCV Paper Plan for UAV-TAlign

## Working Title

UAV-TAlign: Reliable RGB-Thermal Registration for Cross-FOV UAV Imagery

## Target Venue

PRCV.

## Core Positioning

The paper should be positioned as a practical RGB-thermal registration method for real UAV imagery, not as a fully supervised benchmark paper. The dataset contribution should be framed as a curated 1000-image public subset, `UAV-TAlign-1K`, with a reproducible annotation-free evaluation protocol.

All deep baselines should follow an explicit off-the-shelf evaluation setup: public code, public pretrained weights, and no retraining or fine-tuning on UAV-TAlign.

## Main Claims

1. Real UAV RGB-T registration is harder than generic multimodal matching because of cross-FOV capture, cross-resolution sensors, weak texture in thermal images, grayscale/pseudocolor thermal renderings, and day/night/lowlight changes.
2. Strong off-the-shelf multimodal matchers already provide high pairwise availability, but reliable scene-level alignment remains the main bottleneck under UAV RGB-T conditions.
3. The strongest supported gains come from robust aggregation and QA-aware scene acceptance within a practical UAV-oriented pipeline.
4. UAV-TAlign-1K provides a practical public subset and label-free evaluation packaging for UAV RGB-T registration research without requiring manual landmark labels as a prerequisite.

## Contributions

1. A practical scene-level UAV RGB-thermal alignment pipeline that builds reliable alignment on top of strong off-the-shelf multimodal pairwise matching through robust aggregation and QA-aware scene acceptance.
2. UAV-TAlign-1K plus a practical label-free evaluation protocol for real UAV RGB-T alignment without requiring manual landmark annotations as a prerequisite.
3. Extensive off-the-shelf baseline comparisons, proxy-consistency analysis, and cumulative ablations showing that once pairwise availability is largely in place, the main challenge shifts to scene-level reliability and the strongest supported gains come from robust aggregation and reliability-aware decision.

## Paper Structure

### 1. Introduction

- Motivate UAV RGB-T alignment for inspection, monitoring, night operation, and multimodal fusion.
- Explain why real UAV RGB-T differs from standard visible-infrared registration datasets.
- State that manual GT is expensive and unstable for low-texture thermal UAV frames, so this paper adopts a reproducible label-free protocol for PRCV-scale contribution.
- Summarize method and dataset.

### 2. Related Work

- Classical feature-based registration: SIFT, SURF, ORB, KAZE/AKAZE, RANSAC homography.
- Deep matching and multimodal matching: SuperGlue, LightGlue, LoFTR, RoMa, XoFTR, MINIMA.
- Visible-thermal / infrared-visible registration datasets and benchmarks.
- UAV multimodal perception datasets.

### 3. Dataset: UAV-TAlign-1K

- Describe source capture conditions and subset policy.
- Report 15 scenes, 500 pairs, 1000 images.
- Report modality split: day/night/lowlight, grayscale/pseudocolor, wide/zoom for scenes 01-04.
- Explain directory schema and pair naming.
- Explain metadata stripping and privacy considerations.
- State limitation: no manual landmark GT in this PRCV version.

### 4. Method

#### 4.1 Problem Formulation

- Input: paired/sequenced RGB and thermal UAV images.
- Output: thermal-to-RGB homography or rectification transform.

#### 4.2 MINIMA Matching Backend

- Use MINIMA as the strong matcher.
- Convert/normalize RGB and thermal images to matching-compatible inputs.

#### 4.3 Deterministic and Adaptive Frame Selection

- Use evenly spaced candidates instead of pure random sampling.
- Frame deterministic selection as a reproducible default operating policy, not as the main claimed gain.
- Use all frames for small scenes when feasible.
- Expand candidate count when match/stability/QA criteria are not sufficient.

#### 4.4 Robust Homography Estimation

- Per-pair MINIMA matches.
- USAC/MAGSAC or RANSAC.
- Inlier ratio, reprojection error, coverage checks.
- Robust aggregation across frame-level homographies.

#### 4.5 Baseline-Aware QA

- Compare optimized transform against weak H0 only as diagnostic when H0 is naive.
- Use match quality, stability, severe outlier ratio, edge floor, and gradient-improvement ratio.
- Save `pass`, `pass_with_warning`, and `fail` states.

### 5. Evaluation Protocol

#### 5.1 Label-Free Metrics

- Accepted match ratio.
- Mean/median inlier ratio.
- Reprojection error.
- Spatial coverage.
- Homography stability: displacement to aggregate, robust reject ratio.
- Cross-modal alignment proxies: edge F1 delta, gradient NCC delta.
- Failure rate and warning rate.

#### 5.2 Visual QA

- RGB/thermal overlays.
- Edge overlays.
- Before/after rectification panels.
- Failure-case panels.

#### 5.3 Runtime

- Matching time per pair.
- Scene-level rectification time.
- Candidate expansion overhead.

### 6. Experiments

#### 6.1 Baselines

Classical:

- SIFT + RANSAC.
- KAZE or AKAZE + RANSAC.
- ORB + RANSAC as an optional lightweight baseline.
- ECC/MI-based image alignment only if stable enough.

Learning-based:

- LoFTR.
- RoMa.
- official XoFTR.
- MINIMA raw matching.

Do not include `LightGlue` in the first-wave main experiment package.

Ours:

- MINIMA + naive accepted-count aggregation.
- UAV-TAlign full pipeline.

#### 6.2 Main Results

- Table by method over all 500 pairs or by scene-level aggregation.
- Report success rate, edge/grad proxy improvements, stability, and runtime.
- Separate day/night/lowlight.
- Separate grayscale/pseudocolor thermal.
- Separate wide/zoom cross-FOV scenes.

#### 6.3 Ablations

Group A, candidate strategy:

1. Random 30-frame sampling vs deterministic even sampling.
2. Fixed 30 candidates vs adaptive/all candidates.

Group B, geometry estimation:

1. Single/best-frame MINIMA output vs multi-frame aggregation.
2. Direct MINIMA homography aggregation vs robust aggregation.
3. With/without stability filtering.

Group C, QA and decision:

1. Accepted-count-only stopping vs match + stability + QA stopping.
2. Strict H0 hard gate vs baseline-aware QA.
3. With/without severe-outlier ratio allowance.

Cumulative ablation:

1. Raw MINIMA direct output.
2. MINIMA + deterministic/even candidate strategy only.
3. MINIMA + deterministic/even candidates + robust aggregation.
4. MINIMA + deterministic/even candidates + robust aggregation + baseline-aware QA.
5. Full UAV-TAlign.
6. Random-selection sensitivity only as a reproducibility supplement, not as a headline gain claim.

#### 6.4 Robustness Analysis

- Cross-FOV wide vs zoom.
- Night and lowlight.
- Grayscale vs pseudocolor thermal.
- Low-texture thermal frames.
- Repetitive structures such as solar panels and towers.

#### 6.5 Qualitative Results

- 4-6 representative scenes.
- Show challenging cases where raw MINIMA or classical methods fail.
- Include failure cases of UAV-TAlign.

### 7. Limitations

- No dense or sparse manual GT in this PRCV version.
- Homography may be insufficient for strong parallax and non-planar scenes.
- Thermal pseudocolor may depend on camera rendering settings.
- Evaluation proxies are not absolute registration accuracy.

### 8. Conclusion

- Summarize practical contribution.
- State that future work will add a manually verified GT subset and extend beyond homography when needed.

## Priority Experiment Schedule

0.5. Run a small smoke test on 2-3 representative scenes before any full-scene launch.
1. Prepare evaluation scripts for UAV-TAlign-1K.
2. Run raw MINIMA vs UAV-TAlign full over all 15 scenes / 500 pairs.
3. Generate 6-8 representative visual panels for raw MINIMA vs UAV-TAlign.
4. Run classical baselines.
5. Run ready-to-use learning baselines: LoFTR, RoMa, official XoFTR.
6. Build scene-level and condition-level tables.
7. Run cumulative ablations on scenes 01-04, 07, 08, 13, and 14 first.
8. Add proxy-consistency protocol validation.
9. Only if needed, add a small blind visual preference review as rebuttal-oriented backup evidence.
10. Stop experiment expansion once proxy and ablation lines are complete; prioritize paper writing.

## Minimum PRCV Submission Package

- Method: full UAV-TAlign pipeline.
- Dataset: UAV-TAlign-1K.
- Baselines: SIFT, KAZE/AKAZE, LoFTR, RoMa, XoFTR, raw MINIMA.
- Metrics: success rate, inlier ratio, reprojection error, coverage, homography stability, edge F1 delta, grad NCC delta, runtime.
- Visuals: before/after overlays, edge overlays, raw MINIMA vs UAV-TAlign panels, and failure cases.
- Protocol credibility: proxy-consistency analysis, with a small blind visual review reserved as a low-cost fallback.
- Reporting note: keep official XoFTR and raw MINIMA in the main table; reserve MINIMA-XoFTR for source-method dissection or appendix if needed.

## Stronger Version

- Add LightGlue only if the first-wave package is already complete and stable.
- Add pseudo-GT consensus analysis.
- Add more fine-grained runtime/memory comparison.
- Release reproducible scripts and subset mapping.
