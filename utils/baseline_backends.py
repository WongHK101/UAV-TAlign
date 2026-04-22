from __future__ import annotations

import sys
from contextlib import nullcontext
from pathlib import Path
from typing import Dict

import cv2
import numpy as np
import torch
from PIL import Image

from utils.minima_bridge import MinimaMatcherBridge
from utils.minima_match_utils import compute_match_spatial_coverage, estimate_homography_ransac


def _append_sys_path(path: Path) -> None:
    path_str = str(path.resolve())
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def _repo_root(repo_root: str | Path | None) -> Path:
    return Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[1]


def _pil_rgb(path: str | Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGB")


def _gray_u8(path: str | Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L")).copy()


def _confidence_array(length: int, fill: float = 1.0) -> np.ndarray:
    return np.full((int(length),), float(fill), dtype=np.float32)


def _prepare_gray_match_input(
    path: str | Path,
    device: torch.device,
    match_max_dim: int = 0,
) -> Dict[str, object]:
    gray = _gray_u8(path)
    original_height, original_width = gray.shape[:2]
    match_height, match_width = original_height, original_width
    resized_for_matching = False

    if int(match_max_dim) > 0 and max(original_height, original_width) > int(match_max_dim):
        scale = float(match_max_dim) / float(max(original_height, original_width))
        match_width = max(1, int(round(original_width * scale)))
        match_height = max(1, int(round(original_height * scale)))
        interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        gray = cv2.resize(gray, (match_width, match_height), interpolation=interpolation)
        resized_for_matching = True

    tensor = torch.from_numpy(gray.copy()).float()[None][None] / 255.0
    return {
        "tensor": tensor.to(device),
        "original_size": (int(original_width), int(original_height)),
        "match_size": (int(match_width), int(match_height)),
        "scale_to_original": (
            float(original_width) / float(match_width),
            float(original_height) / float(match_height),
        ),
        "resized_for_matching": bool(resized_for_matching),
    }


class OpenCVFeatureMatcher:
    def __init__(self, detector_name: str):
        self.detector_name = str(detector_name).strip().lower()
        if self.detector_name == "sift":
            self.detector = cv2.SIFT_create()
            self.norm = cv2.NORM_L2
            self.ratio = 0.75
        elif self.detector_name == "akaze":
            self.detector = cv2.AKAZE_create()
            self.norm = cv2.NORM_HAMMING
            self.ratio = 0.80
        else:
            raise ValueError(f"Unsupported OpenCV feature matcher: {detector_name}")

    def match(self, rgb_path: str | Path, thermal_path: str | Path) -> Dict[str, object]:
        rgb = _gray_u8(rgb_path)
        thermal = _gray_u8(thermal_path)
        kpts_rgb, desc_rgb = self.detector.detectAndCompute(rgb, None)
        kpts_thermal, desc_thermal = self.detector.detectAndCompute(thermal, None)
        if desc_rgb is None or desc_thermal is None or len(kpts_rgb) == 0 or len(kpts_thermal) == 0:
            return {
                "mkpts0": np.zeros((0, 2), dtype=np.float32),
                "mkpts1": np.zeros((0, 2), dtype=np.float32),
                "mconf": np.zeros((0,), dtype=np.float32),
                "success": False,
                "backend": self.detector_name,
                "debug": {
                    "num_keypoints_rgb": int(len(kpts_rgb)),
                    "num_keypoints_thermal": int(len(kpts_thermal)),
                },
            }

        matcher = cv2.BFMatcher(self.norm, crossCheck=False)
        raw_matches = matcher.knnMatch(desc_thermal, desc_rgb, k=2)
        good = []
        for pair in raw_matches:
            if len(pair) < 2:
                continue
            first, second = pair
            if first.distance < self.ratio * second.distance:
                good.append(first)

        mkpts0 = np.asarray([kpts_rgb[m.trainIdx].pt for m in good], dtype=np.float32).reshape(-1, 2)
        mkpts1 = np.asarray([kpts_thermal[m.queryIdx].pt for m in good], dtype=np.float32).reshape(-1, 2)
        return {
            "mkpts0": mkpts0,
            "mkpts1": mkpts1,
            "mconf": _confidence_array(len(good)),
            "success": bool(len(good) > 0),
            "backend": self.detector_name,
            "debug": {
                "num_keypoints_rgb": int(len(kpts_rgb)),
                "num_keypoints_thermal": int(len(kpts_thermal)),
                "num_good_matches": int(len(good)),
            },
        }


class KorniaLoFTRMatcher:
    def __init__(self, device: str = "cpu", match_max_dim: int = 0, use_amp: bool = False):
        from kornia.feature import LoFTR

        self.device = torch.device(device)
        self.match_max_dim = int(match_max_dim)
        self.use_amp = bool(use_amp) and self.device.type == "cuda"
        self.matcher = LoFTR(pretrained="outdoor").eval().to(self.device)

    def match(self, rgb_path: str | Path, thermal_path: str | Path) -> Dict[str, object]:
        rgb_input = _prepare_gray_match_input(rgb_path, self.device, self.match_max_dim)
        thermal_input = _prepare_gray_match_input(thermal_path, self.device, self.match_max_dim)
        batch = {
            "image0": rgb_input["tensor"],
            "image1": thermal_input["tensor"],
        }
        autocast_context = (
            torch.autocast(device_type="cuda", dtype=torch.float16, enabled=True)
            if self.use_amp
            else nullcontext()
        )
        with torch.inference_mode():
            with autocast_context:
                output = self.matcher(batch)
        if not isinstance(output, dict):
            output = batch
        mkpts0 = output.get("keypoints0", output.get("mkpts0_f"))
        mkpts1 = output.get("keypoints1", output.get("mkpts1_f"))
        mconf = output.get("confidence", output.get("mconf_f"))
        if mkpts0 is None or mkpts1 is None:
            mkpts0_np = np.zeros((0, 2), dtype=np.float32)
            mkpts1_np = np.zeros((0, 2), dtype=np.float32)
            conf_np = np.zeros((0,), dtype=np.float32)
        else:
            mkpts0_np = np.asarray(mkpts0.detach().cpu().numpy(), dtype=np.float32).reshape(-1, 2)
            mkpts1_np = np.asarray(mkpts1.detach().cpu().numpy(), dtype=np.float32).reshape(-1, 2)
            if mconf is None:
                conf_np = _confidence_array(len(mkpts0_np))
            else:
                conf_np = np.asarray(mconf.detach().cpu().numpy(), dtype=np.float32).reshape(-1)
        if mkpts0_np.size:
            mkpts0_np[:, 0] *= float(rgb_input["scale_to_original"][0])
            mkpts0_np[:, 1] *= float(rgb_input["scale_to_original"][1])
        if mkpts1_np.size:
            mkpts1_np[:, 0] *= float(thermal_input["scale_to_original"][0])
            mkpts1_np[:, 1] *= float(thermal_input["scale_to_original"][1])
        return {
            "mkpts0": mkpts0_np,
            "mkpts1": mkpts1_np,
            "mconf": conf_np,
            "success": bool(mkpts0_np.shape[0] > 0),
            "backend": "loftr_outdoor",
            "debug": {
                "device": str(self.device),
                "match_max_dim": int(self.match_max_dim),
                "use_amp": bool(self.use_amp),
                "rgb": {
                    "original_size": list(rgb_input["original_size"]),
                    "match_size": list(rgb_input["match_size"]),
                    "resized_for_matching": bool(rgb_input["resized_for_matching"]),
                },
                "thermal": {
                    "original_size": list(thermal_input["original_size"]),
                    "match_size": list(thermal_input["match_size"]),
                    "resized_for_matching": bool(thermal_input["resized_for_matching"]),
                },
            },
        }


class RoMaOfficialMatcher:
    def __init__(self, repo_root: str | Path | None = None, device: str = "cpu", sample_count: int = 10000):
        root = _repo_root(repo_root)
        roma_root = root / "third_party" / "MINIMA" / "third_party" / "RoMa_minima"
        _append_sys_path(roma_root)
        from romatch import roma_outdoor

        self.device = torch.device(device)
        self.sample_count = int(sample_count)
        self.model = roma_outdoor(device=self.device)

    def match(self, rgb_path: str | Path, thermal_path: str | Path) -> Dict[str, object]:
        band_image = _pil_rgb(thermal_path)
        rgb_image = _pil_rgb(rgb_path)
        width_band, height_band = band_image.size
        width_rgb, height_rgb = rgb_image.size
        with torch.inference_mode():
            warp, certainty = self.model.match(band_image, rgb_image, device=self.device)
            matches, sample_certainty = self.model.sample(warp, certainty, num=self.sample_count)
            mkpts_band, mkpts_rgb = self.model.to_pixel_coordinates(
                matches,
                height_band,
                width_band,
                height_rgb,
                width_rgb,
            )
        mkpts0 = np.asarray(mkpts_rgb.detach().cpu().numpy(), dtype=np.float32).reshape(-1, 2)
        mkpts1 = np.asarray(mkpts_band.detach().cpu().numpy(), dtype=np.float32).reshape(-1, 2)
        mconf = np.asarray(sample_certainty.detach().cpu().numpy(), dtype=np.float32).reshape(-1)
        return {
            "mkpts0": mkpts0,
            "mkpts1": mkpts1,
            "mconf": mconf,
            "success": bool(mkpts0.shape[0] > 0),
            "backend": "roma_outdoor",
            "debug": {"device": str(self.device), "sample_count": int(self.sample_count)},
        }


class OfficialXoFTRMatcher:
    def __init__(
        self,
        repo_root: str | Path | None = None,
        device: str = "cpu",
        ckpt: str | Path = "",
        match_threshold: float = 0.3,
        fine_threshold: float = 0.1,
        match_max_dim: int = 1600,
    ):
        root = _repo_root(repo_root)
        minima_root = root / "third_party" / "MINIMA"
        self.bridge = MinimaMatcherBridge(
            backend="xoftr",
            minima_root=minima_root,
            device=device,
            ckpt=str(ckpt).strip(),
            match_threshold=match_threshold,
            fine_threshold=fine_threshold,
            match_max_dim=match_max_dim,
        )

    def match(self, rgb_path: str | Path, thermal_path: str | Path) -> Dict[str, object]:
        result = self.bridge.match(rgb_path, thermal_path)
        result["backend"] = "xoftr_official"
        return result


class RawMinimaMatcher:
    def __init__(
        self,
        repo_root: str | Path | None = None,
        device: str = "cpu",
        minima_method: str = "roma",
        ckpt: str | Path = "",
        match_threshold: float = 0.3,
        fine_threshold: float = 0.1,
        match_max_dim: int = 1600,
    ):
        root = _repo_root(repo_root)
        minima_root = root / "third_party" / "MINIMA"
        self.minima_method = str(minima_method).strip().lower()
        self.bridge = MinimaMatcherBridge(
            backend=self.minima_method,
            minima_root=minima_root,
            device=device,
            ckpt=str(ckpt).strip(),
            match_threshold=match_threshold,
            fine_threshold=fine_threshold,
            match_max_dim=match_max_dim,
        )

    def match(self, rgb_path: str | Path, thermal_path: str | Path) -> Dict[str, object]:
        result = self.bridge.match(rgb_path, thermal_path)
        result["backend"] = f"raw_minima_{self.minima_method}"
        return result


def create_pairwise_matcher(
    method: str,
    repo_root: str | Path | None = None,
    device: str = "cpu",
    official_xoftr_ckpt: str | Path = "",
    raw_minima_method: str = "roma",
    raw_minima_ckpt: str | Path = "",
    loftr_match_max_dim: int = 0,
    loftr_use_amp: bool = False,
) -> object:
    method_name = str(method).strip().lower()
    if method_name == "sift_ransac":
        return OpenCVFeatureMatcher("sift")
    if method_name == "akaze_ransac":
        return OpenCVFeatureMatcher("akaze")
    if method_name == "loftr_outdoor":
        return KorniaLoFTRMatcher(
            device=device,
            match_max_dim=loftr_match_max_dim,
            use_amp=loftr_use_amp,
        )
    if method_name == "roma_outdoor":
        return RoMaOfficialMatcher(repo_root=repo_root, device=device)
    if method_name == "xoftr_official":
        return OfficialXoFTRMatcher(repo_root=repo_root, device=device, ckpt=official_xoftr_ckpt)
    if method_name == "raw_minima":
        return RawMinimaMatcher(
            repo_root=repo_root,
            device=device,
            minima_method=raw_minima_method,
            ckpt=raw_minima_ckpt,
        )
    raise ValueError(f"Unsupported pairwise smoke-test method: {method}")


def run_pairwise_registration(
    method: str,
    matcher: object,
    rgb_path: str | Path,
    thermal_path: str | Path,
    scene_id: str,
    scene_name: str,
    pair_id: str,
    ransac_method: str = "usac_magsac",
    ransac_thresh: float = 3.0,
    ransac_confidence: float = 0.999,
    ransac_max_iters: int = 10000,
    coverage_grid: int = 4,
) -> Dict[str, object]:
    try:
        match_result = matcher.match(rgb_path, thermal_path)
    except Exception as exc:
        return {
            "method": method,
            "scene_id": scene_id,
            "scene_name": scene_name,
            "pair_id": pair_id,
            "status": "error",
            "num_matches": 0,
            "num_inliers": 0,
            "inlier_ratio": 0.0,
            "reprojection_error": None,
            "coverage": 0.0,
            "homography_available": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }

    mkpts0 = np.asarray(match_result.get("mkpts0", np.zeros((0, 2), dtype=np.float32)), dtype=np.float32).reshape(-1, 2)
    mkpts1 = np.asarray(match_result.get("mkpts1", np.zeros((0, 2), dtype=np.float32)), dtype=np.float32).reshape(-1, 2)
    mconf = np.asarray(match_result.get("mconf", _confidence_array(mkpts0.shape[0])), dtype=np.float32).reshape(-1)

    thermal_height, thermal_width = _gray_u8(thermal_path).shape[:2]
    coverage = compute_match_spatial_coverage(mkpts1, image_shape=(thermal_height, thermal_width), grid_size=coverage_grid)

    if mkpts0.shape[0] == 0:
        status = "no_matches"
        homography = None
        stats = {
            "num_matches": 0,
            "num_inliers": 0,
            "inlier_ratio": 0.0,
            "reproj_error": None,
        }
    else:
        h_stats = estimate_homography_ransac(
            mkpts0,
            mkpts1,
            method=ransac_method,
            ransac_thresh=ransac_thresh,
            confidence=ransac_confidence,
            max_iters=ransac_max_iters,
        )
        homography = h_stats.get("H") if bool(h_stats.get("success", False)) else None
        status = "ok" if homography is not None else ("fit_failed" if mkpts0.shape[0] >= 4 else "insufficient_matches")
        stats = {
            "num_matches": int(mkpts0.shape[0]),
            "num_inliers": int(h_stats.get("num_inliers", 0)),
            "inlier_ratio": float(h_stats.get("inlier_ratio", 0.0)),
            "reproj_error": None if not np.isfinite(float(h_stats.get("reproj_error", np.nan))) else float(h_stats.get("reproj_error")),
        }

    return {
        "method": method,
        "scene_id": scene_id,
        "scene_name": scene_name,
        "pair_id": pair_id,
        "status": status,
        "num_matches": int(stats["num_matches"]),
        "num_inliers": int(stats["num_inliers"]),
        "inlier_ratio": float(stats["inlier_ratio"]),
        "reprojection_error": stats["reproj_error"],
        "coverage": float(coverage),
        "homography_available": homography is not None,
        "homography": None if homography is None else np.asarray(homography, dtype=np.float64).tolist(),
        "confidence_mean": None if mconf.size == 0 else float(np.mean(mconf)),
        "backend": str(match_result.get("backend", method)),
        "debug": match_result.get("debug", {}),
    }
