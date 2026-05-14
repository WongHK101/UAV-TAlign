from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence


SMOKE_TEST_PAIR_IDS: Dict[str, List[str]] = {
    "01_day_grayscale_wide_substation_power_lines_50": ["000001", "000013", "000025", "000037", "000050"],
    "08_night_grayscale_urban_22": ["000001", "000006", "000011", "000016", "000022"],
    "13_lowlight_pseudocolor_road_21": ["000001", "000006", "000011", "000016", "000021"],
}


@dataclass(frozen=True)
class PairRecord:
    scene_name: str
    scene_id: str
    pair_id: str
    rgb_path: str
    thermal_path: str
    light_condition: str
    thermal_rendering: str
    view: str
    scene_label: str


def _load_manifest(dataset_root: Path, manifest_path: str | Path | None = None) -> tuple[Dict[str, object], Path]:
    if manifest_path:
        path = Path(manifest_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Could not find manifest_path: {path}")
        return json.loads(path.read_text(encoding="utf-8")), path

    candidates = [
        dataset_root / "subset_manifest.json",
        dataset_root / "dataset_manifest.json",
    ]
    for manifest_path in candidates:
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8")), manifest_path.resolve()
    raise FileNotFoundError(
        f"Could not find subset_manifest.json or dataset_manifest.json under {dataset_root}"
    )


def _scene_meta_map(manifest: Mapping[str, object]) -> Dict[str, Dict[str, object]]:
    scene_meta: Dict[str, Dict[str, object]] = {}
    for item in manifest.get("scenes", []):
        if not isinstance(item, dict):
            continue
        scene_name = str(item.get("scene_name", "")).strip()
        if scene_name:
            scene_meta[scene_name] = item
    return scene_meta


def _manifest_pair_ids_by_scene(manifest: Mapping[str, object]) -> Dict[str, set[str]]:
    selected: Dict[str, set[str]] = {}
    for item in manifest.get("scenes", []):
        if not isinstance(item, dict):
            continue
        scene_name = str(item.get("scene_name", "")).strip()
        if not scene_name:
            continue
        pair_ids = item.get("valid_pair_ids", None)
        if pair_ids is None:
            pair_ids = item.get("pair_ids", None)
        if pair_ids is None:
            continue
        selected[scene_name] = {str(pair_id).strip() for pair_id in pair_ids if str(pair_id).strip()}
    return selected


def _image_pairs_for_scene(scene_root: Path) -> List[tuple[str, Path, Path]]:
    rgb_root = scene_root / "rgb"
    thermal_root = scene_root / "thermal"
    if not rgb_root.exists():
        raise FileNotFoundError(f"Missing rgb directory: {rgb_root}")
    if not thermal_root.exists():
        raise FileNotFoundError(f"Missing thermal directory: {thermal_root}")

    rgb_map = {path.stem: path for path in sorted(rgb_root.glob("*")) if path.is_file()}
    thermal_map = {path.stem: path for path in sorted(thermal_root.glob("*")) if path.is_file()}
    common_ids = sorted(set(rgb_map.keys()) & set(thermal_map.keys()))
    return [(pair_id, rgb_map[pair_id], thermal_map[pair_id]) for pair_id in common_ids]


def list_dataset_pairs(
    dataset_root: str | Path,
    scene_names: Sequence[str] | None = None,
    pair_ids_by_scene: Mapping[str, Sequence[str]] | None = None,
    manifest_path: str | Path | None = None,
) -> List[PairRecord]:
    root = Path(dataset_root).resolve()
    manifest, _ = _load_manifest(root, manifest_path=manifest_path)
    scene_meta = _scene_meta_map(manifest)
    manifest_ids_by_scene = _manifest_pair_ids_by_scene(manifest)

    selected_scenes = list(scene_names) if scene_names is not None else [
        str(item.get("scene_name", "")).strip()
        for item in manifest.get("scenes", [])
        if isinstance(item, dict) and str(item.get("scene_name", "")).strip()
    ]

    records: List[PairRecord] = []
    for scene_name in selected_scenes:
        scene_root = root / scene_name
        meta = scene_meta.get(scene_name, {})
        allowed_ids = None
        if scene_name in manifest_ids_by_scene:
            allowed_ids = set(manifest_ids_by_scene[scene_name])
        if pair_ids_by_scene is not None and scene_name in pair_ids_by_scene:
            explicit_ids = {str(pair_id).strip() for pair_id in pair_ids_by_scene[scene_name]}
            allowed_ids = explicit_ids if allowed_ids is None else allowed_ids & explicit_ids

        for pair_id, rgb_path, thermal_path in _image_pairs_for_scene(scene_root):
            if allowed_ids is not None and pair_id not in allowed_ids:
                continue
            records.append(
                PairRecord(
                    scene_name=scene_name,
                    scene_id=str(meta.get("scene_id", scene_name.split("_", 1)[0])),
                    pair_id=pair_id,
                    rgb_path=str(rgb_path),
                    thermal_path=str(thermal_path),
                    light_condition=str(meta.get("light_condition", "")),
                    thermal_rendering=str(meta.get("thermal_rendering", "")),
                    view=str(meta.get("view", "")),
                    scene_label=str(meta.get("scene_label", "")),
                )
            )
    return records


def build_smoke_test_pairs(dataset_root: str | Path, manifest_path: str | Path | None = None) -> List[PairRecord]:
    return list_dataset_pairs(
        dataset_root=dataset_root,
        scene_names=list(SMOKE_TEST_PAIR_IDS.keys()),
        pair_ids_by_scene=SMOKE_TEST_PAIR_IDS,
        manifest_path=manifest_path,
    )


def _canonical_manifest_sha256(manifest: Mapping[str, object]) -> str:
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def manifest_provenance(dataset_root: str | Path, manifest_path: str | Path | None = None) -> Dict[str, object]:
    root = Path(dataset_root).resolve()
    manifest, path = _load_manifest(root, manifest_path=manifest_path)
    raw = path.read_bytes()
    official_split = manifest.get("official_evaluation_split", {}) if isinstance(manifest, dict) else {}
    full_collection = manifest.get("full_candidate_collection", {}) if isinstance(manifest, dict) else {}
    return {
        "manifest_path": str(path),
        "manifest_sha256": _canonical_manifest_sha256(manifest),
        "manifest_hash_policy": "canonical_json_sort_keys_compact_utf8",
        "manifest_file_sha256": hashlib.sha256(raw).hexdigest(),
        "dataset_name": manifest.get("dataset_name"),
        "manifest_type": manifest.get("manifest_type", "dataset_manifest"),
        "manifest_version": manifest.get("manifest_version"),
        "full_candidate_pairs": full_collection.get("num_candidate_pairs", manifest.get("num_pairs")),
        "full_candidate_images": full_collection.get("num_candidate_images", manifest.get("num_images")),
        "valid_pair_count": official_split.get("num_valid_pairs", manifest.get("num_pairs")),
        "valid_image_count": official_split.get("num_valid_images", manifest.get("num_images")),
        "excluded_pair_count": official_split.get("num_excluded_pairs", 0),
    }


def group_pairs_by_scene(pairs: Iterable[PairRecord]) -> Dict[str, List[PairRecord]]:
    grouped: Dict[str, List[PairRecord]] = {}
    for pair in pairs:
        grouped.setdefault(pair.scene_name, []).append(pair)
    for scene_name in grouped:
        grouped[scene_name] = sorted(grouped[scene_name], key=lambda item: item.pair_id)
    return grouped
