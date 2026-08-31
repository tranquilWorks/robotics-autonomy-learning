"""Pure, bounded validation for RP01 reference-platform contract fixtures.

The module deliberately uses only the Python standard library and performs local
file reads only. It does not discover devices, contact services, inspect owner
credentials, or perform any physical action.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import unicodedata
from typing import Any, Iterable, Mapping

CONTRACT_VERSION = "1.0.0"
FIXTURE_VERSION = "1.0.0"
CONTRACT_FAMILY = "robotics-autonomy-learning.reference-platform"
CANONICALIZATION_ID = "ral-json-c14n-v1"
CANONICALIZATION_SERIALIZATION = (
    "UTF-8 JSON; Unicode-code-point object-key order; array order preserved; no insignificant whitespace; "
    "strings already NFC; JSON strings use double quotes, escape quotation mark and reverse solidus, use "
    "\\b, \\t, \\n, \\f, and \\r for those controls, use lowercase \\u00xx for other U+0000..U+001F "
    "controls, leave solidus and all other Unicode scalar values unescaped; booleans distinct from numbers; "
    "negative zero and integral floats below 1e21 rendered as integers; other finite floats use lowercase "
    "shortest Python 3.12 representation with an integer exponent"
)

MAX_DOCUMENT_BYTES = 1_048_576
MAX_DEPTH = 32
MAX_NODES = 10_000
MAX_ARRAY_ITEMS = 2_048
MAX_OBJECT_MEMBERS = 512
MAX_STRING_CHARS = 16_384

HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._:-]{1,127}$")
STATE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
TIMESTAMP_PATTERN = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$")
ARTIFACT_URI_PATTERN = re.compile(r"^fixture://[a-z0-9][a-z0-9/_-]{0,255}$")

STATIC_ACCEPTANCE_METRICS = {
    "schema_valid": ("eq", "true", "boolean"),
    "identity_links_valid": ("eq", "true", "boolean"),
}
STATIC_ACCEPTANCE_ITEMS = (
    "schema",
    "identity",
    "canonical_hash",
    "software_only_boundary",
)

VALIDATION_LEVELS = (
    "static",
    "simulated",
    "protocol_replay",
    "low_energy_bench",
    "guarded_motion",
    "controls_experiment",
    "pnp_validation",
    "external_alpha",
)

REQUIRED_EVIDENCE_STATEMENTS = (
    "SOFTWARE CONTRACT ONLY",
    "HARDWARE NOT RUN",
    "TRANQUILITY NOT CONTACTED",
    "CONTROLS-GNC NOT MODIFIED",
    "RELEASE NOT PERFORMED",
)

CONFIGURATION_PROFILES = {
    "drawbot_2r": {
        "active": 2,
        "passive": 0,
        "gravity": "horizontal",
        "tools": ("pen",),
        "release": "baseline",
        "gate": None,
    },
    "rotary_pendulum_1": {
        "active": 1,
        "passive": 1,
        "gravity": "vertical",
        "tools": (),
        "release": "baseline",
        "gate": None,
    },
    "pendubot_2link": {
        "active": 1,
        "passive": 1,
        "gravity": "vertical",
        "tools": (),
        "release": "baseline",
        "gate": None,
    },
    "passive_multilink": {
        "active": 1,
        "passive": 2,
        "gravity": "vertical",
        "tools": (),
        "release": "gated",
        "gate": "G4_MULTILINK",
    },
    "pnp_single_head": {
        "active": 2,
        "passive": 0,
        "gravity": "horizontal",
        "tools": ("z_theta_vacuum_head",),
        "release": "gated",
        "gate": "G5_PNP_FEASIBILITY",
    },
}

SCHEMA_FILES = {
    "configuration": "configuration.schema.json",
    "hardware_inventory": "hardware-inventory.schema.json",
    "plant_model": "plant-model.schema.json",
    "experiment": "experiment.schema.json",
    "run_authorization": "run-authorization.schema.json",
    "telemetry_event": "telemetry-event.schema.json",
    "result": "result.schema.json",
    "evidence": "evidence.schema.json",
}


class ContractError(ValueError):
    """A deterministic contract rejection with a stable machine-facing code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _fail(code: str, message: str) -> None:
    raise ContractError(code, message)


def _reject_constant(value: str) -> None:
    _fail("json.non_finite", f"non-finite JSON number {value!r} is forbidden")


def _bounded_int(value: str) -> int:
    digits = value.removeprefix("-")
    if len(digits) > 128:
        _fail("resource.number", "integer literal exceeds 128 digits")
    return int(value)


def _bounded_float(value: str) -> float:
    if len(value) > 128:
        _fail("resource.number", "floating-point literal exceeds 128 characters")
    number = float(value)
    if not math.isfinite(number):
        _fail("json.non_finite", f"non-finite JSON number {value!r} is forbidden")
    return number


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("json.duplicate_key", f"duplicate object member {key!r}")
        result[key] = value
    return result


def load_json_bytes(raw: bytes, *, source: str = "<bytes>") -> Any:
    """Parse strict UTF-8 JSON after enforcing byte and structural bounds."""

    if len(raw) > MAX_DOCUMENT_BYTES:
        _fail("resource.document_bytes", f"{source} exceeds {MAX_DOCUMENT_BYTES} bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        _fail("json.utf8", f"{source} is not valid UTF-8: {exc}")
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_int=_bounded_int,
            parse_float=_bounded_float,
            parse_constant=_reject_constant,
        )
    except ContractError:
        raise
    except (json.JSONDecodeError, RecursionError, ValueError) as exc:
        _fail("json.malformed", f"{source} is not one complete JSON document: {exc}")
    _validate_resource_limits(value)
    return value


def load_json(path: Path | str, *, allowed_root: Path | None = None) -> Any:
    """Load one bounded regular file, optionally confined to an allowed root."""

    candidate = Path(path)
    if candidate.is_symlink():
        _fail("path.symlink", f"symbolic links are not accepted: {candidate}")
    resolved = candidate.resolve()
    if allowed_root is not None:
        root = allowed_root.resolve()
        try:
            resolved.relative_to(root)
        except ValueError:
            _fail("path.escape", f"{candidate} escapes {root}")
    try:
        metadata = resolved.stat()
    except OSError as exc:
        _fail("path.unreadable", f"cannot read {candidate}: {exc}")
    if not stat.S_ISREG(metadata.st_mode):
        _fail("path.not_regular", f"not a regular file: {candidate}")
    if metadata.st_size > MAX_DOCUMENT_BYTES:
        _fail("resource.document_bytes", f"{candidate} exceeds {MAX_DOCUMENT_BYTES} bytes")
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        _fail("path.unreadable", f"cannot read {candidate}: {exc}")
    return load_json_bytes(raw, source=str(candidate))


def _validate_resource_limits(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 1)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > MAX_NODES:
            _fail("resource.nodes", f"document exceeds {MAX_NODES} values")
        if depth > MAX_DEPTH:
            _fail("resource.depth", f"document exceeds nesting depth {MAX_DEPTH}")
        if isinstance(current, str):
            if len(current) > MAX_STRING_CHARS:
                _fail("resource.string", f"string exceeds {MAX_STRING_CHARS} characters")
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                _fail("json.unicode_scalar", "unpaired Unicode surrogates are forbidden")
            if unicodedata.normalize("NFC", current) != current:
                _fail("canonical.unicode", "strings must already be Unicode NFC")
        elif isinstance(current, list):
            if len(current) > MAX_ARRAY_ITEMS:
                _fail("resource.array", f"array exceeds {MAX_ARRAY_ITEMS} items")
            stack.extend((item, depth + 1) for item in reversed(current))
        elif isinstance(current, dict):
            if len(current) > MAX_OBJECT_MEMBERS:
                _fail("resource.object", f"object exceeds {MAX_OBJECT_MEMBERS} members")
            stack.extend((item, depth + 1) for item in reversed(tuple(current.values())))
            stack.extend((key, depth + 1) for key in reversed(tuple(current.keys())))
        elif isinstance(current, int) and not isinstance(current, bool):
            if abs(current) >= 10**128:
                _fail("resource.number", "integer value exceeds 128 decimal digits")
        elif isinstance(current, float) and not math.isfinite(current):
            _fail("json.non_finite", "non-finite numbers are forbidden")


def canonical_bytes(value: Any) -> bytes:
    """Serialize using the explicitly versioned ``ral-json-c14n-v1`` profile."""

    _validate_resource_limits(value)
    return _canonical_text(value).encode("utf-8")


