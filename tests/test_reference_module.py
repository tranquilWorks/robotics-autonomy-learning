from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReferenceModuleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((ROOT / "curriculum/modules.json").read_text(encoding="utf-8"))
        cls.module = manifest["modules"][0]
        cls.folder = ROOT / cls.module["folder"]

    def test_reference_slice_is_complete_and_concept_first(self):
        self.assertEqual(self.module["id"], "P01")
        self.assertEqual(self.module["status"], "implemented")
        for name in ("README.md", "lesson.m", "model.m", "experiment.m", "interactive.m", "lesson.md", "walkthrough.md", "checks.md", "run_checks.m"):
            self.assertTrue((self.folder / name).is_file(), name)
        experiment = (self.folder / "experiment.m").read_text(encoding="utf-8").lower()
        self.assertGreaterEqual(experiment.count("sweep"), 2)
        self.assertIn("broken", experiment)
        self.assertIn("assert", experiment)

    def test_reference_checks_cover_independent_invariants(self):
        checks = (self.folder / "run_checks.m").read_text(encoding="utf-8")
        self.assertGreaterEqual(checks.count("assert("), 3)
        self.assertIn("P01 checks passed", checks)


if __name__ == "__main__":
    unittest.main()
