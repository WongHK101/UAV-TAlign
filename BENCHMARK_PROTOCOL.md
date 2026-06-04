# UAV-TAlign-12K Benchmark Protocol

This document defines the public benchmark protocol for **UAV-TAlign-12K**, the cross-FOV
UAV infrared-visible alignment benchmark released with this repository. It is the
authoritative specification for what to evaluate, how to evaluate, and what to report.
The companion file `DATASET_MANIFEST_SCHEMA.md` covers the dataset metadata schema; this
file covers the benchmark schema layered on top of it.

---

## 1. Official Data Anchor

All formal results must reference the official manifest and its canonical SHA256.

| Field | Value |
|---|---|
| Dataset | `UAV-TAlign-12K` |
| Official manifest | `manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json` |
| Manifest canonical SHA256 | `a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c` |
| Hash convention | canonical JSON (compact form, `sort_keys=True`, UTF-8) |
| Candidate pairs | 6,039 / 12,078 images |
| Official evaluation split | **6,037** valid pairs / **12,074** images |
| Integrity-excluded pairs | 2 (scene 13, pair 000058 and 000080) |
| Duplicate-hash diagnostic | 1 group (scene 05, thermal 000905/000906; record_only_not_excluded) |
| Scenes | 15 |

**Important:** the published SHA256 is computed over the canonical JSON serialization of the
manifest, **not** the raw file bytes. A reference implementation lives in
`utils/uav_talign_dataset._canonical_manifest_sha256`. Verify with:

```python
import json, hashlib
m = json.loads(open('manifests/UAV-TAlign-12K_official_valid_evaluation_manifest.json').read())
sha = hashlib.sha256(
    json.dumps(m, separators=(',', ':'), sort_keys=True, ensure_ascii=False).encode('utf-8')
).hexdigest()
assert sha == 'a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c'
```

Direct folder traversal must not replace the manifest entry. Doing so would silently change
the evaluated pair set.

---

## 2. Scene Metadata

Each scene exposes the following metadata via the manifest. Both legacy and protocol-aligned
field names are emitted by the runner so existing consumers continue to work.

| Protocol field | Manifest field | Type | Enumeration |
|---|---|---|---|
| `scene_id` | `scene_id` | string | `01`–`15` |
| `scene_name` | `scene_name` | string | full directory name |
| `light_condition` | `light_condition` | string | `day` / `night` / `lowlight` |
| `thermal_rendering` | `thermal_rendering` | string | `grayscale` / `pseudocolor` |
| `view_type` | `view` | string | `wide` / `zoom` / `standard` |
| `scene_family` | `scene_label` | string | see scene_family enumeration below |
| `pair_count` | `pair_count` | int | per-scene valid pair count |

**scene_family enumeration (9 values):**
`substation_power_lines` · `solar_panels` · `transmission_tower` · `urban` · `building` ·
`factory` · `orchard` · `road` · `woodland`

**Conditional distribution (used to validate any new run):**

| `light_condition` | scenes | valid pairs |
|---|---:|---:|
| `day` | 7 | 2,703 |
| `night` | 5 | 2,008 |
| `lowlight` | 3 | 1,326 |

| `thermal_rendering` | scenes | valid pairs |
|---|---:|---:|
| `grayscale` | 8 | 1,483 |
| `pseudocolor` | 7 | 4,554 |

**`view_type` semantics.** `wide` and `zoom` are the only single-variable controlled
comparison in UAV-TAlign-12K: scenes 01–04 capture the same substation/power-line target
in the same flight session under wide-angle and zoom-lens settings, day and night, with
45–50 valid pairs each. `standard` covers the remaining 11 scenes (5,847 pairs) under
regular UAV nadir/oblique viewpoints.

---

## 3. Three Evaluation Tracks

### Track A — Pairwise Homography Evidence

**Question.** Can a method produce usable pairwise homography evidence on real UAV
infrared-visible pairs?

**Unit.** One independent evaluation per pair (6,037 pairs).

**Inputs.** RGB image, thermal image, manifest pair identity.

**Output schema (`pair_result_record`).** Each row of `results.jsonl` for a pairwise
method must contain at least:

