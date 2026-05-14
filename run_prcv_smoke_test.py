from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path
from typing import Dict, List

import numpy as np

from estimate_band_homographies import estimate_band_homographies
from utils.baseline_backends import create_pairwise_matcher, run_pairwise_registration
from utils.prepared_scene_adapter import build_prepared_scene_from_pairs
from utils.uav_talign_dataset import PairRecord, build_smoke_test_pairs, group_pairs_by_scene, manifest_provenance


DEFAULT_METHODS = (
    "sift_ransac",
    "akaze_ransac",
    "loftr_outdoor",
    "roma_outdoor",
    "xoftr_official",
    "raw_minima",
    "uav_talign_full",
)


def _str2bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


def _parse_methods(raw: str) -> List[str]:
    methods = []
    for item in str(raw).split(","):
        method = item.strip()
        if method and method not in methods:
            methods.append(method)
    if not methods:
        raise ValueError("No smoke-test methods were provided.")
    return methods


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def _validate_runtime_isolation(
    dataset_root: Path,
    output_root: Path,
    minima_root: Path,
) -> Dict[str, object]:
    dataset_root = dataset_root.resolve()
    output_root = output_root.resolve()
    minima_root = minima_root.resolve()

    conflicts: List[str] = []
    checks = (
        ("dataset_root", dataset_root),
        ("minima_root", minima_root),
    )
    for other_name, other_path in checks:
        if output_root == other_path:
            conflicts.append(f"output_root must not equal {other_name}: {output_root}")
        if _is_relative_to(output_root, other_path):
            conflicts.append(f"output_root must not be inside {other_name}: {output_root}")
        if _is_relative_to(other_path, output_root):
            conflicts.append(f"{other_name} must not be inside output_root: {other_path}")

    if conflicts:
        raise ValueError("Unsafe runtime path layout detected:\n- " + "\n- ".join(conflicts))

    return {
        "dataset_root": str(dataset_root),
        "dataset_write_policy": "read_only_expected",
        "minima_root": str(minima_root),
        "minima_write_policy": "read_only_expected",
        "output_root": str(output_root),
        "prepared_root_parent": str((output_root / "_prepared").resolve()),
        "notes": [
            "All smoke artifacts must stay under output_root.",
            "The raw dataset root and algorithm source directories are treated as read-only inputs.",
        ],
    }


def _resolve_smoke_min_good_frames(num_pairs: int, explicit_value: int, ratio: float) -> int:
    total = max(int(num_pairs), 0)
    if explicit_value and explicit_value > 0:
        return max(1, min(total, int(explicit_value)))
    computed = int(math.ceil(float(ratio) * float(max(total, 1))))
    return max(1, min(total, computed))


def _set_reproducible_seed(seed: int) -> None:
    random.seed(int(seed))
    np.random.seed(int(seed))
    try:
        import torch

        torch.manual_seed(int(seed))
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(int(seed))
    except Exception:
        pass


