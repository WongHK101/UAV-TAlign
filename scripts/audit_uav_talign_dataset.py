from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}


@dataclass
class SceneAudit:
    dataset_name: str
    scene_name: str
    scene_id: str
    light_condition: str
    thermal_rendering: str
    view_type: str
    scene_family: str
    rgb_count: int
    thermal_count: int
    pair_count: int
    rgb_only_count: int
    thermal_only_count: int
    rgb_resolution_set: str
    thermal_resolution_set: str
    corrupt_rgb_count: int
    corrupt_thermal_count: int
    duplicate_rgb_hash_count: int
    duplicate_thermal_hash_count: int


def _image_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        p for p in root.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )


def _parse_scene_name(scene_name: str) -> dict[str, str]:
    parts = scene_name.split("_")
    scene_id = parts[0] if parts else ""
    light = parts[1] if len(parts) > 1 else "unknown"
    rendering = parts[2] if len(parts) > 2 else "unknown"
    if len(parts) > 3 and parts[3] in {"wide", "zoom"}:
        view_type = parts[3]
        family_parts = parts[4:-1]
    else:
        view_type = "standard"
        family_parts = parts[3:-1]
    return {
        "scene_id": scene_id,
        "light_condition": light,
        "thermal_rendering": rendering,
        "view_type": view_type,
        "scene_family": "_".join(family_parts) if family_parts else "unknown",
    }


def _verify_image(path: Path) -> tuple[bool, str, str]:
    try:
        with Image.open(path) as im:
            resolution = f"{int(im.size[0])}x{int(im.size[1])}"
            mode = str(im.mode)
            im.verify()
        return True, resolution, mode
    except Exception as exc:
        return False, "", f"{type(exc).__name__}: {exc}"


