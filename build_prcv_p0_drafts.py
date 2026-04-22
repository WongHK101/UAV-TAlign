from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

import paramiko

from utils.uav_talign_dataset import list_dataset_pairs


SERVER_ROOTS = {
    "cpu": "/home/user2/whk/UAV-TAlign/outputs/prcv_sync_rerun_cpu_baselines_20260421_151245",
    "stage1": "/home/user2/whk/UAV-TAlign/outputs/prcv_sync_rerun_main_wave1_gpu0_20260421_151245",
    "stage2": "/home/user2/whk/UAV-TAlign/outputs/prcv_sync_rerun_gpu_baselines_20260421_151245",
    "loftr_salvage": "/home/user2/whk/UAV-TAlign/outputs/prcv_loftr_salvage_gpu0_20260421_220118",
}


PAIRWISE_METHOD_ORDER = [
    ("raw_minima", "raw MINIMA"),
    ("roma_outdoor", "official pretrained RoMa via local wrapper"),
    ("xoftr_official", "official pretrained XoFTR-640 via local wrapper"),
    ("akaze_ransac", "AKAZE + RANSAC"),
    ("sift_ransac", "SIFT + RANSAC"),
    ("loftr_outdoor", 'Kornia LoFTR (pretrained="outdoor")'),
]


def _read_remote_text(sftp: paramiko.SFTPClient, path: str) -> str:
    with sftp.open(path, "r") as handle:
        return handle.read().decode("utf-8", errors="replace")


def _read_remote_jsonl(sftp: paramiko.SFTPClient, path: str) -> List[Dict[str, object]]:
    return [json.loads(line) for line in _read_remote_text(sftp, path).splitlines() if line.strip()]


def _fmt_pct(value: float | None) -> float | None:
    return round(100.0 * value, 1) if value is not None else None


def _mean_numeric(values: Iterable[object]) -> float | None:
    numeric: List[float] = []
    for value in values:
        if value is None:
            continue
        try:
            converted = float(value)
        except Exception:
            continue
        if math.isfinite(converted):
            numeric.append(converted)
    return float(statistics.mean(numeric)) if numeric else None


