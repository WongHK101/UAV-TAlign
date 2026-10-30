"""Portable entry point for the frozen RIFT2 resize-aware evaluation.

The numerical path in run_one is unchanged from the archived experiment.
CLI, path isolation, and resume validation are release-time additions.
"""

import argparse
import csv
import hashlib
import json
import os
import pathlib
import subprocess
import time
import traceback
from collections import Counter, defaultdict

DATA = MANIFEST = OUT = RIFT2_REPO = None
MANIFEST_CANONICAL_HASH = "a092f7ad00c6e02ead3bd39de5c246001f1d4bebbc4105ba715ef37bbb202c6c"
RIFT2_COMMIT = "7d92f005f84c25dd23c07670c2aad90e0f3997e5"

CONFIG_NAME = "strong_resize1200_npt2000_patch64"
MAX_DIM = 1200
RIFT2_KWARGS = {"npt": 2000, "patch_size": 64}
LOWES_RATIO = 0.95
MUTUAL = False
ESTIMATOR = "USAC_MAGSAC"
REPROJ_THRESHOLD = 5.0


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_commit(repo):
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo), text=True).strip()
    except Exception:
        return None


def resize_max(img, max_dim):
    h, w = img.shape[:2]
    scale = min(1.0, float(max_dim) / float(max(h, w)))
    if scale < 1.0:
        img = cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return img, scale


def load_records():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    canonical_hash = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if canonical_hash != MANIFEST_CANONICAL_HASH:
        raise ValueError("Use the frozen official evaluation manifest supplied with this release.")
    rows = []
    for scene in manifest["scenes"]:
        for pid in scene["valid_pair_ids"]:
            scene_name = scene["scene_name"]
            rows.append(
                {
                    "scene_id": scene["scene_id"],
                    "scene_name": scene_name,
                    "pair_id": pid,
                    "light_condition": scene["light_condition"],
                    "thermal_rendering": scene["thermal_rendering"],
                    "view": scene.get("view") or scene.get("view_type") or "standard",
                    "scene_family": scene.get("scene_family") or scene.get("scene_label") or "",
                    "rgb_path": str(DATA / scene_name / "rgb" / f"{pid}.jpg"),
                    "thermal_path": str(DATA / scene_name / "thermal" / f"{pid}.jpg"),
                }
            )
    if len(rows) != 6037 or len({(r["scene_id"], r["pair_id"]) for r in rows}) != 6037:
        raise ValueError("Expected 6037 unique official evaluation pairs.")
    for row in rows:
        for key in ("rgb_path", "thermal_path"):
            path = pathlib.Path(row[key]).resolve()
            if DATA not in path.parents or not path.is_file():
                raise FileNotFoundError(f"Missing or external image: {path}")
    return manifest, rows


def existing_rows(path):
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Incomplete JSONL at line {line_number}; preserve and repair it before resuming."
                ) from exc
    return rows


