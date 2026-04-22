# PRCV Results / Discussion Skeleton

## Purpose

This note turns the current stable PRCV evidence into a paper-facing skeleton that a writing
assistant can draft from directly.

It is intentionally conservative:

- use only locally verified numbers
- keep method / baseline wording aligned with `README-paper.md`
- keep the final paper story centered on scene-level reliability rather than matcher ranking

## Locked Facts for the Current Draft

The following statements are currently safe to treat as fixed for the next writing pass:

- Pairwise baselines are now complete on the 500-pair first-wave package:
  - `raw MINIMA`: `500/500`
  - `official pretrained RoMa via local wrapper`: `500/500`
  - `Kornia LoFTR (pretrained="outdoor")`, resize-aware inference: `499/500`
  - `official pretrained XoFTR-640 via local wrapper`: `494/500`
  - `AKAZE + RANSAC`: `479/500`
  - `SIFT + RANSAC`: `457/500`
- The current formal scene-level result for `UAV-TAlign full pipeline` is:
  - `15 scenes`
  - `7/15` canonical scene passes
  - mean accepted ratio `64.5%`
- The current proxy draft already shows one strong fail-side signal:
  - `baseline_relative_qa_outliers` appears in `8/8` failing scenes and `0/7` passing scenes
- The cumulative ablation package is now complete:
  - `A1`: `8/8`
  - `A2`: `8/8`
  - `A3`: `5/8`
  - `A4-subset`: `5/8`
- The multi-seed random-selection supplement is also complete on the same fixed 8-scene subset:
  - `seed 0`: `6/8`
  - `seed 1`: `4/8`
  - `seed 2`: `7/8`
  - `seed 3`: `5/8`
- The current paired controls most worth discussing are:
  - `01 vs 02`
  - `03 vs 04`
- The current first qualitative panel batch is:
  - `01 + 02`
  - `03 + 04`
  - `09 + 13`
  - `05 + 15`

## Results Skeleton

### 6.1 Pairwise Baseline Comparison

Safe headline:

- Off-the-shelf multimodal matchers already provide high pairwise usability on `UAV-TAlign-1K`,
  but this does not by itself guarantee scene-level reliable registration.

Safe paragraph skeleton:

```text
Table X summarizes the first-wave pairwise baselines on 500 RGB-thermal pairs. Raw MINIMA and
RoMa both achieve 500/500 usable pairwise registrations in the current off-the-shelf setup,
while LoFTR reaches 499/500 under a resize-aware inference setting and XoFTR-640 reaches
494/500. Classical baselines remain serviceable but are clearly weaker, with AKAZE and SIFT
reaching 479/500 and 457/500 usable registrations, respectively. These results indicate that
pairwise cross-modal matching availability is already relatively strong on this dataset, so the
remaining challenge lies less in obtaining any match at all and more in forming scene-level
reliable alignments.
```

Writing notes:

- Keep `LoFTR` wording exact:
  - `Kornia LoFTR (pretrained="outdoor"), resize-aware inference (max image dimension = 1600, AMP disabled)`
- Do not describe `LoFTR`, `RoMa`, or `XoFTR` as untouched official-script runs.
- Treat this table as a pairwise reference table, not as the main evidence for scene-level
  robustness.

### 6.2 Scene-Level Performance of UAV-TAlign

Safe headline:

- The main bottleneck is scene-level reliability under QA-aware acceptance, not pairwise matcher
  availability.

Safe paragraph skeleton:

```text
In contrast to the near-saturated pairwise baseline table, the formal scene-level result remains
substantially more challenging. Under the canonical scene-level protocol, UAV-TAlign full
pipeline passes 7 of 15 scenes, with a mean accepted-frame ratio of 64.5%. This gap between
pairwise usability and scene-level canonical pass rate suggests that the central difficulty in
cross-FOV UAV RGB-thermal registration is not merely finding local correspondences, but producing
stable and self-consistent scene-level transforms that survive aggregation and QA checks.
```

Writing notes:

