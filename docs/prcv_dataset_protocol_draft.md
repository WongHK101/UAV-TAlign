# PRCV Dataset / Evaluation Protocol Draft

## Purpose

This note provides a paper-facing draft for the `Dataset` and `Evaluation Protocol` sections of the
PRCV `UAV-TAlign` paper. It is grounded in the current local implementation and the stabilized
formal result package, especially:

- `E:\UAV-TAlign\utils\uav_talign_dataset.py`
- `E:\UAV-TAlign\run_prcv_main_experiment.py`
- `E:\UAV-TAlign\docs\prcv_main_table_draft.md`
- `E:\UAV-TAlign\docs\prcv_scene_condition_tables_draft.md`
- `E:\UAV-TAlign\docs\prcv_proxy_consistency_draft.md`

The key writing constraint remains unchanged:

- `UAV-TAlign-1K` should be framed as a practical public subset plus label-free evaluation package
- not as a fully supervised benchmark with manual geometric ground truth

## Dataset Draft

### 3. UAV-TAlign-1K

#### 3.1 Dataset Scope

For the PRCV version of this work, we package `UAV-TAlign-1K` as a lightweight public evaluation
subset for real UAV RGB-thermal registration. The current subset contains 15 scenes, 500 aligned
RGB-thermal pairs, and 1000 images in total. Each sample is organized as an RGB image paired with a
thermal image captured from the same scene context, while the dataset as a whole spans a range of
practical UAV conditions that make registration substantially harder than standard near-same-view
multimodal matching.

At the scene level, the subset intentionally preserves several sources of variation that matter for
registration reliability: day, night, and low-light capture; grayscale and pseudocolor thermal
rendering; and both wide-view and zoom-view scene families. In the current formal split, the 15
scenes include 7 day scenes, 5 night scenes, and 3 low-light scenes; 8 grayscale-thermal scenes
and 7 pseudocolor-thermal scenes; and paired wide/zoom controls for the substation scene family.
These factors are important because they create the reliability gap that motivates the paper:
pairwise matching can still be strong, while scene-level acceptance remains difficult.

#### 3.2 Organization and Metadata

Each scene is stored under its own scene directory, and paired samples are formed by matching file
stems between `rgb/` and `thermal/` subdirectories. The current dataset loader does not rely on
hard-coded pair lists for formal evaluation. Instead, it constructs scene pairs from the common RGB
and thermal filenames, while scene-level metadata are loaded from the subset manifest.

For each pair, the loader stores:

- `scene_name`
- `scene_id`
- `pair_id`
- `rgb_path`
- `thermal_path`
- `light_condition`
- `thermal_rendering`
- `view`
- `scene_label`

This organization supports both pairwise baseline evaluation and scene-level pipeline evaluation
under the same subset definition, while also enabling condition-based breakdowns without requiring a
separate annotation pass.

#### 3.3 Why a Public Subset Instead of Full Manual GT

Manual landmark-level geometric ground truth is expensive and often unstable in low-texture thermal
UAV imagery. Rather than delaying the paper until dense manual GT is available, the current PRCV
package focuses on a practical and reproducible subset with a label-free evaluation protocol. This
choice should be presented as a scope decision rather than as a claim that manual GT is unnecessary
in general. The contribution here is that `UAV-TAlign-1K` makes scene-level UAV RGB-thermal
registration studyable under realistic conditions without requiring manual landmark annotation as a
prerequisite.

## Evaluation Protocol Draft

### 5. Evaluation Protocol

#### 5.1 Two Evaluation Units

The protocol distinguishes between two related but non-identical evaluation units.

First, off-the-shelf baselines are evaluated at the pair level. Each of the 500 RGB-thermal pairs is
processed independently, and the resulting statistics describe whether a method can produce a usable
pairwise registration and homography under a fixed off-the-shelf setting.

Second, `UAV-TAlign full pipeline` is evaluated at the scene level. In this case, multiple
frame-level estimates are aggregated into a scene-level transform, and the final decision is made by
canonical scene acceptance rather than by pairwise usability alone. This distinction is essential:
the pairwise and scene-level tables are complementary, but they should not be described as if they
measured exactly the same notion of success.

#### 5.2 Pairwise Baseline Protocol

For each pairwise method, the formal runner records whether the pair produced a usable homography,
the final status code, and a small set of geometric summary fields. The current quantitative table
uses:

- usable / `ok` count
- homography availability rate
- mean inlier ratio
- mean spatial coverage
- mean reprojection error
- mean runtime

