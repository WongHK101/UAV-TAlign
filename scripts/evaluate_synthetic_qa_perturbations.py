from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from statistics import mean

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.minima_match_utils import homography_pair_displacement_summary, normalize_homography_matrix
from utils.rectification_utils import score_edge_overlap_f1, score_gradient_ncc


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def assert_isolated_output(dataset_root: Path, input_dir: Path, output_dir: Path) -> None:
    forbidden = (dataset_root, input_dir)
    for root in forbidden:
        if output_dir == root or root in output_dir.parents or output_dir in root.parents:
            raise ValueError(f"Output directory must be isolated from read-only input: {root}")


def read_gray(path: Path) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"Could not decode image: {path}")
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image = np.asarray(image, dtype=np.float32)
    lo, hi = np.percentile(image, [1.0, 99.0])
    if hi <= lo:
        return np.zeros(image.shape, dtype=np.uint8)
    return np.clip((image - lo) * 255.0 / (hi - lo), 0.0, 255.0).astype(np.uint8)


def resize_gray(image: np.ndarray, max_dim: int) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    scale = min(1.0, float(max_dim) / float(max(height, width)))
    if scale == 1.0:
        return image, scale
    resized = cv2.resize(
        image,
        (max(int(round(width * scale)), 16), max(int(round(height * scale)), 16)),
        interpolation=cv2.INTER_AREA,
    )
    return resized, scale


def scale_homography(homography: np.ndarray, target_scale: float, source_scale: float) -> np.ndarray:
    target = np.diag([target_scale, target_scale, 1.0])
    source_inv = np.diag([1.0 / source_scale, 1.0 / source_scale, 1.0])
    return normalize_homography_matrix(target @ homography @ source_inv)