```json
{
  "method": "string",
  "scene_id": "string",
  "scene_name": "string",
  "pair_id": "string",
  "rgb_path": "string",
  "thermal_path": "string",
  "light_condition": "string",
  "thermal_rendering": "string",
  "view": "string",
  "view_type": "string",
  "scene_label": "string",
  "scene_family": "string",
  "status": "ok | insufficient_matches | fit_failed | no_matches | error",
  "homography_available": true,
  "homography": [[3x3 float array or null]],
  "num_matches": 0,
  "num_inliers": 0,
  "inlier_ratio": 0.0,
  "reprojection_error": 0.0,
  "coverage": 0.0,
  "runtime_sec": 0.0
}
```

**Pair-level status codes.**

| Code | Meaning |
|---|---|
| `ok` | homography estimated, `homography_available=true` |
| `insufficient_matches` | matches below the robust-fitting minimum |
| `fit_failed` | enough matches, but robust homography fit failed |
| `no_matches` | matcher returned zero correspondences |
| `error` | runtime exception |

**Required main metrics.**
`OK / N` ↑ · `H availability (%)` ↑ · `mean inlier ratio` ↑ · `mean coverage` ↑ ·
`median reprojection error` ↓ · `runtime / pair (s)` ↓

### Track B — Scene-Level Retained Alignment

**Question.** Can a method produce a scene-level transform that should be retained?

**Unit.** One independent evaluation per scene (15 scenes).

**Inputs.** All pairs in a scene (per the manifest), scene metadata.

**Output schema (`scene_result_record`).**

```json
{
  "method": "string",
  "scene_id": "string",
  "scene_name": "string",
  "pair_id": "__scene__",
  "num_pairs_total": 0,
  "status": "pass | pass_with_warning | fail | canonical_fail | error",
  "num_matches": 0,
  "num_inliers": 0,
  "inlier_ratio": 0.0,
  "reprojection_error": 0.0,
  "coverage": 0.0,
  "homography_available": true,
  "homography": [[3x3 float array or null]],
  "qa_status": "string",
  "accepted_frames": 0,
  "num_attempted_frames": 0,
  "accepted_ratio": 0.0,
  "canonical_scene_pass": true,
  "canonical_failure_reason": "string or null",
  "source_pair_ids": ["list of pair_ids used"],
  "runtime_sec": 0.0
}
```

**Scene-level status codes.**

| Code | Meaning |
|---|---|
| `pass` | canonical gate passed, QA clean |
| `pass_with_warning` | canonical gate passed, QA emitted warning-side guards |
| `fail` | canonical gate failed without a specific reason |
| `canonical_fail` | canonical gate failed with a recorded `canonical_failure_reason` |
| `error` | runtime exception |

**Required main metrics.**
`H Available` ↑ · `Retained Scenes` ↑ · `Retention Rate (%)` ↑ · `Accepted Frames` ↑ ·
`Accepted Ratio (%)` ↑

### Track C — Reliability-Coverage Operating Profile

**Question.** How does coverage and risk evolve as the system relaxes its retention rule?

**Unit.** Scenes ranked by a non-trained reliability score, then swept.

**Required outputs.**

```json
{
  "scene_id": "string",
  "scene_name": "string",
  "reliability_score": 0.0,
  "reliability_rank": 1,
  "canonical_scene_pass": true,
  "accepted_ratio": 0.0,
  "severe_outlier_ratio": 0.0,
  "robust_reject_ratio": 0.0,
  "delta_edge": 0.0,
  "delta_grad": 0.0,
  "homography_dispersion": 0.0
}
```

**Required main metrics.**
`Scene coverage (%)` · `Pair coverage micro (%)` · `Mean severe outlier ratio` ·
`Mean robust reject ratio` · `Canonical pass fraction within retained`

**Visualization rule.** Risk-coverage curves must mark the canonical operating point
explicitly. The score-ranked top-K curve **does not replace** the canonical gate.

---

## 4. Canonical Gate vs Reliability Score (Critical Rule)

These three layers must not be conflated. Mixing them is the single most common way to
mis-report scene-level results.

| Layer | Symbol | Role | Where used |
|---|---|---|---|
| **Diagnostic observables** | `accepted_ratio`, `severe_outlier_ratio`, `delta_edge`, `delta_grad`, … | observation only | Supplement S3/S4 |
| **Canonical gate** | `y_S` | hard decision, fixed protocol rule | scene-level main result |
| **Reliability score** | `R(S)` | continuous ranking, sweep tool | risk-coverage figure |