In the local implementation, these method summaries are derived from per-pair records and aggregated
through method-level summary statistics. This protocol is intentionally simple: it answers whether a
baseline can produce strong off-the-shelf pairwise registrations on `UAV-TAlign-1K`, which is
exactly the first question the paper needs before moving on to the harder scene-level problem.

#### 5.3 Scene-Level Protocol for UAV-TAlign

For `UAV-TAlign full pipeline`, the protocol operates at the scene level. Each scene first produces
multiple accepted frame-level candidates, then aggregates them into a single scene-level transform,
and finally evaluates that transform under a canonical scene-pass rule.

The current formal implementation stores, for each scene:

- `qa_status`
- `canonical_scene_pass`
- `accepted_frames`
- `num_attempted_frames`
- `accepted_ratio`
- accepted-frame summary statistics for:
  - number of matches
  - number of inliers
  - inlier ratio
  - reprojection error
  - coverage
- runtime
- scene-level QA and stability fields such as:
  - `delta_edge_f1`
  - `delta_grad_ncc`
  - `improved_grad_ratio`
  - `severe_outlier_ratio`
  - `robust_reject_ratio`
  - `median_disp_to_aggregate_mean_px`
  - warning codes and decision inputs

Under the current formal configuration, canonical scene acceptance is based on the default
`qa_status` policy. In practice, this means a scene must both accumulate enough accepted frames and
survive the baseline-aware QA stage. This is the protocol-level expression of the paper's main
position: reliable scene-level alignment is harder than pairwise match availability alone.

#### 5.4 Label-Free QA Proxies

Because the current PRCV package does not include manual landmark annotations, the protocol relies
on label-free relative QA signals rather than absolute geometric accuracy. The strongest stored
proxies compare the optimized transform against a weak baseline initialization and summarize whether
scene-level rectification improves cross-modal agreement.

The current proxy family includes:

- edge-overlap improvement (`delta_edge_f1`)
- gradient-NCC improvement (`delta_grad_ncc`)
- ratio of frames with improved gradient agreement
- severe baseline-relative outlier count and ratio
- accepted-frame ratio
- homography-dispersion and robust-rejection diagnostics

These proxies should be presented carefully. They are not a substitute for absolute ground-truth
accuracy. Instead, they provide a practical scene-consistency signal for comparing methods and for
deciding whether a scene-level transform is reliable enough to retain under the current PRCV scope.

#### 5.5 Protocol-Consistency Reading

The current formal snapshot already shows that the protocol is not merely counting matched frames.
The strongest fail-side indicator is the warning code `baseline_relative_qa_outliers`, which appears
in all 8 failing scenes and in none of the 7 passing scenes. At the same time, accepted-frame ratio
is informative but not sufficient by itself: some scenes still fail despite high accepted ratios
when the outlier or stability signals remain poor.

This behavior is useful for writing because it supports a restrained but meaningful claim: the
current protocol is capturing scene-level reliability signals rather than simply mirroring pairwise
matcher availability. That is the level on which the protocol should be defended in the paper.

#### 5.6 Qualitative Evaluation

In addition to tabulated metrics, the protocol includes qualitative before/after visual inspection.
The current paper package already reserves representative panels for:

- wide-vs-zoom controls
- night pass-vs-fail controls
- scenes where scene-level `UAV-TAlign` remains strong while classical baselines are weaker
- explicit failure cases

These visuals are especially important because they provide an interpretable bridge between the
label-free proxy statistics and the scene-level registration behavior that the paper claims to
improve.

## Code-Grounded Facts

The following statements are directly grounded in the current local implementation and are safe to
reuse during writing.

- `UAV-TAlign-1K` pair construction matches RGB and thermal files by shared filename stem within
  each scene directory.
- Scene metadata are loaded from a manifest and include:
  - scene id
  - light condition
  - thermal rendering
  - view
  - scene label
- The current formal runner reports pairwise baselines and `uav_talign_full` in separate summary
  styles because they correspond to different evaluation units.
- Pairwise method summaries aggregate:
  - status counts
  - homography availability
  - match, inlier, coverage, reprojection, and runtime statistics
- Scene-level `uav_talign_full` summaries aggregate:
  - status counts
  - QA-status counts
  - canonical scene-pass count
  - accepted-frame and attempted-frame statistics
  - runtime statistics

## Writing Notes

- Do not write this section as if the dataset already contained manual point-level registration GT.
- Do not describe the protocol as `ground-truth-free accuracy evaluation`.
- The safer wording is:
  - public subset
  - practical label-free evaluation setup
  - scene-consistency / reliability-oriented protocol
- Keep the distinction between pairwise and scene-level evaluation explicit; this helps the reader
  understand why strong pairwise baseline results can coexist with a much harder formal scene-level
  problem.