def _canonical_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            _fail("json.non_finite", "non-finite numbers are forbidden")
        if value == 0:
            return "0"
        if value.is_integer() and abs(value) < 1e21:
            return str(int(value))
        rendered = repr(value).lower()
        if "e" in rendered:
            mantissa, exponent = rendered.split("e", 1)
            rendered = f"{mantissa}e{int(exponent)}"
        return rendered
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, allow_nan=False)
    if isinstance(value, list):
        return "[" + ",".join(_canonical_text(item) for item in value) + "]"
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            _fail("canonical.object_key", "object keys must be strings")
        return "{" + ",".join(
            f"{_canonical_text(key)}:{_canonical_text(value[key])}"
            for key in sorted(value)
        ) + "}"
    _fail("canonical.unsupported_value", f"unsupported value type {type(value).__name__}")


def sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()


def configuration_digest(configuration: Mapping[str, Any]) -> str:
    """Hash a configuration while excluding only its own digest member."""

    if not isinstance(configuration, Mapping):
        _fail("document.root", "configuration must be an object")
    payload = dict(configuration)
    payload.pop("configuration_hash", None)
    return sha256_digest(payload)


def _validate_schema_node(node: Any, root: Mapping[str, Any], path: str) -> None:
    if not isinstance(node, dict):
        _fail("schema.structure", f"{path} must be a schema object")
    known_keywords = {
        "$defs",
        "$id",
        "$ref",
        "$schema",
        "additionalProperties",
        "const",
        "description",
        "enum",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "items",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "oneOf",
        "pattern",
        "properties",
        "required",
        "title",
        "type",
        "uniqueItems",
    }
    unknown = set(node) - known_keywords
    if unknown:
        _fail("schema.keyword", f"{path} has unsupported keywords {sorted(unknown)}")
    allowed_types = {"array", "boolean", "integer", "null", "number", "object", "string"}
    if "type" in node:
        declared = node["type"] if isinstance(node["type"], list) else [node["type"]]
        if not declared or not all(isinstance(item, str) and item in allowed_types for item in declared):
            _fail("schema.type", f"{path}.type is invalid")
    properties = node.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            _fail("schema.structure", f"{path}.properties must be an object")
        for name, child in properties.items():
            if not isinstance(name, str):
                _fail("schema.structure", f"{path}.properties has a non-string name")
            _validate_schema_node(child, root, f"{path}.properties.{name}")
    definitions = node.get("$defs")
    if definitions is not None:
        if not isinstance(definitions, dict):
            _fail("schema.structure", f"{path}.$defs must be an object")
        for name, child in definitions.items():
            _validate_schema_node(child, root, f"{path}.$defs.{name}")
    if "required" in node:
        required = node["required"]
        if not isinstance(required, list) or not required or not all(isinstance(item, str) for item in required) or len(required) != len(set(required)):
            _fail("schema.required", f"{path}.required must contain unique strings")
        if properties is None or not set(required) <= set(properties):
            _fail("schema.required", f"{path}.required names undeclared properties")
    if "items" in node:
        _validate_schema_node(node["items"], root, f"{path}.items")
    if "oneOf" in node:
        choices = node["oneOf"]
        if not isinstance(choices, list) or len(choices) < 2:
            _fail("schema.one_of", f"{path}.oneOf must have at least two schemas")
        for index, child in enumerate(choices):
            _validate_schema_node(child, root, f"{path}.oneOf[{index}]")
    if "$ref" in node:
        reference = node["$ref"]
        if not isinstance(reference, str) or not reference.startswith("#/$defs/"):
            _fail("schema.reference", f"{path} has a non-local reference")
        name = reference.removeprefix("#/$defs/")
        if not isinstance(root.get("$defs"), dict) or name not in root["$defs"]:
            _fail("schema.reference", f"{path} references missing definition {name}")
    if "pattern" in node:
        if not isinstance(node["pattern"], str):
            _fail("schema.pattern", f"{path}.pattern must be a string")
        try:
            re.compile(node["pattern"])
        except re.error as exc:
            _fail("schema.pattern", f"{path}.pattern is invalid: {exc}")
    for minimum_name, maximum_name in (("minimum", "maximum"), ("minItems", "maxItems"), ("minLength", "maxLength"), ("minProperties", "maxProperties")):
        if minimum_name in node and maximum_name in node and node[minimum_name] > node[maximum_name]:
            _fail("schema.bounds", f"{path} has inverted {minimum_name}/{maximum_name}")
    if "additionalProperties" in node and not isinstance(node["additionalProperties"], (bool, dict)):
        _fail("schema.structure", f"{path}.additionalProperties must be boolean or a schema")


def validate_schema_catalog(contract_root: Path | str) -> Mapping[str, Any]:
    """Validate the local v1 schema inventory and its stable identities."""

    root = Path(contract_root)
    index = load_json(root / "contract-index.json", allowed_root=root)
    required = (
        "schema_version",
        "contract_family",
        "contract_version",
        "fixture_bundle_version",
        "canonicalization",
        "evidence_levels",
        "contracts",
    )
    catalog = _object(index, "contract_index", required=required, allowed=required)
    if catalog["schema_version"] != 1 or catalog["contract_version"] != CONTRACT_VERSION:
        _fail("schema.version", "contract index must identify schema family v1.0.0")
    if catalog["contract_family"] != CONTRACT_FAMILY:
        _fail("schema.family", "contract index family identity conflicts")
    if catalog["fixture_bundle_version"] != FIXTURE_VERSION:
        _fail("schema.version", "fixture bundle version conflicts")
    if tuple(catalog["evidence_levels"]) != VALIDATION_LEVELS:
        _fail("schema.evidence_levels", "contract index evidence taxonomy conflicts")
    canonical = _object(
        catalog["canonicalization"],
        "contract_index.canonicalization",
        required=("id", "algorithm", "serialization", "newline_included", "configuration_hash_excludes"),
        allowed=("id", "algorithm", "serialization", "newline_included", "configuration_hash_excludes"),
    )
    if canonical["id"] != CANONICALIZATION_ID or canonical["algorithm"] != "SHA-256" or canonical["newline_included"] is not False:
        _fail("schema.canonicalization", "canonicalization identity conflicts")
    if canonical["serialization"] != CANONICALIZATION_SERIALIZATION:
        _fail("schema.canonicalization", "canonical serialization descriptor conflicts")
    if canonical["configuration_hash_excludes"] != ["configuration_hash"]:
        _fail("schema.canonicalization", "configuration digest exclusion set conflicts")
    records = _array(catalog["contracts"], "contract_index.contracts", minimum=8, maximum=8)
    observed: dict[str, str] = {}
    for index, record_value in enumerate(records):
        record = _object(
            record_value,
            f"contract_index.contracts[{index}]",
            required=("contract_type", "path", "schema_id"),
            allowed=("contract_type", "path", "schema_id"),
        )
        contract_type = _string(record["contract_type"], f"contract_index.contracts[{index}].contract_type")
        if contract_type in observed:
            _fail("schema.duplicate", f"duplicate schema for {contract_type}")
        expected_file = SCHEMA_FILES.get(contract_type)
        if expected_file is None or record["path"] != f"v1/{expected_file}":
            _fail("schema.inventory", f"unexpected schema path for {contract_type}")
        schema_path = root / record["path"]
        schema = load_json(schema_path, allowed_root=root)
        if not isinstance(schema, dict):
            _fail("schema.root", f"{schema_path} must contain an object schema")
        _validate_schema_node(schema, schema, str(schema_path))
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            _fail("schema.dialect", f"{schema_path} must declare Draft 2020-12")
        if schema.get("$id") != record["schema_id"]:
            _fail("schema.identity", f"{schema_path} identity conflicts with the catalog")
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            _fail("schema.strictness", f"{schema_path} must be a strict object schema")
        properties = schema.get("properties")
        required_fields = schema.get("required")
        if not isinstance(properties, dict) or not isinstance(required_fields, list):
            _fail("schema.structure", f"{schema_path} lacks properties or required fields")
        if properties.get("contract_version", {}).get("const") != CONTRACT_VERSION:
            _fail("schema.version", f"{schema_path} does not pin {CONTRACT_VERSION}")
        if properties.get("schema_version", {}).get("const") != 1:
            _fail("schema.version", f"{schema_path} does not pin schema_version 1")
        if properties.get("contract_type", {}).get("const") != contract_type:
            _fail("schema.contract_type", f"{schema_path} contract type conflicts")
        if not {"schema_version", "contract_version", "contract_type"} <= set(required_fields):
            _fail("schema.required", f"{schema_path} does not require its version identity")
        observed[contract_type] = record["path"]
    if set(observed) != set(SCHEMA_FILES):
        _fail("schema.inventory", "contract index does not contain exactly the eight RP01 contract types")
    return catalog


