# RP01 implementation plan — reference-platform contract baseline

## Outcome and boundary

Add a target-owned, versioned, deterministic software contract set for the five canonical reference-platform configurations. Preserve the 24-module curriculum byte-for-byte and perform no hardware, device, credential, network-service, fabrication, procurement, energization, or cross-repository action.

## Owned changes

- `contracts/reference-platform/`: schema index, eight v1 schemas, compatibility record.
- `reference-platform/`: validator, deterministic generator, valid/invalid fixtures, ownership/safety/compatibility/handoff documentation.
- `tests/test_reference_platform*.py`: schema, hash, rejection, evidence, isolation, compatibility, resource-bound, and no-access regression tests.
- `README.md` and `START_HERE.md`: narrow links only.
- `docs/evidence/RP01-2026-08-31.md`: retained evidence and limitations.

## Acceptance and validation

The validator must reject missing or conflicting identity, absent authorization, absent or excessive current/duration/state limits, unsupported PnP release, evidence-level conflation, malformed/duplicate/non-finite JSON, unknown versions/fields, inconsistent links, and resource excess. Five complete software-only fixtures must round-trip and retain golden configuration hashes.

Focused tests precede the exact contract, quick, and full commands in the active batch. Scope and curriculum hashes are compared with implementation-start revision `ae5764598da09f8c8b9d3629b8f64369c9c7025e`; the injected active-batch input is preserved unchanged.

## Rollback

Revert only RP01 additions and the two root-document links. Preserve the curriculum and control-plane history, and retain the rejected contract revision and reason. No migration, external state, device state, or consumer state exists to undo.
