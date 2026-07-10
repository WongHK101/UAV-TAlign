from __future__ import annotations

import argparse
import gc
import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

from estimate_band_homographies import estimate_band_homographies
from utils.baseline_backends import create_pairwise_matcher, run_pairwise_registration
from utils.prepared_scene_adapter import build_prepared_scene_from_pairs
from utils.uav_talign_dataset import PairRecord, group_pairs_by_scene, list_dataset_pairs, manifest_provenance


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
        raise ValueError("No PRCV methods were provided.")
    return methods


def _parse_scene_names(raw: str) -> List[str] | None:
    items = [item.strip() for item in str(raw).split(",") if item.strip()]
    return items or None


def _parse_pair_ids_by_scene(raw: str) -> Dict[str, List[str]] | None:
    value = str(raw or "").strip()
    if not value:
        return None
    candidate_path = Path(value)
    if candidate_path.exists():
        payload = json.loads(candidate_path.read_text(encoding="utf-8"))
    else:
        payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("--pair_ids_by_scene_json must decode to an object mapping scene names to pair-id lists.")
    parsed: Dict[str, List[str]] = {}
    for scene_name, pair_ids in payload.items():
        if not isinstance(pair_ids, list):
            raise ValueError(f"Pair IDs for scene {scene_name!r} must be provided as a list.")
        parsed[str(scene_name)] = [str(pair_id).strip() for pair_id in pair_ids if str(pair_id).strip()]
    return parsed


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
            "All experiment artifacts must stay under output_root.",
            "The raw dataset root and algorithm source directories are treated as read-only inputs.",
        ],
    }


def _write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_jsonl_records(path: Path, records: Sequence[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _file_sha256(path: Path, chunk_size: int = 1 << 20) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _file_provenance(path_value: str | Path) -> Dict[str, object]:
    text = str(path_value or "").strip()
    if not text:
        return {"path": "", "exists": False}
    path = Path(text).resolve()
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size_bytes": int(stat.st_size),
        "mtime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
        "sha256": _file_sha256(path),
    }


def _git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            check=True,
            text=True,
            capture_output=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def _append_jsonl(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False))
        handle.write("\n")


