"""Build P0-D protocol-closure artifacts from P0-C scene-level outputs.

This script is intentionally offline: it only reads exported P0-C summaries and
scene metrics, then writes paper/review artifacts into a separate directory.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def _clip(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct(value: float) -> str:
    return f"{100.0 * float(value):.1f}%"


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def add_reliability_score(df: pd.DataFrame) -> pd.DataFrame:
    """Add an interpretable, non-trained scene reliability score.

    The score is a weighted combination of normalized evidence terms already
    produced by the QA pipeline. It is used for protocol analysis and operating
    curves, not as a learned replacement for the canonical scene criterion.
    """

    df = df.copy()

    accepted = df["accepted_ratio"].map(lambda x: _clip(_safe_float(x)))
    outlier = df["severe_outlier_ratio"].map(lambda x: 1.0 - _clip(_safe_float(x) / 0.10))
    robust = df["robust_reject_ratio"].map(lambda x: 1.0 - _clip(_safe_float(x) / 0.25))
    edge = df["delta_edge_f1"].map(lambda x: _clip((_safe_float(x) + 0.05) / 0.20))
    grad = df["delta_grad_ncc"].map(lambda x: _clip(_safe_float(x) / 0.15))
    inlier = df["mean_inlier_ratio"].map(lambda x: _clip(_safe_float(x) / 0.50))
    coverage = df["mean_coverage"].map(lambda x: _clip(_safe_float(x)))
    reproj = df["mean_reproj_error"].map(lambda x: 1.0 - _clip((_safe_float(x, 1.5) - 1.5) / 1.0))
    geometry = 0.5 * inlier + 0.3 * coverage + 0.2 * reproj

    df["score_accepted_ratio"] = accepted
    df["score_outlier_control"] = outlier
    df["score_robust_consensus"] = robust
    df["score_edge_gain"] = edge
    df["score_grad_gain"] = grad
    df["score_geometry"] = geometry
    df["reliability_score"] = 100.0 * (
        0.25 * accepted
        + 0.25 * outlier
        + 0.20 * robust
        + 0.15 * edge
        + 0.10 * grad
        + 0.05 * geometry
    )
    df["reliability_rank"] = df["reliability_score"].rank(method="first", ascending=False).astype(int)
    return df.sort_values(["reliability_score", "scene_id"], ascending=[False, True])


def build_risk_coverage(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    total_scenes = len(df)
    total_pairs = float(df["valid_pairs"].sum())
    ranked = df.sort_values("reliability_score", ascending=False).reset_index(drop=True)
    for k in range(1, total_scenes + 1):
        subset = ranked.iloc[:k]
        rows.append(
            {
                "retained_scene_count": k,
                "scene_coverage": k / total_scenes,
                "pair_coverage_micro": float(subset["valid_pairs"].sum()) / total_pairs,
                "score_threshold_min": float(subset["reliability_score"].min()),
                "mean_reliability_score": float(subset["reliability_score"].mean()),
                "canonical_pass_count_within_retained": int(subset["canonical_scene_pass"].sum()),
                "canonical_pass_fraction_within_retained": float(subset["canonical_scene_pass"].mean()),
                "mean_severe_outlier_ratio": float(subset["severe_outlier_ratio"].mean()),
                "mean_robust_reject_ratio": float(subset["robust_reject_ratio"].mean()),
                "mean_delta_edge_f1": float(subset["delta_edge_f1"].mean()),
                "mean_delta_grad_ncc": float(subset["delta_grad_ncc"].mean()),
                "mean_accepted_ratio_macro": float(subset["accepted_ratio"].mean()),
                "accepted_attempted_ratio_micro": float(subset["accepted_frames"].sum())
                / float(max(subset["attempted_frames"].sum(), 1)),
                "accepted_total_ratio_micro": float(subset["accepted_frames"].sum())
                / float(max(subset["valid_pairs"].sum(), 1)),
                "retained_scene_ids": ",".join(str(x) for x in subset["scene_id"].tolist()),
            }
        )
    return pd.DataFrame(rows)


def build_canonical_operating_point(df: pd.DataFrame) -> dict:
    """Summarize the strict canonical QA-gate subset.

    This is intentionally separate from the score-ranked risk-coverage curve:
    the canonical gate defines retained alignment products, while the score is
    only used to visualize operating profiles.
    """

    subset = df[df["canonical_scene_pass"]].copy()
    total_scenes = float(len(df))
    total_pairs = float(df["valid_pairs"].sum())
    return {
        "operating_point": "canonical_qa_gate",
        "retained_scene_count": int(len(subset)),
        "scene_coverage": float(len(subset)) / total_scenes if total_scenes else 0.0,
        "pair_coverage_micro": float(subset["valid_pairs"].sum()) / total_pairs if total_pairs else 0.0,
        "mean_reliability_score": float(subset["reliability_score"].mean()) if len(subset) else 0.0,
        "mean_severe_outlier_ratio": float(subset["severe_outlier_ratio"].mean()) if len(subset) else 0.0,
        "mean_robust_reject_ratio": float(subset["robust_reject_ratio"].mean()) if len(subset) else 0.0,
        "mean_delta_edge_f1": float(subset["delta_edge_f1"].mean()) if len(subset) else 0.0,
        "mean_delta_grad_ncc": float(subset["delta_grad_ncc"].mean()) if len(subset) else 0.0,
        "mean_accepted_ratio_macro": float(subset["accepted_ratio"].mean()) if len(subset) else 0.0,
        "accepted_attempted_ratio_micro": float(subset["accepted_frames"].sum())
        / float(max(subset["attempted_frames"].sum(), 1)),
        "accepted_total_ratio_micro": float(subset["accepted_frames"].sum()) / float(max(subset["valid_pairs"].sum(), 1)),
        "retained_scene_ids": ",".join(str(x) for x in subset.sort_values("scene_id")["scene_id"].tolist()),
    }


def build_threshold_sensitivity(df: pd.DataFrame) -> pd.DataFrame:
    thresholds = list(range(95, 24, -5))
    rows: list[dict] = []
    total_pairs = float(df["valid_pairs"].sum())
    for thr in thresholds:
        subset = df[df["reliability_score"] >= thr]
        if len(subset) == 0:
            rows.append(
                {
                    "threshold_type": "reliability_score",
                    "threshold_value": thr,
                    "retained_scene_count": 0,
                    "scene_coverage": 0.0,
                    "pair_coverage_micro": 0.0,
                    "canonical_pass_count_within_retained": 0,
                    "mean_severe_outlier_ratio": "",
                    "mean_robust_reject_ratio": "",
                    "mean_accepted_ratio_macro": "",
                    "accepted_attempted_ratio_micro": "",
                    "retained_scene_ids": "",
                }
            )
            continue
        rows.append(
            {
                "threshold_type": "reliability_score",
                "threshold_value": thr,
                "retained_scene_count": int(len(subset)),
                "scene_coverage": float(len(subset)) / float(len(df)),
                "pair_coverage_micro": float(subset["valid_pairs"].sum()) / total_pairs,
                "canonical_pass_count_within_retained": int(subset["canonical_scene_pass"].sum()),
                "mean_severe_outlier_ratio": float(subset["severe_outlier_ratio"].mean()),
                "mean_robust_reject_ratio": float(subset["robust_reject_ratio"].mean()),
                "mean_accepted_ratio_macro": float(subset["accepted_ratio"].mean()),
                "accepted_attempted_ratio_micro": float(subset["accepted_frames"].sum())
                / float(max(subset["attempted_frames"].sum(), 1)),
                "retained_scene_ids": ",".join(str(x) for x in subset.sort_values("scene_id")["scene_id"].tolist()),
            }
        )

    regimes = [
        ("conservative", 80.0),
        ("balanced", 60.0),
        ("permissive", 40.0),
        ("inclusive_profile", 25.0),
    ]
    for name, thr in regimes:
        subset = df[df["reliability_score"] >= thr]
        rows.append(
            {
                "threshold_type": "named_operating_regime",
                "threshold_value": name,
                "retained_scene_count": int(len(subset)),
                "scene_coverage": float(len(subset)) / float(len(df)),
                "pair_coverage_micro": float(subset["valid_pairs"].sum()) / total_pairs if len(subset) else 0.0,
                "canonical_pass_count_within_retained": int(subset["canonical_scene_pass"].sum()) if len(subset) else 0,
                "mean_severe_outlier_ratio": float(subset["severe_outlier_ratio"].mean()) if len(subset) else "",
                "mean_robust_reject_ratio": float(subset["robust_reject_ratio"].mean()) if len(subset) else "",
                "mean_accepted_ratio_macro": float(subset["accepted_ratio"].mean()) if len(subset) else "",
                "accepted_attempted_ratio_micro": float(subset["accepted_frames"].sum())
                / float(max(subset["attempted_frames"].sum(), 1))
                if len(subset)
                else "",
                "retained_scene_ids": ",".join(str(x) for x in subset.sort_values("scene_id")["scene_id"].tolist()),
            }
        )
    return pd.DataFrame(rows)


def build_condition_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    for group_by in ["light_condition", "thermal_rendering", "view"]:
        for group, subset in df.groupby(group_by, dropna=False):
            valid_pairs = float(subset["valid_pairs"].sum())
            attempted = float(subset["attempted_frames"].sum())
            accepted = float(subset["accepted_frames"].sum())
            rows.append(
                {
                    "group_by": group_by,
                    "group": group,
                    "scene_count": int(len(subset)),
                    "canonical_retained_scene_count": int(subset["canonical_scene_pass"].sum()),
                    "canonical_scene_retention_macro": float(subset["canonical_scene_pass"].mean()),
                    "valid_pairs_micro": int(valid_pairs),
                    "pair_coverage_share": valid_pairs / float(df["valid_pairs"].sum()),
                    "accepted_attempted_ratio_micro": accepted / max(attempted, 1.0),
                    "accepted_total_ratio_micro": accepted / max(valid_pairs, 1.0),
                    "mean_reliability_score_macro": float(subset["reliability_score"].mean()),
                    "mean_severe_outlier_ratio_macro": float(subset["severe_outlier_ratio"].mean()),
                    "mean_robust_reject_ratio_macro": float(subset["robust_reject_ratio"].mean()),
                    "mean_delta_edge_f1_macro": float(subset["delta_edge_f1"].mean()),
                    "mean_delta_grad_ncc_macro": float(subset["delta_grad_ncc"].mean()),
                }
            )
    return pd.DataFrame(rows)


def save_figures(
    df: pd.DataFrame,
    risk_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    cond_df: pd.DataFrame,
    canonical_point: dict,
    out_dir: Path,
) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")

    fig, ax1 = plt.subplots(figsize=(7.6, 4.4))
    ax1.plot(risk_df["scene_coverage"], risk_df["mean_severe_outlier_ratio"], marker="o", label="Mean severe outlier ratio")
    ax1.plot(risk_df["scene_coverage"], risk_df["mean_robust_reject_ratio"], marker="s", label="Mean robust reject ratio")
    ax1.scatter(
        [canonical_point["scene_coverage"]],
        [canonical_point["mean_severe_outlier_ratio"]],
        marker="*",
        s=190,
        color="#d62728",
        edgecolor="black",
        linewidth=0.5,
        zorder=5,
        label="Canonical gate",
    )
    ax1.set_xlabel("Scene coverage")
    ax1.set_ylabel("Risk proxy (lower is better)")
    ax1.set_ylim(bottom=0)
    ax2 = ax1.twinx()
    ax2.plot(risk_df["scene_coverage"], risk_df["mean_accepted_ratio_macro"], color="#2ca02c", marker="^", label="Mean accepted ratio")
    ax2.scatter(
        [canonical_point["scene_coverage"]],
        [canonical_point["mean_accepted_ratio_macro"]],
        marker="*",
        s=160,
        color="#2ca02c",
        edgecolor="black",
        linewidth=0.5,
        zorder=5,
    )
    ax2.set_ylabel("Accepted ratio (higher is better)")
    ax2.set_ylim(0, 1.05)
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3, fontsize=8)
    ax1.set_title("Risk-coverage profile over scene reliability ranking")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out_dir / "risk_coverage_curve.pdf")
    fig.savefig(out_dir / "risk_coverage_curve.png", dpi=220)
    plt.close(fig)

    score_rows = sensitivity_df[sensitivity_df["threshold_type"] == "reliability_score"].copy()
    fig, ax1 = plt.subplots(figsize=(7.6, 4.4))
    ax1.plot(score_rows["threshold_value"], score_rows["retained_scene_count"], marker="o", label="Retained scenes")
    ax1.invert_xaxis()
    ax1.set_xlabel("Reliability score threshold")
    ax1.set_ylabel("Retained scenes")
    ax1.set_ylim(0, len(df) + 1)
    ax2 = ax1.twinx()
    ax2.plot(score_rows["threshold_value"], score_rows["pair_coverage_micro"], color="#ff7f0e", marker="s", label="Pair coverage")
    ax2.set_ylabel("Pair coverage")
    ax2.set_ylim(0, 1.05)
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines + lines2, labels + labels2, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2, fontsize=8)
    ax1.set_title("Threshold sensitivity of reliability-controlled retention")
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(out_dir / "threshold_sensitivity.pdf")
    fig.savefig(out_dir / "threshold_sensitivity.png", dpi=220)
    plt.close(fig)

    light = cond_df[cond_df["group_by"] == "light_condition"].copy()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    x = range(len(light))
    ax.bar([i - 0.18 for i in x], light["canonical_scene_retention_macro"], width=0.36, label="Scene retention")
    ax.bar([i + 0.18 for i in x], light["accepted_attempted_ratio_micro"], width=0.36, label="Accepted / attempted")
    ax.set_xticks(list(x), light["group"].tolist())
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Ratio")
    ax.set_title("Condition-aware reliability profile by illumination")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out_dir / "condition_reliability_profile.pdf")
    fig.savefig(out_dir / "condition_reliability_profile.png", dpi=220)
    plt.close(fig)


def write_design_doc(out_dir: Path) -> None:
    text = """# Reliability Score Design