def _object(
    value: Any,
    path: str,
    *,
    required: Iterable[str],
    allowed: Iterable[str],
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail("field.type", f"{path} must be an object")
    required_set = set(required)
    missing = sorted(required_set - value.keys())
    if missing:
        _fail("field.required", f"{path} is missing {', '.join(missing)}")
    unknown = sorted(value.keys() - set(allowed))
    if unknown:
        _fail("field.unknown", f"{path} has unknown members {', '.join(unknown)}")
    return value


def _array(value: Any, path: str, *, minimum: int = 0, maximum: int = MAX_ARRAY_ITEMS) -> list[Any]:
    if not isinstance(value, list):
        _fail("field.type", f"{path} must be an array")
    if not minimum <= len(value) <= maximum:
        _fail("field.cardinality", f"{path} must contain {minimum}..{maximum} items")
    return value


def _string(
    value: Any,
    path: str,
    *,
    choices: Iterable[str] | None = None,
    pattern: re.Pattern[str] | None = None,
) -> str:
    if not isinstance(value, str) or not value:
        _fail("field.type", f"{path} must be a non-empty string")
    if choices is not None and value not in set(choices):
        _fail("field.value", f"{path} has unsupported value {value!r}")
    if pattern is not None and not pattern.fullmatch(value):
        _fail("field.format", f"{path} has invalid format")
    return value


def _identifier(value: Any, path: str) -> str:
    return _string(value, path, pattern=ID_PATTERN)


def _number(
    value: Any,
    path: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
    integer: bool = False,
) -> float:
    expected = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected):
        _fail("field.type", f"{path} must be a {'integer' if integer else 'number'}")
    number = float(value)
    if not math.isfinite(number):
        _fail("json.non_finite", f"{path} must be finite")
    if minimum is not None and number < minimum:
        _fail("field.minimum", f"{path} must be at least {minimum}")
    if maximum is not None and number > maximum:
        _fail("field.maximum", f"{path} must be at most {maximum}")
    return number


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail("field.type", f"{path} must be boolean")
    return value


def _timestamp(value: Any, path: str) -> datetime:
    text = _string(value, path)
    if not TIMESTAMP_PATTERN.fullmatch(text):
        _fail("field.timestamp", f"{path} must match the published RFC 3339 UTC profile")
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError:
        _fail("field.timestamp", f"{path} is not an RFC 3339 timestamp")
    return parsed


def _hash(value: Any, path: str) -> str:
    text = _string(value, path)
    if not HASH_PATTERN.fullmatch(text):
        _fail("field.hash", f"{path} must be sha256:<64 lowercase hex>")
    return text


def _contract_header(value: Mapping[str, Any], path: str, contract_type: str) -> None:
    if value["schema_version"] != 1:
        _fail("version.unsupported", f"{path}.schema_version must be 1")
    if value["contract_version"] != CONTRACT_VERSION:
        _fail("version.unsupported", f"{path}.contract_version must be {CONTRACT_VERSION}")
    if value["contract_type"] != contract_type:
        _fail("contract.type", f"{path}.contract_type must be {contract_type}")


def _expected_state_units(joint_count: int) -> dict[str, str]:
    expected: dict[str, str] = {}
    for joint in range(1, joint_count + 1):
        expected[f"joint_{joint}_position_rad"] = "rad"
        expected[f"joint_{joint}_velocity_rad_s"] = "rad_s"
    return expected


def _validate_limit_list(value: Any, path: str) -> dict[str, tuple[float, float, str]]:
    items = _array(value, path, minimum=1, maximum=16)
    limits: dict[str, tuple[float, float, str]] = {}
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        record = _object(
            item,
            item_path,
            required=("state", "minimum", "maximum", "unit"),
            allowed=("state", "minimum", "maximum", "unit"),
        )
        state_name = _string(record["state"], f"{item_path}.state", pattern=STATE_NAME_PATTERN)
        if state_name in limits:
            _fail("limit.state_duplicate", f"{path} repeats {state_name}")
        lower = _number(record["minimum"], f"{item_path}.minimum", minimum=-100.0, maximum=100.0)
        upper = _number(record["maximum"], f"{item_path}.maximum", minimum=-100.0, maximum=100.0)
        unit = _string(record["unit"], f"{item_path}.unit", choices=("rad", "rad_s", "m", "m_s"))
        if lower >= upper:
            _fail("limit.state_unbounded", f"{item_path} minimum must be less than maximum")
        limits[state_name] = (lower, upper, unit)
    return limits


def _validate_current_limits(value: Any, path: str, active_joints: int) -> dict[str, float]:
    items = _array(value, path, minimum=active_joints, maximum=active_joints)
    limits: dict[str, float] = {}
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        record = _object(
            item,
            item_path,
            required=("joint_id", "max_abs_a"),
            allowed=("joint_id", "max_abs_a"),
        )
        joint_id = _string(record["joint_id"], f"{item_path}.joint_id", pattern=re.compile(r"^joint_[1-9][0-9]*$"))
        if joint_id in limits:
            _fail("limit.current_duplicate", f"{path} repeats {joint_id}")
        limit = _number(record["max_abs_a"], f"{item_path}.max_abs_a", minimum=0.001, maximum=5.0)
        limits[joint_id] = limit
    expected = {f"joint_{index}" for index in range(1, active_joints + 1)}
    if set(limits) != expected:
        _fail("limit.current_identity", f"{path} must cover {sorted(expected)}")
    return limits


def _validate_configuration(value: Any) -> tuple[Mapping[str, Any], dict[str, float], dict[str, tuple[float, float, str]]]:
    path = "configuration"
    required = (
        "contract_version",
        "schema_version",
        "contract_type",
        "configuration_id",
        "configuration_revision",
        "configuration_kind",
        "configuration_hash",
        "mechanical_revision",
        "hardware_inventory_id",
        "calibration_set_id",
        "controller_firmware_set_id",
        "experiment_schema_version",
        "active_joint_count",
        "passive_joint_count",
        "gravity_plane",
        "permitted_tools",
        "component_envelope",
        "release",
        "safety_envelope",
        "design_status",
    )
    config = _object(value, path, required=required, allowed=required)
    _contract_header(config, path, "configuration")
    if "configuration_id" not in config or not config["configuration_id"]:
        _fail("identity.missing", "configuration.configuration_id is required")
    _identifier(config["configuration_id"], f"{path}.configuration_id")
    _string(config["configuration_revision"], f"{path}.configuration_revision", choices=(CONTRACT_VERSION,))
    kind = _string(config["configuration_kind"], f"{path}.configuration_kind", choices=CONFIGURATION_PROFILES)
    profile = CONFIGURATION_PROFILES[kind]
    _hash(config["configuration_hash"], f"{path}.configuration_hash")
    _identifier(config["mechanical_revision"], f"{path}.mechanical_revision")
    _identifier(config["hardware_inventory_id"], f"{path}.hardware_inventory_id")
    _identifier(config["calibration_set_id"], f"{path}.calibration_set_id")
    _identifier(config["controller_firmware_set_id"], f"{path}.controller_firmware_set_id")
    _string(config["experiment_schema_version"], f"{path}.experiment_schema_version", choices=(CONTRACT_VERSION,))
    active = int(_number(config["active_joint_count"], f"{path}.active_joint_count", minimum=1, maximum=2, integer=True))
    passive = int(_number(config["passive_joint_count"], f"{path}.passive_joint_count", minimum=0, maximum=3, integer=True))
    gravity = _string(config["gravity_plane"], f"{path}.gravity_plane", choices=("horizontal", "vertical"))
    tools = tuple(_string(item, f"{path}.permitted_tools[]") for item in _array(config["permitted_tools"], f"{path}.permitted_tools", maximum=2))
    components = tuple(
        _string(item, f"{path}.component_envelope[]")
        for item in _array(config["component_envelope"], f"{path}.component_envelope", maximum=16)
    )
    release = _object(
        config["release"],
        f"{path}.release",
        required=("status", "gate_id", "decision_evidence_id"),
        allowed=("status", "gate_id", "decision_evidence_id"),
    )
    release_status = _string(release["status"], f"{path}.release.status", choices=("baseline", "gated"))
    gate_id = release["gate_id"]
    if gate_id is not None:
        _string(gate_id, f"{path}.release.gate_id", choices=("G4_MULTILINK", "G5_PNP_FEASIBILITY"))
    if release["decision_evidence_id"] is not None:
        _identifier(release["decision_evidence_id"], f"{path}.release.decision_evidence_id")
    _string(config["design_status"], f"{path}.design_status", choices=("proposal",))
    observed = (active, passive, gravity, tools, release_status, gate_id)
    expected = (
        profile["active"],
        profile["passive"],
        profile["gravity"],
        profile["tools"],
        profile["release"],
        profile["gate"],
    )
    if observed != expected:
        if kind == "pnp_single_head":
            _fail("pnp.release_unsupported", "PnP must remain gated by G5_PNP_FEASIBILITY and unreleased")
        _fail("configuration.conflict", f"{kind} does not match its canonical profile")
    if kind in ("pnp_single_head", "passive_multilink") and release["decision_evidence_id"] is not None:
        _fail("release.unsupported", f"{kind} has no RP01 release evidence")
    allowed_pnp_components = (
        "0805",
        "0603",
        "SOT-23",
        "SOIC",
        "TSSOP",
        "moderate_pitch_QFP",
        "connectors",
    )
    if kind == "pnp_single_head":
        if components != allowed_pnp_components:
            _fail("pnp.component_unsupported", "PnP component envelope exceeds the gated RP01 proposal")
    elif components:
        _fail("configuration.conflict", "non-PnP configurations cannot declare a component envelope")
    expected_hash = configuration_digest(config)
    if config["configuration_hash"] != expected_hash:
        _fail("hash.mismatch", "configuration hash does not match canonical configuration bytes")
    envelope = _object(
        config["safety_envelope"],
        f"{path}.safety_envelope",
        required=("duration_limit_s", "current_limits_a", "state_limits"),
        allowed=("duration_limit_s", "current_limits_a", "state_limits"),
    )
    _number(envelope["duration_limit_s"], f"{path}.safety_envelope.duration_limit_s", minimum=0.001, maximum=30.0)
    current_limits = _validate_current_limits(envelope["current_limits_a"], f"{path}.safety_envelope.current_limits_a", active)
    state_limits = _validate_limit_list(envelope["state_limits"], f"{path}.safety_envelope.state_limits")
    expected_state_units = _expected_state_units(active + passive)
    if set(state_limits) != set(expected_state_units):
        _fail("limit.state_identity", f"configuration state envelope must cover {sorted(expected_state_units)}")
    for state, expected_unit in expected_state_units.items():
        if state_limits[state][2] != expected_unit:
            _fail("limit.state_unit", f"{state} must use {expected_unit}")
    return config, current_limits, state_limits