- Keep the canonical `7/15` as the main headline number for the formal pipeline.
- Do not over-interpret this as a failure of the matcher backend itself.
- Do not write that the method "solves" UAV RGB-thermal registration; write that it improves
  reliability under a practical scene-level protocol.

### 6.3 Protocol / Proxy Evidence

Safe headline:

- The current scene-level failures are better explained by QA-relative reliability signals than by
  pairwise matcher unavailability alone.

Safe paragraph skeleton:

```text
Because this PRCV version does not include manual geometric ground truth, we examine whether the
stored QA and proxy signals are at least internally consistent with scene-level pass/fail
decisions. The strongest currently available discriminator is the warning code
baseline_relative_qa_outliers, which appears in all 8 failing scenes and in none of the 7 passing
scenes. Accepted ratio also correlates with failure, but it is not sufficient by itself: for
example, scene 02 still shows 98% accepted frames yet fails because reject and QA-relative
outlier signals remain high, whereas scene 04 passes with 80% accepted frames when those
fail-side warnings are absent. These observations support the claim that the protocol is capturing
scene-level reliability rather than merely counting matched frames.
```

Writing notes:

- Use this subsection to reduce reviewer concern about the lack of manual GT.
- Be explicit that this is internal consistency evidence, not an absolute accuracy guarantee.
- Keep the strongest exact statistic:
  - `baseline_relative_qa_outliers`: `8/8` fail recall and `7/7` pass exclusion on the current 15-scene snapshot

### 6.4 Scene-Level and Condition-Level Breakdown

Safe headline:

- Difficulty patterns vary by scene condition, and paired controls suggest that QA-relative
  reliability is more decisive than raw match count alone.

Safe paragraph skeleton:

```text
The scene and condition breakdowns show that the remaining failures are unevenly distributed
rather than uniformly random. Night scenes remain the hardest group under the current canonical
gate, while pseudocolor scenes are not uniformly catastrophic but instead produce mixed outcomes
depending on scene structure and QA consistency. The paired controls 01 vs 02 and 03 vs 04 are
especially informative because they keep the scene family fixed while changing view or pass/fail
outcome. Together they support the interpretation that scene-level acceptance depends more on
reliability signals such as reject behavior and QA-relative outliers than on raw pairwise
availability alone.
```

Writing notes:

- Keep `01 vs 02` and `03 vs 04` as the first two paired controls in the main text.
- Prefer a concise main-text condition table for:
  - light condition
  - thermal rendering
- Move the full per-scene condensed table to appendix if space is tight.

### 6.5 Cumulative Ablation

Safe headline:

- The strongest supported gains come from robust aggregation and QA-aware scene decision, while
  deterministic selection is best framed as a reproducible operating policy.

Safe paragraph skeleton:

```text
The cumulative ablations show that the clearest empirical gains come from robust aggregation and
QA-aware scene decision. Relative to A1, A2 keeps the same accepted-only scene survivability but
substantially improves edge and gradient alignment proxies while reducing severe outliers,
supporting the importance of robust aggregation. A3 then brings the ablation line into close
agreement with the formal subset result, with both A3 and A4-subset reaching 5/8 canonical scene
passes and nearly identical proxy summaries. The completed multi-seed random-selection supplement
further shows a 4/8 to 7/8 spread across seeds on the same fixed subset, so deterministic-even
selection is best written as a reproducible default operating policy rather than as the single
largest performance driver.
```

Writing notes:

- Give `A2 vs A1` and `A3 vs A4-subset` the most space.
- Keep the multi-seed `S1` result short and functional:
  - use it to justify deterministic selection as a stable default
  - do not let it become a headline gain claim

### 6.6 Qualitative Results

Recommended figure story:

1. `01 + 02`:
   - wide-vs-zoom paired control
   - use to show that superficially similar pairwise availability can still lead to different
     scene-level outcomes
2. `03 + 04`:
   - night paired control
   - use to explain pass-vs-fail under similar scene family and lighting regime