def _load_jsonl(path: Path) -> List[Dict[str, object]]:
    if not path.exists():
        return []
    records: List[Dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        records.append(json.loads(text))
    return records


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


def _cleanup_torch() -> None:
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def _status_counts(records: Sequence[Dict[str, object]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for record in records:
        status = str(record.get("status", "unknown"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _value_summary(records: Sequence[Dict[str, object]], key: str) -> Dict[str, object]:
    values = []
    for record in records:
        value = record.get(key)
        if value is None:
            continue
        try:
            numeric = float(value)
        except Exception:
            continue
        if np.isfinite(numeric):
            values.append(numeric)
    if not values:
        return {
            "n": 0,
            "min": None,
            "mean": None,
            "median": None,
            "max": None,
            "std": None,
        }
    arr = np.asarray(values, dtype=np.float64)
    return {
        "n": int(arr.size),
        "min": float(np.min(arr)),
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "max": float(np.max(arr)),
        "std": float(np.std(arr)),
    }


def _pair_key(scene_name: str, pair_id: str) -> str:
    return f"{scene_name}::{pair_id}"


def _scene_key(scene_name: str) -> str:
    return str(scene_name)


def _resume_records(
    path: Path,
    key_builder,
    resume: bool,
) -> Tuple[List[Dict[str, object]], set[str]]:
    if not resume:
        return [], set()
    records = _load_jsonl(path)
    keys = {key_builder(record) for record in records}
    return records, keys


def _pair_meta(pair: PairRecord) -> Dict[str, object]:
    return {
        "scene_name": pair.scene_name,
        "scene_id": pair.scene_id,
        "pair_id": pair.pair_id,
        "rgb_path": pair.rgb_path,
        "thermal_path": pair.thermal_path,
        "light_condition": pair.light_condition,
        "thermal_rendering": pair.thermal_rendering,
        # ``view`` / ``scene_label`` are kept for backward compatibility with
        # the manifest field names. ``view_type`` / ``scene_family`` are the
        # protocol-aligned names used by the BENCHMARK_PROTOCOL.md schema and
        # by downstream P0-D summaries.
        "view": pair.view,
        "view_type": pair.view_type,
        "scene_label": pair.scene_label,
        "scene_family": pair.scene_family,
    }


def _pairwise_method_summary(records: Sequence[Dict[str, object]]) -> Dict[str, object]:
    return {
        "num_records": int(len(records)),
        "status_counts": _status_counts(records),
        "homography_available_count": int(sum(1 for record in records if bool(record.get("homography_available", False)))),
        "num_matches_summary": _value_summary(records, "num_matches"),
        "num_inliers_summary": _value_summary(records, "num_inliers"),
        "inlier_ratio_summary": _value_summary(records, "inlier_ratio"),
        "coverage_summary": _value_summary(records, "coverage"),
        "reprojection_error_summary": _value_summary(records, "reprojection_error"),
        "runtime_sec_summary": _value_summary(records, "runtime_sec"),
    }


def _uav_talign_method_summary(records: Sequence[Dict[str, object]]) -> Dict[str, object]:
    qa_status_counts: Dict[str, int] = {}
    for record in records:
        qa_status = str(record.get("qa_status", "unknown"))
        qa_status_counts[qa_status] = qa_status_counts.get(qa_status, 0) + 1
    return {
        "num_records": int(len(records)),
        "status_counts": _status_counts(records),
        "qa_status_counts": qa_status_counts,
        "canonical_scene_pass_count": int(sum(1 for record in records if bool(record.get("canonical_scene_pass", False)))),
        "homography_available_count": int(sum(1 for record in records if bool(record.get("homography_available", False)))),
        "accepted_frames_summary": _value_summary(records, "accepted_frames"),
        "attempted_frames_summary": _value_summary(records, "num_attempted_frames"),
        "runtime_sec_summary": _value_summary(records, "runtime_sec"),
    }


def _scene_result_record(
    scene_name: str,
    pairs: Sequence[PairRecord],
    runtime_sec: float,
    band_payload: Dict[str, object],
) -> Dict[str, object]:
    accepted_summary = (band_payload.get("match_summary", {}) or {}).get("accepted", {})
    num_matches_summary = accepted_summary.get("num_matches_after_conf", {}) or {}
    num_inliers_summary = accepted_summary.get("num_inliers", {}) or {}
    inlier_ratio_summary = accepted_summary.get("inlier_ratio", {}) or {}
    reproj_summary = accepted_summary.get("reproj_error", {}) or {}
    coverage_summary = accepted_summary.get("coverage", {}) or {}
    num_attempted_frames = int(band_payload.get("num_attempted_frames", 0))
    num_accepted_frames = int(band_payload.get("num_accepted_frames", 0))
    accepted_ratio = (
        float(num_accepted_frames) / float(num_attempted_frames)
        if num_attempted_frames > 0
        else 0.0
    )
    canonical_min_good_frames = int(band_payload.get("canonical_min_good_frames", 0))
    qa_status = str(band_payload.get("qa_status", "unknown"))
    homography_available = bool(band_payload.get("T_opt"))
    canonical_scene_pass = bool(band_payload.get("canonical_scene_pass", False))
    # Protocol-aligned 5-state status code:
    #   pass / pass_with_warning / fail / canonical_fail / error
    # ``canonical_scene_pass`` is the hard gate y_S; scenes that pass it inherit
    # ``pass`` (clean QA) or ``pass_with_warning`` (QA emitted warning side guards).
    # Scenes that fail it map to ``canonical_fail`` (specific failure reason)
    # or ``fail`` (generic QA failure with no canonical reason recorded).
    if canonical_scene_pass:
        status = "pass_with_warning" if qa_status == "pass_with_warning" else "pass"
    else:
        if band_payload.get("canonical_failure_reason"):
            status = "canonical_fail"
        else:
            status = "fail"
    return {
        "method": "uav_talign_full",
        "scene_id": str(pairs[0].scene_id),
        "scene_name": scene_name,
        "pair_id": "__scene__",
        "num_pairs_total": int(len(pairs)),
        "status": status,
        "light_condition": pairs[0].light_condition,
        "thermal_rendering": pairs[0].thermal_rendering,
        # Backward-compatible manifest-aligned names.
        "view": pairs[0].view,
        "scene_label": pairs[0].scene_label,
        # Protocol-aligned aliases (BENCHMARK_PROTOCOL.md schema).
        "view_type": pairs[0].view_type,
        "scene_family": pairs[0].scene_family,
        "num_matches": int(round(float(num_matches_summary.get("mean", 0.0) or 0.0))),
        "num_inliers": int(round(float(num_inliers_summary.get("mean", 0.0) or 0.0))),
        "inlier_ratio": float(inlier_ratio_summary.get("mean", 0.0) or 0.0),
        "reprojection_error": reproj_summary.get("mean"),
        "coverage": float(coverage_summary.get("mean", 0.0) or 0.0),
        "homography_available": bool(homography_available),
        "homography": band_payload.get("T_opt"),
        "qa_status": qa_status,
        "num_attempted_frames": int(num_attempted_frames),
        "num_accepted_frames": int(num_accepted_frames),
        "accepted_frames": int(num_accepted_frames),
        "accepted_ratio": float(accepted_ratio),
        "canonical_min_good_frames": int(canonical_min_good_frames),
        "canonical_scene_pass": bool(canonical_scene_pass),
        "canonical_failure_reason": band_payload.get("canonical_failure_reason"),
        "canonical_threshold_note": band_payload.get("canonical_threshold_note"),
        "source_pair_ids": [pair.pair_id for pair in pairs],
        "source_rgb_filenames": [Path(pair.rgb_path).name for pair in pairs],
        "source_thermal_filenames": [Path(pair.thermal_path).name for pair in pairs],
        "runtime_sec": float(runtime_sec),
    }


def _run_uav_talign_scene_method(
    scene_name: str,
    pairs: Sequence[PairRecord],
    output_root: Path,
    minima_root: Path,
    minima_device: str,
    minima_method: str,
    minima_ckpt: str,
    frame_count: int,
    min_good_frames: int,
    seed: int,
    input_dynamic_range: str,
    radiometric_mode: str,
    frame_selection_mode: str,
    scene_pass_policy: str,
    use_metadata_h0: bool,
    min_structure_score: float | None,
    aggregation_mode: str,
    initial_candidate_ratio: float,
    candidate_ratio_step: float,
    max_candidate_ratio: float,
    use_all_if_needed: bool,
    full_if_frames_le: int,
    warning_min_accepted_ratio: float,
    warning_max_severe_outlier_ratio: float,
    warning_max_severe_outlier_count: int,
    stability_warn_mean_px: float,
    stability_max_reject_ratio: float,
    max_severe_outliers: int,
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
            frame_count=int(frame_count),
            seed=int(seed),
            input_dynamic_range=input_dynamic_range,
            radiometric_mode=radiometric_mode,
            rectification_use_metadata_h0=bool(use_metadata_h0),
            rectification_min_structure_score=min_structure_score,
            rectification_frame_selection_mode=frame_selection_mode,
            rectification_scene_pass_policy=scene_pass_policy,
            rectification_max_severe_outliers=int(max_severe_outliers),
            rectification_warning_min_accepted_ratio=float(warning_min_accepted_ratio),
            rectification_warning_max_severe_outlier_ratio=float(warning_max_severe_outlier_ratio),
            rectification_warning_max_severe_outlier_count=int(warning_max_severe_outlier_count),
            rectification_stability_warn_mean_px=float(stability_warn_mean_px),
            rectification_stability_max_reject_ratio=float(stability_max_reject_ratio),
            minima_root=str(minima_root),
            minima_device=minima_device,
            minima_method=minima_method,
            minima_ckpt=minima_ckpt,
            minima_aggregation_mode=aggregation_mode,
            minima_min_good_frames=int(min_good_frames),
            minima_initial_candidate_ratio=float(initial_candidate_ratio),
            minima_candidate_ratio_step=float(candidate_ratio_step),
            minima_max_candidate_ratio=float(max_candidate_ratio),
            minima_use_all_if_needed=bool(use_all_if_needed),
            minima_full_if_frames_le=int(full_if_frames_le),
            rectification_allow_insufficient_frames=True,
        )
        runtime_sec = time.time() - start
        band_payload = payload["bands"]["T"]
        record = _scene_result_record(
            scene_name=scene_name,
            pairs=pairs,
            runtime_sec=runtime_sec,
            band_payload=band_payload,
        )
        _write_json(method_root / "scene_result.json", {"record": record, "band_payload": band_payload})
    except Exception as exc:
        runtime_sec = time.time() - start
        record = {
            "method": "uav_talign_full",
            "scene_id": str(pairs[0].scene_id),
            "scene_name": scene_name,
            "pair_id": "__scene__",
            "num_pairs_total": int(len(pairs)),
            "status": "error",
            "light_condition": pairs[0].light_condition,
            "thermal_rendering": pairs[0].thermal_rendering,
            "view": pairs[0].view,
            "scene_label": pairs[0].scene_label,
            "view_type": pairs[0].view_type,
            "scene_family": pairs[0].scene_family,
            "num_matches": 0,
            "num_inliers": 0,
            "inlier_ratio": 0.0,
            "reprojection_error": None,
            "coverage": 0.0,
            "homography_available": False,
            "homography": None,
            "qa_status": "error",
            "num_attempted_frames": 0,
            "num_accepted_frames": 0,
            "accepted_frames": 0,
            "canonical_min_good_frames": int(min_good_frames),
            "canonical_scene_pass": False,
            "canonical_failure_reason": "unexpected_exception",
            "canonical_threshold_note": None,
            "source_pair_ids": [pair.pair_id for pair in pairs],
            "source_rgb_filenames": [Path(pair.rgb_path).name for pair in pairs],
            "source_thermal_filenames": [Path(pair.thermal_path).name for pair in pairs],
            "runtime_sec": float(runtime_sec),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        _write_json(method_root / "scene_result.json", {"record": record, "error": record})
    return record


def main() -> None:
    repo_root = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description="Run formal UAV-TAlign experiments with optional manifest-filtered evaluation.")
    ap.add_argument("--dataset_root", default=str(repo_root / "UAV-TAlign-1K"))
    ap.add_argument("--manifest_path", default="")
    ap.add_argument("--output_root", default=str(repo_root / "outputs" / "prcv_main_experiment"))
    ap.add_argument("--methods", default="raw_minima,uav_talign_full")
    ap.add_argument("--scene_names", default="")
    ap.add_argument("--pair_ids_by_scene_json", default="")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--loftr_match_max_dim", type=int, default=0)
    ap.add_argument("--loftr_use_amp", type=_str2bool, nargs="?", const=True, default=False)
    ap.add_argument("--minima_root", default=str(repo_root / "third_party" / "MINIMA"))
    ap.add_argument("--official_xoftr_ckpt", default="")
    ap.add_argument("--raw_minima_method", default="roma", choices=["roma", "xoftr"])
    ap.add_argument("--raw_minima_ckpt", default="")
    ap.add_argument("--uav_talign_minima_method", default="roma", choices=["roma", "xoftr"])
    ap.add_argument("--uav_talign_minima_ckpt", default="")
    ap.add_argument("--uav_talign_frame_count", type=int, default=12)
    ap.add_argument("--uav_talign_min_good_frames", type=int, default=0)
    ap.add_argument("--uav_talign_use_metadata_h0", type=_str2bool, nargs="?", const=True, default=True)
    ap.add_argument("--uav_talign_min_structure_score", type=float, default=None)
    ap.add_argument("--uav_talign_frame_selection_mode", default="even", choices=["even", "random"])
    ap.add_argument("--uav_talign_scene_pass_policy", default="qa_status", choices=["qa_status", "legacy_pass", "accepted_only"])
    ap.add_argument("--uav_talign_aggregation_mode", default="robust_weighted", choices=["robust_weighted", "single_best"])
    ap.add_argument("--uav_talign_initial_candidate_ratio", type=float, default=0.15)
    ap.add_argument("--uav_talign_candidate_ratio_step", type=float, default=0.15)
    ap.add_argument("--uav_talign_max_candidate_ratio", type=float, default=0.50)
    ap.add_argument("--uav_talign_use_all_if_needed", type=_str2bool, nargs="?", const=True, default=True)
    ap.add_argument("--uav_talign_full_if_frames_le", type=int, default=300)
    ap.add_argument("--uav_talign_warning_min_accepted_ratio", type=float, default=0.80)
    ap.add_argument("--uav_talign_warning_max_severe_outlier_ratio", type=float, default=0.10)
    ap.add_argument("--uav_talign_warning_max_severe_outlier_count", type=int, default=1)
    ap.add_argument("--uav_talign_stability_warn_mean_px", type=float, default=25.0)
    ap.add_argument("--uav_talign_stability_max_reject_ratio", type=float, default=0.25)
    ap.add_argument("--uav_talign_max_severe_outliers", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--resume", type=_str2bool, nargs="?", const=True, default=True)
    ap.add_argument("--input_dynamic_range", default="uint8", choices=["uint8", "uint16", "float"])
    ap.add_argument("--radiometric_mode", default="raw_dn", choices=["raw_dn", "exposure_normalized", "reflectance_ready_stub"])
    args = ap.parse_args()

    dataset_root = Path(args.dataset_root).resolve()
    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    minima_root = Path(args.minima_root).resolve()
    methods = _parse_methods(args.methods)
    scene_names = _parse_scene_names(args.scene_names)
    pair_ids_by_scene = _parse_pair_ids_by_scene(args.pair_ids_by_scene_json)
    if scene_names is None and pair_ids_by_scene:
        scene_names = list(pair_ids_by_scene.keys())
    _set_reproducible_seed(int(args.seed))
    isolation_info = _validate_runtime_isolation(
        dataset_root=dataset_root,
        output_root=output_root,
        minima_root=minima_root,
    )

    manifest_path = args.manifest_path.strip() or None
    dataset_manifest = manifest_provenance(dataset_root=dataset_root, manifest_path=manifest_path)
    all_pairs = list_dataset_pairs(
        dataset_root=dataset_root,
        scene_names=scene_names,
        pair_ids_by_scene=pair_ids_by_scene,
        manifest_path=manifest_path,
    )
    grouped_pairs = group_pairs_by_scene(all_pairs)
    runtime_environment = {
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "git_commit": _git_commit(repo_root),
    }
    weight_provenance = {
        "raw_minima_ckpt": _file_provenance(args.raw_minima_ckpt),
        "uav_talign_minima_ckpt": _file_provenance(args.uav_talign_minima_ckpt),
        "official_xoftr_ckpt": _file_provenance(args.official_xoftr_ckpt),
        "loftr_source": "kornia.feature.LoFTR(pretrained='outdoor')",
        "roma_source": "third_party.MINIMA.third_party.RoMa_minima.romatch.roma_outdoor",
    }

    config_payload = {
        "dataset_root": str(dataset_root),
        "dataset_manifest": dataset_manifest,
        "output_root": str(output_root),
        "runtime_environment": runtime_environment,
        "weight_provenance": weight_provenance,
        "methods": methods,
        "scene_names": None if scene_names is None else list(scene_names),
        "pair_ids_by_scene": pair_ids_by_scene,
        "num_scenes": int(len(grouped_pairs)),
        "num_pairs": int(len(all_pairs)),
        "device": str(args.device),
        "loftr_match_max_dim": int(args.loftr_match_max_dim),
        "loftr_use_amp": bool(args.loftr_use_amp),
        "seed": int(args.seed),
        "resume": bool(args.resume),
        "raw_minima_method": str(args.raw_minima_method),
        "uav_talign_minima_method": str(args.uav_talign_minima_method),
        "uav_talign_frame_count": int(args.uav_talign_frame_count),
        "uav_talign_min_good_frames": int(args.uav_talign_min_good_frames),
        "uav_talign_use_metadata_h0": bool(args.uav_talign_use_metadata_h0),
        "uav_talign_min_structure_score": args.uav_talign_min_structure_score,
        "uav_talign_frame_selection_mode": str(args.uav_talign_frame_selection_mode),
        "uav_talign_scene_pass_policy": str(args.uav_talign_scene_pass_policy),
        "uav_talign_aggregation_mode": str(args.uav_talign_aggregation_mode),
        "uav_talign_initial_candidate_ratio": float(args.uav_talign_initial_candidate_ratio),
        "uav_talign_candidate_ratio_step": float(args.uav_talign_candidate_ratio_step),
        "uav_talign_max_candidate_ratio": float(args.uav_talign_max_candidate_ratio),
        "uav_talign_use_all_if_needed": bool(args.uav_talign_use_all_if_needed),
        "uav_talign_full_if_frames_le": int(args.uav_talign_full_if_frames_le),
        "uav_talign_warning_min_accepted_ratio": float(args.uav_talign_warning_min_accepted_ratio),
        "uav_talign_warning_max_severe_outlier_ratio": float(args.uav_talign_warning_max_severe_outlier_ratio),
        "uav_talign_warning_max_severe_outlier_count": int(args.uav_talign_warning_max_severe_outlier_count),
        "uav_talign_stability_warn_mean_px": float(args.uav_talign_stability_warn_mean_px),
        "uav_talign_stability_max_reject_ratio": float(args.uav_talign_stability_max_reject_ratio),
        "uav_talign_max_severe_outliers": int(args.uav_talign_max_severe_outliers),
        "input_dynamic_range": str(args.input_dynamic_range),
        "radiometric_mode": str(args.radiometric_mode),
        "runtime_isolation": isolation_info,
        "scene_inventory": [
            {
                "scene_name": scene_name,
                "scene_id": pairs[0].scene_id,
                "num_pairs": int(len(pairs)),
                "light_condition": pairs[0].light_condition,
                "thermal_rendering": pairs[0].thermal_rendering,
                "view": pairs[0].view,
                "scene_label": pairs[0].scene_label,
                "view_type": pairs[0].view_type,
                "scene_family": pairs[0].scene_family,
            }
            for scene_name, pairs in grouped_pairs.items()
        ],
    }
    _write_json(output_root / "experiment_config.json", config_payload)

    method_summaries: Dict[str, Dict[str, object]] = {}

    pairwise_methods = [method for method in methods if method != "uav_talign_full"]
    for method in pairwise_methods:
        method_root = output_root / method
        method_root.mkdir(parents=True, exist_ok=True)
        jsonl_path = method_root / "results.jsonl"
        method_records, seen_keys = _resume_records(
            jsonl_path,
            key_builder=lambda record: _pair_key(str(record.get("scene_name", "")), str(record.get("pair_id", ""))),
            resume=bool(args.resume),
        )

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
        try:
            for index, pair in enumerate(all_pairs, start=1):
                record_key = _pair_key(pair.scene_name, pair.pair_id)
                if record_key in seen_keys:
                    continue
                print(
                    f"[prcv-main:{method}] pair {index}/{len(all_pairs)} "
                    f"scene={pair.scene_name} pair={pair.pair_id}",
                    flush=True,
                )
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
                record.update(_pair_meta(pair))
                record["runtime_sec"] = float(time.time() - start)
                method_records.append(record)
                seen_keys.add(record_key)
                _append_jsonl(jsonl_path, record)
        finally:
            del matcher
            _cleanup_torch()

        _write_json(method_root / "results.json", {"records": method_records})
        method_summaries[method] = _pairwise_method_summary(method_records)

    if "uav_talign_full" in methods:
        method_root = output_root / "uav_talign_full"
        method_root.mkdir(parents=True, exist_ok=True)
        jsonl_path = method_root / "results.jsonl"
        compat_scene_jsonl_path = method_root / "scene_results.jsonl"
        compat_top_level_jsonl_path = output_root / "uav_talign_full_scene_metrics_detailed.jsonl"
        scene_records, seen_scene_keys = _resume_records(
            jsonl_path,
            key_builder=lambda record: _scene_key(str(record.get("scene_name", ""))),
            resume=bool(args.resume),
        )
        for scene_index, (scene_name, pairs) in enumerate(grouped_pairs.items(), start=1):
            if _scene_key(scene_name) in seen_scene_keys:
                continue
            print(
                f"[prcv-main:uav_talign_full] scene {scene_index}/{len(grouped_pairs)} "
                f"name={scene_name} pairs={len(pairs)}",
                flush=True,
            )
            record = _run_uav_talign_scene_method(
                scene_name=scene_name,
                pairs=pairs,
                output_root=output_root,
                minima_root=minima_root,
                minima_device=args.device,
                minima_method=args.uav_talign_minima_method,
                minima_ckpt=args.uav_talign_minima_ckpt,
                frame_count=int(args.uav_talign_frame_count),
                min_good_frames=int(args.uav_talign_min_good_frames),
                seed=int(args.seed),
                input_dynamic_range=args.input_dynamic_range,
                radiometric_mode=args.radiometric_mode,
                frame_selection_mode=args.uav_talign_frame_selection_mode,
                scene_pass_policy=args.uav_talign_scene_pass_policy,
                use_metadata_h0=bool(args.uav_talign_use_metadata_h0),
                min_structure_score=args.uav_talign_min_structure_score,
                aggregation_mode=args.uav_talign_aggregation_mode,
                initial_candidate_ratio=float(args.uav_talign_initial_candidate_ratio),
                candidate_ratio_step=float(args.uav_talign_candidate_ratio_step),
                max_candidate_ratio=float(args.uav_talign_max_candidate_ratio),
                use_all_if_needed=bool(args.uav_talign_use_all_if_needed),
                full_if_frames_le=int(args.uav_talign_full_if_frames_le),
                warning_min_accepted_ratio=float(args.uav_talign_warning_min_accepted_ratio),
                warning_max_severe_outlier_ratio=float(args.uav_talign_warning_max_severe_outlier_ratio),
                warning_max_severe_outlier_count=int(args.uav_talign_warning_max_severe_outlier_count),
                stability_warn_mean_px=float(args.uav_talign_stability_warn_mean_px),
                stability_max_reject_ratio=float(args.uav_talign_stability_max_reject_ratio),
                max_severe_outliers=int(args.uav_talign_max_severe_outliers),
            )
            scene_records.append(record)
            seen_scene_keys.add(_scene_key(scene_name))
            _append_jsonl(jsonl_path, record)
            _cleanup_torch()
        _write_json(method_root / "results.json", {"records": scene_records})
        _write_jsonl_records(compat_scene_jsonl_path, scene_records)
        _write_jsonl_records(compat_top_level_jsonl_path, scene_records)
        method_summaries["uav_talign_full"] = _uav_talign_method_summary(scene_records)

    final_summary = {
        "dataset_root": str(dataset_root),
        "dataset_manifest": dataset_manifest,
        "output_root": str(output_root),
        "runtime_environment": runtime_environment,
        "weight_provenance": weight_provenance,
        "methods": methods,
        "scene_names": None if scene_names is None else list(scene_names),
        "pair_ids_by_scene": pair_ids_by_scene,
        "num_scenes": int(len(grouped_pairs)),
        "num_pairs": int(len(all_pairs)),
        "seed": int(args.seed),
        "resume": bool(args.resume),
        "runtime_isolation": isolation_info,
        "method_summaries": method_summaries,
    }
    _write_json(output_root / "main_experiment_summary.json", final_summary)
    print(json.dumps(final_summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