def _validate_inventory(value: Any, config: Mapping[str, Any]) -> Mapping[str, Any]:
    path = "hardware_inventory"
    required = (
        "contract_version",
        "schema_version",
        "contract_type",
        "inventory_id",
        "inventory_revision",
        "inventory_status",
        "identity_scope",
        "platform_revision",
        "configuration_id",
        "configuration_hash",
        "joint_count",
        "controller_firmware_revisions",
        "encoder_identities",
        "power_configuration",
        "guard_configuration",
        "calibration_set_id",
        "components",
        "evidence_level",
    )
    inventory = _object(value, path, required=required, allowed=required)
    _contract_header(inventory, path, "hardware_inventory")
    _identifier(inventory["inventory_id"], f"{path}.inventory_id")
    _string(inventory["inventory_revision"], f"{path}.inventory_revision", choices=(CONTRACT_VERSION,))
    _string(inventory["inventory_status"], f"{path}.inventory_status", choices=("planned_fixture",))
    _string(inventory["identity_scope"], f"{path}.identity_scope", choices=("synthetic_not_as_built",))
    _identifier(inventory["platform_revision"], f"{path}.platform_revision")
    _number(inventory["joint_count"], f"{path}.joint_count", minimum=1, maximum=5, integer=True)
    _identifier(inventory["calibration_set_id"], f"{path}.calibration_set_id")
    _string(inventory["power_configuration"], f"{path}.power_configuration")
    _string(inventory["guard_configuration"], f"{path}.guard_configuration")
    _string(inventory["evidence_level"], f"{path}.evidence_level", choices=VALIDATION_LEVELS)
    firmware = _object(
        inventory["controller_firmware_revisions"],
        f"{path}.controller_firmware_revisions",
        required=("set_id", "status", "revisions"),
        allowed=("set_id", "status", "revisions"),
    )
    _identifier(firmware["set_id"], f"{path}.controller_firmware_revisions.set_id")
    _string(firmware["status"], f"{path}.controller_firmware_revisions.status", choices=("not_installed",))
    active_joint_count = int(config["active_joint_count"])
    joint_count = int(config["active_joint_count"] + config["passive_joint_count"])
    revisions = _array(firmware["revisions"], f"{path}.controller_firmware_revisions.revisions", minimum=active_joint_count, maximum=active_joint_count)
    firmware_joint_ids: list[str] = []
    for index, revision in enumerate(revisions):
        record = _object(revision, f"{path}.controller_firmware_revisions.revisions[{index}]", required=("joint_id", "revision"), allowed=("joint_id", "revision"))
        firmware_joint_ids.append(_string(record["joint_id"], f"{path}.controller_firmware_revisions.revisions[{index}].joint_id"))
        if record["revision"] is not None:
            _string(record["revision"], f"{path}.controller_firmware_revisions.revisions[{index}].revision")
    expected_firmware_ids = [f"joint_{joint}" for joint in range(1, active_joint_count + 1)]
    if sorted(firmware_joint_ids) != expected_firmware_ids:
        _fail("identity.firmware", "firmware revisions must uniquely cover every active joint")
    encoders = _array(inventory["encoder_identities"], f"{path}.encoder_identities", minimum=joint_count, maximum=joint_count)
    encoder_joint_ids: list[str] = []
    for index, encoder in enumerate(encoders):
        record = _object(encoder, f"{path}.encoder_identities[{index}]", required=("joint_id", "model", "asset_id", "identity_status"), allowed=("joint_id", "model", "asset_id", "identity_status"))
        encoder_joint_ids.append(_string(record["joint_id"], f"{path}.encoder_identities[{index}].joint_id"))
        _string(record["model"], f"{path}.encoder_identities[{index}].model")
        if record["asset_id"] is not None:
            _identifier(record["asset_id"], f"{path}.encoder_identities[{index}].asset_id")
        _string(record["identity_status"], f"{path}.encoder_identities[{index}].identity_status", choices=("planned_not_owned",))
    expected_encoder_ids = [f"joint_{joint}" for joint in range(1, joint_count + 1)]
    if sorted(encoder_joint_ids) != expected_encoder_ids:
        _fail("identity.encoder", "encoder identities must uniquely cover every joint")
    components = _array(inventory["components"], f"{path}.components", minimum=1, maximum=32)
    component_ids: list[str] = []
    component_roles: list[str] = []
    for index, component in enumerate(components):
        record = _object(component, f"{path}.components[{index}]", required=("instance_id", "role", "model", "asset_id", "identity_status"), allowed=("instance_id", "role", "model", "asset_id", "identity_status"))
        component_ids.append(_identifier(record["instance_id"], f"{path}.components[{index}].instance_id"))
        component_roles.append(_string(record["role"], f"{path}.components[{index}].role"))
        _string(record["model"], f"{path}.components[{index}].model")
        if record["asset_id"] is not None:
            _identifier(record["asset_id"], f"{path}.components[{index}].asset_id")
        _string(record["identity_status"], f"{path}.components[{index}].identity_status", choices=("planned_not_owned",))
    if len(component_ids) != len(set(component_ids)):
        _fail("identity.component", "component instance identities must be unique")
    if component_roles.count("joint_controller") != active_joint_count or component_roles.count("local_supervisor") != 1 or component_roles.count("independent_power_stop") != 1:
        _fail("identity.component", "planned inventory must identify every joint controller, one supervisor, and one independent stop")
    if inventory["inventory_id"] != config["hardware_inventory_id"]:
        _fail("link.inventory_id", "configuration and inventory identities differ")
    if inventory["configuration_id"] != config["configuration_id"]:
        _fail("link.configuration_id", "inventory configuration identity conflicts")
    if inventory["configuration_hash"] != config["configuration_hash"]:
        _fail("link.configuration_hash", "inventory configuration hash conflicts")
    if inventory["calibration_set_id"] != config["calibration_set_id"]:
        _fail("link.calibration", "inventory calibration set conflicts")
    if firmware["set_id"] != config["controller_firmware_set_id"]:
        _fail("link.firmware", "inventory firmware set conflicts")
    if inventory["joint_count"] != joint_count:
        _fail("configuration.conflict", "inventory joint count conflicts")
    if inventory["evidence_level"] != "static":
        _fail("evidence.level_conflated", "planned inventory evidence must be static")
    return inventory


