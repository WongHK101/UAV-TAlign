from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}
CONDITION_FIELDS = ("light_condition", "thermal_rendering", "view_type", "scene_family")


def _image_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)


def _verify_image(path: Path) -> tuple[bool, str | None, str | None]:
    try:
        with Image.open(path) as im:
            resolution = f"{int(im.size[0])}x{int(im.size[1])}"
            im.verify()
        return True, resolution, None
    except Exception as exc:
        return False, None, type(exc).__name__


def _file_sha256(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _load_source_manifest(dataset_root: Path) -> dict[str, dict]:
    for name in ("dataset_manifest.json", "subset_manifest.json"):
        path = dataset_root / name
        if not path.exists():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            str(scene.get("scene_name", "")).strip(): scene
            for scene in payload.get("scenes", [])
            if str(scene.get("scene_name", "")).strip()
        }
    return {}


def _parse_scene_name(scene_name: str) -> dict[str, str | None]:
    parts = scene_name.split("_")
    scene_id = parts[0] if parts else ""
    light = parts[1] if len(parts) > 1 else "unknown"
    rendering = parts[2] if len(parts) > 2 else "unknown"
    if len(parts) > 3 and parts[3] in {"wide", "zoom"}:
        view = parts[3]
        family_parts = parts[4:-1]
    else:
        view = None
        family_parts = parts[3:-1]
    return {
        "scene_id": scene_id,
        "light_condition": light,
        "thermal_rendering": rendering,
        "view": view,
        "view_type": view or "standard",
        "scene_label": "_".join(family_parts) if family_parts else "unknown",
        "scene_family": "_".join(family_parts) if family_parts else "unknown",
    }


def _scene_metadata(scene_name: str, source_manifest: dict[str, dict]) -> dict[str, str | None]:
    parsed = _parse_scene_name(scene_name)
    source = source_manifest.get(scene_name, {})
    view = source.get("view", parsed["view"])
    scene_label = source.get("scene_label", parsed["scene_label"])
    return {
        "scene_id": str(source.get("scene_id", parsed["scene_id"])),
        "light_condition": str(source.get("light_condition", parsed["light_condition"])),
        "thermal_rendering": str(source.get("thermal_rendering", parsed["thermal_rendering"])),
        "view": None if view in {"", "None"} else view,
        "view_type": str(view or parsed["view_type"] or "standard"),
        "scene_label": str(scene_label),
        "scene_family": str(scene_label),
    }


