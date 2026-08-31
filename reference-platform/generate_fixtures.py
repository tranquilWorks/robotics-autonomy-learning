#!/usr/bin/env python3
"""Generate deterministic RP01 contract fixtures in a chosen local directory."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from reference_platform.contracts import (
    CANONICALIZATION_ID,
    CONTRACT_VERSION,
    ContractError,
    REQUIRED_EVIDENCE_STATEMENTS,
    configuration_digest,
    sha256_digest,
)

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "fixtures"

PROFILES = {
    "drawbot_2r": {
        "active": 2,
        "passive": 0,
        "gravity": "horizontal",
        "tools": ["pen"],
        "components": [],
        "release": {"status": "baseline", "gate_id": None, "decision_evidence_id": None},
        "lengths": [0.24, 0.22],
        "masses": [0.32, 0.24],
        "inertias": [0.0061, 0.0039],
    },
    "rotary_pendulum_1": {
        "active": 1,
        "passive": 1,
        "gravity": "vertical",
        "tools": [],
        "components": [],
        "release": {"status": "baseline", "gate_id": None, "decision_evidence_id": None},
        "lengths": [0.12, 0.24],
        "masses": [0.28, 0.18],
        "inertias": [0.0032, 0.0017],
    },
    "pendubot_2link": {
        "active": 1,
        "passive": 1,
        "gravity": "vertical",
        "tools": [],
        "components": [],
        "release": {"status": "baseline", "gate_id": None, "decision_evidence_id": None},
        "lengths": [0.23, 0.22],
        "masses": [0.31, 0.19],
        "inertias": [0.0058, 0.0021],
    },
    "passive_multilink": {
        "active": 1,
        "passive": 2,
        "gravity": "vertical",
        "tools": [],
        "components": [],
        "release": {"status": "gated", "gate_id": "G4_MULTILINK", "decision_evidence_id": None},
        "lengths": [0.22, 0.2, 0.18],
        "masses": [0.3, 0.17, 0.13],
        "inertias": [0.0054, 0.0018, 0.0011],
    },
    "pnp_single_head": {
        "active": 2,
        "passive": 0,
        "gravity": "horizontal",
        "tools": ["z_theta_vacuum_head"],
        "components": ["0805", "0603", "SOT-23", "SOIC", "TSSOP", "moderate_pitch_QFP", "connectors"],
        "release": {"status": "gated", "gate_id": "G5_PNP_FEASIBILITY", "decision_evidence_id": None},
        "lengths": [0.24, 0.22],
        "masses": [0.37, 0.29],
        "inertias": [0.0073, 0.0048],
    },
}


def _state_limits(joint_count: int, *, scale: float = 1.0) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for joint in range(1, joint_count + 1):
        records.extend(
            [
                {"state": f"joint_{joint}_position_rad", "minimum": -3.0 * scale, "maximum": 3.0 * scale, "unit": "rad"},
                {"state": f"joint_{joint}_velocity_rad_s", "minimum": -4.0 * scale, "maximum": 4.0 * scale, "unit": "rad_s"},
            ]
        )
    return records


def _current_limits(active_joints: int, maximum: float) -> list[dict[str, Any]]:
    return [{"joint_id": f"joint_{joint}", "max_abs_a": maximum} for joint in range(1, active_joints + 1)]


def _artifact(uri: str, digest: str, availability: str = "embedded") -> dict[str, Any]:
    return {
        "uri": uri,
        "sha256": digest,
        "availability": availability,
        "evidence_level": "static",
    }


def build_fixture(kind: str) -> dict[str, Any]:
    profile = PROFILES[kind]
    active = profile["active"]
    passive = profile["passive"]
    joint_count = active + passive
    stem = kind.replace("_", "-")
    configuration_id = f"ral.{kind}.r1"
    inventory_id = f"ral.inventory.{kind}.r1"
    calibration_id = f"ral.calibration.{kind}.unmeasured-r1"
    firmware_id = f"ral.firmware.{kind}.not-installed-r1"
    plant_id = f"ral.plant.{kind}.nominal-r1"
    experiment_id = f"ral.experiment.{kind}.contract-validation-r1"
    authorization_id = f"ral.authorization.{kind}.withheld-r1"
    result_id = f"ral.result.{kind}.contract-validation-r1"

    configuration = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "contract_type": "configuration",
        "configuration_id": configuration_id,
        "configuration_revision": CONTRACT_VERSION,
        "configuration_kind": kind,
        "configuration_hash": "sha256:" + "0" * 64,
        "mechanical_revision": "ral.mechanical.proposal-r1",
        "hardware_inventory_id": inventory_id,
        "calibration_set_id": calibration_id,
        "controller_firmware_set_id": firmware_id,
        "experiment_schema_version": CONTRACT_VERSION,
        "active_joint_count": active,
        "passive_joint_count": passive,
        "gravity_plane": profile["gravity"],
        "permitted_tools": profile["tools"],
        "component_envelope": profile["components"],
        "release": profile["release"],
        "safety_envelope": {
            "duration_limit_s": 10.0,
            "current_limits_a": _current_limits(active, 1.5),
            "state_limits": _state_limits(joint_count),
        },
        "design_status": "proposal",
    }
    configuration["configuration_hash"] = configuration_digest(configuration)
    config_hash = configuration["configuration_hash"]

    firmware_revisions = [
        {"joint_id": f"joint_{joint}", "revision": None}
        for joint in range(1, active + 1)
    ]
    encoders = [
        {
            "joint_id": f"joint_{joint}",
            "model": "MA600_planned",
            "asset_id": None,
            "identity_status": "planned_not_owned",
        }
        for joint in range(1, joint_count + 1)
    ]
    components = [
        {
            "instance_id": f"planned.joint-controller.{joint}",
            "role": "joint_controller",
            "model": "moteus-c1_planned",
            "asset_id": None,
            "identity_status": "planned_not_owned",
        }
        for joint in range(1, active + 1)
    ]
    components.extend(
        [
            {
                "instance_id": "planned.local-supervisor.1",
                "role": "local_supervisor",
                "model": "decision_required_after_G0",
                "asset_id": None,
                "identity_status": "planned_not_owned",
            },
            {
                "instance_id": "planned.independent-stop.1",
                "role": "independent_power_stop",
                "model": "selection_not_authorized",
                "asset_id": None,
                "identity_status": "planned_not_owned",
            },
        ]
    )
    inventory = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "contract_type": "hardware_inventory",
        "inventory_id": inventory_id,
        "inventory_revision": CONTRACT_VERSION,
        "inventory_status": "planned_fixture",
        "identity_scope": "synthetic_not_as_built",
        "platform_revision": "ral.reference-platform.proposal-r1",
        "configuration_id": configuration_id,
        "configuration_hash": config_hash,
        "joint_count": joint_count,
        "controller_firmware_revisions": {
            "set_id": firmware_id,
            "status": "not_installed",
            "revisions": firmware_revisions,
        },
        "encoder_identities": encoders,
        "power_configuration": "planned_unenergized_no_purchase_authority",
        "guard_configuration": "planned_not_evaluated",
        "calibration_set_id": calibration_id,
        "components": components,
        "evidence_level": "static",
    }

    plant = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "contract_type": "plant_model",
        "plant_model_id": plant_id,
        "plant_model_revision": CONTRACT_VERSION,
        "configuration_id": configuration_id,
        "configuration_hash": config_hash,
        "link_lengths_m": profile["lengths"],
        "link_masses_kg": profile["masses"],
        "inertia_kg_m2": profile["inertias"],
        "joint_friction_model": [
            {
                "joint_id": f"joint_{joint}",
                "model": "viscous_plus_coulomb",
                "viscous_nm_s_rad": round(0.01 + joint * 0.002, 3),
                "coulomb_nm": round(0.02 + joint * 0.003, 3),
            }
            for joint in range(1, joint_count + 1)
        ],
        "transmission_ratios": [4.0 for _ in range(active)],
        "encoder_zero_offsets_rad": [0.0 for _ in range(joint_count)],
        "parameter_source": "deterministic_nominal_fixture",
        "uncertainty": [
            {"parameter": "link_length", "plus_minus": 0.005, "unit": "m", "basis": "assumed_not_measured"},
            {"parameter": "link_mass", "plus_minus": 0.05, "unit": "kg", "basis": "assumed_not_measured"},
        ],
        "evidence_level": "static",
    }

    experiment = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "contract_type": "experiment",
        "experiment_id": experiment_id,
        "experiment_revision": CONTRACT_VERSION,
        "configuration_id": configuration_id,
        "configuration_hash": config_hash,
        "inventory_id": inventory_id,
        "plant_model_id": plant_id,
        "controller_revision": "not_implemented",
        "execution_domain": "contract_only",
        "requested_action": "validate_contracts",
        "sample_rate_hz": 100,
        "duration_limit_s": 5.0,
        "current_limits_a": _current_limits(active, 1.0),
        "position_or_state_limits": _state_limits(joint_count, scale=0.8),
        "abort_conditions": ["command_timeout", "current_limit", "state_envelope", "operator_request"],
        "required_artifacts": ["raw_telemetry", "event_log", "metric_report", "acceptance_map"],
        "acceptance_metrics": [
            {"metric_id": "schema_valid", "operator": "eq", "threshold": "true", "unit": "boolean"},
            {"metric_id": "identity_links_valid", "operator": "eq", "threshold": "true", "unit": "boolean"},
        ],
        "timeout_behavior": "request_abort_and_preserve_partial_artifacts",
        "cancellation_behavior": "request_abort_and_preserve_partial_artifacts",
        "restart_behavior": "require_new_authorization_and_preserve_prior_result",
    }

    authorization = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "contract_type": "run_authorization",
        "authorization_id": authorization_id,
        "authorization_revision": CONTRACT_VERSION,
        "experiment_id": experiment_id,
        "configuration_id": configuration_id,
        "configuration_hash": config_hash,
        "operator": "fixture:rp01",
        "authorization_status": "withheld",
        "physical_run_authorized": False,
        "local_presence_confirmed": False,
        "preflight_checklist_revision": "ral.preflight.not-performed-r1",
        "guard_state": "not_evaluated",
        "e_stop_test_result": "not_run",
        "permitted_configuration": configuration_id,
        "maximum_energy_class": "none",
        "issued_at": "2026-08-31T00:00:00Z",
        "expiration": "2026-08-31T00:05:00Z",
    }

    event_values = [
        ("event", "validated", "contract_validated", {"schema_count": 8}),
        ("telemetry", "validated", "validation_progress", {"fraction": 1.0, "unit": "ratio"}),
        ("event", "awaiting_local_authorization", "authorization_withheld", {"physical_run_authorized": False}),
        ("event", "completed", "completed", {"validation_level": "static"}),
    ]
    records = [
        {
            "schema_version": 1,
            "contract_version": CONTRACT_VERSION,
            "contract_type": "telemetry_event",
            "record_id": f"ral.record.{kind}.{index}",
            "experiment_id": experiment_id,
            "configuration_hash": config_hash,
            "sequence": index,
            "timestamp": f"2026-08-31T00:00:0{index}Z",
            "monotonic_offset_ns": index * 1_000_000,
            "record_kind": record_kind,
            "lifecycle_state": state,
            "event_type": event_type,
            "payload": payload,
            "evidence_level": "static",
        }
        for index, (record_kind, state, event_type, payload) in enumerate(event_values)
    ]

    acceptance_map = [
        {"metric_id": "schema_valid", "outcome": "pass", "evidence_level": "static"},
        {"metric_id": "identity_links_valid", "outcome": "pass", "evidence_level": "static"},
    ]
    result = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "contract_type": "result",
        "result_id": result_id,
        "result_revision": CONTRACT_VERSION,
        "experiment_id": experiment_id,
        "exact_configuration_hash": config_hash,
        "authorization_id": authorization_id,
        "start_timestamp": "2026-08-31T00:00:00Z",
        "stop_timestamp": "2026-08-31T00:00:03Z",
        "termination_reason": "completed",
        "raw_telemetry_artifact": _artifact(f"fixture://{stem}/telemetry-events", sha256_digest(records)),
        "metric_artifact": _artifact(f"fixture://{stem}/acceptance-map", sha256_digest(acceptance_map)),
        "acceptance_map": acceptance_map,
        "anomalies": ["none_observed_during_static_validation"],
        "residual_risks": ["nominal parameters are assumptions and have not been measured"],
        "unperformed_validation": ["all runtime, device, hardware, controls, PnP, HIL, field, and production validation"],
        "partial_artifacts_preserved": True,
        "physical_safe_state_claimed": False,
        "recovery": {
            "restart_detected": False,
            "prior_result_id": None,
            "new_authorization_required": False,
        },
        "evidence_level": "static",
    }
    evidence = {
        "schema_version": 1,
        "contract_version": CONTRACT_VERSION,
        "contract_type": "evidence",
        "evidence_id": f"ral.evidence.{kind}.rp01-r1",
        "evidence_revision": CONTRACT_VERSION,
        "result_id": result_id,
        "configuration_hash": config_hash,
        "validation_level": "static",
        "claim_boundary": "Software contract validation only; no physical capability is demonstrated or accepted.",
        "required_statements": list(REQUIRED_EVIDENCE_STATEMENTS),
        "artifacts": [
            _artifact(f"fixture://{stem}/configuration", config_hash),
            _artifact(f"fixture://{stem}/result", sha256_digest(result)),
        ],
        "acceptance_items": ["schema", "identity", "canonical_hash", "software_only_boundary"],
        "residual_risks": ["future consumers have not yet adopted this contract revision"],
        "unperformed_validation": ["MATLAB runtime and every physical validation level"],
    }
    return {
        "fixture_version": CONTRACT_VERSION,
        "fixture_id": f"ral.fixture.{kind}.valid-r1",
        "fixture_classification": "software_contract_only",
        "canonicalization": CANONICALIZATION_ID,
        "configuration": configuration,
        "hardware_inventory": inventory,
        "plant_model": plant,
        "experiment": experiment,
        "run_authorization": authorization,
        "telemetry_events": records,
        "result": result,
        "evidence": evidence,
    }


def _rebind_configuration(fixture: dict[str, Any]) -> None:
    configuration = fixture["configuration"]
    configuration["configuration_hash"] = configuration_digest(configuration)
    digest = configuration["configuration_hash"]
    for section in ("hardware_inventory", "plant_model", "experiment", "run_authorization"):
        fixture[section]["configuration_hash"] = digest
    for record in fixture["telemetry_events"]:
        record["configuration_hash"] = digest
    fixture["result"]["exact_configuration_hash"] = digest
    fixture["result"]["raw_telemetry_artifact"]["sha256"] = sha256_digest(fixture["telemetry_events"])
    fixture["evidence"]["configuration_hash"] = digest
    fixture["evidence"]["artifacts"][0]["sha256"] = digest
    fixture["evidence"]["artifacts"][1]["sha256"] = sha256_digest(fixture["result"])


def build_invalid_fixtures(valid: dict[str, dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    invalid: dict[str, dict[str, Any]] = {}
    expected: dict[str, str] = {}

    def add(name: str, source: str, code: str, mutate: Any) -> None:
        fixture = deepcopy(valid[source])
        mutate(fixture)
        invalid[name] = fixture
        expected[f"{name}.json"] = code

    add("missing-identity", "drawbot_2r", "identity.missing", lambda item: item["configuration"].pop("configuration_id"))
    add("conflicting-configuration", "drawbot_2r", "link.configuration_id", lambda item: item["hardware_inventory"].__setitem__("configuration_id", "ral.rotary_pendulum_1.r1"))
    add("absent-local-authorization", "drawbot_2r", "authorization.missing", lambda item: item.pop("run_authorization"))
    add("unbounded-current", "drawbot_2r", "field.required", lambda item: item["experiment"]["current_limits_a"][0].pop("max_abs_a"))
    add("unbounded-duration", "drawbot_2r", "field.required", lambda item: item["experiment"].pop("duration_limit_s"))
    add("unbounded-state", "drawbot_2r", "field.required", lambda item: item["experiment"]["position_or_state_limits"][0].pop("maximum"))
    add("excessive-current", "drawbot_2r", "limit.current.exceeded", lambda item: item["experiment"]["current_limits_a"][0].__setitem__("max_abs_a", 2.0))
    add("excessive-duration", "drawbot_2r", "limit.duration.exceeded", lambda item: item["experiment"].__setitem__("duration_limit_s", 20.0))
    add("excessive-state", "drawbot_2r", "limit.state.exceeded", lambda item: item["experiment"]["position_or_state_limits"][0].__setitem__("maximum", 3.5))

    def release_pnp(item: dict[str, Any]) -> None:
        item["configuration"]["release"] = {"status": "baseline", "gate_id": None, "decision_evidence_id": None}
        _rebind_configuration(item)

    add("unsupported-pnp-release", "pnp_single_head", "pnp.release_unsupported", release_pnp)
    add("conflated-evidence-level", "drawbot_2r", "evidence.level_conflated", lambda item: item["evidence"].__setitem__("validation_level", "guarded_motion"))
    add("configuration-hash-mismatch", "drawbot_2r", "hash.mismatch", lambda item: item["configuration"].__setitem__("mechanical_revision", "ral.mechanical.proposal-r2"))
    add("unsupported-contract-version", "drawbot_2r", "version.unsupported", lambda item: item["configuration"].__setitem__("contract_version", "2.0.0"))
    add("unsupported-schema-version", "drawbot_2r", "version.unsupported", lambda item: item["configuration"].__setitem__("schema_version", 2))
    add("unknown-member", "drawbot_2r", "field.unknown", lambda item: item["experiment"].__setitem__("device_path", "/forbidden"))
    add("artifact-path-traversal", "drawbot_2r", "artifact.uri", lambda item: item["result"]["raw_telemetry_artifact"].__setitem__("uri", "fixture://drawbot/../escape"))
    add("artifact-uri-space", "drawbot_2r", "artifact.uri", lambda item: item["result"]["raw_telemetry_artifact"].__setitem__("uri", "fixture://a b"))
    add("artifact-uri-hidden", "drawbot_2r", "artifact.uri", lambda item: item["result"]["raw_telemetry_artifact"].__setitem__("uri", "fixture://.hidden"))
    add("expired-authorization", "drawbot_2r", "authorization.expired", lambda item: item["run_authorization"].__setitem__("expiration", "2026-08-31T00:00:02Z"))

    def remove_configuration_state(item: dict[str, Any]) -> None:
        item["configuration"]["safety_envelope"]["state_limits"].pop()
        _rebind_configuration(item)

    add("missing-state-coverage", "drawbot_2r", "limit.state_identity", remove_configuration_state)
    add("duplicate-firmware-identity", "drawbot_2r", "identity.firmware", lambda item: item["hardware_inventory"]["controller_firmware_revisions"]["revisions"][1].__setitem__("joint_id", "joint_1"))
    add("duplicate-encoder-identity", "drawbot_2r", "identity.encoder", lambda item: item["hardware_inventory"]["encoder_identities"][1].__setitem__("joint_id", "joint_1"))
    add("duplicate-component-identity", "drawbot_2r", "identity.component", lambda item: item["hardware_inventory"]["components"][1].__setitem__("instance_id", item["hardware_inventory"]["components"][0]["instance_id"]))
    add("duplicate-friction-identity", "drawbot_2r", "identity.friction", lambda item: item["plant_model"]["joint_friction_model"][1].__setitem__("joint_id", "joint_1"))
    add("incomplete-acceptance-map", "drawbot_2r", "result.acceptance_map", lambda item: item["result"]["acceptance_map"].pop())
    add("inconsistent-completion-state", "drawbot_2r", "telemetry.event_semantics", lambda item: item["telemetry_events"][-1].__setitem__("lifecycle_state", "failed"))
    add("authorization-event-conflation", "drawbot_2r", "telemetry.payload", lambda item: item["telemetry_events"][2]["payload"].__setitem__("physical_run_authorized", True))
    add("unknown-abort-condition", "drawbot_2r", "field.value", lambda item: item["experiment"]["abort_conditions"].append("unknown_condition"))
    add("invalid-timestamp-profile", "drawbot_2r", "field.timestamp", lambda item: item["run_authorization"].__setitem__("issued_at", "2026-08-31Z"))

    def conflate_static_metric(item: dict[str, Any]) -> None:
        item["experiment"]["acceptance_metrics"][0] = {
            "metric_id": "physical_safe_state",
            "operator": "eq",
            "threshold": "true",
            "unit": "boolean",
        }
        item["result"]["acceptance_map"][0]["metric_id"] = "physical_safe_state"
        item["result"]["metric_artifact"]["sha256"] = sha256_digest(item["result"]["acceptance_map"])
        item["evidence"]["artifacts"][1]["sha256"] = sha256_digest(item["result"])

    add("conflated-static-metric", "drawbot_2r", "claim.metric_conflated", conflate_static_metric)
    add(
        "conflated-static-acceptance-item",
        "drawbot_2r",
        "evidence.acceptance_items",
        lambda item: item["evidence"]["acceptance_items"].__setitem__(0, "working_drawbot"),
    )

    def completion_after_timeout(item: dict[str, Any]) -> None:
        timeout = deepcopy(item["telemetry_events"][-1])
        timeout.update(
            {
                "record_id": "ral.record.drawbot_2r.timeout-before-completion",
                "sequence": 3,
                "timestamp": "2026-08-31T00:00:03Z",
                "monotonic_offset_ns": 3_000_000,
                "lifecycle_state": "failed",
                "event_type": "timeout_detected",
                "payload": {"retained": True},
            }
        )
        completed = item["telemetry_events"][-1]
        completed.update(
            {
                "record_id": "ral.record.drawbot_2r.4",
                "sequence": 4,
                "timestamp": "2026-08-31T00:00:04Z",
                "monotonic_offset_ns": 4_000_000,
            }
        )
        item["telemetry_events"] = item["telemetry_events"][:3] + [timeout, completed]
        item["result"]["stop_timestamp"] = "2026-08-31T00:00:04Z"
        item["result"]["raw_telemetry_artifact"]["sha256"] = sha256_digest(item["telemetry_events"])
        item["evidence"]["artifacts"][1]["sha256"] = sha256_digest(item["result"])

    add("completion-after-timeout", "drawbot_2r", "lifecycle.completion", completion_after_timeout)
    return invalid, expected


def _fail_output(code: str, message: str) -> None:
    raise ContractError(code, message)


def _prepare_output_root(output: Path) -> Path:
    if output.is_symlink():
        _fail_output("path.symlink", f"fixture output root cannot be a symbolic link: {output}")
    try:
        output.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        _fail_output("path.unwritable", f"cannot create fixture output root {output}: {exc}")
    if output.is_symlink():
        _fail_output("path.symlink", f"fixture output root cannot be a symbolic link: {output}")
    if not output.is_dir():
        _fail_output("path.not_directory", f"fixture output root is not a directory: {output}")
    return output.resolve()


def _safe_destination(output_root: Path, relative: Path) -> Path:
    if relative.is_absolute() or not relative.parts or any(part in ("", ".", "..") for part in relative.parts):
        _fail_output("path.escape", f"fixture output path must be relative and confined: {relative}")
    if output_root.is_symlink():
        _fail_output("path.symlink", f"fixture output root cannot be a symbolic link: {output_root}")
    if not output_root.is_dir():
        _fail_output("path.not_directory", f"fixture output root is not a directory: {output_root}")
    if output_root.resolve() != output_root:
        _fail_output("path.escape", f"fixture output root no longer resolves to {output_root}")
    parent = output_root
    for part in relative.parts[:-1]:
        parent /= part
        if parent.is_symlink():
            _fail_output("path.symlink", f"fixture output parent cannot be a symbolic link: {parent}")
        try:
            parent.mkdir(exist_ok=True)
        except OSError as exc:
            _fail_output("path.unwritable", f"cannot create fixture output directory {parent}: {exc}")
        if parent.is_symlink():
            _fail_output("path.symlink", f"fixture output parent cannot be a symbolic link: {parent}")
        if not parent.is_dir():
            _fail_output("path.not_directory", f"fixture output parent is not a directory: {parent}")
        try:
            parent.resolve().relative_to(output_root)
        except ValueError:
            _fail_output("path.escape", f"fixture output parent escapes {output_root}: {parent}")
    destination = parent / relative.name
    if destination.is_symlink():
        _fail_output("path.symlink", f"fixture output file cannot be a symbolic link: {destination}")
    if destination.exists() and not destination.is_file():
        _fail_output("path.not_regular", f"fixture output path is not a regular file: {destination}")
    return destination


def _write_bytes(output_root: Path, relative: Path, raw: bytes) -> None:
    destination = _safe_destination(output_root, relative)
    temporary_name: str | None = None
    descriptor: int | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".tmp", dir=destination.parent)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = None
            stream.write(raw)
        os.chmod(temporary_name, 0o644)
        destination = _safe_destination(output_root, relative)
        os.replace(temporary_name, destination)
        temporary_name = None
    except ContractError:
        raise
    except OSError as exc:
        _fail_output("path.unwritable", f"cannot write fixture output {destination}: {exc}")
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_name is not None:
            try:
                Path(temporary_name).unlink()
            except FileNotFoundError:
                pass


def _write_json(output_root: Path, relative: Path, value: Any) -> None:
    raw = (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    _write_bytes(output_root, relative, raw)


def generate(output: Path) -> None:
    output_root = _prepare_output_root(output)
    valid = {kind: build_fixture(kind) for kind in PROFILES}
    invalid, expected = build_invalid_fixtures(valid)
    for kind, fixture in valid.items():
        _write_json(output_root, Path("valid") / f"{kind.replace('_', '-')}.json", fixture)
    for name, fixture in invalid.items():
        _write_json(output_root, Path("invalid") / f"{name}.json", fixture)
    _write_json(
        output_root,
        Path("canonical-hashes.json"),
        {
            "canonicalization": CANONICALIZATION_ID,
            "configuration_hashes": {
                kind: fixture["configuration"]["configuration_hash"]
                for kind, fixture in sorted(valid.items())
            },
            "fixture_version": CONTRACT_VERSION,
        },
    )
    _write_json(output_root, Path("invalid") / "expected-errors.json", expected)
    _write_bytes(output_root, Path("invalid") / "malformed-trailing-comma.json.txt", b'{"fixture_id":"malformed",}\n')
    _write_bytes(output_root, Path("invalid") / "duplicate-key.json.txt", b'{"fixture_id":"one","fixture_id":"two"}\n')
    _write_bytes(output_root, Path("invalid") / "non-finite.json.txt", b'{"fixture_id":"non-finite","value":NaN}\n')
    _write_bytes(output_root, Path("invalid") / "top-level-array.json.txt", b'[]\n')
    _write_bytes(output_root, Path("invalid") / "invalid-utf8.json.bin", b'{"fixture_id":"invalid-utf8","value":"\xff"}\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    generate(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