This P0-D analysis uses an interpretable, non-trained scene reliability score.
It is designed for ranking, threshold sweep, and risk-coverage visualization,
not as a learned replacement for the canonical QA-controlled scene criterion.

## Inputs

The score uses scene-level quantities already produced by the UAV-TAlign QA
pipeline:

- accepted ratio among attempted frames;
- severe baseline-relative QA outlier ratio;
- robust consensus reject ratio;
- edge-overlap improvement after alignment;
- gradient-NCC improvement after alignment;
- a lightweight geometry diagnostic from inlier ratio, spatial coverage, and
  reprojection error.

## Normalization

- `accepted_score = clip(accepted_ratio, 0, 1)`.
- `outlier_score = 1 - clip(severe_outlier_ratio / 0.10, 0, 1)`.
- `robust_score = 1 - clip(robust_reject_ratio / 0.25, 0, 1)`.
- `edge_score = clip((delta_edge_f1 + 0.05) / 0.20, 0, 1)`.
- `grad_score = clip(delta_grad_ncc / 0.15, 0, 1)`.
- `geometry_score = 0.5 * clip(mean_inlier_ratio / 0.50, 0, 1)
  + 0.3 * clip(mean_coverage, 0, 1)
  + 0.2 * (1 - clip((mean_reproj_error - 1.5) / 1.0, 0, 1))`.

