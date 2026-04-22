# PRCV Related Work Draft

## Purpose

This note provides a paper-facing `Related Work` draft that stays aligned with the current PRCV
positioning:

- `UAV-TAlign` is not introduced as a new matcher backbone
- the paper should emphasize scene-level reliability under UAV RGB-thermal conditions
- the dataset contribution should be framed as `UAV-TAlign-1K` plus a practical label-free
  evaluation package, not as a fully supervised benchmark

Citation placeholders below should be replaced with the final bibliography entries during the
writing pass.

## Related Work Draft

### 2. Related Work

#### 2.1 Classical Image Registration

Classical image registration methods typically rely on hand-crafted local features followed by
robust geometric fitting. Representative pipelines built on SIFT, SURF, ORB, KAZE, or AKAZE with
RANSAC-style homography estimation remain attractive because they are simple, interpretable, and do
not require task-specific training [..]. However, their performance can degrade substantially in
cross-modal settings, especially when the appearance gap between visible and thermal imagery reduces
descriptor repeatability or when thermal frames contain weak texture and large homogeneous regions.

These methods remain important baselines in our study because they represent the classical
registration view of the problem: if sufficiently stable local features can be extracted, a single
pairwise homography may already solve the task. Our results suggest that this assumption is too weak
for real UAV RGB-thermal scenes, where scene-level reliability often remains difficult even when
some individual pairs are usable.

#### 2.2 Deep Pairwise Matching for Multimodal Registration

Recent dense and semi-dense matching methods have significantly improved pairwise geometric
correspondence estimation. Transformer- and correlation-based models such as LoFTR, RoMa, XoFTR,
and MINIMA-family methods have shown that cross-modal pairwise matching can now be performed
substantially more robustly than with purely hand-crafted features [..]. In particular, these
methods are much better at recovering useful correspondences in weak-texture regions, repetitive
structures, or substantial appearance shifts.

Our work builds directly on this progress instead of trying to replace it. The empirical picture in
`UAV-TAlign-1K` is that strong off-the-shelf multimodal matchers already provide very high pairwise
availability. This changes the central question. The bottleneck is no longer only whether a matcher
can produce correspondences for a given RGB-thermal pair, but whether those frame-level estimates
can be converted into a stable and reliable scene-level alignment under realistic UAV operating
conditions.

This distinction is important for positioning. `UAV-TAlign` should therefore be read as a
reliability-oriented scene-level pipeline built on top of strong pairwise backbones, rather than as
another entry in a matcher-zoo comparison.

#### 2.3 Visible-Thermal Registration and Evaluation

Visible-thermal registration has been studied under a range of assumptions, from same-view or
near-same-view alignment to broader multimodal correspondence learning [..]. Many existing settings
either operate under relatively controlled viewpoint changes or evaluate pairwise registration in a
way that does not require a scene-level acceptance decision. By contrast, practical UAV RGB-thermal
data frequently combine cross-FOV capture, cross-resolution sensing, thermal rendering variation,
and low-light conditions. These factors make scene-level reliability a more central concern than in
many standard visible-thermal evaluation setups.

A further complication is that point-level manual geometric ground truth is expensive and sometimes
ill-posed in weak-texture thermal frames. For the current PRCV scope, we therefore avoid presenting
our dataset package as a fully supervised benchmark. Instead, we package a public subset,
`UAV-TAlign-1K`, together with a practical label-free evaluation protocol that measures
scene-consistency and relative alignment quality without requiring manual landmark annotation as a
prerequisite.

#### 2.4 UAV Multimodal Datasets and the Remaining Gap

UAV multimodal datasets have supported progress in detection, tracking, segmentation, and broader
cross-modal perception [..]. However, registration is not always the primary task in those
benchmarks, and the protocol assumptions needed for scene-level RGB-thermal alignment are often
different from those needed for downstream semantic tasks. In particular, a practical registration
pipeline must decide not only how to align frames, but also when the scene-level evidence is strong
enough to trust the resulting transform.

This is the gap our paper targets. Rather than introducing a new paired-image benchmark or a new
matcher architecture, we focus on a practical scene-level registration setting for real UAV
RGB-thermal imagery. Our contribution lies in the combination of a reliability-oriented pipeline, a
public subset packaging, and a label-free protocol that makes the problem studyable without first
building dense manual geometric annotations.

## Positioning Notes

The current safest paper-level contrast is:

- prior work has already made pairwise multimodal matching much stronger
- our paper focuses on the next bottleneck: scene-level reliability under UAV RGB-thermal
  conditions

This means the `Related Work` section should not over-invest in ranking matchers against each other.
Its real job is to set up why a scene-level reliability pipeline is now the right contribution.

## Safe Wording Reminders

- Do not describe `UAV-TAlign-1K` as a new fully supervised benchmark.
- Do not describe the protocol as `ground-truth-free accuracy evaluation`.
- Do not write as if pairwise matching methods were insufficient in general; the safer statement is
  that pairwise availability alone does not solve scene-level reliability.
- Keep `LoFTR`, `RoMa`, `XoFTR`, and `MINIMA` in the narrative as strong pairwise baselines that
  motivate the shift in problem framing.