def _write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _condition_rows(scene_records: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for field in CONDITION_FIELDS:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for scene in scene_records:
            grouped[str(scene.get(field, "unknown") or "standard")].append(scene)
        for value in sorted(grouped):
            scenes = grouped[value]
            candidate_pairs = sum(int(scene["candidate_pair_count"]) for scene in scenes)
            valid_pairs = sum(int(scene["valid_pair_count"]) for scene in scenes)
            excluded_pairs = sum(int(scene["excluded_pair_count"]) for scene in scenes)
            rows.append(
                {
                    "group_type": field,
                    "group_value": value,
                    "num_scenes": len(scenes),
                    "candidate_pair_count": candidate_pairs,
                    "valid_pair_count": valid_pairs,
                    "valid_image_count": 2 * valid_pairs,
                    "excluded_pair_count": excluded_pairs,
                    "macro_valid_pairs_per_scene": round(valid_pairs / max(len(scenes), 1), 4),
                }
            )
    return rows


def build_manifest(dataset_root: Path, dataset_name: str, manifest_version: str) -> tuple[dict, dict, list[dict], list[dict], list[dict]]:
    dataset_root = dataset_root.resolve()
    source_manifest = _load_source_manifest(dataset_root)
    scene_dirs = sorted(path for path in dataset_root.iterdir() if path.is_dir())

    scenes: list[dict] = []
    exclusions: list[dict] = []
    duplicate_rows: list[dict] = []
    filename_mismatch_rows: list[dict] = []
    decode_invalid_rows: list[dict] = []

    for scene_dir in scene_dirs:
        meta = _scene_metadata(scene_dir.name, source_manifest)
        rgb_files = _image_files(scene_dir / "rgb")
        thermal_files = _image_files(scene_dir / "thermal")
        rgb_by_id = {path.stem: path for path in rgb_files}
        thermal_by_id = {path.stem: path for path in thermal_files}
        pair_ids = sorted(set(rgb_by_id) & set(thermal_by_id))
        rgb_only = sorted(set(rgb_by_id) - set(thermal_by_id))
        thermal_only = sorted(set(thermal_by_id) - set(rgb_by_id))

        for pair_id in rgb_only:
            filename_mismatch_rows.append(
                {
                    "scene_name": scene_dir.name,
                    "modality": "rgb",
                    "pair_id": pair_id,
                    "relative_path": _relative(rgb_by_id[pair_id], dataset_root),
                }
            )
        for pair_id in thermal_only:
            filename_mismatch_rows.append(
                {
                    "scene_name": scene_dir.name,
                    "modality": "thermal",
                    "pair_id": pair_id,
                    "relative_path": _relative(thermal_by_id[pair_id], dataset_root),
                }
            )

        decode_status: dict[tuple[str, str], tuple[bool, str | None, str | None]] = {}
        resolution_sets: dict[str, set[str]] = {"rgb": set(), "thermal": set()}
        for modality, files in (("rgb", rgb_files), ("thermal", thermal_files)):
            for image_path in files:
                ok, resolution, error = _verify_image(image_path)
                decode_status[(modality, image_path.stem)] = (ok, resolution, error)
                if ok and resolution:
                    resolution_sets[modality].add(resolution)
                if not ok:
                    decode_invalid_rows.append(
                        {
                            "scene_name": scene_dir.name,
                            "modality": modality,
                            "pair_id": image_path.stem,
                            "relative_path": _relative(image_path, dataset_root),
                            "internal_reason": "decode_invalid",
                            "decode_error": error or "",
                        }
                    )

        for modality, files in (("rgb", rgb_files), ("thermal", thermal_files)):
            hashes: dict[str, list[Path]] = defaultdict(list)
            for image_path in files:
                hashes[_file_sha256(image_path)].append(image_path)
            for digest, paths in sorted(hashes.items()):
                if len(paths) <= 1:
                    continue
                duplicate_rows.append(
                    {
                        "scene_name": scene_dir.name,
                        "modality": modality,
                        "sha256": digest,
                        "count": len(paths),
                        "pair_ids": ";".join(path.stem for path in paths),
                        "relative_paths": ";".join(_relative(path, dataset_root) for path in paths),
                        "diagnostic_policy": "record_only_not_excluded",
                    }
                )

        valid_pair_ids: list[str] = []
        excluded_pair_ids: list[str] = []
        for pair_id in pair_ids:
            rgb_status = decode_status.get(("rgb", pair_id), (False, None, "missing_status"))
            thermal_status = decode_status.get(("thermal", pair_id), (False, None, "missing_status"))
            if rgb_status[0] and thermal_status[0]:
                valid_pair_ids.append(pair_id)
                continue

            invalid_modalities = []
            if not rgb_status[0]:
                invalid_modalities.append("rgb")
            if not thermal_status[0]:
                invalid_modalities.append("thermal")
            excluded_pair_ids.append(pair_id)
            exclusions.append(
                {
                    "scene_name": scene_dir.name,
                    "scene_id": meta["scene_id"],
                    "pair_id": pair_id,
                    "rgb_relative_path": _relative(rgb_by_id[pair_id], dataset_root),
                    "thermal_relative_path": _relative(thermal_by_id[pair_id], dataset_root),
                    "internal_reason": "decode_invalid",
                    "paper_facing_category": "integrity_excluded",
                    "invalid_modalities": ";".join(invalid_modalities),
                }
            )

        scenes.append(
            {
                "scene_name": scene_dir.name,
                "scene_id": meta["scene_id"],
                "light_condition": meta["light_condition"],
                "thermal_rendering": meta["thermal_rendering"],
                "view": meta["view"],
                "view_type": meta["view_type"],
                "scene_label": meta["scene_label"],
                "scene_family": meta["scene_family"],
                "candidate_pair_count": len(pair_ids),
                "candidate_image_count": 2 * len(pair_ids),
                "valid_pair_count": len(valid_pair_ids),
                "valid_image_count": 2 * len(valid_pair_ids),
                "excluded_pair_count": len(excluded_pair_ids),
                "rgb_count": len(rgb_files),
                "thermal_count": len(thermal_files),
                "filename_mismatch_count": len(rgb_only) + len(thermal_only),
                "decode_invalid_count": sum(1 for row in decode_invalid_rows if row["scene_name"] == scene_dir.name),
                "rgb_resolution_set": sorted(resolution_sets["rgb"]),
                "thermal_resolution_set": sorted(resolution_sets["thermal"]),
                "valid_pair_ids": valid_pair_ids,
                "excluded_pair_ids": excluded_pair_ids,
            }
        )

    candidate_pairs = sum(int(scene["candidate_pair_count"]) for scene in scenes)
    valid_pairs = sum(int(scene["valid_pair_count"]) for scene in scenes)
    excluded_pairs = sum(int(scene["excluded_pair_count"]) for scene in scenes)
    condition_counts = _condition_rows(scenes)

    manifest = {
        "dataset_name": dataset_name,
        "manifest_type": "official_valid_evaluation",
        "manifest_version": manifest_version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "naming_policy": {
            "full_benchmark": "UAV-TAlign-12K",
            "lite_subset": "UAV-TAlign-1K-Lite",
            "counting_unit": "images in the dataset name; pair counts are reported explicitly",
        },
        "modalities": ["rgb", "thermal"],
        "pairing_rule": "Files with the same stem under each scene's rgb/ and thermal/ directories form one RGB-thermal pair.",
        "full_candidate_collection": {
            "num_scenes": len(scenes),
            "num_candidate_pairs": candidate_pairs,
            "num_candidate_images": 2 * candidate_pairs,
        },
        "official_evaluation_split": {
            "num_valid_pairs": valid_pairs,
            "num_valid_images": 2 * valid_pairs,
            "num_excluded_pairs": excluded_pairs,
            "selection_policy": "integrity_checked_valid_pairs",
        },
        "exclusions": exclusions,
        "duplicate_hash_diagnostics": duplicate_rows,
        "condition_counts": condition_counts,
        "scenes": scenes,
        "paper_facing_statement": (
            "The official evaluation split contains integrity-checked RGB-thermal pairs "
            "from the UAV-TAlign-12K collection."
        ),
    }

    report = {
        "dataset_name": dataset_name,
        "manifest_type": "integrity_report",
        "manifest_version": manifest_version,
        "generated_at": manifest["generated_at"],
        "summary": {
            "total_candidate_pairs": candidate_pairs,
            "total_candidate_images": 2 * candidate_pairs,
            "valid_evaluation_pairs": valid_pairs,
            "valid_evaluation_images": 2 * valid_pairs,
            "excluded_pair_count": excluded_pairs,
            "filename_mismatch_count": len(filename_mismatch_rows),
            "decode_invalid_count": len(decode_invalid_rows),
            "duplicate_hash_group_count": len(duplicate_rows),
        },
        "excluded_pair_ids": [
            {
                "scene_name": row["scene_name"],
                "pair_id": row["pair_id"],
                "internal_reason": row["internal_reason"],
                "paper_facing_category": row["paper_facing_category"],
            }
            for row in exclusions
        ],
        "filename_mismatches": filename_mismatch_rows,
        "decode_invalid_images": decode_invalid_rows,
        "duplicate_hash_diagnostics": duplicate_rows,
        "per_scene_valid_counts": [
            {
                "scene_name": scene["scene_name"],
                "scene_id": scene["scene_id"],
                "light_condition": scene["light_condition"],
                "thermal_rendering": scene["thermal_rendering"],
                "view_type": scene["view_type"],
                "scene_family": scene["scene_family"],
                "candidate_pair_count": scene["candidate_pair_count"],
                "valid_pair_count": scene["valid_pair_count"],
                "valid_image_count": scene["valid_image_count"],
                "excluded_pair_count": scene["excluded_pair_count"],
            }
            for scene in scenes
        ],
        "per_condition_valid_counts": condition_counts,
    }
    return manifest, report, exclusions, duplicate_rows, decode_invalid_rows


def _write_markdown(path: Path, report: dict, exclusions: list[dict], duplicate_rows: list[dict]) -> None:
    summary = report["summary"]
    lines = [
        "# UAV-TAlign-12K Official Evaluation Integrity Report",
        "",
        "This report defines the integrity-checked official evaluation entry for the UAV-TAlign-12K collection.",
        "",
        "## Summary",
        "",
        "| Field | Count |",
        "|---|---:|",
        f"| Candidate RGB-thermal pairs | {summary['total_candidate_pairs']} |",
        f"| Candidate images | {summary['total_candidate_images']} |",
        f"| Integrity-checked evaluation pairs | {summary['valid_evaluation_pairs']} |",
        f"| Integrity-checked evaluation images | {summary['valid_evaluation_images']} |",
        f"| Integrity-excluded pairs | {summary['excluded_pair_count']} |",
        f"| Filename mismatch count | {summary['filename_mismatch_count']} |",
        f"| Decode-invalid image count | {summary['decode_invalid_count']} |",
        f"| Duplicate-hash diagnostic groups | {summary['duplicate_hash_group_count']} |",
        "",
        "Recommended paper-facing wording:",
        "",
        "> UAV-TAlign-12K contains 6,039 candidate RGB-thermal pairs / 12,078 images; the official evaluation split contains 6,037 integrity-checked pairs.",
        "",
        "## Integrity-Excluded Pairs",
        "",
        "| Scene | Pair ID | Paper-facing category |",
        "|---|---:|---|",
    ]
    if exclusions:
        for row in exclusions:
            lines.append(f"| {row['scene_name']} | {row['pair_id']} | {row['paper_facing_category']} |")
    else:
        lines.append("| None | - | - |")

    lines.extend(
        [
            "",
            "## Duplicate-Hash Diagnostics",
            "",
            "Duplicate hashes are recorded as diagnostics only and are not removed from the official evaluation split.",
            "",
            "| Scene | Modality | Pair IDs | Policy |",
            "|---|---|---|---|",
        ]
    )
    if duplicate_rows:
        for row in duplicate_rows:
            lines.append(
                f"| {row['scene_name']} | {row['modality']} | {row['pair_ids']} | {row['diagnostic_policy']} |"
            )
    else:
        lines.append("| None | - | - | - |")
    _write_text(path, "\n".join(lines) + "\n")


def write_outputs(output_root: Path, manifest: dict, report: dict, exclusions: list[dict], duplicate_rows: list[dict], decode_invalid_rows: list[dict]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    dataset_name = str(manifest["dataset_name"])

    _write_text(
        output_root / f"{dataset_name}_official_valid_evaluation_manifest.json",
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    _write_text(
        output_root / f"{dataset_name}_integrity_report.json",
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    )
    _write_markdown(output_root / f"{dataset_name}_integrity_report.md", report, exclusions, duplicate_rows)

    _write_csv(
        output_root / f"{dataset_name}_integrity_summary.csv",
        [report["summary"]],
        [
            "total_candidate_pairs",
            "total_candidate_images",
            "valid_evaluation_pairs",
            "valid_evaluation_images",
            "excluded_pair_count",
            "filename_mismatch_count",
            "decode_invalid_count",
            "duplicate_hash_group_count",
        ],
    )
    _write_csv(
        output_root / f"{dataset_name}_integrity_excluded_pairs.csv",
        exclusions,
        [
            "scene_name",
            "scene_id",
            "pair_id",
            "rgb_relative_path",
            "thermal_relative_path",
            "internal_reason",
            "paper_facing_category",
            "invalid_modalities",
        ],
    )
    _write_csv(
        output_root / f"{dataset_name}_decode_invalid_images.csv",
        decode_invalid_rows,
        ["scene_name", "modality", "pair_id", "relative_path", "internal_reason", "decode_error"],
    )
    _write_csv(
        output_root / f"{dataset_name}_duplicate_hash_diagnostics.csv",
        duplicate_rows,
        ["scene_name", "modality", "sha256", "count", "pair_ids", "relative_paths", "diagnostic_policy"],
    )
    _write_csv(
        output_root / f"{dataset_name}_per_scene_valid_counts.csv",
        report["per_scene_valid_counts"],
        [
            "scene_name",
            "scene_id",
            "light_condition",
            "thermal_rendering",
            "view_type",
            "scene_family",
            "candidate_pair_count",
            "valid_pair_count",
            "valid_image_count",
            "excluded_pair_count",
        ],
    )
    _write_csv(
        output_root / f"{dataset_name}_per_condition_valid_counts.csv",
        report["per_condition_valid_counts"],
        [
            "group_type",
            "group_value",
            "num_scenes",
            "candidate_pair_count",
            "valid_pair_count",
            "valid_image_count",
            "excluded_pair_count",
            "macro_valid_pairs_per_scene",
        ],
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Build the official UAV-TAlign-12K valid evaluation manifest.")
    ap.add_argument("--dataset_root", required=True)
    ap.add_argument("--output_root", required=True)
    ap.add_argument("--dataset_name", default="UAV-TAlign-12K")
    ap.add_argument("--manifest_version", default="ipt_valid_v1")
    args = ap.parse_args()

    manifest, report, exclusions, duplicate_rows, decode_invalid_rows = build_manifest(
        dataset_root=Path(args.dataset_root),
        dataset_name=str(args.dataset_name),
        manifest_version=str(args.manifest_version),
    )
    write_outputs(
        output_root=Path(args.output_root).resolve(),
        manifest=manifest,
        report=report,
        exclusions=exclusions,
        duplicate_rows=duplicate_rows,
        decode_invalid_rows=decode_invalid_rows,
    )
    print(
        json.dumps(
            {
                "output_root": str(Path(args.output_root).resolve()),
                "summary": report["summary"],
                "excluded_pair_ids": report["excluded_pair_ids"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