- `y_S` is a fixed thresholded decision over diagnostics; it determines `Retained Scenes`.
- `R(S)` is a non-trained continuous score; it ranks scenes for risk-coverage analysis and
  threshold sweeps. **It never replaces `y_S` for main-table reporting.**
- Diagnostics support per-scene/per-condition breakdowns. They are not main-table results.

---

## 5. Required Statistical Views

Because UAV-TAlign-12K has imbalanced scene lengths (45–1,315 pairs per scene), every
formal report must include all four views:

- **micro** — pair-level direct average over all qualifying pairs
- **macro** — average over scenes (each scene weighted equally)
- **per-scene** — table with one row per scene
- **per-condition** — breakdown by `light_condition`, `thermal_rendering`, `view_type`,
  and `scene_family`

---

## 6. Reproducibility Manifest

All formal runs must record:

| Field | Source |
|---|---|
| `manifest_path` | manifest file path |
| `manifest_sha256` | canonical JSON hash (must match §1) |
| `code_commit_hash` | `git rev-parse HEAD` |
| `weights_provenance` | per-method checkpoint origin |
| `image_resize_policy` | per-method preprocessing |
| `robust_backend` | `USAC-MAGSAC` (reproj_threshold=3.0, confidence=0.999, max_iter=10000) |
| `scene_pass_policy` | canonical gate (fixed thresholds) |
| `qa_threshold_version` | QA bundle identifier |
| `seed` | random seed |
| `environment` | Python 3.10, PyTorch 2.0.1, CUDA 11.8, OpenCV 4.11.0, Kornia 0.6.11 |

`run_prcv_main_experiment.py` already records most of these into its summary JSON.

---

## 7. Reporting Stack

### Main paper (required)
1. Pairwise baseline main table (Track A)
2. Scene-level canonical main table (Track B)
3. Light condition breakdown table
4. Risk-coverage figure (Track C, with canonical operating point marked)
5. Cumulative ablation table

### Supplement (required)
1. Reliability score design (S1)
2. Threshold sensitivity sweep (S2)
3. Per-scene reliability details (S3)
4. Condition reliability profile (S4)
5. Manifest integrity summary (S6)
6. Qualitative examples (S7)
7. Classical keypoint completeness (S8)

---

## 8. Baseline Suite

| Group | Method | Track A | Track B/C |
|---|---|:-:|:-:|
| Classical keypoint | `sift_ransac` | ✓ | — |
| Classical keypoint | `akaze_ransac` | ✓ | — |
| Infrared-visible classical | `RIFT2 (Python, resize-aware)` | ✓ | — |
| Modern dense/learned | `loftr_outdoor` | ✓ | — |
| Modern dense/learned | `roma_outdoor` | ✓ | — |
| Modern dense/learned | `xoftr_official` | ✓ | — |
| Modern dense/learned | `raw_minima` | ✓ | — |
| Scene-level reference | `uav_talign_full` | — | ✓ |

All learning-based methods use public pretrained weights without training or fine-tuning
on UAV-TAlign-12K.

---

## 9. Field-Name Compatibility

The manifest stores `view` and `scene_label`. The protocol uses `view_type` and
`scene_family`. To keep the manifest hash stable while aligning paper-facing terminology,
the runner emits **both** sets of names:

- pairwise records carry `view` + `view_type` + `scene_label` + `scene_family`
- scene-level records carry the same four fields
- the `PairRecord` dataclass exposes `view_type` / `scene_family` as aliases of `view` /
  `scene_label`

Downstream consumers should prefer the protocol names (`view_type`, `scene_family`) and
fall back to the manifest names if the upstream output predates this alignment. The
`scripts/build_ipt_p0d_protocol_artifacts.py` script implements this fallback.

---

## 10. Out of Scope (Future Work)

- External-submission schema for a public leaderboard
- Manual GT registration on a calibration subset
- Cross-family robustness study (training-set leakage analysis)
- Calibration-style analysis of `R(S)` against `y_S`

These are deferred and not required for the present protocol release.
