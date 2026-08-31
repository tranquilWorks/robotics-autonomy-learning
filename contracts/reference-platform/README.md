# Reference-platform contract family

This directory is the target-owned interoperability surface for reference-platform contract version `1.0.0`.

[`contract-index.json`](contract-index.json) is authoritative for the eight schema paths, evidence-level vocabulary, fixture bundle version, and `ral-json-c14n-v1` serialization. Schemas under [`v1/`](v1/) are strict Draft 2020-12 JSON schemas with explicit type and version identity.

Shape validation is only one layer. [`../../reference-platform/reference_platform/contracts.py`](../../reference-platform/reference_platform/contracts.py) enforces deterministic parsing, configuration profiles, canonical hashes, cross-document identities, bounded envelopes, withheld physical authorization, lifecycle records, artifact digests, and evidence separation using the Python standard library.

The schemas describe future exchange data; they do not authorize or perform a run. RP01 fixtures remain proposals with synthetic planned inventory and static evidence.