def _scene_result_record(
    method: str,
    scene_name: str,
    scene_id: str,
    runtime_sec: float,
    band_payload: Dict[str, object],
    smoke_min_good_frames: int,
    pairs: List[PairRecord],
) -> Dict[str, object]:
    accepted_summary = (band_payload.get("match_summary", {}) or {}).get("accepted", {})
    num_matches_summary = accepted_summary.get("num_matches_after_conf", {}) or {}
    num_inliers_summary = accepted_summary.get("num_inliers", {}) or {}
    inlier_ratio_summary = accepted_summary.get("inlier_ratio", {}) or {}
    reproj_summary = accepted_summary.get("reproj_error", {}) or {}
    coverage_summary = accepted_summary.get("coverage", {}) or {}
    num_attempted_frames = int(band_payload.get("num_attempted_frames", 0))
    num_accepted_frames = int(band_payload.get("num_accepted_frames", 0))
    canonical_min_good_frames = int(band_payload.get("canonical_min_good_frames", 0))
    qa_status = str(band_payload.get("qa_status", "unknown"))
    homography_available = bool(band_payload.get("T_opt"))
    canonical_scene_pass = bool(
        band_payload.get(
            "canonical_scene_pass",
            num_accepted_frames >= canonical_min_good_frames and qa_status in {"pass", "pass_with_warning"},
        )
    )
    smoke_scene_pass = bool(num_accepted_frames >= int(smoke_min_good_frames) and homography_available)
    if canonical_scene_pass:
        status = "ok"
    elif smoke_scene_pass:
        status = "smoke_pass_canonical_fail"
    else:
        status = "smoke_fail_canonical_fail"
    return {
        "method": method,
        "scene_id": scene_id,
        "scene_name": scene_name,
        "pair_id": "__scene__",
        "status": status,
        "num_matches": int(round(float(num_matches_summary.get("mean", 0.0) or 0.0))),
        "num_inliers": int(round(float(num_inliers_summary.get("mean", 0.0) or 0.0))),
        "inlier_ratio": float(inlier_ratio_summary.get("mean", 0.0) or 0.0),
        "reprojection_error": reproj_summary.get("mean"),
        "coverage": float(coverage_summary.get("mean", 0.0) or 0.0),
        "homography_available": bool(homography_available),
        "qa_status": qa_status,
        "num_attempted_frames": int(num_attempted_frames),
        "num_accepted_frames": int(num_accepted_frames),
        "accepted_frames": int(num_accepted_frames),
        "canonical_min_good_frames": int(canonical_min_good_frames),
        "canonical_scene_pass": bool(canonical_scene_pass),
        "smoke_min_good_frames": int(smoke_min_good_frames),
        "smoke_scene_pass": bool(smoke_scene_pass),
        "canonical_failure_reason": band_payload.get("canonical_failure_reason"),
        "canonical_threshold_note": band_payload.get("canonical_threshold_note"),
        "source_pair_ids": [pair.pair_id for pair in pairs],
        "source_rgb_filenames": [Path(pair.rgb_path).name for pair in pairs],
        "source_thermal_filenames": [Path(pair.thermal_path).name for pair in pairs],
        "runtime_sec": float(runtime_sec),
    }


