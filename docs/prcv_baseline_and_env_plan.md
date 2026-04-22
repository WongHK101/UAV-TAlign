# PRCV Baseline and Environment Plan

## Current Constraint

The PRCV experiments should use ready-to-run baselines only:

- public implementation;
- inference entry point or callable model API;
- public pretrained weights when learning-based;
- no manual annotation on UAV-TAlign;
- no retraining or fine-tuning on UAV-TAlign;
- same downstream homography fitting and QA protocol where possible.

GPU jobs are paused until the user confirms available GPUs.

## Baseline Tiers

The first-wave PRCV experiment set should use an explicit off-the-shelf evaluation setup:

- official public code or a clearly documented public implementation;
- official/public pretrained weights when the method is learning-based;
- no training, fine-tuning, or adaptation on UAV-TAlign;
- identical downstream homography fitting and failure handling when possible.

### Main Baselines

1. **SIFT + RANSAC/USAC-MAGSAC**
   - Status: ready through OpenCV.
   - Role: classical sparse-feature baseline.

2. **AKAZE/KAZE + RANSAC/USAC-MAGSAC**
   - Status: ready through OpenCV.
   - Role: stronger classical local-feature baseline than ORB for this paper.

3. **LoFTR**
   - Status: public code and pretrained weights are available; Kornia integration is installed in the server environment.
   - Planned variant: pretrained outdoor LoFTR, no UAV-TAlign training.
   - Role: widely recognized semi-dense deep matcher.

4. **RoMa**
   - Status: public code and pretrained weights are available; MINIMA vendors a RoMa implementation, but standalone `romatch` is not installed yet.
   - Planned variant: official pretrained outdoor RoMa if package/weights install cleanly; if the official path becomes engineering-heavy, lower its priority rather than turning it into a custom port.
   - Role: strong modern dense matcher.

5. **XoFTR**
   - Status: public implementation, pretrained weights, and visible-thermal design; MINIMA vendors XoFTR code and a MINIMA XoFTR checkpoint.
   - Planned variant: official XoFTR pretrained model for a pure XoFTR baseline if weights are reachable.
   - Reporting note: official XoFTR and MINIMA-XoFTR must be treated as conceptually different methods; MINIMA-XoFTR belongs in source-method dissection or appendix, not the main table by default.
   - Role: main RGB/TIR-specific deep matcher.

6. **Raw MINIMA**
   - Status: local and server code include MINIMA; local weights currently include `minima_roma.pth` and `minima_xoftr.ckpt`.
   - Planned variant: direct MINIMA matching plus homography estimation, without UAV-TAlign candidate selection, robust multi-frame aggregation, adaptive stopping, or baseline-aware QA.
   - Role: source-method baseline and the most important comparison for proving UAV-TAlign is not a wrapper.

7. **UAV-TAlign Full**
   - Status: current method.
   - Role: full pipeline with deterministic/even frame selection, adaptive candidates, robust aggregation, stability diagnostics, and baseline-aware QA.

### Optional Baselines

1. **ORB + RANSAC**
   - Easy to run, but lower priority than SIFT and AKAZE/KAZE.
   - Only add if the classical baseline script is already stable and the marginal cost is near zero.

2. **ECC / MI alignment**
   - Include only if it runs robustly under the same automation and failure reporting.
   - Do not let an unstable optimizer dominate engineering time.

Methods intentionally removed from the first-wave plan:

- `LightGlue`: public and runnable, but not thermal-specific; it does not justify the current engineering budget.

## Experimental Order After GPUs Are Free

0.5. **Smoke test first**
   - Run 2-3 representative scenes with a small number of pairs per scene.
   - Confirm LoFTR, RoMa, XoFTR, raw MINIMA, and UAV-TAlign can all produce parseable outputs or explicit failure codes.
   - Confirm the homography fitting interface, empty-match handling, logs, and JSON schema are unified.

1. Raw MINIMA vs UAV-TAlign full on all 15 scenes / 500 RGB-T pairs.
2. SIFT, AKAZE/KAZE, LoFTR, RoMa, XoFTR on the same pairs.
3. Condition splits: day/night/lowlight, grayscale/pseudocolor, wide/zoom.
4. Cumulative ablation:
   - raw MINIMA direct;
   - MINIMA + deterministic/even candidate strategy;
   - MINIMA + deterministic candidates + robust aggregation;
   - MINIMA + deterministic/even candidates + robust aggregation + baseline-aware QA;
   - full UAV-TAlign.
5. Protocol credibility check without manual landmarks:
   - proxy consistency analysis first;
   - keep a 50-100 pair blind visual preference/success review only as a fallback if proxy trends are not persuasive enough.

## Environment Readiness

Server path:

- code/data root: `/home/user2/whk/UAV-TAlign`
- dataset symlink: `/home/user2/whk/datasets/UAV-TAlign-1K`
- conda environment: `uav-talign`

Verified imports in `uav-talign`:

- `cv2`: OK
- `torch`: OK
- `kornia`: OK
- `einops`: OK
- `yacs`: OK
- `pytorch_lightning`: OK
- `lightglue`: missing as standalone package
- `romatch`: missing as standalone package

Important server note:

- `/home/user2/whk/UAV-TAlign` currently contains copied code and data, but is not a Git working tree. Before full experiments, sync or convert this path to a tracked code checkout so exact code state can be recovered.

## Current Consensus

1. XoFTR is a main baseline, not an optional one.
2. The first-wave main baseline set is:
   - SIFT + RANSAC/USAC-MAGSAC
   - AKAZE/KAZE + RANSAC/USAC-MAGSAC
   - LoFTR pretrained outdoor
   - RoMa pretrained outdoor
   - official XoFTR pretrained
   - raw MINIMA direct matching
   - UAV-TAlign full
3. LightGlue is removed from the first-wave plan to control engineering scope.
4. official XoFTR and MINIMA-XoFTR must be separated conceptually; the default main table should keep official XoFTR and raw MINIMA, while MINIMA-XoFTR is only for source-method dissection if needed.
5. The first protocol-credibility step is proxy consistency analysis; blind visual review stays as a reserve option, not a front-loaded requirement.
