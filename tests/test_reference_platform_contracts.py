from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "reference-platform"
sys.path.insert(0, str(REFERENCE_ROOT))

from reference_platform import (  # noqa: E402
    CANONICALIZATION_ID,
    CANONICALIZATION_SERIALIZATION,
    CONTRACT_FAMILY,
    CONTRACT_VERSION,
    ContractError,
    validate_schema_catalog,
)


class ReferencePlatformContractTests(unittest.TestCase):
    def test_exact_v1_schema_inventory_and_identity(self):
        catalog = validate_schema_catalog(ROOT / "contracts" / "reference-platform")
        expected_types = {
            "configuration",
            "hardware_inventory",
            "plant_model",
            "experiment",
            "run_authorization",
            "telemetry_event",
            "result",
            "evidence",
        }
        self.assertEqual(catalog["contract_version"], CONTRACT_VERSION)
        self.assertEqual(catalog["contract_family"], CONTRACT_FAMILY)
        self.assertEqual(catalog["canonicalization"]["id"], CANONICALIZATION_ID)
        self.assertEqual(catalog["canonicalization"]["serialization"], CANONICALIZATION_SERIALIZATION)
        self.assertEqual({entry["contract_type"] for entry in catalog["contracts"]}, expected_types)
        self.assertEqual(len(catalog["contracts"]), 8)
        for entry in catalog["contracts"]:
            schema = json.loads((ROOT / "contracts" / "reference-platform" / entry["path"]).read_text(encoding="utf-8"))
            with self.subTest(contract_type=entry["contract_type"]):
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["$id"], entry["schema_id"])
                self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
                self.assertEqual(schema["properties"]["contract_version"]["const"], CONTRACT_VERSION)
                self.assertEqual(schema["properties"]["contract_type"]["const"], entry["contract_type"])
                self.assertFalse(schema["additionalProperties"])

    def test_compatibility_record_is_explicit_and_not_a_release_claim(self):
        record = json.loads((ROOT / "contracts" / "reference-platform" / "compatibility.json").read_text(encoding="utf-8"))
        self.assertEqual(record["contract_version"], CONTRACT_VERSION)
        self.assertEqual(record["canonicalization"], CANONICALIZATION_ID)
        self.assertEqual(
            {consumer["repository"] for consumer in record["consumer_records"]},
            {"controls-gnc-learning", "tranquility-te"},
        )
        self.assertTrue(
            all(
                consumer["adoption_status"] in {"not_started", "in_progress", "adopted", "rejected"}
                for consumer in record["consumer_records"]
            )
        )
        approved_revision = record["approved_contract_revision"]
        if approved_revision is None:
            self.assertTrue(all(consumer["adoption_status"] == "not_started" for consumer in record["consumer_records"]))
            self.assertTrue(all(consumer["contract_version"] is None for consumer in record["consumer_records"]))
        else:
            self.assertRegex(approved_revision, r"^[0-9a-f]{40}$")
            for consumer in record["consumer_records"]:
                if consumer["adoption_status"] == "adopted":
                    self.assertIsInstance(consumer["contract_version"], str)
        self.assertIn("Unknown versions", record["upgrade_policy"])
        self.assertIn("Restore", record["rollback_policy"])

    def test_schema_catalog_rejects_identity_and_keyword_drift(self):
        source = ROOT / "contracts" / "reference-platform"
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "contracts"
            shutil.copytree(source, copied)
            schema_path = copied / "v1" / "configuration.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["$id"] = "drifted.schema.json"
            schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            with self.assertRaises(ContractError) as caught:
                validate_schema_catalog(copied)
            self.assertEqual(caught.exception.code, "schema.identity")

    def test_schema_catalog_rejects_family_and_serialization_drift(self):
        source = ROOT / "contracts" / "reference-platform"
        mutations = (
            ("contract_family", "wrong.family", "schema.family"),
            ("canonicalization", {"serialization": "implementation-defined"}, "schema.canonicalization"),
        )
        for field, replacement, code in mutations:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                copied = Path(temporary) / "contracts"
                shutil.copytree(source, copied)
                index_path = copied / "contract-index.json"
                index = json.loads(index_path.read_text(encoding="utf-8"))
                if field == "canonicalization":
                    index[field].update(replacement)
                else:
                    index[field] = replacement
                index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                with self.assertRaises(ContractError) as caught:
                    validate_schema_catalog(copied)
                self.assertEqual(caught.exception.code, code)

    def test_permanent_curriculum_identity_is_unchanged_without_freezing_frontier(self):
        manifest = json.loads((ROOT / "curriculum" / "modules.json").read_text(encoding="utf-8"))
        module_fields = (
            "number",
            "id",
            "title",
            "guiding_question",
            "phase",
            "phase_title",
            "slug",
            "folder",
            "implementation_batch",
            "prerequisites",
        )
        projection = {
            key: manifest[key]
            for key in (
                "schema_version",
                "product",
                "title",
                "purpose",
                "module_count",
                "progression_rule",
                "interaction_contract",
            )
        }
        projection["modules"] = [
            {key: module[key] for key in module_fields}
            for module in manifest["modules"]
        ]
        wire = json.dumps(projection, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        self.assertEqual(len(projection["modules"]), 24)
        self.assertEqual([module["id"] for module in projection["modules"]], [f"P{number:02d}" for number in range(1, 25)])
        self.assertEqual(
            hashlib.sha256(wire).hexdigest(),
            "383411ae7670cccd40e1de27d364f2759519f1a688e5456792dcd2dc552b2883",
        )
        self.assertTrue(all("status" not in module and "evidence_level" not in module for module in projection["modules"]))


if __name__ == "__main__":
    unittest.main()