3. `09 + 13`:
   - positive cases where `UAV-TAlign` remains usable under challenging conditions
4. `05 + 15`:
   - failure cases
   - use to show remaining limitations instead of hiding them

Safe paragraph skeleton:

```text
Qualitative panels further support the scene-level interpretation above. The paired controls 01 vs
02 and 03 vs 04 show that similar scene families can diverge sharply once reject behavior and
QA-relative consistency are considered, while scenes 09 and 13 illustrate representative cases in
which the full pipeline remains usable under more challenging UAV RGB-thermal conditions. We also
retain clear failure examples such as scenes 05 and 15 to show the current limits of the method,
especially under difficult appearance shifts or unstable geometry.
```

## Discussion Skeleton

### D1. Primary Interpretation

Safe thesis:

- The paper should frame the core challenge as scene-level reliability, not pairwise matcher
  availability.

Safe paragraph skeleton:

```text
Taken together, the current results suggest that pairwise matcher availability is no longer the
primary bottleneck on UAV-TAlign-1K. Strong off-the-shelf multimodal matchers already succeed on
most individual pairs, yet scene-level canonical passes remain far from saturated. This shift in
the bottleneck motivates UAV-TAlign as a reliability-oriented pipeline built around candidate
selection, aggregation, and QA-aware decision logic rather than as a new local matcher.
```

### D2. What the Current Results Do and Do Not Prove

Safe statements:

- The current evidence supports:
  - pairwise baselines are complete
  - scene-level reliability remains hard
  - the proxy signals are non-random and interpretable
  - robust aggregation and QA-aware decision are the strongest supported gains
- The current evidence does not yet fully prove:
  - that the protocol is a substitute for manual GT
  - that the current pipeline is fully robust across all UAV RGB-thermal conditions
  - that deterministic selection is universally stronger than random selection

Safe paragraph skeleton:

```text
The present evidence is strong enough to support the paper's main practical message, but it does
not eliminate all uncertainty. In particular, the current proxy analysis supports the internal
logic of the protocol without replacing manual geometric ground truth, and the method should still
be presented as a practical and reproducible pipeline rather than a final solution to UAV
RGB-thermal registration. The completed multi-seed random-selection supplement also suggests that
deterministic selection is best treated as a stable operating policy rather than a universal
performance-superiority claim.
```

### D3. Reviewer-Facing Risk Control

Current risk order:

1. no manual GT
2. protocol credibility not fully closed
3. wrapper / deployment wording precision
4. overclaiming deterministic selection
5. baseline completeness

Implication for writing:

- `Results` should already foreground the protocol-consistency evidence.
- `Discussion` should acknowledge the lack of manual GT before the reviewer does.
- `Limitations` should explicitly mention wrapper / deployment constraints and homography limits.

## Sentence Bank

These lines are currently safe to reuse almost verbatim in paper drafting:

- `Pairwise matcher availability is largely no longer the primary bottleneck on UAV-TAlign-1K; the remaining challenge is scene-level reliability under aggregation and QA-aware acceptance.`
- `UAV-TAlign should be interpreted as a practical UAV-oriented registration pipeline built on top of strong public multimodal matchers rather than as a brand-new matcher backbone.`
- `The current proxy evidence supports protocol consistency, but it does not replace manual geometric ground truth.`

These lines are currently unsafe or too strong:

- `We provide accurate geometric ground truth.`
- `All baselines were run from untouched official scripts.`
- `LoFTR was evaluated in its untouched official full-resolution configuration.`
- `The current protocol proves absolute registration accuracy.`

## Immediate Writing Order

1. Draft the `Results` section using this file together with:
   - `docs/prcv_main_table_draft.md`
   - `docs/prcv_scene_condition_tables_draft.md`
   - `docs/prcv_proxy_consistency_draft.md`
   - `docs/prcv_qualitative_panel_candidates.md`
2. Draft `Discussion` using the scene-level reliability framing above.
3. Draft abstract / contribution wording using `docs/prcv_abstract_contributions_final.md`.
