"""Release-entry safety tests; no dataset, model, or GPU is required."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


SPEC = importlib.util.spec_from_file_location(
    "rift2_release", Path(__file__).resolve().parents[1] / "scripts/run_rift2_evaluation.py"
)
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class ReleaseSafetyTests(unittest.TestCase):
    def test_protected_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            data = root / "data"
            for output in (data, data / "results", root):
                with self.assertRaises(ValueError):
                    runner.validate_output_path(output, [data])
            runner.validate_output_path(root / "results", [data])

    def test_corrupt_jsonl_is_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text('{"scene_id":"01"}\n{"pair_id":', encoding="utf-8")
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                runner.existing_rows(path)
            self.assertEqual(before, path.read_bytes())

    def test_resume_identity_and_configuration(self):
        config = {"dataset_root": "data", "manifest_canonical_hash": "fixed",
                  "rift2_repo_commit": runner.RIFT2_COMMIT, "valid_pair_count": 6037,
                  "config_name": runner.CONFIG_NAME, "max_dim": runner.MAX_DIM,
                  "rift2_kwargs": runner.RIFT2_KWARGS, "lowes_ratio": runner.LOWES_RATIO,
                  "mutual": False, "estimator": runner.ESTIMATOR,
                  "reproj_threshold": runner.REPROJ_THRESHOLD, "opencv_version": "4.10.0"}
        row = {**config, "method": "rift2", "scene_id": "01", "pair_id": "000001"}
        records = [{"scene_id": "01", "pair_id": "000001"}]
        runner.validate_resume([row], records, config, config)
        with self.assertRaises(ValueError):
            runner.validate_resume([row, row], records, config, config)
        with self.assertRaises(ValueError):
            runner.validate_resume([row], records, config, {**config, "max_dim": 800})
        with self.assertRaises(ValueError):
            runner.validate_resume([{**row, "pair_id": "000002"}], records, config, config)

    def test_frozen_profile(self):
        self.assertEqual(runner.MAX_DIM, 1200)
        self.assertEqual(runner.RIFT2_KWARGS, {"npt": 2000, "patch_size": 64})
        self.assertEqual(runner.LOWES_RATIO, 0.95)
        self.assertEqual(runner.REPROJ_THRESHOLD, 5.0)


if __name__ == "__main__":
    unittest.main()