def _write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No rows to write for {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _md_table(rows: List[Dict[str, object]], columns: List[tuple[str, str]]) -> str:
    header = "| " + " | ".join(label for _, label in columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    lines = [header, sep]
    for row in rows:
        values = []
        for key, _ in columns:
            value = row.get(key, "")
            if value is None:
                value = ""
            elif isinstance(value, float):
                value = f"{value:.3f}"
            values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _warning_set(row: Dict[str, object]) -> set[str]:
    return {item.strip() for item in str(row.get("warning_codes", "")).split(",") if item.strip()}


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--repo_root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--dataset_root", default="")
    return parser


def main() -> None:
    args = _build_argument_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    dataset_root = Path(args.dataset_root).resolve() if args.dataset_root else (repo_root / "UAV-TAlign-1K").resolve()
    docs_root = repo_root / "docs"
    review_root = repo_root / "review_artifacts"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = review_root / f"prcv_p0_structuring_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    remote_files = {
        "sift_ransac": SERVER_ROOTS["cpu"] + "/sift_ransac/results.jsonl",
        "akaze_ransac": SERVER_ROOTS["cpu"] + "/akaze_ransac/results.jsonl",
        "raw_minima": SERVER_ROOTS["stage1"] + "/raw_minima/results.jsonl",
        "uav_talign_full": SERVER_ROOTS["stage1"] + "/uav_talign_full/results.jsonl",
        "roma_outdoor": SERVER_ROOTS["stage2"] + "/roma_outdoor/results.jsonl",
        "xoftr_official": SERVER_ROOTS["stage2"] + "/xoftr_official/results.jsonl",
        "loftr_outdoor": SERVER_ROOTS["loftr_salvage"] + "/loftr_outdoor/results.jsonl",
    }

    pairs = list_dataset_pairs(dataset_root)
    scene_meta: Dict[str, Dict[str, object]] = {}
    scene_pair_count: Counter[str] = Counter()
    for pair in pairs:
        scene_pair_count[pair.scene_name] += 1
        scene_meta[pair.scene_name] = {
            "scene_id": pair.scene_id,
            "scene_name": pair.scene_name,
            "light_condition": pair.light_condition,
            "thermal_rendering": pair.thermal_rendering,
            "view": pair.view,
            "scene_label": pair.scene_label,
        }
    for scene_name, count in scene_pair_count.items():
        scene_meta[scene_name]["pair_count"] = count

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=args.host, username=args.username, password=args.password, timeout=15)
    sftp = client.open_sftp()
    results = {method: _read_remote_jsonl(sftp, path) for method, path in remote_files.items()}
    scene_payloads = {}
    for record in results["uav_talign_full"]:
        scene = str(record["scene_name"])
        scene_path = SERVER_ROOTS["stage1"] + f"/uav_talign_full/{scene}/scene_result.json"
        scene_payloads[scene] = json.loads(_read_remote_text(sftp, scene_path))
    sftp.close()
    client.close()

    pairwise_main_rows: List[Dict[str, object]] = []
    for method, label in PAIRWISE_METHOD_ORDER:
        records = results[method]
        num_records = len(records)
        status_counts = Counter(str(record.get("status", "unknown")) for record in records)
        ok_count = status_counts.get("ok", 0)
        homography_count = sum(1 for record in records if bool(record.get("homography_available", False)))
        method_notes = ""
        if method == "loftr_outdoor":
            method_notes = "Resize-aware inference (`match_max_dim=1600`, `use_amp=false`)."
        unusable_full_run = num_records == 0 or (ok_count == 0 and homography_count == 0 and status_counts.get("error", 0) == num_records)
        pairwise_main_rows.append(
            {
                "method_id": method,
                "method_label": label,
                "num_records": num_records,
                "ok_count": ok_count,
                "ok_rate_pct": _fmt_pct(ok_count / num_records if num_records else None),
                "homography_rate_pct": _fmt_pct(homography_count / num_records if num_records else None),
                "mean_inlier_ratio": _mean_numeric(record.get("inlier_ratio") for record in records),
                "mean_coverage": _mean_numeric(record.get("coverage") for record in records),
                "mean_reprojection_error": _mean_numeric(
                    record.get("reprojection_error") for record in records if record.get("status") == "ok"
                ),
                "mean_runtime_sec": _mean_numeric(record.get("runtime_sec") for record in records),
                "status_counts": json.dumps(dict(status_counts), ensure_ascii=False),
                "usable_for_quant_table": not unusable_full_run,
                "notes": method_notes,
            }
        )

    uav_scene_rows: List[Dict[str, object]] = []
    for record in sorted(results["uav_talign_full"], key=lambda item: str(item["scene_name"])):
        scene = str(record["scene_name"])
        payload = scene_payloads[scene]["band_payload"]
        qa_inputs = payload.get("qa_decision_inputs") or {}
        scores = payload.get("scores") or {}
        adaptive_schedule = payload.get("adaptive_schedule") or []
        meta = scene_meta[scene]
        accepted_frames = int(record.get("accepted_frames", 0))
        attempted_frames = int(record.get("num_attempted_frames", 0))
        uav_scene_rows.append(
            {
                "scene_id": meta["scene_id"],
                "scene_name": scene,
                "light_condition": meta["light_condition"],
                "thermal_rendering": meta["thermal_rendering"],
                "view": meta["view"],
                "scene_label": meta["scene_label"],
                "pair_count": scene_pair_count[scene],
                "uav_status": record.get("status"),
                "qa_status": record.get("qa_status"),
                "canonical_scene_pass": bool(record.get("canonical_scene_pass")),
                "accepted_frames": accepted_frames,
                "attempted_frames": attempted_frames,
                "accepted_ratio": qa_inputs.get("accepted_ratio", accepted_frames / max(attempted_frames, 1)),
                "num_matches": record.get("num_matches"),
                "num_inliers": record.get("num_inliers"),
                "mean_inlier_ratio": qa_inputs.get("mean_inlier_ratio", record.get("inlier_ratio")),
                "mean_coverage": qa_inputs.get("mean_coverage", record.get("coverage")),
                "mean_reprojection_error": qa_inputs.get("mean_reproj_error", record.get("reprojection_error")),
                "delta_edge_f1": qa_inputs.get("delta_edge_f1"),
                "delta_grad_ncc": qa_inputs.get("delta_grad_ncc"),
                "improved_grad_ratio": qa_inputs.get("improved_grad_ratio"),
                "match_ok": qa_inputs.get("match_ok"),
                "geometry_ok": qa_inputs.get("geometry_ok"),
                "stability_ok": qa_inputs.get("stability_ok"),
                "grad_ok": qa_inputs.get("grad_ok"),
                "edge_floor_ok": qa_inputs.get("edge_floor_ok"),
                "qa_outlier_ok": qa_inputs.get("qa_outlier_ok"),
                "warning_path_ok": qa_inputs.get("warning_path_ok"),
                "robust_reject_ratio": qa_inputs.get("robust_reject_ratio"),
                "severe_outlier_ratio": qa_inputs.get("severe_outlier_ratio"),
                "severe_outlier_count": qa_inputs.get("severe_outlier_count"),
                "median_disp_to_aggregate_mean_px": qa_inputs.get("median_disp_to_aggregate_mean_px"),
                "warning_codes": ", ".join(payload.get("qa_warning_codes") or []),
                "representative_images": ", ".join(
                    (payload.get("qa_representative_image_names") or scores.get("representative_image_names") or [])[:3]
                ),
                "adaptive_rounds": len(adaptive_schedule),
                "runtime_sec": record.get("runtime_sec"),
            }
        )

    scene_breakdown_rows: List[Dict[str, object]] = []
    for scene in sorted(scene_meta):
        meta = scene_meta[scene]
        row: Dict[str, object] = {
            "scene_id": meta["scene_id"],
            "scene_name": scene,
            "light_condition": meta["light_condition"],
            "thermal_rendering": meta["thermal_rendering"],
            "view": meta["view"],
            "scene_label": meta["scene_label"],
            "pair_count": scene_pair_count[scene],
        }
        for method in ["sift_ransac", "akaze_ransac", "loftr_outdoor", "raw_minima", "roma_outdoor", "xoftr_official"]:
            method_records = [record for record in results[method] if record["scene_name"] == scene]
            ok_count = sum(1 for record in method_records if record.get("status") == "ok")
            row[f"{method}_ok_rate_pct"] = _fmt_pct(ok_count / len(method_records))
        uav_row = next(scene_row for scene_row in uav_scene_rows if scene_row["scene_name"] == scene)
        row.update(
            {
                "uav_status": uav_row["uav_status"],
                "uav_accepted_ratio_pct": _fmt_pct(float(uav_row["accepted_ratio"])),
                "uav_delta_edge_f1": uav_row["delta_edge_f1"],
                "uav_delta_grad_ncc": uav_row["delta_grad_ncc"],
                "uav_robust_reject_ratio": uav_row["robust_reject_ratio"],
                "uav_warning_codes": uav_row["warning_codes"],
            }
        )
        row["classical_mean_ok_rate_pct"] = round(
            (float(row["sift_ransac_ok_rate_pct"]) + float(row["akaze_ransac_ok_rate_pct"])) / 2.0,
            1,
        )
        scene_breakdown_rows.append(row)

    condition_breakdown_pairwise_rows: List[Dict[str, object]] = []
    for condition_type in ["light_condition", "thermal_rendering", "view"]:
        values = sorted({getattr(pair, condition_type) for pair in pairs}, key=str)
        subset_keys = {
            condition_value: {(pair.scene_name, pair.pair_id) for pair in pairs if getattr(pair, condition_type) == condition_value}
            for condition_value in values
        }
        for condition_value, keys in subset_keys.items():
            for method, label in PAIRWISE_METHOD_ORDER:
                method_records = [
                    record for record in results[method] if (record["scene_name"], record["pair_id"]) in keys
                ]
                if not method_records:
                    continue
                ok_count = sum(1 for record in method_records if record.get("status") == "ok")
                condition_breakdown_pairwise_rows.append(
                    {
                        "condition_type": condition_type,
                        "condition_value": condition_value,
                        "num_pairs": len(method_records),
                        "method_id": method,
                        "method_label": label,
                        "ok_count": ok_count,
                        "ok_rate_pct": _fmt_pct(ok_count / len(method_records)),
                        "mean_inlier_ratio": _mean_numeric(record.get("inlier_ratio") for record in method_records),
                        "mean_coverage": _mean_numeric(record.get("coverage") for record in method_records),
                        "mean_reprojection_error": _mean_numeric(
                            record.get("reprojection_error")
                            for record in method_records
                            if record.get("status") == "ok"
                        ),
                    }
                )

    condition_breakdown_uav_rows: List[Dict[str, object]] = []
    for condition_type in ["light_condition", "thermal_rendering", "view"]:
        values = sorted({scene_row[condition_type] for scene_row in uav_scene_rows}, key=str)
        for condition_value in values:
            method_rows = [row for row in uav_scene_rows if row[condition_type] == condition_value]
            pass_count = sum(1 for row in method_rows if row["uav_status"] == "ok")
            matching_scene_rows = [row for row in scene_breakdown_rows if row[condition_type] == condition_value]
            condition_breakdown_uav_rows.append(
                {
                    "condition_type": condition_type,
                    "condition_value": condition_value,
                    "num_scenes": len(method_rows),
                    "pass_count": pass_count,
                    "pass_rate_pct": _fmt_pct(pass_count / len(method_rows)),
                    "mean_accepted_ratio_pct": _fmt_pct(_mean_numeric(row["accepted_ratio"] for row in method_rows)),
                    "mean_delta_edge_f1": _mean_numeric(row["delta_edge_f1"] for row in method_rows),
                    "mean_delta_grad_ncc": _mean_numeric(row["delta_grad_ncc"] for row in method_rows),
                    "mean_robust_reject_ratio": _mean_numeric(row["robust_reject_ratio"] for row in method_rows),
                    "mean_loftr_ok_rate_pct": round(
                        statistics.mean(float(row["loftr_outdoor_ok_rate_pct"]) for row in matching_scene_rows), 1
                    ),
                    "mean_xoftr_ok_rate_pct": round(
                        statistics.mean(float(row["xoftr_official_ok_rate_pct"]) for row in matching_scene_rows), 1
                    ),
                    "mean_classical_ok_rate_pct": round(
                        statistics.mean(float(row["classical_mean_ok_rate_pct"]) for row in matching_scene_rows), 1
                    ),
                }
            )

    proxy_pass_fail_rows: List[Dict[str, object]] = []
    for status in ["ok", "canonical_fail"]:
        grouped_rows = [row for row in uav_scene_rows if row["uav_status"] == status]
        proxy_pass_fail_rows.append(
            {
                "status": status,
                "num_scenes": len(grouped_rows),
                "mean_accepted_ratio_pct": _fmt_pct(_mean_numeric(row["accepted_ratio"] for row in grouped_rows)),
                "mean_delta_edge_f1": _mean_numeric(row["delta_edge_f1"] for row in grouped_rows),
                "mean_delta_grad_ncc": _mean_numeric(row["delta_grad_ncc"] for row in grouped_rows),
                "mean_improved_grad_ratio_pct": _fmt_pct(
                    _mean_numeric(row["improved_grad_ratio"] for row in grouped_rows)
                ),
                "mean_robust_reject_ratio_pct": _fmt_pct(
                    _mean_numeric(row["robust_reject_ratio"] for row in grouped_rows)
                ),
                "mean_severe_outlier_ratio_pct": _fmt_pct(
                    _mean_numeric(row["severe_outlier_ratio"] for row in grouped_rows)
                ),
                "mean_median_disp_to_aggregate_mean_px": _mean_numeric(
                    row["median_disp_to_aggregate_mean_px"] for row in grouped_rows
                ),
                "mean_mean_inlier_ratio": _mean_numeric(row["mean_inlier_ratio"] for row in grouped_rows),
            }
        )

    proxy_fail_driver_rows: List[Dict[str, object]] = []
    for metric in ["match_ok", "geometry_ok", "stability_ok", "grad_ok", "edge_floor_ok", "qa_outlier_ok", "warning_path_ok"]:
        for status in ["ok", "canonical_fail"]:
            grouped_rows = [row for row in uav_scene_rows if row["uav_status"] == status]
            true_count = sum(1 for row in grouped_rows if row.get(metric) is True)
            false_count = sum(1 for row in grouped_rows if row.get(metric) is False)
            proxy_fail_driver_rows.append(
                {
                    "metric": metric,
                    "status": status,
                    "num_scenes": len(grouped_rows),
                    "true_count": true_count,
                    "false_count": false_count,
                    "true_rate_pct": _fmt_pct(true_count / len(grouped_rows) if grouped_rows else None),
                }
            )

    warning_counter: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in uav_scene_rows:
        for code in [item.strip() for item in str(row["warning_codes"]).split(",") if item.strip()]:
            warning_counter[str(row["uav_status"])][code] += 1
    proxy_warning_rows: List[Dict[str, object]] = []
    for status in ["ok", "canonical_fail"]:
        total = sum(1 for row in uav_scene_rows if row["uav_status"] == status)
        for warning_code, count in warning_counter[status].most_common():
            proxy_warning_rows.append(
                {
                    "status": status,
                    "warning_code": warning_code,
                    "scene_count": count,
                    "scene_rate_pct": _fmt_pct(count / total if total else None),
                }
            )

    fail_rows = [row for row in uav_scene_rows if row["uav_status"] == "canonical_fail"]
    pass_rows = [row for row in uav_scene_rows if row["uav_status"] == "ok"]
    joint_rule_specs = [
        (
            "baseline_relative_qa_outliers",
            "baseline_relative_qa_outliers in warning_codes",
            lambda row: "baseline_relative_qa_outliers" in _warning_set(row),
        ),
        (
            "accepted_ratio_lt_0_60",
            "accepted_ratio < 0.60",
            lambda row: float(row["accepted_ratio"]) < 0.60,
        ),
        (
            "accepted_ratio_lt_0_70",
            "accepted_ratio < 0.70",
            lambda row: float(row["accepted_ratio"]) < 0.70,
        ),
        (
            "low_accepted_ratio_warning",
            "low_accepted_ratio in warning_codes",
            lambda row: "low_accepted_ratio" in _warning_set(row),
        ),
        (
            "high_robust_reject_warning",
            "high_robust_reject_ratio in warning_codes",
            lambda row: "high_robust_reject_ratio" in _warning_set(row),
        ),
        (
            "warning_path_fail",
            "warning_path_ok == False",
            lambda row: row.get("warning_path_ok") is False,
        ),
        (
            "qa_outlier_fail",
            "qa_outlier_ok == False",
            lambda row: row.get("qa_outlier_ok") is False,
        ),
        (
            "joint_outlier_or_lowacc",
            "baseline_relative_qa_outliers OR accepted_ratio < 0.60",
            lambda row: ("baseline_relative_qa_outliers" in _warning_set(row)) or (float(row["accepted_ratio"]) < 0.60),
        ),
        (
            "joint_outlier_and_warningfail",
            "baseline_relative_qa_outliers AND warning_path_ok == False",
            lambda row: ("baseline_relative_qa_outliers" in _warning_set(row)) and (row.get("warning_path_ok") is False),
        ),
    ]
    proxy_joint_rows: List[Dict[str, object]] = []
    for rule_name, rule_definition, predicate in joint_rule_specs:
        fail_true_count = sum(1 for row in fail_rows if predicate(row))
        fail_false_count = sum(1 for row in fail_rows if not predicate(row))
        pass_true_count = sum(1 for row in pass_rows if predicate(row))
        pass_false_count = sum(1 for row in pass_rows if not predicate(row))
        proxy_joint_rows.append(
            {
                "rule_name": rule_name,
                "rule_definition": rule_definition,
                "fail_true_count": fail_true_count,
                "fail_false_count": fail_false_count,
                "pass_true_count": pass_true_count,
                "pass_false_count": pass_false_count,
                "fail_recall_pct": _fmt_pct(fail_true_count / len(fail_rows) if fail_rows else None),
                "pass_exclusion_pct": _fmt_pct(pass_false_count / len(pass_rows) if pass_rows else None),
            }
        )

    paired_control_scene_names = [
        "01_day_grayscale_wide_substation_power_lines_50",
        "02_day_grayscale_zoom_substation_power_lines_50",
        "03_night_grayscale_wide_substation_power_lines_45",
        "04_night_grayscale_zoom_substation_power_lines_45",
    ]
    proxy_paired_control_rows: List[Dict[str, object]] = []
    for scene_name in paired_control_scene_names:
        row = next(scene_row for scene_row in uav_scene_rows if scene_row["scene_name"] == scene_name)
        proxy_paired_control_rows.append(
            {
                "scene_name": scene_name,
                "uav_status": row["uav_status"],
                "accepted_ratio_pct": _fmt_pct(float(row["accepted_ratio"])),
                "robust_reject_ratio_pct": _fmt_pct(row["robust_reject_ratio"]),
                "delta_edge_f1": row["delta_edge_f1"],
                "delta_grad_ncc": row["delta_grad_ncc"],
                "warning_codes": row["warning_codes"],
            }
        )

    def scene_row(scene_name: str) -> Dict[str, object]:
        return next(row for row in scene_breakdown_rows if row["scene_name"] == scene_name)

    def uav_row(scene_name: str) -> Dict[str, object]:
        return next(row for row in uav_scene_rows if row["scene_name"] == scene_name)

    candidate_specs = [
        (
            "01_day_grayscale_wide_substation_power_lines_50",
            "paired control / strong pass",
            "Use with scene 02 to show same scene family under wide-vs-zoom; scene 01 is a clean canonical pass with very strong accepted ratio and positive edge/gradient gains.",
        ),
        (
            "02_day_grayscale_zoom_substation_power_lines_50",
            "paired control / fail",
            "Use with scene 01 to show a zoom hard case: accepted ratio stays very high, but QA outliers and reject ratio push the scene into canonical fail.",
        ),
        (
            "03_night_grayscale_wide_substation_power_lines_45",
            "night hard fail",
            "Night wide substation case with strong positive proxy gains but large robust reject ratio; good failure-case panel for explaining why QA still rejects it.",
        ),
        (
            "04_night_grayscale_zoom_substation_power_lines_45",
            "night pass control",
            "Natural companion to scene 03: same scene family at night but canonical pass, useful for before/after and pass-vs-fail comparison.",
        ),
        (
            "09_day_pseudocolor_building_20",
            "classical weak / ours pass",
            "Day pseudocolor building scene where classical baselines are visibly weaker while the full pipeline still passes.",
        ),
        (
            "13_lowlight_pseudocolor_road_21",
            "largest proxy gain pass",
            "Lowlight pseudocolor road scene with the strongest positive edge and gradient gains among passing scenes.",
        ),
        (
            "05_night_pseudocolor_solar_panels_16",
            "low-accepted-ratio fail",
            "Night pseudocolor solar-panel hard case with extremely low accepted ratio; strong candidate for a failure panel.",
        ),
        (
            "15_lowlight_pseudocolor_woodland_26",
            "baseline weakness + fail",
            "Only scene where official XoFTR pairwise ok-rate visibly drops; useful to show a truly difficult lowlight case rather than a pure QA-only rejection.",
        ),
    ]
    qualitative_rows: List[Dict[str, object]] = []
    for priority, (scene_name, category, reason) in enumerate(candidate_specs, start=1):
        condensed = scene_row(scene_name)
        scene_level = uav_row(scene_name)
        qualitative_rows.append(
            {
                "priority": priority,
                "scene_id": condensed["scene_id"],
                "scene_name": scene_name,
                "category": category,
                "light_condition": condensed["light_condition"],
                "thermal_rendering": condensed["thermal_rendering"],
                "view": condensed["view"],
                "classical_mean_ok_rate_pct": condensed["classical_mean_ok_rate_pct"],
                "loftr_ok_rate_pct": condensed["loftr_outdoor_ok_rate_pct"],
                "xoftr_ok_rate_pct": condensed["xoftr_official_ok_rate_pct"],
                "uav_status": scene_level["uav_status"],
                "uav_accepted_ratio_pct": _fmt_pct(float(scene_level["accepted_ratio"])),
                "delta_edge_f1": scene_level["delta_edge_f1"],
                "delta_grad_ncc": scene_level["delta_grad_ncc"],
                "representative_images": scene_level["representative_images"],
                "reason": reason,
            }
        )

    _write_csv(out_dir / "main_table_pairwise.csv", pairwise_main_rows)
    _write_csv(
        out_dir / "main_table_scene.csv",
        [
            {
                "method_label": "UAV-TAlign full pipeline",
                "evaluation_unit": "15 scenes",
                "scene_pass_count": sum(1 for row in uav_scene_rows if row["uav_status"] == "ok"),
                "scene_pass_rate_pct": _fmt_pct(
                    sum(1 for row in uav_scene_rows if row["uav_status"] == "ok") / len(uav_scene_rows)
                ),
                "mean_accepted_ratio_pct": _fmt_pct(_mean_numeric(row["accepted_ratio"] for row in uav_scene_rows)),
                "homography_available_rate_pct": _fmt_pct(
                    sum(1 for row in results["uav_talign_full"] if row.get("homography_available")) / len(results["uav_talign_full"])
                ),
                "mean_runtime_sec": _mean_numeric(row["runtime_sec"] for row in uav_scene_rows),
                "notes": "Scene-level QA-aware pipeline; not directly comparable to pairwise per-pair success rates.",
            }
        ],
    )
    _write_csv(out_dir / "scene_breakdown.csv", scene_breakdown_rows)
    _write_csv(out_dir / "condition_breakdown_pairwise.csv", condition_breakdown_pairwise_rows)
    _write_csv(out_dir / "condition_breakdown_uav_scene.csv", condition_breakdown_uav_rows)
    _write_csv(out_dir / "uav_proxy_scene_metrics.csv", uav_scene_rows)
    _write_csv(out_dir / "uav_proxy_pass_fail_summary.csv", proxy_pass_fail_rows)
    _write_csv(out_dir / "uav_proxy_fail_driver_counts.csv", proxy_fail_driver_rows)
    _write_csv(out_dir / "uav_proxy_warning_code_counts.csv", proxy_warning_rows)
    _write_csv(out_dir / "uav_proxy_joint_rules.csv", proxy_joint_rows)
    _write_csv(out_dir / "uav_proxy_paired_controls.csv", proxy_paired_control_rows)
    _write_csv(out_dir / "qualitative_panel_candidates.csv", qualitative_rows)

    summary = {
        "generated_at": datetime.now().isoformat(),
        "artifact_dir": str(out_dir),
        "uav_scene_pass_rate_pct": _fmt_pct(sum(1 for row in uav_scene_rows if row["uav_status"] == "ok") / len(uav_scene_rows)),
        "night_scene_pass_rate_pct": next(
            row["pass_rate_pct"]
            for row in condition_breakdown_uav_rows
            if row["condition_type"] == "light_condition" and row["condition_value"] == "night"
        ),
        "lowlight_scene_pass_rate_pct": next(
            row["pass_rate_pct"]
            for row in condition_breakdown_uav_rows
            if row["condition_type"] == "light_condition" and row["condition_value"] == "lowlight"
        ),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    usable_pairwise = [row for row in pairwise_main_rows if row["usable_for_quant_table"]]
    blocked_pairwise = [row for row in pairwise_main_rows if not row["usable_for_quant_table"]]
    scene_main_rows = [
        {
            "method": "UAV-TAlign full pipeline",
            "eval_unit": "15 scenes",
            "scene_pass": f"{sum(1 for row in uav_scene_rows if row['uav_status'] == 'ok')}/15",
            "scene_pass_rate_pct": _fmt_pct(sum(1 for row in uav_scene_rows if row["uav_status"] == "ok") / len(uav_scene_rows)),
            "mean_accepted_ratio_pct": _fmt_pct(_mean_numeric(row["accepted_ratio"] for row in uav_scene_rows)),
            "mean_runtime_sec": _mean_numeric(row["runtime_sec"] for row in uav_scene_rows),
        }
    ]

    pairwise_table = _md_table(
        [
            {
                "method": row["method_label"],
                "ok": f"{row['ok_count']}/{row['num_records']}",
                "ok_rate_pct": row["ok_rate_pct"],
                "homography_rate_pct": row["homography_rate_pct"],
                "mean_inlier_ratio": row["mean_inlier_ratio"],
                "mean_coverage": row["mean_coverage"],
                "mean_reprojection_error": row["mean_reprojection_error"],
                "mean_runtime_sec": row["mean_runtime_sec"],
            }
            for row in usable_pairwise
        ],
        [
            ("method", "Method"),
            ("ok", "OK / N"),
            ("ok_rate_pct", "OK Rate (%)"),
            ("homography_rate_pct", "Homography (%)"),
            ("mean_inlier_ratio", "Mean Inlier Ratio"),
            ("mean_coverage", "Mean Coverage"),
            ("mean_reprojection_error", "Mean Reproj Error"),
            ("mean_runtime_sec", "Mean Runtime (s)"),
        ],
    )
    blocked_table = _md_table(
        [{"method": row["method_label"], "status_counts": row["status_counts"], "note": row["notes"]} for row in blocked_pairwise],
        [("method", "Method"), ("status_counts", "Status Counts"), ("note", "Note")],
    )
    if blocked_pairwise:
        blocked_section = f"""## Attempted But Currently Unusable Baseline

{blocked_table}
"""
    else:
        blocked_section = """## Baseline Completion Note

All first-wave pairwise baselines now have usable 500-pair full-run results.
"""
    scene_table = _md_table(
        scene_main_rows,
        [
            ("method", "Method"),
            ("eval_unit", "Eval Unit"),
            ("scene_pass", "Scene Pass"),
            ("scene_pass_rate_pct", "Pass Rate (%)"),
            ("mean_accepted_ratio_pct", "Mean Accepted Ratio (%)"),
            ("mean_runtime_sec", "Mean Runtime (s)"),
        ],
    )
    main_md = f"""# PRCV Main Table Draft

Source artifacts: `{out_dir}`

## Pairwise Baselines (500 paired registrations)

{pairwise_table}

## Scene-Level Pipeline Table

{scene_table}

{blocked_section}

## Immediate Takeaways

- `raw MINIMA` and `official pretrained RoMa via local wrapper` both reach `500/500` usable pairwise results in the current off-the-shelf setup.
- `official pretrained XoFTR-640 via local wrapper` remains a strong learning baseline with `494/500` usable pairwise results.
- `Kornia LoFTR (pretrained="outdoor")` is now usable under the bounded resize-aware inference setting, reaching `499/500` usable pairwise results with only `1` insufficient-match case.
- Classical baselines are still serviceable, but their pairwise `OK` rates are visibly lower than the multimodal matchers.
- `UAV-TAlign full pipeline` is a scene-level QA-aware system. Its current formal result is `7/15` canonical scene passes with a mean accepted-frame ratio of about `{_fmt_pct(_mean_numeric(row['accepted_ratio'] for row in uav_scene_rows))}%`.
- For writing and GPT review, the LoFTR setting should be described explicitly as `Kornia LoFTR (pretrained="outdoor")` with resize-aware inference (`match_max_dim=1600`, `use_amp=false`), not as an untouched official-script full-resolution run.
"""
    (docs_root / "prcv_main_table_draft.md").write_text(main_md, encoding="utf-8")

    scene_display_rows = [
        {
            "scene_id": row["scene_id"],
            "scene_name": row["scene_name"],
            "light": row["light_condition"],
            "rendering": row["thermal_rendering"],
            "view": row["view"],
            "classical_ok_rate_pct": row["classical_mean_ok_rate_pct"],
            "loftr_ok_rate_pct": row["loftr_outdoor_ok_rate_pct"],
            "xoftr_ok_rate_pct": row["xoftr_official_ok_rate_pct"],
            "uav_status": row["uav_status"],
            "uav_accepted_ratio_pct": row["uav_accepted_ratio_pct"],
            "delta_edge_f1": row["uav_delta_edge_f1"],
            "delta_grad_ncc": row["uav_delta_grad_ncc"],
            "robust_reject_ratio": row["uav_robust_reject_ratio"],
        }
        for row in scene_breakdown_rows
    ]
    light_rows = [row for row in condition_breakdown_uav_rows if row["condition_type"] == "light_condition"]
    thermal_rows = [row for row in condition_breakdown_uav_rows if row["condition_type"] == "thermal_rendering"]
    view_rows = [row for row in condition_breakdown_uav_rows if row["condition_type"] == "view"]
    scene_cond_md = f"""# PRCV Scene / Condition Tables Draft

Source artifacts: `{out_dir}`

## Per-Scene Condensed Table

{_md_table(
    scene_display_rows,
    [
        ("scene_id", "Scene"),
        ("scene_name", "Scene Name"),
        ("light", "Light"),
        ("rendering", "Thermal"),
        ("view", "View"),
        ("classical_ok_rate_pct", "Classical Mean OK (%)"),
        ("loftr_ok_rate_pct", "LoFTR OK (%)"),
        ("xoftr_ok_rate_pct", "XoFTR OK (%)"),
        ("uav_status", "UAV-TAlign Status"),
        ("uav_accepted_ratio_pct", "Accepted Ratio (%)"),
        ("delta_edge_f1", "Delta Edge F1"),
        ("delta_grad_ncc", "Delta Grad NCC"),
        ("robust_reject_ratio", "Reject Ratio"),
    ],
)}

## Condition Breakdown: Light Condition

{_md_table(
    light_rows,
    [
        ("condition_value", "Condition"),
        ("num_scenes", "Scenes"),
        ("pass_count", "UAV Pass"),
        ("pass_rate_pct", "UAV Pass Rate (%)"),
        ("mean_accepted_ratio_pct", "Mean Accepted Ratio (%)"),
        ("mean_loftr_ok_rate_pct", "Mean LoFTR OK (%)"),
        ("mean_xoftr_ok_rate_pct", "Mean XoFTR OK (%)"),
        ("mean_classical_ok_rate_pct", "Mean Classical OK (%)"),
        ("mean_delta_edge_f1", "Mean Delta Edge F1"),
        ("mean_delta_grad_ncc", "Mean Delta Grad NCC"),
    ],
)}

## Condition Breakdown: Thermal Rendering

{_md_table(
    thermal_rows,
    [
        ("condition_value", "Condition"),
        ("num_scenes", "Scenes"),
        ("pass_count", "UAV Pass"),
        ("pass_rate_pct", "UAV Pass Rate (%)"),
        ("mean_accepted_ratio_pct", "Mean Accepted Ratio (%)"),
        ("mean_loftr_ok_rate_pct", "Mean LoFTR OK (%)"),
        ("mean_xoftr_ok_rate_pct", "Mean XoFTR OK (%)"),
        ("mean_classical_ok_rate_pct", "Mean Classical OK (%)"),
        ("mean_delta_edge_f1", "Mean Delta Edge F1"),
        ("mean_delta_grad_ncc", "Mean Delta Grad NCC"),
    ],
)}

## Condition Breakdown: View

{_md_table(
    view_rows,
    [
        ("condition_value", "Condition"),
        ("num_scenes", "Scenes"),
        ("pass_count", "UAV Pass"),
        ("pass_rate_pct", "UAV Pass Rate (%)"),
        ("mean_accepted_ratio_pct", "Mean Accepted Ratio (%)"),
        ("mean_loftr_ok_rate_pct", "Mean LoFTR OK (%)"),
        ("mean_xoftr_ok_rate_pct", "Mean XoFTR OK (%)"),
        ("mean_classical_ok_rate_pct", "Mean Classical OK (%)"),
        ("mean_delta_edge_f1", "Mean Delta Edge F1"),
        ("mean_delta_grad_ncc", "Mean Delta Grad NCC"),
    ],
)}

## Immediate Observations

- The current scene-level bottleneck is not pairwise matcher availability: `raw MINIMA`, `RoMa`, `LoFTR`, and almost all `XoFTR` pairs remain usable across the dataset.
- Night scenes are the hardest group for `UAV-TAlign full pipeline` under the current canonical gate.
- Pseudocolor scenes suppress the classical baselines more than they suppress `XoFTR` / `RoMa`, while the `UAV-TAlign` scene pass rate remains mixed rather than uniformly poor.
- The most informative paired controls are `01 vs 02` and `03 vs 04`, because they keep the scene family fixed while changing view or pass/fail outcome.
"""
    (docs_root / "prcv_scene_condition_tables_draft.md").write_text(scene_cond_md, encoding="utf-8")

    qual_md = f"""# PRCV Qualitative Panel Candidates

Source artifacts: `{out_dir}`

{_md_table(
    [
        {
            "priority": row["priority"],
            "scene": row["scene_name"],
            "category": row["category"],
            "light": row["light_condition"],
            "thermal": row["thermal_rendering"],
            "view": row["view"],
            "classical_ok_rate_pct": row["classical_mean_ok_rate_pct"],
            "loftr_ok_rate_pct": row["loftr_ok_rate_pct"],
            "xoftr_ok_rate_pct": row["xoftr_ok_rate_pct"],
            "uav_status": row["uav_status"],
            "accepted_ratio_pct": row["uav_accepted_ratio_pct"],
            "representative_images": row["representative_images"],
            "reason": row["reason"],
        }
        for row in qualitative_rows
    ],
    [
        ("priority", "Priority"),
        ("scene", "Scene"),
        ("category", "Category"),
        ("light", "Light"),
        ("thermal", "Thermal"),
        ("view", "View"),
        ("classical_ok_rate_pct", "Classical Mean OK (%)"),
        ("loftr_ok_rate_pct", "LoFTR OK (%)"),
        ("xoftr_ok_rate_pct", "XoFTR OK (%)"),
        ("uav_status", "UAV Status"),
        ("accepted_ratio_pct", "Accepted Ratio (%)"),
        ("representative_images", "Representative Images"),
        ("reason", "Reason"),
    ],
)}

## Suggested First Batch

- Use `01` and `02` as a paired control figure for wide-vs-zoom under the same scene family.
- Use `03` and `04` as a paired night control figure for pass-vs-fail explanation.
- Use `09` and `13` as the first two "ours pass while baselines are weaker" panels.
- Use `05` and `15` as the first two failure panels.
"""
    (docs_root / "prcv_qualitative_panel_candidates.md").write_text(qual_md, encoding="utf-8")

    proxy_md = f"""# PRCV Proxy-Consistency Draft

Source artifacts: `{out_dir}`

## Currently Available Scene-Level Proxy Fields

The current `uav_talign_full` scene outputs already store the following QA-facing metrics per scene:

- `accepted_ratio`
- `delta_edge_f1`
- `delta_grad_ncc`
- `improved_grad_ratio`
- `robust_reject_ratio`
- `severe_outlier_ratio`
- `severe_outlier_count`
- `median_disp_to_aggregate_mean_px`
- Boolean decision inputs such as `match_ok`, `geometry_ok`, `stability_ok`, `grad_ok`, `edge_floor_ok`, `qa_outlier_ok`, `warning_path_ok`
- Warning codes such as `baseline_relative_qa_outliers`, `low_accepted_ratio`, `high_robust_reject_ratio`, and `homography_dispersion_warning`

## Pass / Fail Aggregate Summary

{_md_table(
    proxy_pass_fail_rows,
    [
        ("status", "Status"),
        ("num_scenes", "Scenes"),
        ("mean_accepted_ratio_pct", "Mean Accepted Ratio (%)"),
        ("mean_delta_edge_f1", "Mean Delta Edge F1"),
        ("mean_delta_grad_ncc", "Mean Delta Grad NCC"),
        ("mean_improved_grad_ratio_pct", "Mean Improved-Grad Ratio (%)"),
        ("mean_robust_reject_ratio_pct", "Mean Reject Ratio (%)"),
        ("mean_severe_outlier_ratio_pct", "Mean Severe-Outlier Ratio (%)"),
        ("mean_median_disp_to_aggregate_mean_px", "Mean Median Disp (px)"),
        ("mean_mean_inlier_ratio", "Mean Scene Inlier Ratio"),
    ],
)}

## Boolean Driver Counts

{_md_table(
    proxy_fail_driver_rows,
    [
        ("metric", "Metric"),
        ("status", "Status"),
        ("num_scenes", "Scenes"),
        ("true_count", "True"),
        ("false_count", "False"),
        ("true_rate_pct", "True Rate (%)"),
    ],
)}

## Warning-Code Frequency

{_md_table(
    proxy_warning_rows,
    [
        ("status", "Status"),
        ("warning_code", "Warning Code"),
        ("scene_count", "Scenes"),
        ("scene_rate_pct", "Scene Rate (%)"),
    ],
)}

## Joint Rule Diagnostics

{_md_table(
    proxy_joint_rows,
    [
        ("rule_name", "Rule"),
        ("rule_definition", "Definition"),
        ("fail_true_count", "Fail+"),
        ("fail_false_count", "Fail-"),
        ("pass_true_count", "Pass+"),
        ("pass_false_count", "Pass-"),
        ("fail_recall_pct", "Fail Recall (%)"),
        ("pass_exclusion_pct", "Pass Exclusion (%)"),
    ],
)}

## Paired Controls

{_md_table(
    proxy_paired_control_rows,
    [
        ("scene_name", "Scene"),
        ("uav_status", "Status"),
        ("accepted_ratio_pct", "Accepted Ratio (%)"),
        ("robust_reject_ratio_pct", "Reject Ratio (%)"),
        ("delta_edge_f1", "Delta Edge F1"),
        ("delta_grad_ncc", "Delta Grad NCC"),
        ("warning_codes", "Warning Codes"),
    ],
)}

## First Read of the Evidence

- `baseline_relative_qa_outliers` appears in all `8/8` failing scenes and in `0/7` passing scenes. This is the cleanest currently stored fail-side discriminator.
- `low_accepted_ratio` is also strongly associated with failure (`6/8` fails), but it is not sufficient by itself because it also appears in some passing scenes.
- `grad_ok` and `edge_floor_ok` are always true in the current 15-scene run, so they do not explain the present pass/fail split.
- `geometry_ok` and `stability_ok` are mixed on both sides, which suggests they are useful but not individually decisive under the current QA rules.
- In the current 15-scene snapshot, `baseline_relative_qa_outliers` alone gives `8/8` fail recall and `7/7` pass exclusion; the combined rules `baseline_relative_qa_outliers OR accepted_ratio < 0.60` and `baseline_relative_qa_outliers AND warning_path_ok == False` are equally separating on the same snapshot.
- `accepted_ratio` by itself is not enough: scene `02` still has `98%` accepted frames yet fails because reject / outlier signals stay high, while scene `04` passes at `80%` accepted frames when those fail-side warnings are absent.
- The paired controls `01 vs 02` and `03 vs 04` therefore support the current interpretation that the scene-level bottleneck is QA-relative reliability rather than raw match availability.
"""
    (docs_root / "prcv_proxy_consistency_draft.md").write_text(proxy_md, encoding="utf-8")

    readme_text = f"""# PRCV P0 Structuring Artifacts

Generated at: {datetime.now().isoformat()}

This directory contains the first-pass structured outputs requested before the next heavy experiment wave:

- `main_table_pairwise.csv`
- `main_table_scene.csv`
- `scene_breakdown.csv`
- `condition_breakdown_pairwise.csv`
- `condition_breakdown_uav_scene.csv`
- `uav_proxy_scene_metrics.csv`
- `uav_proxy_pass_fail_summary.csv`
- `uav_proxy_fail_driver_counts.csv`
- `uav_proxy_warning_code_counts.csv`
- `uav_proxy_joint_rules.csv`
- `uav_proxy_paired_controls.csv`
- `qualitative_panel_candidates.csv`
- `summary.json`

Companion markdown drafts were written to:

- `docs/prcv_main_table_draft.md`
- `docs/prcv_scene_condition_tables_draft.md`
- `docs/prcv_qualitative_panel_candidates.md`
- `docs/prcv_proxy_consistency_draft.md`
"""
    (out_dir / "README.md").write_text(readme_text, encoding="utf-8")

    print(
        json.dumps(
            {
                "artifact_dir": str(out_dir),
                "docs_written": [
                    str(docs_root / "prcv_main_table_draft.md"),
                    str(docs_root / "prcv_scene_condition_tables_draft.md"),
                    str(docs_root / "prcv_qualitative_panel_candidates.md"),
                    str(docs_root / "prcv_proxy_consistency_draft.md"),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
