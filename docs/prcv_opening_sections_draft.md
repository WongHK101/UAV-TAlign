# PRCV Opening Sections Draft

## Purpose

This note provides near-paper-ready draft text for the opening sections that are most likely to
benefit from a strong, stable narrative:

- title
- abstract
- introduction opening
- contribution bullets
- results opening paragraphs

It is based on the final locally supported paper line:

- pairwise availability is already strong
- scene-level reliability is the real bottleneck
- robust aggregation and QA-aware decision are the strongest supported gains

## Title

`UAV-TAlign: Reliable RGB-Thermal Registration for Cross-FOV UAV Imagery`

## Abstract

```text
UAV RGB-thermal alignment is important for inspection, monitoring, and nighttime multimodal perception, but reliable registration remains difficult because viewpoint variation, thermal rendering differences, and low-light conditions make scene-level alignment unstable. In our experiments, strong off-the-shelf multimodal matchers already provide high pairwise availability on UAV-TAlign-1K, yet reliable scene-level acceptance remains the main bottleneck. We present UAV-TAlign, a practical scene-level alignment pipeline that builds on pairwise matching with deterministic candidate selection, robust homography aggregation, and QA-aware scene acceptance. We also package UAV-TAlign-1K together with a practical label-free evaluation setup for studying real UAV RGB-thermal alignment without requiring manual landmark annotation as a prerequisite. Experiments against off-the-shelf baselines, protocol-consistency analysis, and cumulative ablations show that the strongest gains come from robust aggregation and reliability-aware scene decision, rather than from pairwise matcher availability alone.
```

## Introduction Draft

### Intro Opening Version

```text
RGB-thermal alignment is a practical requirement in UAV inspection, monitoring, and low-light perception systems, where visible and thermal imagery provide complementary scene cues. In real deployments, however, reliable registration is difficult to obtain because UAV RGB-T data often combine viewpoint change, cross-resolution sensors, weak thermal texture, grayscale or pseudocolor thermal rendering, and day/night illumination variation. These factors make scene-level alignment substantially harder than standard same-view or near-same-view multimodal matching setups.

Recent multimodal matchers have significantly improved pairwise cross-modal correspondence estimation, and strong off-the-shelf models can already produce usable registrations for many individual RGB-thermal pairs. Yet our experiments show that high pairwise usability does not automatically translate into reliable scene-level alignment under realistic UAV conditions. The remaining difficulty is no longer simply whether a matcher can produce correspondences, but whether a system can aggregate evidence across a scene and retain only transforms that remain stable under quality control.

This observation motivates a shift in problem framing. Rather than treating UAV RGB-T registration primarily as a pairwise matching availability problem, we study it as a scene-level reliability problem. Under this view, the central question becomes how to convert strong but imperfect pairwise registrations into scene-level transforms that remain geometrically stable, internally consistent, and usable after QA-aware acceptance.

To address this problem, we present UAV-TAlign, a practical scene-level UAV RGB-thermal alignment pipeline built on top of strong off-the-shelf multimodal matching. UAV-TAlign uses deterministic candidate selection as a reproducible operating policy, robust homography aggregation to suppress unstable frame-level estimates, and QA-aware scene acceptance to reject transforms that are not sufficiently reliable at the scene level. We further package UAV-TAlign-1K, a public subset and practical label-free evaluation setup for studying real UAV RGB-T alignment without requiring manual landmark annotation as a prerequisite.

Our experiments against classical and learning-based baselines lead to three main conclusions. First, off-the-shelf multimodal baselines already provide strong pairwise availability on UAV-TAlign-1K. Second, the main challenge under UAV RGB-T conditions lies in scene-level reliability rather than pairwise matcher availability alone. Third, cumulative ablations show that the strongest gains in the full pipeline come from robust aggregation and QA-aware scene decision, while deterministic selection is best understood as a stable and reproducible default operating policy. Together, these results position UAV-TAlign as a practical reliability-oriented pipeline for UAV RGB-thermal registration rather than as a new matcher backbone.
```

### Optional Shorter Intro Opening