def run_one(model, record, index, total):
    t0 = time.time()
    rec = {
        "method": "rift2",
        "config_name": CONFIG_NAME,
        "max_dim": MAX_DIM,
        "rift2_kwargs": RIFT2_KWARGS,
        "lowes_ratio": LOWES_RATIO,
        "mutual": MUTUAL,
        "estimator": ESTIMATOR,
        "reproj_threshold": REPROJ_THRESHOLD,
        "index": index,
        "total": total,
        **{
            k: record[k]
            for k in [
                "scene_id",
                "scene_name",
                "pair_id",
                "light_condition",
                "thermal_rendering",
                "view",
                "scene_family",
            ]
        },
    }
    try:
        img1 = cv2.imread(record["rgb_path"])
        img2 = cv2.imread(record["thermal_path"])
        if img1 is None or img2 is None:
            raise RuntimeError("decode_failed")
        rec["rgb_shape"] = list(img1.shape[:2])
        rec["thermal_shape"] = list(img2.shape[:2])
        img1, s1 = resize_max(img1, MAX_DIM)
        img2, s2 = resize_max(img2, MAX_DIM)
        ft0 = time.time()
        kp1, des1, kp2, des2 = model(img1, img2)
        ft1 = time.time()
        rec.update(kp1=len(kp1), kp2=len(kp2), scale_rgb=s1, scale_thermal=s2, feature_sec=ft1 - ft0)
        if des1 is None or des2 is None or len(kp1) < 2 or len(kp2) < 2:
            rec.update(status="no_features", matches=0, inliers=0, inlier_ratio=0.0, homography_available=False)
        else:
            points1, points2, matches = match_keypoints_nn(
                des1, des2, kp1, kp2, lowes_ratio=LOWES_RATIO, mutual=MUTUAL
            )
            H = None
            inliers = 0
            reproj = None
            coverage = 0.0
            if len(points1) >= 4:
                H, mask = cv2.findHomography(points1, points2, cv2.USAC_MAGSAC, REPROJ_THRESHOLD)
                if H is not None and mask is not None:
                    m = mask.ravel().astype(bool)
                    inliers = int(m.sum())
                    if inliers:
                        pts1 = cv2.perspectiveTransform(points1[m].reshape(-1, 1, 2), H).reshape(-1, 2)
                        reproj = float(np.mean(np.linalg.norm(pts1 - points2[m], axis=1)))
                        h, w = img1.shape[:2]
                        grid = 4
                        xs = np.clip((points1[m, 0] / max(w, 1) * grid).astype(int), 0, grid - 1)
                        ys = np.clip((points1[m, 1] / max(h, 1) * grid).astype(int), 0, grid - 1)
                        coverage = float(len(set(zip(xs.tolist(), ys.tolist())))) / float(grid * grid)
            rec.update(
                status="ok" if H is not None else "fit_failed",
                matches=len(matches),
                inliers=inliers,
                inlier_ratio=(float(inliers) / float(len(matches)) if matches else 0.0),
                reproj_error=reproj,
                coverage=coverage,
                homography_available=H is not None,
            )
    except Exception as e:
        rec.update(status="error", error=str(e), traceback=traceback.format_exc())
    rec["runtime_sec"] = time.time() - t0
    return rec


