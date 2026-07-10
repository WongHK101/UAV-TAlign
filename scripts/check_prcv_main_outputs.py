from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


DEFAULT_REQUIRED_METHODS = (
    "sift_ransac",
    "akaze_ransac",
    "loftr_outdoor",
    "roma_outdoor",
    "xoftr_official",
    "raw_minima",
    "uav_talign_full",
)
DEFAULT_MANIFEST_SHA256 = "a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c"


def _status_counts(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status", "missing"))
        counts[status] = counts.get(status, 0) + 1
    return counts


def _int_value(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _parse_methods(raw: str) -> list[str]:
    methods: list[str] = []
    for item in str(raw).split(","):
        method = item.strip()
        if method and method not in methods:
            methods.append(method)
    return methods


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for index, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                rows.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path} line {index}: invalid JSON ({exc})") from exc
    return rows


def _record_check(report: dict, name: str, ok: bool, detail: str) -> None:
    entry = {"name": name, "ok": bool(ok), "detail": detail}
    report["checks"].append(entry)
    if not ok:
        report["failures"].append(entry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate formal UAV-TAlign main-experiment outputs.")
    parser.add_argument("--output_dir", type=Path, required=True)
    parser.add_argument("--required_methods", default=",".join(DEFAULT_REQUIRED_METHODS))
    parser.add_argument("--expect_manifest_sha256", default=DEFAULT_MANIFEST_SHA256)
    parser.add_argument("--expect_pair_count", type=int, default=6037)
    parser.add_argument("--expect_scene_count", type=int, default=15)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    required_methods = _parse_methods(args.required_methods)
    report = {
        "output_dir": str(output_dir),
        "required_methods": required_methods,
        "checks": [],
        "failures": [],
        "artifacts": {},
    }

    summary_path = output_dir / "main_experiment_summary.json"
    config_path = output_dir / "experiment_config.json"
    if not summary_path.is_file():
        _record_check(report, "summary_exists", False, f"Missing {summary_path}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(1)

    summary = _load_json(summary_path)
    report["artifacts"]["summary_path"] = str(summary_path)
    _record_check(report, "experiment_config_exists", config_path.is_file(), str(config_path))
    config = _load_json(config_path) if config_path.is_file() else {}
    if config_path.is_file():
        report["artifacts"]["experiment_config_path"] = str(config_path)
    manifest_info = summary.get("dataset_manifest", {}) if isinstance(summary, dict) else {}
    manifest_sha256 = str(manifest_info.get("manifest_sha256", ""))
    summary_num_pairs = int(summary.get("num_pairs", -1))
    summary_num_scenes = int(summary.get("num_scenes", -1))
    summary_methods = list(summary.get("methods", [])) if isinstance(summary.get("methods", []), list) else []
    method_summaries = summary.get("method_summaries", {}) if isinstance(summary.get("method_summaries", {}), dict) else {}

    _record_check(
        report,
        "manifest_sha256",
        manifest_sha256 == args.expect_manifest_sha256,
        f"expected={args.expect_manifest_sha256} actual={manifest_sha256}",
    )
    _record_check(
        report,
        "summary_num_pairs",
        summary_num_pairs == int(args.expect_pair_count),
        f"expected={args.expect_pair_count} actual={summary_num_pairs}",
    )
    _record_check(
        report,
        "summary_num_scenes",
        summary_num_scenes == int(args.expect_scene_count),
        f"expected={args.expect_scene_count} actual={summary_num_scenes}",
    )

    for method in required_methods:
        _record_check(
            report,
            f"summary_declares_{method}",
            method in summary_methods,
            f"summary methods={summary_methods}",
        )
        _record_check(
            report,
            f"summary_has_method_summary_{method}",
            method in method_summaries,
            f"method_summaries keys={sorted(method_summaries.keys())}",
        )

        if method == "uav_talign_full":
            scene_paths = {
                "canonical_results_jsonl": output_dir / "uav_talign_full" / "results.jsonl",
                "compat_scene_results_jsonl": output_dir / "uav_talign_full" / "scene_results.jsonl",
                "compat_top_level_jsonl": output_dir / "uav_talign_full_scene_metrics_detailed.jsonl",
            }
            loaded_rows: dict[str, list[dict]] = {}
            for label, path in scene_paths.items():
                exists = path.is_file()
                _record_check(report, f"{label}_exists", exists, str(path))
                if not exists:
                    continue
                rows = _load_jsonl(path)
                loaded_rows[label] = rows
                report["artifacts"][label] = {"path": str(path), "count": len(rows)}
                _record_check(
                    report,
                    f"{label}_count",
                    len(rows) == int(args.expect_scene_count),
                    f"expected={args.expect_scene_count} actual={len(rows)} path={path}",
                )
            if loaded_rows:
                reference_label = next(iter(loaded_rows))
                reference_names = [str(row.get("scene_name", "")) for row in loaded_rows[reference_label]]
                for label, rows in loaded_rows.items():
                    scene_names = [str(row.get("scene_name", "")) for row in rows]
                    _record_check(
                        report,
                        f"{label}_scene_name_alignment",
                        scene_names == reference_names,
                        f"reference={reference_label} actual={label}",
                    )
                canonical_rows = loaded_rows.get("canonical_results_jsonl", loaded_rows[reference_label])
                status_counts = _status_counts(canonical_rows)
                homography_available_count = int(
                    sum(1 for row in canonical_rows if bool(row.get("homography_available", False)))
                )
                canonical_scene_pass_count = int(
                    sum(1 for row in canonical_rows if bool(row.get("canonical_scene_pass", False)))
                )
                error_count = int(status_counts.get("error", 0))
                unique_scene_names = len({str(row.get("scene_name", "")) for row in canonical_rows})
                pair_ids = {str(row.get("pair_id", "")) for row in canonical_rows}
                report["artifacts"]["uav_talign_full_semantics"] = {
                    "status_counts": status_counts,
                    "homography_available_count": homography_available_count,
                    "canonical_scene_pass_count": canonical_scene_pass_count,
                    "error_count": error_count,
                    "unique_scene_names": unique_scene_names,
                    "pair_ids": sorted(pair_ids),
                }
                summary_info = method_summaries.get(method, {}) if isinstance(method_summaries.get(method, {}), dict) else {}
                _record_check(
                    report,
                    "uav_talign_full_summary_status_counts_match",
                    summary_info.get("status_counts", {}) == status_counts,
                    f"summary={summary_info.get('status_counts', {})} actual={status_counts}",
                )
                _record_check(
                    report,
                    "uav_talign_full_summary_homography_count_match",
                    _int_value(summary_info.get("homography_available_count", -1), default=-1) == homography_available_count,
                    (
                        f"summary={summary_info.get('homography_available_count', -1)} "
                        f"actual={homography_available_count}"
                    ),
                )
                _record_check(
                    report,
                    "uav_talign_full_summary_canonical_pass_count_match",
                    _int_value(summary_info.get("canonical_scene_pass_count", -1), default=-1) == canonical_scene_pass_count,
                    (
                        f"summary={summary_info.get('canonical_scene_pass_count', -1)} "
                        f"actual={canonical_scene_pass_count}"
                    ),
                )
                _record_check(
                    report,
                    "uav_talign_full_unique_scene_names",
                    unique_scene_names == int(args.expect_scene_count),
                    f"expected={args.expect_scene_count} actual={unique_scene_names}",
                )
                _record_check(
                    report,
                    "uav_talign_full_pair_id_is_scene_sentinel",
                    pair_ids == {"__scene__"},
                    f"pair_ids={sorted(pair_ids)}",
                )
                _record_check(
                    report,
                    "uav_talign_full_not_all_runtime_error",
                    error_count < len(canonical_rows),
                    f"status_counts={status_counts}",
                )
                _record_check(
                    report,
                    "uav_talign_full_has_any_scene_homography",
                    homography_available_count > 0,
                    f"homography_available_count={homography_available_count} status_counts={status_counts}",
                )
        else:
            path = output_dir / method / "results.jsonl"
            exists = path.is_file()
            _record_check(report, f"{method}_results_exists", exists, str(path))
            if not exists:
                continue
            rows = _load_jsonl(path)
            status_counts = _status_counts(rows)
            homography_available_count = int(sum(1 for row in rows if bool(row.get("homography_available", False))))
            error_count = int(status_counts.get("error", 0))
            report["artifacts"][f"{method}_results_jsonl"] = {
                "path": str(path),
                "count": len(rows),
                "status_counts": status_counts,
                "homography_available_count": homography_available_count,
                "error_count": error_count,
            }
            _record_check(
                report,
                f"{method}_results_count",
                len(rows) == int(args.expect_pair_count),
                f"expected={args.expect_pair_count} actual={len(rows)} path={path}",
            )
            summary_info = method_summaries.get(method, {}) if isinstance(method_summaries.get(method, {}), dict) else {}
            _record_check(
                report,
                f"{method}_summary_status_counts_match",
                summary_info.get("status_counts", {}) == status_counts,
                f"summary={summary_info.get('status_counts', {})} actual={status_counts}",
            )
            _record_check(
                report,
                f"{method}_summary_homography_count_match",
                _int_value(summary_info.get("homography_available_count", -1), default=-1) == homography_available_count,
                f"summary={summary_info.get('homography_available_count', -1)} actual={homography_available_count}",
            )
            _record_check(
                report,
                f"{method}_not_all_runtime_error",
                error_count < len(rows),
                f"status_counts={status_counts}",
            )
            _record_check(
                report,
                f"{method}_has_pairwise_evidence",
                homography_available_count > 0,
                f"homography_available_count={homography_available_count} status_counts={status_counts}",
            )
            if method == "loftr_outdoor" and isinstance(config, dict):
                report["artifacts"]["loftr_execution_profile"] = {
                    "loftr_match_max_dim": _int_value(config.get("loftr_match_max_dim", 0), default=0),
                    "loftr_use_amp": bool(config.get("loftr_use_amp", False)),
                }

    ok = not report["failures"]
    report["ok"] = ok
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