def _file_hash(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _counter_to_sorted_string(counter: Counter[str]) -> str:
    return "; ".join(f"{key}:{counter[key]}" for key in sorted(counter))


def _write_frozen_manifest(output_root: Path, dataset_name: str, scene_rows: list[SceneAudit]) -> None:
    pair_count = sum(row.pair_count for row in scene_rows)
    rgb_count = sum(row.rgb_count for row in scene_rows)
    thermal_count = sum(row.thermal_count for row in scene_rows)
    manifest = {
        "dataset_name": dataset_name,
        "manifest_version": "ipt_p0a_v1",
        "naming_policy": {
            "full_benchmark": "UAV-TAlign-12K",
            "lite_subset": "UAV-TAlign-1K-Lite",
            "counting_unit": "images in the dataset name; pair counts are reported explicitly",
        },
        "num_scenes": len(scene_rows),
        "num_rgb_images": rgb_count,
        "num_thermal_images": thermal_count,
        "num_pairs": pair_count,
        "num_images": rgb_count + thermal_count,
        "modalities": ["rgb", "thermal"],
        "pairing_rule": "Files with the same stem under each scene's rgb/ and thermal/ directories form one RGB-thermal pair.",
        "statistics_policy": {
            "micro_pair_level": "Aggregate over all pairs.",
            "macro_scene_level": "Average over scenes to avoid dominance by long sequences.",
            "condition_level": "Report both scene counts and pair counts for light/rendering/view/family groups.",
        },
        "scenes": [
            {
                "scene_name": row.scene_name,
                "scene_id": row.scene_id,
                "light_condition": row.light_condition,
                "thermal_rendering": row.thermal_rendering,
                "view_type": row.view_type,
                "scene_family": row.scene_family,
                "pair_count": row.pair_count,
                "image_count": 2 * row.pair_count,
                "rgb_count": row.rgb_count,
                "thermal_count": row.thermal_count,
                "rgb_resolution_set": row.rgb_resolution_set,
                "thermal_resolution_set": row.thermal_resolution_set,
                "integrity": {
                    "rgb_only_count": row.rgb_only_count,
                    "thermal_only_count": row.thermal_only_count,
                    "corrupt_rgb_count": row.corrupt_rgb_count,
                    "corrupt_thermal_count": row.corrupt_thermal_count,
                    "duplicate_rgb_hash_count": row.duplicate_rgb_hash_count,
                    "duplicate_thermal_hash_count": row.duplicate_thermal_hash_count,
                },
            }
            for row in scene_rows
        ],
    }
    (output_root / f"{dataset_name}_frozen_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def audit_dataset(
    dataset_root: Path,
    dataset_name: str,
    output_root: Path,
    verify_images: bool,
    hash_duplicates: bool,
) -> dict:
    dataset_root = dataset_root.resolve()
    scene_dirs = sorted(p for p in dataset_root.iterdir() if p.is_dir())
    scene_rows: list[SceneAudit] = []
    corrupt_rows: list[dict] = []
    duplicate_rows: list[dict] = []

    for scene_dir in scene_dirs:
        meta = _parse_scene_name(scene_dir.name)
        rgb_files = _image_files(scene_dir / "rgb")
        thermal_files = _image_files(scene_dir / "thermal")
        rgb_by_id = {p.stem: p for p in rgb_files}
        thermal_by_id = {p.stem: p for p in thermal_files}
        common_ids = sorted(set(rgb_by_id) & set(thermal_by_id))
        rgb_only = sorted(set(rgb_by_id) - set(thermal_by_id))
        thermal_only = sorted(set(thermal_by_id) - set(rgb_by_id))

        rgb_resolutions: Counter[str] = Counter()
        thermal_resolutions: Counter[str] = Counter()
        corrupt_rgb = 0
        corrupt_thermal = 0
        if verify_images:
            for modality, files, res_counter in (
                ("rgb", rgb_files, rgb_resolutions),
                ("thermal", thermal_files, thermal_resolutions),
            ):
                for path in files:
                    ok, resolution, error_or_mode = _verify_image(path)
                    if ok:
                        res_counter[resolution] += 1
                    else:
                        if modality == "rgb":
                            corrupt_rgb += 1
                        else:
                            corrupt_thermal += 1
                        corrupt_rows.append(
                            {
                                "dataset_name": dataset_name,
                                "scene_name": scene_dir.name,
                                "modality": modality,
                                "path": str(path),
                                "error": error_or_mode,
                            }
                        )
        else:
            for modality, files, res_counter in (
                ("rgb", rgb_files[:1], rgb_resolutions),
                ("thermal", thermal_files[:1], thermal_resolutions),
            ):
                for path in files:
                    ok, resolution, error_or_mode = _verify_image(path)
                    if ok:
                        res_counter[resolution] += len(rgb_files if modality == "rgb" else thermal_files)
                    else:
                        corrupt_rows.append(
                            {
                                "dataset_name": dataset_name,
                                "scene_name": scene_dir.name,
                                "modality": modality,
                                "path": str(path),
                                "error": error_or_mode,
                            }
                        )

        duplicate_rgb_count = 0
        duplicate_thermal_count = 0
        if hash_duplicates:
            for modality, files in (("rgb", rgb_files), ("thermal", thermal_files)):
                hashes: defaultdict[str, list[str]] = defaultdict(list)
                for path in files:
                    hashes[_file_hash(path)].append(path.name)
                for digest, names in hashes.items():
                    if len(names) > 1:
                        if modality == "rgb":
                            duplicate_rgb_count += len(names)
                        else:
                            duplicate_thermal_count += len(names)
                        duplicate_rows.append(
                            {
                                "dataset_name": dataset_name,
                                "scene_name": scene_dir.name,
                                "modality": modality,
                                "sha256": digest,
                                "count": len(names),
                                "filenames": ";".join(names[:20]),
                            }
                        )

        scene_rows.append(
            SceneAudit(
                dataset_name=dataset_name,
                scene_name=scene_dir.name,
                scene_id=meta["scene_id"],
                light_condition=meta["light_condition"],
                thermal_rendering=meta["thermal_rendering"],
                view_type=meta["view_type"],
                scene_family=meta["scene_family"],
                rgb_count=len(rgb_files),
                thermal_count=len(thermal_files),
                pair_count=len(common_ids),
                rgb_only_count=len(rgb_only),
                thermal_only_count=len(thermal_only),
                rgb_resolution_set=_counter_to_sorted_string(rgb_resolutions),
                thermal_resolution_set=_counter_to_sorted_string(thermal_resolutions),
                corrupt_rgb_count=corrupt_rgb,
                corrupt_thermal_count=corrupt_thermal,
                duplicate_rgb_hash_count=duplicate_rgb_count,
                duplicate_thermal_hash_count=duplicate_thermal_count,
            )
        )

    rows_as_dict = [asdict(row) for row in scene_rows]
    _write_csv(output_root / f"{dataset_name}_scene_audit.csv", rows_as_dict, list(rows_as_dict[0].keys()) if rows_as_dict else [])
    _write_csv(
        output_root / f"{dataset_name}_corrupt_images.csv",
        corrupt_rows,
        ["dataset_name", "scene_name", "modality", "path", "error"],
    )
    _write_csv(
        output_root / f"{dataset_name}_duplicate_hashes.csv",
        duplicate_rows,
        ["dataset_name", "scene_name", "modality", "sha256", "count", "filenames"],
    )

    def aggregate_by(key: str) -> list[dict]:
        grouped: defaultdict[str, list[SceneAudit]] = defaultdict(list)
        for row in scene_rows:
            grouped[str(getattr(row, key))].append(row)
        out = []
        for value in sorted(grouped):
            items = grouped[value]
            pair_count = sum(item.pair_count for item in items)
            out.append(
                {
                    "dataset_name": dataset_name,
                    "group_type": key,
                    "group_value": value,
                    "num_scenes": len(items),
                    "pair_count": pair_count,
                    "image_count": 2 * pair_count,
                    "macro_pairs_per_scene": round(pair_count / max(len(items), 1), 4),
                }
            )
        return out

    condition_rows = []
    for key in ("light_condition", "thermal_rendering", "view_type", "scene_family"):
        condition_rows.extend(aggregate_by(key))
    _write_csv(
        output_root / f"{dataset_name}_condition_audit.csv",
        condition_rows,
        ["dataset_name", "group_type", "group_value", "num_scenes", "pair_count", "image_count", "macro_pairs_per_scene"],
    )
    _write_frozen_manifest(output_root, dataset_name, scene_rows)

    pair_count = sum(row.pair_count for row in scene_rows)
    rgb_count = sum(row.rgb_count for row in scene_rows)
    thermal_count = sum(row.thermal_count for row in scene_rows)
    summary = {
        "dataset_name": dataset_name,
        "dataset_root": str(dataset_root),
        "audit_time": datetime.now().isoformat(timespec="seconds"),
        "num_scenes": len(scene_rows),
        "num_rgb_images": rgb_count,
        "num_thermal_images": thermal_count,
        "num_pairs": pair_count,
        "num_images": rgb_count + thermal_count,
        "light_condition_counts": Counter(row.light_condition for row in scene_rows),
        "thermal_rendering_counts": Counter(row.thermal_rendering for row in scene_rows),
        "view_type_counts": Counter(row.view_type for row in scene_rows),
        "scene_family_counts": Counter(row.scene_family for row in scene_rows),
        "rgb_only_total": sum(row.rgb_only_count for row in scene_rows),
        "thermal_only_total": sum(row.thermal_only_count for row in scene_rows),
        "corrupt_rgb_total": sum(row.corrupt_rgb_count for row in scene_rows),
        "corrupt_thermal_total": sum(row.corrupt_thermal_count for row in scene_rows),
        "duplicate_rgb_hash_total": sum(row.duplicate_rgb_hash_count for row in scene_rows),
        "duplicate_thermal_hash_total": sum(row.duplicate_thermal_hash_count for row in scene_rows),
        "verify_images": bool(verify_images),
        "hash_duplicates": bool(hash_duplicates),
    }
    summary = json.loads(json.dumps(summary, default=dict))
    (output_root / f"{dataset_name}_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def write_markdown_report(output_root: Path, summaries: list[dict]) -> None:
    lines = [
        "# UAV-TAlign Dataset Audit",
        "",
        "This report is generated by `scripts/audit_uav_talign_dataset.py`.",
        "It is read-only with respect to the dataset directories.",
        "",
        "## Dataset Summary",
        "",
        "| Dataset | Scenes | Pairs | Images | RGB-only | Thermal-only | Corrupt | Duplicate-hash |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in summaries:
        corrupt = int(item["corrupt_rgb_total"]) + int(item["corrupt_thermal_total"])
        dup = int(item["duplicate_rgb_hash_total"]) + int(item["duplicate_thermal_hash_total"])
        lines.append(
            f"| {item['dataset_name']} | {item['num_scenes']} | {item['num_pairs']} | "
            f"{item['num_images']} | {item['rgb_only_total']} | {item['thermal_only_total']} | "
            f"{corrupt} | {dup} |"
        )
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            "- `<dataset>_scene_audit.csv`: per-scene metadata, counts, resolution sets, and integrity counters.",
            "- `<dataset>_condition_audit.csv`: light/rendering/view/family grouping for macro and micro reporting.",
            "- `<dataset>_corrupt_images.csv`: image verification failures.",
            "- `<dataset>_duplicate_hashes.csv`: full-file SHA256 duplicate groups.",
            "- `<dataset>_summary.json`: machine-readable top-level summary.",
            "",
            "## Reporting Notes",
            "",
            "- `UAV-TAlign-12K` is the full journal benchmark.",
            "- `UAV-TAlign-1K-Lite` is the fixed lightweight subset for development, ablation, and fast checks.",
            "- Because pair counts are imbalanced across scenes, downstream reports should include micro pair-level, macro scene-level, per-scene, and condition-level statistics.",
        ]
    )
    (output_root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Read-only audit for UAV-TAlign dataset releases.")
    ap.add_argument(
        "--dataset",
        action="append",
        nargs=2,
        metavar=("NAME", "ROOT"),
        required=True,
        help="Dataset name and root path. Can be specified multiple times.",
    )
    ap.add_argument("--output_root", required=True)
    ap.add_argument("--verify_images", action="store_true", help="Verify every image with PIL.")
    ap.add_argument("--hash_duplicates", action="store_true", help="Detect duplicate files by full-file SHA256 hash.")
    args = ap.parse_args()

    output_root = Path(args.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    summaries = []
    for name, root in args.dataset:
        summaries.append(
            audit_dataset(
                dataset_root=Path(root),
                dataset_name=str(name),
                output_root=output_root,
                verify_images=bool(args.verify_images),
                hash_duplicates=bool(args.hash_duplicates),
            )
        )
    write_markdown_report(output_root, summaries)
    print(json.dumps({"output_root": str(output_root), "summaries": summaries}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