def mean(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return float(np.mean(vals)) if vals else None


def median(vals):
    vals = [v for v in vals if isinstance(v, (int, float))]
    return float(np.median(vals)) if vals else None


def summarize(rows, run_config, manifest):
    n = len(rows)
    h = sum(1 for r in rows if r.get("homography_available"))
    summary = dict(run_config)
    summary.update(
        {
            "finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "records": n,
            "status_counts": dict(Counter(r.get("status") for r in rows)),
            "homography_available": h,
            "homography_rate": h / max(n, 1),
            "mean_matches": mean([r.get("matches") for r in rows]),
            "median_matches": median([r.get("matches") for r in rows]),
            "mean_inliers": mean([r.get("inliers") for r in rows]),
            "median_inliers": median([r.get("inliers") for r in rows]),
            "mean_inlier_ratio": mean([r.get("inlier_ratio") for r in rows]),
            "median_inlier_ratio": median([r.get("inlier_ratio") for r in rows]),
            "mean_coverage": mean([r.get("coverage") for r in rows]),
            "median_coverage": median([r.get("coverage") for r in rows]),
            "mean_reproj_error": mean([r.get("reproj_error") for r in rows]),
            "median_reproj_error": median([r.get("reproj_error") for r in rows]),
            "mean_runtime_sec": mean([r.get("runtime_sec") for r in rows]),
            "median_runtime_sec": median([r.get("runtime_sec") for r in rows]),
            "total_pair_runtime_sec": float(np.sum([r.get("runtime_sec", 0.0) for r in rows])),
            "wall_runtime_sec": time.time() - run_config["started_at_unix"],
        }
    )
    return summary


def write_scene_csv(rows, path):
    by_scene = defaultdict(list)
    for row in rows:
        by_scene[row["scene_id"]].append(row)
    fieldnames = [
        "scene_id",
        "scene_name",
        "records",
        "status_counts",
        "homography_available",
        "homography_rate",
        "mean_matches",
        "mean_inliers",
        "median_inlier_ratio",
        "mean_coverage",
        "median_reproj_error",
        "mean_runtime_sec",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for scene_id in sorted(by_scene.keys()):
            vals = by_scene[scene_id]
            n = len(vals)
            writer.writerow(
                {
                    "scene_id": scene_id,
                    "scene_name": vals[0]["scene_name"],
                    "records": n,
                    "status_counts": dict(Counter(r.get("status") for r in vals)),
                    "homography_available": sum(1 for r in vals if r.get("homography_available")),
                    "homography_rate": sum(1 for r in vals if r.get("homography_available")) / max(n, 1),
                    "mean_matches": mean([r.get("matches") for r in vals]),
                    "mean_inliers": mean([r.get("inliers") for r in vals]),
                    "median_inlier_ratio": median([r.get("inlier_ratio") for r in vals]),
                    "mean_coverage": mean([r.get("coverage") for r in vals]),
                    "median_reproj_error": median([r.get("reproj_error") for r in vals]),
                    "mean_runtime_sec": mean([r.get("runtime_sec") for r in vals]),
                }
            )


def write_condition_csv(rows, path):
    fieldnames = [
        "group_type",
        "group_value",
        "records",
        "status_counts",
        "homography_available",
        "homography_rate",
        "mean_matches",
        "mean_inliers",
        "median_inlier_ratio",
        "mean_coverage",
        "median_reproj_error",
        "mean_runtime_sec",
    ]
    groups = defaultdict(list)
    for row in rows:
        for key in ["light_condition", "thermal_rendering", "view"]:
            groups[(key, row.get(key, ""))].append(row)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for (group_type, group_value), vals in sorted(groups.items()):
            n = len(vals)
            writer.writerow(
                {
                    "group_type": group_type,
                    "group_value": group_value,
                    "records": n,
                    "status_counts": dict(Counter(r.get("status") for r in vals)),
                    "homography_available": sum(1 for r in vals if r.get("homography_available")),
                    "homography_rate": sum(1 for r in vals if r.get("homography_available")) / max(n, 1),
                    "mean_matches": mean([r.get("matches") for r in vals]),
                    "mean_inliers": mean([r.get("inliers") for r in vals]),
                    "median_inlier_ratio": median([r.get("inlier_ratio") for r in vals]),
                    "mean_coverage": mean([r.get("coverage") for r in vals]),
                    "median_reproj_error": median([r.get("reproj_error") for r in vals]),
                    "mean_runtime_sec": mean([r.get("runtime_sec") for r in vals]),
                }
            )


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset_root", type=pathlib.Path, required=True)
    parser.add_argument("--manifest_path", type=pathlib.Path, required=True)
    parser.add_argument("--output_root", type=pathlib.Path, required=True)
    parser.add_argument("--rift2_root", type=pathlib.Path, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry_run", action="store_true", help="Validate inputs without loading models or creating outputs.")
    return parser.parse_args()


def validate_output_path(output, protected_roots):
    for root in protected_roots:
        root = root.resolve()
        if output == root or output in root.parents or root in output.parents:
            raise ValueError(f"Output must be separate from protected input/source: {root}")


def validate_resume(rows, records, previous, current):
    keys = (
        "dataset_root", "manifest_canonical_hash", "rift2_repo_commit",
        "valid_pair_count", "config_name", "max_dim", "rift2_kwargs",
        "lowes_ratio", "mutual", "estimator", "reproj_threshold",
        "opencv_version",
    )
    for key in keys:
        if previous.get(key) != current.get(key):
            raise ValueError(f"Resume configuration differs: {key}")
    expected = {(r["scene_id"], r["pair_id"]) for r in records}
    seen = set()
    for row in rows:
        key = (row.get("scene_id"), row.get("pair_id"))
        if key not in expected or key in seen or row.get("method") != "rift2":
            raise ValueError(f"Foreign or duplicate result identity: {key}")
        seen.add(key)
        for field in ("config_name", "max_dim", "rift2_kwargs", "lowes_ratio", "mutual", "estimator", "reproj_threshold"):
            if row.get(field) != current[field]:
                raise ValueError(f"Result configuration differs: {key}, {field}")


def main():
    global DATA, MANIFEST, OUT, RIFT2_REPO, cv2, np, match_keypoints_nn
    args = parse_args()
    DATA, MANIFEST, OUT, RIFT2_REPO = (
        p.resolve() for p in (args.dataset_root, args.manifest_path, args.output_root, args.rift2_root)
    )
    validate_output_path(OUT, (DATA, pathlib.Path(__file__).resolve().parents[1], RIFT2_REPO))
    if OUT.exists() and (not OUT.is_dir() or (any(OUT.iterdir()) and not args.resume)):
        raise FileExistsError("Use a new output directory, or --resume for the same interrupted run.")
    manifest, records = load_records()
    actual_commit = git_commit(RIFT2_REPO)
    if actual_commit != RIFT2_COMMIT:
        raise ValueError(f"RIFT2 checkout must be at {RIFT2_COMMIT}; found {actual_commit}")
    if args.dry_run:
        print(json.dumps({"pairs": len(records), "scenes": len(manifest["scenes"]),
                          "manifest_canonical_hash": MANIFEST_CANONICAL_HASH,
                          "rift2_repo_commit": actual_commit, "outputs_created": False}))
        return

    import cv2
    import numpy as np
    os.sys.path.insert(0, str(RIFT2_REPO))
    from src.RIFT2 import RIFT2
    from src.matcher_functions import match_keypoints_nn

    result_path = OUT / "results.jsonl"
    rows = existing_rows(result_path)
    done = {(r.get("scene_id"), r.get("pair_id")) for r in rows}
    run_config = {
        "dataset_root": str(DATA),
        "manifest_path": str(MANIFEST),
        "manifest_file_sha256": sha256_file(MANIFEST),
        "manifest_canonical_hash": MANIFEST_CANONICAL_HASH,
        "valid_pair_count": manifest["official_evaluation_split"]["num_valid_pairs"],
        "excluded_pair_count": manifest["official_evaluation_split"]["num_excluded_pairs"],
        "output_root": str(OUT),
        "rift2_repo": str(RIFT2_REPO),
        "rift2_repo_commit": git_commit(RIFT2_REPO),
        "environment_python": os.sys.executable,
        "opencv_version": cv2.__version__,
        "method": "rift2",
        "config_name": CONFIG_NAME,
        "max_dim": MAX_DIM,
        "rift2_kwargs": RIFT2_KWARGS,
        "lowes_ratio": LOWES_RATIO,
        "mutual": MUTUAL,
        "estimator": ESTIMATOR,
        "reproj_threshold": REPROJ_THRESHOLD,
        "total_records": len(records),
        "resumed_records": len(done),
        "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "started_at_unix": time.time(),
    }
    config_path = OUT / "config.json"
    if args.resume:
        if not config_path.is_file():
            raise FileNotFoundError("Resume requires the existing config.json.")
        previous = json.loads(config_path.read_text(encoding="utf-8"))
        validate_resume(rows, records, previous, run_config)
        run_config["started_at"] = previous["started_at"]
        run_config["started_at_unix"] = previous["started_at_unix"]
    OUT.mkdir(parents=True, exist_ok=True)
    if not args.resume:
        with config_path.open("x", encoding="utf-8") as f:
            json.dump(run_config, f, indent=2)
    model = RIFT2(**RIFT2_KWARGS)
    mode = "a" if result_path.exists() else "w"
    with result_path.open(mode, encoding="utf-8") as f:
        for i, record in enumerate(records, 1):
            key = (record["scene_id"], record["pair_id"])
            if key in done:
                continue
            row = run_one(model, record, i, len(records))
            rows.append(row)
            done.add(key)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            print(
                json.dumps(
                    {
                        "index": i,
                        "total": len(records),
                        "done": len(done),
                        "scene_id": row["scene_id"],
                        "pair_id": row["pair_id"],
                        "status": row.get("status"),
                        "matches": row.get("matches"),
                        "inliers": row.get("inliers"),
                        "runtime_sec": row.get("runtime_sec"),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    summary = summarize(rows, run_config, manifest)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_scene_csv(rows, OUT / "per_scene_summary.csv")
    write_condition_csv(rows, OUT / "condition_summary.csv")
    print("SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
