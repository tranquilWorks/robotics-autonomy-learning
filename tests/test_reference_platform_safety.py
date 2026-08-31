from __future__ import annotations

import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "reference-platform"
sys.path.insert(0, str(REFERENCE_ROOT))

from reference_platform import ContractError, load_json, validate_contract_set  # noqa: E402
from reference_platform.contracts import REQUIRED_EVIDENCE_STATEMENTS  # noqa: E402


class ReferencePlatformSafetyTests(unittest.TestCase):
    RP01_FIXTURE_NAMES = (
        "drawbot-2r.json",
        "passive-multilink.json",
        "pendubot-2link.json",
        "pnp-single-head.json",
        "rotary-pendulum-1.json",
    )

    def test_owned_python_has_no_device_network_credential_or_process_client(self):
        banned_import_roots = {
            "can",
            "cv2",
            "gpiozero",
            "http",
            "keyring",
            "requests",
            "serial",
            "socket",
            "subprocess",
            "urllib",
            "usb",
        }
        sources = sorted(REFERENCE_ROOT.glob("*.py")) + sorted((REFERENCE_ROOT / "reference_platform").glob("*.py"))
        self.assertGreaterEqual(len(sources), 4)
        for path in sources:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module.split(".")[0])
            with self.subTest(path=path.name):
                self.assertFalse(imported & banned_import_roots)

    def test_all_valid_fixtures_withhold_physical_authorization_and_claim_static_only(self):
        for name in self.RP01_FIXTURE_NAMES:
            path = REFERENCE_ROOT / "fixtures" / "valid" / name
            fixture = load_json(path)
            validate_contract_set(fixture)
            authorization = fixture["run_authorization"]
            with self.subTest(path=path.name):
                self.assertEqual(authorization["authorization_status"], "withheld")
                self.assertFalse(authorization["physical_run_authorized"])
                self.assertFalse(authorization["local_presence_confirmed"])
                self.assertEqual(authorization["e_stop_test_result"], "not_run")
                self.assertEqual(fixture["evidence"]["validation_level"], "static")
                self.assertEqual(tuple(fixture["evidence"]["required_statements"]), REQUIRED_EVIDENCE_STATEMENTS)
                self.assertFalse(fixture["result"]["physical_safe_state_claimed"])
                self.assertFalse({"armed", "running", "aborting", "safe"} & {record["lifecycle_state"] for record in fixture["telemetry_events"]})

    def test_pnp_and_multilink_release_gates_remain_closed(self):
        expected = {
            "passive-multilink.json": "G4_MULTILINK",
            "pnp-single-head.json": "G5_PNP_FEASIBILITY",
        }
        for name, gate in expected.items():
            fixture = load_json(REFERENCE_ROOT / "fixtures" / "valid" / name)
            release = fixture["configuration"]["release"]
            self.assertEqual(release, {"status": "gated", "gate_id": gate, "decision_evidence_id": None})
        pnp = load_json(REFERENCE_ROOT / "fixtures" / "valid" / "pnp-single-head.json")
        prohibited = {"0402", "QFN", "BGA", "production_throughput", "unattended_operation"}
        self.assertFalse(prohibited & set(pnp["configuration"]["component_envelope"]))

    def test_loader_rejects_symlinks_and_root_escape(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            inside = root / "inside.json"
            outside = root.parent / f"{root.name}-outside.json"
            inside.write_text("{}\n", encoding="utf-8")
            outside.write_text("{}\n", encoding="utf-8")
            link = root / "link.json"
            link.symlink_to(inside)
            try:
                with self.assertRaises(ContractError) as caught:
                    load_json(link, allowed_root=root)
                self.assertEqual(caught.exception.code, "path.symlink")
                with self.assertRaises(ContractError) as caught:
                    load_json(outside, allowed_root=root)
                self.assertEqual(caught.exception.code, "path.escape")
            finally:
                outside.unlink()

    def test_documented_handoffs_are_separate_and_unperformed(self):
        handoff = (REFERENCE_ROOT / "CROSS_REPOSITORY_HANDOFF.md").read_text(encoding="utf-8")
        compatibility = (REFERENCE_ROOT / "COMPATIBILITY.md").read_text(encoding="utf-8")
        self.assertIn("separate governed intake for `controls-gnc-learning`", handoff)
        self.assertIn("separate governed intake for `tranquility-te`", handoff)
        self.assertIn("TRANQUILITY NOT CONTACTED", handoff)
        self.assertIn("CONTROLS-GNC NOT MODIFIED", handoff)
        self.assertIn("Unknown contract or fixture versions are rejected", compatibility)
        machine_record = json.loads((ROOT / "contracts" / "reference-platform" / "compatibility.json").read_text(encoding="utf-8"))
        if machine_record["approved_contract_revision"] is None:
            self.assertTrue(all(record["adoption_status"] == "not_started" for record in machine_record["consumer_records"]))


if __name__ == "__main__":
    unittest.main()
