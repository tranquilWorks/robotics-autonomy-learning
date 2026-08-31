# ADR-0001: Target-owned strict JSON contract baseline

Status: accepted for RP01 static validation.

## Decision

The robotics target owns eight Draft 2020-12 JSON schemas, a pure standard-library validator, complete deterministic fixture bundles, and configuration digests under `ral-json-c14n-v1`. Contract and fixture version `1.0.0` reject unknown versions and fields. The configuration hash excludes only its own `configuration_hash` member. The canonicalizer defines key ordering, Unicode normalization, whitespace, exact control/quotation/reverse-solidus escaping, direct UTF-8 scalar emission, booleans, negative zero, integral floats, and exponent spelling rather than relying on unspecified serializer defaults.

Every fixture includes an explicit withheld authorization decision and a scalar evidence level. Cross-document identity and limit checks are part of validation; schema shape alone is insufficient.

## Reasons

- The target CI installs no third-party Python packages.
- Deterministic fixtures must be portable to future controls and orchestration consumers.
- Strict identities prevent planned hardware, configurations, calibrations, and evidence levels from being conflated.
- An explicit withheld decision prevents absence from looking like authorization.

## Consequences

Consumers must implement the same canonicalization profile, validate golden hashes, and opt into new versions. Later compatible evolution is side by side rather than permissive field acceptance. The synchronous offline validator has bounded parsing but no runtime job timeout or cancellation mechanism; the data contracts describe future lifecycle records without pretending to execute them.