def _validate_plant(value: Any, config: Mapping[str, Any]) -> Mapping[str, Any]:
    path = "plant_model"
    required = (
        "contract_version",
        "schema_version",
        "contract_type",
        "plant_model_id",
        "plant_model_revision",
        "configuration_id",
        "configuration_hash",
        "link_lengths_m",
        "link_masses_kg",
        "inertia_kg_m2",
        "joint_friction_model",
        "transmission_ratios",
        "encoder_zero_offsets_rad",
        "parameter_source",
        "uncertainty",
        "evidence_level",
    )
    plant = _object(value, path, required=required, allowed=required)
    _contract_header(plant, path, "plant_model")
    _identifier(plant["plant_model_id"], f"{path}.plant_model_id")
    _string(plant["plant_model_revision"], f"{path}.plant_model_revision", choices=(CONTRACT_VERSION,))
    link_count = max(1, int(config["active_joint_count"] + config["passive_joint_count"]))
    for field, minimum, maximum in (
        ("link_lengths_m", 0.001, 2.0),
        ("link_masses_kg", 0.001, 20.0),
        ("inertia_kg_m2", 0.000001, 20.0),
    ):
        values = _array(plant[field], f"{path}.{field}", minimum=link_count, maximum=link_count)
        for index, item in enumerate(values):
            _number(item, f"{path}.{field}[{index}]", minimum=minimum, maximum=maximum)
    friction = _array(plant["joint_friction_model"], f"{path}.joint_friction_model", minimum=link_count, maximum=link_count)
    friction_joint_ids: list[str] = []
    for index, item in enumerate(friction):
        record = _object(item, f"{path}.joint_friction_model[{index}]", required=("joint_id", "model", "viscous_nm_s_rad", "coulomb_nm"), allowed=("joint_id", "model", "viscous_nm_s_rad", "coulomb_nm"))
        friction_joint_ids.append(_string(record["joint_id"], f"{path}.joint_friction_model[{index}].joint_id"))
        _string(record["model"], f"{path}.joint_friction_model[{index}].model", choices=("viscous_plus_coulomb",))
        _number(record["viscous_nm_s_rad"], f"{path}.joint_friction_model[{index}].viscous_nm_s_rad", minimum=0, maximum=10)
        _number(record["coulomb_nm"], f"{path}.joint_friction_model[{index}].coulomb_nm", minimum=0, maximum=10)
    expected_friction_ids = [f"joint_{joint}" for joint in range(1, link_count + 1)]
    if sorted(friction_joint_ids) != expected_friction_ids:
        _fail("identity.friction", "friction identities must uniquely cover every joint")
    ratios = _array(plant["transmission_ratios"], f"{path}.transmission_ratios", minimum=int(config["active_joint_count"]), maximum=int(config["active_joint_count"]))
    for index, ratio in enumerate(ratios):
        _number(ratio, f"{path}.transmission_ratios[{index}]", minimum=0.1, maximum=100)
    offsets = _array(plant["encoder_zero_offsets_rad"], f"{path}.encoder_zero_offsets_rad", minimum=link_count, maximum=link_count)
    for index, offset in enumerate(offsets):
        _number(offset, f"{path}.encoder_zero_offsets_rad[{index}]", minimum=-6.4, maximum=6.4)
    _string(plant["parameter_source"], f"{path}.parameter_source", choices=("deterministic_nominal_fixture",))
    uncertainty = _array(plant["uncertainty"], f"{path}.uncertainty", minimum=1, maximum=32)
    for index, item in enumerate(uncertainty):
        record = _object(item, f"{path}.uncertainty[{index}]", required=("parameter", "plus_minus", "unit", "basis"), allowed=("parameter", "plus_minus", "unit", "basis"))
        _string(record["parameter"], f"{path}.uncertainty[{index}].parameter")
        _number(record["plus_minus"], f"{path}.uncertainty[{index}].plus_minus", minimum=0, maximum=100)
        _string(record["unit"], f"{path}.uncertainty[{index}].unit")
        _string(record["basis"], f"{path}.uncertainty[{index}].basis", choices=("assumed_not_measured",))
    _string(plant["evidence_level"], f"{path}.evidence_level", choices=VALIDATION_LEVELS)
    if plant["configuration_id"] != config["configuration_id"]:
        _fail("link.configuration_id", "plant configuration identity conflicts")
    if plant["configuration_hash"] != config["configuration_hash"]:
        _fail("link.configuration_hash", "plant configuration hash conflicts")
    if plant["evidence_level"] != "static":
        _fail("evidence.level_conflated", "nominal fixture parameters are static evidence")
    return plant


def _validate_experiment(
    value: Any,
    config: Mapping[str, Any],
    config_currents: Mapping[str, float],
    config_states: Mapping[str, tuple[float, float, str]],
) -> tuple[Mapping[str, Any], dict[str, float], dict[str, tuple[float, float, str]]]:
    path = "experiment"
    required = (
        "contract_version",
        "schema_version",
        "contract_type",
        "experiment_id",
        "experiment_revision",
        "configuration_id",
        "configuration_hash",
        "inventory_id",
        "plant_model_id",
        "controller_revision",
        "execution_domain",
        "requested_action",
        "sample_rate_hz",
        "duration_limit_s",
        "current_limits_a",
        "position_or_state_limits",
        "abort_conditions",
        "required_artifacts",
        "acceptance_metrics",
        "timeout_behavior",
        "cancellation_behavior",
        "restart_behavior",
    )
    experiment = _object(value, path, required=required, allowed=required)
    _contract_header(experiment, path, "experiment")
    _identifier(experiment["experiment_id"], f"{path}.experiment_id")
    _string(experiment["experiment_revision"], f"{path}.experiment_revision", choices=(CONTRACT_VERSION,))
    _identifier(experiment["inventory_id"], f"{path}.inventory_id")
    _identifier(experiment["plant_model_id"], f"{path}.plant_model_id")
    _identifier(experiment["controller_revision"], f"{path}.controller_revision")
    _string(experiment["execution_domain"], f"{path}.execution_domain", choices=("contract_only", "simulated", "protocol_replay", "physical"))
    _string(experiment["requested_action"], f"{path}.requested_action", choices=("validate_contracts", "simulate", "replay", "physical_experiment"))
    _number(experiment["sample_rate_hz"], f"{path}.sample_rate_hz", minimum=1, maximum=10_000)
    duration = _number(experiment["duration_limit_s"], f"{path}.duration_limit_s", minimum=0.001, maximum=30)
    currents = _validate_current_limits(experiment["current_limits_a"], f"{path}.current_limits_a", int(config["active_joint_count"]))
    states = _validate_limit_list(experiment["position_or_state_limits"], f"{path}.position_or_state_limits")
    if set(states) != set(config_states):
        _fail("limit.state_identity", "experiment state limits must cover the complete configuration state envelope")
    aborts = _array(experiment["abort_conditions"], f"{path}.abort_conditions", minimum=4, maximum=16)
    required_aborts = {"command_timeout", "current_limit", "state_envelope", "operator_request"}
    abort_values = [
        _string(item, f"{path}.abort_conditions[]", choices=required_aborts)
        for item in aborts
    ]
    if len(abort_values) != len(set(abort_values)) or set(abort_values) != required_aborts:
        _fail("safety.abort_conditions", "experiment lacks mandatory abort conditions")
    artifacts = _array(experiment["required_artifacts"], f"{path}.required_artifacts", minimum=4, maximum=16)
    required_artifacts = {"raw_telemetry", "event_log", "metric_report", "acceptance_map"}
    artifact_values = [
        _string(item, f"{path}.required_artifacts[]", choices=required_artifacts)
        for item in artifacts
    ]
    if len(artifact_values) != len(set(artifact_values)) or set(artifact_values) != required_artifacts:
        _fail("artifact.required", "experiment lacks mandatory artifacts")
    metrics = _array(experiment["acceptance_metrics"], f"{path}.acceptance_metrics", minimum=1, maximum=32)
    metric_ids: list[str] = []
    for index, metric in enumerate(metrics):
        record = _object(metric, f"{path}.acceptance_metrics[{index}]", required=("metric_id", "operator", "threshold", "unit"), allowed=("metric_id", "operator", "threshold", "unit"))
        metric_ids.append(_identifier(record["metric_id"], f"{path}.acceptance_metrics[{index}].metric_id"))
        _string(record["operator"], f"{path}.acceptance_metrics[{index}].operator", choices=("eq", "lte", "gte"))
        if not isinstance(record["threshold"], (str, int, float)) or isinstance(record["threshold"], bool):
            _fail("field.type", f"{path}.acceptance_metrics[{index}].threshold has invalid type")
        _string(record["unit"], f"{path}.acceptance_metrics[{index}].unit")
    if len(metric_ids) != len(set(metric_ids)):
        _fail("identity.metric", "experiment acceptance metric identities must be unique")
    observed_metrics = {
        record["metric_id"]: (record["operator"], record["threshold"], record["unit"])
        for record in metrics
    }
    if observed_metrics != STATIC_ACCEPTANCE_METRICS:
        _fail("claim.metric_conflated", "RP01 static fixtures may claim only schema and identity-link validation")
    _string(experiment["timeout_behavior"], f"{path}.timeout_behavior", choices=("request_abort_and_preserve_partial_artifacts",))
    _string(experiment["cancellation_behavior"], f"{path}.cancellation_behavior", choices=("request_abort_and_preserve_partial_artifacts",))
    _string(experiment["restart_behavior"], f"{path}.restart_behavior", choices=("require_new_authorization_and_preserve_prior_result",))
    if experiment["configuration_id"] != config["configuration_id"]:
        _fail("link.configuration_id", "experiment configuration identity conflicts")
    if experiment["configuration_hash"] != config["configuration_hash"]:
        _fail("link.configuration_hash", "experiment configuration hash conflicts")
    if experiment["inventory_id"] != config["hardware_inventory_id"]:
        _fail("link.inventory_id", "experiment inventory identity conflicts")
    if experiment["controller_revision"] != "not_implemented":
        _fail("claim.controller", "RP01 has no implemented controller revision")
    if experiment["execution_domain"] != "contract_only" or experiment["requested_action"] != "validate_contracts":
        _fail("authorization.physical_forbidden", "RP01 fixtures are contract-only and cannot request execution")
    if duration > float(config["safety_envelope"]["duration_limit_s"]):
        _fail("limit.duration.exceeded", "experiment duration exceeds the configuration envelope")
    for joint_id, limit in currents.items():
        if limit > config_currents[joint_id]:
            _fail("limit.current.exceeded", f"{joint_id} current exceeds the configuration envelope")
    for state, (lower, upper, unit) in states.items():
        allowed_lower, allowed_upper, allowed_unit = config_states[state]
        if unit != allowed_unit:
            _fail("limit.state_unit", f"{state} unit conflicts with the configuration envelope")
        if lower < allowed_lower or upper > allowed_upper:
            _fail("limit.state.exceeded", f"{state} exceeds the configuration envelope")
    return experiment, currents, states


