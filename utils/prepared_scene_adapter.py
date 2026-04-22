from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Dict, Iterable, List

from utils.spectral_image_utils import load_image_preserve_dtype
from utils.uav_talign_dataset import PairRecord


def _manifest_item(source_path: Path, image_name: str, frame_id: str, modality_kind: str) -> Dict[str, object]:
    loaded = load_image_preserve_dtype(source_path)
    metadata = dict(loaded.metadata or {})
    metadata.update(
        {
            "source_path": str(source_path),
            "width": int(loaded.width),
            "height": int(loaded.height),
            "channel_count": int(loaded.channel_count),
            "dtype": str(loaded.dtype_name),
            "modality_kind": modality_kind,
        }
    )
    return {
        "image_name": image_name,
        "frame_id": frame_id,
        "source_path": str(source_path),
        "metadata": metadata,
    }


def _write_manifest(scene_root: Path, scene_name: str, scene_kind: str, modality_kind: str, images: List[Dict[str, object]]) -> None:
    payload = {
        "scene_name": scene_name,
        "scene_root": str(scene_root),
        "scene_kind": scene_kind,
        "modality_kind": modality_kind,
        "images": images,
    }
    (scene_root / "spectral_manifest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def build_prepared_scene_from_pairs(
    pairs: Iterable[PairRecord],
    out_root: str | Path,
    band_name: str = "T",
) -> Path:
    out_path = Path(out_root).resolve()
    rgb_root = out_path / "RGB"
    band_root = out_path / f"{band_name}_raw"

    if out_path.exists():
        shutil.rmtree(out_path)

    for root in (rgb_root, band_root):
        (root / "images").mkdir(parents=True, exist_ok=True)
    (rgb_root / "sparse" / "0").mkdir(parents=True, exist_ok=True)

    rgb_items: List[Dict[str, object]] = []
    band_items: List[Dict[str, object]] = []
    for pair in pairs:
        image_name = f"{pair.pair_id}.jpg"
        rgb_items.append(
            _manifest_item(
                source_path=Path(pair.rgb_path),
                image_name=image_name,
                frame_id=pair.pair_id,
                modality_kind="rgb",
            )
        )
        band_items.append(
            _manifest_item(
                source_path=Path(pair.thermal_path),
                image_name=image_name,
                frame_id=pair.pair_id,
                modality_kind="thermal",
            )
        )

    rgb_items.sort(key=lambda item: str(item["image_name"]))
    band_items.sort(key=lambda item: str(item["image_name"]))

    _write_manifest(rgb_root, "RGB", "uav_talign_scene", "rgb", rgb_items)
    _write_manifest(band_root, f"{band_name}_raw", "uav_talign_scene", "thermal", band_items)
    return out_path