def prepared_planes(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    blurred = cv2.GaussianBlur(image, (5, 5), 0)
    edges = cv2.Canny(blurred, 40, 120) > 0
    gx = cv2.Sobel(blurred.astype(np.float32) / 255.0, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(blurred.astype(np.float32) / 255.0, cv2.CV_32F, 0, 1, ksize=3)
    gradient = np.sqrt(gx * gx + gy * gy)
    return edges, gradient


def score_alignment(rgb: np.ndarray, thermal: np.ndarray, homography: np.ndarray) -> dict[str, float]:
    height, width = rgb.shape[:2]
    warped = cv2.warpPerspective(thermal, homography, (width, height), flags=cv2.INTER_LINEAR)
    mask = cv2.warpPerspective(
        np.ones(thermal.shape, dtype=np.uint8), homography, (width, height), flags=cv2.INTER_NEAREST
    ) > 0
    rgb_edges, rgb_grad = prepared_planes(rgb)
    thermal_edges, thermal_grad = prepared_planes(warped)
    edge = score_edge_overlap_f1(rgb_edges, thermal_edges, mask, dilate_radius=1)
    grad = score_gradient_ncc(rgb_grad, thermal_grad, mask)
    joint = 0.5 * edge + 0.5 * ((grad + 1.0) / 2.0)
    return {"edge_f1": float(edge), "grad_ncc": float(grad), "joint_score": float(joint), "valid_ratio": float(mask.mean())}


def deterministic_sign(scene_name: str, image_name: str, mode: str) -> float:
    digest = hashlib.sha256(f"{scene_name}|{image_name}|{mode}".encode("utf-8")).digest()
    return 1.0 if digest[0] % 2 == 0 else -1.0


def perturbation(mode: str, severity_px: float, width: int, height: int, sign: float) -> np.ndarray:
    cx, cy = 0.5 * (width - 1), 0.5 * (height - 1)
    if mode == "translation":
        angle = math.radians(31.0 if sign > 0 else 211.0)
        return np.asarray(
            [[1.0, 0.0, severity_px * math.cos(angle)], [0.0, 1.0, severity_px * math.sin(angle)], [0.0, 0.0, 1.0]],
            dtype=np.float64,
        )
    radius = max(0.5 * math.hypot(width, height), 1.0)
    if mode == "rotation":
        angle_deg = math.degrees(sign * severity_px / radius)
        affine = cv2.getRotationMatrix2D((cx, cy), angle_deg, 1.0)
    elif mode == "scale":
        scale = 1.0 + sign * severity_px / radius
        affine = cv2.getRotationMatrix2D((cx, cy), 0.0, scale)
    else:
        raise ValueError(f"Unsupported perturbation mode: {mode}")
    return np.vstack([affine, [0.0, 0.0, 1.0]]).astype(np.float64)


def rankdata(values: list[float]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(len(array), dtype=np.float64)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and array[order[end]] == array[order[start]]:
            end += 1
        ranks[order[start:end]] = 0.5 * (start + end - 1) + 1.0
        start = end
    return ranks


def spearman(values_x: list[float], values_y: list[float]) -> float:
    if len(values_x) < 2:
        return 0.0
    return float(np.corrcoef(rankdata(values_x), rankdata(values_y))[0, 1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate UAV-TAlign QA proxies with known transform perturbations.")
    parser.add_argument("--dataset_root", required=True, type=Path)
    parser.add_argument("--input_dir", required=True, type=Path)
    parser.add_argument("--output_dir", required=True, type=Path)
    parser.add_argument("--frames_per_scene", type=int, default=3)
    parser.add_argument("--max_dim", type=int, default=768)
    parser.add_argument("--severities", default="2,5,10,20,40")
    parser.add_argument("--modes", default="translation,rotation,scale")
    args = parser.parse_args()

    dataset_root = args.dataset_root.resolve()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    assert_isolated_output(dataset_root, input_dir, output_dir)
    scene_root = input_dir / "uav_talign_full"
    if not scene_root.is_dir():
        raise FileNotFoundError(f"Missing scene output directory: {scene_root}")
    severities = [float(value) for value in args.severities.split(",") if value.strip()]
    modes = [value.strip() for value in args.modes.split(",") if value.strip()]

    rows: list[dict] = []
    for scene_dir in sorted(path for path in scene_root.iterdir() if path.is_dir()):
        scene_path = scene_dir / "scene_result.json"
        if not scene_path.is_file():
            continue
        payload = json.loads(scene_path.read_text(encoding="utf-8"))
        record = payload.get("record", {})
        band = payload.get("band_payload", {})
        names = list(band.get("qa_representative_image_names", []))[: max(int(args.frames_per_scene), 1)]
        full_h = normalize_homography_matrix(np.asarray(band.get("T_opt", record.get("homography")), dtype=np.float64))
        for image_name in names:
            rgb_raw = read_gray(dataset_root / scene_dir.name / "rgb" / image_name)
            thermal_raw = read_gray(dataset_root / scene_dir.name / "thermal" / image_name)
            rgb, rgb_scale = resize_gray(rgb_raw, int(args.max_dim))
            thermal, thermal_scale = resize_gray(thermal_raw, int(args.max_dim))
            homography = scale_homography(full_h, rgb_scale, thermal_scale)
            baseline = score_alignment(rgb, thermal, homography)
            for mode in modes:
                sign = deterministic_sign(scene_dir.name, image_name, mode)
                for severity in severities:
                    delta_h = perturbation(mode, severity, rgb.shape[1], rgb.shape[0], sign)
                    displaced = homography_pair_displacement_summary(
                        np.eye(3, dtype=np.float64), delta_h, rgb.shape, grid_size=5
                    )
                    score = score_alignment(rgb, thermal, delta_h @ homography)
                    rows.append(
                        {
                            "scene_id": str(record.get("scene_id", "")),
                            "scene_name": scene_dir.name,
                            "canonical_scene_pass": bool(record.get("canonical_scene_pass", False)),
                            "image_name": image_name,
                            "mode": mode,
                            "severity_px": severity,
                            "known_mean_displacement_px": displaced["mean_px"],
                            "baseline_edge_f1": baseline["edge_f1"],
                            "perturbed_edge_f1": score["edge_f1"],
                            "delta_edge_f1": score["edge_f1"] - baseline["edge_f1"],
                            "baseline_grad_ncc": baseline["grad_ncc"],
                            "perturbed_grad_ncc": score["grad_ncc"],
                            "delta_grad_ncc": score["grad_ncc"] - baseline["grad_ncc"],
                            "baseline_joint_score": baseline["joint_score"],
                            "perturbed_joint_score": score["joint_score"],
                            "delta_joint_score": score["joint_score"] - baseline["joint_score"],
                            "valid_ratio": score["valid_ratio"],
                        }
                    )

    if not rows:
        raise ValueError("No perturbation records were generated.")
    output_dir.mkdir(parents=True, exist_ok=False)
    write_csv(output_dir / "synthetic_perturbation_trials.csv", rows, list(rows[0]))

    aggregate_rows: list[dict] = []
    for mode in modes:
        for severity in severities:
            subset = [row for row in rows if row["mode"] == mode and row["severity_px"] == severity]
            aggregate_rows.append(
                {
                    "mode": mode,
                    "severity_px": severity,
                    "trial_count": len(subset),
                    "mean_known_displacement_px": mean(row["known_mean_displacement_px"] for row in subset),
                    "mean_delta_edge_f1": mean(row["delta_edge_f1"] for row in subset),
                    "mean_delta_grad_ncc": mean(row["delta_grad_ncc"] for row in subset),
                    "mean_delta_joint_score": mean(row["delta_joint_score"] for row in subset),
                    "fraction_joint_degraded": mean(1.0 if row["delta_joint_score"] < 0.0 else 0.0 for row in subset),
                }
            )
    write_csv(output_dir / "synthetic_perturbation_summary.csv", aggregate_rows, list(aggregate_rows[0]))

    summary = {
        "dataset_root": str(dataset_root),
        "input_dir": str(input_dir),
        "scene_count": len({row["scene_name"] for row in rows}),
        "image_count": len({(row["scene_name"], row["image_name"]) for row in rows}),
        "trial_count": len(rows),
        "spearman_displacement_vs_edge": spearman(
            [row["known_mean_displacement_px"] for row in rows], [row["perturbed_edge_f1"] for row in rows]
        ),
        "spearman_displacement_vs_grad": spearman(
            [row["known_mean_displacement_px"] for row in rows], [row["perturbed_grad_ncc"] for row in rows]
        ),
        "spearman_displacement_vs_joint": spearman(
            [row["known_mean_displacement_px"] for row in rows], [row["perturbed_joint_score"] for row in rows]
        ),
        "overall_fraction_joint_degraded": mean(
            1.0 if row["delta_joint_score"] < 0.0 else 0.0 for row in rows
        ),
    }
    (output_dir / "synthetic_perturbation_report.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