def _validate_authorization(value: Any, config: Mapping[str, Any], experiment: Mapping[str, Any]) -> Mapping[str, Any]:
    path = "run_authorization"
    required = (
        "contract_version",
        "schema_version",
        "contract_type",
        "authorization_id",
        "authorization_revision",
        "experiment_id",
        "configuration_id",
        "configuration_hash",
        "operator",
        "authorization_status",
        "physical_run_authorized",
        "local_presence_confirmed",
        "preflight_checklist_revision",
        "guard_state",
        "e_stop_test_result",
        "permitted_configuration",
        "maximum_energy_class",
        "issued_at",
        "expiration",
    )
    authorization = _object(value, path, required=required, allowed=required)
    _contract_header(authorization, path, "run_authorization")
    _identifier(authorization["authorization_id"], f"{path}.authorization_id")
    _string(authorization["authorization_revision"], f"{path}.authorization_revision", choices=(CONTRACT_VERSION,))
    _identifier(authorization["operator"], f"{path}.operator")
    _string(authorization["authorization_status"], f"{path}.authorization_status", choices=("withheld", "authorized"))
    physical = _boolean(authorization["physical_run_authorized"], f"{path}.physical_run_authorized")
    local = _boolean(authorization["local_presence_confirmed"], f"{path}.local_presence_confirmed")
    _identifier(authorization["preflight_checklist_revision"], f"{path}.preflight_checklist_revision")
    _string(authorization["guard_state"], f"{path}.guard_state", choices=("not_evaluated", "accepted"))
    _string(authorization["e_stop_test_result"], f"{path}.e_stop_test_result", choices=("not_run", "passed"))
    _string(authorization["permitted_configuration"], f"{path}.permitted_configuration")
    _string(authorization["maximum_energy_class"], f"{path}.maximum_energy_class", choices=("none", "low_energy", "guarded"))
    issued = _timestamp(authorization["issued_at"], f"{path}.issued_at")
    expires = _timestamp(authorization["expiration"], f"{path}.expiration")
    if expires <= issued:
        _fail("authorization.expiration", "authorization expiration must follow issue time")
    if authorization["experiment_id"] != experiment["experiment_id"]:
        _fail("link.experiment_id", "authorization experiment identity conflicts")
    if authorization["configuration_id"] != config["configuration_id"]:
        _fail("link.configuration_id", "authorization configuration identity conflicts")
    if authorization["configuration_hash"] != config["configuration_hash"]:
        _fail("link.configuration_hash", "authorization configuration hash conflicts")
    if authorization["permitted_configuration"] != config["configuration_id"]:
        _fail("authorization.configuration", "authorization does not permit the configuration")
    if experiment["execution_domain"] == "contract_only":
        if authorization["authorization_status"] != "withheld" or physical or local:
            _fail("authorization.conflated", "contract-only fixtures must explicitly withhold physical authorization")
        if authorization["guard_state"] != "not_evaluated" or authorization["e_stop_test_result"] != "not_run" or authorization["maximum_energy_class"] != "none":
            _fail("authorization.conflated", "contract-only fixtures cannot claim physical preflight")
    elif not (
        authorization["authorization_status"] == "authorized"
        and physical
        and local
        and authorization["guard_state"] == "accepted"
        and authorization["e_stop_test_result"] == "passed"
    ):
        _fail("authorization.local_required", "non-contract execution requires explicit local authorization")
    return authorization


