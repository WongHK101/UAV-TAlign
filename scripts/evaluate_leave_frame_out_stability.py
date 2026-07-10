from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median

import numpy as np

from utils.minima_match_utils import (
    homography_pair_displacement_summary,
    normalize_homography_matrix,
    robust_aggregate_homographies_weighted,
)


def percentile(values: list[float], q: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), q)) if values else 0.0


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def assert_isolated_output(input_dir: Path, output_dir: Path) -> None:
    if input_dir == output_dir or input_dir in output_dir.parents or output_dir in input_dir.parents:
        raise ValueError("Output directory must be isolated from the immutable input directory.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate leave-frame-out UAV-TAlign consensus stability.")
    parser.add_argument("--input_dir", required=True, type=Path)
    parser.add_argument("--output_dir", required=True, type=Path)
    parser.add_argument("--folds", type=int, default=5)
    args = parser.parse_args()

    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    assert_isolated_output(input_dir, output_dir)
    scene_root = input_dir / "uav_talign_full"
    if not scene_root.is_dir():
        raise FileNotFoundError(f"Missing scene output directory: {scene_root}")

    fold_rows: list[dict] = []
    scene_rows: list[dict] = []
    for scene_dir in sorted(path for path in scene_root.iterdir() if path.is_dir()):
        scene_path = scene_dir / "scene_result.json"
        if not scene_path.is_file():
            continue
        payload = json.loads(scene_path.read_text(encoding="utf-8"))
        record = payload.get("record", {})
        band = payload.get("band_payload", {})
        attempts = [item for item in band.get("match_attempts", []) if bool(item.get("accepted", False))]
        attempts.sort(key=lambda item: str(item.get("frame_id", item.get("image_name", ""))))
        if len(attempts) < 4:
            continue

        homographies = [normalize_homography_matrix(np.asarray(item["homography"], dtype=np.float64)) for item in attempts]
        weights = [float(item.get("quality_score", 1.0) or 1.0) for item in attempts]
        full_h = robust_aggregate_homographies_weighted(homographies, weights)
        stored_h = normalize_homography_matrix(np.asarray(band.get("T_aggregate", full_h), dtype=np.float64))
        stability = band.get("homography_stability", {})
        source_shape = stability.get("source_shape", [1024, 1280])
        stored_delta = homography_pair_displacement_summary(stored_h, full_h, source_shape)

        folds = min(max(int(args.folds), 2), len(attempts))
        scene_fold_rows: list[dict] = []
        for fold_index in range(folds):
            keep_indices = [index for index in range(len(attempts)) if index % folds != fold_index]
            held_indices = [index for index in range(len(attempts)) if index % folds == fold_index]
            fold_h = robust_aggregate_homographies_weighted(
                [homographies[index] for index in keep_indices],
                [weights[index] for index in keep_indices],
            )
            displacement = homography_pair_displacement_summary(full_h, fold_h, source_shape)
            row = {
                "scene_id": str(record.get("scene_id", "")),
                "scene_name": str(record.get("scene_name", scene_dir.name)),
                "canonical_scene_pass": bool(record.get("canonical_scene_pass", False)),
                "fold": fold_index,
                "accepted_frames": len(attempts),
                "kept_frames": len(keep_indices),
                "held_out_frames": len(held_indices),
                "mean_displacement_px": displacement["mean_px"],
                "median_displacement_px": displacement["median_px"],
                "max_displacement_px": displacement["max_px"],
                "mean_displacement_rel": displacement["mean_rel"],
            }
            fold_rows.append(row)
            scene_fold_rows.append(row)

        means = [float(row["mean_displacement_px"]) for row in scene_fold_rows]
        scene_rows.append(
            {
                "scene_id": str(record.get("scene_id", "")),
                "scene_name": str(record.get("scene_name", scene_dir.name)),
                "canonical_scene_pass": bool(record.get("canonical_scene_pass", False)),
                "accepted_frames": len(attempts),
                "folds": folds,
                "mean_leave_out_displacement_px": mean(means),
                "median_leave_out_displacement_px": median(means),
                "p95_leave_out_displacement_px": percentile(means, 95),
                "max_leave_out_displacement_px": max(means),
                "stored_vs_recomputed_mean_px": stored_delta["mean_px"],
            }
        )

    if not scene_rows:
        raise ValueError("No eligible scene results were found.")

    output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(output_dir / "leave_frame_out_folds.csv", fold_rows, list(fold_rows[0]))
    write_csv(output_dir / "leave_frame_out_per_scene.csv", scene_rows, list(scene_rows[0]))

    retained = [row for row in scene_rows if row["canonical_scene_pass"]]
    filtered = [row for row in scene_rows if not row["canonical_scene_pass"]]
    summary = {
        "input_dir": str(input_dir),
        "scene_count": len(scene_rows),
        "fold_count": len(fold_rows),
        "all_scene_mean_displacement_px": mean(row["mean_leave_out_displacement_px"] for row in scene_rows),
        "retained_scene_mean_displacement_px": mean(
            row["mean_leave_out_displacement_px"] for row in retained
        ) if retained else None,
        "filtered_scene_mean_displacement_px": mean(
            row["mean_leave_out_displacement_px"] for row in filtered
        ) if filtered else None,
        "retained_scene_count": len(retained),
        "filtered_scene_count": len(filtered),
        "max_stored_vs_recomputed_mean_px": max(row["stored_vs_recomputed_mean_px"] for row in scene_rows),
    }
    (output_dir / "leave_frame_out_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