```text
Reliable RGB-thermal alignment is essential for many UAV perception and inspection tasks, yet it remains difficult in real imagery because cross-FOV capture, thermal appearance variation, and low-light conditions make scene-level registration unstable. Although recent multimodal matchers already provide strong pairwise availability on many RGB-thermal pairs, our experiments show that the main bottleneck now lies in scene-level reliability rather than in correspondence generation alone. We therefore present UAV-TAlign, a practical scene-level pipeline that combines strong off-the-shelf pairwise matching with deterministic candidate selection, robust homography aggregation, and QA-aware scene acceptance. Together with UAV-TAlign-1K and a practical label-free evaluation setup, this formulation allows us to study UAV RGB-T registration as a reliability problem under realistic operating conditions.
```

## Contribution Bullets

```text
Our contributions are threefold:

1. We present UAV-TAlign, a practical scene-level UAV RGB-thermal alignment pipeline that builds reliable alignment on top of strong off-the-shelf multimodal pairwise matching through robust aggregation and QA-aware scene acceptance.
2. We package UAV-TAlign-1K as a public evaluation subset together with a practical label-free evaluation protocol for real UAV RGB-T alignment, without requiring manual landmark annotations as a prerequisite.
3. Extensive off-the-shelf baseline comparisons, proxy-consistency analysis, and cumulative ablations show that, once pairwise match availability is largely in place, the main challenge shifts to scene-level reliability, and the most supported gains come from robust aggregation and reliability-aware decision.
```

## Results Opening Paragraphs

### Results Opening

```text
We begin by asking whether the main difficulty on UAV-TAlign-1K still lies in obtaining usable pairwise RGB-thermal correspondences. Table X shows that this is no longer the dominant bottleneck. Strong off-the-shelf multimodal methods already provide high pairwise usability, with raw MINIMA and RoMa both reaching 500/500 usable pairwise registrations, LoFTR reaching 499/500 under a resize-aware inference setting, and XoFTR-640 reaching 494/500. Classical baselines remain weaker, but they are not uniformly unusable. Taken together, these results indicate that pairwise multimodal matching availability is already relatively strong on this dataset.

However, this near-saturated pairwise picture does not carry over to scene-level performance. Under the canonical QA-aware scene criterion, UAV-TAlign full pipeline passes 7 of 15 scenes, with a mean accepted-frame ratio of 64.5%. This gap between strong pairwise usability and substantially lower scene-level canonical pass rate suggests that the core challenge in UAV RGB-thermal registration is not simply producing pairwise matches, but forming scene-level transforms that remain stable after aggregation and reliability-aware acceptance.

To understand this gap, we next examine the internal consistency of the label-free protocol. The strongest currently stored fail-side discriminator is the warning code baseline_relative_qa_outliers, which appears in all 8 failing scenes and in none of the 7 passing scenes in the current formal snapshot. Paired controls such as 01 vs 02 and 03 vs 04 further show that pass/fail behavior is better explained by QA-relative reliability signals than by raw pairwise availability alone. These observations support the view that the current protocol is capturing scene-level reliability rather than merely counting matched frames.

We then turn to cumulative ablations. The clearest empirical gains come from robust aggregation and QA-aware scene decision: A2 substantially improves alignment proxies and reduces severe outliers relative to A1, while A3 closely matches the formal subset result under the same scene-level decision regime. By contrast, the completed multi-seed random-selection supplement shows a wide 4/8 to 7/8 spread across seeds on the same fixed 8-scene subset, so deterministic-even selection is best understood as a reproducible default operating policy rather than the main source of gain. Overall, the results support a reliability-oriented interpretation of UAV-TAlign.
```

### Short Results Opening

```text
The main quantitative results show a clear separation between pairwise availability and scene-level reliability. Off-the-shelf multimodal baselines already achieve strong pairwise usability on UAV-TAlign-1K, but the formal scene-level result remains substantially more difficult, with UAV-TAlign full pipeline passing 7 of 15 scenes under the canonical QA-aware criterion. This gap suggests that the central challenge in UAV RGB-thermal registration is no longer merely whether a matcher can produce correspondences, but whether the resulting transforms remain stable and reliable after aggregation and scene-level QA. The subsequent proxy analysis and cumulative ablations support this interpretation and indicate that the strongest gains in the full pipeline come from robust aggregation and reliability-aware scene decision.
```

## Use Notes

- Use the longer introduction for the main paper draft, then compress if page pressure is high.
- Keep the results opening close to the current evidence hierarchy:
  - pairwise table first
  - scene-level formal result second
  - proxy evidence third
  - ablation evidence fourth
- Do not let deterministic-vs-random wording dominate the opening sections.
