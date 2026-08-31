#!/usr/bin/env python3
"""Validate or hash local RP01 reference-platform JSON fixtures."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from reference_platform import (
    ContractError,
    configuration_digest,
    load_json,
    validate_contract_set,
    validate_schema_catalog,
)

ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = ROOT.parent
FIXTURE_ROOT = ROOT / "fixtures"
CONTRACT_ROOT = REPOSITORY_ROOT / "contracts" / "reference-platform"


def _validate(path: Path) -> int:
    try:
        value = load_json(path, allowed_root=REPOSITORY_ROOT)
        validate_contract_set(value)
    except ContractError as exc:
        print(f"REJECT {path}: {exc}", file=sys.stderr)
        return 1
    print(f"VALID {path}: {value['configuration']['configuration_hash']}")
    return 0


def _check_all() -> int:
    try:
        validate_schema_catalog(CONTRACT_ROOT)
    except ContractError as exc:
        print(f"SCHEMA REJECT: {exc}", file=sys.stderr)
        return 1
    paths = sorted((FIXTURE_ROOT / "valid").glob("*.json"))
    failures = sum(_validate(path) for path in paths)
    if failures:
        print(f"CHECK FAIL: {failures} of {len(paths)} valid fixtures rejected", file=sys.stderr)
        return 1
    print(f"CHECK PASS: 8 schemas, {len(paths)} valid fixtures")
    return 0


def _hash(path: Path) -> int:
    try:
        value = load_json(path, allowed_root=REPOSITORY_ROOT)
        configuration = value.get("configuration", value) if isinstance(value, dict) else value
        print(configuration_digest(configuration))
    except ContractError as exc:
        print(f"REJECT {path}: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate_parser = commands.add_parser("validate", help="validate one contract-set fixture")
    validate_parser.add_argument("path", type=Path)
    commands.add_parser("check-all", help="validate every retained valid fixture")
    hash_parser = commands.add_parser("hash", help="print a configuration digest")
    hash_parser.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    if args.command == "validate":
        return _validate(args.path)
    if args.command == "check-all":
        return _check_all()
    return _hash(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
