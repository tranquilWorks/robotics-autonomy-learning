from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LearnCliTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            fixture = Path(temporary) / "repo"
            shutil.copytree(ROOT / "bin", fixture / "bin")
            shutil.copytree(ROOT / "curriculum", fixture / "curriculum")
            manifest = json.loads((fixture / "curriculum/modules.json").read_text(encoding="utf-8"))
            for module in manifest["modules"]:
                source = ROOT / module["folder"]
                target = fixture / module["folder"]
                target.mkdir(parents=True, exist_ok=True)
                for name in ("README.md", "lesson.md", "walkthrough.md", "checks.md"):
                    shutil.copy2(source / name, target / name)
            environment = os.environ.copy()
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            return subprocess.run(
                [str(fixture / "bin/learn"), *args],
                cwd=fixture,
                text=True,
                capture_output=True,
                env=environment,
                timeout=10,
            )

    def test_status_and_list(self):
        status = self.run_cli("status")
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("24 total, 1 implemented", status.stdout)
        listing = self.run_cli("list")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        self.assertEqual(len([line for line in listing.stdout.splitlines() if line.strip()]), 24)

    def test_reference_starts_and_scaffold_refuses(self):
        reference = self.run_cli("start", "P01")
        self.assertEqual(reference.returncode, 0, reference.stderr)
        self.assertIn("Guiding question:", reference.stdout)
        scaffold = self.run_cli("start", "P02")
        self.assertEqual(scaffold.returncode, 2)
        self.assertIn("Activate its governed implementation batch", scaffold.stdout)


if __name__ == "__main__":
    unittest.main()