def _run_uav_talign_scene_method(
    scene_name: str,
    pairs: List[PairRecord],
    output_root: Path,
    minima_root: Path,
    minima_device: str,
    minima_method: str,
    minima_ckpt: str,
    input_dynamic_range: str,
    radiometric_mode: str,
    smoke_min_good_frames: int,
) -> Dict[str, object]:
    prepared_root = output_root / "_prepared" / scene_name
    build_prepared_scene_from_pairs(pairs=pairs, out_root=prepared_root, band_name="T")

    method_root = output_root / "uav_talign_full" / scene_name
    method_root.mkdir(parents=True, exist_ok=True)
    homography_json = method_root / "rectification_homographies.json"

    start = time.time()
    try:
        payload = estimate_band_homographies(
            prepared_root=prepared_root,
            out_json=homography_json,
            bands="T",
            frame_count=len(pairs),
            input_dynamic_range=input_dynamic_range,
            radiometric_mode=radiometric_mode,
            minima_root=str(minima_root),
            minima_device=minima_device,
            minima_method=minima_method,
            minima_ckpt=minima_ckpt,
            rectification_allow_insufficient_frames=True,
        )
        runtime_sec = time.time() - start
        band_payload = payload["bands"]["T"]
        record = _scene_result_record(
            method="uav_talign_full",
            scene_name=scene_name,
            scene_id=str(pairs[0].scene_id),
            runtime_sec=runtime_sec,
            band_payload=band_payload,
            smoke_min_good_frames=smoke_min_good_frames,
            pairs=pairs,
        )
        _write_json(method_root / "smoke_result.json", {"record": record, "band_payload": band_payload})
    except Exception as exc:
        runtime_sec = time.time() - start
        record = {
            "method": "uav_talign_full",
            "scene_id": str(pairs[0].scene_id),
            "scene_name": scene_name,
            "pair_id": "__scene__",
            "status": "error",
            "num_matches": 0,
            "num_inliers": 0,
            "inlier_ratio": 0.0,
            "reprojection_error": None,
            "coverage": 0.0,
            "homography_available": False,
            "qa_status": "error",
            "num_attempted_frames": int(len(pairs)),
            "num_accepted_frames": 0,
            "accepted_frames": 0,
            "canonical_min_good_frames": int(len(pairs)),
            "canonical_scene_pass": False,
            "smoke_min_good_frames": int(smoke_min_good_frames),
            "smoke_scene_pass": False,
            "canonical_failure_reason": "unexpected_exception",
            "canonical_threshold_note": (
                "canonical threshold retained for formal runs; on 5-pair smoke subsets "
                "it should be interpreted as a stress-test criterion"
            ),
            "source_pair_ids": [pair.pair_id for pair in pairs],
            "source_rgb_filenames": [Path(pair.rgb_path).name for pair in pairs],
            "source_thermal_filenames": [Path(pair.thermal_path).name for pair in pairs],
            "runtime_sec": float(runtime_sec),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        _write_json(method_root / "smoke_result.json", {"record": record, "error": record})
    return record


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Run the UAV-TAlign smoke test with optional manifest-filtered evaluation.")
    ap.add_argument("--dataset_root", default=str(repo_root / "UAV-TAlign-1K"))
    ap.add_argument("--manifest_path", default="")
    ap.add_argument("--output_root", default=str(repo_root / "outputs" / "prcv_smoke_test"))
    ap.add_argument("--methods", default=",".join(DEFAULT_METHODS))
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--loftr_match_max_dim", type=int, default=0)
    ap.add_argument("--loftr_use_amp", type=_str2bool, nargs="?", const=True, default=False)
    ap.add_argument("--minima_root", default=str(repo_root / "third_party" / "MINIMA"))
    ap.add_argument("--official_xoftr_ckpt", default="")
    ap.add_argument("--raw_minima_method", default="roma", choices=["roma", "xoftr"])
    ap.add_argument("--raw_minima_ckpt", default="")
    ap.add_argument("--uav_talign_minima_method", default="roma", choices=["roma", "xoftr"])
    ap.add_argument("--uav_talign_minima_ckpt", default="")
    ap.add_argument("--uav_talign_smoke_min_good_frames", type=int, default=0)
    ap.add_argument("--uav_talign_smoke_min_ratio", type=float, default=0.60)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--input_dynamic_range", default="uint8", choices=["uint8", "uint16", "float"])
    ap.add_argument("--radiometric_mode", default="raw_dn", choices=["raw_dn", "exposure_normalized", "reflectance_ready_stub"])
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    minima_root = Path(args.minima_root).resolve()
    _set_reproducible_seed(int(args.seed))
    isolation_info = _validate_runtime_isolation(
        dataset_root=dataset_root,
        output_root=output_root,
        minima_root=minima_root,
    )

    methods = _parse_methods(args.methods)
    manifest_path = args.manifest_path.strip() or None
    dataset_manifest = manifest_provenance(dataset_root=dataset_root, manifest_path=manifest_path)
    smoke_pairs = build_smoke_test_pairs(dataset_root, manifest_path=manifest_path)
    grouped_pairs = group_pairs_by_scene(smoke_pairs)

    all_records: List[Dict[str, object]] = []
    method_summaries: Dict[str, Dict[str, object]] = {}

    pairwise_methods = [method for method in methods if method != "uav_talign_full"]
    for method in pairwise_methods:
        method_root = output_root / method
        method_root.mkdir(parents=True, exist_ok=True)
        matcher = create_pairwise_matcher(
            method=method,
            repo_root=repo_root,
            device=args.device,
            official_xoftr_ckpt=args.official_xoftr_ckpt,
            raw_minima_method=args.raw_minima_method,
            raw_minima_ckpt=args.raw_minima_ckpt,
            loftr_match_max_dim=args.loftr_match_max_dim,
            loftr_use_amp=args.loftr_use_amp,
        )
        method_records = []
        for pair in smoke_pairs:
            start = time.time()
            record = run_pairwise_registration(
                method=method,
                matcher=matcher,
                rgb_path=pair.rgb_path,
                thermal_path=pair.thermal_path,
                scene_id=pair.scene_id,
                scene_name=pair.scene_name,
                pair_id=pair.pair_id,
            )
            record["runtime_sec"] = float(time.time() - start)
            method_records.append(record)
            all_records.append(record)
        _write_json(method_root / "smoke_results.json", {"records": method_records})
        status_counts: Dict[str, int] = {}
        for record in method_records:
            status = str(record["status"])
            status_counts[status] = status_counts.get(status, 0) + 1
        method_summaries[method] = {
            "num_records": int(len(method_records)),
            "status_counts": status_counts,
        }

    if "uav_talign_full" in methods:
        scene_records = []
        for scene_name, pairs in grouped_pairs.items():
            smoke_min_good_frames = _resolve_smoke_min_good_frames(
                num_pairs=len(pairs),
                explicit_value=args.uav_talign_smoke_min_good_frames,
                ratio=args.uav_talign_smoke_min_ratio,
            )
            record = _run_uav_talign_scene_method(
                scene_name=scene_name,
                pairs=pairs,
                output_root=output_root,
                minima_root=minima_root,
                minima_device=args.device,
                minima_method=args.uav_talign_minima_method,
                minima_ckpt=args.uav_talign_minima_ckpt,
                input_dynamic_range=args.input_dynamic_range,
                radiometric_mode=args.radiometric_mode,
                smoke_min_good_frames=smoke_min_good_frames,
            )
            scene_records.append(record)
            all_records.append(record)
        _write_json(output_root / "uav_talign_full" / "smoke_results.json", {"records": scene_records})
        status_counts: Dict[str, int] = {}
        for record in scene_records:
            status = str(record["status"])
            status_counts[status] = status_counts.get(status, 0) + 1
        method_summaries["uav_talign_full"] = {
            "num_records": int(len(scene_records)),
            "status_counts": status_counts,
            "canonical_scene_pass_count": int(sum(1 for record in scene_records if bool(record.get("canonical_scene_pass", False)))),
            "smoke_scene_pass_count": int(sum(1 for record in scene_records if bool(record.get("smoke_scene_pass", False)))),
        }

    final_summary = {
        "dataset_root": str(dataset_root),
        "dataset_manifest": dataset_manifest,
        "output_root": str(output_root),
        "methods": methods,
        "device": str(args.device),
        "loftr_match_max_dim": int(args.loftr_match_max_dim),
        "loftr_use_amp": bool(args.loftr_use_amp),
        "uav_talign_smoke_policy": {
            "canonical_min_good_frames_source": "estimate_band_homographies.minima_min_good_frames",
            "smoke_min_good_frames": None if int(args.uav_talign_smoke_min_good_frames) <= 0 else int(args.uav_talign_smoke_min_good_frames),
            "smoke_min_ratio": float(args.uav_talign_smoke_min_ratio),
            "smoke_rule": "explicit_threshold" if int(args.uav_talign_smoke_min_good_frames) > 0 else "ceil(smoke_min_ratio * scene_pair_count)",
            "seed": int(args.seed),
            "canonical_threshold_note": (
                "canonical threshold retained for formal runs; on 5-pair smoke subsets "
                "it should be interpreted as a stress-test criterion"
            ),
            "smoke_subset_pair_ids_by_scene": {scene_name: [pair.pair_id for pair in pairs] for scene_name, pairs in grouped_pairs.items()},
        },
        "runtime_isolation": isolation_info,
        "smoke_pairs": [
            {
                "scene_name": pair.scene_name,
                "scene_id": pair.scene_id,
                "pair_id": pair.pair_id,
                "rgb_path": pair.rgb_path,
                "thermal_path": pair.thermal_path,
            }
            for pair in smoke_pairs
        ],
        "method_summaries": method_summaries,
    }
    _write_json(output_root / "smoke_test_summary.json", final_summary)
    print(json.dumps(final_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
