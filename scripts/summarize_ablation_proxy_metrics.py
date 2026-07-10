from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean


METRICS = (
    "delta_edge_f1",
    "delta_grad_ncc",
    "severe_outlier_ratio",
    "robust_reject_ratio",
    "median_disp_to_aggregate_mean_px",
)


def parse_stage(value: str) -> tuple[str, Path]:
    label, separator, path_text = value.partition("=")
    if not separator or not label.strip() or not path_text.strip():
        raise argparse.ArgumentTypeError("Stage must use LABEL=OUTPUT_DIR syntax.")
    return label.strip(), Path(path_text).expanduser().resolve()


def load_stage(label: str, output_dir: Path) -> list[dict]:
    scene_root = output_dir / "uav_talign_full"
    if not scene_root.is_dir():
        raise FileNotFoundError(f"Missing scene output directory: {scene_root}")

    rows: list[dict] = []
    for scene_dir in sorted(path for path in scene_root.iterdir() if path.is_dir()):
        scene_path = scene_dir / "scene_result.json"
        if not scene_path.is_file():
            continue
        payload = json.loads(scene_path.read_text(encoding="utf-8"))
        record = payload.get("record", {})
        band_payload = payload.get("band_payload", {})
        qa_inputs = band_payload.get("qa_decision_inputs", {})
        row = {
            "stage": label,
            "scene_id": str(record.get("scene_id", "")),
            "scene_name": str(record.get("scene_name", scene_dir.name)),
            "qa_status": str(band_payload.get("qa_status", record.get("qa_status", ""))),
            "canonical_scene_pass": bool(record.get("canonical_scene_pass", False)),
            "accepted_frames": int(record.get("accepted_frames", record.get("num_accepted_frames", 0)) or 0),
        }
        for metric in METRICS:
            row[metric] = float(qa_inputs.get(metric, 0.0) or 0.0)
        rows.append(row)
    if not rows:
        raise ValueError(f"No scene_result.json records found under {scene_root}")
    return rows


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize frozen UAV-TAlign ablation proxy metrics.")
    parser.add_argument("--stage", action="append", required=True, type=parse_stage)
    parser.add_argument("--output_dir", required=True, type=Path)
    args = parser.parse_args()

    labels = [label for label, _ in args.stage]
    if len(labels) != len(set(labels)):
        raise SystemExit("Stage labels must be unique.")

    per_scene_rows: list[dict] = []
    summary_rows: list[dict] = []
    for label, output_dir in args.stage:
        rows = load_stage(label, output_dir)
        per_scene_rows.extend(rows)
        summary = {
            "stage": label,
            "scene_count": len(rows),
            "stage_pass_count": sum(1 for row in rows if row["canonical_scene_pass"]),
            "qa_pass_count": sum(1 for row in rows if row["qa_status"] == "pass"),
            "mean_accepted_frames": mean(row["accepted_frames"] for row in rows),
        }
        for metric in METRICS:
            summary[f"mean_{metric}"] = mean(row[metric] for row in rows)
        summary_rows.append(summary)

    output_dir = args.output_dir.resolve()
    write_csv(
        output_dir / "ablation_proxy_per_scene.csv",
        per_scene_rows,
        [
            "stage",
            "scene_id",
            "scene_name",
            "qa_status",
            "canonical_scene_pass",
            "accepted_frames",
            *METRICS,
        ],
    )
    write_csv(
        output_dir / "ablation_proxy_summary.csv",
        summary_rows,
        [
            "stage",
            "scene_count",
            "stage_pass_count",
            "qa_pass_count",
            "mean_accepted_frames",
            *(f"mean_{metric}" for metric in METRICS),
        ],
    )
    print(json.dumps({"output_dir": str(output_dir), "summary": summary_rows}, indent=2))


if __name__ == "__main__":
    main()
