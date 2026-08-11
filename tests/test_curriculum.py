from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CurriculumTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((ROOT / "curriculum/modules.json").read_text(encoding="utf-8"))

    def test_identity_order_and_frontier(self):
        modules = self.data["modules"]
        self.assertEqual(self.data["module_count"], 24)
        self.assertEqual([m["number"] for m in modules], list(range(1, 25)))
        self.assertEqual([m["id"] for m in modules], [f"P{i:02d}" for i in range(1, 25)])
        implemented = sum(m["status"] == "implemented" for m in modules)
        self.assertEqual(
            [m["status"] for m in modules],
            ["implemented"] * implemented + ["scaffolded"] * (24 - implemented),
        )

    def test_prerequisites_are_earlier_and_questions_are_concrete(self):
        positions = {m["id"]: index for index, m in enumerate(self.data["modules"])}
        for index, module in enumerate(self.data["modules"]):
            with self.subTest(module=module["id"]):
                self.assertTrue(module["guiding_question"].endswith("?"))
                self.assertNotIn("What changes in the observable system behavior", module["guiding_question"])
                self.assertGreaterEqual(len(module["guiding_question"]), 24)
                for prerequisite in module["prerequisites"]:
                    self.assertIn(prerequisite, positions)
                    self.assertLess(positions[prerequisite], index)

    def test_artifact_state_is_honest(self):
        base = {"README.md", "lesson.m", "experiment.m", "lesson.md", "walkthrough.md", "checks.md"}
        rich = {"model.m", "interactive.m", "run_checks.m"}
        for module in self.data["modules"]:
            folder = ROOT / module["folder"]
            names = {path.name for path in folder.iterdir() if path.is_file()}
            with self.subTest(module=module["id"]):
                self.assertTrue(base <= names)
                experiment = (folder / "experiment.m").read_text(encoding="utf-8").lower()
                if module["status"] == "implemented":
                    self.assertTrue(rich <= names)
                    for marker in ("%%", "sweep", "broken"):
                        self.assertIn(marker, experiment)
                else:
                    self.assertFalse(rich & names)
                    self.assertIn("scaffolded", experiment)
                    self.assertIn("error(", experiment)

    def test_learning_cycle_is_explicit(self):
        self.assertEqual(
            self.data["interaction_contract"]["learning_cycle"],
            ["read", "visualize-baseline", "move-one-lever", "visualize-delta", "read-and-explain"],
        )


if __name__ == "__main__":
    unittest.main()