def _validate_telemetry(value: Any, config: Mapping[str, Any], experiment: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    path = "telemetry_events"
    records = _array(value, path, minimum=2, maximum=128)
    sequences: list[int] = []
    monotonic: list[int] = []
    timestamps: list[datetime] = []
    seen_ids: set[str] = set()
    event_types: list[str] = []
    allowed = (
        "contract_version",
        "schema_version",
        "contract_type",
        "record_id",
        "experiment_id",
        "configuration_hash",
        "sequence",
        "timestamp",
        "monotonic_offset_ns",
        "record_kind",
        "lifecycle_state",
        "event_type",
        "payload",
        "evidence_level",
    )
    for index, item in enumerate(records):
        item_path = f"{path}[{index}]"
        record = _object(item, item_path, required=allowed, allowed=allowed)
        _contract_header(record, item_path, "telemetry_event")
        record_id = _identifier(record["record_id"], f"{item_path}.record_id")
        if record_id in seen_ids:
            _fail("telemetry.identity", f"duplicate record ID {record_id}")
        seen_ids.add(record_id)
        if record["experiment_id"] != experiment["experiment_id"]:
            _fail("link.experiment_id", f"{item_path} experiment identity conflicts")
        if record["configuration_hash"] != config["configuration_hash"]:
            _fail("link.configuration_hash", f"{item_path} configuration hash conflicts")
        sequences.append(int(_number(record["sequence"], f"{item_path}.sequence", minimum=0, maximum=1_000_000, integer=True)))
        timestamps.append(_timestamp(record["timestamp"], f"{item_path}.timestamp"))
        monotonic.append(int(_number(record["monotonic_offset_ns"], f"{item_path}.monotonic_offset_ns", minimum=0, maximum=10**15, integer=True)))
        record_kind = _string(record["record_kind"], f"{item_path}.record_kind", choices=("event", "telemetry"))
        state = _string(record["lifecycle_state"], f"{item_path}.lifecycle_state", choices=("drafted", "validated", "awaiting_local_authorization", "armed", "running", "aborting", "safe", "completed", "failed"))
        event_type = _string(record["event_type"], f"{item_path}.event_type", choices=("contract_validated", "authorization_withheld", "validation_progress", "completed", "cancel_requested", "timeout_detected", "aborting", "partial_artifacts_preserved", "failed", "restart_detected", "authorization_invalidated"))
        event_types.append(event_type)
        payload = record["payload"]
        if not isinstance(payload, dict) or len(payload) > 32:
            _fail("field.type", f"{item_path}.payload must be a bounded object")
        _string(record["evidence_level"], f"{item_path}.evidence_level", choices=VALIDATION_LEVELS)
        if state in ("armed", "running", "aborting", "safe"):
            _fail("claim.lifecycle", "RP01 static fixtures cannot claim a physical lifecycle state")
        if record["evidence_level"] != "static":
            _fail("evidence.level_conflated", "fixture telemetry/events must be static")
        event_rules = {
            "contract_validated": ("event", "validated"),
            "validation_progress": ("telemetry", "validated"),
            "authorization_withheld": ("event", "awaiting_local_authorization"),
            "completed": ("event", "completed"),
            "cancel_requested": ("event", "failed"),
            "timeout_detected": ("event", "failed"),
            "aborting": ("event", "aborting"),
            "partial_artifacts_preserved": ("event", "failed"),
            "failed": ("event", "failed"),
            "restart_detected": ("event", "failed"),
            "authorization_invalidated": ("event", "failed"),
        }
        if (record_kind, state) != event_rules[event_type]:
            _fail("telemetry.event_semantics", f"{event_type} has an incompatible record kind or lifecycle state")
        if event_type == "contract_validated" and payload != {"schema_count": 8}:
            _fail("telemetry.payload", "contract_validated must record all eight schemas")
        if event_type == "validation_progress":
            fraction = payload.get("fraction")
            if set(payload) != {"fraction", "unit"} or payload.get("unit") != "ratio" or isinstance(fraction, bool) or not isinstance(fraction, (int, float)) or not 0 <= fraction <= 1:
                _fail("telemetry.payload", "validation progress must contain a bounded ratio")
        if event_type == "authorization_withheld" and payload != {"physical_run_authorized": False}:
            _fail("telemetry.payload", "authorization_withheld cannot imply physical authorization")
        if event_type == "completed" and payload != {"validation_level": "static"}:
            _fail("telemetry.payload", "completion must retain the static validation level")
        if event_type in {"cancel_requested", "timeout_detected", "partial_artifacts_preserved", "failed", "restart_detected", "authorization_invalidated"} and payload != {"retained": True}:
            _fail("telemetry.payload", f"{event_type} must retain its fixture marker")
    if sequences != list(range(len(records))):
        _fail("telemetry.sequence", "record sequences must be contiguous from zero")
    if monotonic != sorted(monotonic) or len(monotonic) != len(set(monotonic)):
        _fail("telemetry.monotonic", "monotonic offsets must strictly increase")
    if timestamps != sorted(timestamps):
        _fail("telemetry.timestamp", "record timestamps must not move backward")
    if event_types.count("contract_validated") != 1 or event_types.count("authorization_withheld") != 1:
        _fail("telemetry.lifecycle", "fixture record set must contain one validation and one withheld-authorization event")
    return records


def _validate_artifact(value: Any, path: str) -> Mapping[str, Any]:
    artifact = _object(value, path, required=("uri", "sha256", "availability", "evidence_level"), allowed=("uri", "sha256", "availability", "evidence_level"))
    try:
        _string(artifact["uri"], f"{path}.uri", pattern=ARTIFACT_URI_PATTERN)
    except ContractError as exc:
        if exc.code not in {"field.type", "field.format"}:
            raise
        _fail("artifact.uri", f"{path}.uri must use the bounded relative fixture URI profile")
    _hash(artifact["sha256"], f"{path}.sha256")
    _string(artifact["availability"], f"{path}.availability", choices=("embedded", "not_produced"))
    _string(artifact["evidence_level"], f"{path}.evidence_level", choices=VALIDATION_LEVELS)
    return artifact


def _validate_result(
    value: Any,
    config: Mapping[str, Any],
    experiment: Mapping[str, Any],
    authorization: Mapping[str, Any],
    records: list[Mapping[str, Any]],
) -> Mapping[str, Any]:
    path = "result"
    required = (
        "contract_version",
        "schema_version",
        "contract_type",
        "result_id",
        "result_revision",
        "experiment_id",
        "exact_configuration_hash",
        "authorization_id",
        "start_timestamp",
        "stop_timestamp",
        "termination_reason",
        "raw_telemetry_artifact",
        "metric_artifact",
        "acceptance_map",
        "anomalies",
        "residual_risks",
        "unperformed_validation",
        "partial_artifacts_preserved",
        "physical_safe_state_claimed",
        "recovery",
        "evidence_level",
    )
    result = _object(value, path, required=required, allowed=required)
    _contract_header(result, path, "result")
    _identifier(result["result_id"], f"{path}.result_id")
    _string(result["result_revision"], f"{path}.result_revision", choices=(CONTRACT_VERSION,))
    start = _timestamp(result["start_timestamp"], f"{path}.start_timestamp")
    stop = _timestamp(result["stop_timestamp"], f"{path}.stop_timestamp")
    if stop < start:
        _fail("result.time", "result stop precedes start")
    authorization_issued = _timestamp(authorization["issued_at"], "run_authorization.issued_at")
    authorization_expiration = _timestamp(authorization["expiration"], "run_authorization.expiration")
    if start < authorization_issued or stop > authorization_expiration:
        _fail("authorization.expired", "result interval falls outside the authorization decision interval")
    reason = _string(result["termination_reason"], f"{path}.termination_reason", choices=("completed", "cancelled", "timeout", "validation_rejected", "failed"))
    raw_artifact = _validate_artifact(result["raw_telemetry_artifact"], f"{path}.raw_telemetry_artifact")
    metric_artifact = _validate_artifact(result["metric_artifact"], f"{path}.metric_artifact")
    acceptance = _array(result["acceptance_map"], f"{path}.acceptance_map", minimum=1, maximum=64)
    acceptance_metric_ids: list[str] = []
    for index, item in enumerate(acceptance):
        record = _object(item, f"{path}.acceptance_map[{index}]", required=("metric_id", "outcome", "evidence_level"), allowed=("metric_id", "outcome", "evidence_level"))
        acceptance_metric_ids.append(_identifier(record["metric_id"], f"{path}.acceptance_map[{index}].metric_id"))
        _string(record["outcome"], f"{path}.acceptance_map[{index}].outcome", choices=("pass", "fail", "not_run"))
        if record["evidence_level"] != "static":
            _fail("evidence.level_conflated", "fixture acceptance outcomes must remain static")
    expected_metric_ids = [metric["metric_id"] for metric in experiment["acceptance_metrics"]]
    if len(acceptance_metric_ids) != len(set(acceptance_metric_ids)) or set(acceptance_metric_ids) != set(expected_metric_ids):
        _fail("result.acceptance_map", "result acceptance map must uniquely cover every requested metric")
    for field in ("anomalies", "residual_risks", "unperformed_validation"):
        for index, item in enumerate(_array(result[field], f"{path}.{field}", minimum=1, maximum=64)):
            _string(item, f"{path}.{field}[{index}]")
    partial = _boolean(result["partial_artifacts_preserved"], f"{path}.partial_artifacts_preserved")
    if _boolean(result["physical_safe_state_claimed"], f"{path}.physical_safe_state_claimed"):
        _fail("evidence.safe_state_conflated", "static results cannot claim a physical safe state")
    recovery = _object(
        result["recovery"],
        f"{path}.recovery",
        required=("restart_detected", "prior_result_id", "new_authorization_required"),
        allowed=("restart_detected", "prior_result_id", "new_authorization_required"),
    )
    restart = _boolean(recovery["restart_detected"], f"{path}.recovery.restart_detected")
    if recovery["prior_result_id"] is not None:
        _identifier(recovery["prior_result_id"], f"{path}.recovery.prior_result_id")
    new_authorization = _boolean(recovery["new_authorization_required"], f"{path}.recovery.new_authorization_required")
    _string(result["evidence_level"], f"{path}.evidence_level", choices=VALIDATION_LEVELS)
    if result["experiment_id"] != experiment["experiment_id"]:
        _fail("link.experiment_id", "result experiment identity conflicts")
    if result["exact_configuration_hash"] != config["configuration_hash"]:
        _fail("link.configuration_hash", "result configuration hash conflicts")
    if result["authorization_id"] != authorization["authorization_id"]:
        _fail("link.authorization_id", "result authorization identity conflicts")
    if result["evidence_level"] != "static" or raw_artifact["evidence_level"] != "static" or metric_artifact["evidence_level"] != "static":
        _fail("evidence.level_conflated", "RP01 results and artifacts must be static")
    if raw_artifact["sha256"] != sha256_digest(records):
        _fail("artifact.digest", "raw telemetry artifact digest conflicts with embedded records")
    if metric_artifact["sha256"] != sha256_digest(acceptance):
        _fail("artifact.digest", "metric artifact digest conflicts with acceptance map")
    event_types = [record["event_type"] for record in records]
    record_times = [_timestamp(record["timestamp"], "telemetry_events[].timestamp") for record in records]
    if any(timestamp < start or timestamp > stop for timestamp in record_times):
        _fail("result.time", "telemetry/event timestamp falls outside the result interval")
    baseline_events = {"contract_validated", "validation_progress", "authorization_withheld"}
    allowed_events = {
        "completed": baseline_events | {"completed"},
        "cancelled": baseline_events | {"cancel_requested", "partial_artifacts_preserved"},
        "timeout": baseline_events | {"timeout_detected", "partial_artifacts_preserved"},
        "validation_rejected": baseline_events | {"failed", "partial_artifacts_preserved"},
        "failed": baseline_events | {"failed", "partial_artifacts_preserved"},
    }[reason]
    if restart:
        if reason != "completed":
            _fail("lifecycle.recovery", "restart recovery cannot be conflated with a terminal failure reason")
        allowed_events |= {"restart_detected", "authorization_invalidated"}
    incompatible_events = set(event_types) - allowed_events
    if incompatible_events:
        code = "lifecycle.completion" if reason == "completed" else f"lifecycle.{reason}"
        _fail(code, f"{reason} result contains incompatible events {sorted(incompatible_events)}")
    validated_index = event_types.index("contract_validated")
    authorization_index = event_types.index("authorization_withheld")
    if validated_index >= authorization_index:
        _fail("telemetry.lifecycle", "contract validation must precede the withheld-authorization decision")
    if reason == "completed" and (not event_types or event_types[-1] != "completed"):
        _fail("lifecycle.completion", "completed results require a final completion event")
    if reason == "cancelled" and not {"cancel_requested", "partial_artifacts_preserved"} <= set(event_types):
        _fail("lifecycle.cancellation", "cancelled results require cancellation and partial-artifact events")
    if reason == "timeout" and not {"timeout_detected", "partial_artifacts_preserved"} <= set(event_types):
        _fail("lifecycle.timeout", "timeout results require timeout and partial-artifact events")
    if reason in ("cancelled", "timeout") and (event_types[-1] != "partial_artifacts_preserved" or "completed" in event_types):
        _fail(f"lifecycle.{reason if reason == 'timeout' else 'cancellation'}", f"{reason} result has an incompatible terminal event")
    if reason == "cancelled" and event_types.index("cancel_requested") >= event_types.index("partial_artifacts_preserved"):
        _fail("lifecycle.cancellation", "cancellation must precede partial-artifact preservation")
    if reason == "timeout" and event_types.index("timeout_detected") >= event_types.index("partial_artifacts_preserved"):
        _fail("lifecycle.timeout", "timeout detection must precede partial-artifact preservation")
    if reason in ("validation_rejected", "failed") and (not event_types or event_types[-1] != "failed"):
        _fail("lifecycle.failure", "failed validation requires a final failed event")
    if reason in ("cancelled", "timeout", "failed") and not partial:
        _fail("lifecycle.partial_artifacts", "non-success termination must preserve partial artifacts")
    if restart:
        if recovery["prior_result_id"] is None or not new_authorization:
            _fail("lifecycle.recovery", "restart recovery requires predecessor identity and new authorization")
        if not {"restart_detected", "authorization_invalidated"} <= set(event_types):
            _fail("lifecycle.recovery", "restart recovery events are incomplete")
        if event_types.index("restart_detected") >= event_types.index("authorization_invalidated"):
            _fail("lifecycle.recovery", "restart detection must precede authorization invalidation")
    elif recovery["prior_result_id"] is not None or new_authorization:
        _fail("lifecycle.recovery", "non-restart result cannot carry recovery claims")
    return result


def _validate_evidence(value: Any, config: Mapping[str, Any], result: Mapping[str, Any]) -> Mapping[str, Any]:
    path = "evidence"
    required = (
        "contract_version",
        "schema_version",
        "contract_type",
        "evidence_id",
        "evidence_revision",
        "result_id",
        "configuration_hash",
        "validation_level",
        "claim_boundary",
        "required_statements",
        "artifacts",
        "acceptance_items",
        "residual_risks",
        "unperformed_validation",
    )
    evidence = _object(value, path, required=required, allowed=required)
    _contract_header(evidence, path, "evidence")
    _identifier(evidence["evidence_id"], f"{path}.evidence_id")
    _string(evidence["evidence_revision"], f"{path}.evidence_revision", choices=(CONTRACT_VERSION,))
    level = _string(evidence["validation_level"], f"{path}.validation_level", choices=VALIDATION_LEVELS)
    boundary = _string(evidence["claim_boundary"], f"{path}.claim_boundary")
    if "software contract" not in boundary.lower() or "no physical capability" not in boundary.lower():
        _fail("evidence.claim_boundary", "evidence must state the software-only physical boundary")
    statements = tuple(_array(evidence["required_statements"], f"{path}.required_statements", minimum=5, maximum=5))
    if statements != REQUIRED_EVIDENCE_STATEMENTS:
        _fail("evidence.statements", "required evidence statements are missing or reordered")
    artifacts = _array(evidence["artifacts"], f"{path}.artifacts", minimum=2, maximum=16)
    for index, artifact in enumerate(artifacts):
        validated = _validate_artifact(artifact, f"{path}.artifacts[{index}]")
        if validated["evidence_level"] != "static":
            _fail("evidence.level_conflated", "fixture evidence artifacts must be static")
    acceptance_items = tuple(
        _string(item, f"{path}.acceptance_items[{index}]")
        for index, item in enumerate(_array(evidence["acceptance_items"], f"{path}.acceptance_items", minimum=1, maximum=64))
    )
    if acceptance_items != STATIC_ACCEPTANCE_ITEMS:
        _fail("evidence.acceptance_items", "RP01 evidence may retain only the four static contract acceptance items")
    for field in ("residual_risks", "unperformed_validation"):
        for index, item in enumerate(_array(evidence[field], f"{path}.{field}", minimum=1, maximum=64)):
            _string(item, f"{path}.{field}[{index}]")
    if evidence["result_id"] != result["result_id"]:
        _fail("link.result_id", "evidence result identity conflicts")
    if evidence["configuration_hash"] != config["configuration_hash"]:
        _fail("link.configuration_hash", "evidence configuration hash conflicts")
    if level != "static":
        _fail("evidence.level_conflated", "software contract fixtures cannot claim a non-static level")
    result_digest = sha256_digest(result)
    if not any(artifact["sha256"] == result_digest for artifact in artifacts):
        _fail("artifact.digest", "evidence does not retain the embedded result digest")
    return evidence


def validate_contract_set(value: Any) -> Mapping[str, Any]:
    """Validate one complete RP01 fixture without mutating it."""

    _validate_resource_limits(value)
    required = (
        "fixture_version",
        "fixture_id",
        "fixture_classification",
        "canonicalization",
        "configuration",
        "hardware_inventory",
        "plant_model",
        "experiment",
        "run_authorization",
        "telemetry_events",
        "result",
        "evidence",
    )
    if not isinstance(value, dict):
        _fail("document.root", "contract set must be an object")
    if "run_authorization" not in value:
        _fail("authorization.missing", "every contract set requires an explicit authorization decision")
    if "configuration" in value and isinstance(value["configuration"], dict) and not value["configuration"].get("configuration_id"):
        _fail("identity.missing", "configuration identity is absent")
    bundle = _object(value, "contract_set", required=required, allowed=required)
    if bundle["fixture_version"] != FIXTURE_VERSION:
        _fail("version.unsupported", f"fixture_version must be {FIXTURE_VERSION}")
    _identifier(bundle["fixture_id"], "contract_set.fixture_id")
    _string(bundle["fixture_classification"], "contract_set.fixture_classification", choices=("software_contract_only",))
    _string(bundle["canonicalization"], "contract_set.canonicalization", choices=(CANONICALIZATION_ID,))
    config, config_currents, config_states = _validate_configuration(bundle["configuration"])
    inventory = _validate_inventory(bundle["hardware_inventory"], config)
    plant = _validate_plant(bundle["plant_model"], config)
    experiment, _, _ = _validate_experiment(bundle["experiment"], config, config_currents, config_states)
    if experiment["inventory_id"] != inventory["inventory_id"]:
        _fail("link.inventory_id", "experiment inventory link conflicts")
    if experiment["plant_model_id"] != plant["plant_model_id"]:
        _fail("link.plant_model_id", "experiment plant-model link conflicts")
    authorization = _validate_authorization(bundle["run_authorization"], config, experiment)
    records = _validate_telemetry(bundle["telemetry_events"], config, experiment)
    result = _validate_result(bundle["result"], config, experiment, authorization, records)
    _validate_evidence(bundle["evidence"], config, result)
    return bundle
