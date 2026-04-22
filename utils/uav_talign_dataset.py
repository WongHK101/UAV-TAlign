from __future__ import annotations

import json
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


def _load_manifest(dataset_root: Path) -> Dict[str, object]:
    candidates = [
        dataset_root / "subset_manifest.json",
        dataset_root / "dataset_manifest.json",
    ]
    for manifest_path in candidates:
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
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
) -> List[PairRecord]:
    root = Path(dataset_root).resolve()
    manifest = _load_manifest(root)
    scene_meta = _scene_meta_map(manifest)

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
        if pair_ids_by_scene is not None and scene_name in pair_ids_by_scene:
            allowed_ids = {str(pair_id).strip() for pair_id in pair_ids_by_scene[scene_name]}

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


def build_smoke_test_pairs(dataset_root: str | Path) -> List[PairRecord]:
    return list_dataset_pairs(
        dataset_root=dataset_root,
        scene_names=list(SMOKE_TEST_PAIR_IDS.keys()),
        pair_ids_by_scene=SMOKE_TEST_PAIR_IDS,
    )


def group_pairs_by_scene(pairs: Iterable[PairRecord]) -> Dict[str, List[PairRecord]]:
    grouped: Dict[str, List[PairRecord]] = {}
    for pair in pairs:
        grouped.setdefault(pair.scene_name, []).append(pair)
    for scene_name in grouped:
        grouped[scene_name] = sorted(grouped[scene_name], key=lambda item: item.pair_id)
    return grouped
