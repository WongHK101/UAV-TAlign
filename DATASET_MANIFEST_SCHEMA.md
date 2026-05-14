# UAV-TAlign Dataset Manifest Schema for IP&T

This schema defines the journal-facing dataset metadata used for the
Infrared Physics & Technology version of UAV-TAlign.

## Naming Policy

- `UAV-TAlign-12K`: the full benchmark collection.
- `UAV-TAlign-1K-Lite`: the fixed lightweight subset for development,
  ablation, fast evaluation, and sanity checks.
- Dataset names use image-count scale. Pair counts must always be reported
  explicitly.

## Top-Level Fields

| Field | Meaning |
|---|---|
| `dataset_name` | `UAV-TAlign-12K` or `UAV-TAlign-1K-Lite`. |
| `manifest_version` | Schema/version tag for reproducibility. |
| `naming_policy` | Human-readable naming convention. |
| `num_scenes` | Number of scene directories. |
| `num_rgb_images` | Number of RGB images. |
| `num_thermal_images` | Number of thermal/infrared images. |
| `num_pairs` | Number of RGB-thermal pairs with matching file stems. |
| `num_images` | `num_rgb_images + num_thermal_images`. |
| `modalities` | Expected modalities, currently `rgb` and `thermal`. |
| `pairing_rule` | Rule for forming RGB-thermal pairs. |
| `statistics_policy` | Required micro, macro, and condition-level reporting policy. |
| `scenes` | Per-scene metadata records. |

## Per-Scene Fields

| Field | Meaning |
|---|---|
| `scene_name` | Directory name. |
| `scene_id` | Numeric scene prefix parsed from `scene_name`. |
| `light_condition` | `day`, `night`, or `lowlight`. |
| `thermal_rendering` | `grayscale` or `pseudocolor`. |
| `view_type` | `wide`, `zoom`, or `standard`. |
| `scene_family` | Parsed scene family label. |
| `pair_count` | Number of matched RGB-thermal pairs. |
| `image_count` | `2 * pair_count`. |
| `rgb_count` | Number of RGB image files. |
| `thermal_count` | Number of thermal image files. |
| `rgb_resolution_set` | Resolution-count summary for RGB images. |
| `thermal_resolution_set` | Resolution-count summary for thermal images. |
| `integrity` | Filename mismatch, corrupt-image, and duplicate-hash counters. |

## Reporting Policy

Because `UAV-TAlign-12K` has 15 scenes with imbalanced pair counts, journal
tables should support all of the following views:

- Micro pair-level averages over all RGB-thermal pairs.
- Macro scene-level averages over scenes.
- Per-scene statistics.
- Condition-level statistics by light condition, thermal rendering, view type,
  and scene family.

## Generation

Use:

```powershell
python scripts\audit_uav_talign_dataset.py `
  --dataset UAV-TAlign-1K-Lite UAV-TAlign-1K `
  --dataset UAV-TAlign-12K UAV-TAlign-12K `
  --output_root review_artifacts\ipt_p0a_dataset_audit_<timestamp> `
  --verify_images `
  --hash_duplicates
```

The script is read-only with respect to dataset directories and writes all
artifacts under the requested output root.
