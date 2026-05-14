# UAV-TAlign-12K Official Evaluation Integrity Report

This report defines the integrity-checked official evaluation entry for the UAV-TAlign-12K collection.

## Summary

| Field | Count |
|---|---:|
| Candidate RGB-thermal pairs | 6039 |
| Candidate images | 12078 |
| Integrity-checked evaluation pairs | 6037 |
| Integrity-checked evaluation images | 12074 |
| Integrity-excluded pairs | 2 |
| Filename mismatch count | 0 |
| Decode-invalid image count | 2 |
| Duplicate-hash diagnostic groups | 1 |

Recommended paper-facing wording:

> UAV-TAlign-12K contains 6,039 candidate RGB-thermal pairs / 12,078 images; the official evaluation split contains 6,037 integrity-checked pairs.

## Integrity-Excluded Pairs

| Scene | Pair ID | Paper-facing category |
|---|---:|---|
| 13_lowlight_pseudocolor_road_469 | 000058 | integrity_excluded |
| 13_lowlight_pseudocolor_road_469 | 000080 | integrity_excluded |

## Duplicate-Hash Diagnostics

Duplicate hashes are recorded as diagnostics only and are not removed from the official evaluation split.

| Scene | Modality | Pair IDs | Policy |
|---|---|---|---|
| 05_night_pseudocolor_solar_panels_1315 | thermal | 000905;000906 | record_only_not_excluded |