## Score

`reliability_score = 100 * (0.25 accepted_score + 0.25 outlier_score
+ 0.20 robust_score + 0.15 edge_score + 0.10 grad_score
+ 0.05 geometry_score)`.

The largest weights are assigned to retained evidence, QA outlier control, and
robust consensus behavior because these terms directly express the
scene-level reliability question. Edge/gradient gains provide image-domain
supporting evidence, while geometry statistics are retained as a low-weight
diagnostic rather than a single absolute quality ordering.

## Paper-facing usage

The strict canonical result remains the primary operating point. The score is
used to show the broader reliability--coverage profile and threshold
sensitivity of the same completed 12K first-wave run.
"""
    (out_dir / "reliability_score_design.md").write_text(text, encoding="utf-8")


def write_summary(
    out_dir: Path,
    summary: dict,
    df: pd.DataFrame,
    risk_df: pd.DataFrame,
    sensitivity_df: pd.DataFrame,
    cond_df: pd.DataFrame,
    canonical_point: dict,
) -> None:
    canonical_pass = int(df["canonical_scene_pass"].sum())
    total = int(len(df))
    top9 = risk_df[risk_df["retained_scene_count"] == 9].iloc[0]
    regimes = sensitivity_df[sensitivity_df["threshold_type"] == "named_operating_regime"]
    lines = [
        "# P0-D Protocol Closure Summary",
        "",
        "## Run Provenance",
        f"- P0-C output root: `{summary['output_root']}`",
        f"- Official manifest: `{summary['dataset_manifest']['manifest_path']}`",
        f"- Manifest canonical SHA256: `{summary['dataset_manifest']['manifest_sha256']}`",
        f"- Valid evaluation pairs: `{summary['dataset_manifest']['valid_pair_count']}`",
        f"- Git commit: `{summary['runtime_environment']['git_commit']}`",
        "",
        "## Main Findings",
        f"- UAV-TAlign produces scene-level homographies for `{total}/{total}` scenes and retains `{canonical_pass}/{total}` scenes under the strict canonical QA-controlled operating point.",
        "- The P0-D reliability score provides an interpretable ordering for coverage analysis without changing the canonical result.",
        f"- The canonical QA gate retains `{canonical_point['retained_scene_ids']}` with scene coverage `{_pct(canonical_point['scene_coverage'])}` and pair coverage `{_pct(canonical_point['pair_coverage_micro'])}`.",
        f"- At 9 retained scenes by score ranking, scene coverage is `{_pct(top9['scene_coverage'])}` and pair coverage is `{_pct(top9['pair_coverage_micro'])}`; the mean severe-outlier ratio is `{top9['mean_severe_outlier_ratio']:.3f}`.",
        "- The score-ranked top-K operating points and the canonical retained-scene set are related but not identical; the score-ranked curve is used for operating-profile visualization, not as a replacement for the canonical QA gate.",
        "- Risk-coverage and threshold-sensitivity curves should be used to present the operating trade-off rather than relaxing the canonical result.",
        "",
        "## Named Operating Regimes",
        "| Regime | Retained scenes | Scene coverage | Pair coverage | Mean severe outlier | Mean robust reject |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for _, row in regimes.iterrows():
        lines.append(
            f"| {row['threshold_value']} | {int(row['retained_scene_count'])} | {_pct(row['scene_coverage'])} | "
            f"{_pct(row['pair_coverage_micro'])} | {float(row['mean_severe_outlier_ratio']):.3f} | "
            f"{float(row['mean_robust_reject_ratio']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Artifacts",
            "- `reliability_score_design.md`",
            "- `per_scene_reliability_table.csv`",
            "- `canonical_operating_point.csv`",
            "- `risk_coverage.csv` and `risk_coverage_curve.pdf/png`",
            "- `threshold_sensitivity.csv` and `threshold_sensitivity.pdf/png`",
            "- `condition_reliability_profile.csv` and `condition_reliability_profile.pdf/png`",
            "",
            "## Suggested Paper Wording",
            "Under the strict canonical reliability gate, UAV-TAlign produces scene-level homographies for all 15 scenes and retains 9 scenes as high-confidence operating points. The risk-coverage curve is a score-ranked operating profile, with the canonical 9/15 point marked explicitly; it visualizes reliability--coverage trade-offs without replacing the canonical decision rule.",
        ]
    )
    (out_dir / "paper_facing_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input_dir",
        type=Path,
        default=Path("review_artifacts/ipt_p0c_12k_first_wave_20260516_0325"),
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=Path("review_artifacts/ipt_p0d_protocol_closure_20260516_0515"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = input_dir / "uav_talign_full_scene_metrics_detailed.jsonl"
    summary_path = input_dir / "main_experiment_summary.json"
    rows = load_jsonl(metrics_path)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    df = pd.DataFrame(rows)
    if "view" in df.columns:
        df["view"] = df["view"].fillna("general").replace({"None": "general", "": "general"})
    df = add_reliability_score(df)
    df = df.sort_values("scene_id")
    risk_df = build_risk_coverage(df)
    canonical_point = build_canonical_operating_point(df)
    sensitivity_df = build_threshold_sensitivity(df)
    cond_df = build_condition_profile(df)

    per_scene_columns = [
        "scene_id",
        "scene_name",
        "light_condition",
        "thermal_rendering",
        "view",
        "valid_pairs",
        "qa_status",
        "canonical_scene_pass",
        "reliability_score",
        "reliability_rank",
        "accepted_frames",
        "attempted_frames",
        "accepted_ratio",
        "accepted_total_ratio",
        "severe_outlier_count",
        "severe_outlier_ratio",
        "robust_reject_ratio",
        "delta_edge_f1",
        "delta_grad_ncc",
        "improved_grad_ratio",
        "median_disp_to_aggregate_mean_px",
        "mean_inlier_ratio",
        "mean_coverage",
        "mean_reproj_error",
        "qa_warning_codes",
    ]
    df[per_scene_columns].sort_values("scene_id").to_csv(output_dir / "per_scene_reliability_table.csv", index=False)
    pd.DataFrame([canonical_point]).to_csv(output_dir / "canonical_operating_point.csv", index=False)
    risk_df.to_csv(output_dir / "risk_coverage.csv", index=False)
    sensitivity_df.to_csv(output_dir / "threshold_sensitivity.csv", index=False)
    cond_df.to_csv(output_dir / "condition_reliability_profile.csv", index=False)

    write_design_doc(output_dir)
    save_figures(df, risk_df, sensitivity_df, cond_df, canonical_point, output_dir)
    write_summary(output_dir, summary, df, risk_df, sensitivity_df, cond_df, canonical_point)

    print(output_dir)


if __name__ == "__main__":
    main()
