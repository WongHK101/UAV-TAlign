from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from build_rectified_band_dataset import build_rectified_band_dataset
from estimate_band_homographies import estimate_band_homographies
from qa_rectification import run_rectification_qa


def _str2bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def run_pipeline(args) -> dict:
    prepared_root = Path(args.prepared_root).resolve()
    rectified_root = Path(args.rectified_root).resolve()
    rectified_root.mkdir(parents=True, exist_ok=True)

    homography_json = Path(args.homography_json).resolve() if args.homography_json else (
        rectified_root / "rectification_homographies.json"
    )

    homography_payload = estimate_band_homographies(
        prepared_root=prepared_root,
        out_json=homography_json,
        bands=args.bands,
        frame_count=args.frame_count,
        input_dynamic_range=args.input_dynamic_range,
        radiometric_mode=args.radiometric_mode,
        rectification_use_metadata_h0=args.rectification_use_metadata_h0,
        rectification_high_modality_bands=args.rectification_high_modality_bands,
        rectification_warning_min_accepted_ratio=args.rectification_warning_min_accepted_ratio,
        rectification_warning_min_delta_edge_f1=args.rectification_warning_min_delta_edge_f1,
        rectification_warning_min_grad_improved_ratio=args.rectification_warning_min_grad_improved_ratio,
        rectification_warning_max_severe_outlier_ratio=args.rectification_warning_max_severe_outlier_ratio,
        rectification_warning_max_severe_outlier_count=args.rectification_warning_max_severe_outlier_count,
        rectification_stability_warn_mean_px=args.rectification_stability_warn_mean_px,
        rectification_stability_max_reject_ratio=args.rectification_stability_max_reject_ratio,
        rectification_backend="minima",
        minima_method=args.minima_method,
        minima_root=args.minima_root,
        minima_device=args.minima_device,
        minima_ckpt=args.minima_ckpt,
        minima_roma_size=args.minima_roma_size,
        minima_match_threshold=args.minima_match_threshold,
        minima_fine_threshold=args.minima_fine_threshold,
        minima_match_max_dim=args.minima_match_max_dim,
        minima_match_conf_thresh=args.minima_match_conf_thresh,
        minima_min_matches=args.minima_min_matches,
        minima_min_inlier_ratio=args.minima_min_inlier_ratio,
        minima_max_reproj_error=args.minima_max_reproj_error,
        minima_min_coverage=args.minima_min_coverage,
        minima_coverage_grid=args.minima_coverage_grid,
        minima_ransac_method=args.minima_ransac_method,
        minima_ransac_thresh=args.minima_ransac_thresh,
        minima_ransac_confidence=args.minima_ransac_confidence,
        minima_ransac_max_iters=args.minima_ransac_max_iters,
        minima_min_good_frames=args.minima_min_good_frames,
        minima_initial_candidate_ratio=args.minima_initial_candidate_ratio,
        minima_candidate_ratio_step=args.minima_candidate_ratio_step,
        minima_max_candidate_ratio=args.minima_max_candidate_ratio,
        minima_use_all_if_needed=args.minima_use_all_if_needed,
        minima_full_if_frames_le=args.minima_full_if_frames_le,
    )

    build_manifest = build_rectified_band_dataset(
        prepared_root=prepared_root,
        rectified_root=rectified_root,
        homography_json=homography_json,
        bands=args.bands,
    )

    qa_homography_json = rectified_root / "rectification_homographies.json"
    if homography_json.resolve() != qa_homography_json.resolve():
        shutil.copy2(homography_json, qa_homography_json)

    qa_summary = run_rectification_qa(
        prepared_root=prepared_root,
        rectified_root=rectified_root,
        out_root=rectified_root / "rectification_qa",
        bands=args.bands,
        input_dynamic_range=args.input_dynamic_range,
        radiometric_mode=args.radiometric_mode,
        frame_count=args.qa_frames,
        min_improved_ratio=args.rectification_min_improved_ratio,
        max_severe_outliers=args.rectification_max_severe_outliers,
        qa_scale=args.rectification_qa_scale,
        warning_continue_enabled=args.rectification_allow_warning_continue,
    )

    summary = {
        "prepared_root": str(prepared_root),
        "rectified_root": str(rectified_root),
        "homography_json": str(homography_json),
        "homography_qa_status_counts": homography_payload.get("qa_status_counts", {}),
        "final_qa_status_counts": qa_summary.get("qa_status_counts", {}),
        "build_manifest": build_manifest,
    }
    summary_path = rectified_root / "uav_talign_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    default_minima_root = repo_root / "third_party" / "MINIMA"

    ap = argparse.ArgumentParser(description="Run UAV-TAlign RGB-thermal rectification.")
    ap.add_argument("--prepared_root", required=True)
    ap.add_argument("--rectified_root", required=True)
    ap.add_argument("--homography_json", default="")
    ap.add_argument("--bands", default="T")
    ap.add_argument("--frame_count", type=int, default=12)
    ap.add_argument("--qa_frames", type=int, default=6)
    ap.add_argument("--input_dynamic_range", default="uint16", choices=["uint8", "uint16", "float"])
    ap.add_argument("--radiometric_mode", default="exposure_normalized", choices=["raw_dn", "exposure_normalized", "reflectance_ready_stub"])

    ap.add_argument("--rectification_use_metadata_h0", type=_str2bool, nargs="?", const=True, default=True)
    ap.add_argument("--rectification_high_modality_bands", default="T,THERMAL,TIR")
    ap.add_argument("--rectification_min_improved_ratio", type=float, default=0.6)
    ap.add_argument("--rectification_max_severe_outliers", type=int, default=0)
    ap.add_argument("--rectification_warning_min_accepted_ratio", type=float, default=0.80)
    ap.add_argument("--rectification_warning_min_delta_edge_f1", type=float, default=-0.05)
    ap.add_argument("--rectification_warning_min_grad_improved_ratio", type=float, default=0.60)
    ap.add_argument("--rectification_warning_max_severe_outlier_ratio", type=float, default=0.10)
    ap.add_argument("--rectification_warning_max_severe_outlier_count", type=int, default=1)
    ap.add_argument("--rectification_stability_warn_mean_px", type=float, default=25.0)
    ap.add_argument("--rectification_stability_max_reject_ratio", type=float, default=0.25)
    ap.add_argument("--rectification_qa_scale", type=float, default=1.0)
    ap.add_argument("--rectification_allow_warning_continue", type=_str2bool, nargs="?", const=True, default=True)

    ap.add_argument("--minima_method", default="roma", choices=["roma", "xoftr"])
    ap.add_argument("--minima_root", default=str(default_minima_root))
    ap.add_argument("--minima_device", default="cuda")
    ap.add_argument("--minima_ckpt", default="")
    ap.add_argument("--minima_roma_size", default="large", choices=["large", "tiny"])
    ap.add_argument("--minima_match_threshold", type=float, default=0.3)
    ap.add_argument("--minima_fine_threshold", type=float, default=0.1)
    ap.add_argument("--minima_match_max_dim", type=int, default=1600)
    ap.add_argument("--minima_match_conf_thresh", type=float, default=0.2)
    ap.add_argument("--minima_min_matches", type=int, default=80)
    ap.add_argument("--minima_min_inlier_ratio", type=float, default=0.30)
    ap.add_argument("--minima_max_reproj_error", type=float, default=4.0)
    ap.add_argument("--minima_min_coverage", type=float, default=0.25)
    ap.add_argument("--minima_coverage_grid", type=int, default=4)
    ap.add_argument("--minima_ransac_method", default="usac_magsac", choices=["usac_magsac", "ransac"])
    ap.add_argument("--minima_ransac_thresh", type=float, default=3.0)
    ap.add_argument("--minima_ransac_confidence", type=float, default=0.999)
    ap.add_argument("--minima_ransac_max_iters", type=int, default=10000)
    ap.add_argument("--minima_min_good_frames", type=int, default=0)
    ap.add_argument("--minima_initial_candidate_ratio", type=float, default=0.15)
    ap.add_argument("--minima_candidate_ratio_step", type=float, default=0.15)
    ap.add_argument("--minima_max_candidate_ratio", type=float, default=0.50)
    ap.add_argument("--minima_use_all_if_needed", type=_str2bool, nargs="?", const=True, default=True)
    ap.add_argument("--minima_full_if_frames_le", type=int, default=300)

    args = ap.parse_args()
    summary = run_pipeline(args)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
