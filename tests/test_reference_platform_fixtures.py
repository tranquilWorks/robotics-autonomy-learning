from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "reference-platform"
FIXTURES = REFERENCE_ROOT / "fixtures"
sys.path.insert(0, str(REFERENCE_ROOT))

from generate_fixtures import generate  # noqa: E402
from reference_platform import (  # noqa: E402
    ContractError,
    canonical_bytes,
    configuration_digest,
    load_json,
    load_json_bytes,
    validate_contract_set,
)
from reference_platform.contracts import (  # noqa: E402
    MAX_ARRAY_ITEMS,
    MAX_DEPTH,
    MAX_DOCUMENT_BYTES,
    MAX_STRING_CHARS,
    sha256_digest,
)


class ReferencePlatformFixtureTests(unittest.TestCase):
    RP01_FIXTURE_NAMES = (
        "drawbot-2r.json",
        "passive-multilink.json",
        "pendubot-2link.json",
        "pnp-single-head.json",
        "rotary-pendulum-1.json",
    )

    @classmethod
    def setUpClass(cls):
        cls.valid_paths = [FIXTURES / "valid" / name for name in cls.RP01_FIXTURE_NAMES]
        cls.expected_hashes = load_json(FIXTURES / "canonical-hashes.json")["configuration_hashes"]

    def load_drawbot(self):
        return load_json(FIXTURES / "valid" / "drawbot-2r.json")

    @staticmethod
    def repair_artifact_links(fixture):
        fixture["result"]["raw_telemetry_artifact"]["sha256"] = sha256_digest(fixture["telemetry_events"])
        fixture["result"]["metric_artifact"]["sha256"] = sha256_digest(fixture["result"]["acceptance_map"])
        fixture["evidence"]["artifacts"][1]["sha256"] = sha256_digest(fixture["result"])

    @staticmethod
    def terminal_record(template, sequence, event_type, state="failed"):
        record = deepcopy(template)
        record["record_id"] = f"ral.record.lifecycle.{sequence}"
        record["sequence"] = sequence
        record["timestamp"] = f"2026-08-31T00:00:0{sequence}Z"
        record["monotonic_offset_ns"] = sequence * 1_000_000
        record["record_kind"] = "event"
        record["lifecycle_state"] = state
        record["event_type"] = event_type
        record["payload"] = {"validation_level": "static"} if event_type == "completed" else {"retained": True}
        return record

    def test_five_valid_configuration_bundles_roundtrip_with_golden_hashes(self):
        self.assertEqual(len(self.valid_paths), 5)
        self.assertTrue(all(path.is_file() for path in self.valid_paths))
        observed = set()
        for path in self.valid_paths:
            fixture = load_json(path)
            before = canonical_bytes(fixture)
            with self.subTest(path=path.name):
                self.assertIs(validate_contract_set(fixture), fixture)
                self.assertEqual(canonical_bytes(fixture), before)
                kind = fixture["configuration"]["configuration_kind"]
                observed.add(kind)
                self.assertEqual(configuration_digest(fixture["configuration"]), self.expected_hashes[kind])
                reordered = json.loads(json.dumps(fixture, sort_keys=False))
                self.assertEqual(canonical_bytes(reordered), before)
                self.assertFalse(before.endswith(b"\n"))
        self.assertEqual(
            observed,
            {"drawbot_2r", "passive_multilink", "pendubot_2link", "pnp_single_head", "rotary_pendulum_1"},
        )
        self.assertTrue(observed <= set(self.expected_hashes))

    def test_semantic_configuration_change_changes_digest(self):
        fixture = self.load_drawbot()
        original = configuration_digest(fixture["configuration"])
        fixture["configuration"]["mechanical_revision"] = "ral.mechanical.proposal-r2"
        self.assertNotEqual(configuration_digest(fixture["configuration"]), original)

    def test_canonical_number_and_key_spelling_is_explicit(self):
        self.assertEqual(
            canonical_bytes({"z": 1e-6, "b": 10.0, "a": -0.0, "flag": True}),
            b'{"a":0,"b":10,"flag":true,"z":1e-6}',
        )

    def test_canonical_string_escaping_unicode_and_positive_exponent_are_explicit(self):
        self.assertEqual(
            canonical_bytes(
                {
                    "unicode": "café/雪",
                    "control": "\b\t\n\f\r\u0001",
                    "quote": "\"\\",
                    "positive": 1e21,
                }
            ),
            b'{"control":"\\b\\t\\n\\f\\r\\u0001","positive":1e21,"quote":"\\"\\\\","unicode":"caf\xc3\xa9/\xe9\x9b\xaa"}',
        )

    def test_every_retained_invalid_fixture_has_one_expected_rejection(self):
        expected = load_json(FIXTURES / "invalid" / "expected-errors.json")
        self.assertGreaterEqual(len(expected), 14)
        for name, code in sorted(expected.items()):
            with self.subTest(name=name):
                with self.assertRaises(ContractError) as caught:
                    validate_contract_set(load_json(FIXTURES / "invalid" / name))
                self.assertEqual(caught.exception.code, code)

    def test_malformed_duplicate_nonfinite_and_nonobject_inputs_are_rejected(self):
        cases = {
            "malformed-trailing-comma.json.txt": "json.malformed",
            "duplicate-key.json.txt": "json.duplicate_key",
            "non-finite.json.txt": "json.non_finite",
            "invalid-utf8.json.bin": "json.utf8",
        }
        for name, code in cases.items():
            with self.subTest(name=name):
                with self.assertRaises(ContractError) as caught:
                    load_json(FIXTURES / "invalid" / name)
                self.assertEqual(caught.exception.code, code)
        with self.assertRaises(ContractError) as caught:
            validate_contract_set(load_json(FIXTURES / "invalid" / "top-level-array.json.txt"))
        self.assertEqual(caught.exception.code, "document.root")

    def test_cancellation_and_timeout_preserve_partial_artifact_records(self):
        for reason, first_event in (("cancelled", "cancel_requested"), ("timeout", "timeout_detected")):
            fixture = self.load_drawbot()
            prefix = fixture["telemetry_events"][:3]
            template = prefix[-1]
            fixture["telemetry_events"] = prefix + [
                self.terminal_record(template, 3, first_event),
                self.terminal_record(template, 4, "partial_artifacts_preserved"),
            ]
            fixture["result"]["termination_reason"] = reason
            fixture["result"]["stop_timestamp"] = "2026-08-31T00:00:04Z"
            fixture["result"]["partial_artifacts_preserved"] = True
            self.repair_artifact_links(fixture)
            with self.subTest(reason=reason):
                validate_contract_set(fixture)
                fixture["telemetry_events"].pop()
                self.repair_artifact_links(fixture)
                with self.assertRaises(ContractError) as caught:
                    validate_contract_set(fixture)
                self.assertEqual(caught.exception.code, f"lifecycle.{reason if reason == 'timeout' else 'cancellation'}")

    def test_restart_recovery_requires_predecessor_and_new_authorization(self):
        fixture = self.load_drawbot()
        prefix = fixture["telemetry_events"][:3]
        template = prefix[-1]
        fixture["telemetry_events"] = prefix + [
            self.terminal_record(template, 3, "restart_detected"),
            self.terminal_record(template, 4, "authorization_invalidated"),
            self.terminal_record(template, 5, "completed", state="completed"),
        ]
        fixture["result"]["stop_timestamp"] = "2026-08-31T00:00:05Z"
        fixture["result"]["recovery"] = {
            "restart_detected": True,
            "prior_result_id": "ral.result.drawbot_2r.pre-restart-r1",
            "new_authorization_required": True,
        }
        self.repair_artifact_links(fixture)
        validate_contract_set(fixture)
        fixture["result"]["recovery"]["prior_result_id"] = None
        self.repair_artifact_links(fixture)
        with self.assertRaises(ContractError) as caught:
            validate_contract_set(fixture)
        self.assertEqual(caught.exception.code, "lifecycle.recovery")

    def test_rejection_is_isolated_and_a_valid_fixture_recovers(self):
        valid = self.load_drawbot()
        invalid = deepcopy(valid)
        invalid["experiment"]["sample_rate_hz"] = True
        snapshot = canonical_bytes(valid)
        with self.assertRaises(ContractError) as caught:
            validate_contract_set(invalid)
        self.assertEqual(caught.exception.code, "field.type")
        validate_contract_set(valid)
        validate_contract_set(valid)
        self.assertEqual(canonical_bytes(valid), snapshot)

    def test_canonical_backup_restore_and_v1_rollback_smoke(self):
        valid = self.load_drawbot()
        restored = load_json_bytes(canonical_bytes(valid), source="restored-v1-fixture")
        validate_contract_set(restored)
        self.assertEqual(configuration_digest(restored["configuration"]), configuration_digest(valid["configuration"]))

        unsupported = load_json(FIXTURES / "invalid" / "unsupported-contract-version.json")
        with self.assertRaises(ContractError) as caught:
            validate_contract_set(unsupported)
        self.assertEqual(caught.exception.code, "version.unsupported")
        validate_contract_set(restored)

    def test_parser_resource_bounds(self):
        with self.assertRaises(ContractError) as caught:
            load_json_bytes(b" " * (MAX_DOCUMENT_BYTES + 1))
        self.assertEqual(caught.exception.code, "resource.document_bytes")

        nested = None
        for _ in range(MAX_DEPTH + 1):
            nested = {"nested": nested}
        with self.assertRaises(ContractError) as caught:
            canonical_bytes(nested)
        self.assertEqual(caught.exception.code, "resource.depth")

        with self.assertRaises(ContractError) as caught:
            canonical_bytes(list(range(MAX_ARRAY_ITEMS + 1)))
        self.assertEqual(caught.exception.code, "resource.array")

        with self.assertRaises(ContractError) as caught:
            canonical_bytes("x" * (MAX_STRING_CHARS + 1))
        self.assertEqual(caught.exception.code, "resource.string")

        oversized_integer = ('{"value":' + "9" * 4_301 + "}").encode("utf-8")
        with self.assertRaises(ContractError) as caught:
            load_json_bytes(oversized_integer)
        self.assertEqual(caught.exception.code, "resource.number")

        with self.assertRaises(ContractError) as caught:
            load_json_bytes(b'{"value":"\\ud800"}')
        self.assertEqual(caught.exception.code, "json.unicode_scalar")

        with self.assertRaises(ContractError) as caught:
            canonical_bytes(10**128)
        self.assertEqual(caught.exception.code, "resource.number")

        fixture = self.load_drawbot()
        fixture["experiment"]["sample_rate_hz"] = 10**309
        with self.assertRaises(ContractError) as caught:
            validate_contract_set(fixture)
        self.assertEqual(caught.exception.code, "resource.number")

    def test_generator_is_reproducible_and_isolated_to_requested_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixtures"
            generate(output)
            retained = {
                path.relative_to(FIXTURES): path.read_bytes()
                for path in FIXTURES.rglob("*")
                if path.is_file()
            }
            regenerated = {
                path.relative_to(output): path.read_bytes()
                for path in output.rglob("*")
                if path.is_file()
            }
            self.assertEqual(regenerated, retained)

    def test_generator_rejects_symlink_escape_without_overwriting_targets(self):
        for link_kind in ("root", "directory", "file"):
            with self.subTest(link_kind=link_kind), tempfile.TemporaryDirectory() as temporary:
                temporary_root = Path(temporary)
                output = temporary_root / "fixtures"
                if link_kind == "root":
                    outside = temporary_root / "outside"
                    outside.mkdir()
                    output.symlink_to(outside, target_is_directory=True)
                else:
                    output.mkdir()
                if link_kind == "file":
                    (output / "valid").mkdir()
                    outside = temporary_root / "outside.json"
                    outside.write_text("sentinel\n", encoding="utf-8")
                    (output / "valid" / "drawbot-2r.json").symlink_to(outside)
                    expected = {outside: b"sentinel\n"}
                elif link_kind == "directory":
                    outside = temporary_root / "outside"
                    outside.mkdir()
                    (output / "valid").symlink_to(outside, target_is_directory=True)
                    expected = {}
                else:
                    expected = {}

                with self.assertRaises(ContractError) as caught:
                    generate(output)

                self.assertEqual(caught.exception.code, "path.symlink")
                if link_kind == "file":
                    self.assertEqual(outside.read_bytes(), expected[outside])
                else:
                    self.assertEqual(list(outside.iterdir()), [])

    def test_cli_is_cwd_independent_and_bounded_by_a_process_timeout(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run(
                [sys.executable, str(REFERENCE_ROOT / "validate.py"), "check-all"],
                cwd=temporary,
                text=True,
                capture_output=True,
                timeout=10,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"CHECK PASS: 8 schemas, [0-9]+ valid fixtures")


if __name__ == "__main__":
    unittest.main()
